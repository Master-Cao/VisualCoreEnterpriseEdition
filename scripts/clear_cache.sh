#!/bin/bash

# 清理系统缓存脚本
# 注意：需要 root 权限

if [ "$EUID" -ne 0 ]; then
    echo "错误：此脚本需要 root 权限"
    echo "请使用: sudo $0"
    exit 1
fi

echo "=========================================="
echo "系统缓存清理脚本"
echo "=========================================="
echo ""

# 显示清理前的内存状态
echo "清理前："
free -h
echo ""

# 1. 同步磁盘（将缓冲区写入磁盘）
echo "1. 同步磁盘缓冲区..."
sync
sleep 1

# 2. 清理页缓存（page cache）
echo "2. 清理页缓存..."
echo 1 > /proc/sys/vm/drop_caches

# 3. 清理目录项和inode缓存
echo "3. 清理目录项和inode..."
echo 2 > /proc/sys/vm/drop_caches

# 4. 清理所有缓存（页缓存+目录项+inode）
echo "4. 清理所有缓存..."
echo 3 > /proc/sys/vm/drop_caches

sleep 1

# 5. 清理共享内存段（如果有孤立的）
echo "5. 检查共享内存..."
orphaned=$(ipcs -m | awk 'NR>3 {print $2}')
if [ -n "$orphaned" ]; then
    echo "发现孤立的共享内存段，正在清理..."
    for id in $orphaned; do
        ipcrm -m $id 2>/dev/null && echo "  已删除共享内存段: $id"
    done
else
    echo "  无孤立的共享内存段"
fi
echo ""

# 6. 清理 /dev/shm 中的临时文件
echo "6. 清理 /dev/shm..."
shm_files=$(find /dev/shm -type f 2>/dev/null | wc -l)
if [ "$shm_files" -gt 0 ]; then
    echo "  发现 $shm_files 个文件"
    # 可选：取消注释下面的行来删除文件
    # find /dev/shm -type f -delete
else
    echo "  /dev/shm 中无临时文件"
fi
echo ""

# 显示清理后的内存状态
echo "清理后："
free -h
echo ""

echo "=========================================="
echo "缓存清理完成"
echo "=========================================="
echo ""
echo "注意事项："
echo "  - 清理缓存是安全的，不会丢失数据"
echo "  - 清理后系统可能暂时变慢（需要重建缓存）"
echo "  - buff/cache 很快会重新增长（这是正常现象）"

