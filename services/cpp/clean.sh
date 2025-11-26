#!/bin/bash
# 清理编译产物脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${YELLOW}[CLEAN]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "清理编译产物..."

# 清理build目录
if [ -d "build" ]; then
    print_info "删除 build/ 目录..."
    rm -rf build
    print_success "build/ 已删除"
fi

# 清理dist目录中的编译产物
if [ -d "dist" ]; then
    print_info "清理 dist/ 目录中的 .so 和 .pyd 文件..."
    rm -f dist/*.so
    rm -f dist/*.pyd
    print_success "dist/ 已清理"
fi

# 清理CMake缓存
find . -name "CMakeCache.txt" -delete 2>/dev/null || true
find . -name "CMakeFiles" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "cmake_install.cmake" -delete 2>/dev/null || true
find . -name "Makefile" -delete 2>/dev/null || true

print_success "清理完成！"
echo ""
print_info "可以运行 ./build.sh 重新编译"

