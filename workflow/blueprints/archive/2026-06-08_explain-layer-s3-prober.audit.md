# Audit Log: S3 — Prober Main Body (application/explain/ + EvidenceTree)

- Blueprint: [2026-06-08_explain-layer-s3-prober.md](./2026-06-08_explain-layer-s3-prober.md)
- Status: implemented

---

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-06-08 | blueprint created (draft) | Preflight source-read complete: `audit/evidence_graph.py` (old flat DAG), `evaluate_result.py` Explanation class, `diagnose_runtime._extend_env_with_atom` dispatcher. Q-S3-A/B/C tentative resolutions written. Dependencies S0/S1/S2/Certainty all ✅. |
| 2026-06-08 | Q-S3-A locked; scoped | User: alpha 版本完全替换，不双轨。旧 `EvidenceGraph(nodes,edges)` 在 S3 中删除；S7 并入 S3。Q-S3-B/C 委托 Codex 在实施中决策。Step 4.6 scope freeze. |
| 2026-06-08 | impl branch cut (Step 4.7) | `v0.2.0-impl-prober-evidence-tree-2026-06-08` forked from `master @ 562c7419`. Q-S3-B/C 由 Codex 在实施时决策。 |
| 2026-06-08 | implemented (Step 4.8) | Impl `69593d36` replaced the old flat DAG audit graph with `EvidenceGraph(paths)`, added `application/explain` prober/DTOs, migrated adapter converters, and verified focused tests/imports/diff-check. |

---

## Decision Notes

### D-1: Complete replacement, no dual-track (Q-S3-A) — LOCKED
**Decision**: Old `EvidenceGraph(nodes, edges, root_node_id, support_kind)` + `EvidenceNode` + `EvidenceEdge` + flat DAG serializers/renderers fully removed in S3. New `EvidenceGraph(paths)` + `EvidenceTree` family replaces them. S7 slice dissolved; cleanup is S3's responsibility. File placement (whether in `audit/evidence_graph.py` or `application/explain/evidence_tree.py`) delegated to Codex.

**Rationale**: Alpha version — no historical compatibility burden. Cleaner codebase outweighs dual-track complexity. User directive 2026-06-08.

### D-2: EvidenceProbeResult as prober return type (Q-S3-B)
**Decision**: `probe_native` returns `EvidenceProbeResult(paths, certainty)`. `EvidenceGraph(graph_id, engine, subject_binding, ...)` assembled by S5 wire-up layer.

**Rationale**: Keeps prober pure (no identity info); S5 adds context.

### D-3: probe_native receives RuleExprLoweringPlan (Q-S3-C)
**Decision**: Caller (S5) lowers `Rule → RuleExprLoweringPlan` and passes to `probe_native`. S3 does not call `lower_rule_expr` internally.

**Rationale**: Avoids duplicate lowering; caller already has the plan from evaluate path.

### D-4: Implementation file layout
**Decision**: Canonical DTO/prober code lives in `src/factgraph/application/explain/`. `src/factgraph/audit/evidence_graph.py` remains as a compatibility import/serialization module for the new `EvidenceGraph(paths)` shape.

**Rationale**: Keeps the prober in application space while preserving existing audit import paths for callsites that only need the evidence graph DTO/JSON helpers.

### D-5: Adapter converter migration in S3
**Decision**: Souffle, ProbLog, and PyReason provenance converters were updated in S3 to return the new paths model.

**Rationale**: Q-S3-A complete replacement would otherwise leave active converter imports/runtime paths broken. Rich per-engine atom/rule filling remains S6 scope.
