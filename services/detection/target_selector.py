#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
目标选择模块
负责从检测结果中选择最佳目标
"""

from typing import List, Optional, Dict, Any
import numpy as np


class TargetSelector:
    """
    目标选择器
    提供多种目标选择策略
    """
    
    @staticmethod
    def select_by_multi_roi_priority(
        detection_results: List[Any],
        roi_configs: List[Dict],
        min_area: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        按多ROI优先级和面积阈值选择最佳目标
        
        选择逻辑：
        1. ROI区域内（ROI可能有多个）
        2. ROI优先级高（从高到低遍历）
        3. Mask大于minArea
        4. Mask最大
        
        Args:
            detection_results: 检测结果列表（DetectionBox对象列表）
            roi_configs: ROI配置列表，每个配置包含：
                        {
                            'x1': int, 'y1': int, 'x2': int, 'y2': int,
                            'priority': int,  # 优先级（数字越小优先级越高）
                            'name': str  # 可选
                        }
            min_area: 最小面积阈值（像素），默认0.0表示不过滤
        
        Returns:
            最佳目标信息字典，包含：
            {
                'target_id': int,
                'detection': object,
                'center': [x, y],
                'area': float,
                'score': float,
                'class_id': int,
                'roi_priority': int,  # 目标所在ROI的优先级
                'roi_name': str       # 目标所在ROI的名称
            }
            无有效目标时返回None
        """
        if not detection_results or not roi_configs:
            return None
        
        try:
            from .roi_processor import RoiProcessor
        except ImportError:
            return None
        
        # 提取所有ROI，按优先级排序（数字越小优先级越高）
        valid_rois = [roi for roi in roi_configs if isinstance(roi, dict)]
        
        if not valid_rois:
            return None
        
        # 按priority排序（优先级数字越小越高）
        valid_rois.sort(key=lambda r: r.get('priority', 999))
        
        # 准备候选目标列表，添加目标的基本信息
        candidates = []
        filtered_by_area = 0
        filtered_by_roi = 0
        
        for idx, detection in enumerate(detection_results):
            try:
                # 获取中心点
                xmin = float(getattr(detection, 'xmin', 0))
                ymin = float(getattr(detection, 'ymin', 0))
                xmax = float(getattr(detection, 'xmax', 0))
                ymax = float(getattr(detection, 'ymax', 0))
                center_x = 0.5 * (xmin + xmax)
                center_y = 0.5 * (ymin + ymax)
                
                # 获取mask面积
                mask = getattr(detection, 'seg_mask', None)
                if mask is not None and isinstance(mask, np.ndarray):
                    area = float(np.sum(mask > 0))
                else:
                    # 没有mask，使用矩形面积
                    area = (xmax - xmin) * (ymax - ymin)
                
                # 面积过滤
                if area < min_area:
                    filtered_by_area += 1
                    continue
                
                # 获取其他属性
                score = float(getattr(detection, 'score', 0.0))
                class_id = int(getattr(detection, 'classId', getattr(detection, 'class_id', 0)))
                
                # 检查该目标在哪些ROI内，记录优先级最高的ROI
                best_roi_priority = None
                best_roi_name = None
                
                for roi in valid_rois:
                    if RoiProcessor.is_point_in_roi(center_x, center_y, roi):
                        # 找到第一个（优先级最高的）包含该目标的ROI
                        best_roi_priority = roi.get('priority', 999)
                        best_roi_name = roi.get('name', f"roi_p{best_roi_priority}")
                        break  # 找到最高优先级ROI后立即退出
                
                # 如果目标不在任何ROI内，跳过
                if best_roi_priority is None:
                    filtered_by_roi += 1
                    continue
                
                candidates.append({
                    'target_id': idx + 1,
                    'detection': detection,
                    'center': [center_x, center_y],
                    'area': area,
                    'score': score,
                    'class_id': class_id,
                    'roi_priority': best_roi_priority,
                    'roi_name': best_roi_name
                })
                
            except Exception as e:
                continue
        
        if not candidates:
            return None
        
        # 按选择逻辑排序并选择最佳目标：
        # 1. 优先级高（priority数字小）
        # 2. 面积大
        # 使用稳定排序，先按面积降序，再按优先级升序
        candidates.sort(key=lambda c: (-c['area'], c['roi_priority']))
        
        # 实际上我们需要先按优先级分组，在每个优先级内选择最大面积
        # 选择优先级最高（数字最小）的ROI组
        best_priority = min(c['roi_priority'] for c in candidates)
        
        # 筛选出优先级最高的ROI中的所有目标
        top_priority_candidates = [c for c in candidates if c['roi_priority'] == best_priority]
        
        # 在这些目标中选择面积最大的
        best = max(top_priority_candidates, key=lambda c: c['area'])
        
        return best

