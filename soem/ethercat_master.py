#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
EtherCAT 主站实现
基于 PySOEM 库，提供 EtherCAT 主站功能
"""

import logging
import threading
import time
from typing import List, Optional, Callable, Dict, Any
import struct

try:
    import pysoem
except ImportError:
    pysoem = None
    print("警告: PySOEM 未安装，请运行: pip install pysoem")


class EtherCATMaster:
    """
    EtherCAT 主站类
    
    功能：
    - 扫描和配置 EtherCAT 从站
    - 周期性 PDO 数据交换
    - 从站状态管理
    - 错误处理和恢复
    """
    
    def __init__(self, interface_name: str, logger: Optional[logging.Logger] = None):
        """
        初始化 EtherCAT 主站
        
        Args:
            interface_name: 网卡接口名称
                Windows: '\\Device\\NPF_{GUID}'  (使用 ipconfig /all 查看)
                Linux: 'eth0', 'enp0s3' 等
            logger: 日志记录器
        """
        if pysoem is None:
            raise ImportError("PySOEM 未安装，请运行: pip install pysoem")
        
        self._logger = logger or logging.getLogger(__name__)
        self._interface = interface_name
        self._master: Optional[pysoem.Master] = None
        self._slaves: List[Any] = []
        
        # 线程控制
        self._cycle_thread: Optional[threading.Thread] = None
        self._running = False
        self._cycle_time = 0.001  # 1ms 默认循环时间
        
        # 状态回调
        self._process_data_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        
        # 统计信息
        self._cycle_count = 0
        self._error_count = 0
        self._last_cycle_time = 0
        
    def open(self) -> bool:
        """
        打开 EtherCAT 主站
        
        Returns:
            bool: 是否成功打开
        """
        try:
            self._master = pysoem.Master()
            self._master.open(self._interface)
            self._logger.info(f"成功打开 EtherCAT 主站: {self._interface}")
            return True
        except Exception as e:
            self._logger.error(f"打开 EtherCAT 主站失败: {e}")
            return False
    
    def scan_slaves(self) -> int:
        """
        扫描 EtherCAT 从站
        
        Returns:
            int: 发现的从站数量
        """
        if not self._master:
            self._logger.error("主站未打开")
            return 0
        
        try:
            slave_count = self._master.config_init()
            self._slaves = self._master.slaves
            
            self._logger.info(f"发现 {slave_count} 个 EtherCAT 从站:")
            for i, slave in enumerate(self._slaves):
                self._logger.info(
                    f"  从站 {i}: {slave.name} "
                    f"(厂商ID: 0x{slave.man:08X}, 产品代码: 0x{slave.id:08X})"
                )
            
            return slave_count
        except Exception as e:
            self._logger.error(f"扫描从站失败: {e}")
            return 0
    
    def config_map(self) -> bool:
        """
        配置 PDO 映射
        
        Returns:
            bool: 是否配置成功
        """
        if not self._master:
            self._logger.error("主站未打开")
            return False
        
        try:
            self._master.config_map()
            
            # 显示 IO 映射信息
            self._logger.info("PDO 映射配置:")
            for i, slave in enumerate(self._slaves):
                self._logger.info(
                    f"  从站 {i}: 输入 {slave.ibytes} 字节, "
                    f"输出 {slave.obytes} 字节"
                )
            
            return True
        except Exception as e:
            self._logger.error(f"配置 PDO 映射失败: {e}")
            return False
    
    def set_operational(self, timeout_ms: int = 5000) -> bool:
        """
        将所有从站设置为 OPERATIONAL 状态
        
        Args:
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            bool: 是否成功进入 OPERATIONAL 状态
        """
        if not self._master:
            self._logger.error("主站未打开")
            return False
        
        try:
            # 进入 SAFE-OP 状态
            self._master.state_check(pysoem.SAFEOP_STATE, timeout_ms * 1000)
            
            # 发送一次过程数据
            self._master.send_processdata()
            self._master.receive_processdata(2000)
            
            # 进入 OP 状态
            self._master.state_check(pysoem.OP_STATE, timeout_ms * 1000)
            
            # 检查所有从站状态
            all_op = True
            for i, slave in enumerate(self._slaves):
                state = self._master.state_check(pysoem.OP_STATE, 50000, i)
                if state != pysoem.OP_STATE:
                    self._logger.warning(f"从站 {i} 未能进入 OP 状态: {state}")
                    all_op = False
            
            if all_op:
                self._logger.info("所有从站已进入 OPERATIONAL 状态")
            else:
                self._logger.warning("部分从站未能进入 OPERATIONAL 状态")
            
            return all_op
        except Exception as e:
            self._logger.error(f"设置 OPERATIONAL 状态失败: {e}")
            return False
    
    def start_cycle(self, cycle_time: float = 0.001) -> bool:
        """
        启动周期性数据交换
        
        Args:
            cycle_time: 循环周期（秒），默认 1ms
            
        Returns:
            bool: 是否成功启动
        """
        if self._running:
            self._logger.warning("循环已经在运行")
            return False
        
        self._cycle_time = cycle_time
        self._running = True
        self._cycle_thread = threading.Thread(target=self._cycle_loop, daemon=True)
        self._cycle_thread.start()
        
        self._logger.info(f"启动 EtherCAT 循环，周期: {cycle_time * 1000:.2f} ms")
        return True
    
    def stop_cycle(self):
        """停止周期性数据交换"""
        if not self._running:
            return
        
        self._running = False
        if self._cycle_thread:
            self._cycle_thread.join(timeout=2.0)
        
        self._logger.info("停止 EtherCAT 循环")
    
    def _cycle_loop(self):
        """循环线程主函数"""
        next_cycle = time.perf_counter()
        
        while self._running:
            cycle_start = time.perf_counter()
            
            try:
                # 发送输出数据
                self._master.send_processdata()
                
                # 接收输入数据
                work_counter = self._master.receive_processdata(2000)
                
                # 调用用户回调
                if self._process_data_callback:
                    self._process_data_callback()
                
                self._cycle_count += 1
                self._last_cycle_time = time.perf_counter() - cycle_start
                
                # 检查工作计数器
                expected_wc = sum(slave.obytes + slave.ibytes for slave in self._slaves)
                if work_counter < expected_wc:
                    self._logger.warning(
                        f"工作计数器不匹配: 期望 {expected_wc}, 实际 {work_counter}"
                    )
                    self._error_count += 1
                
            except Exception as e:
                self._logger.error(f"循环出错: {e}")
                self._error_count += 1
                if self._error_callback:
                    self._error_callback(str(e))
            
            # 等待下一个循环
            next_cycle += self._cycle_time
            sleep_time = next_cycle - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # 循环超时
                next_cycle = time.perf_counter()
    
    def close(self):
        """关闭 EtherCAT 主站"""
        # 停止循环
        self.stop_cycle()
        
        # 关闭主站
        if self._master:
            try:
                # 设置为 INIT 状态
                self._master.state = pysoem.INIT_STATE
                self._master.write_state()
                
                # 关闭接口
                self._master.close()
                self._logger.info("EtherCAT 主站已关闭")
            except Exception as e:
                self._logger.error(f"关闭主站失败: {e}")
            finally:
                self._master = None
    
    def set_process_data_callback(self, callback: Callable):
        """
        设置过程数据回调函数
        
        Args:
            callback: 回调函数，在每个循环周期调用
        """
        self._process_data_callback = callback
    
    def set_error_callback(self, callback: Callable[[str], None]):
        """
        设置错误回调函数
        
        Args:
            callback: 错误回调函数，参数为错误信息字符串
        """
        self._error_callback = callback
    
    def read_slave_input(self, slave_index: int) -> bytes:
        """
        读取从站输入数据
        
        Args:
            slave_index: 从站索引（从0开始）
            
        Returns:
            bytes: 输入数据
        """
        if not self._master or slave_index >= len(self._slaves):
            return b''
        
        return bytes(self._slaves[slave_index].input)
    
    def write_slave_output(self, slave_index: int, data: bytes):
        """
        写入从站输出数据
        
        Args:
            slave_index: 从站索引（从0开始）
            data: 输出数据
        """
        if not self._master or slave_index >= len(self._slaves):
            return
        
        slave = self._slaves[slave_index]
        output_len = min(len(data), slave.obytes)
        slave.output = data[:output_len]
    
    def sdo_read(self, slave_index: int, index: int, subindex: int, 
                 data_type: str = 'B') -> Any:
        """
        SDO 读取
        
        Args:
            slave_index: 从站索引
            index: 对象字典索引
            subindex: 子索引
            data_type: 数据类型（struct格式，如 'B', 'H', 'I', 'f' 等）
            
        Returns:
            读取的数据值
        """
        if not self._master or slave_index >= len(self._slaves):
            return None
        
        try:
            data = self._master.sdo_read(slave_index, index, subindex)
            return struct.unpack(data_type, data)[0]
        except Exception as e:
            self._logger.error(f"SDO 读取失败: {e}")
            return None
    
    def sdo_write(self, slave_index: int, index: int, subindex: int, 
                  value: Any, data_type: str = 'B') -> bool:
        """
        SDO 写入
        
        Args:
            slave_index: 从站索引
            index: 对象字典索引
            subindex: 子索引
            value: 要写入的值
            data_type: 数据类型（struct格式）
            
        Returns:
            bool: 是否写入成功
        """
        if not self._master or slave_index >= len(self._slaves):
            return False
        
        try:
            data = struct.pack(data_type, value)
            self._master.sdo_write(slave_index, index, subindex, data)
            return True
        except Exception as e:
            self._logger.error(f"SDO 写入失败: {e}")
            return False
    
    @property
    def slave_count(self) -> int:
        """获取从站数量"""
        return len(self._slaves)
    
    @property
    def slaves(self) -> List[Any]:
        """获取从站列表"""
        return self._slaves
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
    
    @property
    def cycle_count(self) -> int:
        """获取循环次数"""
        return self._cycle_count
    
    @property
    def error_count(self) -> int:
        """获取错误次数"""
        return self._error_count
    
    @property
    def last_cycle_time(self) -> float:
        """获取上次循环时间（秒）"""
        return self._last_cycle_time
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            dict: 包含循环次数、错误次数等信息
        """
        return {
            'cycle_count': self._cycle_count,
            'error_count': self._error_count,
            'last_cycle_time_ms': self._last_cycle_time * 1000,
            'error_rate': self._error_count / max(self._cycle_count, 1),
            'slave_count': len(self._slaves),
            'is_running': self._running,
        }
    
    def __enter__(self):
        """上下文管理器入口"""
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()

