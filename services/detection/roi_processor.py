#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ROI处理模块
负责ROI区域判断、掩码创建和目标过滤
"""

from typing import Optional, List, Dict, Any
import numpy as np


class RoiProcessor:
    """
    ROI处理器
    提供统一的ROI相关功能（目前支持矩形ROI）
    """
    
    @staticmethod
    def is_point_in_roi(x: float, y: float, roi_config: Dict) -> bool:
        """
        检查点是否在ROI内（矩形）
        
        Args:
            x, y: 点坐标
            roi_config: ROI配置字典，包含以下字段：
                       - x1, y1, x2, y2: 矩形ROI边界
        
        Returns:
            点是否在ROI内
        """
        try:
            if not roi_config:
                return False
            
            x1 = roi_config.get('x1')
            y1 = roi_config.get('y1')
            x2 = roi_config.get('x2')
            y2 = roi_config.get('y2')
            
            # 如果边界未定义，返回False
            if x1 is None or y1 is None or x2 is None or y2 is None:
                return False
            
            # 检查点是否在矩形内
            return x1 <= x <= x2 and y1 <= y <= y2
            
        except Exception:
            return False
    
    @staticmethod
    def filter_detections_by_roi(
        detection_results: List[Any],
        roi_config: Optional[Dict] = None
    ) -> List[Any]:
        """
        根据ROI过滤检测结果
        
        Args:
            detection_results: 检测结果列表（DetectionBox对象列表）
            roi_config: ROI配置字典
        
        Returns:
            ROI内的检测结果列表
        """
        # 如果ROI未启用，返回全部结果
        if not roi_config or not roi_config.get('enable'):
            return detection_results
        
        filtered = []
        for detection in detection_results:
            try:
                # 计算检测框中心点
                xmin = float(getattr(detection, 'xmin', 0))
                ymin = float(getattr(detection, 'ymin', 0))
                xmax = float(getattr(detection, 'xmax', 0))
                ymax = float(getattr(detection, 'ymax', 0))
                center_x = 0.5 * (xmin + xmax)
                center_y = 0.5 * (ymin + ymax)
                
                # 检查中心点是否在ROI内
                if RoiProcessor.is_point_in_roi(center_x, center_y, roi_config):
                    filtered.append(detection)
            except Exception:
                continue
        
        return filtered
    

