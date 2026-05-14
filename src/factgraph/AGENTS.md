# factgraph Docs Rules

## Current Truth

- The current implementation truth for each module lives in that module's `docs/` directory.
- When you change public behavior, compatibility boundaries, workflow shape, or operator-facing behavior, update the affected module docs in the same task.

## Module Docs Convention

Each module's `docs/README.md` must cover these six items. See [docs/module_docs_convention.md](../../docs/module_docs_convention.md) for the full spec and a copy-paste starter template.

1. **Scope** — which code paths this module covers
2. **Responsibilities** — what it actually does, with entry points
3. **Non-responsibilities** — what it explicitly does not do
4. **Limitations & Compatibility** — known limits, deprecated interfaces, compat shims
5. **Test Entry Points** — where to find behavioral verification
6. **Related Historical Blueprints** — links to rationale in `blueprint_history/` or `blueprints/archive/`

## When To Update Module Docs

Must update in the same task when:
- A public entry point is added or removed
- Observable behavior changes (return value, error code, side effect)
- A deprecated interface is introduced or removed
- Module boundaries shift (responsibilities move in or out)

No update needed for:
- Pure internal refactors with no behavioral change
- Comment-only or variable rename changes
- Test helper adjustments with no behavioral change

## New Modules

- If you add a new top-level module under `src/factgraph/`, create a `docs/README.md` for it in the same change unless the user explicitly says not to.
- The new README must satisfy all six items in the convention from the start.

## Relation To Blueprints

- Blueprints constrain the task while implementation is in progress.
- Module docs describe the code that actually shipped.
- If implementation deviates from the blueprint, capture that in the blueprint's audit and `Outcome / Deviations`, then document the final behavior in module docs.

## Indexing

- When a new durable module docs entry is introduced, update [docs/README.md](../../docs/README.md) if that index would otherwise miss it.
