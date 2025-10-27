VisionCorePro
===============

概述
----
VisionCorePro 是对现有 `VisionCore` 的工程化重构版本，目标是清晰的分层、可测试、可替换与可维护。此仓库将在不改变现有业务行为的前提下，逐步迁移并优化结构与文档。

目录结构
----
```
VisionCorePro/
  app/                # 入口与装配（bootstrap）
  domain/             # 领域模型/枚举/类型
  services/           # 业务服务（相机/检测/通信/系统/标定）
  infrastructure/     # 第三方/底层适配（如 SICK SDK 低层）
  configs/            # 配置与示例（config.yaml, transformation_matrix.json）
  docs/               # 文档（架构/配置/部署/开发）
  scripts/            # 运维脚本（systemd/安装脚本）
  tests/              # 单元/集成测试
```

迁移与兼容原则
----
- 不改变对外协议与主要行为，优先保持兼容。
- 配置键统一：采用 `enable`、标准化 ROI 字段（详见 `docs/configuration.md`）。
- 入口瘦身：`app/main.py` 仅负责启动与装配，命令与业务逻辑下沉到各服务。

快速开始（临时开发）
----
```bash
cd VisionCorePro
python -m app.main
```

文档
----
- docs/README.md 文档索引
- docs/architecture.md 架构与分层
- docs/configuration.md 配置说明与示例
- docs/development.md 开发流程与规范
- docs/deployment.md 部署与运维

路线图（短期）
----
- [ ] 迁移通信（TCP/MQTT）至 services/comm
- [ ] 迁移相机与检测至 services/camera 与 services/detection
- [ ] 引入配置校验（可选 JSON Schema）与兼容适配层
- [ ] 最小化单元测试集（无硬件）
- [ ] 渐进替换 `VisionCore/main.py` 调用路径

许可
----
沿用项目根目录 LICENSE。
