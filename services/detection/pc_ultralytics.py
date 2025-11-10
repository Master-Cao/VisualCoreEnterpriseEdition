#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PC端Ultralytics检测器
基于Ultralytics YOLO实现的分割模型检测
"""

from typing import List, Optional
import logging
import cv2
import numpy as np

from ultralytics import YOLO  # type: ignore

from .base import DetectionService, DetectionBox


class PCUltralyticsDetector(DetectionService):
    """
    PC端 Ultralytics YOLOv8-Seg 检测器
    用于Windows/Linux PC端的PyTorch模型推理
    """
    
    def __init__(self, model_path: str, conf_threshold: float = 0.5, logger: Optional[logging.Logger] = None):
        """
        初始化PC端检测器
        
        Args:
            model_path: PyTorch模型路径 (.pt)
            conf_threshold: 置信度阈值
            logger: 日志记录器
        """
        self._model_path = model_path
        self._conf = conf_threshold
        self._logger = logger or logging.getLogger(__name__)
        self._model = None

    def load(self):
        """加载Ultralytics YOLO模型"""
        try:
            self._model = YOLO(self._model_path)
            self._logger.info(f"Ultralytics模型加载成功: {self._model_path}")
        except Exception as e:
            raise RuntimeError(f"加载Ultralytics模型失败: {e}")

    def detect(self, image) -> List[DetectionBox]:
        """
        执行目标检测
        
        Args:
            image: 输入图像 (BGR格式)
        
        Returns:
            List[DetectionBox]: 检测结果列表
        """
        if self._model is None:
            self.load()
        
        img_h, img_w = image.shape[:2]
        
        # Ultralytics推理
        try:
            results = self._model.predict(
                image, 
                imgsz=(256, 256), 
                conf=self._conf, 
                verbose=False
            )
            pred = results[0]
        except Exception as e:
            self._logger.error(f"Ultralytics推理失败: {e}")
            return []
        
        # 解析分割结果
        boxes: List[DetectionBox] = []
        
        try:
            # 获取masks (N, H, W) 在256x256尺度
            masks = pred.masks.data.cpu().numpy()
        except Exception as e:
            raise RuntimeError("Ultralytics结果不包含分割掩膜，请确认模型为分割模型") from e
        
        # 获取置信度和类别
        confs = pred.boxes.conf.cpu().numpy() if getattr(pred, 'boxes', None) is not None else None
        clss = pred.boxes.cls.cpu().numpy().astype(int) if getattr(pred, 'boxes', None) is not None else None
        
        scale_x = img_w / 256.0
        scale_y = img_h / 256.0
        
        for i in range(masks.shape[0]):
            # 二值化mask
            mk = (masks[i] > 0.5).astype(np.uint8)
            
            # 提取轮廓
            cnts, _ = cv2.findContours(mk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            
            # 使用最大轮廓
            cnt = max(cnts, key=cv2.contourArea)
            
            # 计算外接矩形（缩放到原图尺寸）
            xs = cnt[:, 0, 0] * scale_x
            ys = cnt[:, 0, 1] * scale_y
            xmin = int(xs.min())
            ymin = int(ys.min())
            xmax = int(xs.max())
            ymax = int(ys.max())
            
            # 获取置信度和类别
            score = float(confs[i]) if confs is not None and i < len(confs) else 1.0
            class_id = int(clss[i]) if clss is not None and i < len(clss) else 0
            
            # 过滤低置信度
            if score < self._conf:
                continue
            
            # 缩放mask到原图尺寸
            mask_full = cv2.resize(mk, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
            mask_bin = (mask_full > 0).astype(np.uint8)
            
            # 创建DetectionBox
            box = DetectionBox(
                class_id=class_id,
                score=score,
                xmin=xmin,
                ymin=ymin,
                xmax=xmax,
                ymax=ymax,
                seg_mask=mask_bin
            )
            boxes.append(box)
        
        return boxes

    def release(self):
        """释放模型资源"""
        if self._model is not None:
            self._logger.info("Ultralytics模型资源已释放")
            self._model = None
