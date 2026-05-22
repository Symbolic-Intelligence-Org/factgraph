# Task Blueprint: Schema Field Add Lifecycle

- Status: implemented
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `src/kernel/sdk/schema.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/application/schema_mutation_runtime.py`
  - `src/kernel/application/schema_runtime.py`
  - `src/kernel/application/entity_view.py`
  - `src/kernel/application/entity_write.py`
  - `src/kernel/authoring/schema_compile.py`
  - `src/kernel/core/schema/schema_ir.py`
- Related Docs:
  - [docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md](../archive/2026-05-13_schema-mutation-lifecycle.md)
  - [memory/project_schema_mutation_lifecycle_implemented.md](../../../memory/project_schema_mutation_lifecycle_implemented.md)
- Audit Log:
  - [2026-05-13_schema-field-add-lifecycle.audit.md](./2026-05-13_schema-field-add-lifecycle.audit.md)

## 1. Problem

The schema mutation lifecycle slice shipped additive entity-class extension:

```python
fg.schema.add(Account)
```

The next natural schema thread is adding fields to an existing entity type.
This is still additive, but it is not just "entity-add with a smaller diff":

- Python `Entity` declarations are compiled at class creation time;
- `Field` descriptors are used directly by SDK write APIs;
- predicate ids are derived from entity name + field name;
- existing facts have no rows for the new predicate;
- saved rules/inferences may have been compiled against the old schema;
- workspace load still requires caller-provided Python classes.

This slice needs to decide the first safe public shape for field addition
without smuggling destructive schema update semantics into `fg.schema.add(...)`.

## 2. Goals

- Extend schema mutation to support non-identity field additions on existing
  entity types.
- Preserve the additive-only contract from the prior schema mutation slice.
- Reuse `kernel.application.schema_mutation_runtime`, digest anchors, registry
  sync, and workspace save-time behavior.
- Define absence/default semantics for existing assertions after field-add.
- Preserve existing entity-add behavior and lifecycle/assets invariants.

## 3. Non-goals

- No field removal.
- No field rename.
- No field type-domain or cardinality change.
- No identity-field addition or identity model change.
- No automatic backfill of existing facts.
- No relationship-class field-add in this slice unless G0 widens scope.
- No schema migration plan object.
- No class-less dynamic `FactGraph.load(...)`.
- No service route change.

## 4. Source Audit

### 4.1 SDK schema declarations

`Identity`, `Field`, `EntityMeta`, `Entity`, `RelationshipMeta`, and
`Relationship` live in `src/kernel/sdk/schema.py`. Descriptors bind
`sdk_attr_name` / `sdk_owner_cls` through `__set_name__`. `EntityMeta.__new__`
reads `__annotations__`, collects `Identity` and `Field` descriptors, requires
at least one primary-key identity, and writes `cls.__sdk_entity_spec__`.

Implication: field-add cannot be modeled by mutating `fg` alone. The active
graph must receive a Python class declaration whose metaclass has already
compiled the new field into `__sdk_entity_spec__`.

### 4.2 Class declarations are not deep-frozen

`Entity.sdk_entity_spec()` returns the stored spec dict directly, while
`Relationship.sdk_relationship_spec()` returns a shallow copy. The current
implementation treats schema classes as declarations, but not as deeply
immutable values.

Implication: G0 should not rely on post-hoc mutation of an existing class or
its stored spec as the public field-add mechanism. Use a replacement class
object compiled by the metaclass.

### 4.3 Schema compilation and predicate ids

`compile_schema_from_classes(...)` builds authoring schema from SDK classes,
then `compile_authoring_schema_v1(...)` produces schema IR. Field predicate ids
are deterministic:

- entity exists: `<EntityType>:exists`;
- identity / normal entity fields: `<owner_prefix>:<field_name>`;
- relationship fields: `<relationship_prefix>:<field_name>`.

`owner_prefix` lower-snake-cases the entity type. Predicate id stability is
load-bearing because ledger rows, saved rules/inferences, and wire artifacts
refer to `pred_id`.

### 4.4 Current schema mutation runtime

`kernel.application.schema_mutation_runtime.validate_additive_schema_extension`
already allows extra candidate predicates if all existing entities and
predicates are preserved. The main entity-only assumption is
`add_schema_classes(...)`: for an existing `entity_type`, it validates the
candidate class and then `continue`s without replacing the class in
`next_classes`. Final schema IR is compiled from unchanged classes, so a
same-name class with an added field currently validates but becomes a no-op.

### 4.5 SDK descriptor indexes

`SDKStore._index_schema()` maps `Field` descriptors from `self._classes` to
schema predicates. `_refresh_schema_state(...)` clears and rebuilds those maps.
Field-add becomes usable through `fg.write.set(NewUser.nickname, ...)` only if
the active class list is replaced with the updated class object.

### 4.6 Read/write absence behavior already exists

Application reads hydrate fields from active predicate rows:

- missing single-cardinality field rows read as `None`;
- missing multi-cardinality rows read as an empty tuple.

Application writes reject `None` as a set/add value and resolve writes through
`FieldPath(entity_type, field_name)` plus the active schema index.

Implication: first-slice field-add can avoid backfill. Existing assertions have
no rows for the new predicate; reads naturally expose empty values.

### 4.7 Existing defaults are identity-only

`Identity` supports `default` and `default_factory`. `Field` has no default or
nullability parameter. Existing backfill logic materializes entity existence
and identity predicates, not regular field values.

Implication: `Field(default=...)` / automatic backfill would be a new product
surface and should be explicitly deferred unless G0 widens scope.

### 4.8 Workspace/load implications

`FactGraph.load(path, schema_classes=[...])` validates caller-provided classes
against manifest, ledger, and registry digests. After field-add and `fg.save()`,
future loads require the updated class set. The saved registry schema is not
enough to reconstruct Python descriptors.

### 4.9 DSL predicate id risk

One DSL sugar path lowers attribute comparison through a simple
`record_type.lower()` prefix, while schema compilation uses lower-snake
`owner_prefix`. This is an existing risk for CamelCase entity names and is not
specific to field-add, but field-add tests that save rules using a newly added
field should avoid accidentally relying on the wrong prefix.

## 5. Proposed Shape

Recommended first-slice shape:

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

fg = FactGraph.create(schema_classes=[User])

class User(Entity):  # same entity_type, replacement declaration
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    nickname: str = Field(cardinality="single")

result = fg.schema.add(User)
assert result.added_fields == ["User.nickname"]

alice = fg.read.get(User, user_id="u-1")
assert alice.nickname is None

fg.write.set(User.nickname, alice.ref, "Ali")
```

The public contract is "same entity type, replacement class declaration,
additive new non-identity fields only." Old class objects become stale schema
declarations for that active graph; users should use the updated class object
after successful field-add.

## 6. Boundaries And Invariants

- Existing entity-add behavior remains unchanged.
- Field-add is additive-only: no removal, rename, type change, cardinality
  change, relationship target change, or identity-model change.
- Existing facts remain readable.
- Existing saved rules/inferences remain loadable.
- New saved rules/inferences may reference newly added fields after mutation.
- Missing values for added fields use existing read semantics: `None` for
  single fields and `()` for multi fields.
- No automatic value backfill occurs.
- After field-add, SDK reads/writes through superseded `Entity` class objects
  or `Field` descriptors raise `SDKStoreError("schema declaration was
  superseded; use the post-add class object")` or an equivalent anchored
  substring. Detection should happen at SDK boundaries by checking whether the
  descriptor owner class is the currently active class object for that entity
  type.
- Ledger and registry digest anchors follow the schema mutation lifecycle
  slice.
- Workspace manifest updates only on `fg.save()`.
- `FactGraph.load(...)` still requires post-add Python schema classes after
  the workspace is saved.
- DSL predicate-prefix mismatch for CamelCase entity types is a pre-existing
  audit risk. This slice does not normalize every SDK DSL path, but it must add
  a focused regression if field-add tests using CamelCase entities expose the
  mismatch. Broad DSL prefix normalization remains a separate future slice.
- `fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, and
  `fg.schema.deprecate` remain absent.

## 7. G0 Questions

### Q1. Field-add public API

- **F1a** Reuse `fg.schema.add(...)` with an updated class declaration for the
  same `entity_type`. Recommended.
- **F1b** Add `fg.schema.add_field(EntityCls, FieldSpec)`.
- **F1c** Add `fg.schema.extend(...)` for all additive schema changes.

Recommendation: **F1a**. It preserves one additive verb and reuses class-based
schema declarations; `add_field` would require a new mini schema-spec language.

G0 decision (2026-05-13): **F1a locked**. Field-add reuses
`fg.schema.add(...)` with an updated same-entity class declaration.

### Q2. Same-entity class semantics

- **F2a** Same `entity_type` candidate replaces the active class declaration
  after validation. Recommended.
- **F2b** Keep old and new classes bound concurrently.
- **F2c** Require explicit class/schema versioning before any field-add.

Recommendation: **F2a**. Descriptor indexes need the updated class object.
Concurrent same-entity classes would complicate `_classes`, schema compilation,
and descriptor lookup.

G0 decision (2026-05-13): **F2a locked**. Same-`entity_type` candidate classes
replace the active class declaration after validation.

### Q3. Old class object behavior after field-add

- **F3a** Treat old class objects/descriptors as stale for the active graph;
  writes with old descriptors continue only for fields still bound if the
  descriptor map can preserve them.
- **F3b** Reject old class objects/descriptors after replacement with a clear
  "schema declaration was superseded" error. Recommended.
- **F3c** Preserve old class objects as aliases forever.

Recommendation: **F3b**. It is stricter but simpler: after field-add, the
replacement class is the active SDK declaration for that entity type. Keeping
old descriptors partially alive would create two public descriptor identities
for one schema predicate.

G0 decision (2026-05-13): **F3b locked**. Superseded class objects/descriptors
are rejected at SDK boundaries with the anchored superseded-declaration error.

### Q4. Result DTO shape

- **F4a** Extend `SchemaAddResult` with `added_fields: list[str]` while keeping
  `added_entities`; field ids use `"Entity.field"` strings. Recommended.
- **F4b** Add a new `SchemaFieldAddResult`.
- **F4c** Keep only `added_entities`, use empty list for field-add.

Recommendation: **F4a**. Same public verb should have one result type, and
field-add needs a visible result.

G0 decision (2026-05-13): **F4a locked**. `SchemaAddResult` grows
`added_fields: list[str]` while preserving `added_entities`.

### Q5. Field eligibility

- **F5a** Permit only non-identity `Field` additions on existing `Entity`
  classes. Recommended.
- **F5b** Permit `Identity` additions if defaults exist.
- **F5c** Permit fields on `Relationship` classes too.

Recommendation: **F5a**. Identity changes alter entity identity semantics.
Relationship-class mutation is a separate schema thread.

G0 decision (2026-05-13): **F5a locked**. Existing-entity field-add supports
non-identity `Field` descriptors only.

### Q6. Absence/default/backfill semantics

- **F6a** No field defaults and no backfill; missing single reads as `None`,
  missing multi reads as `()`. Recommended.
- **F6b** Add `Field(default=...)` and lazy default read behavior.
- **F6c** Add explicit backfill during schema mutation.

Recommendation: **F6a**. It matches current read behavior and avoids ledger-wide
migration cost.

G0 decision (2026-05-13): **F6a locked**. No defaults and no backfill; absence
uses existing read semantics.

### Q7. Validator adjustment

- **F7a** Preserve all existing predicates exactly, allow only new non-identity
  predicates owned by existing entities or new entities. Recommended.
- **F7b** Allow field additions and selected field metadata changes such as
  description.
- **F7c** Compare only predicate ids.

Recommendation: **F7a**. This keeps the validator additive while lifting the
old "any field change on existing entity" restriction.

G0 decision (2026-05-13): **F7a locked**. Existing predicates stay exact;
only new non-identity predicates are allowed.

### Q8. Predicate id collision policy

- **F8a** New field predicate ids are compiler-generated only and must not
  collide with existing predicate ids. Recommended.
- **F8b** Allow user-supplied predicate ids.
- **F8c** Auto-rename colliding predicates.

Recommendation: **F8a**. Predicate id stability is a core data contract.

G0 decision (2026-05-13): **F8a locked**. Field predicate ids remain
compiler-generated and collision-rejected.

### Q9. Digest anchor behavior

- **F9a** Reuse schema mutation lifecycle digest behavior: preflight ledger and
  registry old digest, then update both anchors after validation. Recommended.
- **F9b** Update in-memory only and defer anchors to `fg.save()`.
- **F9c** Require unbound graphs for field-add.

Recommendation: **F9a**. Same active schema mutation, same anchor rules.

G0 decision (2026-05-13): **F9a locked**. Field-add reuses schema mutation
digest preflight and update behavior.

### Q10. Workspace behavior

- **F10a** Workspace manifest remains save-time; `fg.schema.add(...)` does not
  rewrite it until `fg.save()`. Recommended.
- **F10b** Rewrite workspace manifest immediately.

Recommendation: **F10a**. This preserves Blueprint 3's save-time boundary.

G0 decision (2026-05-13): **F10a locked**. Workspace manifest updates only
through explicit `fg.save(...)`.

### Q11. Saved asset compatibility

- **F11a** Existing saved rules/inferences remain loadable; newly saved assets
  can reference added fields after mutation. Recommended.
- **F11b** Require resaving all assets after field-add.

Recommendation: **F11a**. Existing assets compiled against a subset schema
should remain valid.

G0 decision (2026-05-13): **F11a locked**. Existing saved assets remain
loadable; newly saved assets may reference added fields.

### Q12. Workspace load after saved field-add

- **F12a** `FactGraph.load(...)` requires the post-add Python classes after
  `fg.save()`. Recommended.
- **F12b** Reconstruct Python classes from registry schema.

Recommendation: **F12a**. Class-less load remains deferred.

G0 decision (2026-05-13): **F12a locked**. Loading a saved post-field-add
workspace requires post-add Python schema classes.

### Q13. Idempotent re-add

- **F13a** Re-adding an equivalent post-add class is no-op with
  `added_entities=[]` and `added_fields=[]`. Recommended.
- **F13b** Reject duplicate field-add attempts.

Recommendation: **F13a**. It matches entity-add idempotency.

G0 decision (2026-05-13): **F13a locked**. Re-adding an equivalent post-add
class is a no-op with empty `added_entities` and `added_fields`.

### Q14. Application layer organization

- **F14a** Extend `kernel.application.schema_mutation_runtime`; do not create a
  second runtime module. Recommended.
- **F14b** Create `schema_field_mutation_runtime.py`.

Recommendation: **F14a**. Field-add is the second case in the same additive
schema mutation authority.

G0 decision (2026-05-13): **F14a locked**. Extend
`kernel.application.schema_mutation_runtime`; do not create a second runtime.

### Q15. DSL predicate-id normalization

- **F15a** Add a focused regression if rules/inferences using newly added fields
  expose a predicate-prefix mismatch; fix only if required for field-add tests.
  Recommended.
- **F15b** Broaden scope to normalize all SDK DSL predicate-prefix generation.
- **F15c** Ignore DSL paths and test only read/write.

Recommendation: **F15a**. Do not expand the slice unless field-add actually
needs the fix, but do not leave a broken new-field rule path untested.

G0 decision (2026-05-13): **F15a locked**. Add only focused DSL-prefix
regression/fix work if field-add tests expose the existing mismatch.

### Q16. Public docs

- **F16a** Same-slice docs update for schema mutation docs and SDK API docs.
  Recommended.
- **F16b** Defer docs to a follow-up.

Recommendation: **F16a**. Public schema mutation behavior changes.

G0 decision (2026-05-13): **F16a locked**. Module docs update in the same
slice.

### Q17. Entity type identity for replacement classes

- **F17a** Entity type identity continues to come from the Python class name;
  field-add requires a replacement declaration with the same class name.
  Recommended.
- **F17b** Add `Entity.Meta.entity_type` override in the same slice.
- **F17c** Allow `UserV2` to target existing `User` by convention.

Recommendation: **F17a**. It matches current compilation behavior. `UserV2`
is a new entity type today, and adding an entity-type override would be a
separate schema declaration feature.

G0 decision (2026-05-13): **F17a locked**. Existing entity replacement requires
a replacement class declaration with the same Python class name.

## 8. Acceptance

- [x] G0 locks the field-add API and class replacement semantics.
- [x] G1 inventory covers Python class replacement, result shape, missing-value
  reads, descriptor writes, saved asset compatibility, digest anchors, and
  workspace save-time behavior.
- [x] G1 baseline includes guards preserving entity-add behavior.
- [x] G2 implementation keeps validation preflight before state mutation.
- [x] G2 implementation preserves lifecycle/assets invariants from prior
  slices.
- [x] G3 updates affected SDK/application docs.
- [x] G4 fills Outcome / Deviations and archives the blueprint pair.

## 9. Implementation Plan

1. G1 red baseline for field-add and preservation guards. Expected size:
   roughly 30-40 tests covering field-add API, result DTO shape, class
   replacement, old class/descriptor rejection, missing-value reads, digest
   anchors, workspace save-time behavior, saved asset compatibility,
   idempotent re-add, validator extension, and preservation guards.
2. Extend `schema_mutation_runtime` to compute added fields and class
   replacement plans.
3. Update SDK `fg.schema.add(...)` state refresh to replace same-entity class
   declarations after validation.
4. Preserve digest-anchor and workspace save-time behavior.
5. Add saved rule/inference compatibility tests for added fields.
6. Sync docs and archive.

## 10. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview_en.md`

## 11. Outcome / Deviations

Implemented 2026-05-13.

### Final Behavior

- `fg.schema.add(...)` now supports same-entity replacement classes that add
  non-identity fields.
- Replacement classes must preserve the existing entity type, identity model,
  existing predicates, relationship targets, field type domains, and
  cardinality.
- Field-add rejects identity-field addition, existing-field rewrites, field
  removals, predicate collisions, and stale class/descriptor usage.
- `SchemaAddResult` now returns `added_fields` alongside `added_entities`.
- Existing assertions are not backfilled. Missing added single-cardinality
  fields read as `None`; missing added multi-cardinality fields read as `()`.
- Re-adding an equivalent replacement class is idempotent and returns empty
  `added_entities` and `added_fields`.
- Active SDK/core schema state, ledger schema digest, and graph-bound registry
  schema IR update immediately after validation.
- Workspace manifests remain save-time: `fg.schema.add(...)` does not rewrite
  the manifest until explicit `fg.save(...)`.
- Saved rules/inferences compiled before field-add remain loadable; new saved
  assets may reference added fields.
- `FactGraph.load(...)` after saved field-add requires post-add Python classes;
  pre-add classes fail schema digest validation.
- `fg.schema.delete/update/migrate/deprecate` remain absent.

### Validation

- Field-add lifecycle suite: 33/33 OK.
- Schema mutation + lifecycle/assets preservation + SDK invariant stack:
  217/217 OK.
- `git diff --check` clean.

### Lineage

```text
88728ed3 docs(sdk): document schema field add lifecycle
fae2d142 feat(sdk): wire schema field add replacement
e88bfad3 feat(application): extend schema mutation for field add
4a9abdc6 test(sdk): add schema field add lifecycle baseline
859c3b2c docs(blueprints): scope schema field add lifecycle
27081d61 docs(blueprints): refine schema field add lifecycle draft
b8b7ba0c docs(blueprints): draft schema field add lifecycle
```

### Deviations

- The planned G2.3 verification-only commit was collapsed into G2.2 because
  G2.2 made the full field-add suite green and the digest/workspace behavior
  was already covered by existing schema mutation and workspace runtime paths.
- No broad DSL predicate-prefix normalization was needed. The focused
  CamelCase field-add regression passed with the existing compiler-generated
  predicate path.

### Archive Notes

This slice extends the additive schema mutation thread from entity-only add to
non-identity field-add while preserving the same Path C application-runtime
authority, three-anchor digest handling, and workspace save-time boundary.
Remaining schema evolution work is now genuinely migration-shaped:
relationship schema extension, identity changes, field defaults/backfill,
delete/deprecate/update/migrate planning, and class-less dynamic load remain
future slices.
