#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用装配（bootstrap）
说明：加载配置，初始化各组件（通信/相机/检测/SFTP），并启动健康监控（无限重试）。
"""

from dataclasses import dataclass
import os
import yaml
import logging

from services.system.log_manager import LogManager
from services.system.initializer import SystemInitializer


def _load_config() -> dict:
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir))
    cfg_path = os.path.join(root, "configs", "config.yaml")
    if not os.path.isfile(cfg_path):
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _init_logger(cfg: dict) -> logging.Logger:
    log_cfg = (cfg.get("logging") or {})
    enable = bool(log_cfg.get("enable", True))
    level_str = str(log_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_str, logging.INFO)
    console = bool((log_cfg.get("console") or {}).get("enable", True))
    file_output = bool((log_cfg.get("file") or {}).get("enable", True))
    log_dir = str((log_cfg.get("file") or {}).get("path", "logs"))
    backup = int((log_cfg.get("file") or {}).get("backup_count", 30))

    if not enable:
        lg = logging.getLogger("VisionCorePro")
        lg.addHandler(logging.NullHandler())
        return lg

    lm = LogManager(log_dir=log_dir, app_name="VisionCorePro",
                    level=level, console_output=console,
                    file_output=file_output, backup_count=backup)
    return lm.get_logger()


@dataclass
class Application:
    config: dict
    initializer: SystemInitializer

    def run(self):
        print("VisionCorePro starting...")
        self.initializer.start()
        print("Services started. Monitor is running. Press Ctrl+C to stop.")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
            self.initializer.stop()


def build_app() -> Application:
    config = _load_config()
    logger = _init_logger(config)
    init = SystemInitializer(config=config, logger=logger)
    logger.info("Application built. Configuration loaded.")
    return Application(config=config, initializer=init)
