# Task Blueprint: Design Branch Closeout

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/adapters/pyreason/rule_ext.py`
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `docs/blueprints/archive/README.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/audit/docs/README.md](../../../src/factpy_kernel/audit/docs/README.md)
  - [src/factpy_kernel/audit/docs/02_evidence_graph.md](../../../src/factpy_kernel/audit/docs/02_evidence_graph.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/adapters/docs/03_pyreason_adapter.md](../../../src/factpy_kernel/adapters/docs/03_pyreason_adapter.md)
- Audit Log:
  - [2026-03-28_design-branch-closeout.audit.md](./2026-03-28_design-branch-closeout.audit.md)

## 1. Problem

`EvidenceGraph` unified explainability work is implemented, but the branch still has a final closeout gap: PyReason/ProbLog `EvidenceGraph` only exists as an in-memory/runtime surface and cannot yet be exported, reloaded, and rendered through the audit package/static site path. In parallel, the deprecated `PyReasonRuleDef` compatibility wrapper still remains on the adapter surface, and the archive inventory no longer matches the actual archived blueprint set.

If these gaps remain, the branch is “feature complete” but not fully closed: the unified explainability DTO is not durably delivered across engines, the preferred `Rule.engine_ext` contract is still diluted by a legacy wrapper, and docs/index state does not match repository reality.

## 2. Goals

- Add a durable audit-package `EvidenceGraph` lane so accepted candidates with engine provenance can be exported, reloaded, queried, and rendered offline.
- Remove `PyReasonRuleDef` as an active adapter surface and leave `Rule(..., engine_ext=PyReasonRuleExt(...))` as the single rule-definition carrier.
- Refresh archive inventory/docs so the 2026-03-28 archive set is indexed correctly.
- Record explicit closeout decisions for deferred backlog items so this branch can end without hidden “maybe later in-place” scope.

## 3. Non-goals

- Introduce `ProbLogRuleExt` or any new ProbLog definition-time extension API.
- Refactor `body_confidences` out of the shared evaluate path.
- Add new provenance summary / NL presentation layers for ProbLog proof decomposition.
- Reopen archived blueprints instead of using this closeout slice as the final branch-level task.

## 4. Current Context

- 当前实现入口：
  - runtime export currently materializes `provenance_trees.jsonl` / `provenance_statuses.jsonl` only.
  - `AuditQuery` and static UI can consume Souffle provenance trees, but have no durable `EvidenceGraph` reader lane.
  - PyReason/ProbLog runtime candidate explain already exposes `ProvenanceEnvelope`, and engine-local converters already build `EvidenceGraph`.
  - `PyReasonRuleDef` remains in adapter code and tests as a deprecated compatibility wrapper.
  - `docs/blueprints/archive/README.md` inventory is stale and still says `最后更新：2026-03-27`.
- 当前已知约束：
  - Must keep audit package backward-compatible: new files are additive, not a replacement for existing provenance files.
  - Must not widen this slice into deeper ProbLog semantics or new presentation work.
  - Must update module docs after implementation.
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-28_evidence-graph-unified-explain.md`
  - `docs/blueprints/archive/2026-03-28_rule-engine-ext-alignment.md`
  - `docs/blueprints/archive/2026-03-28_engine-provenance-surface-spike.md`
  - `docs/blueprints/archive/2026-03-28_problog-timeout-eval-surface.md`

## 5. Proposed Shape

Add one new additive audit artifact, `audit/evidence_graphs.jsonl`, keyed by `candidate_id`. Export-time materialization should build `EvidenceGraph` whenever the accepted candidate has a durable engine provenance input that can be converted deterministically:

- `souffle`: derive from the already materialized proof tree
- `pyreason`: derive from stored provenance envelope
- `problog`: derive from stored provenance envelope

The audit reader/query/static path should gain a first-class `EvidenceGraph` reader lane:

- reader loads `evidence_graphs.jsonl`
- query exposes `get_candidate_evidence_graph(...)`
- static UI prefers the durable `EvidenceGraph` if present, and only falls back to Souffle tree reconstruction for older packages

For PyReason rule-definition cleanup, remove `PyReasonRuleDef` from the adapter code path and update remaining callers/tests/docs to use shared `Rule.engine_ext`. `compile_pyreason_rule(...)` and `run_pyreason(...)` should accept `Rule` directly.

Backlog closeout decisions (`ProbLogRuleExt`, `body_confidences` core debt, ProbLog provenance summary/NL`) should be recorded in this blueprint/audit as explicit deferrals/closures, not left as implicit future work on this branch.

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `EvidenceGraph` export is additive and must not break existing audit package readers or Souffle provenance delivery.
  - `Rule.engine_ext` remains the only rule-definition carrier introduced/kept by this slice.
  - Archived blueprints stay archived; this closeout blueprint owns any final branch-level decisions.
- 明确不做的内容：
  - No `ProbLogRuleExt`
  - No `body_confidences` core signature refactor
  - No new NL/tree-summary consumer for ProbLog proof decomposition
- 兼容性约束：
  - Older audit packages without `evidence_graphs.jsonl` must still load/render.
  - Existing Souffle provenance tree pages must keep working.

## 7. Acceptance

- [ ] Audit package writes and reloads `EvidenceGraph` rows for supported engines
- [ ] Static candidate pages render durable `EvidenceGraph` without requiring live runtime injection
- [ ] `PyReasonRuleDef` is removed from active adapter code/tests/docs
- [ ] Deferred backlog items are explicitly recorded as closed/deferred in blueprint/audit/docs
- [ ] 受影响模块 docs 已同步
- [ ] Archive inventory/docs match the current archived blueprint set

## 8. Implementation Plan

1. `service/runtime_v1.py` + audit export/readback: materialize `EvidenceGraph` rows at export time and thread them through package writing.
2. `audit/reader.py` + `audit/query.py` + `audit/static_ui.py`: add durable `EvidenceGraph` loading/query/render behavior with backward-compatible fallback.
3. `adapters/pyreason/*` + tests/docs: remove `PyReasonRuleDef` and migrate remaining call sites to `Rule.engine_ext`.
4. `docs/blueprints/archive/README.md` + affected module docs: record closeout decisions, refresh archive inventory, and sync current-truth docs.

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/README.md`
- `src/factpy_kernel/audit/docs/02_evidence_graph.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
- `docs/blueprints/archive/README.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - runtime audit export 现在会物化 `audit/evidence_graphs.jsonl`，覆盖 Souffle proof tree replay、PyReason provenance event log、以及 ProbLog provenance proof trace 三条来源。
  - `AuditQuery` / reader / static UI 现已具备 durable `EvidenceGraph` 读取与页面渲染能力；旧 package 仍保留 Souffle provenance-tree fallback。
  - `PyReasonRuleDef` 已从 adapter 代码与测试中移除；`Rule(..., engine_ext=PyReasonRuleExt(...))` 成为唯一 rule-definition 入口。
  - closeout 决策已明确：`ProbLogRuleExt`、`body_confidences` shared-core debt、以及 ProbLog provenance summary/NL 都不在本分支继续展开。
  - archive inventory 已补齐 2026-03-27/2026-03-28 条目并修正损坏行。
- 与 blueprint 不同的地方：
  - 为了让 audit static site 能对 provenance-bearing candidate 正常出页，`AuditQuery.get_candidate_evidence_tree(...)` 对 `pyreason_provenance_v1` / `problog_provenance_v1` 额外提供 degraded tree fallback。
- 为什么会有这些调整：
  - 仅增加 durable `EvidenceGraph` getter 还不够；static site 构建链首先要求 candidate tree DTO 可用，否则 provenance-bearing candidate 仍会在离线页面生成阶段失败。
- 归档说明：
  - 本 blueprint 已实现完成并于 2026-03-28 归档到 `docs/blueprints/archive/`，作为该设计分支的最终 closeout 条目。
