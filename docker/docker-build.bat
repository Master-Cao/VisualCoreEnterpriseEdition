@echo off
REM VisionCore Enterprise Edition - Docker构建脚本 (Windows)
REM 用于在Windows上构建CPU/GPU版本的Docker镜像

echo ==========================================
echo   VisionCore EE - Docker构建工具
echo ==========================================
echo.

REM 切换到项目根目录
cd /d %~dp0\..

REM 检查Docker是否安装
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 错误：Docker未安装或未启动
    echo    请先安装Docker Desktop
    pause
    exit /b 1
)

echo 📦 Docker信息:
docker --version
echo.

REM 提示用户选择版本
echo 请选择要构建的版本：
echo   1. CPU版本 (适用于开发测试)
echo   2. GPU版本 (需要NVIDIA显卡)
echo.
set /p VERSION="请输入选项 (1 或 2): "

if "%VERSION%"=="1" (
    set DOCKERFILE=docker/Dockerfile
    set TAG=visioncore-ee:latest
    set COMPOSE=docker/docker-compose.yml
    echo.
    echo 🚀 开始构建CPU版本...
) else if "%VERSION%"=="2" (
    set DOCKERFILE=docker/Dockerfile.gpu
    set TAG=visioncore-ee:gpu
    set COMPOSE=docker/docker-compose.gpu.yml
    echo.
    echo 🚀 开始构建GPU版本...
    echo ⚠️  注意：需要安装NVIDIA驱动和nvidia-docker
) else (
    echo ❌ 无效的选项
    pause
    exit /b 1
)

echo.
echo 这可能需要几分钟，请耐心等待...
echo.

REM 构建镜像
docker build -f %DOCKERFILE% -t %TAG% .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================
    echo ✅ 镜像构建成功！
    echo ==========================================
    echo.
    echo 📊 镜像信息:
    docker images %TAG%
    echo.
    echo 📋 使用方法：
    echo   1. 启动容器：
    echo      cd docker
    echo      docker-compose -f %COMPOSE% up -d
    echo.
    echo   2. 查看日志：
    echo      docker logs -f visioncore_enterprise
    echo.
    echo   3. 停止容器：
    echo      docker-compose -f %COMPOSE% down
    echo.
) else (
    echo.
    echo ==========================================
    echo ❌ 镜像构建失败
    echo ==========================================
    echo.
    echo 请检查上面的错误信息
    echo.
)

pause

