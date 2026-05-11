# Task Blueprint Audit: Engine Ext Decomposition

- Blueprint: [2026-05-11_engine-ext-decomposition.md](./2026-05-11_engine-ext-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A3 opened after source audit. Draft scope removes public SDK `Rule.engine_ext` / `Derivation.engine_ext`, rejects public authoring/service `engine_ext`, keeps adapter-local extension dataclasses as internal transitional bridges, and defers SemanticsProfile to B/C/D. |
| 2026-05-11 | scoped | Scope frozen | Locked D1-D9: remove public SDK `Rule.engine_ext` / `Derivation.engine_ext`; keep no alias or tombstone; reject authoring and service `engine_ext` with future SemanticsProfile redirect; retain all current internal bridge layers unchanged; retain ProbLog/PyReason adapter internals but stop teaching them as public SDK rule syntax; accept temporary public functionality gap; enforce dataclass-field absence invariants. |
| 2026-05-11 | implementing | G1 red baseline tests added | Added `test_engine_ext_decomposition.py` using the A1/A2 forward-asserting red baseline pattern. The suite covers public SDK field absence, constructor rejection, SDK shell object-level read removal, authoring/service rejection, and internal bridge guards. Targeted run `env PYTHONPATH=src python -m unittest kernel.tests.test_engine_ext_decomposition` fails as expected with 8 failures: public `engine_ext` fields still exist, constructors still accept them, SDK evaluate/shells still read object-level `engine_ext`, and authoring/service payloads do not yet reject it. Four internal bridge guard tests already pass. |
| 2026-05-11 | implementing | G2 public `engine_ext` removal implemented | Removed public SDK `Rule.engine_ext` / `Derivation.engine_ext`, removed SDK evaluate/shell object-level `engine_ext` reads, added authoring/service rejection with future SemanticsProfile redirect, and migrated affected tests to compiled-plan or adapter-internal extension paths. Preserved `EngineExtBase`, `CompiledDerivationPlan.engine_ext`, core evaluate bridge, ProbLog extension internals, PyReason extension internals, and the A2 `legacy_body_confidences` bridge. Validation: A3 suite 12/12 OK; targeted A3 + ProbLog/PyReason/SDK regression suite 240/240 OK when run with the known import primer order. |

## Decision Notes

- 2026-05-11: Initial audit found 33 Python files mentioning `engine_ext`, `EngineExtBase`, `ProbLogRuleExt`, `PyReasonRuleExt`, or concrete adapter fields. The heaviest live implementation surface is SDK/store evaluation plumbing, PyReason adapter tests, ProbLog rule extension tests, and docs.
- 2026-05-11: `engine_ext` is asymmetric today: SDK object evaluation reads it, authoring serialization omits it, service JSON cannot realistically construct adapter dataclasses, and adapters consume it as typed or duck-typed internals. A3 should remove the public object/payload entry before adapter migration.
- 2026-05-11: Draft keeps `EngineExtBase` / `CompiledDerivationPlan.engine_ext` / adapter extension dataclasses as internal bridges. G0 must decide whether that bridge is broad enough or should be narrowed layer-by-layer.
- 2026-05-11: G0 keeps D6 broad: `EngineExtBase`, `CompiledDerivationPlan.engine_ext`, core `evaluate(..., engine_ext=...)`, `ProbLogRuleExt`, `PyReasonRuleExt`, and adapter bridge helpers remain unchanged internally. This follows A2's internal-bridge precedent and avoids doing SemanticsProfile / adapter migration before B/C/D.
- 2026-05-11: Redirect text should point only to future SemanticsProfile rule projection. A3 intentionally does not advertise `ProbLogRuleExt` / `PyReasonRuleExt` as an interim public replacement because D8 accepts the temporary public functionality gap.
- 2026-05-11: SDK shell cleanup is part of G2: remove dead `getattr(derivation, "engine_ext", None)` reads instead of leaving defensive no-op forwarding.
