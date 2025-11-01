#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional, Any
import os
import posixpath
import socket

import paramiko  # type: ignore


class SftpClient:
    def __init__(self, config: dict, logger: Optional[Any] = None):
        self._logger = logger
        self._cfg = (config or {})
        self._host = self._cfg.get("host", "127.0.0.1")
        self._port = int(self._cfg.get("port", 22))
        self._username = self._cfg.get("username", "")
        self._password = self._cfg.get("password", "")
        self._remote_root = self._cfg.get("remote_path", "/")
        self._timeout = int(self._cfg.get("connection_timeout", 15))

        self._transport: Optional[paramiko.Transport] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    def connect(self) -> bool:
        try:
            if self._logger:
                self._logger.info(f"SFTP 连接 {self._host}:{self._port} ...")
            self._transport = paramiko.Transport((self._host, self._port))
            self._transport.banner_timeout = self._timeout
            self._transport.connect(username=self._username, password=self._password)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            if self._logger:
                self._logger.info("SFTP 已连接")
            return True
        except (paramiko.SSHException, socket.error) as e:
            if self._logger:
                self._logger.error(f"SFTP 连接失败: {e}")
            self.disconnect()
            return False

    def disconnect(self):
        try:
            if self._sftp:
                self._sftp.close()
        except Exception:
            pass
        finally:
            self._sftp = None
        try:
            if self._transport:
                self._transport.close()
        except Exception:
            pass
        finally:
            self._transport = None
        if self._logger:
            self._logger.info("SFTP 已断开")

    def _ensure_connected(self):
        if self._sftp is None:
            ok = self.connect()
            if not ok:
                raise RuntimeError("SFTP 未连接")

    @staticmethod
    def _to_posix_path(path: str) -> str:
        # 统一 remote 路径为 posix 分隔
        return path.replace("\\", "/")

    def _ensure_remote_dir(self, remote_path: str):
        self._ensure_connected()
        assert self._sftp is not None
        # 逐级创建目录
        remote_path = self._to_posix_path(remote_path)
        dirs = []
        p = remote_path
        while True:
            p, tail = posixpath.split(p)
            if tail:
                dirs.append(tail)
            else:
                if p:
                    dirs.append(p)
                break
        dirs = list(reversed(dirs))
        cur = "/" if remote_path.startswith("/") else ""
        for i, d in enumerate(dirs[:-1]):  # 不包含文件名部分
            cur = posixpath.join(cur, d) if cur else d
            try:
                self._sftp.stat(cur)
            except IOError:
                try:
                    self._sftp.mkdir(cur)
                    if self._logger:
                        self._logger.info(f"SFTP 创建目录: {cur}")
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"SFTP 创建目录失败: {cur} err={e}")
                    raise

    def upload_file(self, local_path: str, remote_rel_path: str) -> bool:
        self._ensure_connected()
        assert self._sftp is not None
        rp = self._to_posix_path(posixpath.join(self._remote_root, remote_rel_path))
        self._ensure_remote_dir(rp)
        try:
            self._sftp.put(local_path, rp)
            if self._logger:
                self._logger.info(f"SFTP 上传成功: {local_path} -> {rp}")
            return True
        except Exception as e:
            if self._logger:
                self._logger.error(f"SFTP 上传失败: {local_path} -> {rp} err={e}")
            return False

    def upload_bytes(self, data: bytes, remote_rel_path: str) -> bool:
        self._ensure_connected()
        assert self._sftp is not None
        rp = self._to_posix_path(posixpath.join(self._remote_root, remote_rel_path))
        self._ensure_remote_dir(rp)
        try:
            with self._sftp.file(rp, 'wb') as f:
                f.write(data)
            if self._logger:
                self._logger.info(f"SFTP 写入成功: {rp} ({len(data)} bytes)")
            return True
        except Exception as e:
            if self._logger:
                self._logger.error(f"SFTP 写入失败: {rp} err={e}")
            return False

    def list_dir(self, remote_rel_dir: str) -> list:
        self._ensure_connected()
        assert self._sftp is not None
        rd = self._to_posix_path(posixpath.join(self._remote_root, remote_rel_dir))
        try:
            return self._sftp.listdir(rd)
        except Exception as e:
            if self._logger:
                self._logger.error(f"SFTP 列表失败: {rd} err={e}")
            return []

    def test(self) -> bool:
        ok = self.connect()
        if not ok:
            return False
        try:
            # 简单列根目录
            self.list_dir(".")
            return True
        finally:
            self.disconnect()
