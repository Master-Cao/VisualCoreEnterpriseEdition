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
        self._was_connected = False  # 标记是否曾经连接过，用于检测断开

    def connect(self, verbose: bool = True) -> bool:
        """
        连接到SFTP服务器
        
        Args:
            verbose: 是否输出详细日志（认证失败等错误）
        
        Returns:
            是否连接成功
        """
        try:
            if self._logger and verbose:
                self._logger.debug(f"SFTP 尝试连接 {self._host}:{self._port} (user={self._username})")
            
            self._transport = paramiko.Transport((self._host, self._port))
            self._transport.banner_timeout = self._timeout
            self._transport.connect(username=self._username, password=self._password)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            
            # 标记已连接
            self._was_connected = True
            
            if self._logger and verbose:
                self._logger.info(f"SFTP 已连接 {self._host}:{self._port}")
            return True
            
        except paramiko.AuthenticationException as e:
            # 认证失败（用户名/密码错误）- 通常不应该频繁重试
            if self._logger and verbose:
                self._logger.error(f"SFTP 认证失败: {self._host}:{self._port} (user={self._username}) | 请检查用户名和密码")
            self.disconnect()
            return False
            
        except socket.timeout:
            # 连接超时
            if self._logger and verbose:
                self._logger.warning(f"SFTP 连接超时: {self._host}:{self._port} | 超时={self._timeout}s")
            self.disconnect()
            return False
            
        except socket.error as e:
            # 网络错误（如无法连接到服务器）
            if self._logger and verbose:
                self._logger.debug(f"SFTP 网络错误: {self._host}:{self._port} | {e}")
            self.disconnect()
            return False
            
        except paramiko.SSHException as e:
            # 其他SSH相关错误
            if self._logger and verbose:
                self._logger.warning(f"SFTP SSH错误: {self._host}:{self._port} | {e}")
            self.disconnect()
            return False
            
        except Exception as e:
            # 未知错误
            if self._logger and verbose:
                self._logger.error(f"SFTP 连接异常: {self._host}:{self._port} | {type(e).__name__}: {e}")
            self.disconnect()
            return False

    def disconnect(self, verbose: bool = False):
        """
        断开SFTP连接
        
        Args:
            verbose: 是否输出断开日志
        """
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
        
        # 主动断开时重置标志
        self._was_connected = False
        
        if self._logger and verbose:
            self._logger.debug("SFTP 已断开")

    def _ensure_connected(self):
        """确保已连接（按需连接，静默模式）"""
        if self._sftp is None:
            ok = self.connect(verbose=False)
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

    def test(self, verbose: bool = True) -> bool:
        """
        测试SFTP连接（会重新建立连接）
        
        Args:
            verbose: 是否输出详细日志
            
        Returns:
            连接是否成功
        """
        ok = self.connect(verbose=verbose)
        if not ok:
            return False
        try:
            # 简单列根目录
            self.list_dir(".")
            return True
        finally:
            self.disconnect(verbose=verbose)
    
    @property
    def healthy(self) -> bool:
        """检查SFTP连接是否健康（不重新连接）"""
        try:
            # 检查transport和sftp对象是否存在
            if self._transport is None or self._sftp is None:
                return False
            
            # 检查transport是否活跃
            if not self._transport.is_active():
                # Transport不活跃，清理连接
                self._cleanup_dead_connection()
                return False
            
            # 检查底层socket是否还活跃
            sock = self._transport.sock
            if sock is None:
                self._cleanup_dead_connection()
                return False
            
            # 尝试发送一个真实的SFTP操作来验证连接
            # stat操作会真正与服务器通信，可以更快检测到断开
            try:
                # 设置较短的超时时间（3秒）用于健康检查
                old_timeout = sock.gettimeout()
                try:
                    sock.settimeout(3.0)
                    # 尝试stat根目录，这是一个轻量但真实的操作
                    self._sftp.stat('.')
                    return True
                finally:
                    # 恢复原超时设置
                    if old_timeout is not None:
                        sock.settimeout(old_timeout)
            except (EOFError, OSError, socket.error, socket.timeout):
                # 连接已断开或超时，清理连接
                self._cleanup_dead_connection()
                return False
            except Exception:
                # 其他异常也认为不健康，清理连接
                self._cleanup_dead_connection()
                return False
                
        except Exception:
            # 检查过程出现异常，清理连接
            self._cleanup_dead_connection()
            return False
    
    def _cleanup_dead_connection(self):
        """清理已经断开的连接对象"""
        try:
            # 如果之前已连接，现在检测到断开，记录一次日志
            if self._was_connected and self._logger:
                self._logger.warning(f"SFTP 连接已断开: {self._host}:{self._port} | 将自动重连")
                self._was_connected = False
            
            if self._sftp:
                try:
                    self._sftp.close()
                except Exception:
                    pass
                self._sftp = None
            
            if self._transport:
                try:
                    self._transport.close()
                except Exception:
                    pass
                self._transport = None
        except Exception:
            pass
