#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
图像处理工具模块
提供图像编码、转换等通用功能
"""

from typing import Optional
import cv2
import numpy as np


class ImageUtils:
    """
    图像处理工具类
    提供图像编码、格式转换等静态方法
    """
    
    @staticmethod
    def encode_jpg(image: np.ndarray, quality: int = 95) -> Optional[bytes]:
        """
        将图像编码为JPG格式
        
        Args:
            image: 输入图像（numpy数组）
            quality: JPEG质量（0-100），默认95
            
        Returns:
            JPG格式的字节数据，失败返回None
        """
        try:
            if image is None:
                return None
            
            # JPEG编码参数
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            
            ok, buf = cv2.imencode(".jpg", image, encode_params)
            if not ok:
                return None
            
            return bytes(buf)
            
        except Exception:
            return None
    

