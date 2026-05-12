# Task Blueprint Audit: Public Inference Naming And FactGraph Create

- Blueprint: [2026-05-12_public-inference-factgraph-create.md](./2026-05-12_public-inference-factgraph-create.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created from `factgraph-lifecycle-and-assets.zh.md` after source audit. Audit found public `Inference` has no symbol collision, while full-stack `Derivation` rename touches SDK, service routes, payload keys, application protocols, registry manifests, and filesystem paths. `fg.rules.inspect(...)` already handles derivation-like objects, so a new `fg.inferences.inspect(...)` namespace is not obviously needed in Blueprint 1. |
| 2026-05-12 | scoped | Scope freeze | Locked Q1-Q13 as I1a/I2a/I3a/I4a/I5a/I6a/I7a/I8a+I8a-2/I9a/I10a/I11a/I12a/I13a. Public SDK will hard-cut `Derivation` to `Inference`, add `FactGraph.create(...)`, rename public parameters/docs, rename the SDK docs file, hard-cut compiled-plan SDK escape hatches from ordinary public surface, and keep substrate vocabulary (`derivation_id`, service/registry paths, `standard="derivation_v1"`) until later slices. |

## Decision Notes

- 2026-05-12 draft: The product is pre-release, so this blueprint can consider hard-cutting public SDK `Derivation` to `Inference` instead of preserving aliases.
- 2026-05-12 draft: The draft recommends a public/internal vocabulary split: SDK public name `Inference`, while service/wire/registry `derivation` vocabulary remains a later slice unless G0 expands scope.
- 2026-05-12 draft: `FactGraph.create(...)` is scoped as a lifecycle naming improvement over `from_schema_classes(...)`, not as graph workspace load/save.
- 2026-05-12 draft: Explain/evidence taxonomy is intentionally out of scope. The design-point now reserves future `fg.explain.*`, but Blueprint 1 should not migrate current audit/proof helpers.
- 2026-05-12 G0: Q2/Q5/Q9/Q13 lock a coherent public/internal split. Public SDK uses `Inference`; substrate vocabulary remains `derivation` for authoring payload keys, service/wire/registry paths, compiled application DTOs, and provenance standard versions.
- 2026-05-12 G0: Q3 locks public parameter rename to `inference`, including `evaluate` docs/errors and what-if shell signatures. Internal helpers may keep `derivation` names.
- 2026-05-12 G0: Q6 adds `FactGraph.create(...)` as a canonical lifecycle constructor over `from_schema_classes(...)`, while keeping `from_schema_classes(...)` available for now.
- 2026-05-12 G0: Q7 does not add `fg.inferences` just for symmetry; `fg.rules.inspect(inference)` remains the structure inspection path unless implementation discovers a real behavior need.
- 2026-05-12 G0: Q8 updates SDK docs in-slice and renames `03_rules_and_derivations.en.md` to `03_rules_and_inferences.en.md`, because it is an SDK public doc filename rather than service wire substrate.
- 2026-05-12 G0: Q12 hard-cuts `fg.eval.evaluate_compiled(...)` / `fg.eval.accept_compiled(...)` from the ordinary public SDK surface; compiled-plan capabilities remain application/substrate behavior.
- 2026-05-12 G0: `accept_many(mode="atomic")` is intentionally deferred to a future SDK keyword/boundary polish slice because it is not forced by the `Inference` rename.
