# Task Blueprint: Candidate Evidence Tree Salience / Impact

- Status: scoped
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_summary.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py`
  - `src/factpy_kernel/core/annotation/docs/README.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
- Audit Log:
  - [2026-03-20_candidate-evidence-tree-salience-impact.audit.md](./2026-03-20_candidate-evidence-tree-salience-impact.audit.md)

## 1. Problem

`candidate_evidence_tree` 现在已经具备：

- recursive proof
- winning-branch narrowing
- unresolved / boundary taxonomy
- engine degraded tree
- provenance-role taxonomy
- summary / narrative / NL explain

但母蓝图中对照 Rainbird 仍显著开放的一项能力是 `salience / impact breakdown`。

当前问题不是“要不要立刻做 salience UI”，而是更基础的三件事仍未冻结：

1. salience / impact 属于 **proof carrier schema**，还是 **annotation / value-semantics** 派生层
2. salience / impact 应在 **evaluate-time capture**，还是 **query/runtime/service-time derivation**
3. first-round 若要落地，它的输入来自：
   - 现有 tree / summary 的结构信号
   - 未来 certainty / weight 语义
   - 还是二者的组合

若这三点不先收口，后续很容易把结构性 provenance 与数值性语义混到一起。

## 2. Goals

- 先冻结 `candidate_evidence_tree salience / impact` 的归属与计算时机
- 明确 first-round 是否可能作为 **query-time derived surface** 单独推进
- 明确哪些输入是现有 contract 已具备的，哪些依赖尚不存在的 certainty / weight 基础设施
- 明确 native tree 与 engine degraded tree 在 first-round 是否需要同等覆盖

## 3. Non-goals

- 不在本轮直接扩 `SupportArtifact` 或 raw tree carrier
- 不在本轮直接引入 certainty evaluator / probability semantics
- 不把 `missing optional conditions` 一并并入这条线
- 不直接设计 salience chart UI
- 不把 Rainbird 的 certainty / impact 字段原样映射为本项目 contract

## 4. Current Context

### 4.1 当前已稳定的 tree carrier

当前 `candidate_evidence_tree` 已是正式 contract，具备：

- native recursive proof
- engine degraded tree
- `node_kind -> provenance-role` taxonomy
- summary / narrative / NL derived surfaces

换句话说，salience / impact 若继续推进，面对的不是空白 proof surface，而是一个已经相对稳定的 consumer-facing tree carrier。

### 4.2 母蓝图中的当前定位

母蓝图 [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md) 目前把 `Salience / Impact` 列为仍开放方向，并在 `§5.8 #3` 中明确指出：

- impact breakdown 更像 annotation / value-semantics
- 但它的计算依赖 proof carrier 提供条件权重和条件 certainty
- compute-time 若在 evaluate 时，会扩大 carrier schema
- compute-time 若在 query / service 时，则更像派生视图

### 4.3 Rainbird 参考的采纳边界

Rainbird 对这条线最有价值的启发是：

- “impact / salience” 是一种 **面向消费方的解释强化能力**
- 它不等于 proof tree 本体
- 它通常依赖某种 certainty / weight vocabulary

但本项目当前不会直接采纳 Rainbird 的 certainty 语义，也不会因比较材料而强行把 salience 塞进现有 carrier。

### 4.4 当前 annotation 真相

`src/factpy_kernel/core/annotation/` 当前仍是 internal / prototype：

- 有 `min-max` 路径置信度传播
- 有结构候选 / provenance 重建 helper
- 但不属于正式 `Store.evaluate(...)` contract

这意味着若 salience / impact 需要 certainty / weight 语义，它很可能不能直接假设已有稳定输入。

## 5. Proposed Shape

### 5.1 Positioning

这份蓝图当前是 **scoping / capability-decision draft**，不是 implementation blueprint。

它首先要回答的是：

- salience / impact 应挂在哪一层
- 应何时计算
- first-round 是否可在不改 carrier 的前提下成立

只有这三个问题收口后，才决定下一步是：

- doc-and-contract promotion
- query-time derived implementation slice
- 或更宽的 carrier / annotation capability line

### 5.2 Freeze Decisions

以下 5 个问题已在 scoping 阶段冻结：

**Q1: Owner layer → annotation / value-semantics 层**

salience / impact 的核心语义是”哪个条件贡献了多少 impact”——这是数值性的，不是结构性的 provenance。它不属于 proof carrier（carrier 回答”怎么推出的”），而属于 annotation / value-semantics 层。first-round 若落地，应以 query-time derived view 形式体现，与现有 summary → narrative → NL 链路模式一致。

**Q2: Compute-time → salience 本身在 query-time / read-time 计算**

salience / impact 这一层本身应保持为 query/read-time derived view，不直接塞进 proof carrier。但这不约束未来 certainty / weight 输入的来源——后者可以来自 evaluate-time capture 或 query-time 派生。salience 层与输入层的 compute-time 是独立决定。

**Q3: First-round 最小输入 → blocked on certainty / weight vocabulary**

现有 tree / summary 的结构信号（role counts、assertion count、recursive depth、completeness indicators）不足以产出有意义的 salience。真正的 impact breakdown 需要回答”条件 A 贡献了 40%”——这要求每个条件有 weight / certainty 输入，当前不存在。

若把结构信号硬包装成”structural salience proxy”，输出只会是 summary 的 rephrasing（”这个 candidate 有 5 条 assertion”），不是 salience。因此 first-round 不产出 implementation slice，只做 doc-and-contract freeze。

**Q4: Native / degraded coverage → deferred until prerequisites exist**

当前既然不实现，不必替未来 UI/DTO 预冻结过细 contract。但记录一条 invariant：degraded tree 未来不应伪装成 native impact breakdown。

**Q5: First-round 输出 → doc-and-contract position freeze，不产出 salience surface**

本蓝图的交付物是 4 条正式冻结结论：

1. `salience / impact` 属于 **annotation / value-semantics layer**
2. `salience / impact` 本身在 **query-time / read-time** 计算
3. 当前 **blocked on certainty / weight vocabulary**
4. first-round **不产出 implementation slice**，只做 doc-and-contract freeze

### 5.3 Pre-salience Baseline

当前 summary 已提供的结构信号作为 pre-salience baseline 记录在案：

- `node_count_by_role` — role 分布
- `witness_assertion_count` — 证据深度
- `rule_ref_count` — 规则链复杂度
- `recursive_depth` — 证明深度
- `has_unresolved` / `has_boundary` — 完整性信号

未来 salience 将在这个 baseline 之上叠加 certainty / weight 语义。当前 baseline 不是 salience，只是 salience 的结构前提。

### 5.4 Why This Needs A Separate Blueprint

这条线若不单独收口，会与以下方向互相污染：

- `missing optional conditions`
- `certainty evaluator`
- `engine witness parity`
- `annotation prototype -> runtime contract`

因此它需要先作为独立 capability line，把“salience 的位置”单独冻结。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不把 Rainbird certainty semantics 直接当作本项目字段
  - 不把 salience 问题偷换成 full annotation-system 设计
  - 不在 draft 阶段重开 `SupportArtifact` / raw tree schema
- 明确不做的内容：
  - 不设计视觉图表
  - 不把 optional-condition semantics 一起塞进本轮
  - 不在本轮承诺 engine adapter 产出新 witness 数据
- 兼容性约束：
  - 现有 `candidate_evidence_tree` raw / summary / narrative / NL surface 不回退
  - 若 first-round 最终是 query-time derived view，则必须是 additive，不破坏现有 summary/narrative/NL contract

## 7. Acceptance

- [x] 已冻结 salience / impact 的 owner layer → annotation / value-semantics
- [x] 已冻结 salience / impact 的 compute-time 选择 → query-time / read-time
- [x] 已明确 first-round 最小输入来自现有 tree/surfaces 还是依赖 future certainty/weight → blocked on certainty/weight
- [x] 已明确 native / degraded 覆盖 → deferred until prerequisites exist
- [x] 已明确下一步 → doc-and-contract position freeze，不产出 implementation slice

## 8. Implementation Plan

1. 回读母蓝图 `§5.8 #3` 与 annotation prototype 真相，确认当前开放问题的精确边界
2. 先冻结 owner layer：carrier vs annotation/value-semantics vs query-time derived view
3. 再冻结 compute-time：evaluate-time vs query/runtime-time
4. 再冻结 first-round 最小输入：结构 proxy vs certainty/weight dependency
5. 明确 native / degraded 覆盖边界
6. 基于上述答案，决定是否需要 child implementation blueprint

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（若 owner / compute-time 成为正式 contract）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若形成 runtime-derived surface）
- `src/factpy_kernel/audit/docs/01_overview.md`（若 audit/static 进入 first-round scope）

## 10. Outcome / Deviations

- 最终落地结果：doc-and-contract position freeze。4 条正式冻结结论（owner layer, compute-time, blocked prerequisite, no implementation slice）。
- 与 blueprint 不同的地方：draft 阶段曾考虑 "structural salience proxy" 作为 first-round 的可能路径；scoping 讨论后判定现有结构信号不足以产出有意义的 salience，遂放弃 proxy 方案。
- 为什么会有这些调整：诚实评估后，结论是 salience 的真正输入（certainty / weight）当前不存在，硬造 proxy 只会是 summary 的 rephrasing。
- 归档说明：作为 decision-only archive 收归。未来若 certainty / weight 基础设施就绪，应开新的 implementation blueprint，以本蓝图冻结的 owner/compute-time 结论为前提。
