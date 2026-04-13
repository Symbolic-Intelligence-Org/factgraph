# Task Blueprint Audit: Examples Demo Rationalization

- Blueprint: [2026-03-31_examples-demo-rationalization.md](./2026-03-31_examples-demo-rationalization.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-31 | draft | Blueprint created | Scope: repair examples learning path and rationalize notebook prose vs runtime output. |
| 2026-03-31 | scoped | Scope frozen | Priorities: fix missing `03` references, then refactor flagship notebook `07`, then clean engine-specific notebooks. |
| 2026-03-31 | implementing | Example set rationalized | Updated `README`, repaired `02`/`04` learning-path references, and refactored `04`/`05`/`06`/`07` so markdown carries prose while prints remain data-driven. |
| 2026-03-31 | implemented | Validation complete | Notebook JSON parsed cleanly, all active code cells compiled, stale `03` references were removed, and the active examples set no longer contains pure-string `print(...)` calls. |

## Decision Notes

- Initial priority: fix broken `03` references and the flagship notebook `07` before broader cleanup.
- Chose not to restore a new public `03` notebook. The durable truth is that certainty / evidence-tree walkthrough material currently lives in notebooks `04` and `07`, and the examples index now says so explicitly.
- Cleared stale execution counts / outputs from active notebooks touched in this task so rendered notebook state does not contradict the updated code cells.
