# VisionCore Enterprise Edition - Docker 快速启动指南

## 🎯 选择适合您的版本

| 版本 | 适用场景 | 构建命令 | 启动命令 |
|------|---------|---------|---------|
| **CPU版本** | 开发测试 | `docker build -f Dockerfile -t visioncore-ee:latest ..` | `docker-compose up -d` |
| **GPU版本** | 生产环境 | `docker build -f Dockerfile.gpu -t visioncore-ee:gpu ..` | `docker-compose -f docker-compose.gpu.yml up -d` |
| **RK3588版本** | 边缘部署 | `./docker-build-rk3588.sh` | `docker-compose -f docker-compose.rk3588.yml up -d` |

---

## 🚀 三步启动

### Windows用户

```batch
REM 1. 构建镜像（双击运行）
docker-build.bat

REM 2. 进入docker目录
cd docker

REM 3. 启动服务
docker-compose up -d
```

### Linux/RK3588用户

```bash
# CPU/GPU版本
cd docker
docker build -f Dockerfile -t visioncore-ee:latest ..
docker-compose up -d

# RK3588版本
cd docker
chmod +x docker-build-rk3588.sh
./docker-build-rk3588.sh
docker-compose -f docker-compose.rk3588.yml up -d
```

---

## 📋 启动前检查清单

- [ ] Docker已安装并运行
- [ ] 配置文件已准备: `configs/config.yaml`
- [ ] 模型文件已准备: `models/xxx.pt` 或 `models/xxx.rknn`
- [ ] (RK3588) RKNN wheel文件存在: `scripts/rknn_toolkit2*.whl`
- [ ] (RK3588) NPU驱动已安装: `ls /dev/rknpu*`
- [ ] (GPU) NVIDIA驱动已安装: `nvidia-smi`

---

## 🔍 验证运行

```bash
# 1. 查看容器状态
docker ps

# 2. 查看日志（寻找 ✓ 成功标记）
docker logs -f <container_name>

# 3. 测试TCP连接
telnet localhost 8888
# 或
echo "catch" | nc localhost 8888

# 4. 进入容器调试
docker exec -it <container_name> bash
```

---

## ⚙️ 常用命令

```bash
# 查看日志
docker logs -f <container_name>

# 重启服务
docker restart <container_name>

# 停止服务
docker-compose down

# 查看资源使用
docker stats <container_name>

# 进入容器
docker exec -it <container_name> bash
```

---

## ❗ 常见问题快速修复

### 容器启动失败
```bash
# 查看详细错误
docker logs <container_name>
```

### 端口被占用
```bash
# Windows
netstat -ano | findstr 8888

# Linux
netstat -tuln | grep 8888
```

### 无法访问相机
```yaml
# 确认 docker-compose.yml 中使用:
network_mode: host
```

### GPU不可用
```bash
# 测试GPU
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu20.04 nvidia-smi
```

### RK3588 NPU不可用
```bash
# 检查设备
ls /dev/rknpu*

# 确认配置
privileged: true
volumes:
  - /dev:/dev
```

---

## 📚 详细文档

- **总体说明**: [README.md](README.md)
- **RK3588专用**: [DOCKER_GUIDE_RK3588.md](DOCKER_GUIDE_RK3588.md)
- **项目文档**: [../README.md](../README.md)

---

## 🎉 成功启动的标志

查看日志应该看到：

```
VisionCorePro starting...
✓ TCP服务器启动成功 | 0.0.0.0:8888
✓ 相机连接成功 | 192.168.2.99:2122
✓ 检测器加载成功 | 后端: xxx
✓ MQTT连接成功
✓ SFTP连接成功
✓ 服务已启动，监控器正在运行
```

---

<div align="center">

**现在就开始使用VisionCore Enterprise Edition！**

有问题？查看 [README.md](README.md) 获取详细信息

</div>

