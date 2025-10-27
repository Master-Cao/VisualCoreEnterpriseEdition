# 架构与分层（VisionCorePro）

目标
- 入口瘦身：`app/` 仅负责装配与启动
- 分层清晰：domain（模型/枚举）/ services（业务）/ infrastructure（适配）
- 可替换：接口驱动服务实现，便于替换相机/检测/通信
- 可测试：无硬件单元测试覆盖配置/路由/ROI 等逻辑

分层
- app/: main 与 bootstrap
- domain/: enums/models/types
- services/
  - system/: initializer/monitor/log/config
  - comm/: mqtt/tcp/command_router
  - camera/: 相机接口与实现（SICK）
  - detection/: 推理与后处理
  - calibration/: 标定
- infrastructure/: 第三方/底层适配（SICK 协议等）

演进
- 优先迁移通信与命令路由 → 相机/检测 → 配置校验 → 监控重启
