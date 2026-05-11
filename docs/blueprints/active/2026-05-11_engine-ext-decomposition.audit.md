# Task Blueprint Audit: Engine Ext Decomposition

- Blueprint: [2026-05-11_engine-ext-decomposition.md](./2026-05-11_engine-ext-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A3 opened after source audit. Draft scope removes public SDK `Rule.engine_ext` / `Derivation.engine_ext`, rejects public authoring/service `engine_ext`, keeps adapter-local extension dataclasses as internal transitional bridges, and defers SemanticsProfile to B/C/D. |

## Decision Notes

- 2026-05-11: Initial audit found 33 Python files mentioning `engine_ext`, `EngineExtBase`, `ProbLogRuleExt`, `PyReasonRuleExt`, or concrete adapter fields. The heaviest live implementation surface is SDK/store evaluation plumbing, PyReason adapter tests, ProbLog rule extension tests, and docs.
- 2026-05-11: `engine_ext` is asymmetric today: SDK object evaluation reads it, authoring serialization omits it, service JSON cannot realistically construct adapter dataclasses, and adapters consume it as typed or duck-typed internals. A3 should remove the public object/payload entry before adapter migration.
- 2026-05-11: Draft keeps `EngineExtBase` / `CompiledDerivationPlan.engine_ext` / adapter extension dataclasses as internal bridges. G0 must decide whether that bridge is broad enough or should be narrowed layer-by-layer.
