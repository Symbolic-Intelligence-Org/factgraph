# Task Blueprint Audit: Engine Provenance Surface Spike

- Blueprint: [2026-03-28_engine-provenance-surface-spike.md](./2026-03-28_engine-provenance-surface-spike.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Opened the next multi-engine phase around provenance delivery after both engine lines reached formal eval-surface parity. |
| 2026-03-28 | scoped | Scope frozen | Freeze the spike around shared provenance target and dispatch shape; defer actual implementation. |
| 2026-03-28 | scoped | Baseline re-verified | Full regression rerun from handoff baseline: 533 tests passed. |
| 2026-03-28 | scoped | Research findings recorded | Confirmed that current candidate explain is tree-first via `SupportArtifact`, while ADR-13 and PyReason findings require an engine-native provenance lane. |
| 2026-03-28 | implementing | Core provenance lane landed | Added `ProvenanceEnvelope`, Store provenance registry/readback, and support-kind dispatch split between support artifacts, provenance envelopes, and degraded fallback. |
| 2026-03-28 | implementing | PyReason runtime provenance landed | `pyreason_engine_eval(...)` now forces `atom_trace=True`, upgrades traced candidates to `pyreason_provenance_v1`, and exposes event-log provenance via runtime `explain_ref(kind="candidate")`. |
| 2026-03-28 | implementing | ProbLog runtime provenance landed | Added `ProbLogTraceV0` parser over CLI `--trace`, upgraded traced candidates to `problog_provenance_v1`, and exposed proof-trace provenance via the same runtime candidate explain lane. |
| 2026-03-28 | implemented | Module docs synced | Updated current-truth docs in `core`, `service`, and adapter docs to record the new provenance lane and the explicit tree-surface limitation. |
| 2026-03-28 | implemented | Full regression green | `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'` passed: 538 tests, OK. |
| 2026-03-28 | archived | Blueprint archived | Runtime provenance spike is complete; audit/static consumer parity remains explicitly deferred. |

## Decision Notes

- Reuse the current first hop `candidate_id -> (support_digest, support_kind)`; do not introduce a parallel candidate-provenance handle unless implementation proves it necessary.
- Do not repurpose `SupportArtifact` into a generic engine provenance union; keep it as the native/Souffle witness carrier.
- First runtime provenance target should be `explain(kind="candidate")`, not `explain-tree(kind="candidate")`, because PyReason is event-log-native.
- Use `pyreason_provenance_v1` / `problog_provenance_v1` naming rather than `*_witness_v1`, to keep tree-bearing witness kinds distinct from engine-native flat provenance envelopes.
- Keep `PyReason atom_trace` adapter-internal; shared evaluate surface remains frozen at `engine_options={"timesteps": ...}`.
