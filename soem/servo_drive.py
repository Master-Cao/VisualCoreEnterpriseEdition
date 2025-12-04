#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
伺服驱动器抽象类
支持 CiA 402 (CANopen over EtherCAT) 标准
"""

import logging
import struct
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Optional, Any


class ServoState(IntEnum):
    """伺服状态枚举 (CiA 402)"""
    NOT_READY_TO_SWITCH_ON = 0
    SWITCH_ON_DISABLED = 1
    READY_TO_SWITCH_ON = 2
    SWITCHED_ON = 3
    OPERATION_ENABLED = 4
    QUICK_STOP_ACTIVE = 5
    FAULT_REACTION_ACTIVE = 6
    FAULT = 7


class ServoMode(IntEnum):
    """伺服工作模式 (CiA 402)"""
    PROFILE_POSITION = 1      # PP 模式 - 位置模式
    PROFILE_VELOCITY = 3      # PV 模式 - 速度模式
    PROFILE_TORQUE = 4        # PT 模式 - 力矩模式
    HOMING = 6                # HM 模式 - 回零模式
    INTERPOLATED_POSITION = 7 # IP 模式 - 插补位置模式
    CYCLIC_SYNC_POSITION = 8  # CSP 模式 - 循环同步位置模式
    CYCLIC_SYNC_VELOCITY = 9  # CSV 模式 - 循环同步速度模式
    CYCLIC_SYNC_TORQUE = 10   # CST 模式 - 循环同步力矩模式


class ServoDrive(ABC):
    """
    伺服驱动器抽象基类
    遵循 CiA 402 标准
    """
    
    # CiA 402 标准对象字典索引
    OD_CONTROLWORD = 0x6040      # 控制字
    OD_STATUSWORD = 0x6041       # 状态字
    OD_OPERATION_MODE = 0x6060   # 操作模式
    OD_OPERATION_MODE_DISPLAY = 0x6061  # 操作模式显示
    
    OD_TARGET_POSITION = 0x607A  # 目标位置
    OD_POSITION_ACTUAL = 0x6064  # 实际位置
    
    OD_TARGET_VELOCITY = 0x60FF  # 目标速度
    OD_VELOCITY_ACTUAL = 0x606C  # 实际速度
    
    OD_TARGET_TORQUE = 0x6071    # 目标力矩
    OD_TORQUE_ACTUAL = 0x6077    # 实际力矩
    
    # 控制字位定义
    CTRL_SWITCH_ON = 0x0001
    CTRL_ENABLE_VOLTAGE = 0x0002
    CTRL_QUICK_STOP = 0x0004
    CTRL_ENABLE_OPERATION = 0x0008
    CTRL_FAULT_RESET = 0x0080
    
    # 状态字位定义
    STATUS_READY_TO_SWITCH_ON = 0x0001
    STATUS_SWITCHED_ON = 0x0002
    STATUS_OPERATION_ENABLED = 0x0004
    STATUS_FAULT = 0x0008
    STATUS_VOLTAGE_ENABLED = 0x0010
    STATUS_QUICK_STOP = 0x0020
    STATUS_SWITCH_ON_DISABLED = 0x0040
    STATUS_WARNING = 0x0080
    STATUS_TARGET_REACHED = 0x0400
    
    def __init__(self, master: Any, slave_index: int, 
                 logger: Optional[logging.Logger] = None):
        """
        初始化伺服驱动器
        
        Args:
            master: EtherCAT 主站实例
            slave_index: 从站索引
            logger: 日志记录器
        """
        self._master = master
        self._slave_index = slave_index
        self._logger = logger or logging.getLogger(__name__)
        
        # 缓存的状态
        self._statusword = 0
        self._controlword = 0
        self._current_position = 0
        self._current_velocity = 0
        self._current_torque = 0
    
    @abstractmethod
    def read_inputs(self):
        """
        从 PDO 读取输入数据
        子类需要实现具体的数据解析
        """
        pass
    
    @abstractmethod
    def write_outputs(self):
        """
        写入 PDO 输出数据
        子类需要实现具体的数据打包
        """
        pass
    
    def sdo_read(self, index: int, subindex: int = 0, data_type: str = 'I') -> Any:
        """
        SDO 读取
        
        Args:
            index: 对象字典索引
            subindex: 子索引
            data_type: 数据类型
            
        Returns:
            读取的值
        """
        return self._master.sdo_read(self._slave_index, index, subindex, data_type)
    
    def sdo_write(self, index: int, subindex: int = 0, 
                  value: Any = None, data_type: str = 'I') -> bool:
        """
        SDO 写入
        
        Args:
            index: 对象字典索引
            subindex: 子索引
            value: 要写入的值
            data_type: 数据类型
            
        Returns:
            是否写入成功
        """
        return self._master.sdo_write(self._slave_index, index, subindex, 
                                       value, data_type)
    
    def get_state(self) -> ServoState:
        """
        获取伺服当前状态
        
        Returns:
            ServoState: 当前状态
        """
        status = self._statusword
        
        # 根据状态字判断状态（CiA 402 状态机）
        if status & 0x004F == 0x0000:
            return ServoState.NOT_READY_TO_SWITCH_ON
        elif status & 0x004F == 0x0040:
            return ServoState.SWITCH_ON_DISABLED
        elif status & 0x006F == 0x0021:
            return ServoState.READY_TO_SWITCH_ON
        elif status & 0x006F == 0x0023:
            return ServoState.SWITCHED_ON
        elif status & 0x006F == 0x0027:
            return ServoState.OPERATION_ENABLED
        elif status & 0x006F == 0x0007:
            return ServoState.QUICK_STOP_ACTIVE
        elif status & 0x004F == 0x000F:
            return ServoState.FAULT_REACTION_ACTIVE
        elif status & 0x004F == 0x0008:
            return ServoState.FAULT
        else:
            return ServoState.NOT_READY_TO_SWITCH_ON
    
    def enable(self) -> bool:
        """
        使能伺服驱动器（进入 OPERATION ENABLED 状态）
        
        Returns:
            bool: 是否成功使能
        """
        try:
            state = self.get_state()
            
            # 如果在故障状态，先复位故障
            if state == ServoState.FAULT:
                self._logger.info(f"从站 {self._slave_index}: 检测到故障，执行故障复位")
                self.fault_reset()
                return False
            
            # 状态机转换
            if state == ServoState.SWITCH_ON_DISABLED:
                # Shutdown 命令
                self._controlword = (self._controlword & ~0x87) | 0x06
                self.write_outputs()
                self._logger.debug(f"从站 {self._slave_index}: Shutdown")
                
            elif state == ServoState.READY_TO_SWITCH_ON:
                # Switch On 命令
                self._controlword = (self._controlword & ~0x87) | 0x07
                self.write_outputs()
                self._logger.debug(f"从站 {self._slave_index}: Switch On")
                
            elif state == ServoState.SWITCHED_ON:
                # Enable Operation 命令
                self._controlword = (self._controlword & ~0x87) | 0x0F
                self.write_outputs()
                self._logger.info(f"从站 {self._slave_index}: Enable Operation")
                
            elif state == ServoState.OPERATION_ENABLED:
                self._logger.debug(f"从站 {self._slave_index}: 已使能")
                return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"使能伺服失败: {e}")
            return False
    
    def fault_reset(self) -> bool:
        """
        故障复位
        
        Returns:
            bool: 是否成功复位
        """
        try:
            # 故障复位命令
            self._controlword = self._controlword | self.CTRL_FAULT_RESET
            self.write_outputs()
            self._logger.info(f"从站 {self._slave_index}: 故障复位")
            return True
        except Exception as e:
            self._logger.error(f"故障复位失败: {e}")
            return False
    
    def set_mode(self, mode: ServoMode) -> bool:
        """
        设置工作模式
        
        Args:
            mode: 工作模式
            
        Returns:
            bool: 是否设置成功
        """
        try:
            success = self.sdo_write(self.OD_OPERATION_MODE, 0, mode, 'b')
            if success:
                self._logger.info(f"从站 {self._slave_index}: 设置模式为 {mode.name}")
            return success
        except Exception as e:
            self._logger.error(f"设置工作模式失败: {e}")
            return False
    
    def set_target_velocity(self, velocity: int):
        """
        设置目标速度（速度模式）
        
        Args:
            velocity: 目标速度（RPM 或编码器计数/s）
        """
        self._target_velocity = velocity
    
    @property
    def position(self) -> int:
        """获取当前位置"""
        return self._current_position
    
    @property
    def velocity(self) -> int:
        """获取当前速度"""
        return self._current_velocity
    
    @property
    def torque(self) -> int:
        """获取当前力矩"""
        return self._current_torque
    
    @property
    def statusword(self) -> int:
        """获取状态字"""
        return self._statusword
    
    @property
    def is_enabled(self) -> bool:
        """是否已使能"""
        return self.get_state() == ServoState.OPERATION_ENABLED
    
    @property
    def is_fault(self) -> bool:
        """是否处于故障状态"""
        return self.get_state() == ServoState.FAULT
    
    def __repr__(self) -> str:
        return (f"<ServoDrive slave={self._slave_index} "
                f"state={self.get_state().name} "
                f"pos={self._current_position}>")

