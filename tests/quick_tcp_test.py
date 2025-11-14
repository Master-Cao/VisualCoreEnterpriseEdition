#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
快速 TCP 测试脚本
快速连接并发送几次 catch 命令
"""

import socket
import time


def quick_test():
    """快速测试 TCP 连接和 catch 命令"""
    host = "192.168.2.126"
    port = 8888
    
    print(f"连接到 {host}:{port} ...")
    
    try:
        # 创建连接
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5)
        client.connect((host, port))
        print(f"✓ 连接成功\n")
        
        # 发送 5 次 catch 命令
        for i in range(5):
            print(f"--- 测试 {i+1}/5 ---")
            
            # 发送命令
            start = time.time()
            client.sendall(b"catch\n")
            
            # 接收响应
            response = client.recv(4096).decode('utf-8').strip()
            elapsed = (time.time() - start) * 1000
            
            print(f"响应: {response}")
            print(f"耗时: {elapsed:.1f}ms\n")
            
            time.sleep(0.5)
        
        client.close()
        print("✓ 测试完成")
        
    except ConnectionRefusedError:
        print(f"✗ 连接被拒绝 (服务器未启动？)")
    except socket.timeout:
        print(f"✗ 连接超时")
    except Exception as e:
        print(f"✗ 错误: {e}")


if __name__ == "__main__":
    quick_test()

