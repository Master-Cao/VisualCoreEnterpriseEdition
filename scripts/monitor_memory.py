#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内存监控脚本
持续监控 VisionCore 进程的内存使用情况
"""

import psutil
import time
import sys
import os
from datetime import datetime


def find_visioncore_process():
    """查找 VisionCore 主进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('main.py' in cmd or 'app.main' in cmd for cmd in cmdline):
                if any('python' in cmd.lower() for cmd in cmdline):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def format_bytes(bytes_val):
    """格式化字节数"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f}TB"


def get_system_memory():
    """获取系统内存信息"""
    mem = psutil.virtual_memory()
    return {
        'total': mem.total,
        'available': mem.available,
        'used': mem.used,
        'free': mem.free,
        'cached': mem.cached if hasattr(mem, 'cached') else 0,
        'buffers': mem.buffers if hasattr(mem, 'buffers') else 0,
        'percent': mem.percent
    }


def monitor_process(process, interval=5):
    """监控进程内存使用"""
    print("=" * 80)
    print(f"开始监控 VisionCore 进程 (PID: {process.pid})")
    print(f"监控间隔: {interval}秒")
    print("=" * 80)
    print()
    
    # 表头
    header = f"{'时间':<12} | {'RSS':<10} | {'VMS':<10} | {'共享':<10} | {'CPU%':<6} | {'系统内存%':<10} | {'Buff/Cache':<12}"
    print(header)
    print("-" * 80)
    
    last_mem = None
    
    try:
        while True:
            try:
                # 进程内存信息
                mem_info = process.memory_info()
                cpu_percent = process.cpu_percent(interval=0.1)
                
                # 系统内存信息
                sys_mem = get_system_memory()
                
                # RSS (Resident Set Size): 实际物理内存
                rss = mem_info.rss
                # VMS (Virtual Memory Size): 虚拟内存
                vms = mem_info.vms
                # 共享内存
                shared = mem_info.shared if hasattr(mem_info, 'shared') else 0
                
                # buff/cache
                buff_cache = sys_mem['buffers'] + sys_mem['cached']
                
                # 当前时间
                now = datetime.now().strftime("%H:%M:%S")
                
                # 内存变化趋势
                trend = ""
                if last_mem:
                    diff = rss - last_mem
                    if diff > 0:
                        trend = f" ↑{format_bytes(diff)}"
                    elif diff < 0:
                        trend = f" ↓{format_bytes(-diff)}"
                
                # 输出
                line = f"{now:<12} | {format_bytes(rss):<10} | {format_bytes(vms):<10} | {format_bytes(shared):<10} | {cpu_percent:>5.1f}% | {sys_mem['percent']:>8.1f}% | {format_bytes(buff_cache):<12}{trend}"
                print(line)
                
                last_mem = rss
                
                time.sleep(interval)
                
            except psutil.NoSuchProcess:
                print("\n进程已退出")
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n监控出错: {e}")
                time.sleep(interval)
                
    except KeyboardInterrupt:
        print("\n\n监控已停止")
        print("=" * 80)
        
        # 显示最终状态
        try:
            sys_mem = get_system_memory()
            print(f"\n最终系统内存状态:")
            print(f"  总内存: {format_bytes(sys_mem['total'])}")
            print(f"  已使用: {format_bytes(sys_mem['used'])} ({sys_mem['percent']:.1f}%)")
            print(f"  可用:   {format_bytes(sys_mem['available'])}")
            print(f"  缓存:   {format_bytes(sys_mem['cached'])}")
            print(f"  缓冲:   {format_bytes(sys_mem['buffers'])}")
            print(f"  总缓存: {format_bytes(sys_mem['cached'] + sys_mem['buffers'])}")
        except Exception:
            pass


def main():
    """主函数"""
    print("\n正在查找 VisionCore 进程...")
    
    process = find_visioncore_process()
    
    if not process:
        print("错误：未找到 VisionCore 进程")
        print("请确保 VisionCore 正在运行")
        sys.exit(1)
    
    # 监控间隔
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    monitor_process(process, interval)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

