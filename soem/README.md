# SOEM EtherCAT 主站模块

## 简介

基于 PySOEM 的 EtherCAT 主站实现，专门用于控制**信捷 DS5C1S 伺服驱动器**。

## 支持的伺服型号

- ✅ **信捷 DS5C1S** - 标准型（17位编码器，最大转速3000 RPM）

## 快速开始

### 1. 安装依赖

```bash
cd soem
pip install -r requirements.txt
```

主要依赖：
- `pysoem` - EtherCAT 主站库
- `pyyaml` - 配置文件支持

### 2. 修改配置

编辑 `examples/xinje_example.py`：

```python
# 修改网卡名称（Windows）
INTERFACE = "\\Device\\NPF_{YOUR_GUID}"
```

**查看网卡GUID：**
```bash
ipconfig /all
```

### 3. 运行示例

```bash
cd examples
python xinje_example.py
```

## 使用示例

### 基本代码

```python
from ethercat_master import EtherCATMaster
from xinje_servo import XinJeDS5C1S
from servo_drive import ServoMode

# 创建主站
master = EtherCATMaster("\\Device\\NPF_{GUID}")
master.open()
master.scan_slaves()
master.config_map()

# 创建信捷 DS5C1S 伺服
servo = XinJeDS5C1S(master, slave_index=0)

# 设置速度模式
servo.set_mode(ServoMode.PROFILE_VELOCITY)

# 进入运行状态
master.set_operational()

def process_data():
    servo.read_inputs()
    if not servo.is_enabled:
        servo.enable()
    servo.write_outputs()

master.set_process_data_callback(process_data)
master.start_cycle(0.001)

# 等待使能
import time
while not servo.is_enabled:
    time.sleep(0.1)

# 控制速度
servo.set_target_velocity(1000)  # 1000 RPM
time.sleep(5)

servo.set_target_velocity(0)     # 停止
time.sleep(1)

master.close()
```

## 控制模式

### PV 模式（推荐 - 传送带控制）

**Profile Velocity 模式（模式代码：3）**

根据 DS5C1S 手册，PV 模式的 PDO 映射：
- **RxPDO（输出）**: 控制字(0x6040) + 目标速度(0x60FF)
- **TxPDO（输入）**: 状态字(0x6041) + 速度反馈(0x606C)

```python
# 创建伺服对象（指定PV模式）
servo = XinJeDS5C1S(master, 0, pdo_mode='velocity')

# 设置PV模式
servo.set_mode(ServoMode.PROFILE_VELOCITY)  # 模式3

# 配置PV参数（加减速度等）
servo.configure_pv_parameters()

# 启动
servo.set_target_velocity(1000)  # 1000 指令单位/s

# 停止
servo.set_target_velocity(0)

# 读取速度反馈
current_speed = servo.velocity  # 从 0x606C 读取
```

**适用场景：** 传送带启停、速度控制

**重要参数（根据手册）：**
- `0x60FF`: 目标速度（Target velocity）
- `0x6083`: 轮廓加速度
- `0x6084`: 轮廓减速度
- `0x606C`: 速度反馈（Velocity actual）

### PP 模式（位置控制）

```python
servo.set_mode(ServoMode.PROFILE_POSITION)  # 模式1

# 移动到指定位置（PP模式示例，PV模式不需要）
servo.set_target_position(100000)

# 等待到达（PP模式才需要）
time.sleep(3.0)  # 等待运动完成
```

**适用场景：** 定位、往复运动

## 目录结构

```
soem/
├── README.md                    # 本文档
├── requirements.txt             # 依赖包
├── __init__.py                  # 模块初始化
├── ethercat_master.py          # EtherCAT 主站类
├── servo_drive.py              # 伺服驱动器基类
├── xinje_servo.py              # 信捷伺服实现
├── utils.py                    # 工具函数
├── config_example.yaml         # 配置示例
└── examples/
    └── xinje_example.py        # 信捷伺服示例
```

## 主要类说明

### EtherCATMaster - 主站类

```python
master = EtherCATMaster(interface, logger)
master.open()                    # 打开主站
master.scan_slaves()             # 扫描从站
master.config_map()              # 配置PDO
master.set_operational()         # 进入运行状态
master.start_cycle(0.001)        # 启动1ms循环
master.close()                   # 关闭主站
```

### 信捷 DS5C1S 伺服类

```python
# 创建伺服对象
from xinje_servo import XinJeDS5C1S
servo = XinJeDS5C1S(master, slave_index=0)

# 控制方法
servo.set_mode(mode)             # 设置工作模式
servo.enable()                   # 使能伺服
servo.set_target_velocity(rpm)   # 设置速度
servo.set_target_position(pos)   # 设置位置

# 属性读取
servo.position                   # 当前位置
servo.velocity                   # 当前速度
servo.is_enabled                 # 是否使能
servo.get_state()                # 获取状态
```

## 常见问题

### Q: 未发现从站？
A: 检查：
1. 伺服驱动器是否上电
2. 网线是否连接
3. 网卡名称是否正确

### Q: 伺服使能失败？
A: 检查：
1. 驱动器是否报警（查看显示屏）
2. 紧急停止按钮是否按下
3. 使能信号是否正确

### Q: 循环时间过长？
A: 
- 检查电脑性能
- 减少日志输出
- 关闭其他程序

## 技术支持

- **PySOEM 文档**: https://github.com/bnjmnp/pysoem
- **CiA 402 标准**: CANopen 设备规范
- **信捷官方**: 查看伺服驱动器手册

## 版本信息

- **版本**: 1.0.0
- **Python**: 3.8+
- **操作系统**: Windows 10+, Linux

---

**注意**: 使用前请仔细阅读伺服驱动器手册，确保正确配置和安全操作。

