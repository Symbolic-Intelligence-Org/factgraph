# FactGraph SDK Documentation

- Applicable scope: `src/factgraph/sdk`
- Last updated: 2026-08-01
- Audience: SDK users and maintainers of the Python product surface

`factgraph.sdk` provides schema declarations, the `FactGraph` lifecycle,
namespaced reads and writes, rule/evaluation values, outward result shapes, and
the public error hierarchy. Runtime planning authority lives in
`factgraph.application`; durable commit authority lives in `Database`.

## Scope

The SDK compiles Python schema classes, owns or attaches a Database, translates
entity/field/ingest operations into application plans, and exposes read,
evaluation, audit, and package namespaces.

## Current Responsibilities

- Create in-memory or durable graphs through `FactGraph.create(...)`.
- Open durable workspaces through `FactGraph.load_workspace(...)` and release
  their exclusive writer lock through `close()` or a context manager.
- Attach to a caller-owned Database through `FactGraph.attach(...)`.
- Route canonical SDK mutations through `Database.commit_changes(...)` when a
  Database is present, including entity create/delete, field writes, ingest,
  metadata append, schema transition, and batch commit.
- Keep `FactGraph.from_schema_classes(...)` as the lower-level unmanaged
  Ledger compatibility constructor.

## Quick Start

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity

class User(Entity):
    user_id: str = Identity()
    name: str = Field()

with FactGraph.create(schema_classes=[User], path="./workspace") as fg:
    ref_alice = fg.entities.create(User, user_id="u-1")
    fg.fields.set(User.name, ref_alice, "Alice")  # durable on return
    print(fg.entities.get(User, user_id="u-1").name)

with FactGraph.load_workspace("./workspace", schema_classes=[User]) as fg:
    print(fg.entities.get(User, user_id="u-1").name)
```

`FactGraph` is the canonical entry point and a literal alias of `SDKStore`.

## Lifecycle and Ownership

`FactGraph.create(path=...)` creates and owns a durable Database;
`FactGraph.load_workspace(...)` opens and owns one. Both hold the workspace's
exclusive writer lock until `close()`. A second open, even for read-only use,
fails explicitly in v0.3.

`FactGraph.attach(db, schema_classes=...)` binds to a caller-owned Database.
Base attach is writable and all canonical SDK write surfaces route through the
Database transaction chain. Closing the attached graph does not close `db`.
`FactGraph.attach(db, view=view, ...)` is read-only.

Factual writes are write-through. `fg.save_workspace()` is an optional
lifecycle-metadata touch and does not establish durability, advance the head,
copy, or rebind a workspace. To sandbox or dry-run changes, copy the workspace
directory first and open the copy. The old "modify, omit save, then discard"
behavior no longer exists.

Closed v0.2 workspaces must be migrated explicitly:

```bash
python -m factgraph migrate-workspace ./workspace
```

Migration uses a visible `<workspace-name>.legacy-<UTC timestamp>` sibling
during atomic replacement. If a crash strands that sibling, rerun the same
command: it returns `workspace_recovery_required` with candidate paths and
whether a replacement is already present. Verify the indicated copy before
renaming, archiving, or removing anything; recovery is intentionally not
automatic.

## Non-responsibilities

- The SDK does not provide concurrent read-only opens for durable workspaces.
- It does not reconstruct pre-v0.3 transaction history during migration.
- It does not own HTTP routes, service DTOs, engine implementations, or
  meander deployment/pinning policy.
- It does not persist in-memory rules/inferences or assertion-view manager
  state as part of a workspace save.

## Limitations and Compatibility

- `FactGraph.create(...)` rejects `ledger=` and `ledger_path=`; use
  `from_schema_classes(...)` for unmanaged Ledger compatibility.
- Database-backed ingest rejects raw target/entity-reference tokens that are
  not present in the graph's managed identity cache. Use
  `fg.entities.ref/create` first. The lower-level
  `from_schema_classes(...)` lifecycle alone retains the legacy direct-write
  fallback.
- `save_workspace(path=other)` does not copy or rebind; make an explicit
  directory copy for sandbox workflows.
- Durable lifecycle is single-writer. Multi-worker deployments must arrange a
  single writer or wait for a separately designed read-only channel.
- Schema mutation remains additive-only. Successful durable schema changes are
  committed immediately as isolated `schema_change` transactions. The raw
  core `SchemaTransitionInput` mechanism is policy-free and is not exported
  from `factgraph.sdk`.
- Snapshot attach (`db.as_of(...)`) and method-level `view=` parameters remain
  future work.

## Test Entry Points

- `tests/test_factgraph_workspace_lifecycle.py`
- `tests/test_db_attach_lifecycle.py`
- `tests/test_application_entity_write.py`
- `tests/test_sdk_batch_application_delegate.py`
- `tests/test_schema_mutation_lifecycle.py`
- `tests/test_a20e_registry_final_removal.py`

## Related Historical Blueprints

- `workflow/blueprints/active/2026-07-31_stage-a-lifecycle-convergence.md`
  — current lifecycle convergence and write-routing contract.
- `workflow/design/decisions/active/2026-07-31_q-sae-6-release-target-decision.md`
  — v0.3 release and cross-repository pinning rationale.

## Doc Map

The user-facing official quickstart lives at
`docs/official/factgraph/index.md`. The module documents below remain the
implementation-truth layer for maintainers and advanced users.

| Doc | When to read |
|---|---|
| [`00_user_guide.en.md`](00_user_guide.en.md) | End-to-end SDK tour and lifecycle examples. |
| [`01_concepts.en.md`](01_concepts.en.md) | Object lifecycles, layer ownership, frozen DTOs, stability tiers. |
| [`02_readwrite_and_ingest.en.md`](02_readwrite_and_ingest.en.md) | Read/write and ingest behavior. |
| [`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md) | Rule DSL and evaluation namespace. |
| [`04_api_surface.en.md`](04_api_surface.en.md) | Public API index and signatures. |
| [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md) | Evidence and closed-head replay overview. |
| [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) | Advanced direct imports and adapters. |

## Stability and Versioning

- `factgraph.sdk.__all__` is the product surface. Removing or renaming an
  exported name requires a major version bump.
- The namespaced form (`fg.entities.*`, `fg.fields.*`, `fg.assertions.*`,
  `fg.eval.*`) is the recommended shape for new code.
- Behavior labels in the detailed docs distinguish stable contract, current
  behavior, and deliberate current boundary.
