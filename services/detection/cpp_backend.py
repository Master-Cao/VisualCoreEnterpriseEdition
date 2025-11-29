#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
C++ RKNN检测器后端
使用C++实现的高性能检测器

注意：此模块要求 vc_detection_cpp 模块必须可用
     如果导入失败，将直接抛出异常，不会回退到Python版本
"""

from typing import List, Optional
import logging
import numpy as np

# 直接导入，失败则抛出异常
import vc_detection_cpp

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
            model_path: RKNN模型路径（相对路径或绝对路径）
            conf_threshold: 置信度阈值
            nms_threshold: NMS阈值
            logger: 日志记录器
            target: 目标RKNPU平台
            device_id: 设备ID（暂不支持）
        """
        import os
        
        self._logger = logger or logging.getLogger(__name__)
        self._conf = conf_threshold
        self._nms = nms_threshold
        self._target = target
        
        # 处理模型路径：转换为绝对路径
        if not os.path.isabs(model_path):
            # 相对路径：相对于项目根目录
            # 获取项目根目录（向上两级：cpp_backend.py -> detection -> services -> 根目录）
            current_file = os.path.abspath(__file__)
            project_root = os.path.abspath(os.path.join(os.path.dirname(current_file), "..", ".."))
            abs_model_path = os.path.join(project_root, model_path)
        else:
            # 已经是绝对路径
            abs_model_path = model_path
        
        # 规范化路径
        abs_model_path = os.path.normpath(abs_model_path)
        self._model_path = abs_model_path
        
        # 验证文件是否存在
        if not os.path.exists(abs_model_path):
            error_msg = (
                f"模型文件不存在: {abs_model_path}\n"
                f"原始路径: {model_path}\n"
                f"项目根目录: {project_root if not os.path.isabs(model_path) else 'N/A'}\n"
                f"请检查：\n"
                f"  1. 模型文件是否已下载到正确位置\n"
                f"  2. 配置文件中的路径是否正确"
            )
            if self._logger:
                self._logger.error(f"✗ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        if self._logger:
            self._logger.debug(f"模型路径解析: {model_path} -> {abs_model_path}")
        
        # 创建C++检测器实例
        try:
            self._detector = vc_detection_cpp.RKNNDetector(
                abs_model_path,  # 使用绝对路径
                conf_threshold, 
                nms_threshold, 
                target
            )
            self._released = False  # 防止重复释放
            if self._logger:
                self._logger.info(f"✓ C++ RKNN检测器初始化成功 | 模型: {os.path.basename(abs_model_path)}")
        except Exception as e:
            if self._logger:
                self._logger.error(f"✗ 创建C++ RKNN检测器失败: {e}")
            raise RuntimeError(
                f"创建C++ RKNN检测器失败: {e}\n"
                f"模型路径: {abs_model_path}\n"
                f"目标平台: {target}\n"
                f"请检查：\n"
                f"  1. 模型格式是否正确(.rknn)\n"
                f"  2. RKNN运行时库是否已安装\n"
                f"  3. NPU驱动是否正常\n"
                f"  4. 模型是否与目标平台匹配"
            ) from e
    
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
        # 防止重复释放
        if hasattr(self, '_released') and self._released:
            return
        
        if hasattr(self, '_detector') and self._detector:
            try:
                self._detector.release()
                if self._logger:
                    self._logger.info("✓ C++ RKNN资源已释放")
            except Exception as e:
                if self._logger:
                    self._logger.warning(f"释放C++ RKNN资源时出错: {e}")
            finally:
                try:
                    del self._detector
                except Exception:
                    pass
                self._detector = None
                if hasattr(self, '_released'):
                    self._released = True
    
    def __del__(self):
        """析构函数：确保C++资源被释放"""
        try:
            if not getattr(self, '_released', False):
                self.release()
        except Exception:
            pass

