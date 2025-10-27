#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SICK 相机服务封装（基于官方 SDK common 包）
- 提供最小接口：connect()/disconnect()/get_frame()
- 支持单步触发或连续流
"""

import logging
from typing import Any, Dict, Optional
import os
import sys

# 确保官方 SDK 的顶层包名 'common' 可被导入
_SICK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "infrastructure", "sick"))
if _SICK_ROOT not in sys.path:
    sys.path.insert(0, _SICK_ROOT)

from infrastructure.sick.common.Control import Control
from infrastructure.sick.common.Stream import Streaming
from infrastructure.sick.common.Streaming.BlobServerConfiguration import BlobClientConfig
from infrastructure.sick.common.Streaming.Data import Data


class SickCamera:
    def __init__(self, ip: str, port: int = 2122, protocol: str = "Cola2", use_single_step: bool = True, logger: Optional[logging.Logger] = None):
        self._ip = ip
        self._port = port
        self._protocol = protocol
        self._use_single_step = use_single_step
        self._logger = logger or logging.getLogger(__name__)

        self._ctrl: Optional[Control] = None
        self._stream: Optional[Streaming] = None
        self.is_connected = False

    def connect(self) -> bool:
        try:
            # 控制通道
            self._ctrl = Control(self._ip, self._protocol, control_port=self._port)
            self._ctrl.open()
            try:
                name, version = self._ctrl.getIdent()
                self._logger.info(f"Connected device: {name.decode('utf-8')}, version: {version.decode('utf-8')}")
            except Exception:
                self._logger.info("Connected to device (no ident)")

            # BLOB 客户端配置
            cfg = BlobClientConfig()
            cfg.setTransportProtocol(self._ctrl, cfg.PROTOCOL_TCP)
            cfg.setBlobTcpPort(self._ctrl, 2114)

            # 数据流
            self._stream = Streaming(self._ip, 2114)
            self._stream.openStream()

            # 模式
            if self._use_single_step:
                self._ctrl.stopStream()
            else:
                self._ctrl.startStream()

            self.is_connected = True
            return True
        except Exception as e:
            self._logger.error(f"SickCamera connect failed: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        try:
            if self._ctrl:
                try:
                    self._ctrl.stopStream()
                except Exception:
                    pass
            if self._stream:
                try:
                    self._stream.closeStream()
                except Exception:
                    pass
            if self._ctrl:
                try:
                    self._ctrl.close()
                except Exception:
                    pass
        finally:
            self.is_connected = False
            self._ctrl = None
            self._stream = None

    def get_frame(self, convert_to_mm: bool = True) -> Optional[Dict[str, Any]]:
        if not self.is_connected or not self._ctrl or not self._stream:
            raise RuntimeError("Camera not connected")
        try:
            if self._use_single_step:
                self._ctrl.singleStep()
            # 请求一帧
            self._stream.sendBlobRequest()
            self._stream.getFrame()
            raw = bytes(self._stream.frame)
            parser = Data()
            parser.read(raw, convertToMM=convert_to_mm)
            # 输出关键结构
            out: Dict[str, Any] = {
                "hasDepthMap": getattr(parser, "hasDepthMap", False),
                "hasPolar2D": getattr(parser, "hasPolar2D", False),
                "hasCartesian": getattr(parser, "hasCartesian", False),
                "parsing_time_s": getattr(parser, "parsing_time_s", 0.0),
                "corrupted": getattr(parser, "corrupted", False),
            }
            if getattr(parser, "hasDepthMap", False):
                out["cameraParams"] = parser.cameraParams
                out["depthmap"] = parser.depthmap  # 包含 distance/intensity/confidence
            if getattr(parser, "hasPolar2D", False):
                out["polar2D"] = parser.polarData2D
            if getattr(parser, "hasCartesian", False):
                out["cartesian"] = parser.cartesianData
            return out
        except Exception as e:
            self._logger.error(f"SickCamera get_frame failed: {e}")
            return None

    @property
    def healthy(self) -> bool:
        return bool(self.is_connected)
