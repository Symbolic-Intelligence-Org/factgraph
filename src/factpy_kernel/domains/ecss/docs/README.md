# FactPy ECSS 文档

- 适用范围：`src/factpy_kernel/ecss`
- 最后更新：2026-03-18
- 目标读者：需要复用 ECSS domain preset、但不想把写侧或读侧逻辑混在一起的开发者。

本目录记录 `src/factpy_kernel/ecss` 的当前实现口径。

## 范围

覆盖 `src/factpy_kernel/ecss` 下的 shared ECSS helpers，当前包括：

- `ECSS-M-ST-10` 风格 VCD/compliance predicate preset
- `Scenario A` 第一轮 `T1` temporal predicate preset（deadline/window/interval relation 的 shared schema owner）
- `Scenario A` 第一轮 uncertainty predicate preset（threshold-bearing probability lane 的 shared schema owner）

## 当前职责

- 维护 ECSS VCD predicate 常量与 schema preset 定义 -> `factpy_kernel.ecss.vcd`
- 提供 `schema_ir` 扩展 helper -> `extend_schema_ir_with_ecss_vcd_predicates(...)`
- 维护 ECSS temporal predicate 常量与 schema preset 定义 -> `factpy_kernel.ecss.temporal`
- 提供 `schema_ir` 扩展 helper -> `extend_schema_ir_with_ecss_temporal_predicates(...)`
- 维护 ECSS uncertainty predicate 常量与 schema preset 定义 -> `factpy_kernel.ecss.uncertainty`
- 提供 `schema_ir` 扩展 helper -> `extend_schema_ir_with_ecss_uncertainty_predicates(...)`

## 不负责什么

- 不负责 audit package 查询、matrix 组装或静态页面渲染（属于 `audit`）
- 不负责 runtime facts 写入工作流或 HTTP surface（属于 `sdk` / `service`）
- 不负责 schema DSL 编译、registry publish/apply（属于 `authoring`）
- 不负责标准原文核实、领域本体、通用 runtime temporal semantics 或 uncertainty semantics

## 当前限制与兼容边界

- 当前只提供一个很窄的 VCD/compliance preset、一个第一轮 Scenario A temporal preset、以及一个第一轮 Scenario A uncertainty preset；还没有更广的 ECSS/ESSB preset 集合
- preset 目前是手写 schema predicate dict，不是 `Entity` class/DSL sugar
- 示例代码如果只是为了走当前 SDK 声明路径，优先在 demo 本地显式声明承载 schema 的 `Entity`，而不是在示例层直接用 `extend_schema_ir_with_ecss_*` 篡改已有 `schema_ir`
- `audit` 仍 re-export `extend_schema_ir_with_ecss_vcd_predicates(...)` 以保持既有调用兼容，但 canonical owner 已迁到本模块

## 相关测试入口

- `src/factpy_kernel/tests/test_phase3_contracts_v1.py`

## 相关历史蓝图

- [`docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md) — Scenario B 作为近期锚点的选择依据
- [`docs/blueprints/archive/2026-03-18_ecss-vcd-compliance-delivery.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_ecss-vcd-compliance-delivery.md) — VCD/compliance matrix 的 data model 与 delivery 边界
- [`docs/blueprints/archive/2026-03-18_ecss-requirement-authoring-surface.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_ecss-requirement-authoring-surface.md) — shared preset owner 与写侧 helper 的当前任务边界
- [`docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md) — Scenario A 第一轮 temporal semantics contract 与 preset owner 边界
- [`docs/blueprints/archive/2026-03-18_scenario-a-uncertainty-and-confidence.md`](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_scenario-a-uncertainty-and-confidence.md) — Scenario A 第一轮 uncertainty lane 与 `ppm` scalar contract

## 当前文档

- `src/factpy_kernel/ecss/docs/01_overview.md`
  - shared ECSS preset 的公共入口、模块边界与当前限制。
