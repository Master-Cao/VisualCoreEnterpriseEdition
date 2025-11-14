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
        
        # 2. 获取相机帧和图像数据
        # 使用新的 get_frame 方法，获取所有需要的数据
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
        depthmap = result.get('depthmap')
        camera_params = result.get('cameraParams')
        
        # 3. 检查数据完整性
        if img is None:
            return MQTTResponse(
                command=VisionCoreCommands.GET_CALIBRAT_IMAGE.value,
                component="camera",
                messageType=MessageType.ERROR,
                message="image_conversion_failed",
                data={}
            )
        
        if not depthmap or not camera_params:
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
        
        # 5. 计算世界坐标
        width = int(getattr(camera_params, 'width', 0))
        height = int(getattr(camera_params, 'height', 0))
        depth_data = list(getattr(depthmap, 'z', []))
        
        points_info = []
        for i, block in enumerate(blocks):
            xyz = _compute_world_coordinate(
                block.center_u, block.center_v,
                depth_data, width, height, camera_params
            )
            
            if xyz is None:
                if logger:
                    logger.warning(f"块{i+1}({block.center_u},{block.center_v})世界坐标计算失败")
                points_info.append({
                    'index': i + 1,
                    'pixel_u': block.center_u,
                    'pixel_v': block.center_v,
                    'valid': False,
                    'world_x': None,
                    'world_y': None,
                    'world_z': None
                })
            else:
                points_info.append({
                    'index': i + 1,
                    'pixel_u': block.center_u,
                    'pixel_v': block.center_v,
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
        if ctx.sftp:
            try:
                annotated_img = _annotate_blocks(img, blocks)
                jpg = ImageUtils.encode_jpg(annotated_img)
                if jpg:
                    upload_info = SftpHelper.upload_image_bytes(ctx.sftp, jpg, prefix="calib")
                    if upload_info and logger:
                        logger.info(f"标定图像已上传: {upload_info.get('filename')}")
            except Exception as upload_err:
                if logger:
                    logger.warning(f"标定图像上传失败: {upload_err}")
        
        # 7. 构造响应
        response_data = {
            'blocks_detected': len(blocks),
            'valid_points': valid_count,
            'points': points_info,
            'note': '请使用机器人示教器移动到每个点位，记录坐标后发送coordinate_calibration命令'
        }
        
        if upload_info:
            response_data['image_remote'] = upload_info
        
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
    
    Payload格式:
    {
        "world_points": [
            {"x": xw1, "y": yw1, "z": zw1},
            {"x": xw2, "y": yw2, "z": zw2},
            ...
        ],
        "robot_points": [
            {"x": xr1, "y": yr1, "z": zr1},
            {"x": xr2, "y": yr2, "z": zr2},
            ...
        ]
    }
    
    或简化格式（world_points从上次get_calibrat_image缓存获取）:
    {
        "robot_points": [...]
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
        
        world_points_raw = payload_data.get('world_points', [])
        robot_points_raw = payload_data.get('robot_points', [])
        
        if not robot_points_raw:
            return MQTTResponse(
                command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                component="calibrator",
                messageType=MessageType.ERROR,
                message="missing_robot_points",
                data={"hint": "payload中必须包含robot_points字段"}
            )
        
        # 2. 如果没有world_points，返回错误（需要先调用get_calibrat_image）
        if not world_points_raw:
            return MQTTResponse(
                command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
                component="calibrator",
                messageType=MessageType.ERROR,
                message="missing_world_points",
                data={"hint": "payload中必须包含world_points字段（从get_calibrat_image获取）"}
            )
        
        # 3. 解析坐标点
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
        
        # 4. 过滤有效点对
        world_valid = []
        robot_valid = []
        for i in range(min(len(world_points), len(robot_points))):
            if world_points[i] is not None and robot_points[i] is not None:
                world_valid.append(world_points[i])
                robot_valid.append(robot_points[i])
        
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
        
        # 5. 执行标定
        output_path = Path(ctx.project_root) / "configs" / "transformation_matrix.json"
        
        try:
            result = calibrate_from_points(world_valid, robot_valid, output_path)
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
        
        # 6. 提取结果
        metadata = result['metadata']
        
        if logger:
            logger.info(
                f"坐标标定成功 | 点数={metadata['calibration_points_count']} | "
                f"XY_RMSE=({metadata['xy_rmse_x']:.2f}, {metadata['xy_rmse_y']:.2f})mm | "
                f"Z_RMSE={metadata['z_rmse']:.2f}mm | "
                f"总体2D_RMSE={metadata['overall_rmse_2d']:.2f}mm"
            )
        
        # 7. 返回成功结果
        return MQTTResponse(
            command=VisionCoreCommands.COORDINATE_CALIBRATION.value,
            component="calibrator",
            messageType=MessageType.SUCCESS,
            message="calibration_completed",
            data={
                'success': True,
                'calibration_points': metadata['calibration_points_count'],
                'rmse_x': round(metadata['xy_rmse_x'], 3),
                'rmse_y': round(metadata['xy_rmse_y'], 3),
                'rmse_z': round(metadata['z_rmse'], 3),
                'rmse_2d': round(metadata['overall_rmse_2d'], 3),
                'quality': _assess_quality(metadata),
                'matrix': result['matrix'].tolist(),
                'matrix_file': str(output_path),
                'timestamp': metadata.get('calibration_datetime', '')
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

def _sample_depth_mm(depth_data: List[float], u: int, v: int, 
                     width: int, height: int, ksize: int = 5) -> Optional[float]:
    """采样深度值（使用中值滤波）"""
    if not depth_data or width <= 0 or height <= 0:
        return None
    
    u = int(np.clip(u, 0, width - 1))
    v = int(np.clip(v, 0, height - 1))
    
    half = max(1, ksize // 2)
    values = []
    
    for dv in range(-half, half + 1):
        vv = v + dv
        if vv < 0 or vv >= height:
            continue
        base = vv * width
        for du in range(-half, half + 1):
            uu = u + du
            if uu < 0 or uu >= width:
                continue
            idx = base + uu
            if 0 <= idx < len(depth_data):
                d = float(depth_data[idx])
                if d > 0:
                    values.append(d)
    
    if not values:
        return None
    return float(np.median(values))


def _uv_depth_to_world_xyz(u: float, v: float, depth_mm: float, camera_params) -> Optional[Tuple[float, float, float]]:
    """将像素坐标和深度转换为世界坐标"""
    try:
        from Rknn.RknnYolo import RKNN_YOLO
        
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
        
        ok, coords = RKNN_YOLO._calculate_3d_fast(
            None, float(u), float(v), float(depth_mm),
            cx, cy, fx, fy, k1, k2, f2rc, m_c2w
        )
        
        if not ok:
            return None
        
        return float(coords[0]), float(coords[1]), float(coords[2])
    
    except Exception:
        return None


def _compute_world_coordinate(u: int, v: int, depth_data: List[float],
                              width: int, height: int, camera_params) -> Optional[Tuple[float, float, float]]:
    """计算像素位置的世界坐标"""
    depth_mm = _sample_depth_mm(depth_data, u, v, width, height, ksize=5)
    if depth_mm is None or depth_mm <= 0:
        return None
    
    return _uv_depth_to_world_xyz(u, v, depth_mm, camera_params)


def _annotate_blocks(image: np.ndarray, blocks) -> np.ndarray:
    """在图像上标注检测到的黑块"""
    vis = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    
    for i, block in enumerate(blocks, start=1):
        # 画圆标记中心
        cv2.circle(vis, (block.center_u, block.center_v), 6, (0, 255, 0), -1)
        # 画编号
        cv2.putText(
            vis, str(i),
            (block.center_u + 8, block.center_v - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA
        )
    
    return vis



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
