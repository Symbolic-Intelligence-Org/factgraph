# Design Point Research Notes

Status: working / non-authoritative
Authority: This directory is research input for future blueprints and module docs. It is not current implementation truth.

This directory collects focused design-point investigations that sit between raw chat/session analysis and final user-facing documentation. Each note should clarify one concept by comparing:

- current source behavior;
- historical design intent when available;
- user-facing mental model;
- documentation implications.

Use these notes to make release docs clearer, but do not treat them as the final contract. When a conclusion becomes durable, migrate it into the relevant module docs under `src/kernel/*/docs/` or into `docs/architecture_principles.md`, then cite the migrated location from the note.

## Note Template

Each note should include:

1. `Status` and `Authority` headers.
2. The question being answered.
3. Source-grounded current behavior.
4. Historical/design context.
5. User-facing explanation.
6. Documentation action items.
7. Open risks or follow-up tests.

## Current Notes

- [identity-primary-key-coordinate-semantics.md](./identity-primary-key-coordinate-semantics.md) — English source note on `Identity`, `primary_key=True`, `Field`, and entity-reference coordinate semantics.
- [identity-primary-key-coordinate-semantics.zh.md](./identity-primary-key-coordinate-semantics.zh.md) — Expanded Chinese blog-style working article for iterative design and documentation edits.
- [read-write-snapshot-assertion-selection.zh.md](./read-write-snapshot-assertion-selection.zh.md) — Chinese blog-style working article on `read` / `write` namespaces, `EntitySnapshot` structure, `AssertionRecordSet` selection helpers, and precise `retract(asrt_id)` usage.
- [rule-policy-function-tree-and-syntax.zh.md](./rule-policy-function-tree-and-syntax.zh.md) — Chinese working note on the proposed `data` / `rules` / `policy` / `explain` / `simulate` / `audit` / `registry` taxonomy, `Rule` / `Query` / `Derivation` boundaries, and `fg.rules.evaluate(derivation, engine="native")` syntax direction.
- [possibility-probability-transmission.zh.md](./possibility-probability-transmission.zh.md) — Chinese working note on preserving raw uncertainty semantics and projecting probabilistic / possibilistic bounds into engine-specific views at runtime.
- [post-track3-semantics-public-api.zh.md](./post-track3-semantics-public-api.zh.md) — Chinese working note on post-Track-3 public semantics API direction: Branch identity, rule inspect, engine-specific `*Semantics` wrappers, and PyReason branch-bound projection.
