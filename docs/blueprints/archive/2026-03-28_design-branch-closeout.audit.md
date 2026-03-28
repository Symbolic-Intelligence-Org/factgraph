# Task Blueprint Audit: Design Branch Closeout

- Blueprint: [2026-03-28_design-branch-closeout.md](./2026-03-28_design-branch-closeout.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Recorded final branch closeout scope: durable EvidenceGraph audit delivery, PyReasonRuleDef cleanup, archive inventory refresh, and explicit handling for the remaining backlog items. |
| 2026-03-28 | scoped | Scope frozen | Confirmed this slice will implement items 1/5/6 and explicitly close/defer 2/3/4 without reopening archived blueprints. |
| 2026-03-28 | implemented | EvidenceGraph audit delivery landed | Added export-time `evidence_graphs.jsonl` materialization, audit reader/query support, static candidate-page rendering, and provenance-bearing degraded-tree fallback for offline package pages. |
| 2026-03-28 | implemented | PyReason rule-definition cleanup landed | Removed `PyReasonRuleDef`; `compile_pyreason_rule(...)` and `run_pyreason(..., rule_defs=[...])` now accept shared `Rule` only. |
| 2026-03-28 | implemented | Docs and inventory synced | Updated audit/service/adapter current-truth docs and repaired archive inventory coverage for the 2026-03-27/2026-03-28 archive set. |
| 2026-03-28 | archived | Blueprint archived | Branch closeout slice is complete; no active implementation blueprint remains for this design branch. |

## Decision Notes

- `ProbLogRuleExt`: explicitly deferred/closed for this branch because no real definition-time consumer exists.
- `body_confidences` core debt: explicitly deferred because it requires shared evaluate-signature refactoring outside this branch closeout scope.
- `ProbLog provenance summary/NL`: explicitly deferred because carrier-level provenance is already present and presentation-layer summary is not required for branch closure.
