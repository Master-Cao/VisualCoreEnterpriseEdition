#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检测结果可视化模块
负责绘制检测框、mask、ROI等可视化元素
"""

from typing import List, Optional, Dict, Any
import cv2
import numpy as np


class DetectionVisualizer:
    """
    检测结果可视化器
    提供统一的检测结果绘制功能
    """
    
    # 默认颜色列表（用于不同类别）
    DEFAULT_COLORS = [
        (0, 255, 0),    # 绿色
        (255, 0, 0),    # 蓝色
        (0, 0, 255),    # 红色
        (255, 255, 0),  # 青色
        (255, 0, 255),  # 品红
        (0, 255, 255),  # 黄色
    ]
    
    @staticmethod
    def draw_detections(
        image: np.ndarray, 
        detection_results: List[Any], 
        class_names: Optional[List[str]] = None,
        show_mask: bool = True,
        show_contour: bool = True,
        show_bbox: bool = True,
        colors: Optional[List[tuple]] = None
    ) -> np.ndarray:
        """
        在图像上绘制检测结果
        
        Args:
            image: 输入图像（灰度或BGR）
            detection_results: 检测结果列表（DetectionBox对象列表）
            class_names: 类别名称列表，默认None则使用class_id
            show_mask: 是否绘制分割mask，默认True
            show_contour: 是否绘制轮廓，默认True
            show_bbox: 是否绘制边界框，默认True
            colors: 自定义颜色列表，默认None则使用默认颜色
            
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
            
            # 使用自定义颜色或默认颜色
            color_palette = colors if colors else DetectionVisualizer.DEFAULT_COLORS
            
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
                color = color_palette[int(class_id) % len(color_palette)]
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
                
                # 不绘制标签（类名、置信度等）
            
            return annotated_image
            
        except Exception:
            # 如果绘制失败，返回原图像的副本
            if len(image.shape) == 2:
                return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            return image.copy()
    
    @staticmethod
    def draw_roi(
        image: np.ndarray,
        roi_config: Optional[Dict] = None,
        color: tuple = (0, 255, 255),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图像上绘制ROI区域（矩形）
        
        Args:
            image: 输入图像
            roi_config: ROI配置字典
            color: ROI边框颜色，默认黄色(0, 255, 255)
            thickness: 线条粗细，默认2
        
        Returns:
            绘制了ROI的图像
        """
        try:
            # 确保图像是彩色的
            if len(image.shape) == 2 or image.shape[2] == 1:
                result = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            else:
                result = image.copy()
            
            # 检查ROI配置是否有效
            if not roi_config:
                return result
            
            # 获取矩形边界
            x1 = roi_config.get('x1')
            y1 = roi_config.get('y1')
            x2 = roi_config.get('x2')
            y2 = roi_config.get('y2')
            
            if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                # 绘制矩形边框
                cv2.rectangle(
                    result,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    color,
                    thickness
                )
            
            return result
            
        except Exception:
            return image.copy()
    
    @staticmethod
    def draw_crosshair(
        image: np.ndarray,
        center_x: int,
        center_y: int,
        size: int = 20,
        color: tuple = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图像上绘制十字准星
        
        Args:
            image: 输入图像
            center_x, center_y: 十字准星中心坐标
            size: 十字准星大小（半径）
            color: 颜色，默认绿色
            thickness: 线条粗细
        
        Returns:
            绘制了十字准星的图像
        """
        try:
            result = image.copy()
            
            # 绘制水平线
            cv2.line(
                result,
                (center_x - size, center_y),
                (center_x + size, center_y),
                color,
                thickness
            )
            
            # 绘制垂直线
            cv2.line(
                result,
                (center_x, center_y - size),
                (center_x, center_y + size),
                color,
                thickness
            )
            
            # 绘制中心点
            cv2.circle(result, (center_x, center_y), 3, color, -1)
            
            return result
            
        except Exception:
            return image.copy()
    

