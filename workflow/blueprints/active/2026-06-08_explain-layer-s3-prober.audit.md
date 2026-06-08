# Audit Log: S3 — Prober Main Body (application/explain/ + EvidenceTree)

- Blueprint: [2026-06-08_explain-layer-s3-prober.md](./2026-06-08_explain-layer-s3-prober.md)
- Status: draft

---

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-06-08 | blueprint created (draft) | Preflight source-read complete: `audit/evidence_graph.py` (old flat DAG), `evaluate_result.py` Explanation class, `diagnose_runtime._extend_env_with_atom` dispatcher. Q-S3-A/B/C tentative resolutions written. Dependencies S0/S1/S2/Certainty all ✅. |

---

## Decision Notes

### D-1: New EvidenceGraph lives in application/explain/ (Q-S3-A)
**Decision**: New `EvidenceGraph` (paths model) defined in `application/explain/evidence_tree.py`, separate from `audit/evidence_graph.py`. S5 switches `Explanation.evidence` type to the new one. S7 removes old.

**Rationale**: Zero src/ touch in S3. Clear migration path. Python allows same class name in different modules.

### D-2: EvidenceProbeResult as prober return type (Q-S3-B)
**Decision**: `probe_native` returns `EvidenceProbeResult(paths, certainty)`. `EvidenceGraph(graph_id, engine, subject_binding, ...)` assembled by S5 wire-up layer.

**Rationale**: Keeps prober pure (no identity info); S5 adds context.

### D-3: probe_native receives RuleExprLoweringPlan (Q-S3-C)
**Decision**: Caller (S5) lowers `Rule → RuleExprLoweringPlan` and passes to `probe_native`. S3 does not call `lower_rule_expr` internally.

**Rationale**: Avoids duplicate lowering; caller already has the plan from evaluate path.
