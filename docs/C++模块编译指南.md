# VisionCore Enterprise Edition - C++模块编译指南

> **版本**: v1.3.0  
> **更新日期**: 2025-11-26  
> **难度**: ⭐⭐⭐⭐☆（高级）

---

## 📋 目录

- [概述](#概述)
- [前置要求](#前置要求)
- [Windows平台编译](#windows平台编译)
- [Linux平台编译](#linux平台编译)
- [RK3588平台编译](#rk3588平台编译)
- [CMake配置选项](#cmake配置选项)
- [编译产物说明](#编译产物说明)
- [测试验证](#测试验证)
- [常见问题](#常见问题)
- [开发者指南](#开发者指南)

---

## 概述

### 什么是C++模块？

VisionCore的C++模块是使用C++实现的高性能组件，通过pybind11绑定为Python扩展模块。

### 模块列表

| 模块 | 文件名 | 功能 | 性能提升 |
|------|--------|------|---------|
| **相机模块** | `vc_camera_cpp.pyd/.so` | SICK 3D相机接口 | 取图速度提升50%+ |
| **检测模块** | `vc_detection_cpp.pyd/.so` | RKNN推理后端 | 推理速度提升30%+ |

### 为什么需要C++模块？

**优势**:
- ✅ **性能更高**: C++直接调用底层API，避免Python解释器开销
- ✅ **内存效率**: 更好的内存管理，减少拷贝
- ✅ **多线程**: 真正的并行处理，不受GIL限制

**劣势**:
- ❌ **编译复杂**: 需要C++编译环境
- ❌ **平台相关**: 需要为每个平台单独编译
- ❌ **调试困难**: C++调试比Python复杂

### 是否必须编译？

**不是必须的**。系统会自动回退：

```
尝试导入C++模块 → 失败 → 自动使用Python实现
```

但**强烈推荐**在以下场景编译：
- RK3588平台（NPU推理性能提升明显）
- 对性能有高要求的场景
- 生产环境部署

---

## 前置要求

### 通用要求

| 软件 | 版本 | 说明 |
|------|------|------|
| **CMake** | ≥ 3.16 | 构建系统 |
| **Python** | 3.8-3.10 | 与运行环境一致 |
| **pybind11** | ≥ 2.6 | Python-C++绑定库 |
| **C++编译器** | 支持C++17 | GCC/Clang/MSVC |

### Windows平台

**编译器选择**（二选一）：

#### 选项A: Visual Studio（推荐）

```powershell
# 1. 下载Visual Studio 2019或2022
# https://visualstudio.microsoft.com/

# 2. 安装时选择工作负载:
#    ✅ Desktop development with C++

# 3. 验证安装
cl
# 应该显示: Microsoft (R) C/C++ Optimizing Compiler
```

#### 选项B: MinGW-w64

```powershell
# 1. 安装MSYS2
# https://www.msys2.org/

# 2. 在MSYS2终端中安装MinGW
pacman -S mingw-w64-x86_64-gcc mingw-w64-x86_64-cmake

# 3. 添加到PATH
# C:\msys64\mingw64\bin
```

**其他依赖**:

```powershell
# CMake
# 下载: https://cmake.org/download/
# 安装时勾选: Add CMake to system PATH

# pybind11
pip install pybind11
```

### Linux平台

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y \
    build-essential \
    cmake \
    python3-dev \
    python3-pybind11

# CentOS/RHEL
sudo yum install -y \
    gcc gcc-c++ \
    cmake3 \
    python3-devel

pip3 install pybind11

# 验证安装
gcc --version    # 应该 ≥ 7.0
cmake --version  # 应该 ≥ 3.16
python3 --version
```

### RK3588平台

```bash
# 1. 基础工具
sudo apt install -y \
    build-essential \
    cmake \
    python3-dev

# 2. RKNN SDK（必须）
# 确保以下文件存在:
ls /usr/lib/librknn_api.so
ls /usr/include/rknn_api.h

# 如果不存在，从Rockchip官网下载RKNN SDK
# https://github.com/rockchip-linux/rknn-toolkit2

# 3. pybind11
pip3 install pybind11

# 4. OpenCV（可选）
sudo apt install -y libopencv-dev
```

---

## Windows平台编译

### 快速开始（推荐）

#### 方法1: 使用批处理脚本

```cmd
# 1. 打开"Developer Command Prompt for VS 2019/2022"
#    （开始菜单 → Visual Studio → Developer Command Prompt）

# 2. 进入cpp目录
cd C:\...\VisualCoreEnterpriseEdition\services\cpp

# 3. 一键编译
build.bat

# 4. 查看产物
dir dist\Release\
# 应该看到:
# vc_camera_cpp.pyd
# vc_detection_cpp.pyd
```

#### 方法2: 使用PowerShell脚本

```powershell
# 1. 启用脚本执行（首次需要，以管理员运行PowerShell）
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 2. 进入cpp目录
cd C:\...\VisualCoreEnterpriseEdition\services\cpp

# 3. 执行编译
.\build.ps1

# 或指定选项
.\build.ps1 -Clean          # 清理后编译
.\build.ps1 -Debug          # Debug模式
.\build.ps1 -CameraOnly     # 只编译相机模块
.\build.ps1 -Jobs 8         # 使用8个并行任务
```

### 手动编译（详细步骤）

#### 步骤1: 配置CMake

```cmd
# 1. 创建构建目录
cd services\cpp
mkdir build
cd build

# 2. 配置CMake（Visual Studio）
cmake .. -G "Visual Studio 16 2019" -A x64

# 或配置为MinGW
cmake .. -G "MinGW Makefiles"

# 3. 查看配置输出
# 应该显示:
# -- Configuring Camera Module...
# -- Camera Module configured.
# -- Configuring Detection Module...
# -- Detection Module configured.
```

#### 步骤2: 编译

```cmd
# Release模式（推荐）
cmake --build . --config Release

# Debug模式（用于调试）
cmake --build . --config Debug

# 使用多线程编译（更快）
cmake --build . --config Release -j 8
```

#### 步骤3: 安装

```cmd
# 复制编译产物到目标位置
cmake --install . --config Release

# 或手动复制
copy Release\vc_camera_cpp.pyd ..\..\camera\
copy Release\vc_detection_cpp.pyd ..\..\detection\
```

### 高级选项

```cmd
# 只编译相机模块
cmake .. -DBUILD_DETECTION_MODULE=OFF

# 只编译检测模块
cmake .. -DBUILD_CAMERA_MODULE=OFF

# 指定Python解释器
cmake .. -DPYTHON_EXECUTABLE=C:\Python39\python.exe

# 指定安装路径
cmake .. -DCMAKE_INSTALL_PREFIX=C:\MyProject\modules
```

---

## Linux平台编译

### 快速开始

```bash
# 1. 进入cpp目录
cd services/cpp

# 2. 一键编译
chmod +x build.sh
./build.sh

# 3. 查看产物
ls -l dist/
# 应该看到:
# vc_camera_cpp.so
# vc_detection_cpp.so
```

### 手动编译

```bash
# 1. 创建构建目录
cd services/cpp
mkdir build
cd build

# 2. 配置CMake
cmake ..

# 3. 编译
make -j$(nproc)

# 4. 安装
make install

# 或手动复制
cp vc_camera_cpp.so ../../camera/
cp vc_detection_cpp.so ../../detection/
```

### 指定Python版本

```bash
# 使用Python 3.9
cmake .. -DPYTHON_EXECUTABLE=/usr/bin/python3.9

# 或使用虚拟环境中的Python
cmake .. -DPYTHON_EXECUTABLE=/path/to/venv/bin/python3
```

### 编译选项

```bash
# Debug模式
cmake .. -DCMAKE_BUILD_TYPE=Debug

# Release模式（默认）
cmake .. -DCMAKE_BUILD_TYPE=Release

# 只编译相机模块
cmake .. -DBUILD_DETECTION_MODULE=OFF

# 启用详细输出
cmake .. --trace
make VERBOSE=1
```

---

## RK3588平台编译

### 前置检查

```bash
# 1. 验证RKNN SDK
ls /usr/lib/librknn_api.so
ls /usr/include/rknn_api.h

# 如果缺失，安装RKNN SDK
sudo dpkg -i rknn-toolkit2_*.deb

# 2. 验证编译环境
gcc --version     # 应该 ≥ 7.0
cmake --version   # 应该 ≥ 3.16
```

### 编译步骤

```bash
# 1. 进入cpp目录
cd services/cpp

# 2. 清理旧构建（如果存在）
rm -rf build dist

# 3. 创建构建目录
mkdir build
cd build

# 4. 配置CMake
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DPYTHON_EXECUTABLE=$(which python3)

# 5. 编译（使用所有CPU核心）
make -j$(nproc)

# 6. 检查产物
ls ../dist/
# 应该看到:
# vc_camera_cpp.so
# vc_detection_cpp.so

# 7. 安装
make install

# 或手动复制
cp ../dist/vc_camera_cpp.so ../../camera/
cp ../dist/vc_detection_cpp.so ../../detection/
```

### RK3588特殊注意事项

1. **RKNN API版本**: 确保RKNN SDK版本与模型兼容
```bash
# 查看RKNN版本
cat /usr/lib/librknn_api.so | strings | grep "RKNN"
```

2. **NPU权限**: 确保用户有权限访问NPU设备
```bash
ls -l /dev/rknpu*
# 如果权限不足:
sudo chmod 666 /dev/rknpu*
```

3. **内存限制**: RK3588内存有限，建议Release模式编译
```bash
cmake .. -DCMAKE_BUILD_TYPE=Release
```

---

## CMake配置选项

### 基本选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `BUILD_CAMERA_MODULE` | ON | 是否编译相机模块 |
| `BUILD_DETECTION_MODULE` | ON | 是否编译检测模块 |
| `CMAKE_BUILD_TYPE` | Release | 构建类型（Release/Debug） |
| `PYTHON_EXECUTABLE` | 自动检测 | Python解释器路径 |

### 使用示例

```bash
# 只编译相机模块，Debug模式
cmake .. \
    -DBUILD_DETECTION_MODULE=OFF \
    -DCMAKE_BUILD_TYPE=Debug

# 指定Python，只编译检测模块
cmake .. \
    -DBUILD_CAMERA_MODULE=OFF \
    -DPYTHON_EXECUTABLE=/usr/bin/python3.9

# 完整配置示例
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_CAMERA_MODULE=ON \
    -DBUILD_DETECTION_MODULE=ON \
    -DPYTHON_EXECUTABLE=/usr/bin/python3 \
    -DCMAKE_INSTALL_PREFIX=/opt/visioncore
```

---

## 编译产物说明

### 文件命名

| 平台 | 相机模块 | 检测模块 |
|------|---------|---------|
| **Windows** | `vc_camera_cpp.pyd` | `vc_detection_cpp.pyd` |
| **Linux** | `vc_camera_cpp.so` | `vc_detection_cpp.so` |
| **RK3588** | `vc_camera_cpp.so` | `vc_detection_cpp.so` |

### 文件位置

```
services/cpp/
├── dist/                           # 编译产物目录
│   ├── Release/                    # Release版本
│   │   ├── vc_camera_cpp.pyd
│   │   └── vc_detection_cpp.pyd
│   └── Debug/                      # Debug版本
│       ├── vc_camera_cpp.pyd
│       └── vc_detection_cpp.pyd
│
├── camera/                         # 安装目标（推荐）
│   └── vc_camera_cpp.pyd
│
└── detection/                      # 安装目标（推荐）
    └── vc_detection_cpp.pyd
```

### 文件大小参考

| 模块 | Windows | Linux | RK3588 |
|------|---------|-------|--------|
| **相机模块** | ~500KB | ~400KB | ~400KB |
| **检测模块** | ~200KB | ~150KB | ~150KB |

如果文件大小明显不同，可能是：
- Debug版本（更大，包含调试信息）
- 静态链接vs动态链接
- 编译器优化级别不同

---

## 测试验证

### 验证模块导入

```bash
# 进入项目根目录
cd VisualCoreEnterpriseEdition

# 激活虚拟环境
source venv/bin/activate    # Linux
# 或
venv\Scripts\activate       # Windows

# 测试相机模块
python -c "import vc_camera_cpp; print('✓ 相机模块导入成功')"

# 测试检测模块
python -c "import vc_detection_cpp; print('✓ 检测模块导入成功')"
```

### 运行测试脚本

```bash
# 1. 相机模块测试
cd services/cpp/tests
python test_camera.py

# 预期输出:
# Testing VisionaryCamera...
# ✓ Camera connected
# ✓ Frame captured
# ✓ Frame data valid

# 2. 检测模块测试（RK3588）
python test_detection.py

# 预期输出:
# Testing RKNNDetector...
# ✓ Model loaded
# ✓ Inference successful
# ✓ Results valid
```

### 性能基准测试

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
C++ vs Python性能对比测试
"""
import time
import numpy as np

# 测试相机取图性能
def benchmark_camera():
    print("=== 相机取图性能对比 ===")
    
    # C++版本
    try:
        import vc_camera_cpp
        camera_cpp = vc_camera_cpp.VisionaryCamera("192.168.2.99", 2122, True)
        camera_cpp.connect()
        
        times = []
        for _ in range(100):
            t0 = time.time()
            frame = camera_cpp.get_frame()
            times.append((time.time() - t0) * 1000)
        
        print(f"C++版本: {np.mean(times):.1f}ms (平均)")
        camera_cpp.disconnect()
    except ImportError:
        print("C++模块未安装")
    
    # Python版本
    from services.camera.sick_camera import SickCamera
    camera_py = SickCamera("192.168.2.99", 2122, True, None, None)
    camera_py.connect()
    
    times = []
    for _ in range(100):
        t0 = time.time()
        frame = camera_py.get_frame()
        times.append((time.time() - t0) * 1000)
    
    print(f"Python版本: {np.mean(times):.1f}ms (平均)")
    camera_py.disconnect()

# 测试检测性能（仅RK3588）
def benchmark_detection():
    print("\n=== RKNN推理性能对比 ===")
    
    dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    
    # C++版本
    try:
        from services.detection.cpp_backend import CPPRKNNDetector
        detector_cpp = CPPRKNNDetector("models/test.rknn", 0.5, 0.45, None)
        
        times = []
        for _ in range(100):
            t0 = time.time()
            results = detector_cpp.detect(dummy_image)
            times.append((time.time() - t0) * 1000)
        
        print(f"C++版本: {np.mean(times):.1f}ms (平均)")
    except ImportError:
        print("C++模块未安装")
    
    # Python版本
    from services.detection.rknn_backend import RKNNDetector
    detector_py = RKNNDetector("models/test.rknn", 0.5, 0.45, None)
    
    times = []
    for _ in range(100):
        t0 = time.time()
        results = detector_py.detect(dummy_image)
        times.append((time.time() - t0) * 1000)
    
    print(f"Python版本: {np.mean(times):.1f}ms (平均)")

if __name__ == "__main__":
    benchmark_camera()
    # benchmark_detection()  # 仅在RK3588上运行
```

---

## 常见问题

### Q1: CMake找不到Python

#### 症状
```
CMake Error: Could not find PythonInterp
```

#### 解决方案
```bash
# 方法1: 指定Python路径
cmake .. -DPYTHON_EXECUTABLE=/usr/bin/python3.9

# 方法2: 确保Python在PATH中
which python3    # Linux
where python     # Windows

# 方法3: 创建符号链接（Linux）
sudo ln -s /usr/bin/python3.9 /usr/bin/python3
```

---

### Q2: pybind11找不到

#### 症状
```
CMake Error: Could not find pybind11
```

#### 解决方案
```bash
# 方法1: 安装pybind11
pip install pybind11

# 方法2: 安装系统包
# Ubuntu:
sudo apt install python3-pybind11

# 方法3: 手动指定pybind11路径
cmake .. -Dpybind11_DIR=/path/to/pybind11
```

---

### Q3: SICK SDK头文件找不到

#### 症状
```
fatal error: VisionaryControl.h: No such file or directory
```

#### 解决方案
```bash
# 确认SICK SDK存在
ls infrastructure/sick_visionary_cpp_shared/

# 如果缺失，从项目仓库获取
git submodule update --init --recursive
```

---

### Q4: RKNN API找不到（RK3588）

#### 症状
```
fatal error: rknn_api.h: No such file or directory
```

#### 解决方案
```bash
# 1. 检查RKNN SDK
ls /usr/lib/librknn_api.so
ls /usr/include/rknn_api.h

# 2. 如果缺失，安装RKNN SDK
# 从Rockchip官网下载SDK包
sudo dpkg -i rknn-toolkit2_*.deb

# 3. 或手动指定路径
cmake .. \
    -DRKNN_INCLUDE_DIR=/path/to/rknn/include \
    -DRKNN_LIB_DIR=/path/to/rknn/lib
```

---

### Q5: 编译成功但导入失败

#### 症状
```python
>>> import vc_camera_cpp
ImportError: DLL load failed: The specified module could not be found.
```

#### 原因
缺少依赖库或Python版本不匹配

#### 解决方案

**Windows**:
```powershell
# 1. 检查Python版本
python --version
# 应该与编译时使用的版本一致

# 2. 使用Dependency Walker检查缺失的DLL
# 下载: http://www.dependencywalker.com/
depends.exe vc_camera_cpp.pyd

# 3. 安装Visual C++运行库
# 下载: https://support.microsoft.com/en-us/help/2977003/
```

**Linux**:
```bash
# 1. 检查依赖
ldd vc_camera_cpp.so

# 2. 安装缺失的库
sudo apt install libstdc++6

# 3. 检查Python版本
python3 --version
```

---

### Q6: 编译速度慢

#### 优化方案
```bash
# 1. 使用多线程编译
cmake --build . -j$(nproc)    # Linux
cmake --build . -j 8          # Windows

# 2. 使用ccache加速（Linux）
sudo apt install ccache
cmake .. -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

# 3. 只编译需要的模块
cmake .. -DBUILD_DETECTION_MODULE=OFF
```

---

### Q7: Release和Debug版本冲突

#### 症状
```
ImportError: cannot import name 'VisionaryCamera' from 'vc_camera_cpp'
```

#### 原因
混用了Release和Debug版本

#### 解决方案
```bash
# 1. 清理所有构建产物
cd services/cpp
rm -rf build dist
rm camera/vc_camera_cpp.*
rm detection/vc_detection_cpp.*

# 2. 重新编译（统一使用Release）
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release
cmake --install .
```

---

## 开发者指南

### 源码结构

```
services/cpp/
├── CMakeLists.txt              # 顶层CMake配置
│
├── camera/                     # 相机模块
│   ├── CMakeLists.txt          # 相机模块CMake
│   ├── bindings.cpp            # pybind11绑定代码
│   ├── VisionaryCameraLib.h    # 相机封装头文件
│   └── VisionaryCameraLib.cpp  # 相机封装实现
│
├── detection/                  # 检测模块
│   ├── CMakeLists.txt          # 检测模块CMake
│   ├── bindings.cpp            # pybind11绑定代码
│   ├── DetectorLib.h           # 检测器接口
│   ├── RKNNDetector.h          # RKNN检测器头文件
│   └── RKNNDetector.cpp        # RKNN检测器实现
│
└── tests/                      # 测试脚本
    ├── test_camera.py
    └── test_detection.py
```

### 添加新功能

#### 1. 添加C++函数

**VisionaryCameraLib.h**:
```cpp
class VisionaryCamera {
public:
    // 添加新方法
    bool setExposureTime(int microseconds);
};
```

**VisionaryCameraLib.cpp**:
```cpp
bool VisionaryCamera::setExposureTime(int microseconds) {
    // 实现逻辑
    return true;
}
```

#### 2. 添加Python绑定

**bindings.cpp**:
```cpp
PYBIND11_MODULE(vc_camera_cpp, m) {
    py::class_<VisionaryCamera>(m, "VisionaryCamera")
        // 现有绑定...
        
        // 添加新方法绑定
        .def("set_exposure_time", &VisionaryCamera::setExposureTime,
             py::arg("microseconds"),
             "Set camera exposure time in microseconds");
}
```

#### 3. 重新编译测试

```bash
cd services/cpp/build
cmake --build . --config Release
cmake --install .

# Python测试
python -c "
import vc_camera_cpp
camera = vc_camera_cpp.VisionaryCamera('192.168.2.99', 2122, True)
camera.connect()
camera.set_exposure_time(5000)
print('✓ 新功能测试通过')
"
```

### 调试技巧

#### 1. 启用Debug模式

```bash
cmake .. -DCMAKE_BUILD_TYPE=Debug
cmake --build . --config Debug
```

#### 2. 使用日志

**C++代码中添加日志**:
```cpp
#include <iostream>
#include <fstream>

void log_debug(const std::string& msg) {
    std::ofstream logfile("cpp_debug.log", std::ios::app);
    logfile << msg << std::endl;
}

// 使用
log_debug("Camera connected successfully");
```

#### 3. GDB调试（Linux）

```bash
# 1. 编译Debug版本
cmake .. -DCMAKE_BUILD_TYPE=Debug
make

# 2. 使用GDB调试Python
gdb --args python3 test_camera.py

# GDB命令:
(gdb) break VisionaryCamera::connect
(gdb) run
(gdb) step
(gdb) print variable_name
```

#### 4. Visual Studio调试（Windows）

```powershell
# 1. 生成VS解决方案
cmake .. -G "Visual Studio 16 2019" -A x64

# 2. 打开解决方案
start VisualCoreEnterpriseEdition_CPP.sln

# 3. 在VS中:
#    - 设置断点
#    - 调试 → 附加到进程 → python.exe
#    - 运行Python脚本
```

### 性能优化

#### 1. 编译器优化

```bash
# 启用最高优化级别
cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="-O3 -march=native"

# RK3588专用优化
cmake .. -DCMAKE_CXX_FLAGS="-O3 -march=armv8-a+fp+simd"
```

#### 2. 内存对齐

```cpp
// 使用内存对齐提高性能
alignas(64) float buffer[1024];

// 使用SIMD指令
#include <arm_neon.h>  // ARM
#include <emmintrin.h> // x86
```

#### 3. 减少内存拷贝

```cpp
// ❌ 不好：多次拷贝
py::array_t<float> get_data() {
    std::vector<float> data = process();
    return py::array_t<float>(data.size(), data.data());
}

// ✅ 好：使用移动语义
py::array_t<float> get_data() {
    auto data = new std::vector<float>(process());
    auto capsule = py::capsule(data, [](void *v) { 
        delete reinterpret_cast<std::vector<float>*>(v); 
    });
    return py::array_t<float>(data->size(), data->data(), capsule);
}
```

---

## 附录

### 完整构建脚本示例

#### Windows (build.bat)

```batch
@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Visual Core C++ Module Builder
echo ========================================

REM 检查CMake
where cmake >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake not found
    exit /b 1
)

REM 检查Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found
    exit /b 1
)

REM 创建构建目录
if not exist build mkdir build
cd build

REM 配置CMake
echo [INFO] Configuring CMake...
cmake .. -G "Visual Studio 16 2019" -A x64
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed
    exit /b 1
)

REM 编译
echo [INFO] Building...
cmake --build . --config Release -j %NUMBER_OF_PROCESSORS%
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed
    exit /b 1
)

REM 安装
echo [INFO] Installing...
cmake --install . --config Release

echo [SUCCESS] Build completed successfully!
echo Output: dist\Release\
dir ..\dist\Release\*.pyd

exit /b 0
```

#### Linux (build.sh)

```bash
#!/bin/bash
set -e

echo "========================================"
echo "Visual Core C++ Module Builder"
echo "========================================"

# 检查依赖
command -v cmake >/dev/null 2>&1 || { echo "[ERROR] CMake not found"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "[ERROR] Python3 not found"; exit 1; }

# 创建构建目录
mkdir -p build
cd build

# 配置CMake
echo "[INFO] Configuring CMake..."
cmake .. -DCMAKE_BUILD_TYPE=Release

# 编译
echo "[INFO] Building..."
make -j$(nproc)

# 安装
echo "[INFO] Installing..."
make install

echo "[SUCCESS] Build completed successfully!"
echo "Output: dist/"
ls -lh ../dist/

exit 0
```

### 依赖库下载链接

| 软件 | Windows | Linux | 官网 |
|------|---------|-------|------|
| **CMake** | [下载](https://cmake.org/download/) | `apt install cmake` | cmake.org |
| **Visual Studio** | [下载](https://visualstudio.microsoft.com/) | - | visualstudio.com |
| **Python** | [下载](https://www.python.org/downloads/) | `apt install python3` | python.org |
| **pybind11** | `pip install pybind11` | `apt install python3-pybind11` | pybind11.org |
| **RKNN SDK** | - | [下载](https://github.com/rockchip-linux/rknn-toolkit2) | GitHub |

---

## 总结

### 快速参考

| 平台 | 命令 | 产物 |
|------|------|------|
| **Windows** | `build.bat` | `dist/Release/*.pyd` |
| **Linux** | `./build.sh` | `dist/*.so` |
| **RK3588** | `./build.sh` | `dist/*.so` |

### 推荐工作流

```bash
# 1. 首次编译
cd services/cpp
./build.sh         # Linux/RK3588
# 或
build.bat          # Windows

# 2. 安装到目标位置
cmake --install build --config Release

# 3. 测试验证
python -c "import vc_camera_cpp; print('OK')"

# 4. 运行系统
cd ../..
python -m app.main
```

### 性能对比

| 场景 | Python | C++ | 提升 |
|------|--------|-----|------|
| **相机取图** | 150ms | 80ms | **47%** |
| **RKNN推理** | 65ms | 45ms | **31%** |
| **数据处理** | 20ms | 8ms | **60%** |

---

<div align="center">

**VisionCore Enterprise Edition**  
*专业工业视觉检测系统*

C++模块 - 更快的性能，更好的体验

返回 [文档中心](./README.md) | [系统安装手册](./系统安装配置手册.md)

</div>

