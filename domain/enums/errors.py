#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TCP检测错误码枚举
"""

from enum import Enum


class TcpErrorCode(Enum):
    """TCP检测命令错误码"""
    
    # 1xxx: 请求限制类错误
    TOO_FREQUENT = 1001         # 命令过于频繁（防抖）
    STILL_PROCESSING = 1002     # 上一条命令仍在处理中
    COMPONENT_NOT_READY = 1003  # 关键组件未就绪
    
    # 2xxx: 检测流程类错误
    DETECTION_FAILED = 2002     # 检测流程失败
    
    # 9xxx: 系统级错误
    UNKNOWN_ERROR = 9000        # 未知错误
    
    def to_response(self) -> str:
        """转换为TCP响应格式: "错误码,0,0,0,0" """
        return f"{self.value},0,0,0,0"
    
    @property
    def description(self) -> str:
        """获取错误描述"""
        descriptions = {
            self.TOO_FREQUENT: "命令过于频繁",
            self.STILL_PROCESSING: "上一条命令仍在处理中",
            self.COMPONENT_NOT_READY: "关键组件未就绪",
            self.DETECTION_FAILED: "检测流程失败",
            self.UNKNOWN_ERROR: "未知错误"
        }
        return descriptions.get(self, "未知错误")

