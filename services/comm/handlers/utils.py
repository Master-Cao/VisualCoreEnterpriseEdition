# -*- coding: utf-8 -*-

"""
Handlers 共享工具函数
避免在多个handler中重复相同的代码
"""

import os
from datetime import datetime
from typing import Optional, List

import cv2
import numpy as np


def encode_jpg(img) -> Optional[bytes]:
    """
    将图像编码为JPG格式
    
    Args:
        img: 输入图像
        
    Returns:
        JPG格式的字节数据，失败返回None
    """
    try:
        if cv2 is None:
            return None
        ok, buf = cv2.imencode(".jpg", img)
        if not ok:
            return None
        return bytes(buf)
    except Exception:
        return None


def upload_image_to_sftp(sftp, image_data: bytes, prefix: str = "image") -> Optional[dict]:
    """
    上传图像字节数据到SFTP服务器
    
    Args:
        sftp: SFTP客户端实例
        image_data: 图像字节数据
        prefix: 文件名前缀
        
    Returns:
        上传信息字典，包含文件名、路径等信息，失败返回None
        {
            "filename": 文件名,
            "remote_path": 远程目录路径,
            "remote_rel_path": 相对路径,
            "remote_file": 完整文件路径,
            "file_size": 文件大小
        }
    """
    try:
        if not sftp or image_data is None:
            return None
        
        # 生成带时间戳的文件名
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{prefix}_{ts}.jpg"
        
        # 构建远程路径（上传到 images 目录）
        remote_rel = os.path.join("images", filename).replace("\\", "/")
        
        # 使用SFTP客户端的upload_bytes方法上传
        ok = sftp.upload_bytes(image_data, remote_rel)
        if not ok:
            return None
        
        # 构建返回信息
        remote_dir = os.path.dirname(remote_rel).replace("\\", "/")
        if not remote_dir.startswith("/"):
            remote_dir = f"/{remote_dir}" if remote_dir else "/"
        if not remote_dir.endswith("/"):
            remote_dir = f"{remote_dir}/"
        remote_file = f"{remote_dir.rstrip('/')}/{filename}"
        
        return {
            "filename": filename,
            "remote_path": remote_dir,
            "remote_rel_path": remote_rel,
            "remote_file": remote_file,
            "file_size": len(image_data),
        }
    except Exception:
        return None


def select_best_target(
    detection_results: List,
    roi_config: Optional[dict] = None
) -> Optional[dict]:
    """
    从检测结果中选择最佳目标（参考 RknnYolo.process_detection_to_coordinates_fast）
    
    选择策略：
    1. ROI 内优先（若启用 ROI，则仅在 ROI 内选择；ROI 外不选）
    2. 选择 mask 面积最大的目标
    
    Args:
        detection_results: 检测结果列表（DetectionBox对象列表）
        roi_config: ROI配置字典，包含以下字段：
                   - enabled: 是否启用ROI
                   - shapeMode: ROI形状 ('rectangle', 'semicircle', 'quarter_tl'等)
                   - x1, y1, x2, y2: 矩形ROI边界
                   - center_x, center_y: 圆形ROI中心
                   - radius: 圆形ROI半径
                   - direction: 半圆方向
    
    Returns:
        最佳目标信息字典，包含：
        {
            'target_id': int,           # 目标在原列表中的索引+1
            'detection': object,        # 原始检测对象
            'center': [x, y],          # 目标中心点
            'area_full': float,        # 完整mask面积（像素）
            'area_in_roi': float,      # ROI内的mask面积（像素）
            'score': float,            # 置信度
            'class_id': int            # 类别ID
        }
        无有效目标时返回None
    """
    if not detection_results:
        return None
    
    # 按 ROI 过滤候选目标
    roi_enabled = bool(roi_config and roi_config.get('enable'))
    candidates = []
    
    for idx, detection in enumerate(detection_results):
        try:
            # 获取中心点
            xmin = float(getattr(detection, 'xmin', 0))
            ymin = float(getattr(detection, 'ymin', 0))
            xmax = float(getattr(detection, 'xmax', 0))
            ymax = float(getattr(detection, 'ymax', 0))
            center_x = 0.5 * (xmin + xmax)
            center_y = 0.5 * (ymin + ymax)
            
            # ROI 过滤检查
            if roi_enabled:
                inside_roi = _is_point_in_roi(center_x, center_y, roi_config)
                if not inside_roi:
                    continue  # ROI 外的目标直接跳过
            
            # 获取 mask 面积
            mask = getattr(detection, 'seg_mask', None)
            area_full = 0.0
            area_in_roi = 0.0
            
            if mask is not None and isinstance(mask, np.ndarray):
                # 计算完整面积
                area_full = float(np.sum(mask > 0))
                
                # 计算 ROI 内的面积
                if roi_enabled and roi_config:
                    # 创建 ROI mask
                    roi_mask = _create_roi_mask(mask.shape, roi_config)
                    if roi_mask is not None:
                        # 计算交集面积
                        area_in_roi = float(np.sum((mask > 0) & roi_mask))
                    else:
                        area_in_roi = area_full
                else:
                    area_in_roi = area_full
            else:
                # 没有 mask，使用矩形面积
                area_full = (xmax - xmin) * (ymax - ymin)
                area_in_roi = area_full
            
            # 获取其他属性
            score = float(getattr(detection, 'score', 0.0))
            class_id = int(getattr(detection, 'classId', getattr(detection, 'class_id', 0)))
            
            candidates.append({
                'target_id': idx + 1,
                'detection': detection,
                'center': [center_x, center_y],
                'area_full': area_full,
                'area_in_roi': area_in_roi,
                'score': score,
                'class_id': class_id
            })
            
        except Exception:
            continue
    
    if not candidates:
        return None
    
    # 选择 ROI 内面积最大的目标
    best = max(candidates, key=lambda c: c['area_in_roi'])
    
    return best


def _is_point_in_roi(x: float, y: float, roi_config: dict) -> bool:
    """
    检查点是否在ROI内（支持矩形、半圆、1/4圆）
    
    Args:
        x, y: 点坐标
        roi_config: ROI配置
    
    Returns:
        点是否在ROI内
    """
    try:
        shape_mode = roi_config.get('shapeMode', 'rectangle')
        
        if shape_mode == 'semicircle':
            # 半圆 ROI
            center_x = roi_config.get('center_x')
            center_y = roi_config.get('center_y')
            radius = roi_config.get('radius', 0)
            direction = roi_config.get('direction', 'bottom')
            
            if center_x is None or center_y is None:
                return True
            
            # 检查是否在圆内
            distance_squared = (x - center_x) ** 2 + (y - center_y) ** 2
            if distance_squared > radius ** 2:
                return False
            
            # 检查是否在正确的半边
            if direction == 'bottom':
                return y >= center_y
            elif direction == 'top':
                return y <= center_y
            elif direction == 'right':
                return x >= center_x
            elif direction == 'left':
                return x <= center_x
            else:
                return False
                
        elif shape_mode in ('quarter_tl', 'quarter_tr', 'quarter_bl', 'quarter_br'):
            # 1/4 圆 ROI
            center_x = roi_config.get('center_x')
            center_y = roi_config.get('center_y')
            radius = roi_config.get('radius', 0)
            
            if center_x is None or center_y is None:
                return True
            
            # 检查是否在圆内
            if (x - center_x) ** 2 + (y - center_y) ** 2 > radius ** 2:
                return False
            
            # 检查是否在正确的象限
            if shape_mode == 'quarter_tl':
                return x <= center_x and y <= center_y
            elif shape_mode == 'quarter_tr':
                return x >= center_x and y <= center_y
            elif shape_mode == 'quarter_bl':
                return x <= center_x and y >= center_y
            elif shape_mode == 'quarter_br':
                return x >= center_x and y >= center_y
            else:
                return False
        else:
            # 矩形 ROI（默认）
            x1 = roi_config.get('x1')
            y1 = roi_config.get('y1')
            x2 = roi_config.get('x2')
            y2 = roi_config.get('y2')
            
            if x1 is None or y1 is None or x2 is None or y2 is None:
                return True
            
            return x1 <= x <= x2 and y1 <= y <= y2
            
    except Exception:
        return True


def _create_roi_mask(shape: tuple, roi_config: dict) -> Optional[np.ndarray]:
    """
    创建ROI掩码（支持矩形、半圆、1/4圆）
    
    Args:
        shape: 图像形状 (height, width)
        roi_config: ROI配置
    
    Returns:
        ROI掩码（布尔数组），创建失败返回None
    """
    try:
        height, width = shape[:2]
        shape_mode = roi_config.get('shapeMode', 'rectangle')
        
        if shape_mode == 'semicircle':
            # 半圆 ROI mask
            center_x = roi_config.get('center_x', width // 2)
            center_y = roi_config.get('center_y', height // 2)
            radius = roi_config.get('radius', 100)
            direction = roi_config.get('direction', 'bottom')
            
            # 创建坐标网格
            y_coords, x_coords = np.ogrid[:height, :width]
            
            # 计算距离
            distance_squared = (x_coords - center_x) ** 2 + (y_coords - center_y) ** 2
            
            # 基础圆形掩码
            circle_mask = distance_squared <= radius ** 2
            
            # 根据方向创建半圆掩码
            if direction == 'bottom':
                direction_mask = y_coords >= center_y
            elif direction == 'top':
                direction_mask = y_coords <= center_y
            elif direction == 'right':
                direction_mask = x_coords >= center_x
            elif direction == 'left':
                direction_mask = x_coords <= center_x
            else:
                direction_mask = np.ones((height, width), dtype=bool)
            
            return circle_mask & direction_mask
            
        elif shape_mode in ('quarter_tl', 'quarter_tr', 'quarter_bl', 'quarter_br'):
            # 1/4 圆 ROI mask
            center_x = roi_config.get('center_x', width // 2)
            center_y = roi_config.get('center_y', height // 2)
            radius = roi_config.get('radius', 100)
            
            y_coords, x_coords = np.ogrid[:height, :width]
            distance_squared = (x_coords - center_x) ** 2 + (y_coords - center_y) ** 2
            circle_mask = distance_squared <= radius ** 2
            
            # 象限掩码
            if shape_mode == 'quarter_tl':
                quadrant_mask = (x_coords <= center_x) & (y_coords <= center_y)
            elif shape_mode == 'quarter_tr':
                quadrant_mask = (x_coords >= center_x) & (y_coords <= center_y)
            elif shape_mode == 'quarter_bl':
                quadrant_mask = (x_coords <= center_x) & (y_coords >= center_y)
            else:  # quarter_br
                quadrant_mask = (x_coords >= center_x) & (y_coords >= center_y)
            
            return circle_mask & quadrant_mask
            
        else:
            # 矩形 ROI mask（默认）
            x1 = roi_config.get('x1', 0)
            y1 = roi_config.get('y1', 0)
            x2 = roi_config.get('x2', width)
            y2 = roi_config.get('y2', height)
            
            mask = np.zeros((height, width), dtype=bool)
            x1 = max(0, min(int(x1), width))
            y1 = max(0, min(int(y1), height))
            x2 = max(0, min(int(x2), width))
            y2 = max(0, min(int(y2), height))
            
            if x2 > x1 and y2 > y1:
                mask[y1:y2, x1:x2] = True
            
            return mask
            
    except Exception:
        return None


def draw_detection_results(
    image, 
    detection_results: List, 
    class_names: Optional[List[str]] = None,
    show_mask: bool = True,
    show_contour: bool = True,
    show_bbox: bool = True
) -> np.ndarray:
    """
    在图像上绘制检测结果（参考 RknnYolo._draw_detection_annotations）
    
    Args:
        image: 输入图像（灰度或BGR）
        detection_results: 检测结果列表（DetectionBox对象列表）
        class_names: 类别名称列表，默认None则使用class_id
        show_mask: 是否绘制分割mask，默认True
        show_contour: 是否绘制轮廓，默认True
        show_bbox: 是否绘制边界框，默认True
        
    Returns:
        绘制了检测结果的图像
    """
    try:
        # 确保图像是彩色的
        if len(image.shape) == 2 or image.shape[2] == 1:
            annotated_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            annotated_image = image.copy()
        
        if not detection_results:
            return annotated_image
        
        # 定义颜色列表（用于不同类别）
        colors = [
            (0, 255, 0),    # 绿色
            (255, 0, 0),    # 蓝色
            (0, 0, 255),    # 红色
            (255, 255, 0),  # 青色
            (255, 0, 255),  # 品红
            (0, 255, 255),  # 黄色
        ]
        
        # 绘制所有检测目标
        for i, detection in enumerate(detection_results):
            # 获取类别ID和置信度
            try:
                class_id = getattr(detection, 'classId', getattr(detection, 'class_id', 0))
                confidence = float(getattr(detection, 'score', 0.0))
            except Exception:
                class_id = 0
                confidence = 0.0
            
            # 选择颜色
            color = colors[int(class_id) % len(colors)]
            line_thickness = 2
            
            # 绘制分割mask（若存在且启用）
            if show_mask:
                mask = getattr(detection, 'seg_mask', None)
                if mask is not None and isinstance(mask, np.ndarray):
                    try:
                        # 半透明填充
                        overlay = annotated_image.copy()
                        overlay[mask > 0] = color
                        cv2.addWeighted(overlay, 0.35, annotated_image, 0.65, 0, annotated_image)
                        
                        # 绘制轮廓
                        if show_contour:
                            # 优先使用预存的轮廓
                            contour = getattr(detection, 'contour', None)
                            if contour is not None:
                                try:
                                    cv2.polylines(annotated_image, [contour.reshape(-1, 1, 2)], True, color, line_thickness)
                                except Exception:
                                    pass
                            else:
                                # 从mask计算轮廓
                                contours, _ = cv2.findContours(
                                    (mask > 0).astype(np.uint8),
                                    cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE
                                )
                                if contours:
                                    largest_contour = max(contours, key=cv2.contourArea)
                                    cv2.drawContours(annotated_image, [largest_contour], -1, color, line_thickness)
                    except Exception:
                        pass
            
            # 绘制边界框（若启用或没有mask）
            if show_bbox or not show_mask:
                try:
                    xmin = int(getattr(detection, 'xmin', 0))
                    ymin = int(getattr(detection, 'ymin', 0))
                    xmax = int(getattr(detection, 'xmax', 0))
                    ymax = int(getattr(detection, 'ymax', 0))
                    cv2.rectangle(annotated_image, (xmin, ymin), (xmax, ymax), color, line_thickness)
                except Exception:
                    pass
            
            # 构建标签文本
            try:
                # 获取类别名称
                if class_names and 0 <= class_id < len(class_names):
                    class_label = class_names[class_id]
                else:
                    class_label = f"cls_{class_id}"
                
                # 获取面积（如果有）
                area_px = getattr(detection, 'area', None)
                if area_px is not None:
                    label = f"{class_label} {confidence:.2f} A:{area_px}"
                else:
                    label = f"{class_label} {confidence:.2f}"
            except Exception:
                label = f"obj {confidence:.2f}"
            
            # 计算标签位置（优先使用轮廓左上角，否则使用bbox左上角）
            try:
                contour = getattr(detection, 'contour', None)
                if contour is not None and hasattr(contour, 'shape'):
                    if contour.ndim == 2:
                        text_x = int(contour[:, 0].min())
                        text_y = int(contour[:, 1].min()) - 6
                    else:
                        pts = contour.reshape(-1, 2)
                        text_x = int(pts[:, 0].min())
                        text_y = int(pts[:, 1].min()) - 6
                else:
                    text_x = int(getattr(detection, 'xmin', 0))
                    text_y = int(getattr(detection, 'ymin', 0)) - 6
                
                # 确保标签在图像内
                if text_y < 10:
                    text_y = 10
            except Exception:
                text_x = 10
                text_y = 30 + i * 20
            
            # 绘制标签背景和文本
            try:
                (text_width, text_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                )
                # 背景矩形（黑色）
                cv2.rectangle(
                    annotated_image,
                    (text_x, text_y - text_height - 4),
                    (text_x + text_width + 4, text_y + 2),
                    (0, 0, 0),
                    -1
                )
                # 文本（白色）
                cv2.putText(
                    annotated_image,
                    label,
                    (text_x + 2, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA
                )
            except Exception:
                pass
        
        return annotated_image
        
    except Exception:
        # 如果绘制失败，返回原图像的副本
        if len(image.shape) == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        return image.copy()
