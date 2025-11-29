#!/bin/bash

echo "=========================================="
echo "内存使用情况诊断脚本"
echo "=========================================="
echo ""

# 1. 总体内存使用
echo "1. 总体内存使用："
free -h
echo ""

# 2. 检查 VisionCore 进程
echo "2. VisionCore 相关进程："
ps aux | grep -E "python.*main|python.*app" | grep -v grep
echo ""

# 3. 共享内存（可能未释放）
echo "3. 共享内存段："
ipcs -m
echo ""

# 4. 检查 /dev/shm 使用
echo "4. /dev/shm 使用情况："
df -h /dev/shm
ls -lh /dev/shm/ 2>/dev/null || echo "无权限查看"
echo ""

# 5. 页缓存占用最多的文件（需要 root）
echo "5. 检查缓存占用（需要root权限）："
if [ "$EUID" -eq 0 ]; then
    echo "Top 10 cached files:"
    find /proc/*/fd -lname "*rknn*" -o -lname "*.so" 2>/dev/null | head -10
else
    echo "提示：使用 sudo 运行此脚本可查看更多信息"
fi
echo ""

# 6. buff/cache 详细信息
echo "6. buff/cache 详细分析："
echo "  - Buffers: 块设备缓冲"
echo "  - Cached: 文件页缓存"
echo "  - 实际可用内存 = free + buff/cache"
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|Slab"
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="

