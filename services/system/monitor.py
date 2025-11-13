#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
from typing import Callable, Dict, Optional, Any, List


class SystemMonitor:
    def __init__(self, logger: Optional[Any] = None, check_interval: int = 30, retry_delay: int = 5, failure_threshold: int = 1):
        self._logger = logger
        self._check_interval = max(1, int(check_interval))
        self._retry_delay = max(1, int(retry_delay))
        self._failure_threshold = max(1, int(failure_threshold))
        self._components: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._threads: List[threading.Thread] = []  # 改为线程列表，每个组件一个线程
        self._stop_event = threading.Event()  # 用于可中断的等待，实现快速停止

    def register(self, name: str, check_func: Callable[[], bool], restart_func: Callable[[], bool], is_critical: bool = True):
        """
        注册监控组件（每个组件将在独立线程中监控）
        
        Args:
            name: 组件名称
            check_func: 健康检查函数
            restart_func: 重启函数
            is_critical: 是否为关键组件。关键组件会记录重试日志，非关键组件静默重试
        """
        self._components[name] = {
            "check": check_func,
            "restart": restart_func,
            "fails": 0,
            "is_critical": is_critical,
        }
        if self._logger:
            component_type = "关键组件" if is_critical else "非关键组件"
            self._logger.info(f"监控注册: {name} ({component_type})")

    def start(self):
        """启动监控器（为每个组件创建独立的监控线程）"""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()  # 清除停止信号
        
        # 为每个组件启动独立的监控线程
        for name, meta in self._components.items():
            thread = threading.Thread(
                target=self._component_loop,
                args=(name, meta),
                daemon=True,
                name=f"Monitor-{name}"
            )
            thread.start()
            self._threads.append(thread)
        
        if self._logger:
            self._logger.info(f"系统监控已启动 | 组件数={len(self._components)} | 每个组件独立监控线程")

    def stop(self):
        """停止所有监控线程，确保资源正确释放"""
        if not self._running:
            return
        
        if self._logger:
            self._logger.info(f"正在停止监控器 | 活跃线程={len([t for t in self._threads if t.is_alive()])}")
        
        # 设置停止标志，让所有线程退出循环
        self._running = False
        # 设置停止事件，中断所有正在等待的 sleep
        self._stop_event.set()
        
        # 等待所有线程结束（已使用可中断等待，线程会快速响应）
        max_wait_per_thread = 0.5  # 每个线程最多等待0.5秒（线程会立即响应停止信号）
        for thread in self._threads:
            if thread.is_alive():
                try:
                    thread_name = thread.name
                    if self._logger:
                        self._logger.debug(f"等待线程退出: {thread_name}")
                    thread.join(timeout=max_wait_per_thread)
                    
                    # 检查线程是否成功退出
                    if thread.is_alive():
                        if self._logger:
                            self._logger.warning(f"线程未能及时退出: {thread_name} | 可能仍在运行")
                    else:
                        if self._logger:
                            self._logger.debug(f"线程已退出: {thread_name}")
                except Exception as e:
                    if self._logger:
                        self._logger.error(f"等待线程退出时异常: {e}")
        
        # 清理线程列表
        alive_threads = [t for t in self._threads if t.is_alive()]
        self._threads.clear()
        
        if self._logger:
            if alive_threads:
                self._logger.warning(f"监控器已停止 | 仍有{len(alive_threads)}个线程未退出（daemon线程会随主线程结束）")
            else:
                self._logger.info("✓ 监控器已完全停止 | 所有线程已退出")

    # internal
    def _interruptible_sleep(self, seconds: float) -> bool:
        """
        可中断的等待（替代time.sleep，支持快速停止）
        
        Args:
            seconds: 等待秒数
            
        Returns:
            True表示正常等待结束，False表示被中断（收到停止信号）
        """
        return not self._stop_event.wait(timeout=seconds)
    
    def _component_loop(self, name: str, meta: Dict[str, Any]):
        """
        单个组件的独立监控循环（在独立线程中运行）
        
        Args:
            name: 组件名称
            meta: 组件元数据（包含check、restart函数等）
        """
        is_critical = meta.get("is_critical", True)
        
        while self._running:
            try:
                # 健康检查
                ok = False
                try:
                    ok = bool(meta["check"]())
                except Exception:
                    ok = False
                
                if ok:
                    # 组件健康
                    if meta["fails"] > 0 and self._logger:
                        # 只有关键组件或经历了多次失败的非关键组件才记录恢复日志
                        if is_critical or meta["fails"] >= 10:
                            self._logger.info(f"组件恢复: {name}")
                    meta["fails"] = 0
                    # 等待下次检查（可中断）
                    if not self._interruptible_sleep(self._check_interval):
                        break  # 收到停止信号，退出循环
                    continue
                
                # 组件不健康
                meta["fails"] += 1
                
                # 只有关键组件才记录异常日志
                if self._logger and is_critical:
                    self._logger.warning(f"组件异常: {name} fails={meta['fails']}")
                
                if meta["fails"] >= self._failure_threshold:
                    # 进入重启循环
                    restart_attempt = 0
                    while self._running:
                        restart_attempt += 1
                        
                        # 尝试重启
                        ok_restart = False
                        try:
                            ok_restart = bool(meta["restart"]())
                        except Exception:
                            ok_restart = False
                        
                        if ok_restart:
                            # 重启成功
                            meta["fails"] = 0
                            # 只有关键组件或经历了多次重试的非关键组件才记录成功日志
                            if self._logger and (is_critical or restart_attempt >= 10):
                                if restart_attempt > 1:
                                    self._logger.info(f"组件已重启: {name} | 重试{restart_attempt}次后成功")
                                else:
                                    self._logger.info(f"组件已重启: {name}")
                            break
                        
                        # 重启失败，继续重试
                        # 只有关键组件才记录重试日志（每10次或首次）
                        if self._logger and is_critical and (restart_attempt == 1 or restart_attempt % 10 == 0):
                            self._logger.error(f"组件重启失败: {name} | 已重试{restart_attempt}次 | {self._retry_delay}s后继续...")
                        
                        # 可中断的等待
                        if not self._interruptible_sleep(self._retry_delay):
                            break  # 收到停止信号，退出重启循环
                else:
                    # 还未达到故障阈值，等待下次检查（可中断）
                    if not self._interruptible_sleep(self._check_interval):
                        break  # 收到停止信号，退出循环
                    
            except Exception as e:
                # 捕获异常，防止监控线程退出
                if self._logger:
                    self._logger.error(f"监控线程异常: {name} | {e}")
                # 可中断的等待
                if not self._interruptible_sleep(self._retry_delay):
                    break  # 收到停止信号，退出循环
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取所有组件的状态
        
        Returns:
            包含所有组件状态的字典
        """
        status = {
            "monitoring": self._running,
            "components": {},
            "threads": len(self._threads),
        }
        
        for name, meta in self._components.items():
            try:
                is_healthy = bool(meta["check"]())
                status["components"][name] = {
                    "healthy": is_healthy,
                    "fails": meta.get("fails", 0),
                    "is_critical": meta.get("is_critical", True),
                }
            except Exception as e:
                status["components"][name] = {
                    "healthy": False,
                    "error": str(e),
                    "fails": meta.get("fails", 0),
                    "is_critical": meta.get("is_critical", True),
                }
        
        return status

