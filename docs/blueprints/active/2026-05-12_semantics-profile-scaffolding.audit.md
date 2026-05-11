# Task Blueprint Audit: SemanticsProfile Scaffolding

- Blueprint: [2026-05-12_semantics-profile-scaffolding.md](./2026-05-12_semantics-profile-scaffolding.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Track 3 / B opened after A1-A4 completion. Source audit found no existing `SemanticsProfile` implementation; current references are redirects and docs created by Uncertainty Phase 1 plus A2/A3/A4. Draft scope frames B as data shape, validation, normalization, and inspection scaffolding only, with ProbLog/PyReason adapter migration deferred to C/D. |

## Decision Notes

- 2026-05-12: A1-A4 completed the public-surface decomposition phase. B is the first slice that introduces a new runtime value object rather than removing or reclassifying an existing public field.
- 2026-05-12: Initial audit found current bridge carriers that B must not break: `CompiledDerivationPlan.engine_ext`, `CompiledDerivationPlan.engine_options`, core `evaluate(..., engine_ext=..., engine_options=...)`, `legacy_body_confidences`, `ProbLogRuleExt`, `PyReasonRuleExt`, and retained `condition_weights`.
- 2026-05-12: Initial draft keeps adapter execution out of scope. This prevents B from becoming C/D and lets profile validation stabilize before any adapter consumes it.
