# -*- coding: utf-8 -*-

"""
坐标标定命令处理器
- get_calibrat_image: 检测黑块并返回世界坐标
- coordinate_calibration: 接收机器人坐标并执行标定计算
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple

from domain.enums.commands import VisionCoreCommands, MessageType
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from services.calibration import detect_black_blocks, calibrate_from_points
from services.shared import ImageUtils, SftpHelper
from services.detection import CoordinateProcessor, DetectionVisualizer


def handle_get_calibrat_image(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    """
    获取标定图像命令
    
    功能:
    1. 从相机获取图像
    2. 检测黑色标记块（最多12个，3x4网格）
    3. 计算每个块的世界坐标(xw, yw, zw)
    4. 可选：上传标注图像到SFTP
    5. 返回世界坐标列表给客户端
    
    客户端收到后:
    - 显示12个点的世界坐标
    - 用户使用机器人示教器移动到每个点记录机器人坐标
    - 填写完成后触发 coordinate_calibration 命令
    
    Returns:
        包含世界坐标列表的响应
    """
    logger = ctx.logger
    
    try:
        # 1. 检查相机可用性
        cam = ctx.camera
        if not cam or not getattr(cam, "healthy", False):
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_not_ready",
                data={}
            )
        
        # 2. 获取相机帧和图像数据（需要深度和相机参数来计算世界坐标）
        result = cam.get_frame(depth=True, intensity=True, camera_params=True)
        if not result:
            if logger:
                logger.error("获取相机帧失败: get_frame returned None")
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="camera_capture_failed",
                data={}
            )
        
        img = result.get('intensity_image')
        depth_data = result.get('depthmap')  # 注意：这里直接是list，不是对象
        camera_params = result.get('cameraParams')
        
        # ========== 临时调试：使用本地图片代替相机图像 ==========
        try:
            import os
            debug_img_path = os.path.join(ctx.project_root, "configs", "calib_raw_20251028_143410_668_pre.jpg")
            if os.path.exists(debug_img_path):
                debug_img = cv2.imread(debug_img_path, cv2.IMREAD_GRAYSCALE)
                if debug_img is not None:
                    img = debug_img
                    if logger:
                        logger.warning(f"⚠️ 调试模式：使用本地图片代替相机图像 - {debug_img_path}")
        except Exception as debug_err:
            if logger:
                logger.warning(f"加载调试图片失败: {debug_err}")
        # ========== 调试代码结束 ==========
        
        # 3. 检查数据完整性
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="image_conversion_failed",
                data={}
            )
        
        if not depth_data or not camera_params:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="missing_depth_or_params",
                data={}
            )
        
        

        # 4. 检测黑色标记块
        try:
            blocks = detect_black_blocks(img, max_blocks=12, rows=3, cols=4)
        except Exception as det_err:
            if logger:
                logger.error(f"黑块检测失败: {det_err}")
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="detector",
                messageType=MessageType.ERROR,
                message="block_detection_failed",
                data={}
            )
        
        if not blocks:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="detector",
                messageType=MessageType.ERROR,
                message="no_blocks_detected",
                data={"hint": "请确保有黑色方形标记块在相机视野内"}
            )
        
        if logger:
            logger.info(f"检测到 {len(blocks)} 个黑色标记块")
        
        # 5. 计算世界坐标（XY平面标定需要世界坐标的XY值）
        width = int(getattr(camera_params, 'width', 0))
        height = int(getattr(camera_params, 'height', 0))
        # depth_data 已经在上面获取了，是 list 类型
        
        # 提取相机参数
        cx = float(getattr(camera_params, 'cx', 0))
        cy = float(getattr(camera_params, 'cy', 0))
        fx = float(getattr(camera_params, 'fx', 1))
        fy = float(getattr(camera_params, 'fy', 1))
        k1 = float(getattr(camera_params, 'k1', 0))
        k2 = float(getattr(camera_params, 'k2', 0))
        f2rc = float(getattr(camera_params, 'f2rc', 0))
        
        # 获取cam2world矩阵
        m_c2w = None
        try:
            if hasattr(camera_params, 'cam2worldMatrix') and camera_params.cam2worldMatrix:
                if len(camera_params.cam2worldMatrix) == 16:
                    m_c2w = np.array(camera_params.cam2worldMatrix, dtype=np.float64).reshape(4, 4)
        except Exception:
            pass
        
        points_info = []
        for i, block in enumerate(blocks):
            # 直接从depth_data获取中心点深度值
            u, v = block.center_u, block.center_v
            if 0 <= u < width and 0 <= v < height:
                depth_idx = v * width + u
                if depth_idx < len(depth_data):
                    depth_mm = float(depth_data[depth_idx])
                else:
                    depth_mm = 0.0
            else:
                depth_mm = 0.0
            
            # 如果深度无效，使用默认深度值（调试用）
            if depth_mm <= 0:
                depth_mm = 650.0  # 使用默认深度值650mm
                if logger:
                    logger.warning(f"块{i+1}({u},{v})深度值无效，使用默认值{depth_mm}mm")
            
            # 直接使用_calculate_3d_fast计算3D世界坐标
            ok, xyz = CoordinateProcessor._calculate_3d_fast(
                float(u), float(v), float(depth_mm),
                cx, cy, fx, fy, k1, k2, f2rc, m_c2w
            )
            
            if not ok:
                if logger:
                    logger.warning(f"块{i+1}({u},{v})世界坐标计算失败")
                points_info.append({
                    'index': i + 1,
                    'pixel_u': u,
                    'pixel_v': v,
                    'valid': False,
                    'world_x': None,
                    'world_y': None,
                    'world_z': None
                })
            else:
                points_info.append({
                    'index': i + 1,
                    'pixel_u': u,
                    'pixel_v': v,
                    'valid': True,
                    'world_x': round(xyz[0], 3),
                    'world_y': round(xyz[1], 3),
                    'world_z': round(xyz[2], 3)
                })
        
        # 统计有效点
        valid_count = sum(1 for p in points_info if p['valid'])
        
        if valid_count < 3:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="calibrator",
                messageType=MessageType.ERROR,
                message="insufficient_valid_points",
                data={
                    "detected": len(blocks),
                    "valid": valid_count,
                    "required": 3
                }
            )
        
        # 6. 可选：标注图像并上传SFTP
        upload_info = None
        vis_img = None
        if ctx.sftp:
            try:
                # 使用DetectionVisualizer绘制标注
                vis_img = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                for i, block in enumerate(blocks, start=1):
                    # 画圆标记中心
                    cv2.circle(vis_img, (block.center_u, block.center_v), 6, (0, 255, 0), -1)
                    # 画编号
                    cv2.putText(
                        vis_img, str(i),
                        (block.center_u + 8, block.center_v - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA
                    )
                
                jpg = ImageUtils.encode_jpg(vis_img)
                if not jpg:
                    if logger:
                        logger.error("标注图像编码失败")
                else:
                    upload_info = SftpHelper.upload_image_bytes(ctx.sftp, jpg, prefix="calib")
                    if not upload_info:
                        if logger:
                            logger.error("标定图像上传失败")
                    else:
                        # 获取SFTP配置并构建完整路径（与detection.py保持一致）
                        sftp_cfg = ctx.config.get("sftp") if isinstance(ctx.config, dict) else {}
                        upload_info = SftpHelper.get_upload_info_with_prefix(upload_info, sftp_cfg)
                        
                        if logger:
                            logger.info(f"标定图像已上传: {upload_info.get('filename')}")
            except Exception as upload_err:
                if logger:
                    logger.warning(f"标定图像上传失败: {upload_err}")
        
        # 7. 构造响应（参考detection.py的详细信息格式）
        response_data = {
            'blocks_detected': len(blocks),
            'valid_points': valid_count,
            'points': points_info,
            'note': '请使用机器人示教器移动到每个点位，记录机器人XY坐标后发送coordinate_calibration命令\n'
                   '注意：本次标定仅建立XY平面映射关系（world_xy → robot_xy），不包含Z轴'
        }
        
        # 添加详细的图片信息（与detection.py保持一致）
        if upload_info:
            response_data['filename'] = upload_info.get('filename')
            response_data['remote_path'] = upload_info.get('remote_path')
            response_data['remote_rel_path'] = upload_info.get('remote_rel_path')
            response_data['remote_file'] = upload_info.get('remote_file')
            response_data['remote_full_path'] = upload_info.get('remote_full_path')
            response_data['file_size'] = upload_info.get('file_size')
            response_data['image_remote'] = upload_info
        
        # 添加图像尺寸信息
        if vis_img is not None and hasattr(vis_img, 'shape'):
            response_data['image_shape'] = list(vis_img.shape)
        
        return MQTTResponse(
            command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
            component="calibrator",
            messageType=MessageType.SUCCESS,
            message="ok",
            data=response_data
        )
    
    except Exception as e:
        if logger:
            logger.error(f"get_calibrat_image异常: {e}")
        return MQTTResponse(
            command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
            component="system",
            messageType=MessageType.ERROR,
            message=str(e),
            data={}
        )


def handle_coordinate_calibration(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    """
    坐标标定命令
    
    前提:
    - 客户端已通过 get_calibrat_image 获取世界坐标
    - 用户已使用机器人示教器记录对应的机器人坐标
    
    Payload格式 (新格式):
    {
        "calibration_points": [
            {
                "pixel_u": u1, "pixel_v": v1,
                "world_x": xw1, "world_y": yw1,
                "robot_x": xr1, "robot_y": yr1
            },
            ...
        ],
        "z_axis_mappings": [
            {"camera_height": h1, "robot_z": z1},
            {"camera_height": h2, "robot_z": z2}
        ]
    }
    
    或旧格式（兼容）:
    {
        "world_points": [{"x": xw1, "y": yw1, "z": zw1}, ...],
        "robot_points": [{"x": xr1, "y": yr1, "z": zr1}, ...]
    }
    
    功能:
    1. 接收世界坐标和机器人坐标
    2. 执行标定计算（XY仿射 + Z线性）
    3. 保存变换矩阵到 configs/transformation_matrix.json
    4. 返回标定结果和精度统计
    
    Returns:
        标定结果，包含变换矩阵和RMSE
    """
    logger = ctx.logger
    
    try:
        # 1. 解析payload
        payload_data = req.data if isinstance(req.data, dict) else {}
        
        # 检测消息格式（新格式优先）
        calibration_points = payload_data.get('calibration_points', [])
        z_axis_mappings = payload_data.get('z_axis_mappings', [])
        
        world_valid = []
        robot_valid = []
        
        # 2. 如果是新格式（包含calibration_points）
        if calibration_points:
            if logger:
                logger.info(f"检测到新格式标定数据，共 {len(calibration_points)} 个标定点")
            
            # 解析标定点（XY平面）
            for i, point in enumerate(calibration_points):
                if not isinstance(point, dict):
                    continue
                
                try:
                    world_x = float(point.get('world_x', 0))
                    world_y = float(point.get('world_y', 0))
                    robot_x = float(point.get('robot_x', 0))
                    robot_y = float(point.get('robot_y', 0))
                    
                    # 使用默认Z值0（后续会通过z_axis_mappings处理Z轴）
                    world_valid.append((world_x, world_y, 0.0))
                    robot_valid.append((robot_x, robot_y, 0.0))
                    
                    if logger:
                        logger.debug(
                            f"点{i+1}: world=({world_x:.2f}, {world_y:.2f}) -> "
                            f"robot=({robot_x:.2f}, {robot_y:.2f})"
                        )
                except (ValueError, TypeError) as e:
                    if logger:
                        logger.warning(f"解析标定点{i+1}失败: {e}")
                    continue
            
            # 处理Z轴映射（如果提供）
            if z_axis_mappings and len(z_axis_mappings) >= 2:
                if logger:
                    logger.info(f"检测到Z轴映射数据，共 {len(z_axis_mappings)} 个映射点")
                
                # 提取Z轴映射点用于标定
                z_world_points = []
                z_robot_points = []
                for i, mapping in enumerate(z_axis_mappings):
                    if not isinstance(mapping, dict):
                        continue
                    try:
                        camera_height = float(mapping.get('camera_height', 0))
                        robot_z = float(mapping.get('robot_z', 0))
                        
                        # 使用(0, 0, camera_height)作为世界坐标
                        z_world_points.append((0.0, 0.0, camera_height))
                        z_robot_points.append((0.0, 0.0, robot_z))
                        
                        if logger:
                            logger.debug(f"Z轴映射{i+1}: camera_height={camera_height} -> robot_z={robot_z}")
                    except (ValueError, TypeError) as e:
                        if logger:
                            logger.warning(f"解析Z轴映射{i+1}失败: {e}")
                        continue
                
                # 将Z轴映射点添加到标定数据中
                if z_world_points and z_robot_points:
                    world_valid.extend(z_world_points)
                    robot_valid.extend(z_robot_points)
                    if logger:
                        logger.info(f"已添加 {len(z_world_points)} 个Z轴映射点到标定数据")
        
        # 3. 否则尝试旧格式（兼容性）
        else:
            world_points_raw = payload_data.get('world_points', [])
            robot_points_raw = payload_data.get('robot_points', [])
            
            if not robot_points_raw:
                return MQTTResponse(
                    command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                    component="calibrator",
                    messageType=MessageType.ERROR,
                    message="missing_calibration_data",
                    data={"hint": "payload中必须包含calibration_points字段或robot_points字段"}
                )
            
            if not world_points_raw:
                return MQTTResponse(
                    command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                    component="calibrator",
                    messageType=MessageType.ERROR,
                    message="missing_world_points",
                    data={"hint": "payload中必须包含calibration_points字段或world_points字段"}
                )
            
            if logger:
                logger.info(f"检测到旧格式标定数据")
            
            # 解析坐标点
            world_points = []
            for wp in world_points_raw:
                if isinstance(wp, dict):
                    try:
                        world_points.append((
                            float(wp.get('x', 0)),
                            float(wp.get('y', 0)),
                            float(wp.get('z', 0))
                        ))
                    except (ValueError, TypeError):
                        world_points.append(None)
                else:
                    world_points.append(None)
            
            robot_points = []
            for rp in robot_points_raw:
                if isinstance(rp, dict):
                    try:
                        robot_points.append((
                            float(rp.get('x', 0)),
                            float(rp.get('y', 0)),
                            float(rp.get('z', 0))
                        ))
                    except (ValueError, TypeError):
                        robot_points.append(None)
                else:
                    robot_points.append(None)
            
            # 过滤有效点对
            for i in range(min(len(world_points), len(robot_points))):
                if world_points[i] is not None and robot_points[i] is not None:
                    world_valid.append(world_points[i])
                    robot_valid.append(robot_points[i])
        
        # 4. 检查有效点数
        
        if len(world_valid) < 3:
            return MQTTResponse(
                command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                component="calibrator",
                messageType=MessageType.ERROR,
                message="insufficient_valid_pairs",
                data={
                    "valid_pairs": len(world_valid),
                    "required": 3,
                    "hint": "至少需要3组有效的坐标对应点"
                }
            )
        
        if logger:
            logger.info(f"准备执行标定，共 {len(world_valid)} 个有效点对")
        
        # 5. 决定是否启用Z轴标定
        # 如果有z_axis_mappings数据且至少有2个映射点，则启用Z轴标定
        calibrate_z = bool(z_axis_mappings and len(z_axis_mappings) >= 2)
        
        # 6. 执行标定
        output_path = Path(ctx.project_root) / "configs" / "transformation_matrix.json"
        
        try:
            result = calibrate_from_points(world_valid, robot_valid, output_path, calibrate_z=calibrate_z)
            if logger:
                if calibrate_z:
                    logger.info("标定模式: XY平面仿射变换 + Z轴线性映射")
                else:
                    logger.info("标定模式: 仅XY平面仿射变换，Z轴保持单位映射（z_robot = z_world）")
        except Exception as calib_err:
            if logger:
                logger.error(f"标定计算失败: {calib_err}")
            return MQTTResponse(
                command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                component="calibrator",
                messageType=MessageType.ERROR,
                message="calibration_calculation_failed",
                data={"error": str(calib_err)}
            )
        
        # 7. 提取结果
        metadata = result['metadata']
        
        if logger:
            calibration_mode = metadata.get('calibration_mode', 'xy_only')
            if calibration_mode == 'xy_only':
                logger.info(
                    f"XY平面标定成功 | 点数={metadata['calibration_points_count']} | "
                    f"XY_RMSE=({metadata['xy_rmse_x']:.2f}, {metadata['xy_rmse_y']:.2f})mm | "
                    f"总体2D_RMSE={metadata['overall_rmse_2d']:.2f}mm | "
                    f"Z轴使用单位映射"
                )
            else:
                logger.info(
                    f"完整XYZ标定成功 | 点数={metadata['calibration_points_count']} | "
                    f"XY_RMSE=({metadata['xy_rmse_x']:.2f}, {metadata['xy_rmse_y']:.2f})mm | "
                    f"Z_RMSE={metadata['z_rmse']:.2f}mm | "
                    f"总体2D_RMSE={metadata['overall_rmse_2d']:.2f}mm"
                )
        
        # 8. 返回成功结果
        return MQTTResponse(
            command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
            component="calibrator",
            messageType=MessageType.SUCCESS,
            message="calibration_completed",
            data={
                'success': True,
                'calibration_mode': metadata.get('calibration_mode', 'xy_only'),
                'calibration_points': metadata['calibration_points_count'],
                'rmse_x': round(metadata['xy_rmse_x'], 3),
                'rmse_y': round(metadata['xy_rmse_y'], 3),
                'rmse_z': round(metadata['z_rmse'], 3),
                'rmse_2d': round(metadata['overall_rmse_2d'], 3),
                'quality': _assess_quality(metadata),
                'matrix': result['matrix'].tolist(),
                'matrix_file': str(output_path),
                'timestamp': metadata.get('calibration_datetime', ''),
                'note': 'XY平面标定完成，Z轴保持单位映射（z_robot = z_world）' if metadata.get('calibration_mode') == 'xy_only' else '完整XYZ标定完成'
            }
        )
    
    except Exception as e:
        if logger:
            logger.error(f"coordinate_calibration异常: {e}")
        return MQTTResponse(
            command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
            component="system",
            messageType=MessageType.ERROR,
            message=str(e),
            data={}
        )


# ==================== 辅助函数 ====================



def _assess_quality(metadata: dict) -> str:
    """评估标定质量"""
    rmse_2d = metadata.get('overall_rmse_2d', float('inf'))
    rmse_z = metadata.get('z_rmse', float('inf'))
    
    if rmse_2d < 3.0 and rmse_z < 5.0:
        return "excellent"
    elif rmse_2d < 5.0 and rmse_z < 10.0:
        return "good"
    elif rmse_2d < 10.0 and rmse_z < 20.0:
        return "acceptable"
    else:
        return "poor"
