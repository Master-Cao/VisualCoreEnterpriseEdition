#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
from typing import Callable, Dict, Optional, Any


class SystemMonitor:
    def __init__(self, logger: Optional[Any] = None, check_interval: int = 30, retry_delay: int = 5, failure_threshold: int = 1):
        self._logger = logger
        self._check_interval = max(1, int(check_interval))
        self._retry_delay = max(1, int(retry_delay))
        self._failure_threshold = max(1, int(failure_threshold))
        self._components: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def register(self, name: str, check_func: Callable[[], bool], restart_func: Callable[[], bool]):
        self._components[name] = {
            "check": check_func,
            "restart": restart_func,
            "fails": 0,
        }
        if self._logger:
            self._logger.info(f"监控注册: {name}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        if self._logger:
            self._logger.info("系统监控已启动")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=1.0)
            except Exception:
                pass
        if self._logger:
            self._logger.info("系统监控已停止")

    # internal
    def _loop(self):
        while self._running:
            try:
                for name, meta in self._components.items():
                    ok = False
                    try:
                        ok = bool(meta["check"]())
                    except Exception:
                        ok = False
                    if ok:
                        if meta["fails"] > 0 and self._logger:
                            self._logger.info(f"组件恢复: {name}")
                        meta["fails"] = 0
                        continue
                    meta["fails"] += 1
                    if self._logger:
                        self._logger.warning(f"组件异常: {name} fails={meta['fails']}")
                    if meta["fails"] >= self._failure_threshold:
                        # 无限重试重启
                        while self._running:
                            try:
                                ok_restart = bool(meta["restart"]())
                            except Exception:
                                ok_restart = False
                            if ok_restart:
                                meta["fails"] = 0
                                if self._logger:
                                    self._logger.info(f"组件已重启: {name}")
                                break
                            if self._logger:
                                self._logger.error(f"组件重启失败，{self._retry_delay}s后重试: {name}")
                            time.sleep(self._retry_delay)
                time.sleep(self._check_interval)
            except Exception:
                # 不让监控退出
                time.sleep(self._retry_delay)

