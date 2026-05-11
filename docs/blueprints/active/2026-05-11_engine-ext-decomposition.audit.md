# Task Blueprint Audit: Engine Ext Decomposition

- Blueprint: [2026-05-11_engine-ext-decomposition.md](./2026-05-11_engine-ext-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A3 opened after source audit. Draft scope removes public SDK `Rule.engine_ext` / `Derivation.engine_ext`, rejects public authoring/service `engine_ext`, keeps adapter-local extension dataclasses as internal transitional bridges, and defers SemanticsProfile to B/C/D. |
| 2026-05-11 | scoped | Scope frozen | Locked D1-D9: remove public SDK `Rule.engine_ext` / `Derivation.engine_ext`; keep no alias or tombstone; reject authoring and service `engine_ext` with future SemanticsProfile redirect; retain all current internal bridge layers unchanged; retain ProbLog/PyReason adapter internals but stop teaching them as public SDK rule syntax; accept temporary public functionality gap; enforce dataclass-field absence invariants. |

## Decision Notes

- 2026-05-11: Initial audit found 33 Python files mentioning `engine_ext`, `EngineExtBase`, `ProbLogRuleExt`, `PyReasonRuleExt`, or concrete adapter fields. The heaviest live implementation surface is SDK/store evaluation plumbing, PyReason adapter tests, ProbLog rule extension tests, and docs.
- 2026-05-11: `engine_ext` is asymmetric today: SDK object evaluation reads it, authoring serialization omits it, service JSON cannot realistically construct adapter dataclasses, and adapters consume it as typed or duck-typed internals. A3 should remove the public object/payload entry before adapter migration.
- 2026-05-11: Draft keeps `EngineExtBase` / `CompiledDerivationPlan.engine_ext` / adapter extension dataclasses as internal bridges. G0 must decide whether that bridge is broad enough or should be narrowed layer-by-layer.
- 2026-05-11: G0 keeps D6 broad: `EngineExtBase`, `CompiledDerivationPlan.engine_ext`, core `evaluate(..., engine_ext=...)`, `ProbLogRuleExt`, `PyReasonRuleExt`, and adapter bridge helpers remain unchanged internally. This follows A2's internal-bridge precedent and avoids doing SemanticsProfile / adapter migration before B/C/D.
- 2026-05-11: Redirect text should point only to future SemanticsProfile rule projection. A3 intentionally does not advertise `ProbLogRuleExt` / `PyReasonRuleExt` as an interim public replacement because D8 accepts the temporary public functionality gap.
- 2026-05-11: SDK shell cleanup is part of G2: remove dead `getattr(derivation, "engine_ext", None)` reads instead of leaving defensive no-op forwarding.
