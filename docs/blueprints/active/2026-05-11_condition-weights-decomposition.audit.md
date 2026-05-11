# Task Blueprint Audit: Condition Weights Decomposition

- Blueprint: [2026-05-11_condition-weights-decomposition.md](./2026-05-11_condition-weights-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A4 opened after source audit. Draft records that `condition_weights` differs from A1-A3 surfaces: it is current certainty/explain rule metadata with production consumers, not an adapter-specific engine shortcut. G0 must choose retain, hard-remove, or bridge-toward-SemanticsProfile scope. |
| 2026-05-11 | scoped | Scope frozen | Locked Option C over A/B/D. A4 keeps public `condition_weights` behavior for SDK, authoring, service, and agent surfaces; reclassifies it as certainty/explain projection input; points future migration to `SemanticsProfile.certainty_projection`; preserves the March 2026 boundary that weights stay out of `where` / `where_ast` / evaluator / adapter syntax; and switches G1 to a guard-baseline cadence rather than forward-failing red baseline. |

## Decision Notes

- 2026-05-11: Initial audit found `condition_weights` in SDK `Rule`, authoring compile, service rule registry, agent rule tools, service certainty lookup, core confidence-kind routing, core certainty materialization, core annotation math, and release-facing docs.
- 2026-05-11: Historical constraint from `2026-03-20_rule-condition-weight-metadata`: `condition_weights` was deliberately defined as version-scoped rule metadata keyed by `b{branch}.a{atom}`, with `RuleSpec`, `where_ast`, and evaluators kept out of scope.
- 2026-05-11: A4 cannot mechanically copy A1-A3 hard-removal logic without deciding how to preserve or intentionally suspend certainty-summary / explain behavior.
- 2026-05-11: Option D (skip A4 and jump directly to SemanticsProfile B) was considered explicitly. It is defensible, but Option C was chosen because it is small, preserves current behavior, and gives B an explicit `SemanticsProfile.certainty_projection` migration target instead of leaving the March 2026 metadata boundary implicit.
- 2026-05-11: G1 is guard-only by design. Unlike A1/A2/A3, A4 does not remove a public surface at G2, so forward-failing red tests would create churn rather than useful baseline signal.
