#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CommandRouter（占位骨架）
- 负责注册与分发系统命令（MQTT/TCP 入口均可复用）
- 后续将注入具体处理器（配置/图像/标定/模型/系统）
"""

from typing import Callable, Dict, Any


class CommandRouter:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register(self, command: str, handler: Callable[[Dict[str, Any]], Any]):
        self._handlers[command] = handler

    def route(self, command: str, payload: Dict[str, Any]) -> Any:
        handler = self._handlers.get(command)
        if not handler:
            raise ValueError(f"Unknown command: {command}")
        return handler(payload)
