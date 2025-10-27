# 部署与运维

系统服务（示例）
- 参见 `scripts/visioncore.service`
- `WorkingDirectory` 指向项目根或打包目录

常用命令
```bash
# 启动/停止/重启
sudo systemctl start visioncore
sudo systemctl stop visioncore
sudo systemctl restart visioncore

# 查看日志
journalctl -u visioncore -f
```
