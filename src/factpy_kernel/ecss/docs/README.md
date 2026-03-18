# FactPy ECSS 文档

- 适用范围：`src/factpy_kernel/ecss`
- 最后更新：2026-03-18
- 目标读者：需要复用 ECSS domain preset、但不想把写侧或读侧逻辑混在一起的开发者。

本目录记录 `src/factpy_kernel/ecss` 的当前实现口径。

## 范围

覆盖 `src/factpy_kernel/ecss` 下的 shared ECSS helpers，当前主要是 `ECSS-M-ST-10` 风格 VCD/compliance predicate preset。

## 当前职责

- 维护 ECSS VCD predicate 常量与 schema preset 定义 -> `factpy_kernel.ecss.vcd`
- 提供 `schema_ir` 扩展 helper -> `extend_schema_ir_with_ecss_vcd_predicates(...)`

## 不负责什么

- 不负责 audit package 查询、matrix 组装或静态页面渲染（属于 `audit`）
- 不负责 runtime facts 写入工作流或 HTTP surface（属于 `sdk` / `service`）
- 不负责 schema DSL 编译、registry publish/apply（属于 `authoring`）
- 不负责标准原文核实、领域本体或 temporal/uncertainty semantics

## 当前限制与兼容边界

- 当前只提供一个很窄的 VCD/compliance preset；还没有更广的 ECSS/ESSB preset 集合
- preset 目前是手写 schema predicate dict，不是 `Entity` class/DSL sugar
- `audit` 仍 re-export `extend_schema_ir_with_ecss_vcd_predicates(...)` 以保持既有调用兼容，但 canonical owner 已迁到本模块

## 相关测试入口

- `src/factpy_kernel/tests/test_phase3_contracts_v1.py`

## 相关历史蓝图

- [`docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md) — Scenario B 作为近期锚点的选择依据
- [`docs/blueprints/archive/2026-03-18_ecss-vcd-compliance-delivery.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_ecss-vcd-compliance-delivery.md) — VCD/compliance matrix 的 data model 与 delivery 边界
- [`docs/blueprints/active/2026-03-18_ecss-requirement-authoring-surface.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-18_ecss-requirement-authoring-surface.md) — shared preset owner 与写侧 helper 的当前任务边界

## 当前文档

- `src/factpy_kernel/ecss/docs/01_overview.md`
  - shared ECSS preset 的公共入口、模块边界与当前限制。
