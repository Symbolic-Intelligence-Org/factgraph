# Task Blueprint: Runtime Traceability Evidence-Tree Realignment

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/audit`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [docs/blueprints/active/2026-03-17_durable-artifact-storage.md](./2026-03-17_durable-artifact-storage.md)
  - [docs/blueprints/archive/2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-18_runtime-traceability-evidence-tree-realignment.audit.md](./2026-03-18_runtime-traceability-evidence-tree-realignment.audit.md)

## 1. Problem

`runtime-traceability-explainability` 母蓝图打开时，仓库还处于较早的 explainability 阶段。此后已经落地的一批 child slices，显著改变了当前基线：

- native `SupportArtifact` capture / readback 已存在
- service explain 统一入口与 `candidate` / `rule_run` handle 已存在
- `rule_run` 的 `raw -> summary -> narrative -> NL -> audit/static` delivery spine 已闭环
- engine explain 第一轮已明确为 `degraded/no-witness` 语义，而不是“假装 parity”
- 多个 domain / source-shape / evidence-pattern walkthrough 已验证当前 substrate 边界

如果不先做一次母蓝图对齐，就直接讨论或实现 Rainbird-like evidence tree，会出现两个问题：

1. 容易把 evidence tree 误读为“新计划”，而不是现有母蓝图里原本就有的 `proof-tree / support-graph` 下一阶段。
2. 容易继续引用母蓝图里已经被后续实现部分更新的旧判断，尤其是 delivery shape、proof entry handle、以及 child-slice 依赖关系。

## 2. Goals

- 明确 evidence tree 属于现有 `runtime-traceability-explainability` 母蓝图的原计划下一阶段，而不是新的母计划。
- 把母蓝图中的“当前实现基线”与“剩余真正未落地的部分”重新对齐。
- 记录 evidence tree 与其他 active 母蓝图的关系，特别是：
  - `overall-system-blueprint`
  - `temporal-hybrid-reasoning-blueprint`
  - `durable-artifact-storage`
- 为后续 evidence-tree implementation slice 提供准确的起点描述。

## 3. Non-goals

- 不在本轮开启 evidence tree 的实现。
- 不在本轮设计新的 proof-tree DTO、service endpoint 或 static UI。
- 不在本轮修改 runtime/service/audit/core contract。
- 不在本轮把 `T2`、judgment、`U2`、snippet/span、source-linkage 等 deferred gaps 升级为 blocker。
- 不归档或重写现有母蓝图；只做对齐更新。

## 4. Current Context

- 当前相关 child slices 已归档并落地：
  - `support-artifact-native-capture`
  - `support-artifact-readback`
  - `explain-ref-service-unification`
  - `rule-run-trace-schema-contract`
  - `engine-witness-parity`
  - `runtime-rule-run-explain-summary-api`
  - `audit-rule-run-explain-summary-export`
  - `rule-run-explain-narrative`
  - `rule-run-explain-narrative-parity`
  - `rule-run-nl-explain`
- 当前模块 docs 已明确记录的实现真相包括：
  - `candidate_id -> support_digest/support_kind`
  - `rule_run_id -> RuleTraceArtifact`
  - runtime `raw / summary / narrative / NL`
  - audit/static `rule_run_id` proof-entry
- 当前 active 母蓝图之间的关系：
  - `overall-system-blueprint` 已把 runtime traceability/explainability 列为既有子方向
  - `temporal-hybrid-reasoning-blueprint` 仍主要约束 `T2/judgment/U2` 类语义扩张
  - `durable-artifact-storage` 仍是 explain carrier durability 的邻接蓝图，但不自动阻塞 first-round evidence tree

## 5. Proposed Shape

本轮对齐只做一件事：把母蓝图的“当前位置”收口成准确表述。

### 5.1 Adopted Position

evidence tree 应被明确视为：

- `runtime-traceability-explainability` 母蓝图内原本就存在的 `proof-tree / support-graph` 下一子阶段；
- 不是新的母计划；
- 也不是必须先等 `temporal-hybrid` 或 `durable-artifact-storage` 全部收口之后，才能开始讨论的工作。

### 5.2 Alignment Changes To Record In The Parent Blueprint

母蓝图应明确记录：

1. `audit-log-first` / delivery spine 的第一阶段已基本完成
   - `raw -> summary -> narrative -> NL -> audit/static` 已经是当前事实
2. proof entry handle 已不再是完全空白
   - `candidate_id + support_digest/support_kind`
   - `rule_run_id`
3. 近期剩余真正未落地的 traceability/explainability 大项，应重新聚焦为：
   - recursive evidence tree / support-graph carrier
   - tree-oriented delivery
   - engine true-witness parity
   - annotation/value-semantics formalization
4. 若下一步要开 implementation slice，最自然的方向是 native-first evidence tree，而不是继续补同层 walkthrough 或提前打开 unrelated capability gap

### 5.3 Relationship To Other Active Blueprints

- `overall-system-blueprint`
  - evidence tree 继续属于既有的 `Runtime Kernel / Delivery / Audit` 主线，不改变总图分层。
- `temporal-hybrid-reasoning-blueprint`
  - 除非 evidence tree 试图同时解决 ordering semantics、state transition、judgment 或 graded uncertainty，否则它不是前置阻塞。
- `durable-artifact-storage`
  - 当前导出/readback substrate 已足够支撑 native-first evidence tree v1 的讨论与第一轮实现。
  - cross-session live durability 可继续作为邻接问题后置。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 本轮是 doc-only alignment。
  - 模块 docs 继续是当前实现真相。
  - 母蓝图仍保持母图/讨论入口角色，不被这次 alignment 改写成具体实现 blueprint。
- 明确不做的内容：
  - 不直接起草 evidence tree DTO
  - 不新增 service 或 audit contract
  - 不把外部对照文档写成当前真相
- 兼容性约束：
  - alignment 结论必须与现有模块 docs 对齐；
  - 若母蓝图旧判断与模块 docs 冲突，以模块 docs 为准，并在母蓝图中显式修正。

## 7. Acceptance

- [x] 已明确 evidence tree 属于现有 `runtime-traceability-explainability` 母蓝图的原计划下一阶段
- [x] 母蓝图已补充当前实现基线与剩余未落地部分的对齐说明
- [x] 已明确 evidence tree 与其他 active 母蓝图的关系，且没有制造新的前置阻塞
- [x] 本轮没有越过 doc-only alignment 的边界

## 8. Implementation Plan

1. 新建一个 doc-only alignment blueprint，收口本轮任务范围。
2. 更新 `runtime-traceability-explainability` 母蓝图，补充当前实现对齐说明与 next-stage positioning。
3. 在母蓝图 audit 中记录这次 realignment，明确 evidence tree 属于原计划下一阶段。
4. 完成本蓝图 `Outcome / Deviations` 并归档。

## 9. Docs To Update

- `docs/blueprints/archive/2026-03-17_runtime-traceability-explainability-blueprint.md`
- `docs/blueprints/archive/2026-03-17_runtime-traceability-explainability-blueprint.audit.md`
- `docs/blueprints/active/2026-03-18_runtime-traceability-evidence-tree-realignment.md`
- `docs/blueprints/active/2026-03-18_runtime-traceability-evidence-tree-realignment.audit.md`

## 10. Outcome / Deviations

- 最终落地结果：已完成 doc-only alignment；`runtime-traceability-explainability` 母蓝图现在明确记录了当前 delivery closure 基线，并把 evidence tree 定位为原计划中的 `proof-tree / support-graph` 下一子阶段。
- 与 blueprint 不同的地方：无
- 为什么会有这些调整：无
- 归档说明：归档到 `docs/blueprints/archive/2026-03-18_runtime-traceability-evidence-tree-realignment.*`
