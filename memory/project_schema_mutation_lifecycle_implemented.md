# Schema Mutation Lifecycle Implemented

Date: 2026-05-13

Published source: `f0279791`

Milestone branch ref: `origin/milestone/schema-mutation-lifecycle-2026-05-13`

## Scope

The schema mutation lifecycle slice is implemented and published. It adds the first public schema evolution API:

- `fg.schema.add(EntityCls)`
- `fg.schema.add(schema_classes=[...])`
- `SchemaAddResult(old_digest, new_digest, added_entities)`

The slice is additive-only. Delete, update, deprecate, and migrate remain absent from `fg.schema`.

## Landed Architecture

- New application layer module: `kernel.application.schema_mutation_runtime`
- Public SDK result DTO: `SchemaAddResult`
- SDK schema manager method: `fg.schema.add(...)`
- In-memory schema refresh updates:
  - SDK class list
  - schema IR
  - schema digest
  - core store schema IR
  - application schema index
  - descriptor indexes
- Ledger and registry schema-digest anchors are checked before mutation and updated after validation.
- Workspace manifest remains save-time state; `fg.schema.add(...)` does not rewrite `factgraph_workspace.json` until `fg.save()`.

## Validator Boundary

The strict additive validator rejects attempts to smuggle destructive schema edits through `add(...)`.

Locked behavior:

- Existing entity types must remain present.
- Existing identity fields must not change.
- Existing predicate ids, owners, names, domains, and cardinality must not change.
- Existing relationship targets must not change.
- Existing fields must not be changed.
- New predicate ids must not collide with existing ids.
- New entity classes may reference existing entity types through relationship fields.
- Re-adding an equivalent class is idempotent and returns `added_entities=[]`.

## Validation

- `test_schema_mutation_lifecycle.py`: 39/39 OK
- Lifecycle/assets preservation suite: 88/88 OK
- SDK invariants: 57/57 OK
- `git diff --check`: clean

## Published Refs

- `origin/master = f0279791`
- `origin/milestone/schema-mutation-lifecycle-2026-05-13 = f0279791`
- `origin/release/0.1.x = e996aa5b`
- `v0.1.0-rc.1`, `v0.1.0-rc.2`, and `v0.1.0-rc.3` remain intact.

## Remaining Design Lines

Schema mutation is not complete as a whole. This slice only implements additive entity-class extension. Remaining independent follow-ups include:

- destructive schema lifecycle: `delete`, `deprecate`, `update`, `migrate`
- field-level additive mutations beyond adding new entity classes
- relationship-class additions, if promoted to public schema lifecycle
- query persistence
- explain/evidence user surface
- class-less dynamic workspace load
- package/workspace convergence
