# Task Blueprint: Runtime Traceability And Explainability Blueprint

- Status: draft
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/audit`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/service`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/active/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
  - [docs/blueprints/archive/2026-03-17_souffle-annotation-kernel-prototype.md](../archive/2026-03-17_souffle-annotation-kernel-prototype.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/docs/04_public_contract_v1.md](../../../src/factpy_kernel/core/docs/04_public_contract_v1.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-17_runtime-traceability-explainability-blueprint.audit.md](./2026-03-17_runtime-traceability-explainability-blueprint.audit.md)

## 1. Problem

当前仓库已经分别讨论和实现了几块相关能力，但还没有一份专门蓝图来回答一个更聚焦的问题：

- `audit-log`、`proof-tree`、`graph-based` 这三类可解释性/追溯性形态，项目近期到底应如何分层和比较？
- `annotation` 在这件事里是“主要载体”“附属语义值”还是“局部 helper”？
- `CandidateSet`、`support/provenance`、`audit package`、以及可能的 proof/support graph 之间，未来是否需要一个更清晰的运行时承载模型？

当前已有材料给出了方向，但没有给出单独的讨论入口：

- 母蓝图已经提出 `audit-log -> proof-tree -> graph-based` 的优先级建议；
- annotation spike / prototype 已经证明 annotation 对某些 workload 有价值；
- 但仓库里仍缺少一份蓝图，专门比较不同 traceability / explainability 承载方式的优缺点、边界和后续实验入口。

因此，本蓝图的目标不是立即决定一种方案，而是把“运行时追溯与可解释性应该如何承载”这件事单独收口为一个可讨论、可拆解的主题。

## 2. Goals

- 建立一个专门讨论 runtime traceability / explainability 承载模型的子蓝图入口。
- 明确区分当前已存在的几种事实：
  - 现有 `audit` 与 `CandidateSet` 契约
  - 已实现的 prototype 级 annotation 摘要
  - 尚未形成独立 contract 的 proof/support graph 设想
- 比较若干可能的承载形态，而不是预先假定某一种为正确路线。
- 为后续是否要开实现型子蓝图提供判断问题，例如：
  - 是否需要 runtime-governance 级 contract 扩展
  - 是否值得引入 support/proof graph
  - annotation 是否应进入正式 runtime / audit 口径

## 3. Non-goals

- 不在本蓝图中决定“必须采用 support/proof graph first + annotation second”。
- 不在本蓝图中把 annotation 提升为唯一的解释/追溯载体。
- 不在本蓝图中修改正式 `Store.evaluate(...)`、`CandidateSet`、`audit` package、SDK 或 service 契约。
- 不在本蓝图中直接实现新的 runtime capability。
- 不把 `PyReason`、`Souffle`、`ProbLog` 任一引擎的语义假设直接写成系统真相。

## 4. Current Context

- 当前实现入口：
  - `core` 已提供 `CandidateSet`、accept、query、view projector audit 等主线能力。
  - `audit` 已作为离线审计消费层存在，读取导出的 package 做查询与静态展示。
  - `core/annotation` 当前是 internal / prototype，只覆盖 `Workload A + C` 的最小 annotation 能力。
- 当前已知约束：
  - `CandidateSet.confidence` 仍是窄字段，不等价于完整解释对象。
  - `ProjectorAudit` 目前只提供轻量统计，不是 proof/provenance contract。
  - `audit` 当前主要消费离线 package，不直接暴露 live runtime trace。
  - prototype 级 provenance 摘要已经存在，但它们仍按 workload 区分，不是统一 carrier。
- 当前相关历史蓝图：
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
    - 已证明 annotation 在部分 workload 上有价值，但价值具有 workload 依赖性。
  - [docs/blueprints/archive/2026-03-17_souffle-annotation-kernel-prototype.md](../archive/2026-03-17_souffle-annotation-kernel-prototype.md)
    - 已将 A/C 的 annotation 能力沉淀为 internal prototype。
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
    - 已提出 `audit-log -> proof-tree -> graph-based` 的长期排序，但尚未展开承载模型本身。

## 5. Proposed Shape

### 5.1 Positioning

本蓝图更适合作为一个 **runtime-governance 侧的探索子蓝图**：

- 关注 runtime 结果如何被解释、追溯、导出和消费；
- 不默认把问题缩减为“增加一个 annotation 字段”；
- 也不默认把问题放大成“必须先做完整 graph engine”。

### 5.2 Candidate Design Directions To Compare

本蓝图建议至少比较以下几种方向，而不是先选定其一：

1. `CandidateSet-first`
   - 保持当前 candidate identity 为主轴；
   - 逐步丰富 support/provenance 摘要与 confidence/annotation 载体。

2. `audit-log-first`
   - 继续把 run / candidate / decision / apply event 作为主追溯链；
   - proof-tree 或 graph-based 解释作为 audit 的派生视图。

3. `proof-tree / support-graph-oriented`
   - 探索是否需要一个更显式的 proof/support object；
   - 由 candidate、annotation、audit 引用或投影到该对象。

4. `hybrid`
   - candidate identity 仍留在 runtime；
   - annotation 负责语义值；
   - audit 负责 run/session/decision 可追溯性；
   - proof/support graph 仅在需要更强 explainability 时作为补充层。

### 5.3 Questions This Blueprint Should Clarify

1. explainability 与 traceability 的最小公共需求是什么？
   - “为什么成立”
   - “依赖了什么”
   - “由哪次 run / 规则 / decision 产生”
   - “为什么强度是这个值”

2. annotation 在这条链上更像什么？
   - 候选结果的附加语义值
   - proof/support object 上的属性
   - audit package 的派生摘要
   - 或仅在特定 workload 中成立的局部 helper

3. 当前 contract 缺的究竟是哪一段？
   - `CandidateSet -> richer support summary`
   - `runtime -> audit package`
   - `audit-log -> proof-tree`
   - `proof/support graph -> UI / service delivery`

4. 哪类承载方式最适合近期对外演示，哪类适合中期内核建设？

### 5.4 Likely Documentation And Implementation Touchpoints

若后续从讨论进入实现，最可能触及的区域是：

- `src/factpy_kernel/core/derivation`
- `src/factpy_kernel/core/store`
- `src/factpy_kernel/core/view`
- `src/factpy_kernel/core/annotation`
- `src/factpy_kernel/audit`
- `src/factpy_kernel/service`

但本蓝图当前阶段不要求这些模块立刻修改，只要求把“哪些点未来可能需要 contract 级变更”讲清楚。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 当前模块 docs 仍然是实现真相。
  - `audit` 仍然是当前的离线审计消费层，不因本蓝图被重写为 live runtime layer。
  - `core/annotation` 仍然是 internal / prototype；其存在不自动意味着正式 contract 已决定。
  - 本蓝图只讨论承载模型，不把任何单个方向提前写成默认路线。
- 明确不做的内容：
  - 不在当前阶段起草新的 stable DTO。
  - 不在当前阶段定义完整 proof/support graph schema。
  - 不直接把此蓝图等同于 `PyReason` 集成、temporal engine 或 graph visualization 项目。
- 兼容性约束：
  - 若后续进入实现，必须复用现有 `candidate / support / provenance / audit` 词汇与边界，而不是重新发明平行语义。
  - 若未来需要新增承载层，必须明确它与 `CandidateSet` 和 `audit package` 的映射，而不是以 side-channel 存在。

## 7. Acceptance

- [ ] 已形成一份专门讨论 runtime traceability / explainability 承载模型的子蓝图
- [ ] 蓝图已明确列出若干候选方向，而不是把某一种写成既定路线
- [ ] 蓝图已明确指出 annotation prototype、当前 audit、以及潜在 proof/support graph 之间的边界
- [ ] 已为后续实现型子蓝图或 contract 讨论留出清晰入口

## 8. Implementation Plan

1. 先建立本讨论型蓝图，明确问题、候选方向和边界，不直接冻结实现方案。
2. 在后续讨论中，把“现有 contract 真相”和“仍需探索的问题”分开记录，避免把设想误写成现状。
3. 若后续对某个方向形成足够强的共识，再拆分为实现型子蓝图，例如 runtime integration、audit contract、proof/support carrier 等。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.audit.md`
- `docs/blueprints/active/2026-03-15_overall-system-blueprint.md`
- `docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
