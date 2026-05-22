# Task Blueprint Audit: PyReason Seed Warning And Demo Reframe

- Blueprint: [2026-03-28_pyreason-seed-warning-and-demo-reframe.md](./2026-03-28_pyreason-seed-warning-and-demo-reframe.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Real-engine seed limitation recorded | Bounded node seeds appear to be accepted by PyReason but do not participate in propagation the way boolean seeds do. |
| 2026-03-28 | scoped | Scope frozen for warning + demo rewrite | Task limited to explicit runner warning, docs sync, and PyReason demo reframing. No silent semantic fallback. |
| 2026-03-28 | implemented | Runner warning and test coverage landed | `run_pyreason(...)` now warns once when rules are combined with non-default node seeds. Coverage includes bounded session node seeds and bounded `fact_def` inputs. |
| 2026-03-28 | implemented | Demo reframe completed | ECSS/DORA PyReason demos and notebook mirrors were rewritten to boolean/topology propagation stories with uncertainty kept as side-channel display data. |
| 2026-03-28 | implemented | Validation completed | Targeted runner/rule-ext suites passed with 50 tests; both rewritten demo scripts ran successfully to the expected PyReason import/fallback boundary in the current environment; notebook JSON structure checks passed. |

## Decision Notes

- The adapter will keep encoding bounded node facts as bounded facts. This task adds observability, not semantic coercion.
