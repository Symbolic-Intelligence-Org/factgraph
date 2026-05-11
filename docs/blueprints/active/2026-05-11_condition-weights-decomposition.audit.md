# Task Blueprint Audit: Condition Weights Decomposition

- Blueprint: [2026-05-11_condition-weights-decomposition.md](./2026-05-11_condition-weights-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A4 opened after source audit. Draft records that `condition_weights` differs from A1-A3 surfaces: it is current certainty/explain rule metadata with production consumers, not an adapter-specific engine shortcut. G0 must choose retain, hard-remove, or bridge-toward-SemanticsProfile scope. |
| 2026-05-11 | scoped | Scope frozen | Locked Option C over A/B/D. A4 keeps public `condition_weights` behavior for SDK, authoring, service, and agent surfaces; reclassifies it as certainty/explain projection input; points future migration to `SemanticsProfile.certainty_projection`; preserves the March 2026 boundary that weights stay out of `where` / `where_ast` / evaluator / adapter syntax; and switches G1 to a guard-baseline cadence rather than forward-failing red baseline. |
| 2026-05-11 | implementing | G1 guard baseline tests added | Added `test_condition_weights_decomposition.py` using A4's guard-only cadence. The suite proves retained SDK field/payload behavior, authoring validation, service compile-preview + registry persistence, agent serialization, confidence-kind routing to `certainty`, and certainty-summary materialization. Validation: A4 guard suite 9/9 OK; declaration metadata + core certainty annotation suite 43/43 OK; A4 + certainty explain contract suite 50/50 OK. No production code changed. |
| 2026-05-11 | implementing | G2 code marker added | Added a narrow SDK field comment classifying `Rule.condition_weights` as certainty/explain projection input and pointing future runtime semantics to `SemanticsProfile.certainty_projection`. No behavior, validation, serialization, confidence-kind routing, certainty-summary math, or agent/service forwarding changed. |
| 2026-05-11 | implementing | G3 docs synced | Updated SDK, authoring, core, annotation, audit, and service docs to classify `condition_weights` as certainty/explain projection input, not engine adapter semantics or `where` execution semantics. Release-facing docs now point future runtime configuration for this lane to `SemanticsProfile.certainty_projection` while preserving current examples and registry/summary behavior. Validation: A4 guard suite 9/9 OK; declaration metadata + core certainty annotation suite 43/43 OK; A4 + certainty explain contract suite 50/50 OK; docs grep shows engine-adapter mentions only in explicit negative classification text. |

## Decision Notes

- 2026-05-11: Initial audit found `condition_weights` in SDK `Rule`, authoring compile, service rule registry, agent rule tools, service certainty lookup, core confidence-kind routing, core certainty materialization, core annotation math, and release-facing docs.
- 2026-05-11: Historical constraint from `2026-03-20_rule-condition-weight-metadata`: `condition_weights` was deliberately defined as version-scoped rule metadata keyed by `b{branch}.a{atom}`, with `RuleSpec`, `where_ast`, and evaluators kept out of scope.
- 2026-05-11: A4 cannot mechanically copy A1-A3 hard-removal logic without deciding how to preserve or intentionally suspend certainty-summary / explain behavior.
- 2026-05-11: Option D (skip A4 and jump directly to SemanticsProfile B) was considered explicitly. It is defensible, but Option C was chosen because it is small, preserves current behavior, and gives B an explicit `SemanticsProfile.certainty_projection` migration target instead of leaving the March 2026 metadata boundary implicit.
- 2026-05-11: G1 is guard-only by design. Unlike A1/A2/A3, A4 does not remove a public surface at G2, so forward-failing red tests would create churn rather than useful baseline signal.
- 2026-05-11: G2 used a minimal code-marker cadence rather than an empty implementation step. The marker is intentionally non-behavioral and exists to keep the retained public field aligned with A4's classification and Track 3 / B migration target.
