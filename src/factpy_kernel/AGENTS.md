# factpy_kernel Docs Rules

## Current Truth

- The current implementation truth for each module lives in that module's `docs/` directory.
- When you change public behavior, compatibility boundaries, workflow shape, or operator-facing behavior, update the affected module docs in the same task.

## New Modules

- If you add a new top-level module under `src/factpy_kernel/`, create a `docs/README.md` for it in the same change unless the user explicitly says not to.

## Relation To Blueprints

- Blueprints constrain the task while implementation is in progress.
- Module docs describe the code that actually shipped.
- If implementation deviates from the blueprint, capture that in the blueprint's audit and `Outcome / Deviations`, then document the final behavior in module docs.

## Indexing

- When a new durable module docs entry is introduced, update [docs/README.md](/Users/zhenzhili/symbolic_agent/docs/README.md) if that index would otherwise miss it.
