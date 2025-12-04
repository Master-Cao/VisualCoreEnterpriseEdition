# 机器人反馈控制系统

## 📋 概述

本系统实现了**基于机器人反馈的状态机控制**，解决两个关键问题：
1. **传送带停止后物体晃动** → 等待物体稳定后再发送坐标
2. **机器人遮挡视野** → 发送坐标后等待机器人完成再继续检测发送

---

## 🔄 工作流程

### **完整流程图**

```
┌─────────────────────────────────────────────────────────────┐
│  开始检测循环                                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  1. 取图检测    │
        └────────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │ 检测到目标？    │
        └────┬───────┬───┘
             │ 否    │ 是
             │       ▼
             │  ┌────────────────┐
             │  │ GPIO控制传送带  │
             │  │ 有目标 → GPIO低 │
             │  │ 无目标 → GPIO高 │
             │  └────────┬───────┘
             │           │
             │           ▼
             │  ┌─────────────────────┐
             │  │ 传送带刚停止？       │
             │  └────┬───────┬────────┘
             │       │ 是    │ 否
             │       ▼       │
             │  ┌────────────────────┐│
             │  │ 启动稳定等待        ││
             │  │ (150ms)            ││
             │  └────────────────────┘│
             │           │             │
             │           ▼             │
             │  ┌────────────────────┐│
             │  │ 等待稳定中？        ││
             │  └────┬───────┬────────┘
             │       │ 是    │ 否
             │       │       ▼
             │       │  ┌────────────────────┐
             │       │  │ 机器人抓取中？      │
             │       │  └────┬───────┬───────┘
             │       │       │ 是    │ 否
             │       │       │       ▼
             │       │       │  ┌─────────────────┐
             │       │       │  │ 2. 计算坐标      │
             │       │       │  └────────┬────────┘
             │       │       │           ▼
             │       │       │  ┌─────────────────┐
             │       │       │  │ 3. 发送TCP       │
             │       │       │  └────────┬────────┘
             │       │       │           ▼
             │       │       │  ┌─────────────────┐
             │       │       │  │ 设置抓取中状态   │
             │       │       │  └─────────────────┘
             │       │       │
             ▼       ▼       ▼
        ┌────────────────────────┐
        │  4. 日志输出            │
        │  - 无目标               │
        │  - 等待稳定             │
        │  - 抓取中               │
        │  - 已发送               │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ 等待10ms        │
        └────────┬───────┘
                 │
                 └──────► 返回循环开始
                 
        (并行) 机器人客户端
                 │
                 ▼
        ┌────────────────┐
        │ 完成抓取        │
        └────────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │ 发送 "complete" │
        └────────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │ 解除抓取锁定    │
        └────────────────┘
```

---

## 🎯 状态机定义

### **1. 稳定等待状态**

```python
stability_state = {
    "waiting_stable": False,      # 是否正在等待物体稳定
    "stable_start_time": 0,       # 开始等待的时间
    "stable_wait_duration": 0.15, # 等待时长（可配置）
    "last_gpio_state": {},        # 记录上次GPIO状态
}
```

**触发条件**：GPIO从高变低（传送带停止）

**等待时长**：可配置，默认150ms（在 `config.yaml` 中设置 `roi.stabilityWaitTime`）

**结束条件**：等待时间到达

---

### **2. 机器人抓取状态**

```python
_robot_state = {
    "is_picking": False,      # 是否正在抓取
    "lock": threading.Lock(), # 线程安全锁
    "last_send_time": 0,      # 上次发送时间
}
```

**触发条件**：成功发送TCP坐标

**结束条件**：收到机器人的 "complete" 消息

---

## 📊 日志状态说明

系统会根据不同状态输出不同的日志：

| 状态 | 日志输出 | 说明 |
|------|---------|------|
| **无目标** | `状态=无目标` <br> `TCP=[0,0,0,0,0]` | 视野内没有检测到物体 |
| **等待稳定** | `状态=等待稳定` <br> `TCP=[暂不发送]` | 传送带刚停止，等待物体停稳 |
| **抓取中** | `状态=抓取中` <br> `TCP=[等待complete]` | 已发送坐标，机器人正在抓取 |
| **已发送** | `TCP=[x,y,z]` <br> `发送=Xms` | 坐标已成功发送给机器人 |

### **日志示例**

```
# 正常工作流程
[循环#100] 取图=25.3ms | 检测=45.2ms | 检测数=3 | 目标数=1 | ROI1=1 | ROI2=0 | 状态=无目标 | TCP=[0,0,0,0,0] | 总计=75.8ms

[循环#101] 取图=24.8ms | 检测=44.9ms | 检测数=2 | 目标数=1 | ROI1=1 | ROI2=0 | 坐标=2.3ms | TCP=[252.13,-398.12,-78.52] | 发送=0.5ms | 总计=73.2ms
✓ 坐标已发送 [252.13,-398.12,-78.52]，机器人进入抓取状态，等待complete消息

[循环#102] 取图=25.1ms | 检测=45.3ms | 检测数=2 | 目标数=1 | ROI1=1 | ROI2=0 | 状态=抓取中 | TCP=[等待complete] | 总计=72.5ms

[循环#103] 取图=24.9ms | 检测=0.0ms | 检测数=0 | 目标数=0 | ROI1=0 | ROI2=0 | 状态=抓取中 | TCP=[等待complete] | 总计=26.1ms
(机器人遮挡视野，检测结果为0，但因为抓取中状态，不会触发传送带移动)

✓ 收到complete消息，机器人抓取完成（耗时2.35秒），恢复检测发送

[循环#104] 取图=25.2ms | 检测=45.1ms | 检测数=3 | 目标数=1 | ROI1=1 | ROI2=0 | 坐标=2.4ms | TCP=[251.63,-383.17,-76.93] | 发送=0.6ms | 总计=74.8ms
```

---

## 🔧 配置说明

### **config.yaml**

```yaml
roi:
  enable: true
  minArea: 3000
  depthThreshold: 665
  stabilityWaitTime: 0.15  # 传送带停止后等待物体稳定的时间（秒）
  regions:
    - name: main_work_area
      shape: rectangle
      width: 150
      height: 100
      offsetx: 0
      offsety: 30
      priority: 1
      gpio:
        enable: true
        pin: 20
        chip: dev/gpiochip3
```

**参数说明**：

- `stabilityWaitTime`: 
  - 默认值：`0.15` (150毫秒)
  - 建议范围：`0.1 - 0.3` 秒
  - 说明：传送带停止后等待物体完全停稳的时间
  - 调优建议：
    - 传送带速度快 → 增大此值（0.2-0.3秒）
    - 传送带速度慢 → 减小此值（0.1-0.15秒）
    - 物体轻巧易晃 → 增大此值
    - 物体重稳定快 → 减小此值

---

## 📡 TCP通信协议

### **1. 坐标发送（系统 → 机器人）**

**格式**：`x,y,z\r\n`

**示例**：
```
252.13,-398.12,-78.52\r\n
```

**说明**：
- 坐标格式：浮点数，保留2位小数
- 单位：毫米（mm）
- 坐标系：已通过标定转换为机器人坐标系

---

### **2. 完成反馈（机器人 → 系统）**

**格式**：`complete\r\n`

**示例**：
```
complete\r\n
```

**说明**：
- 机器人完成抓取后发送此消息
- 系统收到后解除抓取锁定，恢复检测发送
- 系统会回复 `ok\r\n` 确认收到

**机器人客户端示例代码**：

```python
import socket
import time

# 连接到VisionCore系统
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('192.168.2.90', 8888))

while True:
    # 接收坐标
    data = sock.recv(1024).decode('utf-8').strip()
    if data:
        print(f"收到坐标: {data}")
        
        # 解析坐标
        coords = data.split(',')
        if len(coords) == 3:
            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
            
            # 移动机器人到目标位置
            move_robot(x, y, z)
            
            # 执行抓取
            time.sleep(2.0)  # 模拟抓取过程
            
            # 发送完成消息
            sock.sendall(b"complete\r\n")
            print("抓取完成，已发送complete")
```

---

## ⚙️ 代码实现

### **关键函数**

#### **1. handle_robot_complete()**

```python
def handle_robot_complete(message: str, ctx) -> None:
    """
    处理机器人发送的 complete 消息
    解除抓取锁定状态
    """
    global _robot_state
    
    if message and "complete" in message.lower():
        with _robot_state["lock"]:
            was_picking = _robot_state["is_picking"]
            _robot_state["is_picking"] = False
            pick_duration = time.perf_counter() - _robot_state["last_send_time"]
        
        if logger and was_picking:
            logger.info(f"✓ 收到complete消息，机器人抓取完成（耗时{pick_duration:.2f}秒），恢复检测发送")
        
        return True
    
    return False
```

**调用位置**：`services/comm/comm_manager.py` 的 TCP 消息回调中

---

#### **2. 发送坐标后设置状态**

```python
if tcp_response:
    # ... 发送TCP代码 ...
    
    # 发送成功后，设置机器人状态为抓取中
    if send_success:
        with _robot_state["lock"]:
            _robot_state["is_picking"] = True
            _robot_state["last_send_time"] = current_time
        if logger:
            logger.info(f"✓ 坐标已发送 [{tcp_response}]，机器人进入抓取状态，等待complete消息")
```

---

#### **3. 检测和发送逻辑**

```python
# 检查机器人状态（线程安全）
with _robot_state["lock"]:
    is_robot_picking = _robot_state["is_picking"]

# 只有在非等待稳定 AND 机器人非抓取状态时才计算和发送坐标
if best_target and depth_data is not None and camera_params is not None:
    # 条件1：等待物体稳定
    if stability_state["waiting_stable"]:
        # 跳过
        pass
    # 条件2：机器人正在抓取
    elif is_robot_picking:
        # 跳过
        pass
    # 条件3：都满足，可以计算和发送
    else:
        # 计算坐标并发送
        coord = CoordinateProcessor.calculate_coordinate_for_detection(...)
        tcp_response = f"{x:.2f},{y:.2f},{z:.2f}"
```

---

## 🔍 问题排查

### **问题1：收到complete后仍然显示"抓取中"**

**可能原因**：
- TCP消息格式不正确（需要包含 `\r\n`）
- complete消息被其他命令拦截

**排查方法**：
```bash
# 查看日志
tail -f logs/visioncore_*.log | grep -i complete
```

**解决方案**：
- 确保机器人发送 `complete\r\n`
- 检查TCP客户端代码

---

### **问题2：坐标抖动严重**

**可能原因**：
- `stabilityWaitTime` 设置过短
- 传送带惯性大

**解决方案**：
```yaml
# 增加等待时间
roi:
  stabilityWaitTime: 0.2  # 从0.15增加到0.2秒
```

---

### **问题3：响应延迟过大**

**可能原因**：
- `stabilityWaitTime` 设置过长
- 机器人抓取时间过长

**分析方法**：
```bash
# 查看抓取耗时
grep "抓取完成（耗时" logs/visioncore_*.log
```

**优化方案**：
- 减少 `stabilityWaitTime`
- 优化机器人动作速度
- 检查网络延迟

---

### **问题4：机器人遮挡时传送带仍然移动**

**可能原因**：
- 未收到complete消息
- 抓取状态未正确设置

**排查方法**：
```bash
# 查看状态变化
grep -E "抓取状态|complete" logs/visioncore_*.log
```

**解决方案**：
- 确认机器人正确发送complete
- 检查TCP连接稳定性

---

## 🎯 最佳实践

### **1. 参数调优顺序**

1. **先调整 `stabilityWaitTime`**
   - 测试传送带停止后物体的晃动时间
   - 设置为 `晃动时间 + 50ms` 的安全余量

2. **测试机器人抓取流程**
   - 确保complete消息正确发送
   - 验证抓取锁定正常工作

3. **观察日志状态变化**
   - 确认状态转换符合预期
   - 检查坐标稳定性

---

### **2. 性能优化建议**

- **稳定等待时间**：尽可能短，但保证坐标稳定
- **机器人动作**：优化路径规划，减少抓取时间
- **网络通信**：使用TCP_NODELAY，减少延迟

---

### **3. 生产环境配置**

```yaml
# 推荐配置
roi:
  stabilityWaitTime: 0.15  # 根据实际测试调整
  minArea: 3000           # 过滤小物体
  
DetectionServer:
  buffer_size: 4096
  connection_timeout: 300
  heartbeat_interval: 30
```

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `handlers/system.py` | 主检测循环、状态机实现 |
| `services/comm/comm_manager.py` | TCP消息处理、complete消息解析 |
| `services/comm/tcp_server.py` | TCP服务器实现 |
| `configs/config.yaml` | 系统配置 |

---

## ✅ 验证清单

部署后请验证：

- [ ] 传送带停止后等待150ms才发送坐标
- [ ] 坐标发送后日志显示"抓取中"状态
- [ ] 机器人遮挡时传送带不会移动
- [ ] 收到complete消息后恢复正常检测
- [ ] 日志状态变化符合预期：`无目标 → 已发送 → 抓取中 → 收到complete → 已发送`

---

**更新日期**：2025-11-29  
**版本**：v2.0  
**状态**：✅ 已实现并测试

