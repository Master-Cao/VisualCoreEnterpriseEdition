#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import platform
from typing import Optional, Any

from .pc_ultralytics import PCUltralyticsDetector
from .rknn_backend import RKNNDetector
from .base import DetectionService


def create_detector(config: dict, logger: Optional[Any] = None) -> DetectionService:
    """
    根据配置创建检测器实例
    
    Args:
        config: 配置字典，包含model配置
        logger: 日志记录器
    
    Returns:
        DetectionService: 检测器实例
    """
    model_cfg = config.get("model") or {}
    backend = str(model_cfg.get("backend", "auto")).lower()
    model_path = str(model_cfg.get("path", ""))
    conf = float(model_cfg.get("conf_threshold", 0.5))
    nms = float(model_cfg.get("nms_threshold", 0.45))

    # 自动选择后端
    if backend == "auto":
        if sys.platform.startswith("win") or platform.system().lower().startswith("windows"):
            backend = "pc"
        else:
            backend = "rknn"

    # 创建PC端检测器
    if backend == "pc":
        return PCUltralyticsDetector(
            model_path=model_path, 
            conf_threshold=conf, 
            logger=logger
        )
    
    # 创建RKNN检测器
    if backend == "rknn":
        # 获取RKNN特定参数
        target = str(model_cfg.get("target", "rk3588"))
        device_id = model_cfg.get("device_id")  # 可选
        
        return RKNNDetector(
            model_path=model_path, 
            conf_threshold=conf, 
            nms_threshold=nms, 
            logger=logger,
            target=target,
            device_id=device_id
        )
    
    raise ValueError(f"Unknown detection backend: {backend}")
