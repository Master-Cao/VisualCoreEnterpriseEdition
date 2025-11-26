#!/bin/bash
# Visual Core Enterprise Edition C++ 模块编译脚本

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "===================================="
print_info "Visual Core C++ 模块编译"
print_info "===================================="
echo ""

# 解析命令行参数
BUILD_TYPE="Release"
BUILD_CAMERA=1
BUILD_DETECTION=1
CLEAN_BUILD=0
NUM_JOBS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            BUILD_TYPE="Debug"
            shift
            ;;
        --camera-only)
            BUILD_DETECTION=0
            shift
            ;;
        --detection-only)
            BUILD_CAMERA=0
            shift
            ;;
        --clean)
            CLEAN_BUILD=1
            shift
            ;;
        -j)
            NUM_JOBS="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --debug              使用Debug模式编译（默认Release）"
            echo "  --camera-only        只编译camera模块"
            echo "  --detection-only     只编译detection模块"
            echo "  --clean              清理后重新编译"
            echo "  -j <num>             使用指定数量的并行任务（默认: $NUM_JOBS）"
            echo "  --help, -h           显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                   # 编译所有模块"
            echo "  $0 --clean           # 清理后重新编译"
            echo "  $0 --debug           # Debug模式编译"
            echo "  $0 --camera-only     # 只编译camera模块"
            echo "  $0 -j 8              # 使用8个并行任务"
            exit 0
            ;;
        *)
            print_error "未知选项: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 检查必要的工具
print_info "检查编译环境..."
check_tool() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装，请先安装"
        exit 1
    fi
}

check_tool cmake
check_tool make
print_success "编译工具检查通过"

# 检查Python和pybind11
print_info "检查Python环境..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    print_error "未找到Python，请先安装Python 3"
    exit 1
fi

PYTHON_CMD=$(command -v python3 || command -v python)
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
print_info "Python版本: $PYTHON_VERSION"

# 检查pybind11
if ! $PYTHON_CMD -c "import pybind11" &> /dev/null; then
    print_error "未找到pybind11，请安装: pip install pybind11"
    exit 1
fi
PYBIND11_VERSION=$($PYTHON_CMD -c "import pybind11; print(pybind11.__version__)")
print_success "pybind11版本: $PYBIND11_VERSION"
echo ""

# 清理build目录
if [ $CLEAN_BUILD -eq 1 ]; then
    print_info "清理旧的编译文件..."
    rm -rf build
    rm -rf dist/*.so dist/*.pyd
    print_success "清理完成"
fi

# 创建build目录
BUILD_DIR="$SCRIPT_DIR/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# 配置CMake
print_info "配置CMake..."
CMAKE_ARGS="-DCMAKE_BUILD_TYPE=$BUILD_TYPE"

if [ $BUILD_CAMERA -eq 0 ]; then
    CMAKE_ARGS="$CMAKE_ARGS -DBUILD_CAMERA_MODULE=OFF"
    print_warning "跳过camera模块编译"
fi

if [ $BUILD_DETECTION -eq 0 ]; then
    CMAKE_ARGS="$CMAKE_ARGS -DBUILD_DETECTION_MODULE=OFF"
    print_warning "跳过detection模块编译"
fi

print_info "CMake参数: $CMAKE_ARGS"
cmake $CMAKE_ARGS ..

if [ $? -ne 0 ]; then
    print_error "CMake配置失败"
    exit 1
fi
print_success "CMake配置完成"
echo ""

# 编译
print_info "开始编译（使用 $NUM_JOBS 个并行任务）..."
make -j$NUM_JOBS

if [ $? -ne 0 ]; then
    print_error "编译失败"
    exit 1
fi
print_success "编译完成"
echo ""

# 检查生成的文件
print_info "检查生成的模块..."
cd "$SCRIPT_DIR"
DIST_DIR="$SCRIPT_DIR/dist"

if [ $BUILD_CAMERA -eq 1 ]; then
    if [ -f "$DIST_DIR/vc_camera_cpp.so" ] || [ -f "$DIST_DIR/vc_camera_cpp.pyd" ]; then
        print_success "✓ vc_camera_cpp 模块已生成"
    else
        print_warning "✗ vc_camera_cpp 模块未找到"
    fi
fi

if [ $BUILD_DETECTION -eq 1 ]; then
    if [ -f "$DIST_DIR/vc_detection_cpp.so" ] || [ -f "$DIST_DIR/vc_detection_cpp.pyd" ]; then
        print_success "✓ vc_detection_cpp 模块已生成"
    else
        print_warning "✗ vc_detection_cpp 模块未找到"
    fi
fi
echo ""

# 显示生成的文件
print_info "生成的文件列表:"
ls -lh "$DIST_DIR"/ 2>/dev/null | grep -E '\.(so|pyd)$' || echo "  (无)"
echo ""

print_success "===================================="
print_success "编译流程完成！"
print_success "===================================="
echo ""
print_info "输出目录: $DIST_DIR"
print_info "构建类型: $BUILD_TYPE"
echo ""
print_info "测试模块是否可导入:"
echo "  cd $SCRIPT_DIR"
if [ $BUILD_CAMERA -eq 1 ]; then
    echo "  python3 -c 'import sys; sys.path.insert(0, \"dist\"); import vc_camera_cpp; print(\"camera模块导入成功\")'"
fi
if [ $BUILD_DETECTION -eq 1 ]; then
    echo "  python3 -c 'import sys; sys.path.insert(0, \"dist\"); import vc_detection_cpp; print(\"detection模块导入成功\")'"
fi
echo ""

