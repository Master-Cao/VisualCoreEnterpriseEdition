#!/bin/bash

echo "=========================================="
echo "  VisionCore EE - RK3588 Docker构建工具"
echo "=========================================="
echo ""

# 检查是否在ARM64平台
ARCH=$(uname -m)
echo "📋 当前系统架构: $ARCH"

if [ "$ARCH" != "aarch64" ]; then
    echo "⚠️  警告：当前平台是 $ARCH，不是 aarch64 (ARM64)"
    echo "   如果要为RK3588构建镜像，建议在RK3588设备上构建"
    echo "   或者使用Docker buildx进行交叉编译"
    echo ""
    read -p "是否继续？(y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 构建已取消"
        exit 1
    fi
fi

# 切换到项目根目录
cd "$(dirname "$0")/.." || exit 1

# 检查RKNN wheel文件是否存在
RKNN_WHEEL="scripts/rknn_toolkit2-2.3.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
if [ ! -f "$RKNN_WHEEL" ]; then
    echo "❌ 错误：找不到RKNN wheel文件"
    echo "   期望路径: $RKNN_WHEEL"
    echo "   请确保文件存在"
    exit 1
fi

echo "✅ 找到RKNN wheel文件"
echo ""

# 检查必要的目录
echo "📁 检查项目结构..."
REQUIRED_DIRS=("app" "domain" "handlers" "services" "infrastructure" "configs" "models")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "❌ 错误：缺少目录 $dir"
        exit 1
    fi
done
echo "✅ 项目结构完整"
echo ""

# 显示Docker版本
echo "📦 Docker信息:"
docker --version || { echo "❌ 错误：Docker未安装"; exit 1; }
echo ""

# 开始构建
echo "🚀 开始构建RK3588镜像..."
echo "   这可能需要5-10分钟，请耐心等待..."
echo ""

# 构建镜像
docker build \
    -f docker/Dockerfile.rk3588 \
    -t visioncore-ee:rk3588 \
    --build-arg BUILDDATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    .

# 检查构建结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ RK3588镜像构建成功！"
    echo "=========================================="
    echo ""
    echo "📊 镜像信息:"
    docker images visioncore-ee:rk3588
    echo ""
    echo "📋 使用方法："
    echo "  1. 启动容器："
    echo "     cd docker"
    echo "     docker-compose -f docker-compose.rk3588.yml up -d"
    echo ""
    echo "  2. 查看日志："
    echo "     docker logs -f visioncore_rk3588"
    echo ""
    echo "  3. 进入容器："
    echo "     docker exec -it visioncore_rk3588 bash"
    echo ""
    echo "  4. 停止容器："
    echo "     docker-compose -f docker-compose.rk3588.yml down"
    echo ""
    echo "⚠️  重要提醒："
    echo "  - 确保 configs/config.yaml 中 model.backend 设置为 'rknn' 或 'auto'"
    echo "  - 模型文件应使用 .rknn 格式"
    echo "  - 首次运行需要加载NPU驱动，可能需要几秒钟"
    echo "  - 确保RK3588的NPU驱动已正确安装"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ 镜像构建失败"
    echo "=========================================="
    echo ""
    echo "请检查上面的错误信息，常见问题："
    echo "  1. 网络问题 - 尝试使用国内镜像源"
    echo "  2. 权限问题 - 确保有Docker执行权限"
    echo "  3. 磁盘空间不足 - 至少需要2GB可用空间"
    echo "  4. RKNN wheel文件路径错误"
    echo ""
    exit 1
fi

