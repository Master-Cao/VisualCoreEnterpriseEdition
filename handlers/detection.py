# -*- coding: utf-8 -*-

import time
import json
import os
import numpy as np

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from services.shared import ImageUtils, SftpHelper
from services.detection import DetectionVisualizer, RoiProcessor, TargetSelector, CoordinateProcessor


def handle_model_test(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    logger = getattr(ctx, "logger", None)
    try:
        det = ctx.detector
        cam = ctx.camera
        sftp = ctx.sftp
        
        if not det:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="detector",
                messageType=MessageType.ERROR,
                message="detector_not_ready",
                data={},
            )
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={},
            )
        # SFTP是非关键组件，允许为None（禁用时不影响测试功能）
        
        # 使用新的 get_frame 方法，只获取强度图像以加快速度
        result = cam.get_frame(depth=False, intensity=True, camera_params=False)
        img = result.get('intensity_image') if result else None
        
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={},
            )
        
        # 执行检测
        t0 = time.time()
        results = det.detect(img)
        dt = (time.time() - t0) * 1000.0
        count = len(results) if hasattr(results, "__len__") else (1 if results else 0)
        
        # 绘制检测结果到图像上
        vis_img = DetectionVisualizer.draw_detections(
            img, results, 
            class_names=["seasoning", "hand"], 
            show_bbox=False
        )
        
        # 编码为JPG
        jpg = ImageUtils.encode_jpg(vis_img)
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={},
            )
        
        # 上传到SFTP（非关键操作，失败不影响测试结果）
        upload_info = None
        if sftp:
            try:
                upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="detection_test")
                if upload_info:
                    # 获取SFTP配置并构建完整路径
                    sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
                    upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
                elif logger:
                    logger.warning("SFTP上传失败，但继续返回测试结果")
            except Exception as e:
                if logger:
                    logger.warning(f"SFTP上传异常: {e}，但继续返回测试结果")
        else:
            if logger:
                logger.debug("SFTP未启用，跳过图像上传")
        
        # 构建返回数据（SFTP信息可选）
        payload = {
            "detection_count": count,
            "infer_time_ms": round(dt, 1),
            "filename": upload_info.get("filename") if upload_info else None,
            "remote_path": upload_info.get("remote_path") if upload_info else None,
            "remote_rel_path": upload_info.get("remote_rel_path") if upload_info else None,
            "remote_file": upload_info.get("remote_file") if upload_info else None,
            "remote_full_path": upload_info.get("remote_full_path") if upload_info else None,
            "file_size": upload_info.get("file_size") if upload_info else None,
            "image_shape": list(vis_img.shape) if hasattr(vis_img, "shape") else None,
        }
        
        if logger and upload_info:
            try:
                logger.info(
                    f"检测测试完成: {count}个目标, 推理耗时={dt:.1f}ms, 图像已上传: {upload_info.get('filename')}"
                )
            except Exception:
                pass
        
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.SUCCESS,
            message="ok",
            data=payload,
        )
    except Exception as e:
        if logger:
            try:
                logger.error(f"handle_model_test error: {e}")
            except Exception:
                pass
        return MQTTResponse(
            command=VisionCoreCommands.MODEL_TEST.value,
            component="detector",
            messageType=MessageType.ERROR,
            message=str(e),
            data={},
        )



def handle_catch(_req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    """
    抓取命令处理：检测目标、选择最佳目标、计算机器人坐标
    
    流程：
    1. 获取相机数据（深度图、强度图、相机参数）
    2. 执行目标检测
    3. ROI过滤（支持p1roi和p2roi）
    4. 最佳目标选择
    5. 3D坐标计算和坐标转换
    6. 可视化和结果返回
    7. 通过TCP发送响应：p1_flag,p2_flag,x,y,z
    """
    logger = getattr(ctx, "logger", None)
    
    # ===== 性能监控：记录各步骤耗时 =====
    time_start = time.time()
    time_points = {}
    
    try:
        det = ctx.detector
        cam = ctx.camera
        sftp = ctx.sftp
        
        # 验证组件状态
        if not det:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="detector",
                messageType=MessageType.ERROR,
                message="detector_not_ready",
                data={"response": "0,0,0,0,0"},
            )
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={"response": "0,0,0,0,0"},
            )
        # SFTP是非关键组件，允许为None（禁用时不影响检测功能）
        
        # 获取相机数据（深度、强度、参数）
        t0_camera = time.time()
        result = cam.get_frame(depth=True, intensity=True, camera_params=True)
        img = result.get('intensity_image') if result else None
        depth_data = result.get('depthmap') if result else None
        camera_params = result.get('cameraParams') if result else None
        time_points['camera'] = (time.time() - t0_camera) * 1000.0
        
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={"response": "0,0,0,0,0"},
            )
        
        # 执行检测
        t0_detect = time.time()
        detection_results = det.detect(img)
        time_points['detection'] = (time.time() - t0_detect) * 1000.0
        total_count = len(detection_results) if hasattr(detection_results, "__len__") else (1 if detection_results else 0)
        
        # 先绘制检测结果（不包含ROI）
        t0_visualize = time.time()
        vis_img = DetectionVisualizer.draw_detections(
            img, detection_results,
            class_names=["seasoning", "hand"], 
            show_bbox=False
        )
        time_points['visualize_detections'] = (time.time() - t0_visualize) * 1000.0
        
        # 直接从config中获取ROI配置
        t0_roi_setup = time.time()
        roi_cfg = ctx.config.get('roi') or {}
        regions = roi_cfg.get('regions') or []
        min_area = float(roi_cfg.get('minArea', 0))
        
        # 构建ROI配置列表（转换为统一格式）
        height, width = img.shape[:2]
        roi_list = []
        
        for region in regions:
            if not isinstance(region, dict):
                continue
            
            roi_width = int(region.get('width', 120))
            roi_height = int(region.get('height', 140))
            x1 = int(region.get('offsetx', 0))
            y1 = int(region.get('offsety', 0))
            x2 = x1 + roi_width
            y2 = y1 + roi_height
            
            # 限制在图像范围内
            x1 = max(0, min(x1, width))
            y1 = max(0, min(y1, height))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))
            
            roi_config = {
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'priority': region.get('priority', 999),
                'name': region.get('name', f"roi_{len(roi_list)+1}")
            }
            roi_list.append(roi_config)
            
            # 绘制ROI（不同优先级用不同颜色）
            priority = region.get('priority', 999)
            if priority == 1:
                vis_img = DetectionVisualizer.draw_roi(vis_img, roi_config, color=(0, 255, 255), thickness=2)  # 黄色
            elif priority == 2:
                vis_img = DetectionVisualizer.draw_roi(vis_img, roi_config, color=(255, 128, 0), thickness=2)  # 橙色
            else:
                vis_img = DetectionVisualizer.draw_roi(vis_img, roi_config, color=(128, 128, 128), thickness=2)  # 灰色
        
        time_points['roi_setup'] = (time.time() - t0_roi_setup) * 1000.0
        
        # 过滤seasoning目标（只针对类别0）
        t0_filter = time.time()
        seasoning_detections = []
        for det_box in detection_results:
            class_id = int(getattr(det_box, 'class_id', getattr(det_box, 'classId', -1)))
            if class_id == 0:  # seasoning
                seasoning_detections.append(det_box)
        
        # 精简日志：移除详细检测结果输出
        
        # 使用多ROI优先级选择：ROI区域内(仅判断中点) > ROI优先级高 > Mask大于minArea > Mask最大
        best_target = TargetSelector.select_by_multi_roi_priority(
            seasoning_detections,
            roi_list,
            min_area=min_area
        )
        time_points['filter_and_select'] = (time.time() - t0_filter) * 1000.0
        
        # 精简日志：移除最佳目标选择的详细输出
        
        # 统计各ROI中的目标数量（通过中点判断 + 深度阈值递增计数）
        # 逻辑：p_count = ROI内物体总数（基数） + 所有物体的深度增量总和
        # 例如：P1 ROI有3个物体，深度增量分别为1,2,0 → p1_count = 3 + 1 + 2 + 0 = 6
        p1_base_count = 0  # P1 ROI内物体基数
        p2_base_count = 0  # P2 ROI内物体基数
        p1_depth_increment = 0  # P1 ROI深度增量总和
        p2_depth_increment = 0  # P2 ROI深度增量总和
        roi_depth_threshold = float(roi_cfg.get('depthThreshold', 0))
        
        for det_box in seasoning_detections:
            xmin = float(getattr(det_box, 'xmin', 0))
            ymin = float(getattr(det_box, 'ymin', 0))
            xmax = float(getattr(det_box, 'xmax', 0))
            ymax = float(getattr(det_box, 'ymax', 0))
            center_x = 0.5 * (xmin + xmax)
            center_y = 0.5 * (ymin + ymax)
            
            # 遍历roi_list，找到所属ROI（按中点判断）
            matched_roi = None
            for roi in roi_list:
                if RoiProcessor.is_point_in_roi(center_x, center_y, roi):
                    matched_roi = roi
                    break
            
            if matched_roi is None:
                continue
            
            priority = matched_roi.get('priority', 999)
            
            # 累加基数（物体数量）
            if priority == 1:
                p1_base_count += 1
            elif priority == 2:
                p2_base_count += 1
            
            # 若存在深度与相机参数，则计算深度增量
            if depth_data is None or camera_params is None:
                continue
            
            # 计算物体中心的世界坐标
            coord_info = None
            try:
                coord_info = CoordinateProcessor.calculate_coordinate_for_detection(
                    det_box,
                    depth_data,
                    camera_params,
                    None  # 只需要世界坐标，不需要机器人坐标
                )
            except Exception as e:
                if logger:
                    logger.warning(f"计算物体坐标失败: {e}")
                coord_info = None
            
            if not coord_info or 'camera_3d' not in coord_info or not coord_info['camera_3d']:
                continue
            
            # 提取世界坐标Z值
            world_xyz = coord_info['camera_3d']
            world_z = float(world_xyz[2])
            
            # 计算深度差值：depthThreshold - world_z
            delta = roi_depth_threshold - world_z
            
            # 深度增量：每小于阈值10个单位+1
            increments = int(delta // 10.0) if delta >= 10.0 else 0
            
            if priority == 1:
                p1_depth_increment += increments
            elif priority == 2:
                p2_depth_increment += increments
        
        # 计算最终计数：基数 + 深度增量
        p1_count = p1_base_count + p1_depth_increment
        p2_count = p2_base_count + p2_depth_increment
        
        # 精简日志：移除ROI计数的详细输出
        
        in_p1roi = p1_count
        in_p2roi = p2_count
        
        # 初始化响应字符串（默认无目标）
        tcp_response = "0,0,0,0,0"
        best_target_info = None
        robot_coordinates = None
        
        # ===== 获取TCP间隔信息和遮挡检测配置 =====
        tcp_interval_ms = _req.data.get('tcp_interval_ms', 0.0)
        occlusion_cfg = roi_cfg.get('occlusion', {})
        interval_threshold = float(occlusion_cfg.get('intervalThreshold', 700))
        ignore_count = int(occlusion_cfg.get('ignoreCount', 3))
        
        # ===== 遮挡检测：优先检查TCP间隔和忽略状态 =====
        t0_coordinate = time.time()
        
        # 步骤1：检查是否在忽略期内
        if ctx.occlusion_ignore_remaining > 0:
            # 还在忽略期内，直接返回遮挡标志
            tcp_response = "-1,0,0,0,0"
            ctx.occlusion_ignore_remaining -= 1
            if logger:
                logger.warning(
                    f"[OCCLUSION] 机器人遮挡期间（忽略中）: 剩余忽略次数={ctx.occlusion_ignore_remaining}, "
                    f"返回遮挡标志='{tcp_response}'"
                )
            # 跳过正常的坐标计算，直接进入可视化阶段
        
        # 步骤2：检查当前TCP间隔是否超过阈值（无论是否有目标）
        elif tcp_interval_ms > interval_threshold:
            # TCP间隔超过阈值，启动遮挡忽略模式（无论是否检测到目标）
            ctx.occlusion_ignore_remaining = ignore_count
            tcp_response = "-1,0,0,0,0"
            if logger:
                logger.warning(
                    f"[OCCLUSION-START] 检测到机器人动作: TCP间隔={tcp_interval_ms:.1f}ms > {interval_threshold}ms, "
                    f"启动遮挡忽略模式，接下来{ignore_count}次检测将返回遮挡标志, "
                    f"检测{total_count}个目标/有效目标={'有' if best_target else '无'}, 返回='{tcp_response}'"
                )
        
        # 步骤3：正常检测流程 - 如果有有效目标，进行坐标计算
        elif best_target:
            # 精简日志：移除坐标计算过程的详细输出
            if depth_data is None or camera_params is None:
                pass  # 静默处理，错误会在最终结果中体现
            else:
                # 第一步：像素坐标 + 深度 → 相机坐标 → 世界坐标（使用相机内置的 cam2worldMatrix）
                # 注意：这里不传入 transformation_matrix，让 CoordinateProcessor 只完成第一步转换
                coord_info = CoordinateProcessor.calculate_coordinate_for_detection(
                    best_target['detection'],
                    depth_data,
                    camera_params,
                    None  # 不使用外部变换矩阵
                )
                
                if coord_info:
                    # coord_info['camera_3d'] 实际是世界坐标（相机已通过 cam2worldMatrix 转换）
                    world_xyz = coord_info['camera_3d']
                    
                    # 第二步：世界坐标 → 机器人坐标（使用外部标定的 transformation_matrix.json）
                    robot_coordinates = _world_to_robot_using_calib(world_xyz, ctx.project_root)
                    
                    if robot_coordinates is not None and len(robot_coordinates) >= 3:
                        x, y, z = robot_coordinates[0], robot_coordinates[1], robot_coordinates[2]
                        
                        # 构建TCP响应字符串：p1_flag,p2_flag,x,y,z
                        tcp_response = f"{in_p1roi},{in_p2roi},{x:.2f},{y:.2f},{z:.2f}"
                    else:
                        # 没有外部标定矩阵，使用世界坐标
                        x, y, z = world_xyz[0], world_xyz[1], world_xyz[2]
                        robot_coordinates = world_xyz
                        
                        # 构建TCP响应字符串：p1_flag,p2_flag,x,y,z
                        tcp_response = f"{in_p1roi},{in_p2roi},{x:.2f},{y:.2f},{z:.2f}"
                    
                    # 在图像上绘制最佳目标的中心点
                    center_x, center_y = coord_info['center']
                    vis_img = DetectionVisualizer.draw_crosshair(
                        vis_img,
                        int(center_x),
                        int(center_y),
                        size=20,
                        color=(0, 255, 0),
                        thickness=2
                    )
                    
                    best_target_info = {
                        'target_id': best_target['target_id'],
                        'class_id': coord_info['class_id'],
                        'score': coord_info['score'],
                        'area': coord_info['area'],
                        'center_pixel': coord_info['center'],
                        'depth_mm': coord_info['depth'],
                        'camera_3d': coord_info['camera_3d'],
                        'robot_3d': robot_coordinates,
                        'in_p1roi': in_p1roi,
                        'in_p2roi': in_p2roi
                    }
            
            # 找到有效目标，清零遮挡忽略计数（虽然前面已经检查过了，但这里为了安全再次清零）
            ctx.occlusion_ignore_remaining = 0
        
        # 步骤4：无有效目标且TCP间隔正常的情况
        else:
            # TCP间隔正常且无有效目标，返回正常的无目标响应
            tcp_response = "0,0,0,0,0"
        
        time_points['coordinate_calc'] = (time.time() - t0_coordinate) * 1000.0
        
        # 编码为JPG并上传
        t0_encode = time.time()
        jpg = ImageUtils.encode_jpg(vis_img)
        time_points['jpg_encode'] = (time.time() - t0_encode) * 1000.0
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={"response": "0,0,0,0,0"},
            )
        
        # 上传到SFTP（非关键操作，失败不影响检测结果）
        t0_upload = time.time()
        upload_info = None
        if sftp:
            try:
                upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="catch")
            except Exception:
                pass  # 精简日志：SFTP上传错误静默处理
        time_points['sftp_upload'] = (time.time() - t0_upload) * 1000.0
        
        # 获取SFTP配置并构建完整路径（如果有上传信息）
        if upload_info:
            sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
            upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
        
        # 构建返回数据
        payload = {
            "response": tcp_response,  # TCP响应字符串
            "total_detection_count": total_count,
            "p1roi_detection_count": p1_count,
            "p2roi_detection_count": p2_count,
            "infer_time_ms": round(time_points.get('detection', 0), 1),
            "has_target": best_target_info is not None,
            "best_target": best_target_info,
            "filename": upload_info.get("filename") if upload_info else None,
            "remote_path": upload_info.get("remote_path") if upload_info else None,
            "remote_rel_path": upload_info.get("remote_rel_path") if upload_info else None,
            "remote_file": upload_info.get("remote_file") if upload_info else None,
            "remote_full_path": upload_info.get("remote_full_path") if upload_info else None,
            "file_size": upload_info.get("file_size") if upload_info else None,
            "image_shape": list(vis_img.shape) if hasattr(vis_img, "shape") else None,
        }
        
        # 计算总耗时
        time_points['total'] = (time.time() - time_start) * 1000.0
        
        if logger:
            try:
                # 构建详细的性能日志
                perf_details = (
                    f"相机取图={time_points.get('camera', 0):.1f}ms, "
                    f"AI检测={time_points.get('detection', 0):.1f}ms, "
                    f"ROI配置={time_points.get('roi_setup', 0):.1f}ms, "
                    f"目标筛选={time_points.get('filter_and_select', 0):.1f}ms, "
                    f"坐标计算={time_points.get('coordinate_calc', 0):.1f}ms, "
                    f"可视化={time_points.get('visualize_detections', 0):.1f}ms, "
                    f"JPG编码={time_points.get('jpg_encode', 0):.1f}ms, "
                    f"SFTP上传={time_points.get('sftp_upload', 0):.1f}ms"
                )
                
                if best_target_info:
                    logger.info(
                        f"抓取命令完成: 检测{total_count}个目标, "
                        f"p1roi内{p1_count}个, p2roi内{p2_count}个, "
                        f"TCP响应='{tcp_response}' | 总耗时={time_points['total']:.1f}ms"
                    )
                    logger.info(f"性能分析: {perf_details}")
                else:
                    logger.info(
                        f"抓取命令完成: 检测{total_count}个目标, "
                        f"p1roi内{p1_count}个, p2roi内{p2_count}个, "
                        f"无有效目标, TCP响应='{tcp_response}' | 总耗时={time_points['total']:.1f}ms"
                    )
                    logger.info(f"性能分析: {perf_details}")
            except Exception:
                pass
        
        return MQTTResponse(
            command=VisionCoreCommands.CATCH.value,
            component="detector",
            messageType=MessageType.SUCCESS,
            message="ok",
            data=payload,
        )
    except Exception as e:
        if logger:
            try:
                logger.error(f"handle_catch error: {e}", exc_info=True)
            except Exception:
                pass
        return MQTTResponse(
            command=VisionCoreCommands.CATCH.value,
            component="detector",
            messageType=MessageType.ERROR,
            message=str(e),
            data={"response": "0,0,0,0,0"},
        )


def _world_to_robot_using_calib(world_xyz, project_root: str):
    """
    使用 transformation_matrix.json 中的 matrix_xy 与 z_mapping 将世界坐标转换为机器人坐标
    
    优先使用 matrix_xy (2x3) + z_mapping (alpha, beta)
    回退使用完整 4x4 matrix
    
    Args:
        world_xyz: 世界坐标 [x, y, z]
        project_root: 项目根目录
    
    Returns:
        机器人坐标 [x, y, z]，失败返回 None
    """
    try:
        if world_xyz is None:
            return None
        
        xw, yw, zw = float(world_xyz[0]), float(world_xyz[1]), float(world_xyz[2])
        
        calib_path = os.path.join(project_root, "configs", "transformation_matrix.json")
        if not os.path.exists(calib_path):
            return None
        
        with open(calib_path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        
        # 优先：使用 matrix_xy + z_mapping
        mx = data.get('matrix_xy')
        zm = data.get('z_mapping')
        if isinstance(mx, list) and len(mx) == 2 and all(isinstance(r, list) and len(r) == 3 for r in mx) and isinstance(zm, dict):
            a11, a12, a13 = float(mx[0][0]), float(mx[0][1]), float(mx[0][2])
            a21, a22, a23 = float(mx[1][0]), float(mx[1][1]), float(mx[1][2])
            xr = a11 * xw + a12 * yw + a13
            yr = a21 * xw + a22 * yw + a23
            alpha = float(zm.get('alpha', 1.0)) if zm else 1.0
            beta = float(zm.get('beta', 0.0)) if zm else 0.0
            zr = alpha * zw + beta
            if zr < -85.0:
                zr = -85.0
            return [xr, yr, zr]
        
        # 回退：使用完整 4x4 matrix
        M = data.get('matrix')
        if isinstance(M, list) and len(M) == 4 and all(isinstance(r, list) and len(r) == 4 for r in M):
            m = M
            xr = m[0][0]*xw + m[0][1]*yw + m[0][2]*zw + m[0][3]
            yr = m[1][0]*xw + m[1][1]*yw + m[1][2]*zw + m[1][3]
            zr = m[2][0]*xw + m[2][1]*yw + m[2][2]*zw + m[2][3]
            w  = m[3][0]*xw + m[3][1]*yw + m[3][2]*zw + m[3][3]
            if w != 0:
                xr, yr, zr = xr / w, yr / w, zr / w
            if zr < -85.0:
                zr = -85.0
            return [xr, yr, zr]
        
        return None
        
    except Exception:
        return None