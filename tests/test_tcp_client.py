#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
TCP 客户端测试工具
用于测试 TCP 服务器的连接和命令响应
"""

import socket
import time
import sys


class TCPTestClient:
    """简单的 TCP 测试客户端"""
    
    def __init__(self, host: str = "192.168.2.126", port: int = 8888):
        """
        初始化 TCP 客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
    
    def connect(self, timeout: int = 5) -> bool:
        """
        连接到 TCP 服务器
        
        Args:
            timeout: 连接超时时间（秒）
            
        Returns:
            连接是否成功
        """
        try:
            print(f"正在连接到 {self.host}:{self.port} ...")
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.host, self.port))
            
            self.connected = True
            print(f"✓ 连接成功: {self.host}:{self.port}")
            return True
            
        except socket.timeout:
            print(f"✗ 连接超时: {self.host}:{self.port}")
            return False
        except ConnectionRefusedError:
            print(f"✗ 连接被拒绝: {self.host}:{self.port} (服务器可能未启动)")
            return False
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def send_command(self, command: str, timeout: float = 10.0) -> str:
        """
        发送命令到服务器并接收响应
        
        Args:
            command: 要发送的命令（自动添加换行符）
            timeout: 接收超时时间（秒）
            
        Returns:
            服务器响应字符串，失败返回空字符串
        """
        if not self.connected or not self.socket:
            print("✗ 未连接到服务器")
            return ""
        
        try:
            # 发送命令（确保有换行符）
            if not command.endswith('\n'):
                command += '\n'
            
            print(f"\n→ 发送: {command.strip()}")
            self.socket.sendall(command.encode('utf-8'))
            
            # 接收响应（设置临时超时）
            self.socket.settimeout(timeout)
            response = self.socket.recv(4096).decode('utf-8').strip()
            
            print(f"← 响应: {response}")
            return response
            
        except socket.timeout:
            print(f"✗ 接收响应超时 (>{timeout}s)")
            return ""
        except Exception as e:
            print(f"✗ 命令发送/接收失败: {e}")
            return ""
    
    def disconnect(self):
        """断开连接"""
        if self.socket:
            try:
                self.socket.close()
                print(f"\n✓ 已断开连接")
            except Exception as e:
                print(f"✗ 断开连接失败: {e}")
        self.connected = False
        self.socket = None
    
    def test_catch_command(self, count: int = 1, interval: float = 0.5):
        """
        测试 catch 命令
        
        Args:
            count: 测试次数
            interval: 每次测试间隔（秒）
        """
        if not self.connected:
            print("✗ 未连接到服务器，无法测试")
            return
        
        print(f"\n{'='*60}")
        print(f"开始测试 catch 命令 (共 {count} 次)")
        print(f"{'='*60}")
        
        success_count = 0
        total_time = 0.0
        
        for i in range(count):
            print(f"\n--- 测试 {i+1}/{count} ---")
            
            start_time = time.time()
            response = self.send_command("catch")
            elapsed = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response:
                success_count += 1
                total_time += elapsed
                
                # 解析响应（格式：检测数量,x,y,z,angle）
                try:
                    parts = response.split(',')
                    if len(parts) >= 5:
                        det_count = int(parts[0])
                        x = float(parts[1])
                        y = float(parts[2])
                        z = float(parts[3])
                        angle = float(parts[4])
                        
                        print(f"  检测数量: {det_count}")
                        if det_count > 0:
                            print(f"  坐标: X={x:.3f}, Y={y:.3f}, Z={z:.3f}, Angle={angle:.3f}")
                        print(f"  响应时间: {elapsed:.1f}ms")
                    else:
                        # 可能是错误代码
                        print(f"  服务器响应: {response}")
                        print(f"  响应时间: {elapsed:.1f}ms")
                except Exception as e:
                    print(f"  解析响应失败: {e}")
            
            # 等待间隔
            if i < count - 1:
                time.sleep(interval)
        
        # 统计信息
        print(f"\n{'='*60}")
        print(f"测试完成统计:")
        print(f"  总测试次数: {count}")
        print(f"  成功次数: {success_count}")
        print(f"  失败次数: {count - success_count}")
        if success_count > 0:
            print(f"  平均响应时间: {total_time / success_count:.1f}ms")
        print(f"{'='*60}")


def interactive_mode():
    """交互模式：用户手动输入命令"""
    print("\n" + "="*60)
    print("TCP 客户端测试工具 - 交互模式")
    print("="*60)
    print("输入命令并按回车发送，输入 'quit' 或 'exit' 退出")
    print("="*60 + "\n")
    
    client = TCPTestClient(host="192.168.2.126", port=8888)
    
    if not client.connect():
        return
    
    try:
        while True:
            command = input("\n请输入命令 > ").strip()
            
            if command.lower() in ('quit', 'exit', 'q'):
                print("退出交互模式...")
                break
            
            if not command:
                continue
            
            client.send_command(command)
    
    except KeyboardInterrupt:
        print("\n\n检测到 Ctrl+C，退出...")
    finally:
        client.disconnect()


def auto_test_mode():
    """自动测试模式：自动执行预定义的测试"""
    print("\n" + "="*60)
    print("TCP 客户端测试工具 - 自动测试模式")
    print("="*60 + "\n")
    
    client = TCPTestClient(host="192.168.2.100", port=8888)
    
    if not client.connect():
        return
    
    try:
        # 测试 catch 命令
        client.test_catch_command(count=1000, interval=0.5)
        
    except KeyboardInterrupt:
        print("\n\n检测到 Ctrl+C，停止测试...")
    finally:
        client.disconnect()


def main():
    """主函数"""
    print("\n" + "="*60)
    print("TCP 客户端测试工具")
    print("目标服务器: 192.168.2.126:8888")
    print("="*60)
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        print("\n选择测试模式:")
        print("  1. 交互模式 (手动输入命令)")
        print("  2. 自动测试模式 (自动执行测试)")
        choice = input("\n请选择 (1/2, 默认=1): ").strip() or "1"
        mode = "interactive" if choice == "1" else "auto"
    
    if mode in ("interactive", "i", "1"):
        interactive_mode()
    elif mode in ("auto", "a", "2"):
        auto_test_mode()
    else:
        print(f"未知模式: {mode}")
        print("用法: python test_tcp_client.py [interactive|auto]")


if __name__ == "__main__":
    main()

