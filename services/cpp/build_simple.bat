@echo off
REM Visual Core C++ 简化编译脚本 (Windows)
REM 适用于在Visual Studio Developer Command Prompt中使用

echo ====================================
echo Visual Core C++ Module Build
echo ====================================
echo.

REM 检查CMake
where cmake >nul 2>nul
if errorlevel 1 (
    echo ERROR: CMake not found
    echo Please install CMake from: https://cmake.org/download/
    exit /b 1
)
echo [OK] CMake found

REM 检查Python
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3 from: https://www.python.org/downloads/
    exit /b 1
)
echo [OK] Python found

REM 检查pybind11
echo [INFO] Checking pybind11...
python -c "import pybind11" 2>nul
if errorlevel 1 (
    echo ERROR: pybind11 not found
    echo Please install: pip install pybind11
    exit /b 1
)
echo [OK] pybind11 found
echo.

REM 创建build目录
if not exist build mkdir build
cd build

REM 配置CMake
echo [INFO] Configuring CMake...
cmake -DCMAKE_BUILD_TYPE=Release ..
if errorlevel 1 (
    echo ERROR: CMake configuration failed
    cd ..
    exit /b 1
)
echo [OK] CMake configured
echo.

REM 编译
echo [INFO] Building...
cmake --build . --config Release --parallel %NUMBER_OF_PROCESSORS%
if errorlevel 1 (
    echo ERROR: Build failed
    cd ..
    exit /b 1
)
echo [OK] Build completed
cd ..
echo.

REM 检查结果
echo [INFO] Generated modules:
dir /b dist\*.pyd 2>nul
echo.
echo ====================================
echo Build Complete!
echo ====================================
echo Output directory: dist\
echo.
echo Test import:
echo   python -c "import sys; sys.path.insert(0, 'dist'); import vc_camera_cpp; print('OK')"
echo.

exit /b 0

