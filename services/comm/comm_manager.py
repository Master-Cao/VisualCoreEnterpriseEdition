#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional
import time

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
        
        # 时间戳追踪（用于分析catch命令间隔）
        self._last_catch_time = None
        self._catch_count = 0

    def start(self):
        self._start_mqtt()
        self._start_tcp()

    def stop(self):
        """停止通信服务，释放资源"""
        try:
            # 停止TCP服务器
            if self._tcp:
                try:
                    if self._logger:
                        self._logger.info("停止TCP服务器...")
                    self._tcp.stop()
                    if self._logger:
                        self._logger.info("TCP服务器已停止")
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"停止TCP服务器失败: {e}")
        finally:
            # 断开MQTT连接
            try:
                if self._mqtt:
                    if self._logger:
                        self._logger.info("断开MQTT连接...")
                    self._mqtt.disconnect()
                    if self._logger:
                        self._logger.info("MQTT已断开")
            except Exception as e:
                if self._logger:
                    self._logger.error(f"断开MQTT失败: {e}")

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
        """重启MQTT客户端（静默重试，由监控器调用）"""
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
            # verbose=False: 监控器后台重试时静默
            ok = self._mqtt.connect(verbose=False)
            return ok
        except Exception as e:
            # 监控器重启时不输出错误日志
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
        """启动MQTT客户端（初始启动，显示详细日志）"""
        mqtt_cfg = (self._config.get("mqtt") or {})
        if not bool(mqtt_cfg.get("enable", False)):
            return
        self._mqtt = MqttClient(mqtt_cfg, logger=self._logger)
        self._mqtt.set_general_callback(self._make_mqtt_router_cb())
        # verbose=True: 初始启动时显示详细错误信息
        ok = self._mqtt.connect(verbose=True)
        if not ok and self._logger:
            self._logger.error("MQTT初始连接失败")

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
                if not isinstance(msg, dict):
                    raise TypeError(f"Unexpected MQTT message type: {type(msg)}")

                payload = msg.get("payload")
                command = ""
                component = "system"
                message = ""
                data = {}

                if isinstance(payload, dict):
                    command = str(payload.get("command", ""))
                    component = str(payload.get("component", component))
                    message = str(payload.get("message", message))
                    raw_data = payload.get("data")
                    if isinstance(raw_data, dict):
                        data = raw_data
                    elif raw_data is not None:
                        data = {"data": raw_data}
                elif payload is not None:
                    command = str(payload)

                command = command.strip()
                if not command:
                    return

                req = MQTTResponse(
                    command=command,
                    component=component,
                    messageType=MessageType.INFO,
                    message=message,
                    data=data,
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
                from datetime import datetime
                
                # ===== 时间戳记录（用于分析命令间隔）=====
                receive_time = time.time()
                
                command = line.strip()
                data: Dict[str, Any] = {"client_id": client_id}
                
                # 尝试解析JSON格式的命令
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        command = str(obj.get("command", command))
                        if isinstance(obj.get("data"), dict):
                            data.update(obj.get("data"))
                except Exception:
                    pass
                
                # ===== 特别记录catch命令的时间戳 =====
                tcp_interval_ms = 0.0  # 默认值
                if command.lower() == "catch":
                    self._catch_count += 1
                    
                    # 转换时间戳为可读格式
                    readable_time = datetime.fromtimestamp(receive_time).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    
                    if self._last_catch_time is None:
                        # 第一次catch命令
                        if self._logger:
                            self._logger.info(f"[CATCH #{self._catch_count:04d}] 时间={readable_time} | 时间戳={receive_time:.6f} | 客户端={client_id}")
                    else:
                        # 计算与上一次的时间间隔
                        tcp_interval_ms = (receive_time - self._last_catch_time) * 1000.0
                        if self._logger:
                            self._logger.info(f"[CATCH #{self._catch_count:04d}] 时间={readable_time} | 时间戳={receive_time:.6f} | 间隔={tcp_interval_ms:.1f}ms | 客户端={client_id}")
                    
                    self._last_catch_time = receive_time
                    
                    # ===== 将间隔时间传递给处理器 =====
                    data['tcp_interval_ms'] = tcp_interval_ms
                
                req = MQTTResponse(
                    command=command,
                    component="tcp",
                    messageType=MessageType.INFO,
                    message="",
                    data=data,
                )
                result = self._router.route(req)
                
                # 发送结果到MQTT（如果MQTT已启用）
                if isinstance(result, MQTTResponse) and self._mqtt is not None:
                    try:
                        pub_map = (self._config.get("mqtt") or {}).get("topics", {}).get("publish", {})
                        topic = pub_map.get("message")
                        if topic:
                            payload_out = json.dumps(result.to_dict(), ensure_ascii=False)
                            self._mqtt.publish(topic, payload_out)
                    except Exception as e:
                        if self._logger:
                            self._logger.error(f"发送TCP结果到MQTT失败: {e}")
                
                # TCP响应处理（返回给TCP客户端）
                if isinstance(result, MQTTResponse):
                    # catch命令返回特殊格式的字符串
                    if result.command == "catch" or command.lower() == "catch":
                        resp = (result.data or {}).get("response")
                        return str(resp) if isinstance(resp, str) else None
                    # 其他命令可以返回JSON格式
                    elif result.data:
                        return json.dumps(result.to_dict(), ensure_ascii=False)
                
                return None
            except Exception as e:
                if self._logger:
                    self._logger.error(f"TCP route error: {e}")
                return None
        return _on_message
