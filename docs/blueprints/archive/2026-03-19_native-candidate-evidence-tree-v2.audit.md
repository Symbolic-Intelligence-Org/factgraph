# Task Blueprint Audit: Native Candidate Evidence Tree V2

- Blueprint: [2026-03-19_native-candidate-evidence-tree-v2.md](./2026-03-19_native-candidate-evidence-tree-v2.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened the next candidate evidence-tree slice after v1 shipped. Scope is intentionally narrowed to deepening the tree body itself: richer node taxonomy, sectioned recursion, and better nested rendering, while keeping graph, engine parity, salience, and fine-grained provenance deferred. |
| 2026-03-19 | scoped | Scope freeze | Confirmed that V2 keeps the same `explain-tree` entry handle, accepts a controlled root-level shape change via `support_section`, and only emits `rule_ref_section` when `SupportArtifact.rule_refs` is non-empty. |
| 2026-03-19 | implemented | Sectioned tree body shipped | Refactored the shared candidate tree builder to emit `support_section` plus optional `rule_ref_section`, updated static rendering to be node-kind-aware, and added runtime tests for both the common no-rule-ref case and explicit rule-ref nodes. |
| 2026-03-19 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 77 tests after the v2 shape change. |
| 2026-03-19 | archived | Blueprint archived after docs sync | Updated core/service/audit module docs to describe the current sectioned candidate tree shape, then archived the task blueprint. |

## Decision Notes

- 2026-03-19: `candidate evidence tree v2` is a continuation of the existing runtime-traceability mother blueprint, not a new plan.
- 2026-03-19: V2 should deepen the tree body first, not open new capability axes such as graph, engine parity, annotation/value semantics, or finer provenance.
- 2026-03-19: The v1 assertion leaf ownership boundary remains load-bearing; richer tree structure must not turn leaves into embedded full assertion dumps.
- 2026-03-19: The new section layer is treated as an acceptable, bounded shape change rather than pure additive enrichment, because v1 has no external consumers yet and the top-level entry / leaf ownership boundaries remain stable.
- 2026-03-19: `rule_ref_section` must not be emitted as an empty placeholder; section nodes only appear when they carry real children.
