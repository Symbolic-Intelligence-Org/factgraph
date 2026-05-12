# Task Blueprint Audit: Authoring Asset Persistence Facade

- Blueprint: [2026-05-12_authoring-asset-persistence-facade.md](./2026-05-12_authoring-asset-persistence-facade.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Blueprint 1 public `Inference` + `FactGraph.create(...)` and the inference wire/registry vocabulary slice both shipped. Source audit split across registry surface, ref/namespace surface, and application/FactGraph binding. Load-bearing findings: `SDKRegistry` is still public and raw-dict-shaped; `FileAuthoringRegistry` has enough low-level primitives but returns compiler-facing inference payloads with `derivation_id`; current `RuleRef` is a where-clause DSL carrier, not a persisted asset handle; `InferenceRef` is absent and explicitly guarded; `SDKStore` has no authoring registry binding; and no `kernel.application.authoring_runtime` exists yet. |

## Decision Notes

- 2026-05-12 draft: The central G0 question is registry attachment. `fg.rules.save(...)` and `fg.inferences.save(...)` cannot be clean instance methods unless `FactGraph` is bound to a registry root/object or every call takes an explicit registry.
- 2026-05-12 draft: Reusing current `RuleRef` as a save return type is risky because it already means a where-clause RuleRef atom carrier with hidden object-backed dependency behavior.
- 2026-05-12 draft: Adding `InferenceRef` is a real public API expansion. Current tests explicitly assert it does not exist; G1 must invert that only if G0 locks it.
- 2026-05-12 draft: `SDKRegistry` export fate must be explicit. If `fg.rules.*` / `fg.inferences.*` become the product facade, keeping `SDKRegistry` public creates duplicate persistence surfaces.
- 2026-05-12 draft: The stale docs claim that `fg.eval.run(...)` accepts a direct `RuleRef` should be fixed or explicitly scoped, because code treats `RuleRef` as a where-clause DSL carrier, not a runnable rule selector.
