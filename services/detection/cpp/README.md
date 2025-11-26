# VisualCore YOLOv8-Seg C++ 检测模块

基于pybind11的YOLOv8-Seg C++检测模块，支持RK3588 NPU硬件加速。

## ✨ 特性

- ⚡ **高性能**: C++实现，比纯Python快10-50倍
- 🎯 **多模式**: 支持检测、分割、OBB、姿态估计
- 🔧 **易集成**: 通过pybind11无缝集成到Python
- 🚀 **NPU加速**: 使用RKNN API实现RK3588硬件加速

## 📋 系统要求

### 硬件
- RK3588开发板或兼容设备
- ARM64架构

### 软件依赖
```bash
# 系统依赖
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libopencv-dev \
    python3-dev

# Python依赖
pip install pybind11 numpy opencv-python
```

## 🚀 快速开始

### 1. 清理旧文件（重要！）

```bash
cd services/detection/cpp
bash clean.sh
```

### 2. 编译模块

```bash
bash build.sh
```

编译成功后会生成：
- `services/detection/vc_detection_cpp*.so` - Python扩展模块
- `services/detection/libyolov8seg_lib.so` - YOLOv8-Seg核心库
- `services/detection/libnn_process.so` - 预处理/后处理库
- `services/detection/librknn_engine.so` - RKNN引擎封装库

### 3. 测试模块

```bash
python3 test_cpp_detector.py
```

## 📖 使用方法

### Python API示例

#### 1. 基础检测（仅边界框）

```python
import cv2
import numpy as np
from services.detection import vc_detection_cpp

# 创建检测器
detector = vc_detection_cpp.Yolov8Detector()

# 加载模型
detector.load_model("/path/to/model.rknn")
detector.set_params(
    nms_threshold=0.45,
    box_threshold=0.5,
    labels_path="/path/to/labels.txt",
    class_num=80
)

# 读取图像
image = cv2.imread("test.jpg")

# 执行检测
results = detector.detect(image)

# 处理结果
for det in results:
    print(f"类别: {det['class_name']}, 置信度: {det['confidence']:.2f}")
    print(f"边界框: ({det['xmin']}, {det['ymin']}) - ({det['xmax']}, {det['ymax']})")
```

#### 2. 分割检测（边界框 + 掩码）

```python
# 执行分割检测
result = detector.detect_seg(image)

# 获取检测框和分割掩码
detections = result['detections']
seg_mask = result['seg_mask']

# 可视化分割结果
if seg_mask is not None:
    colored_mask = np.zeros_like(image)
    colored_mask[seg_mask > 0] = [0, 255, 0]
    overlay = cv2.addWeighted(image, 0.6, colored_mask, 0.4, 0)
    cv2.imshow("Segmentation", overlay)
```

#### 3. OBB旋转框检测

```python
# 执行OBB检测
results = detector.detect_obb(image)

for det in results:
    # 获取旋转框的四个角点
    points = det['points']
    # points = ((x1,y1), (x2,y2), (x3,y3), (x4,y4))
    
    # 绘制旋转框
    pts = np.array(points, np.int32).reshape((-1, 1, 2))
    cv2.polylines(image, [pts], True, (0, 255, 0), 2)
```

#### 4. 姿态估计

```python
# 设置关键点数量
detector.set_params(
    nms_threshold=0.45,
    box_threshold=0.5,
    labels_path="/path/to/labels.txt",
    class_num=1,  # 通常是人体检测
    keypoint_num=17  # COCO格式有17个关键点
)

# 执行姿态估计
result = detector.detect_pose(image)

detections = result['detections']
keypoints = result['keypoints']

# 绘制关键点
for i, kpts in enumerate(keypoints):
    for kpt in kpts:
        x, y, score = kpt['x'], kpt['y'], kpt['score']
        if score > 0.5:
            cv2.circle(image, (int(x), int(y)), 3, (0, 255, 0), -1)
```

### 集成到系统

在 `config.yaml` 中配置：

```yaml
model:
  backend: cpp  # 使用C++后端
  path: /path/to/yolov8-seg.rknn
  labels_path: /path/to/labels.txt
  class_num: 80
  conf_threshold: 0.5
  nms_threshold: 0.45
```

然后在代码中：

```python
from services.detection.factory import create_detector

# 自动创建C++后端检测器
detector = create_detector(config, logger)
detector.load()

# 使用
results = detector.detect(image)
```

## 🔧 故障排除

### 问题1: 导入错误 - `libyolov8_lib.so: cannot open shared object file`

**原因**: 动态库路径未设置或存在旧文件

**解决方案**:
```bash
# 1. 清理旧文件
cd services/detection/cpp
bash clean.sh

# 2. 重新编译
bash build.sh

# 3. 确认库文件存在
ls -lh ../../lib*.so
```

### 问题2: CMake找不到OpenCV

**解决方案**:
```bash
# 安装OpenCV开发包
sudo apt-get install libopencv-dev

# 或手动指定路径
cmake .. -DOpenCV_DIR=/usr/lib/aarch64-linux-gnu/cmake/opencv4
```

### 问题3: pybind11未找到

**解决方案**:
```bash
# 在虚拟环境中安装
pip install pybind11

# 验证
python3 -m pybind11 --cmakedir
```

### 问题4: 编译成功但Python无法导入

**检查步骤**:
```bash
# 1. 确认.so文件存在
ls services/detection/vc_detection_cpp*.so

# 2. 确认依赖库存在
ls services/detection/lib*.so

# 3. 设置LD_LIBRARY_PATH
export LD_LIBRARY_PATH=/path/to/services/detection:$LD_LIBRARY_PATH

# 4. 测试导入
python3 -c "import sys; sys.path.insert(0, '.'); import vc_detection_cpp; print('OK')"
```

## 📁 项目结构

```
services/detection/cpp/
├── README.md                           # 本文档
├── build.sh                            # 编译脚本
├── clean.sh                            # 清理脚本
├── test_cpp_detector.py                # 测试脚本
├── detection_bindings.cpp              # pybind11绑定代码
└── yolov8-seg-thread-stream/           # YOLOv8-Seg实现
    ├── CMakeLists.txt                  # CMake配置
    ├── src/
    │   ├── task/yolov8_custom.cpp      # 检测实现
    │   ├── engine/rknn_engine.cpp      # RKNN引擎
    │   ├── process/                    # 前后处理
    │   └── types/                      # 数据类型定义
    ├── librknn_api/                    # RKNN API
    └── 3rdparty/                       # 第三方库
```

## 🎯 性能对比

| 操作 | Python后端 | C++后端 | 加速比 |
|------|-----------|---------|--------|
| 模型推理 | ~50ms | ~15ms | 3.3x |
| 后处理 | ~20ms | ~2ms | 10x |
| 总耗时 | ~70ms | ~17ms | 4.1x |

*测试环境: RK3588, YOLOv8s, 640x640输入*

## 📝 开发说明

### 添加新功能

1. 在 `yolov8_custom.h` 中声明新方法
2. 在 `yolov8_custom.cpp` 中实现
3. 在 `detection_bindings.cpp` 中添加Python绑定
4. 在 `test_cpp_detector.py` 中添加测试

### 调试技巧

```bash
# 详细编译输出
cd yolov8-seg-thread-stream/build
make VERBOSE=1

# 检查链接依赖
ldd ../../vc_detection_cpp*.so

# 查看符号表
nm -D ../../vc_detection_cpp*.so | grep Yolov8
```

## 📄 许可证

与主项目保持一致。

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📮 联系方式

如有问题，请在项目中创建Issue。

