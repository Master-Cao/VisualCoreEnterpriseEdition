# 坐标标定工作流程

## 概述

坐标标定采用**两步工作流**，分离了"获取坐标"和"执行标定"两个阶段，便于用户交互。

---

## 工作流程图

```
┌──────────────────────────────────────────────────────────────┐
│                     坐标标定完整流程                          │
└──────────────────────────────────────────────────────────────┘

第1步: 获取世界坐标
─────────────────────
客户端发送:
  {"command": "get_calibrat_image"}
         │
         ├──> VisionCore检测黑块
         ├──> 计算世界坐标(xw, yw, zw)
         └──> 返回12个点的坐标信息

客户端收到:
  {
    "blocks_detected": 12,
    "valid_points": 12,
    "points": [
      {"index": 1, "world_x": 234.5, "world_y": -123.4, "world_z": 678.9},
      {"index": 2, "world_x": 245.1, "world_y": -98.7, "world_z": 679.2},
      ...
    ]
  }

                    ↓

用户操作：
─────────
1. 查看12个点的世界坐标
2. 使用机器人示教器逐点移动
3. 记录每个点的机器人TCP坐标(xr, yr, zr)
4. 在客户端界面填写机器人坐标

                    ↓

第2步: 执行标定计算
─────────────────────
客户端发送:
  {
    "command": "coordinate_calibration",
    "world_points": [
      {"x": 234.5, "y": -123.4, "z": 678.9},
      {"x": 245.1, "y": -98.7, "z": 679.2},
      ...
    ],
    "robot_points": [
      {"x": 237.96, "y": -286.302, "z": -80.0},
      {"x": 273.822, "y": -179.879, "z": -70.0},
      ...
    ]
  }
         │
         ├──> 执行XY仿射拟合
         ├──> 执行Z线性拟合
         ├──> 合成4x4变换矩阵
         ├──> 保存到 configs/transformation_matrix.json
         └──> 返回标定结果

客户端收到:
  {
    "success": true,
    "calibration_points": 12,
    "rmse_x": 2.345,
    "rmse_y": 1.876,
    "rmse_z": 3.456,
    "quality": "excellent",
    "matrix": [[...], [...], [...], [...]]
  }
```

---

## 命令详解

### 第1步: `get_calibrat_image`

**功能**: 检测黑色标记块并返回世界坐标

#### 请求格式

```json
{
  "command": "get_calibrat_image"
}
```

#### 成功响应

```json
{
  "command": "get_calibrat_image",
  "component": "calibrator",
  "messageType": "success",
  "message": "ok",
  "data": {
    "blocks_detected": 12,
    "valid_points": 12,
    "points": [
      {
        "index": 1,
        "pixel_u": 123,
        "pixel_v": 89,
        "valid": true,
        "world_x": 234.567,
        "world_y": -123.456,
        "world_z": 678.901
      },
      {
        "index": 2,
        "pixel_u": 156,
        "pixel_v": 92,
        "valid": true,
        "world_x": 245.123,
        "world_y": -98.765,
        "world_z": 679.234
      }
      // ... 其他10个点
    ],
    "note": "请使用机器人示教器移动到每个点位，记录坐标后发送coordinate_calibration命令",
    "image_remote": {
      "filename": "calib_20251110_153045_123.jpg",
      "remote_path": "/images/",
      "file_size": 123456
    }
  }
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `blocks_detected` | int | 检测到的黑块总数 |
| `valid_points` | int | 有效点数（能计算世界坐标的） |
| `points` | array | 点位列表 |
| `points[].index` | int | 点序号（1-12） |
| `points[].pixel_u` | int | 像素横坐标 |
| `points[].pixel_v` | int | 像素纵坐标 |
| `points[].valid` | bool | 是否有效 |
| `points[].world_x` | float | 世界坐标X（mm） |
| `points[].world_y` | float | 世界坐标Y（mm） |
| `points[].world_z` | float | 世界坐标Z（mm） |
| `image_remote` | object | SFTP上传的标注图像信息（可选） |

#### 错误响应

```json
{
  "command": "get_calibrat_image",
  "component": "detector",
  "messageType": "error",
  "message": "no_blocks_detected",
  "data": {
    "hint": "请确保有黑色方形标记块在相机视野内"
  }
}
```

**常见错误**:
- `camera_not_ready`: 相机未就绪
- `camera_capture_failed`: 相机采集失败
- `no_blocks_detected`: 未检测到黑块
- `insufficient_valid_points`: 有效点不足（需至少3个）

---

### 第2步: `coordinate_calibration`

**功能**: 接收坐标对并执行标定计算

#### 请求格式

```json
{
  "command": "coordinate_calibration",
  "world_points": [
    {"x": 234.567, "y": -123.456, "z": 678.901},
    {"x": 245.123, "y": -98.765, "z": 679.234},
    {"x": 256.789, "y": -74.321, "z": 680.567},
    // ... 其他点（至少3个）
  ],
  "robot_points": [
    {"x": 237.96, "y": -286.302, "z": -80.0},
    {"x": 273.822, "y": -179.879, "z": -70.0},
    {"x": 244.257, "y": -86.047, "z": -60.0},
    // ... 对应的机器人坐标
  ]
}
```

#### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `world_points` | array | 是 | 世界坐标列表（从get_calibrat_image获取） |
| `world_points[].x` | float | 是 | 世界坐标X（mm） |
| `world_points[].y` | float | 是 | 世界坐标Y（mm） |
| `world_points[].z` | float | 是 | 世界坐标Z（mm） |
| `robot_points` | array | 是 | 机器人坐标列表（用户示教） |
| `robot_points[].x` | float | 是 | 机器人坐标X（mm） |
| `robot_points[].y` | float | 是 | 机器人坐标Y（mm） |
| `robot_points[].z` | float | 是 | 机器人坐标Z（mm） |

**注意**:
- `world_points` 和 `robot_points` 数量必须相同
- 至少需要3组有效的坐标对
- 推荐使用12组以获得最佳精度

#### 成功响应

```json
{
  "command": "coordinate_calibration",
  "component": "calibrator",
  "messageType": "success",
  "message": "calibration_completed",
  "data": {
    "success": true,
    "calibration_points": 12,
    "rmse_x": 2.345,
    "rmse_y": 1.876,
    "rmse_z": 3.456,
    "rmse_2d": 2.987,
    "quality": "excellent",
    "matrix": [
      [1.002, -0.003, 0.0, -123.456],
      [0.002, 0.998, 0.0, 234.567],
      [0.0, 0.0, -0.985, 650.123],
      [0.0, 0.0, 0.0, 1.0]
    ],
    "matrix_file": "configs/transformation_matrix.json",
    "timestamp": "2025-11-10T15:30:45.123456"
  }
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 标定是否成功 |
| `calibration_points` | int | 使用的标定点数 |
| `rmse_x` | float | X轴均方根误差（mm） |
| `rmse_y` | float | Y轴均方根误差（mm） |
| `rmse_z` | float | Z轴均方根误差（mm） |
| `rmse_2d` | float | XY平面综合误差（mm） |
| `quality` | string | 质量评级（excellent/good/acceptable/poor） |
| `matrix` | array | 4x4变换矩阵 |
| `matrix_file` | string | 保存的文件路径 |
| `timestamp` | string | 标定时间戳 |

#### 质量评级标准

| 等级 | 条件 | 说明 |
|------|------|------|
| **excellent** | XY < 3mm 且 Z < 5mm | 优秀，可直接使用 |
| **good** | XY < 5mm 且 Z < 10mm | 良好，适合生产 |
| **acceptable** | XY < 10mm 且 Z < 20mm | 可接受，建议优化 |
| **poor** | XY ≥ 10mm 或 Z ≥ 20mm | 较差，需重新标定 |

#### 错误响应

```json
{
  "command": "coordinate_calibration",
  "component": "calibrator",
  "messageType": "error",
  "message": "missing_robot_points",
  "data": {
    "hint": "payload中必须包含robot_points字段"
  }
}
```

**常见错误**:
- `missing_robot_points`: 缺少机器人坐标
- `missing_world_points`: 缺少世界坐标
- `insufficient_valid_pairs`: 有效坐标对不足（需至少3组）
- `calibration_calculation_failed`: 标定计算失败

---

## 客户端实现示例

### Python示例

```python
import paho.mqtt.client as mqtt
import json
import time

class CalibrationClient:
    def __init__(self, broker_host="192.168.2.126", broker_port=1883):
        self.client = mqtt.Client()
        self.client.on_message = self.on_message
        self.client.connect(broker_host, broker_port)
        self.client.subscribe("PI/robot/message")
        self.client.loop_start()
        self.response = None
        self.world_points = []
    
    def on_message(self, client, userdata, msg):
        self.response = json.loads(msg.payload.decode())
        print(f"\n📨 收到响应:")
        print(json.dumps(self.response, indent=2, ensure_ascii=False))
    
    def send_command(self, command, data=None):
        payload = {"command": command}
        if data:
            payload.update(data)
        self.client.publish("sickvision/system/command", json.dumps(payload))
        print(f"\n📤 发送命令: {command}")
    
    def wait_for_response(self, timeout=10):
        """等待响应"""
        start = time.time()
        while self.response is None and (time.time() - start) < timeout:
            time.sleep(0.1)
        return self.response
    
    def step1_get_world_coords(self):
        """第1步: 获取世界坐标"""
        print("\n" + "="*60)
        print("第1步: 检测黑块并获取世界坐标")
        print("="*60)
        
        self.response = None
        self.send_command("get_calibrat_image")
        
        resp = self.wait_for_response()
        if resp and resp.get('messageType') == 'success':
            points = resp['data'].get('points', [])
            valid_points = [p for p in points if p.get('valid')]
            
            print(f"\n✅ 检测成功!")
            print(f"检测到 {len(points)} 个黑块，其中 {len(valid_points)} 个有效")
            print("\n世界坐标列表:")
            print("-" * 60)
            
            for p in valid_points:
                print(f"  [{p['index']:2d}] 世界坐标: "
                      f"X={p['world_x']:8.2f}, Y={p['world_y']:8.2f}, Z={p['world_z']:8.2f}")
            
            # 保存世界坐标供第2步使用
            self.world_points = [
                {"x": p['world_x'], "y": p['world_y'], "z": p['world_z']}
                for p in valid_points
            ]
            
            return True
        else:
            print(f"\n❌ 获取世界坐标失败")
            return False
    
    def step2_calibrate(self, robot_coords):
        """第2步: 执行标定"""
        print("\n" + "="*60)
        print("第2步: 执行标定计算")
        print("="*60)
        
        # 构造robot_points
        robot_points = [
            {"x": r[0], "y": r[1], "z": r[2]}
            for r in robot_coords
        ]
        
        self.response = None
        self.send_command("coordinate_calibration", {
            "world_points": self.world_points,
            "robot_points": robot_points
        })
        
        resp = self.wait_for_response()
        if resp and resp.get('messageType') == 'success':
            data = resp['data']
            print(f"\n✅ 标定成功!")
            print(f"  标定点数: {data['calibration_points']}")
            print(f"  XY误差: X={data['rmse_x']:.2f}mm, Y={data['rmse_y']:.2f}mm")
            print(f"  Z误差: {data['rmse_z']:.2f}mm")
            print(f"  2D综合误差: {data['rmse_2d']:.2f}mm")
            print(f"  质量评级: {data['quality']}")
            print(f"  矩阵文件: {data['matrix_file']}")
            return True
        else:
            print(f"\n❌ 标定失败")
            return False


# 使用示例
if __name__ == "__main__":
    client = CalibrationClient()
    
    # 第1步: 获取世界坐标
    if client.step1_get_world_coords():
        print("\n" + "="*60)
        print("⚠️  请使用机器人示教器完成以下操作:")
        print("="*60)
        print("1. 依次移动机器人TCP到上述每个点位")
        print("2. 记录每个点的机器人坐标(xr, yr, zr)")
        print("3. 填入下方 robot_coords 列表")
        print("4. 运行第2步进行标定\n")
        
        # 等待用户填写机器人坐标
        input("按回车继续...")
        
        # 第2步: 用户填写的机器人坐标
        robot_coords = [
            (237.96, -286.302, -80.0),     # 点1
            (273.822, -179.879, -70.0),    # 点2
            (244.257, -86.047, -60.0),     # 点3
            (246.192, -27.904, -51.0),     # 点4
            (326.734, -243.453, -40.0),    # 点5
            (330.738, -182.645, -40.0),    # 点6
            (306.965, -89.572, -40.0),     # 点7
            (311.254, -10.232, -40.0),     # 点8
            (413.145, -275.568, -40.0),    # 点9
            (417.033, -216.46, -40.0),     # 点10
            (421.3, -95.94, -40.0),        # 点11
            (391.739, -5.352, -40.0)       # 点12
        ]
        
        # 执行标定
        client.step2_calibrate(robot_coords)
```

### JavaScript/TypeScript示例

```typescript
import mqtt from 'mqtt';

interface Point3D {
  x: number;
  y: number;
  z: number;
}

class CalibrationClient {
  private client: mqtt.MqttClient;
  private worldPoints: Point3D[] = [];

  constructor(brokerUrl: string = 'mqtt://192.168.2.126:1883') {
    this.client = mqtt.connect(brokerUrl);
    
    this.client.on('connect', () => {
      console.log('✅ 已连接到MQTT');
      this.client.subscribe('PI/robot/message');
    });
    
    this.client.on('message', (topic, payload) => {
      const response = JSON.parse(payload.toString());
      console.log('📨 收到响应:', JSON.stringify(response, null, 2));
    });
  }

  async step1GetWorldCoords(): Promise<Point3D[]> {
    return new Promise((resolve, reject) => {
      console.log('\n第1步: 获取世界坐标...');
      
      this.client.publish('sickvision/system/command', 
        JSON.stringify({ command: 'get_calibrat_image' })
      );
      
      const handler = (topic: string, payload: Buffer) => {
        const response = JSON.parse(payload.toString());
        if (response.command === 'get_calibrat_image') {
          this.client.off('message', handler);
          
          if (response.messageType === 'success') {
            const points = response.data.points
              .filter((p: any) => p.valid)
              .map((p: any) => ({
                x: p.world_x,
                y: p.world_y,
                z: p.world_z
              }));
            
            this.worldPoints = points;
            console.log(`✅ 获取到 ${points.length} 个世界坐标`);
            resolve(points);
          } else {
            reject(new Error(response.message));
          }
        }
      };
      
      this.client.on('message', handler);
    });
  }

  async step2Calibrate(robotPoints: Point3D[]): Promise<boolean> {
    return new Promise((resolve, reject) => {
      console.log('\n第2步: 执行标定...');
      
      this.client.publish('sickvision/system/command',
        JSON.stringify({
          command: 'coordinate_calibration',
          world_points: this.worldPoints,
          robot_points: robotPoints
        })
      );
      
      const handler = (topic: string, payload: Buffer) => {
        const response = JSON.parse(payload.toString());
        if (response.command === 'coordinate_calibration') {
          this.client.off('message', handler);
          
          if (response.messageType === 'success') {
            console.log('✅ 标定成功!');
            console.log(`  质量: ${response.data.quality}`);
            console.log(`  RMSE: ${response.data.rmse_2d}mm`);
            resolve(true);
          } else {
            reject(new Error(response.message));
          }
        }
      };
      
      this.client.on('message', handler);
    });
  }
}

// 使用
const client = new CalibrationClient();
await client.step1GetWorldCoords();
// 用户填写机器人坐标...
await client.step2Calibrate(robotPoints);
```

---

## 注意事项

### 1. 坐标对应关系

**关键**: `world_points` 和 `robot_points` 的**顺序必须一一对应**！

```
world_points[0] ←→ robot_points[0]
world_points[1] ←→ robot_points[1]
world_points[2] ←→ robot_points[2]
...
```

### 2. 最少点数

- **最少**: 3组对应点
- **推荐**: 12组对应点（3×4网格）
- **更多点 = 更高精度**

### 3. 点位分布

- 均匀覆盖工作区域
- 避免集中在一小块区域
- 网格状分布最佳

### 4. 示教精度

- 机器人示教位置要准确
- TCP必须对准黑块中心
- 记录时避免抖动

### 5. 数据保存

建议客户端保存每次标定的原始数据：

```json
{
  "timestamp": "2025-11-10T15:30:45",
  "world_points": [...],
  "robot_points": [...],
  "result": {
    "rmse_2d": 2.987,
    "quality": "excellent"
  }
}
```

---

## 故障排除

### Q1: 检测不到黑块

**原因**:
- 黑块对比度不足
- 黑块太小或太大
- 光照不均匀

**解决**:
- 使用哑光黑色材料
- 调整黑块尺寸（推荐20mm×20mm）
- 改善光照

### Q2: 标定精度差

**原因**:
- 坐标对应关系错误
- 示教不准确
- 点数太少

**解决**:
- 检查坐标顺序是否一致
- 重新仔细示教
- 增加标定点到12个

### Q3: 缺少有效点

**原因**:
- 深度数据缺失
- 黑块超出视野

**解决**:
- 调整黑块位置到相机视野内
- 检查深度图质量

---

## 变换矩阵文件

标定成功后，变换矩阵保存在: `configs/transformation_matrix.json`

```json
{
  "matrix": [
    [1.002, -0.003, 0.0, -123.456],
    [0.002, 0.998, 0.0, 234.567],
    [0.0, 0.0, -0.985, 650.123],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "matrix_xy": [
    [1.002, -0.003, -123.456],
    [0.002, 0.998, 234.567]
  ],
  "z_mapping": {
    "alpha": -0.985,
    "beta": 650.123
  },
  "calibration_datetime": "2025-11-10T15:30:45.123456",
  "transformation_type": "affine_xy_linear_z",
  "calibration_points_count": 12,
  "xy_rmse_x": 2.345,
  "xy_rmse_y": 1.876,
  "z_rmse": 3.456,
  "overall_rmse_2d": 2.987
}
```

---

## 总结

**两步工作流的优势**:

1. ✅ **交互友好**: 用户可查看世界坐标后再示教
2. ✅ **灵活性高**: 可以多次尝试不同的机器人坐标
3. ✅ **易于调试**: 分步执行，便于定位问题
4. ✅ **数据可追溯**: 世界坐标和机器人坐标分离保存

**工作流总结**:
```
get_calibrat_image → 返回世界坐标 → 用户示教 → coordinate_calibration → 标定完成
```

