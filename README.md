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

已完成的主要改动
----
- 通信重构：`services/comm/` 新增 MQTT/TCP 纯实现与 `CommManager`，支持订阅成功/失败日志、通用回调接入路由。
- 日志系统：`services/system/log_manager.py` + `configs/logging`，窗口打印 + 文件按日轮转。
- 相机封装：`services/camera/sick_camera.py`，接入官方 SDK；完整复制 `infrastructure/sick/common/` 包。
- 检测重构：`services/detection/` 引入分层与工厂：
  - `pc_ultralytics.py`（固定分割解析），`rknn_backend.py`（加载/推理骨架），`base.py` 接口，`factory.py` 按平台/配置选择，`roi.py` 统一 ROI。
- 配置统一：`configs/config.yaml` 统一 `enable`，新增 `logging` 与 `model.backend/path/conf_threshold/nms_threshold`。
- 文档完善：更新配置/架构/部署/开发说明。

后续需要进行的改动
----
- 命令处理：基于 `CommandRouter` 实现各 MQTT 命令的处理器（配置获取/保存、抓图、标定、系统状态等）。
- 系统装配与监控：新增 `services/system/initializer.py`、`monitor.py`，统一装配相机/检测/通信并加入健康监控与自动重启策略。
- RKNN 后处理：补全与现有 RKNN 模型输出匹配的后处理（NMS/Seg）与性能优化。
- SFTP 集成：迁移 `SFTP` 客户端到 `services/sftp/` 并与命令处理打通（图像/文件上传）。
- 测试与质量：添加无硬件单元测试（配置校验、路由、ROI），引入 `pre-commit`（black/ruff/mypy）与 CI。
- 配置校验：可选引入 JSON Schema，对 `configs/config.yaml` 做加载期校验与旧键兼容映射。
- 业务打通：将相机+检测管道对接 TCP `catch` 流程，输出坐标/角度/评分等；与 ROI/标定矩阵融合。
- 部署与运维：Windows/Linux 服务脚本完善、示例环境变量与打包说明。

路线图（短期）
----
- [x] 迁移通信（TCP/MQTT）至 services/comm
- [x] 迁移相机与检测至 services/camera 与 services/detection
- [ ] 引入配置校验（可选 JSON Schema）与兼容适配层
- [ ] 最小化单元测试集（无硬件）
- [ ] 渐进替换 `VisionCore/main.py` 调用路径
- [ ] 接入命令处理与 SFTP 上传
- [ ] 完成 RKNN 后处理与性能验收

许可
----
沿用项目根目录 LICENSE。
