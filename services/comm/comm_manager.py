#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional

from .mqtt_client import MqttClient
from .tcp_server import TcpServer
from .command_router import CommandRouter
from domain.models.mqtt import MQTTResponse
from domain.enums.commands import MessageType


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

    # --- health ---
    @property
    def healthy(self) -> bool:
        mqtt_cfg = (self._config.get("mqtt") or {})
        tcp_cfg = (self._config.get("DetectionServer") or {})
        mqtt_enabled = bool(mqtt_cfg.get("enable", False))
        tcp_enabled = bool(tcp_cfg.get("enable", False))
        mqtt_ok = (not mqtt_enabled) or (self._mqtt is not None and self._mqtt.healthy)
        tcp_ok = (not tcp_enabled) or (self._tcp is not None and self._tcp.healthy)
        return mqtt_ok and tcp_ok

    # --- restart helpers ---
    def restart_mqtt(self) -> bool:
        mqtt_cfg = (self._config.get("mqtt") or {})
        if not bool(mqtt_cfg.get("enable", False)):
            return True
        try:
            if self._mqtt:
                try:
                    self._mqtt.disconnect()
                except Exception:
                    pass
            self._mqtt = MqttClient(mqtt_cfg, logger=self._logger)
            self._mqtt.set_general_callback(self._make_mqtt_router_cb())
            ok = self._mqtt.connect()
            return ok
        except Exception as e:
            if self._logger:
                self._logger.error(f"重启 MQTT 失败: {e}")
            return False

    def restart_tcp(self) -> bool:
        tcp_cfg = (self._config.get("DetectionServer") or {})
        if not bool(tcp_cfg.get("enable", False)):
            return True
        try:
            if self._tcp:
                try:
                    self._tcp.stop()
                except Exception:
                    pass
            self._tcp = TcpServer(tcp_cfg, logger=self._logger)
            self._tcp.set_message_callback(self._make_tcp_router_cb())
            ok = self._tcp.start()
            return ok
        except Exception as e:
            if self._logger:
                self._logger.error(f"重启 TCP 失败: {e}")
            return False

    # --- internal ---
    def _start_mqtt(self):
        mqtt_cfg = (self._config.get("mqtt") or {})
        if not bool(mqtt_cfg.get("enable", False)):
            return
        self._mqtt = MqttClient(mqtt_cfg, logger=self._logger)
        self._mqtt.set_general_callback(self._make_mqtt_router_cb())
        ok = self._mqtt.connect()
        if not ok and self._logger:
            self._logger.error("MQTT connect failed")

    def _start_tcp(self):
        tcp_cfg = (self._config.get("DetectionServer") or {})
        if not bool(tcp_cfg.get("enable", False)):
            return
        self._tcp = TcpServer(tcp_cfg, logger=self._logger)
        self._tcp.set_message_callback(self._make_tcp_router_cb())
        self._tcp.start()

    def _make_mqtt_router_cb(self):
        def _on_message(msg):
            try:
                import json
                payload = getattr(msg, "payload", None)
                if isinstance(payload, dict):
                    command = str(payload.get("command", ""))
                    data = payload.get("data")
                    req = MQTTResponse(
                        command=command,
                        component=str(payload.get("component", "system")),
                        messageType=MessageType.INFO,
                        message=str(payload.get("message", "")),
                        data=data if isinstance(data, dict) else {"data": data},
                    )
                    result = self._router.route(req)
                    # 按配置发布响应
                    if isinstance(result, MQTTResponse) and self._mqtt is not None:
                        try:
                            pub_map = (self._config.get("mqtt") or {}).get("topics", {}).get("publish", {})
                            topic = pub_map.get("message")
                            if topic:
                                payload_out = json.dumps(result.to_dict(), ensure_ascii=False)
                                self._mqtt.publish(topic, payload_out)
                        except Exception:
                            pass
            except Exception as e:
                if self._logger:
                    self._logger.error(f"MQTT route error: {e}")
        return _on_message

    def _make_tcp_router_cb(self):
        def _on_message(client_id: str, line: str):
            try:
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
                req = MQTTResponse(
                    command=command,
                    component="tcp",
                    messageType=MessageType.INFO,
                    message="",
                    data=data,
                )
                result = self._router.route(req)
                # TCP 仅在 catch 时回写字符串
                if isinstance(result, MQTTResponse) and result.command == "catch":
                    resp = (result.data or {}).get("response")
                    return str(resp) if isinstance(resp, str) else None
                return None
            except Exception as e:
                if self._logger:
                    self._logger.error(f"TCP route error: {e}")
                return None
        return _on_message
