#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandRouter
- 负责注册与分发系统命令（MQTT/TCP 入口均可复用）
- 自身提供默认命令注册（register_default），通过 bind 注入依赖
"""

from typing import Callable, Dict, Any
import os
from domain.enums.commands import VisionCoreCommands
from domain.models.mqtt import MQTTResponse
from services.comm.handlers.context import CommandContext
from services.comm.handlers import config as h_config
from services.comm.handlers import system as h_system
from services.comm.handlers import camera as h_camera
from services.comm.handlers import detection as h_detection
from services.comm.handlers import sftp as h_sftp
from services.comm.handlers import tcp as h_tcp


class CommandRouter:
    def __init__(self):
        self._handlers: Dict[str, Callable[[MQTTResponse], MQTTResponse]] = {}
        self._ctx = CommandContext(
            config={}, camera=None, detector=None, sftp=None, monitor=None, logger=None,
            project_root=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        )

    def register(self, command: str, handler: Callable[[MQTTResponse], MQTTResponse]):
        key = self._normalize_command(command)
        if not key:
            raise ValueError("Command name must be non-empty")
        self._handlers[key] = handler

    def route(self, req: MQTTResponse) -> MQTTResponse:
        normalized = self._normalize_command(req.command)
        handler = self._handlers.get(normalized)
        if not handler:
            raise ValueError(f"Unknown command: {req.command}")
        return handler(req)

    # 由外部注入依赖；可多次调用，按需更新
    def bind(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self._ctx, k):
                setattr(self._ctx, k, v)

    # 注册默认命令集合（一次性）
    def register_default(self):
        # 系统/配置
        self.register(VisionCoreCommands.GET_CONFIG.value, lambda req: h_config.handle_get_config(req, self._ctx))
        self.register(VisionCoreCommands.SAVE_CONFIG.value, lambda req: h_config.handle_save_config(req, self._ctx))
        self.register(VisionCoreCommands.GET_SYSTEM_STATUS.value, lambda req: h_system.handle_get_system_status(req, self._ctx))
        self.register(VisionCoreCommands.RESTART.value, lambda req: h_system.handle_restart(req, self._ctx))
        # 图像/标定/模型/SFTP
        self.register(VisionCoreCommands.GET_IMAGE.value, lambda req: h_camera.handle_get_image(req, self._ctx))
        self.register(VisionCoreCommands.GET_CALIBRAT_IMAGE.value, lambda req: h_camera.handle_get_calibrat_image(req, self._ctx))
        self.register(VisionCoreCommands.MODEL_TEST.value, lambda req: h_detection.handle_model_test(req, self._ctx))
        self.register(VisionCoreCommands.SFTP_TEST.value, lambda req: h_sftp.handle_sftp_test(req, self._ctx))
        # TCP 专用命令（兼容已有协议）
        self.register("catch", lambda req: h_tcp.handle_catch(req, self._ctx))

    # 处理逻辑已全部下沉至 services/comm/handlers/*

    @staticmethod
    def _normalize_command(command: Any) -> str:
        if command is None:
            return ""
        try:
            return str(command).strip().upper()
        except Exception:
            return ""
