#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MQTT 客户端（全新实现，不依赖旧版）
- 同步 connect()/disconnect()
- 背景网络循环（loop_start/loop_stop 内部管理）
- 通用回调与按主题回调
- 基于 paho-mqtt 2.x
"""

from typing import Any, Dict, Callable, Optional, List
import time
import threading

try:
    import paho.mqtt.client as mqtt
except Exception as e:
    mqtt = None  # 运行时若缺失，将在初始化时报错


class MqttClient:
    def __init__(self, config: Dict[str, Any], logger: Optional[Any] = None):
        if mqtt is None:
            raise ImportError("paho-mqtt 未安装，无法启用 MQTT")
        self._logger = logger
        self._cfg = config or {}
        self._conn = self._cfg.get("connection", {})
        self._qos = self._cfg.get("qos", {})
        self._topics = self._cfg.get("topics", {})
        self._message_cfg = self._cfg.get("message", {})

        client_id = self._conn.get("client_id", f"visioncorepro_{int(time.time()*1000)%100000}")
        self.client = mqtt.Client(client_id=client_id)

        user = self._conn.get("username")
        pwd = self._conn.get("password")
        if user:
            self.client.username_pw_set(user, pwd)
        if self._conn.get("use_ssl", False):
            self.client.tls_set()

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self._is_connected = False
        self._connect_ev = threading.Event()
        self._general_cb: Optional[Callable[[Any], None]] = None
        self._topic_cbs: Dict[str, List[Callable[[Any], None]]] = {}

    # public API
    def connect(self, timeout: float = 10.0) -> bool:
        host = self._conn.get("broker_host", "127.0.0.1")
        port = int(self._conn.get("broker_port", 1883))
        keepalive = int(self._conn.get("keepalive", 60))
        try:
            self._connect_ev.clear()
            self.client.connect(host, port, keepalive)
            self.client.loop_start()
            ok = self._connect_ev.wait(timeout=timeout)
            if not ok:
                if self._logger:
                    self._logger.error("MQTT 连接超时")
                return False
            return self._is_connected
        except Exception as e:
            if self._logger:
                self._logger.error(f"MQTT 连接失败: {e}")
            return False

    def disconnect(self):
        try:
            self.client.loop_stop()
        finally:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self._is_connected = False

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> bool:
        try:
            r = self.client.publish(topic, payload=payload, qos=qos, retain=retain)
            return r.rc == mqtt.MQTT_ERR_SUCCESS if hasattr(r, 'rc') else True
        except Exception:
            return False

    def subscribe(self, topic: str, callback: Optional[Callable] = None, qos: int = 0) -> bool:
        try:
            r = self.client.subscribe(topic, qos=qos)
            ok = (getattr(r, 'rc', mqtt.MQTT_ERR_SUCCESS) == mqtt.MQTT_ERR_SUCCESS) if r is not None else True
            if self._logger:
                if ok:
                    self._logger.info(f"MQTT 订阅成功: {topic} (qos={qos})")
                else:
                    self._logger.error(f"MQTT 订阅失败: {topic} rc={getattr(r, 'rc', None)}")
            if ok and callback:
                self._topic_cbs.setdefault(topic, []).append(callback)
            return ok
        except Exception as e:
            if self._logger:
                self._logger.error(f"MQTT 订阅异常: {topic} err={e}")
            return False

    def set_general_callback(self, callback: Callable[[Any], None]):
        self._general_cb = callback

    @property
    def healthy(self) -> bool:
        return self._is_connected

    # callbacks
    def _on_connect(self, _client, _userdata, _flags, rc):
        self._is_connected = (rc == 0)
        self._connect_ev.set()
        if self._logger:
            if self._is_connected:
                self._logger.info("MQTT 已连接")
            else:
                self._logger.error(f"MQTT 连接失败，rc={rc}")
        # 自动订阅默认订阅主题（显式订阅 system_command）
        sub_map = (self._topics.get("subscribe") or {})
        topic = sub_map.get("system_command")
        if topic:
            try:
                r = self.client.subscribe(str(topic), qos=int(self._qos.get("subscribe", 0)))
                ok = (getattr(r, 'rc', mqtt.MQTT_ERR_SUCCESS) == mqtt.MQTT_ERR_SUCCESS) if r is not None else True
                if self._logger:
                    if ok:
                        self._logger.info(f"MQTT 订阅成功: {topic} (qos={int(self._qos.get('subscribe', 0))})")
                    else:
                        self._logger.error(f"MQTT 订阅失败: {topic} rc={getattr(r, 'rc', None)}")
            except Exception as e:
                if self._logger:
                    self._logger.error(f"MQTT 订阅异常: {topic} err={e}")

    def _on_disconnect(self, *_args):
        self._is_connected = False
        if self._logger:
            self._logger.warning("MQTT 已断开")

    def _on_message(self, _client, _userdata, msg):
        try:
            m = {
                "topic": msg.topic,
                "payload": self._safe_decode(msg.payload),
                "qos": msg.qos,
                "retain": msg.retain,
            }
            # 主题回调
            cbs = self._topic_cbs.get(msg.topic) or []
            for cb in cbs:
                try:
                    cb(m)
                except Exception:
                    pass
            # 通用回调
            if self._general_cb:
                self._general_cb(m)
        except Exception:
            pass

    @staticmethod
    def _safe_decode(payload: Any) -> Any:
        try:
            if isinstance(payload, (bytes, bytearray)):
                s = payload.decode("utf-8", errors="ignore")
                # 尝试解析 JSON
                import json
                try:
                    return json.loads(s)
                except Exception:
                    return s
            return payload
        except Exception:
            return payload
