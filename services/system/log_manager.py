#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import datetime
from logging.handlers import TimedRotatingFileHandler
import threading


class LogManager:
    """
    系统日志管理器（单例）
    - 控制台输出（窗口打印）
    - 按日轮转文件输出
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LogManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, log_dir: str = "logs", app_name: str = "VisionCorePro",
                 level: int = logging.INFO, console_output: bool = True,
                 file_output: bool = True, backup_count: int = 30):
        if self._initialized:
            return
        self.log_dir = log_dir
        self.app_name = app_name
        self.level = level
        self.console_output = console_output
        self.file_output = file_output
        self.backup_count = backup_count
        self.loggers = {}

        if self.file_output and not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

        self._initialized = True

    def get_logger(self, name: str = None) -> logging.Logger:
        if name is None:
            name = self.app_name
        if name in self.loggers:
            return self.loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(self.level)
        logger.propagate = False

        # 清理已有处理器
        for h in logger.handlers[:]:
            logger.removeHandler(h)

        # 基础格式（保证窗口打印清晰）
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        if self.console_output:
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)

        if self.file_output:
            today = datetime.date.today().isoformat()
            log_file = os.path.join(self.log_dir, f"{self.app_name}_{today}.log")
            fh = TimedRotatingFileHandler(
                log_file, when="midnight", interval=1, backupCount=self.backup_count, encoding="utf-8"
            )
            fh.suffix = "%Y-%m-%d.log"
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        self.loggers[name] = logger
        return logger

    def set_level(self, level: int, name: str = None):
        if name and name in self.loggers:
            self.loggers[name].setLevel(level)
            return
        self.level = level
        for lg in self.loggers.values():
            lg.setLevel(level)
