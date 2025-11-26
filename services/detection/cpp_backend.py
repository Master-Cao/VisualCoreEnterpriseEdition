#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
C++ RKNN检测器后端
使用C++实现的高性能检测器
"""

from typing import List, Optional
import logging
import numpy as np
import sys
import os

# 尝试导入C++模块
try:
    # 添加C++模块的路径（支持多种路径布局）
    base_dir = os.path.dirname(__file__)
    possible_paths = [
        os.path.join(base_dir, '../cpp/dist/Release'),  # Windows 编译输出
        os.path.join(base_dir, '../cpp/dist'),           # 直接在 dist 目录
        os.path.join(base_dir, '../cpp/build'),          # Linux 编译输出
    ]
    
    # 尝试所有可能的路径
    for cpp_dist_path in possible_paths:
        cpp_dist_path = os.path.abspath(cpp_dist_path)
        if os.path.exists(cpp_dist_path) and cpp_dist_path not in sys.path:
            sys.path.insert(0, cpp_dist_path)
    
    import vc_detection_cpp
    CPP_MODULE_AVAILABLE = True
except ImportError as e:
    vc_detection_cpp = None
    CPP_MODULE_AVAILABLE = False
    _import_error = str(e)

from .base import DetectionService, DetectionBox


class CPPRKNNDetector(DetectionService):
    """
    C++实现的RKNN检测器
    提供更高性能的检测推理
    
    优势：
    - 更快的推理速度（C++实现）
    - 更低的内存占用
    - 更好的多核NPU利用率
    """
    
    def __init__(
        self, 
        model_path: str, 
        conf_threshold: float = 0.5, 
        nms_threshold: float = 0.45, 
        logger: Optional[logging.Logger] = None,
        target: str = 'rk3588',
        device_id: Optional[str] = None
    ):
        """
        初始化C++ RKNN检测器
        
        Args:
            model_path: RKNN模型路径
            conf_threshold: 置信度阈值
            nms_threshold: NMS阈值
            logger: 日志记录器
            target: 目标RKNPU平台
            device_id: 设备ID（暂不支持）
        """
        if not CPP_MODULE_AVAILABLE:
            raise RuntimeError(
                f"C++检测模块未编译或加载失败。\n"
                f"错误信息: {_import_error}\n"
                f"请确保已编译C++模块：\n"
                f"  cd services/cpp\n"
                f"  mkdir build && cd build\n"
                f"  cmake ..\n"
                f"  cmake --build .\n"
            )
        
        self._logger = logger or logging.getLogger(__name__)
        self._model_path = model_path
        self._conf = conf_threshold
        self._nms = nms_threshold
        self._target = target
        
        # 创建C++检测器实例
        try:
            self._detector = vc_detection_cpp.RKNNDetector(
                model_path, 
                conf_threshold, 
                nms_threshold, 
                target
            )
            self._logger.info("C++ RKNN检测器初始化成功")
        except Exception as e:
            self._logger.error(f"创建C++检测器失败: {e}")
            raise
    
    def load(self):
        """加载RKNN模型"""
        try:
            self._detector.load()
            self._logger.info(f"C++ RKNN模型加载成功: {self._model_path}")
        except Exception as e:
            raise RuntimeError(f"加载C++ RKNN模型失败: {e}")
    
    def detect(self, image) -> List[DetectionBox]:
        """
        执行目标检测
        
        Args:
            image: 输入图像 (numpy数组，BGR或灰度格式)
        
        Returns:
            List[DetectionBox]: 检测结果列表
        """
        try:
            # 确保图像是numpy数组
            if not isinstance(image, np.ndarray):
                raise TypeError("输入必须是numpy数组")
            
            # 确保是uint8类型
            if image.dtype != np.uint8:
                self._logger.warning(f"图像类型为{image.dtype}，转换为uint8")
                image = image.astype(np.uint8)
            
            # 确保是连续数组
            if not image.flags['C_CONTIGUOUS']:
                image = np.ascontiguousarray(image)
            
            # 调用C++检测器
            cpp_boxes = self._detector.detect(image)
            
            # 转换为Python DetectionBox
            results = []
            for cpp_box in cpp_boxes:
                # 获取分割掩码
                seg_mask = cpp_box.seg_mask if hasattr(cpp_box, 'seg_mask') else None
                
                box = DetectionBox(
                    class_id=cpp_box.class_id,
                    score=cpp_box.score,
                    xmin=cpp_box.xmin,
                    ymin=cpp_box.ymin,
                    xmax=cpp_box.xmax,
                    ymax=cpp_box.ymax,
                    seg_mask=seg_mask
                )
                results.append(box)
            
            self._logger.debug(f"C++检测完成，检测到{len(results)}个目标")
            return results
            
        except Exception as e:
            self._logger.error(f"C++检测失败: {e}")
            import traceback
            self._logger.error(traceback.format_exc())
            return []
    
    def release(self):
        """释放RKNN资源"""
        if hasattr(self, '_detector') and self._detector:
            try:
                self._detector.release()
                self._logger.info("C++ RKNN资源已释放")
            except Exception as e:
                self._logger.warning(f"释放C++ RKNN资源时出错: {e}")


def is_cpp_detector_available() -> bool:
    """
    检查C++检测器是否可用
    
    Returns:
        bool: True表示可用，False表示不可用
    """
    return CPP_MODULE_AVAILABLE


def get_cpp_detector_info() -> dict:
    """
    获取C++检测器信息
    
    Returns:
        dict: 包含版本、可用性等信息的字典
    """
    info = {
        'available': CPP_MODULE_AVAILABLE,
        'version': None,
        'error': None
    }
    
    if CPP_MODULE_AVAILABLE:
        try:
            info['version'] = getattr(vc_detection_cpp, '__version__', 'unknown')
        except:
            pass
    else:
        info['error'] = _import_error
    
    return info

