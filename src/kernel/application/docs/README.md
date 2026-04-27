# FactPy Application 文档

本目录记录 `src/kernel/application` 的当前实现口径，面向需要理解 application 中层职责、已完成迁移范围与当前保守边界的开发者。

## 当前文档

- `src/kernel/application/docs/01_overview.md`
  - application 模块职责、当前模块结构、已落地能力、SDK 委托关系、保守 fallback 边界与下一步迁移入口。

## 使用约定

- 本目录文档以当前实现行为为准，不是独立设计草案。
- 新增或调整 `application` 公共入口时，应同步更新本目录文档与对应测试。
- `application` 是 `core` 之上的中性运行层，不等价于 SDK facade，也不等价于 service HTTP 层。
- 历史架构背景与任务蓝图流程见 [docs/blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md) 与 [docs/blueprint_history/application_projection_blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/application_projection_blueprint.md)。
