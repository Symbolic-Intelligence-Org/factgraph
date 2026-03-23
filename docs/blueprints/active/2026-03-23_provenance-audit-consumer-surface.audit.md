# Audit Log: Provenance Audit Consumer Surface

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-23 | scoped | Blueprint created | Mirrors certainty-audit-static-delivery pattern: export-time materialization → JSONL → reader → query → static site. Souffle-only, adapter-local format, no core contract. |
| 2026-03-23 | working | Step 1 implemented | Added session-scoped derivation recipe cache keyed by `run_id` during `evaluate_runtime_derivation(...)`. Cache stays in `RuntimeSession` only and preserves distinct recipes when the same `derivation_id` is re-used across evaluations. |
| 2026-03-23 | working | Step 3 implemented | `audit.reader` now loads optional `provenance_trees.jsonl` into `AuditPackageData.provenance_trees`, and `AuditQuery` exposes `get_candidate_provenance_tree(candidate_id)` with backward-compatible empty-dict behavior for older packages. |
