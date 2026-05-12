# Task Blueprint: Schema Mutation Lifecycle

- Status: draft
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `src/kernel/sdk/store.py`
  - `src/kernel/application/schema_runtime.py`
  - `src/kernel/core/schema/schema_ir.py`
  - `src/kernel/authoring/registry_fs.py`
  - `src/kernel/application/workspace_runtime.py`
- Related Docs:
  - [docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md](../../references/working/design-points/factgraph-lifecycle-and-assets.zh.md)
  - [docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md](../archive/2026-05-12_factgraph-workspace-lifecycle.md)
  - [memory/project_lifecycle_assets_remaining_after_rc3.md](../../../memory/project_lifecycle_assets_remaining_after_rc3.md)
- Audit Log:
  - [2026-05-13_schema-mutation-lifecycle.audit.md](./2026-05-13_schema-mutation-lifecycle.audit.md)

## 1. Problem

The lifecycle/assets sequence shipped `FactGraph.create(...)`, graph-bound
authoring asset persistence, and workspace `save/load`, but schema evolution
remains intentionally unresolved. Users can create a graph from schema classes,
save/load that graph, and persist rules/inferences, but cannot evolve a graph's
schema through a public lifecycle API such as:

```python
fg.schema.add(...)
fg.schema.delete(...)
fg.schema.update(...)
```

The missing schema story is now the most direct remaining gap in the lifecycle
design. It must be scoped carefully because schema changes affect:

- ledger `schema_digest` metadata;
- in-memory `SDKStore` schema indexes;
- registry `schema/schema_ir.json`;
- workspace manifest validation;
- saved rules/inferences compiled against prior schema;
- query, evidence, and future migration semantics.

## 2. Goals

- Define the first public schema mutation slice after rc.3.
- Add a safe additive schema extension path if G0 locks it.
- Preserve existing graph runtime, authoring asset, and workspace behavior.
- Explicitly defer destructive delete and full migration machinery unless G0
  chooses otherwise.

## 3. Non-goals

- No hard delete of entity types, fields, predicates, facts, rules, inferences,
  or evidence.
- No automatic data migration or value backfill.
- No class-less dynamic schema generation.
- No query persistence.
- No explain/evidence surface change.
- No package/workspace convergence.
- No service route changes in the first slice unless G0 explicitly widens scope.

## 4. Current Context

### 4.1 Current SDK schema namespace

`_SDKSchemaManager` currently exposes only:

- `fg.schema.ingest(...)`;
- `fg.schema.validate_provenance(...)`.

The manager is frozen and delegates to flat `SDKStore` methods. It has no
`add`, `delete`, `update`, `deprecate`, `migrate`, `describe`, or plan/apply
surface.

### 4.2 Current graph construction and schema caches

`SDKStore.__init__` compiles or receives `schema_ir`, then stores:

- `self._classes`;
- `self._store.schema_ir`;
- `self._schema_ir`;
- `self._schema_digest`;
- `self._application_schema_index`;
- field descriptor indexes built by `_index_schema()`.

Any in-place schema mutation must update all of these together. Updating only
`self._schema_ir` would leave stale runtime indexes; updating only
`Store.schema_ir` would leave the SDK facade stale.

### 4.3 Current digest anchors

Schema digest is already a load-bearing contract:

- ledger metadata stores `schema_digest`;
- registry schema entry stores `schema_digest`;
- workspace manifest stores `schema_digest`;
- `FactGraph.load(path, schema_classes=[...])` validates manifest, ledger,
  registry, and provided-class digest anchors.

Schema mutation must define when these anchors change and which writes happen
immediately versus at `fg.save(...)`.

### 4.4 Registry and workspace behavior

Blueprint 2 made first asset save auto-upsert registry schema IR and reject
schema digest mismatch. Blueprint 3 made `fg.save(...)` write Level 4 workspace
state. Schema mutation must not bypass those invariants.

### 4.5 Source design note

The lifecycle design point already warns that `schema.add/delete/update` are
not equal:

- additive schema extension is the safest candidate;
- hard delete can orphan ledger rows, views, rules, inferences, proof frames,
  and registry versions;
- update/migrate likely needs a migration plan object.

## 5. Proposed Shape

This draft recommends a narrow first slice:

```python
fg.schema.add(NewEntity)
fg.schema.add(schema_classes=[NewEntity, OtherEntity])
```

The operation is immediate, additive-only, and class-based:

1. Validate supplied classes are SDK `Entity` subclasses.
2. Compile candidate schema from `current classes + new classes`.
3. Verify the candidate schema is a strict additive superset of the current
   schema.
4. Reject existing entity type changes, field changes on existing entity types,
   identity changes, predicate rewrites, and removals.
   New entity types may declare relationships to existing entity types; the
   resulting predicates are part of the additive set as long as existing schema
   components are unchanged.
5. Atomically refresh SDK/Core schema state and digest anchors.
6. If a ledger is bound, update ledger `schema_digest` from old digest to new
   digest only if it currently equals the old digest.
7. If a registry is bound, upsert the new schema IR only if its existing schema
   digest is absent or equals the old digest.
8. If a workspace is bound, require `fg.save()` to persist the new workspace
   manifest; do not silently rewrite the workspace manifest from `schema.add`.

## 6. Boundaries And Invariants

- Existing facts remain valid after additive schema extension.
- Existing rules/inferences remain loadable; they were compiled against a
  subset schema.
- `fg.rules.save/load/list/get` and `fg.inferences.save/load/list/get` keep
  Blueprint 2 behavior.
- `fg.save(...)` and `FactGraph.load(...)` keep Blueprint 3 Level 4 workspace
  behavior.
- `FactGraph.load(...)` still requires Python schema classes.
- `from_schema_classes(...)` remains lower-level and unchanged.
- `fg.schema.delete(...)`, `fg.schema.update(...)`, and
  `fg.schema.migrate(...)` are not created unless G0 widens scope.
- Hard delete must not be smuggled in through `add(...)` by accepting a
  replacement class list that omits existing schema components.
- Validation must complete before any state mutation. The implementation should
  use a preflight/commit split: first validate class inputs, candidate schema
  shape, additive compatibility, ledger digest, and registry digest; only then
  update in-memory state, ledger metadata, and registry schema. If a
  post-validation write still fails, raise `SDKStoreError` with enough context
  to identify which phase failed.
- After `fg.schema.add(...)`, follow-on `fg.rules.save(...)` and
  `fg.inferences.save(...)` must use the new schema digest and must be able to
  save assets that reference newly added entity classes.

## 7. G0 Questions

### Q1. First-slice mutation scope

- **S1a** Additive-only schema extension. Recommended.
- **S1b** Additive extension plus deprecate metadata.
- **S1c** Full add/delete/update/migrate family.

Recommendation: **S1a**. It addresses the user's `add` request while avoiding
destructive compatibility questions that need migration machinery.

### Q2. Public API shape

- **S2a** `fg.schema.add(NewEntity, ...)` and
  `fg.schema.add(schema_classes=[...])`. Recommended.
- **S2b** `fg.schema.extend(schema_classes=[...])`.
- **S2c** `plan = fg.schema.plan_add(...); fg.schema.apply(plan)`.

Recommendation: **S2a**. The user asked for `add`, and additive-only semantics
make the verb honest in the first slice. Plan/apply is better saved for
`update/migrate`.

### Q3. Supported add targets

- **S3a** New entity classes only. Recommended.
- **S3b** New entity classes plus new fields on existing entity types.
- **S3c** Any additive schema IR delta.

Recommendation: **S3a** for the first implementation. Adding fields to an
existing Python entity type needs a clear class-version story and field default
semantics. Entity-only addition is mechanically safer.

### Q4. Immediate mutation vs preview

- **S4a** Immediate in-place mutation after validation. Recommended.
- **S4b** Return a preview object and require explicit apply.
- **S4c** Dry-run only in the first slice.

Recommendation: **S4a** for entity-only additive extension. The operation is
safe enough if the additive validator is strict and state refresh is atomic.

### Q5. Digest anchor update behavior

- **S5a** Update in-memory schema, `Store.schema_ir`, SDK indexes, ledger
  `schema_digest`, and registry schema IR together; workspace manifest updates
  only on `fg.save(...)`. Recommended.
- **S5b** Update in-memory only; require explicit `fg.save(...)` to update
  ledger/registry.
- **S5c** Refuse schema mutation when any ledger/registry/workspace is bound.

Recommendation: **S5a**. Ledger and registry digest anchors are part of the
active graph state; leaving them stale would make subsequent writes fail in
surprising ways. Workspace manifest remains save-time state.

### Q6. Additive compatibility validator

- **S6a** Candidate schema must pass an explicit additive diff validator.
  Recommended. The validator checks:
  1. every existing entity type remains present;
  2. every existing entity's identity fields remain byte-for-byte equivalent
     after schema canonicalization;
  3. every existing predicate id remains present;
  4. every existing predicate's owner, `py_field_name`, `arg_specs`, value type
     domain, cardinality, and semantic flags remain equivalent;
  5. existing relationship targets are not changed;
  6. new entity types may introduce new predicates, including relationship
     predicates that target existing entity types;
  7. new predicate ids must not collide with existing predicate ids.
- **S6b** Preserve only entity and predicate ids.
- **S6c** Rely on `ensure_schema_ir(...)` and skip explicit additive diff.

Recommendation: **S6a**. This is the safety boundary that keeps `add(...)` from
becoming accidental update/delete.

### Q7. Registry mismatch behavior

- **S7a** Registry absent or old digest: upsert new schema; registry different
  from old digest: raise `SDKStoreError`. Recommended.
- **S7b** Always overwrite registry schema.
- **S7c** Never touch registry schema from `fg.schema.add`.

Recommendation: **S7a**. This mirrors Blueprint 2's digest mismatch safety and
preserves registry as durable schema reference.

### Q8. Ledger mismatch behavior

- **S8a** Ledger absent or old digest: update to new digest; ledger different
  from old digest: raise `SDKStoreError`. Recommended.
- **S8b** Always overwrite ledger schema digest.
- **S8c** Never touch ledger metadata from `fg.schema.add`.

Recommendation: **S8a**. The ledger must not silently move if another graph
schema wrote it first.

### Q9. Workspace behavior

- **S9a** In-memory/ledger/registry update immediately; workspace manifest
  updates only on explicit `fg.save(...)`. Recommended.
- **S9b** If workspace-bound, `fg.schema.add(...)` immediately rewrites the
  workspace manifest.
- **S9c** If workspace-bound, refuse schema mutation until caller passes a
  workspace migration flag.

Recommendation: **S9a**. It preserves the Blueprint 3 separation between graph
state changes and workspace save.

### Q10. Delete/deprecate public surface

- **S10a** No `delete`, `remove`, `drop`, or `deprecate` method in this slice.
  Recommended.
- **S10b** Add `fg.schema.deprecate(...)` metadata only.
- **S10c** Add hard `delete(...)` with rejection for now.

Recommendation: **S10a**. Empty/rejecting methods are public API noise; real
deprecation needs durable metadata.

### Q11. Update/migrate public surface

- **S11a** No `update`, `migrate`, `plan_update`, or `apply_migration` in this
  slice. Recommended.
- **S11b** Add plan object types but no apply.
- **S11c** Add a minimal field-add migration.

Recommendation: **S11a**. Migration needs its own blueprint.

### Q12. Application layer ownership

- **S12a** Add `kernel.application.schema_mutation_runtime` as the authority for
  additive validation and state transition helpers. Recommended.
- **S12b** Implement directly in `SDKStore`.
- **S12c** Implement in `kernel.core.schema`.

Recommendation: **S12a**. It follows Blueprint 2 and Blueprint 3's
application-first runtime authority pattern.

### Q13. Return shape

- **S13a** Return a small `SchemaAddResult(old_digest, new_digest, added_entities)`
  DTO. Recommended.
- **S13b** Return the mutated `FactGraph`.
- **S13c** Return raw schema IR.

Recommendation: **S13a**. The caller needs confirmation without conflating a
mutation result with the graph object.

### Q14. Docs strategy

- **S14a** Update SDK user guide and API surface in the same slice; module docs
  classify delete/update/migrate as future. Recommended.
- **S14b** Code first, docs later.

Recommendation: **S14a**. Public lifecycle behavior must not lag behind code.

### Q15. Re-adding an already present class

- **S15a** Idempotent no-op: accept the call and return
  `SchemaAddResult(added_entities=[])` when every supplied class is already
  present and equivalent. Recommended.
- **S15b** Reject with "entity already exists".
- **S15c** Accept only if caller passes `allow_existing=True`.

Recommendation: **S15a**. Idempotency matches Blueprint 2's schema upsert
behavior and makes repeated setup cells/notebooks safe.

## 8. Acceptance

- [ ] G0 locks first-slice schema mutation scope.
- [ ] G0 locks public API shape and supported add targets.
- [ ] G0 locks digest anchor update behavior.
- [ ] G0 locks delete/update/migrate as included or deferred.
- [ ] G0 locks re-add idempotency behavior.
- [ ] G1 baseline covers additive entity add, rejection of unsafe deltas, and
  lifecycle preservation guards.
- [ ] G2 implementation keeps SDK/Core schema state refresh atomic.
- [ ] G2 implementation preserves Blueprint 2 and Blueprint 3 behavior.
- [ ] G3 docs sync public schema mutation teaching.
- [ ] G4 fills outcome/deviations and archives the blueprint pair.

## 9. Implementation Plan

1. G1 red/guard baseline:
   - expected scope is roughly 30-40 tests because the matrix spans additive
     diff categories, ledger/registry/workspace digest anchors, idempotency,
     and lifecycle preservation guards;
   - forward tests for `fg.schema.add(NewEntity)`;
   - rejection tests for duplicate entity type and changed existing schema;
   - strict additive validator tests for entity removal, identity change,
     predicate owner/name/type/cardinality changes, relationship target changes,
     and predicate id collisions;
   - digest anchor tests for in-memory, ledger, registry, and workspace save;
   - idempotent re-add tests;
   - guards for `fg.schema.delete/update/migrate` absence;
   - preservation tests for rules/inferences/workspace lifecycle.
2. G2 implementation:
   - add application-layer additive schema mutation helpers;
   - add SDK result DTO and public `fg.schema.add(...)`;
   - atomically refresh SDK/Core schema state and digest anchors.
3. G3 docs sync:
   - update SDK user guide and API surface;
   - update lifecycle design note from "future" to "additive first slice
     landed" if implemented.
4. G4 close-out:
   - fill outcome/deviations;
   - archive blueprint pair.

## 10. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/application/docs/01_overview_en.md` if a new application runtime
  module is introduced.
- `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`
  if the design note should reflect landed behavior.

## 11. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Validation:
- Deviations:
- Archive notes:
