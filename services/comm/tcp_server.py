#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TCP 服务器（全新实现）
- 多线程：accept 线程 + 每客户端线程
- 文本协议：按行分割，回调返回字符串时回写
"""

from typing import Any, Dict, Optional, Callable
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class _ClientInfo:
    socket: socket.socket
    address: tuple
    connect_time: datetime
    last_heartbeat: datetime
    is_active: bool = True


class TcpServer:
    def __init__(self, config: Dict[str, Any], logger: Optional[Any] = None):
        self._cfg = config or {}
        self._logger = logger
        self._host = self._cfg.get("host", "0.0.0.0")
        self._port = int(self._cfg.get("port", 8888))
        self._max_conn = int(self._cfg.get("max_connections", 10))
        self._buf_size = int(self._cfg.get("buffer_size", 4096))
        self._heartbeat_interval = int(self._cfg.get("heartbeat_interval", 30))
        self._conn_timeout = int(self._cfg.get("connection_timeout", 300))

        self._server_sock: Optional[socket.socket] = None
        self._is_running = False
        self._clients: Dict[str, _ClientInfo] = {}
        self._lock = threading.RLock()

        self._accept_th: Optional[threading.Thread] = None
        self._hb_th: Optional[threading.Thread] = None

        self._on_message: Optional[Callable[[str, str], Optional[str]]] = None
        self._on_disconnect: Optional[Callable[[str, str], None]] = None

    def set_message_callback(self, callback: Callable[[str, str], Optional[str]]):
        self._on_message = callback

    def set_disconnect_callback(self, callback: Callable[[str, str], None]):
        self._on_disconnect = callback

    def start(self) -> bool:
        if self._is_running:
            return True
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self._host, self._port))
            self._server_sock.listen(self._max_conn)
            self._server_sock.settimeout(1.0)
            self._is_running = True

            self._accept_th = threading.Thread(target=self._accept_loop, daemon=True)
            self._hb_th = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._accept_th.start()
            self._hb_th.start()
            if self._logger:
                self._logger.info(f"TCP 服务器启动: {self._host}:{self._port}")
            return True
        except Exception as e:
            if self._logger:
                self._logger.error(f"TCP 启动失败: {e}")
            self.stop()
            return False

    def stop(self):
        """停止TCP服务器，释放所有资源"""
        if not self._is_running:
            return
        
        if self._logger:
            self._logger.info(f"正在停止TCP服务器 | 活跃连接={len(self._clients)}")
        
        # 设置停止标志
        self._is_running = False
        
        # 1. 关闭所有客户端连接
        with self._lock:
            for cid, info in list(self._clients.items()):
                try:
                    info.socket.close()
                except Exception:
                    pass
            self._clients.clear()
        
        # 2. 关闭服务器socket
        try:
            if self._server_sock:
                try:
                    self._server_sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._server_sock.close()
        finally:
            self._server_sock = None
        
        # 3. 等待accept线程和心跳线程退出（daemon线程会自动结束，但我们尝试等待）
        for thread_name, thread in [("accept", self._accept_th), ("heartbeat", self._hb_th)]:
            if thread and thread.is_alive():
                try:
                    thread.join(timeout=1.0)
                    if thread.is_alive():
                        if self._logger:
                            self._logger.debug(f"TCP {thread_name}线程未能及时退出（daemon线程会随主线程结束）")
                except Exception:
                    pass
        
        if self._logger:
            self._logger.info("✓ TCP服务器已完全停止")

    @property
    def healthy(self) -> bool:
        return self._is_running and self._server_sock is not None

    # internal
    def _accept_loop(self):
        while self._is_running and self._server_sock is not None:
            try:
                try:
                    client_sock, addr = self._server_sock.accept()
                except socket.timeout:
                    continue
                
                # 设置 TCP_NODELAY，禁用 Nagle 算法，立即发送数据（避免延迟）
                try:
                    client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    if self._logger:
                        self._logger.debug(f"为客户端 {addr} 设置 TCP_NODELAY")
                except Exception as e:
                    if self._logger:
                        self._logger.warning(f"设置 TCP_NODELAY 失败: {e}")
                
                cid = f"{addr[0]}:{addr[1]}:{int(time.time())}"
                info = _ClientInfo(
                    socket=client_sock,
                    address=addr,
                    connect_time=datetime.now(),
                    last_heartbeat=datetime.now(),
                )
                with self._lock:
                    self._clients[cid] = info
                th = threading.Thread(target=self._client_loop, args=(cid,), daemon=True)
                th.start()
            except Exception:
                continue

    def _client_loop(self, cid: str):
        info = self._clients.get(cid)
        if not info:
            return
        sock = info.socket
        sock.settimeout(1.0)
        buffer = ""
        try:
            while self._is_running and info.is_active:
                try:
                    data = sock.recv(self._buf_size)
                    if not data:
                        break
                    buffer += data.decode("utf-8", errors="ignore")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        info.last_heartbeat = datetime.now()
                        if self._on_message:
                            try:
                                resp = self._on_message(cid, line)
                                if isinstance(resp, str) and resp:
                                    self._send(sock, resp)
                            except Exception:
                                pass
                except socket.timeout:
                    continue
        except Exception:
            pass
        finally:
            self._disconnect(cid, "连接断开")

    def _send(self, sock: socket.socket, message: str):
        try:
            if not message.endswith("\r\n"):
                message += "\r\n"
            sock.sendall(message.encode("utf-8"))
        except Exception:
            pass

    def _disconnect(self, cid: str, reason: str):
        with self._lock:
            info = self._clients.pop(cid, None)
        if info:
            try:
                info.socket.close()
            except Exception:
                pass
            info.is_active = False
            if self._on_disconnect:
                try:
                    self._on_disconnect(cid, reason)
                except Exception:
                    pass

    def _heartbeat_loop(self):
        while self._is_running:
            try:
                now = datetime.now()
                to_close: list[str] = []
                with self._lock:
                    for cid, info in self._clients.items():
                        if not info.is_active:
                            to_close.append(cid)
                            continue
                        dt = (now - info.last_heartbeat).total_seconds()
                        if dt > self._conn_timeout:
                            to_close.append(cid)
                for cid in to_close:
                    self._disconnect(cid, "心跳超时")
                time.sleep(self._heartbeat_interval)
            except Exception:
                time.sleep(1)
