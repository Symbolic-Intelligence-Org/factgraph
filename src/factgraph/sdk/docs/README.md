# factgraph SDK Documentation

`factgraph.sdk` is the Python product surface of factgraph: schema authoring,
ergonomic facade, DSL primitives, outward result shapes, and a stable
public error hierarchy. The canonical runtime authority lives in
`factgraph.application`; the SDK delegates to it.

## Quick Start

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity

class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

fg = FactGraph.create(schema_classes=[User])

ref_alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.name, ref_alice, "Alice")

snap = fg.read.get(User, user_id="u-1")
print(snap.name)            # → Alice
```

`FactGraph` is the canonical entry point — a literal alias of
`SDKStore`. Both names refer to the same class.

## Doc Map

The user-facing official quickstart lives at
[`docs/official/factgraph/index.md`](/Users/zhenzhili/hnsm-backend/docs/official/factgraph/index.md).
The module docs below remain the implementation-truth layer for maintainers and
advanced users.

| Doc | When to read |
|---|---|
| [`00_user_guide.en.md`](00_user_guide.en.md) | Start here. End-to-end tour with examples for each namespace. |
| [`01_concepts.en.md`](01_concepts.en.md) | The conceptual model: object lifecycles, layer ownership, frozen DTO boundary, stability tiers. |
| [`02_readwrite_and_ingest.en.md`](02_readwrite_and_ingest.en.md) | In-depth reference for `read`, `write`, `schema.ingest`, `schema.validate_provenance`. |
| [`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md) | In-depth reference for the DSL (`Rule`, `Query`, `Inference`) and the `eval` namespace. |
| [`04_api_surface.en.md`](04_api_surface.en.md) | Full public API index with every method signature, every export, every error class. |
| [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md) | Tutorial for the nine `what_if.*` and `audit.*` methods. |
| [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) | When and why to use direct imports (walker views, recorder, raw DTOs, engine adapters). |

## Stability and Versioning

- `factgraph.sdk.__all__` is the product surface. Removing or renaming an
  exported name requires a major version bump.
- The `FactGraph` namespaced form (`fg.read.get`, `fg.what_if.check`,
  etc.) is the recommended shape for new code.
- The flat form (`fg.get`, `fg.check`, etc.) is **permanently
  supported** foundational API. Never deprecated, never removed.
- Behaviors in the docs are labeled **stable contract** (safe to assert
  against), **current behavior** (subject to evolution), or **current
  boundary** (a deliberate non-feature). See
  [`01_concepts.en.md` §4](01_concepts.en.md#4-three-stability-tiers).

## Contributing

- Issues: file at the project's GitHub issue tracker.
- Code contributions: see the project root `CONTRIBUTING.md`.
- Doc fixes: PRs welcome; docs are versioned alongside the code they
  describe. Changes to behavior must update the relevant doc in the
  same PR.

## Internal Design Records

Internal design history (blueprints, drift analyses, reference
bundles) is not shipped with the release; it is preserved in the
source repository alongside the corresponding code and git history,
which capture the design rationale behind specific API decisions.
