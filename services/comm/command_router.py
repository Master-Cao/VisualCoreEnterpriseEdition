#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandRouter
- 负责注册与分发系统命令（MQTT/TCP 入口均可复用）
- 自身提供默认命令注册（register_default），通过 bind 注入依赖
"""

from typing import Callable, Dict, Any, Optional
from domain.enums.commands import VisionCoreCommands


class CommandRouter:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        # 运行期依赖上下文，由 initializer 绑定
        self._ctx: Dict[str, Any] = {
            "config": None,
            "camera": None,
            "detector": None,
            "sftp": None,
            "monitor": None,
            "logger": None,
        }

    def register(self, command: str, handler: Callable[[Dict[str, Any]], Any]):
        self._handlers[command] = handler

    def route(self, command: str, payload: Dict[str, Any]) -> Any:
        handler = self._handlers.get(command)
        if not handler:
            raise ValueError(f"Unknown command: {command}")
        return handler(payload)

    # 由外部注入依赖；可多次调用，按需更新
    def bind(self, **kwargs):
        self._ctx.update({k: v for k, v in kwargs.items() if k in self._ctx})

    # 注册默认命令集合（一次性）
    def register_default(self):
        # 系统/配置
        self.register(VisionCoreCommands.GET_CONFIG.value, self._h_get_config)
        self.register(VisionCoreCommands.SAVE_CONFIG.value, self._h_save_config)
        self.register(VisionCoreCommands.GET_SYSTEM_STATUS.value, self._h_get_system_status)
        self.register(VisionCoreCommands.RESTART.value, self._h_restart)
        # 图像/标定/模型/SFTP
        self.register(VisionCoreCommands.GET_IMAGE.value, self._h_get_image)
        self.register(VisionCoreCommands.GET_CALIBRAT_IMAGE.value, self._h_get_calibrat_image)
        self.register(VisionCoreCommands.COORDINATE_CALIBRATION.value, self._h_coordinate_calibration)
        self.register(VisionCoreCommands.MODEL_TEST.value, self._h_model_test)
        self.register(VisionCoreCommands.SFTP_TEST.value, self._h_sftp_test)
        # TCP 专用命令（兼容已有协议）
        self.register("catch", self._h_catch)

    # --- handlers ---
    def _h_get_config(self, _payload: Dict[str, Any]):
        return {"ok": True, "command": VisionCoreCommands.GET_CONFIG.value, "config": self._ctx.get("config")}

    def _h_save_config(self, payload: Dict[str, Any]):
        try:
            cfg = payload.get("config") if isinstance(payload, dict) else None
            if isinstance(cfg, dict):
                self._ctx["config"] = cfg
                return {"ok": True, "command": VisionCoreCommands.SAVE_CONFIG.value}
            return {"ok": False, "error": "invalid_config", "command": VisionCoreCommands.SAVE_CONFIG.value}
        except Exception as e:
            return {"ok": False, "error": str(e), "command": VisionCoreCommands.SAVE_CONFIG.value}

    def _h_get_system_status(self, _payload: Dict[str, Any]):
        mon = self._ctx.get("monitor")
        status = mon.get_system_status() if mon else {"monitoring": False}
        return {"ok": True, "command": VisionCoreCommands.GET_SYSTEM_STATUS.value, "status": status}

    def _h_restart(self, _payload: Dict[str, Any]):
        # 返回确认，由外层进程管理实际重启
        return {"ok": True, "command": VisionCoreCommands.RESTART.value, "message": "ack"}

    def _h_get_image(self, _payload: Dict[str, Any]):
        try:
            cam = self._ctx.get("camera")
            if not cam or not getattr(cam, "healthy", False):
                return {"ok": False, "error": "camera_not_ready", "command": VisionCoreCommands.GET_IMAGE.value}
            frame = cam.get_frame(convert_to_mm=True)
            ok = bool(frame)
            return {"ok": ok, "command": VisionCoreCommands.GET_IMAGE.value}
        except Exception as e:
            return {"ok": False, "error": str(e), "command": VisionCoreCommands.GET_IMAGE.value}

    def _h_get_calibrat_image(self, payload: Dict[str, Any]):
        res = self._h_get_image(payload)
        if isinstance(res, dict):
            res["command"] = VisionCoreCommands.GET_CALIBRAT_IMAGE.value
        return res

    def _h_coordinate_calibration(self, _payload: Dict[str, Any]):
        return {"ok": False, "error": "not_implemented", "command": VisionCoreCommands.COORDINATE_CALIBRATION.value}

    def _h_model_test(self, _payload: Dict[str, Any]):
        try:
            det = self._ctx.get("detector")
            ok = det is not None
            return {"ok": ok, "command": VisionCoreCommands.MODEL_TEST.value}
        except Exception as e:
            return {"ok": False, "error": str(e), "command": VisionCoreCommands.MODEL_TEST.value}

    def _h_sftp_test(self, _payload: Dict[str, Any]):
        try:
            sftp = self._ctx.get("sftp")
            ok = sftp.test() if sftp else False
            return {"ok": ok, "command": VisionCoreCommands.SFTP_TEST.value}
        except Exception as e:
            return {"ok": False, "error": str(e), "command": VisionCoreCommands.SFTP_TEST.value}

    def _h_catch(self, _payload: Dict[str, Any]) -> str:
        # 兼容 TCP 协议：返回 "count,x,y,z,angle"
        return "0,0,0,0,0"
