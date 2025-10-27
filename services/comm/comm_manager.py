#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional

from .mqtt_client import MqttClient
from .tcp_server import TcpServer
from .command_router import CommandRouter


class CommManager:
    def __init__(self, config: Dict[str, Any], router: CommandRouter, logger: Optional[Any] = None):
        self._logger = logger
        self._router = router
        self._config = config or {}
        self._mqtt: Optional[MqttClient] = None
        self._tcp: Optional[TcpServer] = None

    def start(self):
        self._start_mqtt()
        self._start_tcp()

    def stop(self):
        try:
            if self._tcp:
                self._tcp.stop()
        finally:
            try:
                if self._mqtt:
                    self._mqtt.disconnect()
            except Exception:
                pass

    # --- internal ---
    def _start_mqtt(self):
        mqtt_cfg = (self._config.get("mqtt") or {})
        if not bool(mqtt_cfg.get("enable", False)):
            return
        self._mqtt = MqttClient(mqtt_cfg, logger=self._logger)

        # 将通用回调接入路由：payload 预期为 {"command": str, "data": any}
        def _on_message(msg):
            try:
                payload = getattr(msg, "payload", None)
                if isinstance(payload, dict):
                    command = str(payload.get("command", ""))
                    data = payload.get("data")
                    self._router.route(command, data if isinstance(data, dict) else {"data": data})
            except Exception as e:
                if self._logger:
                    self._logger.error(f"MQTT route error: {e}")
                else:
                    print(f"MQTT route error: {e}")

        try:
            self._mqtt.set_general_callback(_on_message)
        except Exception:
            pass

        # 启动连接（同步）
        ok = self._mqtt.connect()
        if not ok and self._logger:
            self._logger.error("MQTT connect failed")

    def _start_tcp(self):
        tcp_cfg = (self._config.get("DetectionServer") or {})
        if not bool(tcp_cfg.get("enable", False)):
            return
        self._tcp = TcpServer(tcp_cfg, logger=self._logger)

        def _on_message(client_id: str, line: str) -> Optional[str]:
            try:
                # 简单协议：直接将行作为 command 或 JSON 载荷
                import json
                command = line
                data: Dict[str, Any] = {}
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        command = str(obj.get("command", command))
                        data = obj.get("data") or {}
                except Exception:
                    pass
                result = self._router.route(command, data)
                # 仅当业务返回字符串时透传给客户端
                return result if isinstance(result, str) else None
            except Exception as e:
                if self._logger:
                    self._logger.error(f"TCP route error: {e}")
                return None

        self._tcp.set_message_callback(_on_message)
        self._tcp.start()
