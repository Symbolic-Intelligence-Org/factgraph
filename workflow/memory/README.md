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
- [project_v0_1_0_rc3_published.md](/Users/zhenzhili/hnsm-backend/memory/project_v0_1_0_rc3_published.md)
  - `v0.1.0-rc.3` publish checkpoint.
- [project_lifecycle_assets_remaining_after_rc3.md](/Users/zhenzhili/hnsm-backend/memory/project_lifecycle_assets_remaining_after_rc3.md)
  - rc.3 之后仍未完成的 lifecycle/assets 设计线索。
- [project_schema_mutation_lifecycle_implemented.md](/Users/zhenzhili/hnsm-backend/memory/project_schema_mutation_lifecycle_implemented.md)
  - `fg.schema.add(...)` additive schema mutation lifecycle publish checkpoint.
- [project_schema_field_add_lifecycle_implemented.md](/Users/zhenzhili/hnsm-backend/memory/project_schema_field_add_lifecycle_implemented.md)
  - Additive non-identity schema field-add lifecycle publish checkpoint.
- [project_confidence_evidence_meta_release_cleanup_implemented.md](/Users/zhenzhili/hnsm-backend/memory/project_confidence_evidence_meta_release_cleanup_implemented.md)
  - Confidence / evidence meta release cleanup publish checkpoint.
- [project_eval_row_bindings_port_map_slice_zeta_implemented.md](/Users/zhenzhili/hnsm-backend/workflow/memory/project_eval_row_bindings_port_map_slice_zeta_implemented.md)
  - Evaluate-result flatten Slice ζ checkpoint: `EvaluateRow.bindings` port-map shape implemented and archived.
- `session_handoffs/YYYY-MM-DD.md`
  - 按日期保留的 handoff 记录，用于回放某一工作日的 stopping point。

## 使用规则

- 开新 session 时优先从 `memory/current.md` 启动。
- 需要恢复某一天的细节时，再下钻到对应 `session_handoffs/` 文件。
- 不要把 `memory/` 文档当作当前系统 truth；若其中结论变成 durable boundary，应迁回 blueprint 或模块 docs。
