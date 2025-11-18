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
        """运行应用程序，包含完整的启动和关闭逻辑"""
        import signal
        import time
        import sys
        import threading
        
        # 控制主循环的标志和事件
        self._running = True
        self._stop_event = threading.Event()
        
        # 注册信号处理器，确保优雅关闭
        def signal_handler(signum, frame):
            print(f"\n收到停止信号 (signal={signum})...")
            self._running = False  # 通知主循环退出
            self._stop_event.set()  # 中断主循环的等待
            # 同时中断 initializer 中的启动重试循环
            self.initializer.request_stop()
            # 注意：不在信号处理器中调用 shutdown，而是让主循环自然退出后调用
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            print("VisionCorePro starting...")
            self.initializer.start()
            print("✓ 服务已启动，监控器正在运行")
            print("按 Ctrl+C 停止系统")
            
            # 主循环（可被快速中断）
            while self._running:
                # 使用 Event.wait 替代 time.sleep，可以被信号立即中断
                if self._stop_event.wait(timeout=1.0):
                    break  # 收到停止信号，退出循环
            
            # 正常退出流程
            self._shutdown()
                
        except KeyboardInterrupt:
            # Ctrl+C 会触发此异常
            print("\n检测到键盘中断...")
            self._shutdown()
        except Exception as e:
            print(f"\n应用程序异常: {e}")
            self._shutdown()
            raise
        finally:
            # 确保程序退出
            print("程序即将退出...")
            sys.exit(0)
    
    def _shutdown(self):
        """优雅关闭应用程序，释放所有资源"""
        try:
            print("正在停止系统...")
            self.initializer.stop()
            print("✓ 系统已完全停止")
        except Exception as e:
            print(f"关闭过程中发生异常: {e}")
            raise


def build_app() -> Application:
    config = _load_config()
    logger = _init_logger(config)
    init = SystemInitializer(config=config, logger=logger)
    logger.info("Application built. Configuration loaded.")
    return Application(config=config, initializer=init)
