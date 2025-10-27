#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DetectionBox:
    class_id: int
    score: float
    xmin: int
    ymin: int
    xmax: int
    ymax: int
    seg_mask: Optional["np.ndarray"] = None  # 延迟导入以避免硬依赖


class DetectionService:
    def load(self):
        raise NotImplementedError

    def detect(self, image) -> List[DetectionBox]:
        raise NotImplementedError

    def release(self):
        pass
