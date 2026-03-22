# Memory Workspace

本目录承载仓库的 **operational memory**：

- session continuity
- 当前阶段的工作记忆入口
- 历史 handoff 归档

它不是：

- 当前实现真相
- active blueprint
- stable architecture principle

## 边界

- 当前实现真相仍以 `src/factpy_kernel/*/docs/` 为准。
- 当前任务约束仍以 `docs/blueprints/active/` 为准。
- 稳定原则与长期边界仍以 `docs/architecture_principles.md` 为准。

## 结构

- [current.md](/Users/zhenzhili/hnsm-backend/memory/current.md)
  - 当前 canonical operational memory 入口。
- `session_handoffs/YYYY-MM-DD.md`
  - 按日期保留的 handoff 记录，用于回放某一工作日的 stopping point。

## 使用规则

- 开新 session 时优先从 `memory/current.md` 启动。
- 需要恢复某一天的细节时，再下钻到对应 `session_handoffs/` 文件。
- 不要把 `memory/` 文档当作当前系统 truth；若其中结论变成 durable boundary，应迁回 blueprint 或模块 docs。
