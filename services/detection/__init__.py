#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检测服务模块
提供目标检测、坐标处理、ROI处理、目标选择和可视化功能
"""

from .coordinate_processor import CoordinateProcessor
from .roi_processor import RoiProcessor
from .target_selector import TargetSelector
from .visualizer import DetectionVisualizer
from .factory import create_detector

# 尝试导入C++后端（可选）
try:
    from .cpp_backend import CPPRKNNDetector, is_cpp_detector_available, get_cpp_detector_info
    _cpp_available = True
except ImportError:
    _cpp_available = False
    CPPRKNNDetector = None
    is_cpp_detector_available = lambda: False
    get_cpp_detector_info = lambda: {'available': False, 'error': 'Module not compiled'}

__all__ = [
    'CoordinateProcessor',
    'RoiProcessor',
    'TargetSelector',
    'DetectionVisualizer',
    'create_detector',
    'is_cpp_detector_available',
    'get_cpp_detector_info',
]

# 如果C++模块可用，也导出
if _cpp_available:
    __all__.append('CPPRKNNDetector')

