#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
RKNN检测器后端
实现基于RKNN的YOLOv8分割模型推理和后处理
"""

from typing import List, Optional
import logging
import math
import numpy as np
import cv2

try:
    from rknn.api import RKNN  # type: ignore
except ImportError:
    RKNN = None

from .base import DetectionService, DetectionBox


class RKNNDetector(DetectionService):
    """
    RKNN YOLOv8-Seg 检测器
    支持256x256输入的分割模型
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
        初始化RKNN检测器
        
        Args:
            model_path: RKNN模型路径
            conf_threshold: 置信度阈值
            nms_threshold: NMS阈值
            logger: 日志记录器
            target: 目标RKNPU平台
            device_id: 设备ID
        """
        if RKNN is None:
            raise RuntimeError("RKNN未安装，无法使用RKNN检测器")
        
        self._model_path = model_path
        self._conf = conf_threshold
        self._nms = nms_threshold
        self._logger = logger or logging.getLogger(__name__)
        self._target = target
        self._device_id = device_id
        self._rknn = None
        
        # YOLOv8-Seg 256x256 模型参数
        self._input_size = (256, 256)
        self._class_num = 2  # ['seasoning', 'hand']
        self._head_num = 3
        self._strides = [8, 16, 32]
        self._map_sizes = [[32, 32], [16, 16], [8, 8]]  # 对应stride的特征图尺寸
        self._mask_num = 32  # mask系数数量
        
        # 生成meshgrid（用于解码检测框）
        self._meshgrid = []
        self._generate_meshgrid()
    
    def _generate_meshgrid(self):
        """生成网格坐标，用于解码检测框"""
        self._meshgrid = []
        for index in range(self._head_num):
            h, w = self._map_sizes[index]
            for i in range(h):
                for j in range(w):
                    self._meshgrid.append(j + 0.5)
                    self._meshgrid.append(i + 0.5)
    
    @staticmethod
    def _sigmoid(x):
        """Sigmoid激活函数"""
        return 1.0 / (1.0 + math.exp(-x))
    
    @staticmethod
    def _iou_rect(a, b):
        """计算两个矩形的IoU
        
        Args:
            a, b: (xmin, ymin, xmax, ymax)
        
        Returns:
            float: IoU值
        """
        ixmin = max(a[0], b[0])
        iymin = max(a[1], b[1])
        ixmax = min(a[2], b[2])
        iymax = min(a[3], b[3])
        
        iw = max(0.0, ixmax - ixmin)
        ih = max(0.0, iymax - iymin)
        inter = iw * ih
        
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        union = area_a + area_b - inter
        
        if union <= 0:
            return 0.0
        return inter / union
    
    def _nms_rect(self, boxes, scores, classes):
        """NMS非极大值抑制
        
        Args:
            boxes: 检测框列表 [(xmin, ymin, xmax, ymax), ...]
            scores: 置信度列表
            classes: 类别ID列表
        
        Returns:
            List[int]: 保留的索引列表
        """
        idxs = list(range(len(boxes)))
        idxs.sort(key=lambda i: scores[i], reverse=True)
        kept = []
        
        while idxs:
            i = idxs.pop(0)
            kept.append(i)
            rest = []
            
            for j in idxs:
                # 不同类别不进行NMS
                if classes[j] != classes[i]:
                    rest.append(j)
                    continue
                
                # IoU小于阈值则保留
                if self._iou_rect(boxes[i], boxes[j]) <= self._nms:
                    rest.append(j)
            
            idxs = rest
        
        return kept
    
    def _postprocess_boxes(self, outputs, img_h, img_w):
        """
        YOLOv8-Seg后处理：解码检测框和mask系数
        
        Args:
            outputs: RKNN推理输出
            img_h: 原图高度
            img_w: 原图宽度
        
        Returns:
            tuple: (boxes, scores, classes, mask_coeffs)
        """
        output = [outputs[i].reshape((-1)) for i in range(len(outputs))]
        scale_h = img_h / float(self._input_size[1])
        scale_w = img_w / float(self._input_size[0])
        
        boxes = []
        scores = []
        classes = []
        mask_coeffs = []
        
        grid_index = -2
        
        for head_idx in range(self._head_num):
            # YOLOv8输出：reg(回归), cls(分类), mask(掩码系数)
            reg = output[head_idx * 2 + 0]
            cls = output[head_idx * 2 + 1]
            msk = output[6 + head_idx]
            
            h, w = self._map_sizes[head_idx]
            stride = self._strides[head_idx]
            
            for i in range(h):
                for j in range(w):
                    grid_index += 2
                    
                    for class_id in range(self._class_num):
                        # 计算分类置信度
                        cls_idx = class_id * h * w + i * w + j
                        cls_val = self._sigmoid(cls[cls_idx])
                        
                        if cls_val <= self._conf:
                            continue
                        
                        # 解码检测框
                        base_idx = i * w + j
                        x1 = (self._meshgrid[grid_index + 0] - reg[0 * h * w + base_idx]) * stride
                        y1 = (self._meshgrid[grid_index + 1] - reg[1 * h * w + base_idx]) * stride
                        x2 = (self._meshgrid[grid_index + 0] + reg[2 * h * w + base_idx]) * stride
                        y2 = (self._meshgrid[grid_index + 1] + reg[3 * h * w + base_idx]) * stride
                        
                        # 缩放到原图尺寸
                        xmin = max(0.0, x1 * scale_w)
                        ymin = max(0.0, y1 * scale_h)
                        xmax = min(float(img_w), x2 * scale_w)
                        ymax = min(float(img_h), y2 * scale_h)
                        
                        if xmax <= xmin or ymax <= ymin:
                            continue
                        
                        # 提取mask系数
                        mask_vec = [msk[m * h * w + base_idx] for m in range(self._mask_num)]
                        
                        boxes.append((xmin, ymin, xmax, ymax))
                        scores.append(float(cls_val))
                        classes.append(int(class_id))
                        mask_coeffs.append(mask_vec)
        
        return boxes, scores, classes, mask_coeffs
    
    def _decode_masks(self, proto, mask_coeffs, boxes, img_h, img_w):
        """
        解码分割掩码
        
        Args:
            proto: proto输出 (C, H, W)
            mask_coeffs: mask系数列表
            boxes: 检测框列表
            img_h: 原图高度
            img_w: 原图宽度
        
        Returns:
            List[np.ndarray]: 分割掩码列表（原图尺寸）
        """
        if not mask_coeffs or proto is None:
            return []
        
        try:
            proto = np.array(proto[0])
            if proto.ndim != 3:
                return []
            
            c, mh, mw = proto.shape
            proto2d = proto.reshape(c, -1)  # (C, H*W)
            
            masks = []
            for i, coeffs in enumerate(mask_coeffs):
                try:
                    # 计算mask: coeffs @ proto
                    coeffs_np = np.array(coeffs, dtype=np.float32).reshape(1, -1)
                    mask_low = coeffs_np @ proto2d  # (1, H*W)
                    mask_low = 1.0 / (1.0 + np.exp(-mask_low))  # sigmoid
                    mask_low = mask_low.reshape(mh, mw)
                    
                    # 缩放到原图尺寸
                    mask_full = cv2.resize(mask_low, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
                    
                    # 二值化
                    mask_bin = (mask_full > 0.5).astype(np.uint8)
                    
                    # 裁剪到检测框区域
                    xmin, ymin, xmax, ymax = boxes[i]
                    xmin = max(0, int(xmin))
                    ymin = max(0, int(ymin))
                    xmax = min(img_w, int(xmax))
                    ymax = min(img_h, int(ymax))
                    
                    # 创建只在检测框内的mask
                    mask_final = np.zeros((img_h, img_w), dtype=np.uint8)
                    if xmax > xmin and ymax > ymin:
                        mask_final[ymin:ymax, xmin:xmax] = mask_bin[ymin:ymax, xmin:xmax]
                    
                    masks.append(mask_final)
                    
                except Exception as e:
                    self._logger.warning(f"解码mask {i} 失败: {e}")
                    masks.append(np.zeros((img_h, img_w), dtype=np.uint8))
            
            return masks
            
        except Exception as e:
            self._logger.error(f"解码masks失败: {e}")
            return []
    
    def load(self):
        """加载RKNN模型"""
        try:
            self._rknn = RKNN(verbose=False)
            
            ret = self._rknn.load_rknn(self._model_path)
            if ret != 0:
                raise RuntimeError(f"加载RKNN模型失败: {self._model_path}")
            
            # 初始化运行时环境，使用多核NPU
            ret = self._rknn.init_runtime(
                target=self._target,
                device_id=self._device_id,
                core_mask=RKNN.NPU_CORE_0 | RKNN.NPU_CORE_1 | RKNN.NPU_CORE_2
            )
            if ret != 0:
                raise RuntimeError("初始化RKNN运行时环境失败")
            
            self._logger.info(f"RKNN模型加载成功: {self._model_path}")
            
        except Exception as e:
            if self._rknn is not None:
                try:
                    self._rknn.release()
                except:
                    pass
                self._rknn = None
            raise RuntimeError(f"加载RKNN模型失败: {e}")
    
    def detect(self, image) -> List[DetectionBox]:
        """
        执行目标检测
        
        Args:
            image: 输入图像 (BGR格式)
        
        Returns:
            List[DetectionBox]: 检测结果列表
        """
        if self._rknn is None:
            self.load()
        
        img_h, img_w = image.shape[:2]
        
        # 预处理
        img_resized = cv2.resize(image, self._input_size, interpolation=cv2.INTER_LINEAR)
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_rgb = np.expand_dims(img_rgb, 0)
        
        # RKNN推理
        try:
            outputs = self._rknn.inference(inputs=[img_rgb], data_format='nhwc')
        except Exception as e:
            self._logger.error(f"RKNN推理失败: {e}")
            return []
        
        # 后处理：解码检测框和mask系数
        boxes, scores, classes, mask_coeffs = self._postprocess_boxes(outputs, img_h, img_w)
        
        if not boxes:
            return []
        
        # NMS
        keep_indices = self._nms_rect(boxes, scores, classes)
        
        # 保留NMS后的结果
        kept_boxes = [boxes[i] for i in keep_indices]
        kept_scores = [scores[i] for i in keep_indices]
        kept_classes = [classes[i] for i in keep_indices]
        kept_coeffs = [mask_coeffs[i] for i in keep_indices]
        
        # 解码分割掩码
        masks = self._decode_masks(outputs[-1], kept_coeffs, kept_boxes, img_h, img_w)
        
        # 构建检测结果
        results = []
        for i in range(len(kept_boxes)):
            xmin, ymin, xmax, ymax = kept_boxes[i]
            mask = masks[i] if i < len(masks) else None
            
            box = DetectionBox(
                class_id=kept_classes[i],
                score=kept_scores[i],
                xmin=int(xmin),
                ymin=int(ymin),
                xmax=int(xmax),
                ymax=int(ymax),
                seg_mask=mask
            )
            results.append(box)
        
        return results
    
    def release(self):
        """释放RKNN资源"""
        if self._rknn is not None:
            try:
                self._rknn.release()
                self._logger.info("RKNN资源已释放")
            except Exception as e:
                self._logger.warning(f"释放RKNN资源时出错: {e}")
            finally:
                self._rknn = None
