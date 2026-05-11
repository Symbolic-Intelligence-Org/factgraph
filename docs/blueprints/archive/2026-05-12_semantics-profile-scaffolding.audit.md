# Task Blueprint Audit: SemanticsProfile Scaffolding

- Blueprint: [2026-05-12_semantics-profile-scaffolding.md](./2026-05-12_semantics-profile-scaffolding.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Track 3 / B opened after A1-A4 completion. Source audit found no existing `SemanticsProfile` implementation; current references are redirects and docs created by Uncertainty Phase 1 plus A2/A3/A4. Draft scope frames B as data shape, validation, normalization, and inspection scaffolding only, with ProbLog/PyReason adapter migration deferred to C/D. |
| 2026-05-12 | scoped | Scope frozen | Locked D1-D10: new `kernel.core.semantics` subpackage, no SDK export, no `evaluate(semantics=...)` integration, frozen value object, profile version `"1.0"` only, generic rule-projection shape validation, locked uncertainty policy enum, temporal `mode="none"` only, core-only inspection helper, and preservation of A1-A4 rejection gates plus all internal bridges. |
| 2026-05-12 | implementing | G1 red + guard baseline added | Added `test_semantics_profile_scaffolding.py` with B's dual cadence: forward-failing tests for the missing core semantics module, profile validation, inspection helper, SDK rejection, and service rejection; guard tests for no SDK export, unchanged application protocol, adapter non-import, ProbLog `legacy_body_confidences`, and `PyReasonRuleExt`. Baseline result: 24 tests, FAILED with 15 errors, 4 failures, and 5 passing guards. No production code changed. |
| 2026-05-12 | design note | Recorded future engine-selection naming preference | B does not rename current evaluate APIs, but Track 3 / E should prefer `engine=` as the public call-site engine-selection keyword over historical `mode=` when it designs the durable SDK/service runtime shape. |
| 2026-05-12 | implementing | G2 SemanticsProfile scaffolding implemented | Added `kernel.core.semantics` with a frozen `SemanticsProfile`, generic validation, and pure `inspect_semantics_profile`; added explicit SDK/service rejection for `semantics` / `semantics_profile`; added minimal core semantics module docs. Validation: B suite 24/24 OK and A1-A4+B focused suites 62/62 OK. No adapter imports or consumes `SemanticsProfile`. |
| 2026-05-12 | documenting | G3 docs sync | Updated SDK, core, adapter, service, root docs index, and transmission reference docs to describe B as core scaffolding only: `SemanticsProfile` is importable for validation / inspection, SDK and service runtime reject `semantics` / `semantics_profile`, and ProbLog/PyReason/runtime consumption remains deferred to C/D/E. |
| 2026-05-12 | implemented | Closed and archived | Filled §10 Outcome / Deviations, marked implemented, archived the blueprint pair, and updated archive inventory. Final validation: B suite 24/24 OK, A1-A4+B focused suite 62/62 OK, docs grep gates clean, adapter Python imports no `SemanticsProfile`, and `git diff --check` clean. |

## Decision Notes

- 2026-05-12: A1-A4 completed the public-surface decomposition phase. B is the first slice that introduces a new runtime value object rather than removing or reclassifying an existing public field.
- 2026-05-12: Initial audit found current bridge carriers that B must not break: `CompiledDerivationPlan.engine_ext`, `CompiledDerivationPlan.engine_options`, core `evaluate(..., engine_ext=..., engine_options=...)`, `legacy_body_confidences`, `ProbLogRuleExt`, `PyReasonRuleExt`, and retained `condition_weights`.
- 2026-05-12: Initial draft keeps adapter execution out of scope. This prevents B from becoming C/D and lets profile validation stabilize before any adapter consumes it.
- 2026-05-12: Module placement chooses `kernel.core.semantics` over core store types or application protocol because the profile is larger than a scalar store type and will accumulate normalization / inspection helpers across B/C/D/E.
- 2026-05-12: SDK export and `evaluate(semantics=...)` are intentionally deferred. Accepting a profile before adapters consume it would create silent-ignore risk; E owns the public SDK call-site shape.
- 2026-05-12: Rule projection validation is deliberately generic in B. Engine-specific kinds and target resolution require concrete adapter migration context and are therefore C/D work.
- 2026-05-12: Uncertainty projection policies are a locked enum in B to catch typos early, while temporal projection is `none`-only to avoid accepting future PyReason valid-time semantics before D implements them.
- 2026-05-12: G1 uses both red-baseline and guard-baseline patterns. This differs from A4's guard-only cadence because B introduces a new value object, while still preserving A1-A4 rejection gates and internal bridge behavior.
- 2026-05-12: Engine selection naming should move toward `engine=` in future public call-site APIs. Historical `mode=` remains the current SDK spelling in B, but `engine=` better matches `DerivationEvaluateRequest.engine` and the post-A1 rule that engine selection belongs at runtime rather than definition time.
- 2026-05-12: G2 keeps `SemanticsProfile` out of SDK exports and adapters. The implementation provides importable core scaffolding plus rejection guards only; runtime consumption remains Track 3 / E for call-site shape and C/D for adapter interpretation.
