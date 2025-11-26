# Visual Core C++ 模块编译指南 (Windows)

本文档说明如何在Windows平台上编译相机模块和检测模块。

## 📋 前置要求

### 1. 必需软件

- **CMake** (>= 3.16)
  - 下载: https://cmake.org/download/
  - 安装时选择"Add CMake to system PATH"

- **Python 3** (>= 3.7)
  - 下载: https://www.python.org/downloads/
  - 安装时勾选"Add Python to PATH"
  - 安装pybind11: `pip install pybind11`

- **C++ 编译器**（二选一）:
  - **选项A: Visual Studio** (推荐)
    - Visual Studio 2019/2022 (Community版免费)
    - 下载: https://visualstudio.microsoft.com/
    - 安装时选择"Desktop development with C++"
  
  - **选项B: MinGW-w64**
    - 下载: https://www.mingw-w64.org/
    - 或使用MSYS2: https://www.msys2.org/

### 2. 可选软件

- **OpenCV** (用于检测模块的图像处理)
  - 下载预编译版本: https://opencv.org/releases/
  - 或使用vcpkg安装: `vcpkg install opencv`

---

## 🚀 编译方法

### 方法一：使用批处理脚本 (推荐新手)

#### 基本用法

```cmd
# 在Visual Studio Developer Command Prompt中运行
cd services\cpp

# 编译所有模块
build.bat

# 只编译camera模块
build.bat --camera-only

# 只编译detection模块
build.bat --detection-only

# 清理后重新编译
build.bat --clean

# Debug模式编译
build.bat --debug

# 使用MinGW编译
build.bat --mingw

# 使用8个并行任务编译
build.bat -j 8
```

#### 清理编译产物

```cmd
clean.bat
```

---

### 方法二：使用PowerShell脚本 (推荐高级用户)

#### 启用PowerShell脚本执行

首次使用需要设置执行策略：

```powershell
# 以管理员身份运行PowerShell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 基本用法

```powershell
cd services\cpp

# 编译所有模块
.\build.ps1

# 只编译camera模块
.\build.ps1 -CameraOnly

# 只编译detection模块
.\build.ps1 -DetectionOnly

# 清理后重新编译
.\build.ps1 -Clean

# Debug模式编译
.\build.ps1 -Debug

# 使用MinGW编译
.\build.ps1 -MinGW

# 查看帮助
.\build.ps1 -Help
```

---

### 方法三：手动使用CMake

```cmd
cd services\cpp
mkdir build
cd build

# 配置（Visual Studio）
cmake ..

# 配置（MinGW）
cmake -G "MinGW Makefiles" ..

# 编译
cmake --build . --config Release --parallel 8

# 生成的文件在 services\cpp\dist\ 目录下
```

---

## 🔧 常见问题排查

### 问题1: 找不到CMake

**错误信息:**
```
'cmake' 不是内部或外部命令
```

**解决方法:**
1. 确认已安装CMake
2. 将CMake添加到系统PATH
3. 重启命令行窗口

---

### 问题2: 找不到编译器

**错误信息 (Visual Studio):**
```
未找到Visual Studio编译器
```

**解决方法:**
1. 使用"Developer Command Prompt for VS 2022"（开始菜单中搜索）
2. 或者使用 `--mingw` 选项切换到MinGW编译器

**错误信息 (MinGW):**
```
未找到MinGW编译器
```

**解决方法:**
1. 确认已安装MinGW-w64
2. 将MinGW的bin目录添加到PATH
   例如: `C:\mingw64\bin`

---

### 问题3: pybind11未找到

**错误信息:**
```
未找到pybind11
```

**解决方法:**
```cmd
pip install pybind11
# 或指定版本
pip install pybind11==2.11.1
```

---

### 问题4: Python版本不匹配

**错误信息:**
```
Could not find a package configuration file provided by "Python3"
```

**解决方法:**
1. 确认Python 3已安装并在PATH中
2. 指定Python路径：
   ```cmd
   cmake -DPython3_ROOT_DIR="C:\Python39" ..
   ```

---

### 问题5: RKNN库未找到（检测模块）

**错误信息:**
```
YOLOv8-Seg项目未找到
```

**解决方法:**
1. 确认 `infrastructure/yolov8-seg-thread-stream` 目录存在
2. 确认RKNN库文件存在:
   - `infrastructure/yolov8-seg-thread-stream/librknn_api/*/librknnrt.so`

**注意:** Windows平台可能不支持RKNN（仅Linux/ARM），可以只编译camera模块：
```cmd
build.bat --camera-only
```

---

### 问题6: OpenCV未找到

**警告信息:**
```
未找到OpenCV，将使用基础图像处理功能
```

**解决方法（可选）:**

方式A: 使用vcpkg
```cmd
# 安装vcpkg
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
bootstrap-vcpkg.bat

# 安装OpenCV
vcpkg install opencv:x64-windows

# 配置CMake
cmake -DCMAKE_TOOLCHAIN_FILE=C:/path/to/vcpkg/scripts/buildsystems/vcpkg.cmake ..
```

方式B: 手动安装
1. 下载OpenCV: https://opencv.org/releases/
2. 解压到 `C:\opencv`
3. 配置环境变量:
   ```cmd
   set OpenCV_DIR=C:\opencv\build
   cmake ..
   ```

---

## ✅ 验证编译结果

### 检查生成的文件

```cmd
dir dist
# 应该看到:
#   vc_camera_cpp.pyd      (相机模块)
#   vc_detection_cpp.pyd   (检测模块)
```

### 测试模块导入

#### 测试相机模块
```cmd
python -c "import sys; sys.path.insert(0, 'dist'); import vc_camera_cpp; print('camera模块导入成功')"
```

#### 测试检测模块
```cmd
python -c "import sys; sys.path.insert(0, 'dist'); import vc_detection_cpp; print('detection模块导入成功')"
```

#### 运行测试套件
```cmd
cd tests
python test_camera.py
python test_detection.py
```

---

## 📁 目录结构

编译完成后的目录结构：

```
services/cpp/
├── build/                  # CMake构建目录（临时文件）
├── dist/                   # 编译输出目录
│   ├── vc_camera_cpp.pyd   # 相机模块（Python扩展）
│   └── vc_detection_cpp.pyd # 检测模块（Python扩展）
├── camera/                 # 相机模块源码
│   ├── bindings.cpp
│   ├── VisionaryCameraLib.cpp
│   ├── VisionaryCameraLib.h
│   └── CMakeLists.txt
├── detection/              # 检测模块源码
│   ├── bindings.cpp
│   ├── DetectorLib.h
│   ├── RKNNDetector.h
│   ├── RKNNDetector.cpp
│   └── CMakeLists.txt
├── tests/                  # 测试脚本
│   ├── test_camera.py
│   └── test_detection.py
├── build.bat              # 批处理编译脚本
├── build.ps1              # PowerShell编译脚本
├── build.sh               # Linux/Mac编译脚本
├── clean.bat              # Windows清理脚本
├── clean.sh               # Linux/Mac清理脚本
└── CMakeLists.txt         # 主CMake配置文件
```

---

## 🎯 使用编译好的模块

### Python代码示例

```python
import sys
sys.path.insert(0, 'services/cpp/dist')

# 使用相机模块
import vc_camera_cpp
camera = vc_camera_cpp.VisionaryCamera("192.168.1.10", 2114, True)

# 使用检测模块
import vc_detection_cpp
detector = vc_detection_cpp.RKNNDetector(
    "model.rknn",
    conf_threshold=0.5,
    nms_threshold=0.45,
    target="rk3588"
)
```

详细使用说明请参考: [使用指南文档](../../docs/cpp_modules_usage.md)

---

## 💡 开发提示

### Visual Studio 配置

1. **设置启动项目**
   ```
   在Visual Studio中打开: services\cpp\build\*.sln
   ```

2. **调试Python扩展**
   - 项目属性 → 调试 → 命令: `python.exe`
   - 命令参数: `test_script.py`
   - 工作目录: `$(ProjectDir)`

### 增量编译

修改代码后，无需重新运行CMake，直接编译：
```cmd
cd services\cpp\build
cmake --build . --config Release
```

### 多配置构建

```cmd
# Debug版本
build.bat --debug

# Release版本
build.bat
```

---

## 🆘 获取帮助

如果遇到问题：

1. 查看编译输出的错误信息
2. 确认所有前置软件已正确安装
3. 尝试清理后重新编译: `clean.bat` 然后 `build.bat --clean`
4. 查看详细日志: `build.bat > build.log 2>&1`

---

## 📝 更新日志

- 2025-11-26: 初始版本
  - 支持Windows批处理和PowerShell编译脚本
  - 支持Visual Studio和MinGW编译器
  - 模块化camera和detection子项目

