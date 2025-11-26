# VisionCore Enterprise Edition - API接口使用手册

> **版本**: v1.3.0  
> **更新日期**: 2025-11-26  
> **文档类型**: API参考手册

---

## 📋 目录

- [接口概述](#接口概述)
- [TCP接口](#tcp接口)
- [MQTT接口](#mqtt接口)
- [命令详解](#命令详解)
- [错误码说明](#错误码说明)
- [最佳实践](#最佳实践)
- [示例代码](#示例代码)

---

## 接口概述

VisionCore Enterprise Edition 提供两种通信接口：

| 接口类型 | 用途 | 特点 | 推荐场景 |
|---------|------|------|---------|
| **TCP** | 实时检测 | 低延迟、高性能 | PLC、机器人实时控制 |
| **MQTT** | 远程控制 | 异步、可靠 | 上位机、远程监控 |

### 架构图

```
┌─────────────┐                    ┌──────────────────┐
│   PLC/机器人 │ ─── TCP ────────→ │                  │
└─────────────┘     (实时检测)      │   VisionCore     │
                                    │   Enterprise     │
┌─────────────┐                    │                  │
│   上位机     │ ─── MQTT ───────→ │                  │
└─────────────┘     (远程控制)      └──────────────────┘
```

---

## TCP接口

### 基本信息

- **协议**: TCP Socket
- **默认端口**: 8888
- **编码**: UTF-8
- **消息格式**: 文本行（以 `\n` 结尾）
- **连接方式**: 长连接（支持多客户端并发）

### 连接建立

```python
import socket

# 创建TCP连接
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("192.168.2.126", 8888))
print("✓ TCP连接成功")
```

### 心跳机制

- 系统每30秒检查一次客户端心跳
- 超过5分钟无通信的连接会被自动清理
- 建议客户端定期发送命令保持连接活跃

### 支持的命令

#### 1. catch - 执行检测

**功能**: 执行一次目标检测，返回机器人坐标

**请求格式**:
```
catch\n
```

**响应格式**:
```
p1_flag,p2_flag,x,y,z\n
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `p1_flag` | int | 主标志位（1=检测到目标，0=未检测到，-1=遮挡） |
| `p2_flag` | int | 副标志位（保留，当前为0） |
| `x` | float | X坐标（mm） |
| `y` | float | Y坐标（mm） |
| `z` | float | Z坐标（mm） |

**响应示例**:

```
# 成功检测到目标
1,0,363.30,-110.74,-85.00

# 未检测到目标
0,0,0.00,0.00,0.00

# 机器人遮挡（正在执行抓取动作）
-1,0,0.00,0.00,0.00

# 错误：相机未就绪
E1,0,0,0,0

# 错误：请求频率过高
E2,0,0,0,0

# 错误：正在处理中
E3,0,0,0,0
```

**完整示例**:

```python
import socket
import time

def tcp_catch():
    # 连接服务器
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("192.168.2.126", 8888))
    
    try:
        # 发送catch命令
        client.sendall(b"catch\n")
        
        # 接收响应
        response = client.recv(4096).decode('utf-8').strip()
        print(f"响应: {response}")
        
        # 解析响应
        parts = response.split(',')
        if len(parts) == 5:
            p1, p2, x, y, z = parts
            
            if p1 == '1':
                print(f"✓ 检测到目标: X={x}, Y={y}, Z={z}")
                return float(x), float(y), float(z)
            elif p1 == '0':
                print("× 未检测到目标")
                return None
            elif p1 == '-1':
                print("⚠ 机器人遮挡（正在动作）")
                return None
            elif p1.startswith('E'):
                print(f"✗ 错误: {p1}")
                return None
    finally:
        client.close()

# 使用示例
coords = tcp_catch()
if coords:
    x, y, z = coords
    print(f"发送坐标给机器人: [{x}, {y}, {z}]")
```

### 性能特性

| 指标 | 数值 | 说明 |
|------|------|------|
| **响应延迟** | < 200ms | 从发送命令到接收响应 |
| **最大并发** | 15个客户端 | 可配置 |
| **防抖间隔** | 100ms | 两次请求最小间隔 |
| **超时时间** | 5分钟 | 无通信自动断开 |

### 遮挡检测机制

VisionCore v1.3.0+ 引入智能遮挡检测：

**工作原理**:
1. 系统监测两次TCP请求的时间间隔
2. 当间隔 > `intervalThreshold`（默认700ms）时，认为机器人正在执行抓取动作
3. 接下来的 `ignoreCount`（默认3）次检测都返回 `-1,0,0,0,0`（遮挡标志）
4. 避免机器人动作期间误触发皮带移动信号

**配置**:
```yaml
roi:
  occlusion:
    intervalThreshold: 700  # 间隔阈值（ms）
    ignoreCount: 3          # 忽略次数
```

**典型时序**:
```
时间    |  动作                    | TCP响应
--------|-------------------------|------------------
T0      | 检测1                   | 1,0,100,200,-50
T0+200  | 检测2                   | 1,0,105,198,-48
T0+1000 | 检测3（间隔800ms）       | -1,0,0,0,0  ← 检测到大间隔
T0+1100 | 检测4（机器人正在抓取）   | -1,0,0,0,0  ← 忽略（1/3）
T0+1200 | 检测5（机器人正在抓取）   | -1,0,0,0,0  ← 忽略（2/3）
T0+1300 | 检测6（机器人正在抓取）   | -1,0,0,0,0  ← 忽略（3/3）
T0+1400 | 检测7（恢复正常）        | 1,0,110,195,-52 ← 恢复检测
```

### 多线程并发处理

VisionCore的TCP服务器支持多客户端并发：

- **Accept线程**: 监听并接受新连接
- **Client线程**: 每个客户端独立线程处理
- **Heartbeat线程**: 心跳检测和超时清理

**优势**:
- 多个客户端互不影响
- 单个客户端阻塞不影响其他客户端
- 自动清理超时连接

---

## MQTT接口

### 基本信息

- **协议**: MQTT 3.1.1
- **默认端口**: 1883
- **QoS**: 2（精确一次传递）
- **消息格式**: JSON

### 主题订阅

| 主题 | 方向 | 用途 |
|------|------|------|
| `visual/system/command` | 订阅 | 接收控制命令 |
| `visual/system/result` | 发布 | 发送执行结果 |

### 连接示例

```python
import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc):
    print(f"✓ MQTT连接成功: {rc}")
    # 订阅命令主题
    client.subscribe("visual/system/result", qos=2)

def on_message(client, userdata, msg):
    print(f"收到消息: {msg.topic}")
    data = json.loads(msg.payload)
    print(json.dumps(data, indent=2, ensure_ascii=False))

# 创建客户端
client = mqtt.Client(client_id="visioncore_client")
client.on_connect = on_connect
client.on_message = on_message

# 连接服务器
client.connect("192.168.2.126", 1883, 60)
client.loop_start()
```

### 消息格式

#### 请求格式

```json
{
  "command": "命令名称",
  "data": {
    // 命令参数（可选）
  }
}
```

#### 响应格式

```json
{
  "command": "命令名称",
  "component": "组件名称",
  "messageType": "success | error | warning | info",
  "message": "执行结果描述",
  "data": {
    // 返回数据
  }
}
```

---

## 命令详解

### 1. get_config - 获取系统配置

**功能**: 获取当前系统配置和可用模型列表

**请求**:
```json
{
  "command": "get_config"
}
```

**响应**:
```json
{
  "command": "get_config",
  "component": "config",
  "messageType": "success",
  "message": "获取配置成功",
  "data": {
    "config": {
      "logging": { ... },
      "camera": { ... },
      "model": { ... },
      "DetectionServer": { ... },
      "mqtt": { ... },
      "roi": { ... },
      "sftp": { ... }
    },
    "available_models": [
      "seasoning_11.18.pt",
      "yolov8n-seg.pt"
    ]
  }
}
```

**用途**:
- 查看当前配置
- 获取可用模型列表
- 配置备份

---

### 2. save_config - 保存系统配置

**功能**: 保存新的系统配置（自动备份旧配置）

**请求**:
```json
{
  "command": "save_config",
  "data": {
    "config": {
      "model": {
        "conf_threshold": 0.8,
        "nms_threshold": 0.5
      },
      "roi": {
        "minArea": 3500
      }
    }
  }
}
```

**响应**:
```json
{
  "command": "save_config",
  "component": "config",
  "messageType": "success",
  "message": "配置已保存",
  "data": {
    "backup_file": "config.yaml.backup_20251126_103045",
    "changes": {
      "model.conf_threshold": "0.7 → 0.8",
      "model.nms_threshold": "0.6 → 0.5",
      "roi.minArea": "3000 → 3500"
    }
  }
}
```

**注意事项**:
- 保存前会自动备份旧配置到 `configs/config_backup/`
- 部分配置需要重启系统才能生效
- 建议先用 `get_config` 获取完整配置，修改后再保存

---

### 3. get_image - 获取相机图像

**功能**: 获取相机原始图像并上传到SFTP

**请求**:
```json
{
  "command": "get_image"
}
```

**响应**:
```json
{
  "command": "get_image",
  "component": "camera",
  "messageType": "success",
  "message": "获取图像成功",
  "data": {
    "filename": "camera_20251126_103045_123.jpg",
    "remote_path": "D://Camera/camera_20251126_103045_123.jpg",
    "image_size": [256, 192],
    "timestamp": "2025-11-26 10:30:45.123"
  }
}
```

**用途**:
- 查看相机实时画面
- 检查相机是否正常工作
- 调试图像质量问题

---

### 4. model_test - 测试AI模型

**功能**: 执行一次完整的检测测试，返回检测结果和可视化图像

**请求**:
```json
{
  "command": "model_test"
}
```

**响应**:
```json
{
  "command": "model_test",
  "component": "detector",
  "messageType": "success",
  "message": "模型测试成功",
  "data": {
    "detection_count": 2,
    "infer_time_ms": 45.3,
    "filename": "detection_test_20251126_103045_456.jpg",
    "remote_path": "D://Camera/detection_test_20251126_103045_456.jpg",
    "detections": [
      {
        "class": "seasoning",
        "confidence": 0.89,
        "bbox": [120, 80, 45, 38]
      },
      {
        "class": "seasoning",
        "confidence": 0.76,
        "bbox": [180, 95, 42, 35]
      }
    ]
  }
}
```

**用途**:
- 测试模型性能
- 验证检测效果
- 调试检测参数

---

### 5. catch - 执行单次检测

**功能**: 执行一次目标检测并返回机器人坐标

**请求**:
```json
{
  "command": "catch"
}
```

**响应（成功）**:
```json
{
  "command": "catch",
  "component": "detector",
  "messageType": "success",
  "message": "检测成功",
  "data": {
    "p1_flag": 1,
    "p2_flag": 0,
    "robot_coords": {
      "x": 363.30,
      "y": -110.74,
      "z": -85.00
    },
    "world_coords": {
      "x": 128.5,
      "y": 96.3,
      "z": -42.8
    },
    "detection": {
      "class": "seasoning",
      "confidence": 0.89,
      "area": 3245
    },
    "roi": "main_work_area",
    "infer_time_ms": 42.1,
    "timestamp": "2025-11-26 10:30:45.678"
  }
}
```

**响应（未检测到）**:
```json
{
  "command": "catch",
  "component": "detector",
  "messageType": "info",
  "message": "未检测到目标",
  "data": {
    "p1_flag": 0,
    "p2_flag": 0,
    "robot_coords": {
      "x": 0.0,
      "y": 0.0,
      "z": 0.0
    },
    "detection_count": 0,
    "infer_time_ms": 38.5
  }
}
```

**响应（遮挡）**:
```json
{
  "command": "catch",
  "component": "detector",
  "messageType": "warning",
  "message": "机器人遮挡",
  "data": {
    "p1_flag": -1,
    "p2_flag": 0,
    "robot_coords": {
      "x": 0.0,
      "y": 0.0,
      "z": 0.0
    },
    "occlusion_remaining": 2
  }
}
```

---

### 6. get_calibrat_image - 获取标定图像

**功能**: 检测标定板上的黑块并返回世界坐标

**请求**:
```json
{
  "command": "get_calibrat_image"
}
```

**响应**:
```json
{
  "command": "get_calibrat_image",
  "component": "calibration",
  "messageType": "success",
  "message": "检测到12个标定点",
  "data": {
    "blocks_count": 12,
    "world_coords": [
      {"id": 0, "x": 23.4, "y": 45.2, "z": -38.5},
      {"id": 1, "x": 54.3, "y": 43.8, "z": -37.9},
      // ... 其余10个点
    ],
    "grid": {
      "rows": 3,
      "cols": 4
    },
    "filename": "calib_20251126_103045_789.jpg",
    "remote_path": "D://Camera/calib_20251126_103045_789.jpg"
  }
}
```

**用途**:
- 标定流程第一步
- 获取标定板上的黑块世界坐标
- 用户使用机器人示教器移动到各点记录机器人坐标

---

### 7. coordinate_calibration - 执行坐标标定

**功能**: 根据世界坐标和机器人坐标执行标定，生成变换矩阵

**请求**:
```json
{
  "command": "coordinate_calibration",
  "data": {
    "world_points": [
      [23.4, 45.2, -38.5],
      [54.3, 43.8, -37.9],
      // ... 其余10个点
    ],
    "robot_points": [
      [363.30, -110.74, -85.00],
      [385.12, -142.56, -84.23],
      // ... 其余10个点
    ]
  }
}
```

**响应**:
```json
{
  "command": "coordinate_calibration",
  "component": "calibration",
  "messageType": "success",
  "message": "标定成功",
  "data": {
    "transformation_matrix": [
      [0.9876, -0.1234, 0.0056, 340.23],
      [0.1235, 0.9875, -0.0023, -95.67],
      [0.0034, 0.0045, 0.9999, -45.12],
      [0.0000, 0.0000, 0.0000, 1.0000]
    ],
    "rmse": {
      "xy": 2.34,
      "z": 3.21,
      "overall": 2.67
    },
    "quality": "优秀",
    "backup_file": "transformation_matrix.json.backup_20251126_103045"
  }
}
```

**质量评级**:
- `优秀`: RMSE < 3mm
- `良好`: RMSE < 5mm
- `合格`: RMSE < 8mm
- `需改进`: RMSE >= 8mm

---

## 错误码说明

### TCP错误码

| 错误码 | 含义 | 原因 | 解决方案 |
|--------|------|------|---------|
| `E1` | 设备未就绪 | 相机或检测器未初始化 | 检查相机连接和模型加载 |
| `E2` | 请求频率过高 | 两次请求间隔<100ms | 增加请求间隔 |
| `E3` | 正在处理中 | 上一次检测未完成 | 等待上一次完成后再请求 |

### MQTT错误响应

**示例**:
```json
{
  "command": "catch",
  "component": "camera",
  "messageType": "error",
  "message": "camera_not_ready",
  "data": {
    "error_code": "CAMERA_NOT_CONNECTED",
    "details": "相机连接断开，正在尝试重连..."
  }
}
```

**常见错误类型**:

| messageType | 含义 | 示例场景 |
|-------------|------|---------|
| `error` | 严重错误 | 相机断开、模型加载失败 |
| `warning` | 警告 | 未检测到目标、SFTP上传失败 |
| `info` | 信息 | 正常状态反馈 |

---

## 最佳实践

### TCP客户端最佳实践

```python
import socket
import time
import logging

class VisionCoreTCPClient:
    def __init__(self, host, port, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """建立连接"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.logger.info(f"✓ TCP连接成功: {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"✗ TCP连接失败: {e}")
            return False
    
    def catch(self, retry=3):
        """执行检测（带重试）"""
        for attempt in range(retry):
            try:
                # 发送命令
                self.socket.sendall(b"catch\n")
                
                # 接收响应
                response = self.socket.recv(4096).decode('utf-8').strip()
                
                # 解析响应
                parts = response.split(',')
                if len(parts) != 5:
                    raise ValueError(f"无效响应格式: {response}")
                
                p1, p2, x, y, z = parts
                
                # 处理不同情况
                if p1 == '1':
                    return {
                        'success': True,
                        'coords': (float(x), float(y), float(z))
                    }
                elif p1 == '0':
                    return {'success': False, 'reason': 'no_target'}
                elif p1 == '-1':
                    return {'success': False, 'reason': 'occlusion'}
                elif p1.startswith('E'):
                    error_code = p1
                    if error_code == 'E2' and attempt < retry - 1:
                        # 频率过高，等待后重试
                        time.sleep(0.2)
                        continue
                    return {'success': False, 'reason': f'error_{error_code}'}
                
            except socket.timeout:
                self.logger.warning(f"请求超时，重试 {attempt+1}/{retry}")
                if attempt < retry - 1:
                    time.sleep(0.5)
                    continue
            except Exception as e:
                self.logger.error(f"执行失败: {e}")
                break
        
        return {'success': False, 'reason': 'max_retry_exceeded'}
    
    def close(self):
        """关闭连接"""
        if self.socket:
            self.socket.close()
            self.logger.info("TCP连接已关闭")

# 使用示例
client = VisionCoreTCPClient("192.168.2.126", 8888)
if client.connect():
    result = client.catch()
    if result['success']:
        x, y, z = result['coords']
        print(f"检测成功: X={x}, Y={y}, Z={z}")
    else:
        print(f"检测失败: {result['reason']}")
    client.close()
```

### MQTT客户端最佳实践

```python
import paho.mqtt.client as mqtt
import json
import time
import logging
from queue import Queue

class VisionCoreMQTTClient:
    def __init__(self, broker_host, broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id=f"client_{int(time.time())}")
        self.logger = logging.getLogger(__name__)
        self.response_queue = Queue()
        
        # 设置回调
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info("✓ MQTT连接成功")
            # 订阅结果主题
            client.subscribe("visual/system/result", qos=2)
        else:
            self.logger.error(f"✗ MQTT连接失败: {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
            self.response_queue.put(data)
        except Exception as e:
            self.logger.error(f"消息解析失败: {e}")
    
    def connect(self):
        """连接服务器"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            time.sleep(1)  # 等待连接完成
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False
    
    def send_command(self, command, data=None, timeout=10):
        """发送命令并等待响应"""
        # 清空响应队列
        while not self.response_queue.empty():
            self.response_queue.get()
        
        # 构建请求
        request = {"command": command}
        if data:
            request["data"] = data
        
        # 发送请求
        self.client.publish(
            "visual/system/command",
            json.dumps(request),
            qos=2
        )
        self.logger.info(f"发送命令: {command}")
        
        # 等待响应
        try:
            response = self.response_queue.get(timeout=timeout)
            return response
        except:
            self.logger.error(f"等待响应超时: {command}")
            return None
    
    def get_config(self):
        """获取配置"""
        return self.send_command("get_config")
    
    def model_test(self):
        """模型测试"""
        return self.send_command("model_test")
    
    def catch(self):
        """执行检测"""
        return self.send_command("catch")
    
    def disconnect(self):
        """断开连接"""
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("MQTT连接已关闭")

# 使用示例
client = VisionCoreMQTTClient("192.168.2.126")
if client.connect():
    # 获取配置
    config = client.get_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))
    
    # 执行检测
    result = client.catch()
    if result and result['messageType'] == 'success':
        coords = result['data']['robot_coords']
        print(f"检测成功: {coords}")
    
    client.disconnect()
```

### 错误处理建议

```python
def robust_catch(client, max_retries=3):
    """鲁棒的检测调用"""
    for attempt in range(max_retries):
        result = client.catch()
        
        if not result:
            # 无响应，可能超时
            print(f"尝试 {attempt+1}/{max_retries}: 无响应")
            time.sleep(1)
            continue
        
        p1 = result.get('p1_flag')
        
        if p1 == 1:
            # 检测成功
            return result
        elif p1 == 0:
            # 未检测到目标（正常情况）
            return result
        elif p1 == -1:
            # 遮挡，等待后重试
            print(f"尝试 {attempt+1}/{max_retries}: 遮挡")
            time.sleep(0.5)
            continue
        elif p1 == 'E2':
            # 频率过高，等待后重试
            print(f"尝试 {attempt+1}/{max_retries}: 频率过高")
            time.sleep(0.2)
            continue
        else:
            # 其他错误
            print(f"错误: {p1}")
            return result
    
    return None
```

---

## 示例代码

### PLC集成示例（Python模拟）

```python
"""
PLC集成示例：周期性检测并发送坐标给机器人
"""
import time
from vision_tcp_client import VisionCoreTCPClient

def plc_control_loop():
    # 连接视觉系统
    vision = VisionCoreTCPClient("192.168.2.126", 8888)
    if not vision.connect():
        print("无法连接视觉系统")
        return
    
    try:
        while True:
            # 等待传感器信号（模拟）
            print("等待传感器信号...")
            time.sleep(1)  # 模拟等待
            
            # 执行检测
            result = vision.catch()
            
            if result['success']:
                x, y, z = result['coords']
                print(f"检测到目标: X={x:.2f}, Y={y:.2f}, Z={z:.2f}")
                
                # 发送给机器人（实际PLC中通过OPC UA/Modbus等协议）
                send_to_robot(x, y, z)
                
                # 等待机器人完成动作
                time.sleep(2)
            elif result['reason'] == 'no_target':
                print("未检测到目标，继续监测")
            elif result['reason'] == 'occlusion':
                print("机器人遮挡，跳过本次")
            else:
                print(f"检测失败: {result['reason']}")
    
    finally:
        vision.close()

def send_to_robot(x, y, z):
    """发送坐标给机器人（模拟）"""
    print(f"→ 发送给机器人: MOVEJ X={x} Y={y} Z={z}")

if __name__ == "__main__":
    plc_control_loop()
```

### 上位机监控示例

```python
"""
上位机监控示例：MQTT远程监控和控制
"""
from vision_mqtt_client import VisionCoreMQTTClient
import time

def monitoring_dashboard():
    client = VisionCoreMQTTClient("192.168.2.126")
    if not client.connect():
        print("无法连接MQTT服务器")
        return
    
    try:
        # 1. 获取系统配置
        print("=== 获取系统配置 ===")
        config = client.get_config()
        if config:
            print(f"模型: {config['data']['config']['model']['model_name']}")
            print(f"置信度阈值: {config['data']['config']['model']['conf_threshold']}")
        
        # 2. 模型测试
        print("\n=== 模型测试 ===")
        test_result = client.model_test()
        if test_result and test_result['messageType'] == 'success':
            data = test_result['data']
            print(f"检测数量: {data['detection_count']}")
            print(f"推理时间: {data['infer_time_ms']}ms")
            print(f"图像路径: {data.get('remote_path', 'N/A')}")
        
        # 3. 持续监测
        print("\n=== 开始监测（每5秒一次）===")
        for i in range(10):
            result = client.catch()
            if result and result['messageType'] == 'success':
                data = result['data']
                if data['p1_flag'] == 1:
                    coords = data['robot_coords']
                    print(f"[{i+1}] 检测到: X={coords['x']:.2f}, Y={coords['y']:.2f}, Z={coords['z']:.2f}")
                else:
                    print(f"[{i+1}] 未检测到目标")
            time.sleep(5)
    
    finally:
        client.disconnect()

if __name__ == "__main__":
    monitoring_dashboard()
```

---

## 性能优化建议

### TCP通信优化

1. **使用长连接**: 避免频繁建立/断开连接
2. **合理的请求频率**: 建议间隔 ≥ 200ms
3. **并发请求**: 多个工位可以独立连接
4. **错误重试**: 实现指数退避的重试策略

### MQTT通信优化

1. **QoS选择**: 
   - QoS 0: 最快，但可能丢消息
   - QoS 1: 至少一次送达
   - QoS 2: 精确一次送达（推荐）

2. **异步处理**: 使用回调而不是阻塞等待

3. **消息批处理**: 避免频繁发送小消息

---

## 常见问题

### Q1: TCP连接经常断开

**原因**: 长时间无通信导致超时

**解决**: 
- 定期发送心跳命令
- 增加 `connection_timeout` 配置
- 使用长连接并保持活跃

### Q2: MQTT消息丢失

**原因**: QoS设置过低

**解决**: 使用 QoS 2

### Q3: 检测延迟高

**原因**: 
- 网络延迟
- 相机取图慢
- 模型推理慢

**解决**:
- 使用千兆网络
- 启用C++后端
- 使用GPU加速（PC）或NPU加速（RK3588）

---

<div align="center">

**VisionCore Enterprise Edition**  
*专业工业视觉检测系统*

下一步: 阅读 [标定操作手册](./标定操作手册.md)

</div>

