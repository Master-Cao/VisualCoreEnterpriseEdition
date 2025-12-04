#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
信捷（XinJe）伺服驱动器实现
支持 DS5C1S 型号
遵循 CiA 402 标准，通过 EtherCAT (CoE) 协议通信
"""

import struct
import logging
from typing import Optional, Any

from .servo_drive import ServoDrive, ServoMode


class XinJeDS5C1S(ServoDrive):
    """
    信捷 DS5C1S 系列伺服驱动器
    
    特性：
    - 支持位置、速度、力矩控制
    - 17位绝对值编码器（131072 pulse/rev）
    - 最大转速 3000 RPM
    
    PDO 映射（根据手册 - PV模式推荐）:
    - RxPDO (输出到驱动器):
        - Controlword (0x6040): 2 bytes
        - Target Velocity (0x60FF): 4 bytes  ← PV模式核心
        
    - TxPDO (从驱动器输入):
        - Statusword (0x6041): 2 bytes
        - Velocity Actual (0x606C): 4 bytes  ← PV模式反馈
    
    注意：实际PDO映射可能因驱动器配置而异，如果数据不匹配，
         请根据实际配置修改 read_inputs() 和 write_outputs()
    """
    
    def __init__(self, master: Any, slave_index: int, 
                 pdo_mode: str = 'velocity',
                 logger: Optional[logging.Logger] = None):
        """
        初始化信捷 DS5C1S 驱动器
        
        Args:
            master: EtherCAT 主站实例
            slave_index: 从站索引
            pdo_mode: PDO模式 ('velocity' 速度模式, 'position' 位置模式)
            logger: 日志记录器
        """
        super().__init__(master, slave_index, logger)
        
        # PDO 模式
        self._pdo_mode = pdo_mode
        
        # 输出数据缓存
        self._target_position = 0
        self._target_velocity = 0
        
        # 信捷 DS5C1S 特定参数
        self.encoder_resolution = 131072  # 17位编码器
        self.max_rpm = 3000
        
        self._logger.info(f"DS5C1S 初始化，PDO模式: {pdo_mode}")
        
    def read_inputs(self):
        """从 PDO 读取输入数据"""
        try:
            data = self._master.read_slave_input(self._slave_index)
            
            if len(data) < 6:
                self._logger.warning(f"输入数据长度不足: {len(data)} bytes")
                return
            
            # 状态字（所有模式都有）
            self._statusword = struct.unpack('<H', data[0:2])[0]
            
            if self._pdo_mode == 'velocity':
                # PV 模式：状态字(2) + 速度反馈(4)
                if len(data) >= 6:
                    self._current_velocity = struct.unpack('<i', data[2:6])[0]
                    # 位置可能不在PDO中，保持上次的值
            else:
                # PP 模式：状态字(2) + 位置反馈(4)
                if len(data) >= 6:
                    self._current_position = struct.unpack('<i', data[2:6])[0]
                
        except Exception as e:
            self._logger.error(f"读取输入数据失败: {e}")
    
    def write_outputs(self):
        """写入 PDO 输出数据"""
        try:
            if self._pdo_mode == 'velocity':
                # PV 模式：控制字(2) + 目标速度(4)
                data = struct.pack('<Hi', 
                                 self._controlword,
                                 self._target_velocity)
            else:
                # PP 模式：控制字(2) + 目标位置(4)
                data = struct.pack('<Hi', 
                                 self._controlword,
                                 self._target_position)
            
            self._master.write_slave_output(self._slave_index, data)
            
        except Exception as e:
            self._logger.error(f"写入输出数据失败: {e}")
    
    def set_target_velocity(self, velocity: int):
        """
        设置目标速度（PV模式）
        
        Args:
            velocity: 目标速度（指令单位/s，根据608Fh和6092h配置）
                     通常可以理解为 RPM 或 编码器计数/s
        """
        self._target_velocity = velocity
        self._logger.debug(f"设置目标速度: {velocity}")
    
    def configure_pv_parameters(self):
        """
        配置 PV 模式的常用参数（通过SDO）
        建议在使能前调用
        """
        try:
            self._logger.info("配置 PV 模式参数...")
            
            # 设置加速度和减速度（根据手册）
            self.sdo_write(0x6083, 0, 3000, 'I')  # 轮廓加速度
            self.sdo_write(0x6084, 0, 3000, 'I')  # 轮廓减速度
            
            # 设置最大加减速度
            self.sdo_write(0x60C5, 0, 10000, 'I')  # 最大加速度
            self.sdo_write(0x60C6, 0, 10000, 'I')  # 最大减速度
            
            # 设置最大速度
            self.sdo_write(0x607F, 0, 3000, 'I')  # 最大轮廓速度
            
            self._logger.info("PV 模式参数配置完成")
            return True
            
        except Exception as e:
            self._logger.error(f"配置 PV 参数失败: {e}")
            return False


# 信捷伺服常用参数表
XINJE_COMMON_PARAMS = {
    'DS5C1S': {
        'encoder_resolution': 131072,  # 17位
        'max_rpm': 3000,
        'rated_torque': 1.27,  # N·m (根据具体型号不同)
        'max_torque': 3.82,    # N·m
    }
}


if __name__ == "__main__":
    # 显示支持的型号信息
    print("信捷伺服驱动器支持的型号:")
    for model, params in XINJE_COMMON_PARAMS.items():
        print(f"\n{model}:")
        print(f"  编码器分辨率: {params['encoder_resolution']} pulse/rev")
        print(f"  最大转速: {params['max_rpm']} RPM")
        print(f"  额定力矩: {params['rated_torque']} N·m")
        print(f"  最大力矩: {params['max_torque']} N·m")



