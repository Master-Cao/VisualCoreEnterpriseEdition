@echo off
REM Visual Core Enterprise Edition C++ 模块编译脚本 (Windows)
setlocal enabledelayedexpansion

REM 颜色代码（需要Windows 10以上支持ANSI转义序列）
set "ESC="

echo ====================================
echo Visual Core C++ 模块编译 (Windows)
echo ====================================
echo.

REM 解析命令行参数
set BUILD_TYPE=Release
set BUILD_CAMERA=1
set BUILD_DETECTION=1
set CLEAN_BUILD=0
set NUM_JOBS=%NUMBER_OF_PROCESSORS%
set GENERATOR=

:parse_args
if "%~1"=="" goto end_parse_args
if /i "%~1"=="--debug" (
    set BUILD_TYPE=Debug
    shift
    goto parse_args
)
if /i "%~1"=="--camera-only" (
    set BUILD_DETECTION=0
    shift
    goto parse_args
)
if /i "%~1"=="--detection-only" (
    set BUILD_CAMERA=0
    shift
    goto parse_args
)
if /i "%~1"=="--clean" (
    set CLEAN_BUILD=1
    shift
    goto parse_args
)
if /i "%~1"=="-j" (
    set NUM_JOBS=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--mingw" (
    set GENERATOR=MinGW Makefiles
    shift
    goto parse_args
)
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="-h" goto show_help
echo [ERROR] 未知选项: %~1
echo 使用 --help 查看帮助
exit /b 1

:show_help
echo 用法: build.bat [选项]
echo.
echo 选项:
echo   --debug              使用Debug模式编译（默认Release）
echo   --camera-only        只编译camera模块
echo   --detection-only     只编译detection模块
echo   --clean              清理后重新编译
echo   -j ^<num^>             使用指定数量的并行任务（默认: CPU核心数）
echo   --mingw              使用MinGW编译器（默认使用Visual Studio）
echo   --help, -h           显示此帮助信息
echo.
echo 示例:
echo   build.bat                   # 编译所有模块
echo   build.bat --clean           # 清理后重新编译
echo   build.bat --debug           # Debug模式编译
echo   build.bat --camera-only     # 只编译camera模块
echo   build.bat --mingw           # 使用MinGW编译
exit /b 0

:end_parse_args

REM 检查CMake
echo [INFO] 检查编译环境...
where cmake >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到CMake，请先安装CMake
    echo 下载地址: https://cmake.org/download/
    exit /b 1
)
echo [OK] 找到CMake

REM 检查编译器
if defined GENERATOR (
    echo [INFO] 使用指定的生成器: %GENERATOR%
    where g++ >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] 未找到MinGW编译器
        exit /b 1
    )
    echo [OK] 找到MinGW编译器
) else (
    REM 检查Visual Studio
    where cl >nul 2>nul
    if errorlevel 1 (
        echo [WARNING] 未找到Visual Studio编译器
        echo [INFO] 尝试使用Developer Command Prompt或安装Visual Studio
        echo.
        echo 提示: 如果已安装MinGW，可以使用 --mingw 选项
        exit /b 1
    )
    echo [OK] 找到Visual Studio编译器
)

REM 检查Python
echo [INFO] 检查Python环境...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到Python，请先安装Python 3
    echo 下载地址: https://www.python.org/downloads/
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Python版本: %PYTHON_VERSION%

REM 检查pybind11
python -c "import pybind11" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到pybind11，请安装: pip install pybind11
    exit /b 1
)
for /f %%i in ('python -c "import pybind11; print(pybind11.__version__)"') do set PYBIND11_VERSION=%%i
echo [OK] pybind11版本: %PYBIND11_VERSION%
echo.

REM 清理build目录
if "%CLEAN_BUILD%"=="1" (
    echo [INFO] 清理旧的编译文件...
    if exist build rmdir /s /q build
    if exist dist\*.pyd del /q dist\*.pyd
    if exist dist\*.dll del /q dist\*.dll
    echo [OK] 清理完成
)

REM 创建build目录
if not exist build mkdir build
cd build

REM 配置CMake
echo [INFO] 配置CMake...
set CMAKE_ARGS=-DCMAKE_BUILD_TYPE=%BUILD_TYPE%

if "%BUILD_CAMERA%"=="0" (
    set CMAKE_ARGS=%CMAKE_ARGS% -DBUILD_CAMERA_MODULE=OFF
    echo [WARNING] 跳过camera模块编译
)

if "%BUILD_DETECTION%"=="0" (
    set CMAKE_ARGS=%CMAKE_ARGS% -DBUILD_DETECTION_MODULE=OFF
    echo [WARNING] 跳过detection模块编译
)

if defined GENERATOR (
    set CMAKE_ARGS=%CMAKE_ARGS% -G "%GENERATOR%"
)

echo [INFO] CMake参数: %CMAKE_ARGS%

cmake %CMAKE_ARGS% ..
if errorlevel 1 (
    echo [ERROR] CMake配置失败
    cd ..
    exit /b 1
)
echo [OK] CMake配置完成
echo.

REM 编译
echo [INFO] 开始编译（使用 %NUM_JOBS% 个并行任务）...
cmake --build . --config %BUILD_TYPE% --parallel %NUM_JOBS%
if errorlevel 1 (
    echo [ERROR] 编译失败
    cd ..
    exit /b 1
)
echo [OK] 编译完成
cd ..
echo.

REM 检查生成的文件
echo [INFO] 检查生成的模块...
set FOUND_FILES=0

if "%BUILD_CAMERA%"=="1" (
    if exist "dist\vc_camera_cpp.pyd" (
        echo [OK] vc_camera_cpp.pyd 模块已生成
        set FOUND_FILES=1
    ) else (
        echo [WARNING] vc_camera_cpp.pyd 模块未找到
    )
)

if "%BUILD_DETECTION%"=="1" (
    if exist "dist\vc_detection_cpp.pyd" (
        echo [OK] vc_detection_cpp.pyd 模块已生成
        set FOUND_FILES=1
    ) else (
        echo [WARNING] vc_detection_cpp.pyd 模块未找到
    )
)

echo.
echo [INFO] 生成的文件列表:
dir /b dist\*.pyd 2>nul
echo.

echo ====================================
echo 编译流程完成！
echo ====================================
echo.
echo [INFO] 输出目录: dist\
echo [INFO] 构建类型: %BUILD_TYPE%
echo.
echo [INFO] 测试模块是否可导入:
if "%BUILD_CAMERA%"=="1" (
    echo   python -c "import sys; sys.path.insert(0, 'dist'); import vc_camera_cpp; print('camera模块导入成功')"
)
if "%BUILD_DETECTION%"=="1" (
    echo   python -c "import sys; sys.path.insert(0, 'dist'); import vc_detection_cpp; print('detection模块导入成功')"
)
echo.

endlocal
exit /b 0

