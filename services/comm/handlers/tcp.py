# -*- coding: utf-8 -*-

"""
TCP检测命令处理器
处理catch命令的完整检测流程
"""

import time
import json
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np

from domain.enums.commands import MessageType
from domain.enums.errors import TcpErrorCode
from domain.models.mqtt import MQTTResponse
from .context import CommandContext
from services.detection.coordinate_processor import CoordinateProcessor


# 全局状态（按客户端ID）
_last_tcp_command_time = {}
_tcp_processing_flags = {}


def handle_catch(req: MQTTResponse, ctx: CommandContext) -> MQTTResponse:
    """
    处理TCP catch命令：执行单次检测并返回坐标
    
    返回格式：
    - 成功: "count,x,y,z,angle"
    - 无目标: "0,0,0,0,0"
    - 错误: "错误码,0,0,0,0"
    """
    start_time = time.time()
    client_id = req.data.get("client_id", "unknown") if isinstance(req.data, dict) else "unknown"
    logger = ctx.logger
    
    try:
        # 1. 防抖检查
        current_time = time.time()
        debounce_time = _get_debounce_time(ctx.config)
        
        if client_id in _last_tcp_command_time:
            time_since_last = current_time - _last_tcp_command_time[client_id]
            if time_since_last < debounce_time:
                return _make_response(TcpErrorCode.TOO_FREQUENT.to_response())
        
        # 2. 并发控制
        if _tcp_processing_flags.get(client_id, False):
            return _make_response(TcpErrorCode.STILL_PROCESSING.to_response())
        
        _last_tcp_command_time[client_id] = current_time
        _tcp_processing_flags[client_id] = True
        
        try:
            # 3. 检查组件可用性
            if not ctx.camera or not ctx.detector or not ctx.config:
                return _make_response(TcpErrorCode.COMPONENT_NOT_READY.to_response())
            
            # 4. 执行检测
            result = _perform_detection(ctx)
            
            if result is None:
                return _make_response(TcpErrorCode.DETECTION_FAILED.to_response())
            
            # 5. 构造响应
            best_target = result.get('best_target')
            detection_count = result.get('detection_count', 0)
            
            if best_target and best_target.get('robot_3d'):
                # 检查面积阈值
                area = best_target.get('area', 0)
                min_area = _get_min_area(ctx.config)
                if area < min_area:
                    if logger:
                        logger.debug(f"Mask面积不足 | 面积={area:.0f}px < {min_area}px | 忽略")
                    return _make_response("0,0,0,0,0")
                
                # 获取坐标（不应用工具偏置）
                x, y, z = best_target['robot_3d']
                angle = best_target.get('angle', 0.0)
                
                # Z轴补偿和限制
                z_offset = _get_z_offset(ctx.config)
                z_final = z + z_offset
                if z_final < -85.0:
                    z_final = -85.0
                
                # 构造响应字符串
                response_str = f"{detection_count},{x:.3f},{y:.3f},{z_final:.3f},{angle:.3f}"
                
                # 记录日志
                if logger and detection_count > 0:
                    elapsed = (time.time() - start_time) * 1000
                    logger.info(
                        f"✓ 检测成功 | 客户端={client_id} | 数量={detection_count} | "
                        f"坐标=[X:{x:.2f}, Y:{y:.2f}, Z:{z_final:.2f}, A:{angle:.2f}] | "
                        f"面积={area:.0f}px | 耗时={elapsed:.1f}ms"
                    )
                
                return _make_response(response_str)
            else:
                # 无有效目标
                return _make_response("0,0,0,0,0")
        
        finally:
            _tcp_processing_flags[client_id] = False
    
    except Exception as e:
        if logger:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"处理catch命令异常: {e} | 耗时={elapsed:.1f}ms")
        return _make_response(TcpErrorCode.UNKNOWN_ERROR.to_response())


def _perform_detection(ctx: CommandContext) -> Optional[Dict[str, Any]]:
    """
    执行检测的核心流程
    
    Returns:
        包含检测结果的字典，失败返回None
    """
    logger = ctx.logger
    
    try:
        # 1. 获取相机帧
        frame_result = _get_camera_frame(ctx)
        if frame_result is None:
            return None
        
        image, depth_data, camera_params = frame_result
        
        # 2. 配置ROI
        roi_config = _build_roi_config(image.shape, ctx.config)
        
        # 3. 执行检测
        detection_boxes = ctx.detector.detect(image)
        
        if not detection_boxes:
            return {
                'detection_count': 0,
                'best_target': None
            }
        
        # 4. 加载变换矩阵
        transformation_matrix = _load_transformation_matrix(ctx.project_root)
        
        # 5. 坐标处理
        best_target = CoordinateProcessor.process_detection_to_coordinates(
            detection_boxes,
            depth_data,
            camera_params,
            roi_config,
            transformation_matrix
        )
        
        # 6. 统计ROI内的检测数量
        detection_count = _count_detections_in_roi(detection_boxes, roi_config)
        
        return {
            'detection_count': detection_count,
            'best_target': best_target
        }
    
    except Exception as e:
        if logger:
            logger.error(f"检测流程异常: {e}")
        return None


def _get_camera_frame(ctx: CommandContext) -> Optional[tuple]:
    """
    获取相机帧数据
    
    Returns:
        (image, depth_data, camera_params) 或 None
    """
    try:
        camera = ctx.camera
        if not hasattr(camera, 'get_frame'):
            return None
        
        frame_data = camera.get_frame(convert_to_mm=True)
        if not frame_data:
            return None
        
        # 提取图像
        depthmap = frame_data.get('depthmap')
        camera_params = frame_data.get('cameraParams')
        
        if not depthmap or not camera_params:
            return None
        
        # 构建图像数组
        width = getattr(camera_params, 'width', 0)
        height = getattr(camera_params, 'height', 0)
        intensity = getattr(depthmap, 'intensity', None)
        
        if not intensity or width <= 0 or height <= 0:
            return None
        
        import cv2
        arr = np.array(list(intensity), dtype=np.float32).reshape((height, width))
        image = cv2.convertScaleAbs(arr, alpha=0.05, beta=1)
        
        # 提取深度数据
        depth_data = list(getattr(depthmap, 'z', []))
        
        return (image, depth_data, camera_params)
    
    except Exception as e:
        if ctx.logger:
            ctx.logger.error(f"获取相机帧失败: {e}")
        return None


def _build_roi_config(image_shape: tuple, config: dict) -> Dict:
    """
    构建矩形ROI配置
    
    Args:
        image_shape: 图像形状 (height, width, ...)
        config: 系统配置
    
    Returns:
        ROI配置字典
    """
    roi_cfg = config.get('roi') or {}
    roi_enabled = bool(roi_cfg.get('enable', False))
    
    if not roi_enabled:
        return {'enabled': False}
    
    height, width = image_shape[:2]
    center_x = width // 2 + int(roi_cfg.get('offsetx', 0))
    center_y = height // 2 + int(roi_cfg.get('offsety', 0))
    
    # 矩形ROI配置
    roi_width = int(roi_cfg.get('width', 120))
    roi_height = int(roi_cfg.get('height', 140))
    
    x1 = max(0, center_x - roi_width // 2)
    y1 = max(0, center_y - roi_height // 2)
    x2 = min(width, x1 + roi_width)
    y2 = min(height, y1 + roi_height)
    
    return {
        'enabled': True,
        'x1': x1,
        'y1': y1,
        'x2': x2,
        'y2': y2
    }


def _load_transformation_matrix(project_root: str) -> Optional[np.ndarray]:
    """
    加载坐标变换矩阵
    
    Args:
        project_root: 项目根目录
    
    Returns:
        4x4变换矩阵，未找到返回None
    """
    try:
        matrix_path = Path(project_root) / "configs" / "transformation_matrix.json"
        if not matrix_path.exists():
            return None
        
        with open(matrix_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        matrix_data = data.get('matrix')
        if not matrix_data or len(matrix_data) != 4:
            return None
        
        return np.array(matrix_data, dtype=np.float64)
    
    except Exception:
        return None


def _count_detections_in_roi(detection_boxes: list, roi_config: Dict) -> int:
    """
    统计ROI内的检测数量
    
    Args:
        detection_boxes: 检测框列表
        roi_config: ROI配置
    
    Returns:
        ROI内的检测数量
    """
    if not roi_config.get('enabled'):
        return len(detection_boxes)
    
    count = 0
    for box in detection_boxes:
        center_x = 0.5 * (float(box.xmin) + float(box.xmax))
        center_y = 0.5 * (float(box.ymin) + float(box.ymax))
        
        if CoordinateProcessor._is_point_in_roi(center_x, center_y, roi_config):
            count += 1
    
    return count


def _get_debounce_time(config: dict) -> float:
    """获取防抖时间配置"""
    try:
        return float(config.get('stability', {}).get('debounceTime', 0.0))
    except Exception:
        return 0.0


def _get_z_offset(config: dict) -> float:
    """获取Z轴补偿配置"""
    try:
        return float(config.get('stability', {}).get('zOffset', 0.0))
    except Exception:
        return 0.0


def _get_min_area(config: dict) -> float:
    """获取最小面积阈值配置"""
    try:
        return float(config.get('roi', {}).get('minArea', 2500.0))
    except Exception:
        return 2500.0


def _make_response(response_str: str) -> MQTTResponse:
    """构造统一的响应对象"""
    return MQTTResponse(
        command="catch",
        component="tcp",
        messageType=MessageType.SUCCESS,
        message="ok",
        data={"response": response_str},
    )


