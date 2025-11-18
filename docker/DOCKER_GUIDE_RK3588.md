# VisionCore Enterprise Edition - RK3588 Docker部署指南

## 📋 目录

- [平台要求](#平台要求)
- [快速部署](#快速部署)
- [详细说明](#详细说明)
- [性能优化](#性能优化)
- [常见问题](#常见问题)
- [监控维护](#监控维护)

---

## 平台要求

### 硬件要求

- **SoC**: RK3588 / RK3588S
- **开发板**: Orange Pi 5 Plus、Rock 5B、ArmSoM-W3等
- **内存**: 至少4GB RAM（推荐8GB）
- **存储**: 至少16GB可用空间
- **相机**: SICK 3D相机或其他支持的相机

### 软件要求

- **操作系统**: Ubuntu 20.04/22.04 ARM64（官方支持）
- **Docker**: 20.10+ 
- **Docker Compose**: 1.29+
- **Python**: 3.10（镜像内已包含）
- **NPU驱动**: 已安装RK3588 NPU驱动

### 验证NPU驱动

```bash
# 检查NPU设备
ls /dev/rknpu*

# 应该看到类似输出：
# /dev/rknpu0  /dev/rknpu1  /dev/rknpu2
```

如果没有找到设备，需要先安装NPU驱动：

```bash
# 方法1: 使用官方驱动包（推荐）
sudo apt-get update
sudo apt-get install rockchip-npu-driver

# 方法2: 从源码编译
# 请参考您的开发板厂商文档
```

---

## 快速部署

### 1. 安装Docker和Docker Compose

```bash
# 安装Docker
curl -fsSL https://get.docker.com | sh

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker

# 添加用户到docker组（避免每次使用sudo）
sudo usermod -aG docker $USER
newgrp docker

# 验证安装
docker --version
docker-compose --version
```

### 2. 准备项目文件

```bash
# 进入项目目录
cd /path/to/VisualCoreEnterpriseEdition

# 检查必要文件
ls -la configs/config.yaml      # 配置文件
ls -la models/*.rknn            # RKNN模型文件
ls -la scripts/rknn_toolkit2*.whl  # RKNN依赖包
```

### 3. 配置系统参数

编辑 `configs/config.yaml`，确保以下配置正确：

```yaml
# 检测模型 - RK3588配置
model:
  backend: rknn              # 或 auto（自动检测）
  model_name: seasoning_11.18.float.rknn
  path: models/seasoning_11.18.float.rknn
  conf_threshold: 0.5
  nms_threshold: 0.45

# 相机配置（根据实际情况修改）
camera:
  enable: true
  connection:
    ip: 192.168.2.99        # 相机IP
    port: 2122
    timeout: 0

# TCP服务器配置
DetectionServer:
  enable: true
  host: 0.0.0.0             # 监听所有接口
  port: 8888
  max_connections: 15
```

### 4. 构建Docker镜像

```bash
# 赋予脚本执行权限
chmod +x docker/docker-build-rk3588.sh

# 构建镜像（首次构建约5-10分钟）
./docker/docker-build-rk3588.sh
```

构建过程中会：
- ✅ 检查系统架构
- ✅ 验证RKNN wheel文件
- ✅ 安装系统依赖
- ✅ 安装Python包
- ✅ 复制应用代码

### 5. 启动容器

```bash
# 进入docker目录
cd docker

# 启动服务（后台运行）
docker-compose -f docker-compose.rk3588.yml up -d

# 查看启动日志
docker logs -f visioncore_rk3588
```

看到以下日志表示启动成功：

```
VisionCorePro starting...
✓ TCP服务器启动成功 | 0.0.0.0:8888
✓ 相机连接成功 | 192.168.2.99:2122
✓ 检测器加载成功 | 后端: rknn
✓ MQTT连接成功
✓ 服务已启动，监控器正在运行
```

### 6. 验证运行

```bash
# 方法1: 检查容器状态
docker ps | grep visioncore

# 方法2: 测试TCP连接
telnet localhost 8888
# 或
echo "catch" | nc localhost 8888

# 方法3: 查看NPU使用情况（宿主机执行）
watch -n 1 cat /sys/kernel/debug/rknpu/load
```

---

## 详细说明

### 文件结构

```
VisualCoreEnterpriseEdition/
├── docker/                              # Docker相关文件
│   ├── Dockerfile.rk3588               # RK3588专用Dockerfile
│   ├── requirements-rk3588.txt         # 精简依赖列表
│   ├── docker-compose.rk3588.yml       # 部署配置
│   ├── docker-build-rk3588.sh          # 构建脚本
│   ├── .dockerignore                   # Docker忽略文件
│   └── DOCKER_GUIDE_RK3588.md          # 本文档
├── configs/                             # 配置文件（挂载）
├── models/                              # 模型文件（挂载）
├── logs/                                # 日志输出（挂载）
└── debug/                               # 调试输出（挂载）
```

### 与PC版本的主要区别

| 项目 | PC版本 | RK3588版本 |
|------|--------|------------|
| **基础镜像** | `python:3.8-slim` | `arm64v8/python:3.10-slim` |
| **架构** | x86_64 | ARM64/aarch64 |
| **推理引擎** | PyTorch + Ultralytics | RKNN Toolkit2 |
| **模型格式** | `.pt` (PyTorch) | `.rknn` (RK3588) |
| **加速硬件** | NVIDIA CUDA GPU | RK3588 NPU |
| **内存需求** | 2-4GB | 1-2GB |
| **推理速度** | 30-50 FPS (GPU) | 15-25 FPS (NPU) |
| **镜像大小** | ~3GB | ~1.5GB |

### 网络模式说明

#### Host模式（推荐）

```yaml
network_mode: host
```

**优点**:
- 直接访问宿主机网络设备（相机、PLC等）
- 无需端口映射，性能最佳
- 适合工业现场部署

**缺点**:
- 端口可能与宿主机冲突

#### Bridge模式

```yaml
ports:
  - "8888:8888"
```

**优点**:
- 网络隔离更好
- 端口映射灵活

**缺点**:
- 可能无法直接访问某些硬件设备
- 需要额外配置相机网络

### 数据持久化

容器挂载了以下目录到宿主机：

| 容器路径 | 宿主机路径 | 说明 |
|---------|-----------|------|
| `/app/configs` | `../configs` | 配置文件（必须挂载） |
| `/app/models` | `../models` | AI模型文件（必须挂载） |
| `/app/logs` | `../logs` | 日志输出 |
| `/app/debug` | `../debug` | 调试图像 |
| `/dev` | `/dev` | 设备访问（NPU） |

**重要**: 
- `configs` 和 `models` 必须挂载，否则容器无法正常工作
- `/dev` 挂载是访问NPU的关键

---

## 性能优化

### 1. NPU频率优化

RK3588的NPU支持动态频率调整，可以设置为性能模式：

```bash
# 查看当前频率
cat /sys/class/devfreq/fdab0000.npu/cur_freq

# 查看可用频率
cat /sys/class/devfreq/fdab0000.npu/available_frequencies

# 设置为最高性能（需要root权限）
echo performance | sudo tee /sys/class/devfreq/fdab0000.npu/governor

# 验证设置
cat /sys/class/devfreq/fdab0000.npu/governor
```

### 2. 内存优化

根据实际情况调整容器内存限制：

```yaml
# docker-compose.rk3588.yml
deploy:
  resources:
    limits:
      memory: 2G      # 最大内存
    reservations:
      memory: 1G      # 预留内存
```

### 3. 日志级别优化

生产环境建议使用INFO级别：

```yaml
environment:
  - LOG_LEVEL=INFO  # 而非DEBUG
```

或在 `configs/config.yaml` 中设置：

```yaml
logging:
  level: INFO  # DEBUG会产生大量日志
```

### 4. 模型量化

使用量化模型可以显著提升推理速度：

```python
# 在PC上转换模型时启用量化（需要rknn-toolkit2 PC版）
from rknn.api import RKNN

rknn = RKNN()
rknn.config(target_platform='rk3588')
rknn.load_pytorch(model='yolov8n.pt')
rknn.build(do_quantization=True, dataset='./dataset.txt')  # 启用量化
rknn.export_rknn('yolov8n.quant.rknn')
```

### 5. 启用Swap（内存不足时）

```bash
# 创建2GB swap文件
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 验证
free -h
```

---

## 常见问题

### Q1: 提示 "RKNN API not found" 或 "No RKNN device"

**原因**: NPU驱动未正确加载

**解决方案**:

```bash
# 1. 检查NPU设备
ls -la /dev/rknpu*

# 如果没有找到设备：
# 2. 重新安装NPU驱动
sudo apt-get update
sudo apt-get install --reinstall rockchip-npu-driver

# 3. 重启系统
sudo reboot

# 4. 验证驱动
dmesg | grep -i rknpu
```

### Q2: 容器启动后立即退出

**排查步骤**:

```bash
# 1. 查看容器日志
docker logs visioncore_rk3588

# 2. 检查配置文件
cat configs/config.yaml

# 3. 检查模型文件是否存在
ls -la models/*.rknn

# 4. 尝试交互式运行
docker run -it --rm \
  --network host \
  --privileged \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/models:/app/models \
  visioncore-ee:rk3588 bash

# 5. 手动启动应用
python -m app.main
```

### Q3: 无法访问相机

**原因**: 网络配置或权限问题

**解决方案**:

```bash
# 1. 确认使用host网络模式
# docker-compose.rk3588.yml 中确认：
network_mode: host

# 2. 测试网络连通性（在容器内）
docker exec -it visioncore_rk3588 bash
ping 192.168.2.99
telnet 192.168.2.99 2122

# 3. 检查防火墙
sudo ufw status
sudo ufw allow 8888/tcp

# 4. 确认相机IP配置
# 编辑 configs/config.yaml
```

### Q4: 推理速度比预期慢

**可能原因和解决方案**:

```bash
# 1. 检查NPU是否被占用
cat /sys/kernel/debug/rknpu/load

# 2. 检查NPU频率
cat /sys/class/devfreq/fdab0000.npu/cur_freq

# 3. 设置性能模式
echo performance | sudo tee /sys/class/devfreq/fdab0000.npu/governor

# 4. 检查是否使用了float模型（建议使用量化模型）
# 在config.yaml中查看模型文件名

# 5. 检查容器资源限制
docker stats visioncore_rk3588
```

### Q5: 内存不足 (OOM)

**解决方案**:

```bash
# 1. 增加容器内存限制
# 编辑 docker-compose.rk3588.yml:
deploy:
  resources:
    limits:
      memory: 3G  # 增加到3GB

# 2. 启用swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 3. 降低日志级别
# config.yaml 中设置:
logging:
  level: INFO  # 而非DEBUG

# 4. 减少TCP最大连接数
# config.yaml 中设置:
DetectionServer:
  max_connections: 5  # 减少并发连接
```

### Q6: 容器无法访问NPU

**解决方案**:

确保 `docker-compose.rk3588.yml` 中包含：

```yaml
privileged: true
volumes:
  - /dev:/dev
```

### Q7: 权限问题（日志目录无法写入）

**解决方案**:

```bash
# 1. 调整目录权限
sudo chown -R $USER:$USER logs/ debug/

# 2. 或使用更宽松的权限
chmod 777 logs debug

# 3. 检查SELinux（如果启用）
sudo setenforce 0
```

### Q8: 镜像构建失败

**常见原因**:

```bash
# 1. 网络问题 - 使用国内镜像源
# 编辑 Dockerfile.rk3588，添加：
RUN pip install ... -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. RKNN wheel文件路径错误
ls -la scripts/rknn_toolkit2*.whl

# 3. 磁盘空间不足
df -h

# 4. Docker版本过旧
docker --version  # 需要 20.10+
```

---

## 监控维护

### 日常监控

```bash
# 1. 查看容器状态
docker ps -a

# 2. 实时日志
docker logs -f visioncore_rk3588

# 3. 资源使用情况
docker stats visioncore_rk3588

# 4. NPU使用情况（宿主机）
watch -n 1 cat /sys/kernel/debug/rknpu/load

# 5. 系统资源
htop
```

### 容器管理

```bash
# 启动
docker-compose -f docker/docker-compose.rk3588.yml up -d

# 停止
docker-compose -f docker/docker-compose.rk3588.yml stop

# 重启
docker-compose -f docker/docker-compose.rk3588.yml restart

# 完全删除
docker-compose -f docker/docker-compose.rk3588.yml down

# 重新构建并启动
docker-compose -f docker/docker-compose.rk3588.yml up -d --build
```

### 进入容器调试

```bash
# 进入容器shell
docker exec -it visioncore_rk3588 bash

# 在容器内：
# - 查看进程
ps aux | grep python

# - 查看NPU设备
ls /dev/rknpu*

# - 测试Python环境
python -c "from rknnlite.api import RKNNLite; print('RKNN OK')"

# - 查看配置
cat /app/configs/config.yaml

# - 查看日志
tail -f /app/logs/*.log
```

### 日志管理

```bash
# 导出日志
docker logs visioncore_rk3588 > visioncore.log 2>&1

# 清理旧日志
docker logs visioncore_rk3588 --tail 1000

# 日志轮转（docker-compose中已配置）
# 查看配置：
docker inspect visioncore_rk3588 | grep -A 5 LogConfig
```

### 备份和恢复

```bash
# 备份配置
tar -czf backup-$(date +%Y%m%d).tar.gz configs/ models/

# 备份镜像
docker save visioncore-ee:rk3588 | gzip > visioncore-rk3588.tar.gz

# 恢复镜像
docker load < visioncore-rk3588.tar.gz
```

### 更新应用

```bash
# 方法1: 重新构建镜像
./docker/docker-build-rk3588.sh
docker-compose -f docker/docker-compose.rk3588.yml up -d

# 方法2: 仅更新代码（开发环境）
# 如果挂载了代码目录，只需重启容器
docker restart visioncore_rk3588
```

---

## 生产环境建议

### 1. 开机自启动

```bash
# docker-compose.rk3588.yml 中已配置：
restart: unless-stopped

# 确保Docker服务开机自启
sudo systemctl enable docker
```

### 2. 系统服务方式（可选）

创建systemd服务：

```bash
sudo tee /etc/systemd/system/visioncore.service > /dev/null <<EOF
[Unit]
Description=VisionCore Enterprise Edition
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/VisualCoreEnterpriseEdition/docker
ExecStart=/usr/bin/docker-compose -f docker-compose.rk3588.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.rk3588.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable visioncore
sudo systemctl start visioncore
```

### 3. 监控告警

可以集成Prometheus + Grafana进行监控，或使用简单脚本：

```bash
# 创建监控脚本
cat > monitor.sh <<'EOF'
#!/bin/bash
while true; do
    if ! docker ps | grep -q visioncore_rk3588; then
        echo "容器已停止，尝试重启..."
        cd /path/to/project/docker
        docker-compose -f docker-compose.rk3588.yml up -d
        # 可以添加告警通知
    fi
    sleep 60
done
EOF

chmod +x monitor.sh
nohup ./monitor.sh &
```

### 4. 安全加固

```bash
# 1. 使用非root用户运行（Dockerfile中配置）
# 2. 限制容器权限（仅在必要时使用privileged）
# 3. 定期更新镜像
# 4. 配置防火墙规则
```

---

## 技术支持

### 获取帮助

- 查看系统日志: `docker logs visioncore_rk3588`
- 查看应用日志: `logs/VisionCorePro_*.log`
- 检查配置: `configs/config.yaml`
- NPU状态: `/sys/kernel/debug/rknpu/load`

### 常用命令速查

```bash
# 构建
./docker/docker-build-rk3588.sh

# 启动
cd docker && docker-compose -f docker-compose.rk3588.yml up -d

# 日志
docker logs -f visioncore_rk3588

# 进入
docker exec -it visioncore_rk3588 bash

# 停止
docker-compose -f docker-compose.rk3588.yml down

# 重启
docker restart visioncore_rk3588

# 状态
docker ps | grep visioncore
```

---

## 附录

### RK3588 NPU规格

- **核心**: 3个NPU核心
- **算力**: 6 TOPS (INT8)
- **支持**: INT8/INT16/FP16
- **框架**: TensorFlow, PyTorch, ONNX等

### 推荐配置

| 场景 | 内存配置 | NPU频率 | 并发连接 |
|------|---------|---------|---------|
| 开发测试 | 1GB | 默认 | 5 |
| 生产环境 | 2GB | performance | 10 |
| 高负载 | 3GB | performance | 15 |

---

<div align="center">

**VisionCore Enterprise Edition**  
*Built for Industrial Automation on RK3588*

最后更新: 2025-11-18

</div>

