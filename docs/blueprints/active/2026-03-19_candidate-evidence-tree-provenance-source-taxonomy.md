# Task Blueprint: Candidate Evidence Tree Provenance / Source Taxonomy

- Status: draft
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/static_ui.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
- Audit Log:
  - [2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.audit.md](./2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.audit.md)

## 1. Problem

`candidate_evidence_tree` 现在已经有稳定的 node taxonomy、recursive proof contract、winning-branch narrowing、unresolved/boundary taxonomy，以及 engine degraded tree shape，但它仍缺一个正式的 provenance/source taxonomy。

当前 tree surface 上只有零散的 `support_kind`、`witness_status` 和 node-kind 自身，consumer 可以看出“这是 native recursive proof 还是 engine degraded”，却没有一套正式字段来表达“这个 node 的来源/承载类型是什么”。这会让 native recursive nodes、engine degraded nodes、legacy fallback nodes 的来源语义继续散落在说明文档和推断逻辑里，而不是成为显式 contract。

## 2. Goals

- 冻结 `candidate_evidence_tree` 是否需要正式的 `source_kind` / `provenance_kind` 类字段。
- 确定 first-round provenance/source taxonomy 适用于哪些 node kinds。
- 明确 native recursive proof 与 engine degraded tree 是否共享同一套 vocabulary。
- 明确 provenance/source 是 carrier contract 还是 display-only contract。

## 3. Non-goals

- 不重开 recursive proof DTO、winning-branch narrowing、或 unresolved taxonomy。
- 不直接展开 snippet/span 级 finer provenance。
- 不直接展开 source-linkage graph 或 proof graph。
- 不把 engine degraded tree 提升成 full witness parity。
- 不修改 engine adapter、native evaluator 或 SupportArtifact capture 语义。

## 4. Current Context

- 当前 tree surface 已有：
  - native recursive proof nodes
  - unresolved/boundary terminals
  - engine degraded `degraded_support`
- runtime / audit / static 共享同一 tree carrier，但没有正式的 provenance/source enum。
- engine degraded surface 当前主要依赖：
  - `support_kind in {"engine_no_witness_v1", "none"}`
  - `witness_status="degraded"`
- native recursive nodes 当前主要依赖 node kind 自身和 support-side carrier，而不是显式 source taxonomy。
- 外部参照：
  - [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md) 明确指出当前体系还缺 `fact source taxonomy`，这是可借鉴的设计输入，但不是当前 contract。

## 5. Proposed Shape

First-round 先冻结 very narrow 的 capability questions，而不直接承诺字段落地：

1. `candidate_evidence_tree` 是否需要一套正式 `source_kind` / `provenance_kind` vocabulary？
2. 若需要，哪些 node kinds 必须携带它：
   - `candidate_result`
   - `support_section`
   - native proof leaf / section children
   - `degraded_support`
   - legacy flat `rule_ref`
   - recursive terminals
3. native recursive proof 与 engine degraded node 是否共享同一 vocabulary，还是只共享上层 category？
4. provenance/source taxonomy 是 tree carrier contract，还是 static/runtime display layer 才需要的派生标签？
5. legacy fallback 没有 recursive child-proof contract 时，是否也应进入同一 source taxonomy？

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不让 `source/provenance taxonomy` 偷偷演变成 graph、snippet/span、或 full source-linkage contract。
  - 不让这条线重新定义 `support_kind` 或 `witness_status` 的现有语义。
  - 不把 `unresolved_support` / `recursion_boundary` 的 reason taxonomy 和 source taxonomy 混成一个字段。
- 明确不做的内容：
  - 不在 first-round 讨论 UI 配色、icon、或 presentation wording。
  - 不把 ingest/provenance validation 的 assertion-meta 语义直接搬到 tree node 上。
- 兼容性约束：
  - runtime / audit / static 若采纳 taxonomy，应共享同一底层 contract。
  - legacy tree readback 不能因为 taxonomy 讨论而失效。

## 7. Acceptance

- [ ] 已明确是否需要正式 `source_kind` / `provenance_kind` contract，而不是继续依赖隐式推断。
- [ ] 已冻结 first-round taxonomy 覆盖的 node 范围与非目标范围。
- [ ] 已明确 native recursive proof、engine degraded、legacy fallback 的 vocabulary 关系。
- [ ] 已明确 provenance/source 是 carrier contract 还是 display-only contract。
- [ ] 若采用外部参考结论，blueprint audit 已记录“采纳了什么、没有采纳什么”。

## 8. Implementation Plan

1. 盘点当前 tree surface 已有的来源暗示字段和 node kinds。
2. 结合 Rainbird source taxonomy 参考，提出 first-round freeze options。
3. 冻结 owner / scope / compatibility 边界，推进到 `scoped`。
4. 若最终需要代码实现，再决定是否继续在本蓝图内实现，还是拆 implementation blueprint。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（若 taxonomy 成为正式 contract）
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若 runtime tree surface 新增 provenance/source 语义）
- `src/factpy_kernel/audit/docs/01_overview.md`（若 audit/static 消费同一 taxonomy）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
