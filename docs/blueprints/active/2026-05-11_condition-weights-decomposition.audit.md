# Task Blueprint Audit: Condition Weights Decomposition

- Blueprint: [2026-05-11_condition-weights-decomposition.md](./2026-05-11_condition-weights-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A4 opened after source audit. Draft records that `condition_weights` differs from A1-A3 surfaces: it is current certainty/explain rule metadata with production consumers, not an adapter-specific engine shortcut. G0 must choose retain, hard-remove, or bridge-toward-SemanticsProfile scope. |

## Decision Notes

- 2026-05-11: Initial audit found `condition_weights` in SDK `Rule`, authoring compile, service rule registry, agent rule tools, service certainty lookup, core confidence-kind routing, core certainty materialization, core annotation math, and release-facing docs.
- 2026-05-11: Historical constraint from `2026-03-20_rule-condition-weight-metadata`: `condition_weights` was deliberately defined as version-scoped rule metadata keyed by `b{branch}.a{atom}`, with `RuleSpec`, `where_ast`, and evaluators kept out of scope.
- 2026-05-11: A4 cannot mechanically copy A1-A3 hard-removal logic without deciding how to preserve or intentionally suspend certainty-summary / explain behavior.
