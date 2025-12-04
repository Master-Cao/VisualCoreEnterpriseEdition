#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检测服务模块
提供目标检测、坐标处理、ROI处理、目标选择和可视化功能

注意：C++后端不在此处导入，由 factory 按需导入
"""

from .coordinate_processor import CoordinateProcessor
from .roi_processor import RoiProcessor
from .target_selector import TargetSelector
from .visualizer import DetectionVisualizer
from .factory import create_detector

__all__ = [
    'CoordinateProcessor',
    'RoiProcessor',
    'TargetSelector',
    'DetectionVisualizer',
    'create_detector',
]

