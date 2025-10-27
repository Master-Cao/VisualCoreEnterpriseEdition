#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict
import numpy as np
import cv2


def _disk_mask(h, w, cy, cx, r):
    yy, xx = np.ogrid[:h, :w]
    return (((yy - cy) ** 2 + (xx - cx) ** 2) <= (r * r)).astype(np.uint8)


def build_roi_mask(height: int, width: int, roi: Dict) -> np.ndarray:
    if not roi or not roi.get('enable'):
        return np.ones((height, width), dtype=np.uint8)
    shape = str(roi.get('shape', 'rectangle')).lower()
    m = np.zeros((height, width), dtype=np.uint8)
    if shape == 'rectangle' and isinstance(roi.get('rect'), dict):
        x1 = int(roi['rect'].get('x1', 0)); y1 = int(roi['rect'].get('y1', 0))
        x2 = int(roi['rect'].get('x2', width)); y2 = int(roi['rect'].get('y2', height))
        x1 = max(0, x1); y1 = max(0, y1); x2 = min(width, x2); y2 = min(height, y2)
        m[y1:y2+1, x1:x2+1] = 255
        return (m > 0).astype(np.uint8)
    if shape == 'semicircle':
        cx = int(roi.get('center_x', width//2)); cy = int(roi.get('center_y', height//2)); r = int(roi.get('radius', min(width, height)//4))
        direction = str(roi.get('direction', 'bottom')).lower()
        cv2.ellipse(m, (cx, cy), (r, r), 0, 0, 360, 255, -1)
        if direction == 'bottom':
            m[:cy, :] = 0
        elif direction == 'top':
            m[cy:, :] = 0
        elif direction == 'right':
            m[:, :cx] = 0
        elif direction == 'left':
            m[:, cx:] = 0
        return (m > 0).astype(np.uint8)
    if shape.startswith('quarter_'):
        cx = int(roi.get('center_x', width//2)); cy = int(roi.get('center_y', height//2)); r = int(roi.get('radius', min(width, height)//4))
        cv2.ellipse(m, (cx, cy), (r, r), 0, 0, 360, 255, -1)
        sm = shape
        if sm.endswith('br') or sm.endswith('bottom_right'):
            m[:cy, :] = 0; m[:, :cx] = 0
        elif sm.endswith('bl') or sm.endswith('bottom_left'):
            m[:cy, :] = 0; m[:, cx:] = 0
        elif sm.endswith('tl') or sm.endswith('top_left'):
            m[cy:, :] = 0; m[:, cx:] = 0
        else:  # tr
            m[cy:, :] = 0; m[:, :cx] = 0
        return (m > 0).astype(np.uint8)
    # 默认全图
    m[:, :] = 255
    return (m > 0).astype(np.uint8)
