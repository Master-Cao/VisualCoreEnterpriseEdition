# 配置规范与示例（VisionCorePro）

统一规范
- 统一使用 `enable` 表示开关
- 统一 ROI 字段：
  - `enable`, `shape`, `center_x`, `center_y`, `radius`, `direction`
  - `rect: {x1,y1,x2,y2}`（矩形）
  - `min_area_px`, `alpha`, `beta`
- 兼容旧键：读取时可将 `enabled` 归一到 `enable`

检测后端
```yaml
model:
  backend: auto     # auto | pc | rknn （Windows 默认 pc，其它默认 rknn）
  path: ./Models/seasoning_256x256_3.pt   # PC使用 .pt / .pt-f16，RKNN 使用 .rknn
  conf_threshold: 0.5
  nms_threshold: 0.45
```

日志配置
```yaml
logging:
  enable: true
  level: INFO           # DEBUG/INFO/WARNING/ERROR/CRITICAL
  console:
    enable: true        # 窗口打印
  file:
    enable: true        # 文件按日轮转
    path: logs
    backup_count: 30
```

示例
参见 `configs/config.yaml`

建议
- 引入 JSON Schema 校验（可选 `schema.yaml`）
- 提供配置迁移脚本，将旧键映射到新键
