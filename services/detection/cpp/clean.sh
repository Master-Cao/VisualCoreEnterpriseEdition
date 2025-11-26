#!/bin/bash

# ============================================
# VisualCore Detection C++ 清理脚本
# 清理旧的编译产物
# ============================================

echo "============================================"
echo "  清理旧的编译产物"
echo "============================================"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECTION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${YELLOW}检测模块目录: ${DETECTION_DIR}${NC}"

# 清理detection目录下的.so文件
echo ""
echo -e "${YELLOW}[1/3] 清理detection目录下的.so文件...${NC}"
cd "$DETECTION_DIR"

# 删除旧的vc_detection_cpp模块
if ls vc_detection_cpp*.so 1> /dev/null 2>&1; then
    rm -vf vc_detection_cpp*.so
    echo -e "${GREEN}✓ 已删除vc_detection_cpp*.so${NC}"
fi

# 删除旧的依赖库（包括所有可能的命名）
for lib in libyolov8_lib.so libyolov8seg_lib.so libnn_process.so librknn_engine.so; do
    if [ -f "$lib" ]; then
        rm -vf "$lib"
        echo -e "${GREEN}✓ 已删除 ${lib}${NC}"
    fi
done

echo -e "${YELLOW}清理所有.so文件...${NC}"
find . -maxdepth 1 -name "lib*.so" -type f -exec rm -v {} \;

# 清理build目录
echo ""
echo -e "${YELLOW}[2/3] 清理build目录...${NC}"

# yolov8-thread-stream (旧版本)
if [ -d "$SCRIPT_DIR/yolov8-thread-stream/build" ]; then
    echo "清理 yolov8-thread-stream/build"
    rm -rf "$SCRIPT_DIR/yolov8-thread-stream/build"
    echo -e "${GREEN}✓ 已清理${NC}"
fi

# yolov8-seg-thread-stream (新版本)
if [ -d "$SCRIPT_DIR/yolov8-seg-thread-stream/build" ]; then
    echo "清理 yolov8-seg-thread-stream/build"
    rm -rf "$SCRIPT_DIR/yolov8-seg-thread-stream/build"
    echo -e "${GREEN}✓ 已清理${NC}"
fi

# 清理Desktop等其他位置的残留文件
echo ""
echo -e "${YELLOW}[3/3] 检查其他位置的残留文件...${NC}"

# 检查Desktop
if ls ~/Desktop/vc_detection_cpp*.so 1> /dev/null 2>&1; then
    echo "发现Desktop中的文件:"
    ls -lh ~/Desktop/vc_detection_cpp*.so
    echo -e "${YELLOW}是否删除? (y/n)${NC}"
    read -n 1 CHOICE
    echo ""
    if [ "$CHOICE" = "y" ] || [ "$CHOICE" = "Y" ]; then
        rm -vf ~/Desktop/vc_detection_cpp*.so
        echo -e "${GREEN}✓ 已删除${NC}"
    fi
fi

# 清理Python缓存
echo ""
echo -e "${YELLOW}清理Python缓存...${NC}"
find "$DETECTION_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DETECTION_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Python缓存已清理${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  清理完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "现在可以重新编译:"
echo "  cd $(basename $SCRIPT_DIR)"
echo "  bash build.sh"
echo ""

