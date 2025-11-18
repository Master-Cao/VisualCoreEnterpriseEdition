# VisionCore Enterprise Edition - Docker部署文件

本目录包含VisionCore Enterprise Edition的Docker部署相关文件。

## 📁 文件说明

### Dockerfile文件

| 文件 | 平台 | 说明 |
|------|------|------|
| `Dockerfile` | x86_64 (CPU) | 通用CPU版本，使用PyTorch |
| `Dockerfile.gpu` | x86_64 (GPU) | GPU加速版本，需要NVIDIA显卡 |
| `Dockerfile.rk3588` | ARM64 (RK3588) | RK3588专用版本，使用RKNN NPU |

### Docker Compose文件

| 文件 | 对应Dockerfile | 说明 |
|------|---------------|------|
| `docker-compose.yml` | `Dockerfile` | CPU版本部署配置 |
| `docker-compose.gpu.yml` | `Dockerfile.gpu` | GPU版本部署配置 |
| `docker-compose.rk3588.yml` | `Dockerfile.rk3588` | RK3588版本部署配置 |

### 其他文件

| 文件 | 说明 |
|------|------|
| `requirements-rk3588.txt` | RK3588专用Python依赖（不含PyTorch） |
| `docker-build-rk3588.sh` | RK3588镜像构建脚本 |
| `.dockerignore` | Docker构建忽略文件 |
| `DOCKER_GUIDE_RK3588.md` | RK3588详细部署指南 |
| `README.md` | 本文档 |

## 🚀 快速开始

### 方案1: CPU版本（通用x86_64平台）

```bash
# 构建镜像
cd docker
docker build -f Dockerfile -t visioncore-ee:latest ..

# 启动服务
docker-compose up -d

# 查看日志
docker logs -f visioncore_enterprise
```

**适用场景**: 
- 开发测试
- 低成本部署
- 不需要高性能推理

**性能**: 10-20 FPS（CPU推理）

---

### 方案2: GPU版本（NVIDIA显卡）

**前提条件**: 
- 已安装NVIDIA驱动
- 已安装nvidia-docker

```bash
# 构建镜像
cd docker
docker build -f Dockerfile.gpu -t visioncore-ee:gpu ..

# 启动服务
docker-compose -f docker-compose.gpu.yml up -d

# 查看日志
docker logs -f visioncore_enterprise_gpu
```

**适用场景**:
- 生产环境
- 高性能需求
- PC端部署

**性能**: 30-50 FPS（GPU推理）

---

### 方案3: RK3588版本（ARM嵌入式平台）

**前提条件**:
- RK3588开发板（如Orange Pi 5 Plus、Rock 5B等）
- 已安装NPU驱动

```bash
# 构建镜像（在RK3588设备上执行）
cd docker
chmod +x docker-build-rk3588.sh
./docker-build-rk3588.sh

# 启动服务
docker-compose -f docker-compose.rk3588.yml up -d

# 查看日志
docker logs -f visioncore_rk3588
```

**适用场景**:
- 边缘计算
- 工业现场部署
- 低功耗需求

**性能**: 15-25 FPS（NPU推理）

**详细说明**: 请查看 [DOCKER_GUIDE_RK3588.md](DOCKER_GUIDE_RK3588.md)

---

## 🔍 平台对比

| 特性 | CPU版本 | GPU版本 | RK3588版本 |
|------|--------|---------|------------|
| **架构** | x86_64 | x86_64 | ARM64 |
| **推理引擎** | PyTorch | PyTorch+CUDA | RKNN |
| **模型格式** | .pt | .pt | .rknn |
| **推理速度** | 10-20 FPS | 30-50 FPS | 15-25 FPS |
| **内存需求** | 2-4GB | 4-6GB | 1-2GB |
| **功耗** | 中等 | 高 | 低 |
| **成本** | 低 | 高 | 中等 |
| **适用场景** | 开发测试 | 生产环境 | 边缘部署 |

---

## 📋 使用步骤

### 1. 准备工作

确保以下文件准备就绪：

```bash
# 项目根目录
VisualCoreEnterpriseEdition/
├── configs/
│   └── config.yaml          # 必须配置
├── models/
│   ├── *.pt                 # CPU/GPU版本
│   └── *.rknn               # RK3588版本
├── scripts/
│   └── rknn_toolkit2*.whl   # 仅RK3588需要
└── docker/                  # 本目录
```

### 2. 配置文件

编辑 `configs/config.yaml`，根据不同平台设置：

**CPU/GPU版本**:
```yaml
model:
  backend: auto              # 或 pc
  model_name: xxx.pt
  path: models/xxx.pt
```

**RK3588版本**:
```yaml
model:
  backend: rknn              # 或 auto
  model_name: xxx.rknn
  path: models/xxx.rknn
```

### 3. 构建镜像

根据目标平台选择对应的Dockerfile：

```bash
# CPU版本
docker build -f docker/Dockerfile -t visioncore-ee:latest .

# GPU版本
docker build -f docker/Dockerfile.gpu -t visioncore-ee:gpu .

# RK3588版本（在RK3588设备上）
./docker/docker-build-rk3588.sh
```

### 4. 启动服务

```bash
cd docker

# CPU版本
docker-compose up -d

# GPU版本
docker-compose -f docker-compose.gpu.yml up -d

# RK3588版本
docker-compose -f docker-compose.rk3588.yml up -d
```

### 5. 验证运行

```bash
# 查看容器状态
docker ps

# 查看日志
docker logs -f <container_name>

# 测试TCP连接
telnet localhost 8888
```

---

## 🛠️ 常用命令

### 容器管理

```bash
# 启动
docker-compose up -d

# 停止
docker-compose down

# 重启
docker-compose restart

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 镜像管理

```bash
# 查看镜像
docker images | grep visioncore

# 删除镜像
docker rmi visioncore-ee:latest

# 导出镜像
docker save visioncore-ee:latest | gzip > visioncore-latest.tar.gz

# 导入镜像
docker load < visioncore-latest.tar.gz
```

### 容器调试

```bash
# 进入容器
docker exec -it <container_name> bash

# 查看资源使用
docker stats <container_name>

# 查看详细信息
docker inspect <container_name>
```

---

## ⚙️ 高级配置

### 网络模式选择

**Host模式**（推荐）:
```yaml
network_mode: host
```
- 优点: 直接访问宿主机网络，适合访问相机等设备
- 缺点: 端口可能冲突

**Bridge模式**:
```yaml
ports:
  - "8888:8888"
```
- 优点: 网络隔离，端口灵活
- 缺点: 需要配置端口映射

### 资源限制

```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2'
    reservations:
      memory: 2G
      cpus: '1'
```

### GPU配置

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1              # 使用1个GPU
          capabilities: [gpu]
```

---

## 🔧 故障排除

### 常见问题

#### 1. 容器无法启动

```bash
# 查看详细日志
docker logs <container_name>

# 检查配置文件
cat ../configs/config.yaml

# 检查端口占用
netstat -tuln | grep 8888
```

#### 2. 无法访问相机

```bash
# 确认使用host网络模式
# 测试网络连通性
docker exec -it <container_name> ping <camera_ip>
```

#### 3. GPU不可用

```bash
# 检查nvidia-docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu20.04 nvidia-smi

# 确认配置了GPU
docker inspect <container_name> | grep -i gpu
```

#### 4. 内存不足

```bash
# 增加内存限制
# 编辑 docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 8G
```

---

## 📚 更多信息

- **RK3588详细指南**: [DOCKER_GUIDE_RK3588.md](DOCKER_GUIDE_RK3588.md)
- **项目文档**: [../README.md](../README.md)
- **配置说明**: 查看 `configs/config.yaml` 中的注释

---

## 📞 技术支持

如遇到问题：

1. 查看容器日志: `docker logs -f <container_name>`
2. 查看应用日志: `../logs/VisionCorePro_*.log`
3. 检查配置文件: `../configs/config.yaml`
4. 验证模型文件: `ls -la ../models/`

---

<div align="center">

**VisionCore Enterprise Edition**  
*Professional Industrial Vision System*

选择适合您的部署方案 | CPU · GPU · RK3588

</div>

