#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import platform
from typing import Optional, Any

from .pc_ultralytics import PCUltralyticsDetector
from .rknn_backend import RKNNDetector
from .base import DetectionService


def create_detector(config: dict, logger: Optional[Any] = None) -> DetectionService:
    model_cfg = config.get("model") or {}
    backend = str(model_cfg.get("backend", "auto")).lower()
    model_path = str(model_cfg.get("path", ""))
    conf = float(model_cfg.get("conf_threshold", 0.5))
    nms = float(model_cfg.get("nms_threshold", 0.45))

    if backend == "auto":
        if sys.platform.startswith("win") or platform.system().lower().startswith("windows"):
            backend = "pc"
        else:
            backend = "rknn"

    if backend == "pc":
        return PCUltralyticsDetector(model_path=model_path, conf_threshold=conf, logger=logger)
    if backend == "rknn":
        return RKNNDetector(model_path=model_path, conf_threshold=conf, nms_threshold=nms, logger=logger)
    raise ValueError(f"Unknown detection backend: {backend}")
