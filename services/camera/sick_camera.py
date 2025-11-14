#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SICK 相机服务封装（基于官方 SDK common 包）
- 提供最小接口：connect()/disconnect()/get_frame()
- 支持单步触发或连续流
"""

import logging
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union
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

import cv2
import numpy as np


class SickCamera:
    _LEVEL_ALIASES = {
        "run": Control.USERLEVEL_OPERATOR,
        "operator": Control.USERLEVEL_OPERATOR,
        "maintenance": Control.USERLEVEL_MAINTENANCE,
        "maint": Control.USERLEVEL_MAINTENANCE,
        "client": Control.USERLEVEL_AUTH_CLIENT,
        "authorizedclient": Control.USERLEVEL_AUTH_CLIENT,
        "authclient": Control.USERLEVEL_AUTH_CLIENT,
        "service": Control.USERLEVEL_SERVICE,
    }

    def __init__(
        self,
        ip: str,
        port: int = 2122,
        protocol: str = "Cola2",
        use_single_step: bool = True,
        logger: Optional[logging.Logger] = None,
        login_attempts: Optional[Iterable[Union[Tuple[Union[int, str], str], Dict[str, Any]]]] = None,
    ):
        self._ip = ip
        self._port = port
        self._protocol = protocol
        self._use_single_step = use_single_step
        self._logger = logger or logging.getLogger(__name__)
        self._ctrl: Optional[Control] = None
        self._stream: Optional[Streaming] = None
        self._login_attempts: Sequence[Tuple[int, str]] = self._normalise_login_attempts(login_attempts)
        self.is_connected = False

    def connect(self) -> bool:
        try:
            # 控制通道
            self._ctrl = Control(self._ip, self._protocol, control_port=self._port)
            self._ctrl.open()
            self._perform_login()
            try:
                name, version = self._ctrl.getIdent()
                self.camera_name = name.decode("utf-8")
                self._logger.info(f"Connected device: {self.camera_name}, version: {version.decode('utf-8')}")
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

    def get_camera_name(self) -> Optional[str]:
        return getattr(self, "camera_name", None)

    def _normalise_login_attempts(
        self,
        attempts: Optional[Iterable[Union[Tuple[Union[int, str], str], Dict[str, Any]]]],
    ) -> Sequence[Tuple[int, str]]:
        default = [
            (Control.USERLEVEL_SERVICE, "123456"),
            (Control.USERLEVEL_AUTH_CLIENT, "CLIENT"),
        ]
        if not attempts:
            return default

        result = []
        for item in attempts:
            level_raw: Union[int, str, None]
            password: Optional[str]
            if isinstance(item, dict):
                level_raw = item.get("level")
                password = item.get("password")
            elif isinstance(item, tuple) and len(item) >= 2:
                level_raw = item[0]
                password = item[1]
            else:
                continue

            resolved_level = self._resolve_user_level(level_raw)
            if resolved_level is None or password is None:
                continue
            result.append((resolved_level, str(password)))

        return result or default

    def _resolve_user_level(self, value: Union[int, str, None]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        key = str(value).strip().lower()
        return self._LEVEL_ALIASES.get(key)

    def _perform_login(self) -> None:
        if not self._ctrl:
            return

        for level, password in self._login_attempts:
            try:
                self._ctrl.login(level, password)
                level_name = None
                try:
                    level_name = Control.USER_LEVEL_NAMES[level]
                except Exception:
                    level_name = str(level)
                self._logger.info(f"登录设备成功，级别 {level_name}")
                return
            except Exception as exc:
                self._logger.warning(f"尝试登录级别 {level} 失败: {exc}")

        raise RuntimeError("未能成功登录 SICK 相机，无法继续后续写操作")

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

    def get_frame(
        self,
        depth: bool = True,
        intensity: bool = True,
        camera_params: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        获取相机帧并返回处理后的数据
        
        参考 SickSDK._get_frame_data 的实现
        convert_to_mm 固定为 True
        
        Args:
            depth: 是否返回深度数据（depthmap对象），默认True
            intensity: 是否返回处理后的强度图像，默认True
            camera_params: 是否返回相机内参，默认True
            
        Returns:
            dict: {
                'depthmap': depthmap object or None,  # 原始深度图对象（包含distance/z/intensity/confidence等）
                'intensity_image': np.ndarray or None,  # 处理后的强度图像
                'cameraParams': CameraParams or None  # 相机内参
            }
            或 None（如果获取失败）
        """
        if not self.is_connected or not self._ctrl or not self._stream:
            self._logger.error("Camera not connected")
            return None
            
        try:
            if self._use_single_step:
                self._ctrl.singleStep()
            
            # 获取帧数据（参考 SickSDK._get_frame_data 的实现）
            self._stream.getFrame()
            wholeFrame = self._stream.frame
            
            # 解析数据（convert_to_mm 固定为 True）
            parser = Data()
            parser.read(wholeFrame, convertToMM=True)
            
            if not getattr(parser, "hasDepthMap", False):
                self._logger.error("No depth map data available")
                return None
            
            dm = parser.depthmap
            params = parser.cameraParams
            
            # 准备返回结果
            result: Dict[str, Any] = {
                'depthmap': None,
                'intensity_image': None,
                'cameraParams': None
            }
            
            # 返回深度数据列表（与 VisionCore 中的格式一致）
            if depth:
                # 提取 distance 数据并转换为 list（单位：毫米）
                distance_data = getattr(dm, 'distance', None)
                if distance_data is not None:
                    result['depthmap'] = list(distance_data)
                else:
                    # 回退：尝试使用 z 数据
                    z_data = getattr(dm, 'z', None)
                    if z_data is not None:
                        result['depthmap'] = list(z_data)
                    else:
                        self._logger.warning("深度图对象没有 distance 或 z 属性")
            
            # 处理强度图像
            if intensity:
                # 获取图像尺寸
                width = int(getattr(params, 'width', 0) or getattr(params, 'Width', 0) or 0)
                height = int(getattr(params, 'height', 0) or getattr(params, 'Height', 0) or 0)
                
                if width > 0 and height > 0:
                    intensity_data = getattr(dm, 'intensity', None)
                    if intensity_data is not None:
                        # 重塑为图像数组
                        intensity_array = np.array(list(intensity_data), dtype=np.float32).reshape((height, width))
                        # 调整对比度（与SickSDK._get_frame_data保持一致：alpha=0.05, beta=1）
                        adjusted_image = cv2.convertScaleAbs(intensity_array, alpha=0.05, beta=1)
                        result['intensity_image'] = adjusted_image
            
            # 返回相机参数
            if camera_params:
                result['cameraParams'] = params
                
            return result
            
        except Exception as e:
            self._logger.error(f"SickCamera get_frame failed: {e}")
            return None

    @property
    def healthy(self) -> bool:
        return bool(self.is_connected)
