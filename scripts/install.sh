#!/usr/bin/env bash
set -euo pipefail

# 占位安装脚本（后续完善）
# 用法：sudo ./scripts/install.sh

mkdir -p /opt/VisionCorePro
cp -r . /opt/VisionCorePro/
cp scripts/visioncore.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable visioncore

echo "Installed VisionCorePro skeleton."
