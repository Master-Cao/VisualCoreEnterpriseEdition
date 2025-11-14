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
        if not sftp:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="sftp_not_ready",
                data={},
            )
        
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
        
        # 上传到SFTP
        upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="detection_test")
        if not upload_info:
            return MQTTResponse(
                command=VisionCoreCommands.MODEL_TEST.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="upload_failed",
                data={},
            )
        
        # 获取SFTP配置并构建完整路径
        sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
        upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
        
        # 构建返回数据
        remote_path = upload_info.get("remote_path")
        filename = upload_info.get("filename")
        remote_rel_path = upload_info.get("remote_rel_path")
        remote_full_path = upload_info.get("remote_full_path")
        
        payload = {
            "detection_count": count,
            "infer_time_ms": round(dt, 1),
            "filename": filename,
            "remote_path": remote_path,
            "remote_rel_path": remote_rel_path,
            "remote_file": upload_info.get("remote_file"),
            "remote_full_path": remote_full_path,
            "file_size": upload_info.get("file_size"),
            "image_shape": list(vis_img.shape) if hasattr(vis_img, "shape") else None,
        }
        
        if logger and filename:
            try:
                logger.info(
                    f"检测测试完成: {count}个目标, 推理耗时={dt:.1f}ms, 图像已上传: {filename}"
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
        if not sftp:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="sftp_not_ready",
                data={"response": "0,0,0,0,0"},
            )
        
        # 获取相机数据（深度、强度、参数）
        result = cam.get_frame(depth=True, intensity=True, camera_params=True)
        img = result.get('intensity_image') if result else None
        depth_data = result.get('depthmap') if result else None
        camera_params = result.get('cameraParams') if result else None
        
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="no_frame",
                data={"response": "0,0,0,0,0"},
            )
        
        # 执行检测
        t0 = time.time()
        detection_results = det.detect(img)
        dt_detect = (time.time() - t0) * 1000.0
        total_count = len(detection_results) if hasattr(detection_results, "__len__") else (1 if detection_results else 0)
        
        # 先绘制检测结果（不包含ROI）
        vis_img = DetectionVisualizer.draw_detections(
            img, detection_results,
            class_names=["seasoning", "hand"], 
            show_bbox=False
        )
        
        # 直接从config中获取ROI配置
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
        
        # 过滤seasoning目标（只针对类别0）
        seasoning_detections = []
        for det_box in detection_results:
            class_id = int(getattr(det_box, 'class_id', getattr(det_box, 'classId', -1)))
            if class_id == 0:  # seasoning
                seasoning_detections.append(det_box)
        
        if logger:
            try:
                logger.info(f"检测结果: 总计{total_count}个目标, seasoning目标{len(seasoning_detections)}个")
                logger.info(f"ROI配置: {len(roi_list)}个ROI, minArea={min_area}")
                for i, roi in enumerate(roi_list):
                    logger.info(f"  ROI[{i}]: priority={roi.get('priority')}, name={roi.get('name')}, "
                               f"区域=[{roi.get('x1')},{roi.get('y1')}]-[{roi.get('x2')},{roi.get('y2')}]")
                
                # 详细检查每个seasoning目标
                logger.info(f"开始检查{len(seasoning_detections)}个seasoning目标:")
                for idx, det_box in enumerate(seasoning_detections):
                    xmin = float(getattr(det_box, 'xmin', 0))
                    ymin = float(getattr(det_box, 'ymin', 0))
                    xmax = float(getattr(det_box, 'xmax', 0))
                    ymax = float(getattr(det_box, 'ymax', 0))
                    center_x = 0.5 * (xmin + xmax)
                    center_y = 0.5 * (ymin + ymax)
                    
                    # 获取mask面积
                    mask = getattr(det_box, 'seg_mask', None)
                    if mask is not None and isinstance(mask, np.ndarray):
                        area = float(np.sum(mask > 0))
                    else:
                        area = (xmax - xmin) * (ymax - ymin)
                    
                    # 检查是否在ROI内
                    in_roi = False
                    roi_name = "无"
                    for roi in roi_list:
                        if RoiProcessor.is_point_in_roi(center_x, center_y, roi):
                            in_roi = True
                            roi_name = roi.get('name', 'unknown')
                            break
                    
                    logger.info(f"  目标[{idx}]: 中心点=({center_x:.1f},{center_y:.1f}), "
                               f"面积={area:.0f}px, 在ROI内={in_roi}, ROI={roi_name}, "
                               f"通过面积过滤={area >= min_area}")
            except Exception as e:
                logger.error(f"调试日志输出失败: {e}")
        
        # 使用多ROI优先级选择：ROI区域内(仅判断中点) > ROI优先级高 > Mask大于minArea > Mask最大
        best_target = TargetSelector.select_by_multi_roi_priority(
            seasoning_detections,
            roi_list,
            min_area=min_area
        )
        
        if logger:
            try:
                if best_target:
                    logger.info(f"✓ 已选择最佳目标: target_id={best_target.get('target_id')}, "
                               f"area={best_target.get('area'):.0f}px, priority={best_target.get('roi_priority')}, "
                               f"roi_name={best_target.get('roi_name')}")
                else:
                    logger.warning(f"✗ 未选择到最佳目标！seasoning={len(seasoning_detections)}个, "
                                  f"roi_list={len(roi_list)}个, minArea={min_area}")
                    # 给出可能的原因提示
                    if len(seasoning_detections) == 0:
                        logger.warning("  → 原因: 没有检测到seasoning类别(class_id=0)的目标")
                    elif len(roi_list) == 0:
                        logger.warning("  → 原因: 没有配置ROI区域")
                    else:
                        logger.warning("  → 原因: 所有seasoning目标被过滤（不在ROI内 或 面积小于minArea）")
            except Exception:
                pass
        
        # 统计各ROI中的目标数量（通过中点判断）
        p1_count = 0
        p2_count = 0
        for det_box in seasoning_detections:
            xmin = float(getattr(det_box, 'xmin', 0))
            ymin = float(getattr(det_box, 'ymin', 0))
            xmax = float(getattr(det_box, 'xmax', 0))
            ymax = float(getattr(det_box, 'ymax', 0))
            center_x = 0.5 * (xmin + xmax)
            center_y = 0.5 * (ymin + ymax)
            
            # 遍历roi_list统计
            for roi in roi_list:
                if RoiProcessor.is_point_in_roi(center_x, center_y, roi):
                    priority = roi.get('priority', 999)
                    if priority == 1:
                        p1_count += 1
                    elif priority == 2:
                        p2_count += 1
                    break  # 只计入第一个匹配的ROI
        
        # 判断目标在哪个ROI中（用于TCP响应）
        in_p1roi = 0
        in_p2roi = 0
        
        if best_target:
            roi_priority = best_target.get('roi_priority', 999)
            if roi_priority == 1:
                in_p1roi = 1
            elif roi_priority == 2:
                in_p2roi = 1
        
        # 初始化响应字符串（默认无目标）
        tcp_response = "0,0,0,0,0"
        best_target_info = None
        robot_coordinates = None
        
        # 如果有有效目标，进行坐标计算
        if best_target:
            if logger:
                logger.info(f"开始计算最佳目标坐标: depth_data={'有' if depth_data else '无'}, "
                           f"camera_params={'有' if camera_params else '无'}")
            
            if depth_data is None:
                if logger:
                    logger.error("✗ 坐标计算失败: depth_data为None，无法获取深度信息")
            elif camera_params is None:
                if logger:
                    logger.error("✗ 坐标计算失败: camera_params为None，无法获取相机参数")
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
                    
                    if logger:
                        logger.info(f"第一步转换完成: 世界坐标=[{world_xyz[0]:.2f}, {world_xyz[1]:.2f}, {world_xyz[2]:.2f}]")
                    
                    # 第二步：世界坐标 → 机器人坐标（使用外部标定的 transformation_matrix.json）
                    robot_coordinates = _world_to_robot_using_calib(world_xyz, ctx.project_root)
                    
                    if robot_coordinates is not None and len(robot_coordinates) >= 3:
                        x, y, z = robot_coordinates[0], robot_coordinates[1], robot_coordinates[2]
                        
                        # 构建TCP响应字符串：p1_flag,p2_flag,x,y,z
                        tcp_response = f"{in_p1roi},{in_p2roi},{x:.2f},{y:.2f},{z:.2f}"
                        
                        if logger:
                            logger.info(f"第二步转换完成: 机器人坐标=[{x:.2f}, {y:.2f}, {z:.2f}]")
                            logger.info(f"✓ 坐标计算成功: TCP响应='{tcp_response}'")
                    else:
                        # 没有外部标定矩阵，使用世界坐标
                        x, y, z = world_xyz[0], world_xyz[1], world_xyz[2]
                        robot_coordinates = world_xyz
                        
                        # 构建TCP响应字符串：p1_flag,p2_flag,x,y,z
                        tcp_response = f"{in_p1roi},{in_p2roi},{x:.2f},{y:.2f},{z:.2f}"
                        
                        if logger:
                            logger.warning(f"未找到外部标定矩阵，使用世界坐标: TCP响应='{tcp_response}'")
                    
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
                else:
                    if logger:
                        logger.error(f"✗ 坐标计算失败: CoordinateProcessor返回None (可能深度值无效或计算出错)")
        
        # 编码为JPG并上传
        jpg = ImageUtils.encode_jpg(vis_img)
        if jpg is None:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="encode_failed",
                data={"response": "0,0,0,0,0"},
            )
        
        # 上传到SFTP
        upload_info = SftpHelper.upload_image_bytes(sftp, jpg, prefix="catch")
        if not upload_info:
            return MQTTResponse(
                command=VisionCoreCommands.CATCH.value,
                component="sftp",
                messageType=MessageType.ERROR,
                message="upload_failed",
                data={"response": "0,0,0,0,0"},
            )
        
        # 获取SFTP配置并构建完整路径
        sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
        upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
        
        # 构建返回数据
        payload = {
            "response": tcp_response,  # TCP响应字符串
            "total_detection_count": total_count,
            "p1roi_detection_count": p1_count,
            "p2roi_detection_count": p2_count,
            "infer_time_ms": round(dt_detect, 1),
            "has_target": best_target_info is not None,
            "best_target": best_target_info,
            "filename": upload_info.get("filename"),
            "remote_path": upload_info.get("remote_path"),
            "remote_rel_path": upload_info.get("remote_rel_path"),
            "remote_file": upload_info.get("remote_file"),
            "remote_full_path": upload_info.get("remote_full_path"),
            "file_size": upload_info.get("file_size"),
            "image_shape": list(vis_img.shape) if hasattr(vis_img, "shape") else None,
        }
        
        if logger:
            try:
                if best_target_info:
                    logger.info(
                        f"抓取命令完成: 检测{total_count}个目标, "
                        f"p1roi内{p1_count}个, p2roi内{p2_count}个, "
                        f"推理耗时={dt_detect:.1f}ms, TCP响应='{tcp_response}'"
                    )
                else:
                    logger.info(
                            f"抓取命令完成: 检测{total_count}个目标, "
                            f"p1roi内{p1_count}个, p2roi内{p2_count}个, "
                            f"推理耗时={dt_detect:.1f}ms, 无有效目标, TCP响应='0,0,0,0,0'"
                    )
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


def _load_transformation_matrix(project_root: str) -> np.ndarray:
    """
    加载坐标转换矩阵
    
    Args:
        project_root: 项目根目录
    
    Returns:
        4x4变换矩阵，如果加载失败返回None
    """
    try:
        matrix_path = os.path.join(project_root, "configs", "transformation_matrix.json")
        
        if not os.path.exists(matrix_path):
            return None
        
        with open(matrix_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 获取4x4矩阵
        matrix_data = data.get('matrix')
        if not isinstance(matrix_data, list) or len(matrix_data) != 4:
            return None
        
        if not all(isinstance(row, list) and len(row) == 4 for row in matrix_data):
            return None
        
        return np.array(matrix_data, dtype=np.float64)
        
    except Exception:
        return None


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