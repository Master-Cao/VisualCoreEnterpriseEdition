#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SOEM EtherCAT 主站模块
支持通过EtherCAT协议控制信捷DS5C1S伺服驱动器
"""

from .ethercat_master import EtherCATMaster
from .servo_drive import ServoDrive, ServoState, ServoMode
from .xinje_servo import XinJeDS5C1S

__all__ = [
    'EtherCATMaster',
    'ServoDrive',
    'ServoState',
    'ServoMode',
    'XinJeDS5C1S',
]

__version__ = '1.0.0'

