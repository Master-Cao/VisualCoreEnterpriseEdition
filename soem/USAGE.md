# 信捷 DS5C1S 伺服使用指南

## 📖 快速上手

### 传送带启停控制（PV 模式）

```python
from ethercat_master import EtherCATMaster
from xinje_servo import XinJeDS5C1S
from servo_drive import ServoMode
import time

# 1. 创建主站
master = EtherCATMaster("\\Device\\NPF_{YOUR_GUID}")
master.open()
master.scan_slaves()
master.config_map()

# 2. 创建伺服对象（PV模式）
servo = XinJeDS5C1S(master, slave_index=0, pdo_mode='velocity')

# 3. 设置PV模式
servo.set_mode(ServoMode.PROFILE_VELOCITY)  # 模式 3

# 4. 配置参数
servo.configure_pv_parameters()  # 配置加减速度

# 5. 启动主站
master.set_operational()

def process_data():
    servo.read_inputs()
    if not servo.is_enabled:
        servo.enable()
    servo.write_outputs()

master.set_process_data_callback(process_data)
master.start_cycle(0.001)

# 6. 等待使能
while not servo.is_enabled:
    time.sleep(0.1)

# 7. 控制传送带
# 启动
servo.set_target_velocity(1000)
time.sleep(5)

# 停止
servo.set_target_velocity(0)
time.sleep(1)

# 8. 关闭
master.close()
```

---

## 📋 PV 模式详解

### PDO 映射（根据手册 7.7）

**RxPDO（主站 → 驱动器）：**
| 地址 | 名称 | 类型 | 字节数 | 说明 |
|------|------|------|--------|------|
| 0x6040 | 控制字 | U16 | 2 | 伺服控制命令 |
| 0x60FF | 目标速度 | I32 | 4 | 速度给定值 |

**TxPDO（驱动器 → 主站）：**
| 地址 | 名称 | 类型 | 字节数 | 说明 |
|------|------|------|--------|------|
| 0x6041 | 状态字 | U16 | 2 | 伺服状态 |
| 0x606C | 速度反馈 | I32 | 4 | 实际速度 |

### 关键参数（SDO）

**速度相关：**
- `0x60FF`: 目标速度（Target velocity）- 通过 PDO 发送
- `0x606C`: 速度反馈（Velocity actual）- 通过 PDO 读取
- `0x607F`: 最大轮廓速度（Max profile velocity）
- `0x6080`: 最大电机速度（Max motor speed）

**加减速：**
- `0x6083`: 轮廓加速度（Profile acceleration）
- `0x6084`: 轮廓减速度（Profile deceleration）
- `0x60C5`: 最大加速度（Max acceleration）
- `0x60C6`: 最大减速度（Max deceleration）

### 速度单位说明

根据手册，速度单位为 **"指令单位/s"**，实际含义取决于：
- `0x608F`: 位置编码器分辨率（Encoder resolution）
- `0x6092`: Feed 常数（Feed constant）

**示例：**
如果配置为：
- 编码器分辨率 = 131072 pulse/rev
- Feed常数 = 1（转）

则 `速度 1000` = 1000 pulse/s ≈ 0.0076 转/s ≈ 0.46 RPM

**建议：**查看驱动器实际配置，或通过测试确定速度比例关系。

---

## 🔧 常见操作

### 1. 启动传送带
```python
servo.set_target_velocity(1000)  # 设置速度
# 伺服会自动按照配置的加速度加速
```

### 2. 停止传送带
```python
servo.set_target_velocity(0)  # 速度设为0
# 伺服会自动按照配置的减速度减速停止
```

### 3. 调整速度
```python
# 运行中可以随时改变速度
servo.set_target_velocity(500)   # 减速
servo.set_target_velocity(1500)  # 加速
```

### 4. 反转
```python
servo.set_target_velocity(-1000)  # 负数=反转
```

### 5. 读取状态
```python
speed = servo.velocity          # 当前速度反馈
state = servo.get_state()       # 伺服状态
enabled = servo.is_enabled      # 是否使能
status = servo.statusword       # 状态字
```

---

## ⚙️ 高级配置

### 自定义加减速度

```python
# 使用 SDO 设置参数
servo.sdo_write(0x6083, 0, 5000, 'I')   # 加速度 5000
servo.sdo_write(0x6084, 0, 5000, 'I')   # 减速度 5000
servo.sdo_write(0x60C5, 0, 10000, 'I')  # 最大加速度
servo.sdo_write(0x60C6, 0, 10000, 'I')  # 最大减速度
```

### 速度限制

```python
servo.sdo_write(0x607F, 0, 3000, 'I')   # 最大轮廓速度
servo.sdo_write(0x6080, 0, 3000, 'I')   # 最大电机速度
```

### 读取编码器配置

```python
# 读取编码器分辨率
enc_pulse = servo.sdo_read(0x608F, 1, 'I')  # 编码器脉冲数
motor_rev = servo.sdo_read(0x608F, 2, 'I')  # 电机转数
print(f"编码器分辨率: {enc_pulse}/{motor_rev} = {enc_pulse/motor_rev} pulse/rev")
```

---

## ⚠️ 注意事项

1. **使能等待**：根据手册，使能后需等待约 100ms 才能发送速度命令

2. **PDO 映射**：实际 PDO 映射可能因驱动器配置而异，可通过以下方式确认：
   ```python
   print(f"输入字节: {master.slaves[0].ibytes}")  # 应为 6 bytes
   print(f"输出字节: {master.slaves[0].obytes}")  # 应为 6 bytes
   ```

3. **速度单位**：需要根据实际配置确定速度单位换算关系

4. **模式切换**：切换控制模式前，应先禁用伺服

---

## 🐛 故障排查

### 问题1：伺服无法使能
- 检查状态字 `servo.statusword`
- 检查是否有故障 `servo.is_fault`
- 尝试故障复位 `servo.fault_reset()`

### 问题2：发送速度命令无反应
- 确认已使能 `servo.is_enabled`
- 确认模式正确（PV 模式 = 3）
- 检查最大速度限制

### 问题3：速度反馈为 0
- 检查 PDO 映射是否正确
- 确认 `pdo_mode='velocity'`
- 打印原始输入数据查看

---

## 📚 参考文档

- **DS5C1S 用户手册**: 第7章 EtherCAT 总线控制模式
- **CiA 402**: CANopen 设备规范
- **PySOEM**: https://github.com/bnjmnp/pysoem

