# Task Blueprint Audit: Derivation Mode To Call-Site

- Blueprint: [2026-05-11_derivation-mode-to-callsite.md](./2026-05-11_derivation-mode-to-callsite.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A1 opened after source-grounded engine-params audit. Scope is limited to moving `Derivation.mode` out of public derivation definitions and into call-site evaluation semantics. |
| 2026-05-11 | draft | Source audit refined | Confirmed only two production code areas directly read public derivation `mode`: SDK object payload emission and authoring dict mode validation. Other mode flows are compiled/runtime or call-site dispatch. |
| 2026-05-11 | scoped | Scope frozen | Locked D1-D5: remove SDK `Derivation.mode`; stop object payload emission; reject structured derivation `mode`; retain internal compiled `native` default if needed; rewire service derivation evaluation to request-level engine selection. |
| 2026-05-11 | implementing | G1 red baseline tests added | Added `test_derivation_mode_callsite_migration.py` covering D1-D5. Targeted run `env PYTHONPATH=src python -m unittest kernel.tests.test_derivation_mode_callsite_migration` fails as expected with 5 failures: SDK dataclass still exposes `mode`, constructor still accepts `mode`, authoring dict `mode` is still accepted, service still ignores top-level engine, and service still accepts `derivation.mode`. |
| 2026-05-11 | implementing | G2 implementation landed | Removed public SDK `Derivation.mode`, rejected structured derivation `mode`, retained compiled `native` default, and rewired service runtime derivation evaluation to top-level `engine`. Targeted A1 run `env PYTHONPATH=src python -m unittest kernel.tests.test_derivation_mode_callsite_migration` now passes 7/7; focused migration/adapters/service suite passes 84/84; import-order-compatible explain/declaration checks pass 48/48 and 23/23. |

## Decision Notes

- 2026-05-11: Engine Semantics Unification is split into smaller blueprint slices. A1 handles only `Derivation.mode`; `Body.confidence` / `body_confidences`, `engine_ext`, `condition_weights`, SemanticsProfile shape, and adapter migrations are deferred.
- 2026-05-11: Preferred direction is decomposition-first. Remove definition-time engine selectors before introducing `SemanticsProfile`, so the new profile shape is not constrained by legacy public fields.
- 2026-05-11: Service runtime currently uses `compiled["mode"]` for derivation evaluation. A1 must move this to request-level engine selection; application protocol already has the right shape through `DerivationEvaluateRequest.engine`, while service v1 needs a small DTO-level resolver.
- 2026-05-11: G1 red baseline intentionally includes passing guards for D2/D4 (`to_authoring_payload()` has no mode when the SDK object has no mode, and compiled payload may still keep internal `native`) alongside failing tests for the current public-surface violations.
- 2026-05-11: G2 accepts top-level service `engine` for runtime derivation evaluation and rejects top-level service `mode`, keeping `mode` reserved for existing SDK call-site APIs until the broader SemanticsProfile surface is designed.
- 2026-05-11: Some audit/provenance tests still have an existing standalone import-order cycle between `kernel.audit.round_events` and `kernel.application`; G2 verification runs those checks after an A1/runtime import primer and does not alter the import graph.
