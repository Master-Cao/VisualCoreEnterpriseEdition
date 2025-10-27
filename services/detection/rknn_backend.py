#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Optional
import logging
import numpy as np
import cv2

from .base import DetectionService, DetectionBox


class RKNNDetector(DetectionService):
    def __init__(self, model_path: str, conf_threshold: float = 0.5, nms_threshold: float = 0.45, logger: Optional[logging.Logger] = None):
        try:
            from rknn.api import RKNN  # type: ignore
        except Exception:
            raise ImportError("未安装 rknn-toolkit2，无法使用 RKNN 检测")
        self._RKNN = RKNN
        self._model_path = model_path
        self._conf = conf_threshold
        self._nms = nms_threshold
        self._logger = logger or logging.getLogger(__name__)
        self._rknn = None

    def load(self):
        self._rknn = self._RKNN(verbose=False)
        ret = self._rknn.load_rknn(self._model_path)
        if ret != 0:
            raise RuntimeError(f"Load RKNN model failed: {self._model_path}")
        ret = self._rknn.init_runtime()
        if ret != 0:
            raise RuntimeError("Init runtime failed")

    def detect(self, image) -> List[DetectionBox]:
        if self._rknn is None:
            self.load()
        h, w = image.shape[:2]
        img = cv2.resize(image, (256, 256), interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = np.expand_dims(img, 0)
        outs = self._rknn.inference(inputs=[img], data_format='nhwc')
        # 提示：此处需根据实际模型输出实现后处理（NMS/Seg），当前返回空结果以确保结构完整
        return []

    def release(self):
        if self._rknn is not None:
            try:
                self._rknn.release()
            except Exception:
                pass
            self._rknn = None
