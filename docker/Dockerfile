# VisionCore Enterprise Edition - 通用Dockerfile (CPU版本)
# 适用于x86_64平台，使用PyTorch进行推理

FROM python:3.8-slim

# 维护者信息
LABEL maintainer="VisionCore Team"
LABEL description="VisionCore Enterprise Edition - CPU Version"
LABEL platform="x86_64"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    # OpenCV依赖
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # 网络工具
    iputils-ping \
    net-tools \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY ../requirements.txt .

# 安装Python依赖
# 使用清华镜像加速（可选）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY ../app/ ./app/
COPY ../domain/ ./domain/
COPY ../handlers/ ./handlers/
COPY ../services/ ./services/
COPY ../infrastructure/ ./infrastructure/

# 创建必要的目录
RUN mkdir -p /app/configs /app/models /app/logs /app/debug

# 暴露端口
EXPOSE 8888

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('127.0.0.1', 8888)); s.close()" || exit 1

# 启动命令
CMD ["python", "-m", "app.main"]

