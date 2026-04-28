# FactPy Application 文档

本目录记录 `src/kernel/application` 的当前实现口径。`application` 是 `core` 之上的 canonical Python runtime authority；`sdk` 负责 Python product surface、DSL authoring 和 outward facade compatibility。

## 当前文档

- `src/kernel/application/docs/01_overview.md`
  - application 模块职责、runtime protocol / executor 结构、SDK adapter 关系、保守 fallback 边界与测试入口。
- `src/kernel/application/docs/01_overview_en.md`
  - English mirror of the overview.

## 使用约定

- 本目录文档以当前实现行为为准，不是独立设计草案。
- 新增或调整 `application` 公共入口时，应同步更新本目录文档与对应测试。
- application protocol 不接收 SDK facade objects、SDK `Field` descriptors 或 SDK DSL objects；SDK 负责把 ergonomic 输入 lower/adapter 成 application runtime DTO。
- 历史架构背景与任务蓝图流程见 [docs/blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md) 与 [runtime-authority cleanup blueprint](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md)。
