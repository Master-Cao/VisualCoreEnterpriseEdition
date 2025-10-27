#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Optional
import logging

from .base import DetectionService, DetectionBox


class PCUltralyticsDetector(DetectionService):
    def __init__(self, model_path: str, conf_threshold: float = 0.5, logger: Optional[logging.Logger] = None):
        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as e:
            raise ImportError("未安装 ultralytics，无法在 PC 平台进行检测")
        self._YOLO = YOLO
        self._model_path = model_path
        self._conf = conf_threshold
        self._logger = logger or logging.getLogger(__name__)
        self._model = None

    def load(self):
        self._model = self._YOLO(self._model_path)

    def detect(self, image) -> List[DetectionBox]:
        if self._model is None:
            self.load()
        h, w = image.shape[:2]
        res = self._model.predict(image, imgsz=(256, 256), conf=self._conf, verbose=False)
        pred = res[0]
        boxes: List[DetectionBox] = []
        # 固定按分割模型解析
        try:
            masks = pred.masks.data.cpu().numpy()  # (N, H, W) at 256
        except Exception as e:
            raise RuntimeError("Ultralytics 结果不包含分割掩膜，请确认模型为分割模型") from e
        confs = pred.boxes.conf.cpu().numpy() if getattr(pred, 'boxes', None) is not None else None
        clss = pred.boxes.cls.cpu().numpy().astype(int) if getattr(pred, 'boxes', None) is not None else None
        import cv2
        scale_x = w / 256.0
        scale_y = h / 256.0
        for i in range(masks.shape[0]):
            mk = (masks[i] > 0.5).astype('uint8')
            cnts, _ = cv2.findContours(mk, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            cnt = max(cnts, cv2.contourArea)
            # 注意：cv2.minAreaRect 不是必须，这里直接用外接矩形
            xs = cnt[:, 0, 0] * scale_x
            ys = cnt[:, 0, 1] * scale_y
            xmin, ymin = int(xs.min()), int(ys.min())
            xmax, ymax = int(xs.max()), int(ys.max())
            score = float(confs[i]) if confs is not None and i < len(confs) else 1.0
            cls_id = int(clss[i]) if clss is not None and i < len(clss) else 0
            if score < self._conf:
                continue
            mask_full = cv2.resize(mk, (w, h), interpolation=cv2.INTER_NEAREST)
            boxes.append(DetectionBox(cls_id, score, xmin, ymin, xmax, ymax, seg_mask=(mask_full > 0).astype('uint8')))
        return boxes

    def release(self):
        self._model = None
