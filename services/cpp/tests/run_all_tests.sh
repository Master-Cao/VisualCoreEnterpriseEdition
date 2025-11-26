#!/bin/bash
# 运行所有C++模块测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  $1"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[→]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_header "Visual Core C++ 模块测试套件"
echo ""

# 检查Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    print_error "未找到Python，请先安装Python 3"
    exit 1
fi

print_info "使用Python: $PYTHON_CMD ($(${PYTHON_CMD} --version))"
echo ""

# 检查numpy
if ! ${PYTHON_CMD} -c "import numpy" &> /dev/null; then
    print_error "未找到numpy，请安装: pip install numpy"
    exit 1
fi

# 检查C++模块是否已编译
DIST_DIR="$SCRIPT_DIR/../dist"
if [ ! -d "$DIST_DIR" ]; then
    print_error "未找到dist目录，请先编译C++模块"
    print_info "运行: cd ../.. && ./build.sh"
    exit 1
fi

# 测试计数
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 运行相机模块测试
print_header "测试相机模块 (vc_camera_cpp)"
echo ""

if [ -f "test_camera.py" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if ${PYTHON_CMD} test_camera.py; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        print_success "相机模块测试通过"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        print_error "相机模块测试失败"
    fi
else
    print_error "未找到test_camera.py"
fi

echo ""
echo ""

# 运行检测模块测试
print_header "测试检测模块 (vc_detection_cpp)"
echo ""

if [ -f "test_detection.py" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if ${PYTHON_CMD} test_detection.py; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        print_success "检测模块测试通过"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        print_error "检测模块测试失败"
    fi
else
    print_error "未找到test_detection.py"
fi

echo ""
echo ""

# 打印总结
print_header "测试总结"
echo ""
echo "总测试数: $TOTAL_TESTS"
print_success "通过: $PASSED_TESTS"
if [ $FAILED_TESTS -gt 0 ]; then
    print_error "失败: $FAILED_TESTS"
fi
echo ""

if [ $FAILED_TESTS -eq 0 ] && [ $TOTAL_TESTS -gt 0 ]; then
    print_success "所有测试通过！🎉"
    exit 0
else
    print_error "部分测试失败，请检查错误信息"
    exit 1
fi

