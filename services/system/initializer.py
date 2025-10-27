#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Optional, Any

from services.comm.command_router import CommandRouter
from services.comm.comm_manager import CommManager
from services.camera.sick_camera import SickCamera
from services.detection.factory import create_detector
from services.sftp.sftp_client import SftpClient
from .monitor import SystemMonitor


class SystemInitializer:
    def __init__(self, config: dict, logger: Optional[Any] = None):
        self._cfg = config or {}
        self._logger = logger
        self.router = CommandRouter()
        self.comm: Optional[CommManager] = None
        self.camera: Optional[SickCamera] = None
        self.detector = None
        self.sftp: Optional[SftpClient] = None
        self.monitor: Optional[SystemMonitor] = None

        bm = (self._cfg.get("board_mode") or {})
        mon = (bm.get("monitoring") or {})
        self._retry_delay = int(bm.get("retry_delay", 5))
        self._check_interval = int(mon.get("check_interval", 30))
        self._failure_threshold = int(mon.get("failure_threshold", 1))

    # 装配与启动
    def start(self):
        # 通信
        self.comm = CommManager(config=self._cfg, router=self.router, logger=self._logger)
        self.comm.start()
        if self._logger:
            self._logger.info("通信服务已启动")
        # 相机
        cam_cfg = (self._cfg.get("camera") or {})
        if bool(cam_cfg.get("enable", False)):
            ip = (cam_cfg.get("connection") or {}).get("ip", "192.168.2.99")
            port = int((cam_cfg.get("connection") or {}).get("port", 2122))
            use_single = bool((cam_cfg.get("mode") or {}).get("useSingleStep", True))
            self.camera = SickCamera(ip=ip, port=port, use_single_step=use_single, logger=self._logger)
            self.camera.connect()
            if self._logger:
                self._logger.info("相机已连接")
        # 检测
        try:
            self.detector = create_detector(self._cfg, logger=self._logger)
            self.detector.load()
            if self._logger:
                self._logger.info("检测器已加载")
        except Exception as e:
            if self._logger:
                self._logger.error(f"检测器加载失败: {e}")
            self.detector = None
        # SFTP
        sftp_cfg = (self._cfg.get("sftp") or {})
        if bool(sftp_cfg.get("enable", False)):
            try:
                self.sftp = SftpClient(sftp_cfg, logger=self._logger)
                if self._logger:
                    self._logger.info("SFTP 客户端已就绪")
            except Exception as e:
                if self._logger:
                    self._logger.error(f"SFTP 初始化失败: {e}")
                self.sftp = None
        # 监控
        self._setup_monitor()

    def stop(self):
        try:
            if self.camera:
                try:
                    self.camera.disconnect()
                except Exception:
                    pass
            if self.comm:
                self.comm.stop()
        finally:
            if self._logger:
                self._logger.info("系统已停止")

    # 监控注册
    def _setup_monitor(self):
        self.monitor = SystemMonitor(
            logger=self._logger,
            check_interval=self._check_interval,
            retry_delay=self._retry_delay,
            failure_threshold=self._failure_threshold,
        )
        # 通信
        if self.comm:
            self.monitor.register(
                "comm",
                lambda: bool(self.comm.healthy),
                lambda: (self.comm.restart_mqtt() and self.comm.restart_tcp()),
            )
        # 相机
        if self.camera:
            self.monitor.register(
                "camera",
                lambda: bool(self.camera.healthy),
                self._restart_camera,
            )
        # 检测
        if self.detector:
            self.monitor.register(
                "detector",
                self._check_detector,
                self._restart_detector,
            )
        # SFTP（以测试作为健康检查）
        if self.sftp:
            self.monitor.register(
                "sftp",
                self._check_sftp,
                self._noop_restart,
            )
        self.monitor.start()

    # 重启实现
    def _restart_camera(self) -> bool:
        try:
            if self.camera:
                try:
                    self.camera.disconnect()
                except Exception:
                    pass
                return self.camera.connect()
        except Exception:
            return False
        return False

    def _check_detector(self) -> bool:
        try:
            # 简单认为加载成功即健康；如需细化，可执行一次空推理/自检
            return self.detector is not None
        except Exception:
            return False

    def _restart_detector(self) -> bool:
        try:
            self.detector = create_detector(self._cfg, logger=self._logger)
            self.detector.load()
            return True
        except Exception:
            return False

    def _check_sftp(self) -> bool:
        try:
            if self.sftp is None:
                return False
            return self.sftp.test()
        except Exception:
            return False

    @staticmethod
    def _noop_restart() -> bool:
        # SFTP 客户端为按需连接，重启意义不大，保持无限重试由 check 触发
        return True
