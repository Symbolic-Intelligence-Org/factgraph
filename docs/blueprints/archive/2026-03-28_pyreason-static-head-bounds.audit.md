# Task Blueprint Audit: PyReason Static Head Bounds

- Blueprint: [2026-03-28_pyreason-static-head-bounds.md](./2026-03-28_pyreason-static-head-bounds.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Captured the newly validated PyReason head-annotation behavior and scoped the adapter response. |
| 2026-03-28 | scoped | Scope frozen | Limit implementation to static head-bound lowering through `PyReasonRuleExt`; exclude dynamic bound propagation. |
| 2026-03-28 | implemented | Compiler and tests landed | Added `PyReasonRuleExt.head_bound` plus lowering in both adapter-local and execution-surface compilers; covered with focused regression tests. |
| 2026-03-28 | implemented | Module docs synced | Adapter docs now distinguish static head annotation from dynamic body-bound propagation. |
| 2026-03-28 | implemented | Validation completed | Targeted PyReason regression suite passed with 88 tests; full suite passed with 526 tests; `/tmp/pyreason` smoke produced derived bound `(0.8, 0.9)` through compiled `head_bound`. |
| 2026-03-28 | archived | Blueprint archived | Outcome recorded and files moved to `docs/blueprints/archive/`. |

## Decision Notes

- Real-engine evidence supports explicit head annotation as a static derived-bound mechanism.
- This slice preserves the existing value-carrying boundary: no dynamic interval propagation claim is added.
- Existing demos were intentionally left unchanged so the main demo narrative stays centered on current propagation limits rather than on static annotated heads.
