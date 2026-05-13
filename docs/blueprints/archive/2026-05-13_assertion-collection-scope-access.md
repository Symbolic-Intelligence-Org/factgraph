# Task Blueprint: Assertion Collection Scope Access

- Status: implemented
- Created: 2026-05-13
- Last Updated: 2026-05-14
- Related Modules:
  - `src/kernel/sdk/facade.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/tests/test_sdk_assertion_record_set.py`
  - `src/kernel/tests/test_official_kernel_docs_baseline.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-13_readpolicy-confidence-meta-removal.md](../archive/2026-05-13_readpolicy-confidence-meta-removal.md)
  - [src/kernel/sdk/docs/00_user_guide.en.md](../../../src/kernel/sdk/docs/00_user_guide.en.md)
  - [src/kernel/sdk/docs/02_readwrite_and_ingest.en.md](../../../src/kernel/sdk/docs/02_readwrite_and_ingest.en.md)
  - [src/kernel/sdk/docs/04_api_surface.en.md](../../../src/kernel/sdk/docs/04_api_surface.en.md)
  - [docs/official/kernel/quickstart/assertions.md](../../../docs/official/kernel/quickstart/assertions.md)
- Audit Log:
  - [2026-05-13_assertion-collection-scope-access.audit.md](./2026-05-13_assertion-collection-scope-access.audit.md)

## 1. Problem

Assertion record selection currently becomes ergonomic only after the user has
already selected a field:

```python
snap.field("name").history.where(
    value="Alice",
    source="seed",
    trace_id="import-001",
).one()
```

The chain works because `.history` returns an `AssertionRecordSet`, and the
selection DSL (`where`, `at`, `version`, `by_id`, `one`, `first`, `all`) lives
on `AssertionRecordSet`.

At the snapshot and graph levels, the equivalent assertion collection entry
points do not exist. `snap.assertions` is a field-name namespace and
`fg.assertions` is a by-id manager. The current docs explicitly say
`snap.assertions.where(...)`, `fg.assertions.active`, `fg.assertions.history`,
and graph-wide assertion queries are not supported.

That split makes users learn three shapes for one mental model:

- field-level assertion record sets;
- snapshot-level field namespaces;
- graph-level by-id lookup.

The scoped cleanup is to make `snap.assertions` and `fg.assertions` behave
like scoped assertion collection managers. They should expose the same core
verbs and return `AssertionRecordSet` wherever selection is expected.

## 2. Goals

- Unify assertion collection access across field, snapshot, and graph scopes.
- Preserve `AssertionRecordSet` as the selection DSL carrier.
- Add explicit snapshot-level field selection under `snap.assertions.field(...)`.
- Add graph-level field selection under `fg.assertions.field(...)`.
- Add `active()` and `all()` collection entry points for snapshot and graph scopes.
- Prefer `all()` over `history()` for active-plus-revoked records to avoid
  ledger/audit history ambiguity.
- Avoid field-name collisions such as a schema field named `active`.
- Add record context needed once record sets can span multiple fields or the
  whole graph.
- Keep the API small enough that pagination, sorting, and richer graph query
  planning can remain future work.

## 3. Non-goals

- Do not introduce a general graph query language.
- Do not add pagination or streaming in this slice.
- Do not add arbitrary predicate algebra beyond `AssertionRecordSet.where(...)`.
- Do not change write semantics or retract-by-id safety.
- Do not expose `AssertionRecordSet` through `kernel.sdk.__all__`.
- Do not add inference fact-universe scoping or frozen-view evaluation scoping.
- Do not move `Query` out of `fg.eval.run(...)` in this slice.
- Do not add `AssertionRecordSet.match(query)` or assertion-set-scoped Query
  execution in this slice.
- Do not add a "view as new FactGraph" construction API in this slice.

## 4. Current Context

- `AssertionRecordSet` lives in `src/kernel/sdk/facade.py` and currently owns:
  - `where(...)`
  - `at(...)`
  - `version(...)`
  - `by_id(...)`
  - `one()`
  - `first()`
  - `all()`
- `FieldAssertions` currently owns field-local:
  - `.active` property
  - `.history` property
  - `.at(t)` shortcut over active
  - `.version(v)` shortcut over active
- `AssertionNamespace` currently provides field attribute access:
  - `snap.assertions.name`
- `_SDKAssertionsManager` currently provides graph by-id access:
  - `fg.assertions.by_id(asrt_id)`
  - `fg.assertions.by_ids(asrt_ids)`
- Current SDK `Query` is not an assertion-returning surface:
  - entity heads return `EntitySnapshot` values;
  - scalar heads return raw projected values;
  - existing tests assert that `Query` entity snapshots expose empty field
    assertion sets.
  Query therefore cannot currently provide `asrt_id` values for a
  `query -> asrt_ids -> view/new graph -> assertion filtering` pipeline without
  additional runtime design.
- Official docs now have a dedicated assertion records page, but still document
  snapshot-wide and graph-wide collection queries as unsupported.
- SDK `AssertionRecord.is_revoked` is currently a pure read-side derivative of
  `not is_active` during SDK record construction. Local survey found no SDK
  runtime decision path consuming it; docs expose it as a first-class record
  field. Service/audit/agent DTOs have their own `is_revoked` fields and are
  outside this SDK surface cleanup unless a later scope expansion says
  otherwise.
- The product is unreleased, so public SDK hard cuts are allowed when they
  produce a cleaner surface.

## 5. Scoped Shape

### 5.1 Shared manager verbs

Both `snap.assertions` and `fg.assertions` should expose:

```python
assertions.by_id(asrt_id)
assertions.by_ids(asrt_ids)
assertions.field(...)
assertions.active()
assertions.all()
```

`active()` returns currently active assertion records in the manager's scope.
`all()` returns active plus revoked assertion records in the manager's scope.
Both return `AssertionRecordSet`.

### 5.2 Snapshot scope

Snapshot scope is constrained to one entity snapshot and all of its field
assertions:

```python
snap.assertions.field("name").active().where(source="seed")
snap.assertions.active().where(source="seed", trace_id="import-001").one()
snap.assertions.all().where(meta={"version": "tag-v1"}).all()
snap.assertions.by_id(asrt_id)
snap.assertions.by_ids([asrt_id])
```

`snap.assertions.field(name)` returns a field-scoped assertion collection.
The old `snap.assertions.<field>` attribute access should be removed or
rejected in this slice to avoid collisions with manager methods such as
`active()` and `all()`. Field names should be reached explicitly through
`.field(name)`.

`snap.assertions.field(...)` accepts both a string field name and an SDK
`Field` descriptor. The snapshot already fixes the entity type, so `"name"` is
unambiguous and `User.name` remains available for IDE/refactor support.

### 5.3 Graph scope

Graph scope is all assertions in the graph:

```python
fg.assertions.active().where(source="seed")
fg.assertions.all().where(trace_id="import-001")
fg.assertions.by_id(asrt_id)
fg.assertions.by_ids(asrt_ids)
fg.assertions.field(User.name).active().where(source="seed")
```

Graph `field(...)` accepts only SDK `Field` descriptors (`User.name`) because
string field names can collide across entity types. String field names are
rejected at graph scope.

### 5.4 Field scope

Field scope should align with the manager vocabulary:

```python
snap.assertions.field("name").active()
snap.assertions.field("name").all()
```

The existing field-level `.active` and `.history` properties are candidates for
hard-cut removal or compatibility aliases. The preferred new vocabulary is:

- `active()` for currently non-revoked records;
- `all()` for active plus revoked records.

Scope-freeze decisions:

- `snap.assertions.<field>` attribute access is removed; `.field(name)` is the
  only snapshot assertion field selection path.
- `FieldAssertions.active` and `FieldAssertions.history` properties are
  removed; `active()` and `all()` are the field-level record-set entry points.
- SDK `AssertionRecord.is_revoked` is removed; `not record.is_active` is the
  revoked/inactive check.

### 5.5 Assertion record context

Cross-field and graph-wide record sets need enough context for users to
understand what a returned record represents. Extend `AssertionRecord` with:

- `entity_type`
- `field_name`
- `pred_id`
- `e_ref`

These are read-side context fields. They do not change write protocol or core
ledger shape.

`pred_id` intentionally overlaps with `(entity_type, field_name)`.
`pred_id` is the canonical kernel predicate id; `entity_type` and
`field_name` are user-facing SDK names. Both are kept because SDK code, audit
displays, and lower-level inspection need different anchors.

### 5.6 Derived status field cleanup

Remove `AssertionRecord.is_revoked` from the SDK record surface in the same
slice. At the SDK level it is fully derivable as `not record.is_active` and is
not consumed internally. Removing it keeps the record status model
single-source:

```python
record.is_active
not record.is_active   # revoked / inactive at read time
```

This cleanup is scoped to SDK `AssertionRecord` and SDK docs/tests. It does not
remove service/audit/agent `is_revoked` DTO fields, which have separate wire
contracts.

### 5.7 Query and view composition note

There is a useful future model where Query/search and assertion collection
selection compose:

```text
original fg -> run query -> asrt_ids -> frozen view / scoped graph
    -> assertions.active().where(...).all()
```

That is not current behavior. Current `Query` rows do not carry the assertion
ids that witnessed the match, and Query-returned entity snapshots do not carry
field assertion records. Supporting this composition would require a separate
design for Query witness/assertion returns or assertion-set-scoped Query
execution.

This blueprint keeps that future direction visible but out of scope. A later
blueprint should address Query/Search taxonomy separately from Inference:

- Query/Search: find existing rows/facts/assertions.
- Inference: produce candidate facts for acceptance.

Potential future surfaces include `fg.read.query(...)`, `fg.query.match(...)`,
or `AssertionRecordSet.match(query)`, but none are part of this slice.

## 6. Boundaries And Invariants

- `AssertionRecordSet` remains tuple-compatible.
- `AssertionRecordSet.where(...)` remains the filtering DSL; managers produce
  record sets rather than becoming independent query builders.
- `by_id(...)` returns `AssertionRecord | None` at manager scope.
- `by_ids(...)`, `active()`, `all()`, and `field(...).active()/all()` return
  `AssertionRecordSet`.
- `AssertionRecordSet.all()` remains the terminal tuple conversion helper.
- If `AssertionRecord.is_revoked` is removed, `is_active` is the only SDK
  first-class status boolean and revoked state is expressed as
  `not record.is_active`.
- `snap.assertions.active()` and `snap.assertions.all()` never leave the
  snapshot's entity scope.
- `fg.assertions.active()` and `fg.assertions.all()` may scan the current graph
  in-memory/ledger state in this slice; pagination is deferred.
- Field-name collisions are resolved by explicit `.field(...)` selection, not
  attribute dispatch.
- Retract continues to accept assertion ids only.
- Record shape is uniform across field cardinality. A single-field assertion
  record and a multi-field assertion record expose the same SDK fields;
  cardinality affects collection membership, not record shape.
- Graph-scope `active()` and `all()` enumerate the current ledger eagerly in
  this slice. They do not push `.where(...)` predicates into ledger queries and
  they do not stream. Large graphs may need future pagination or streaming.
- `fg.assertions.*` is a ledger-level view, not snapshot projection and not
  read-policy filtering. An entity whose current facts are all retracted still
  has records visible through `fg.assertions.all()`.
- Frozen views remain id-set containers. Resolve a frozen view through the
  manager with `fg.assertions.by_ids(view.asrt_ids)`. View-scoped
  `.active()`, `.all()`, or `.field(...)` is not part of this slice.
- Query composition is explicitly deferred. `AssertionRecordSet.match(query)`
  and Query-returned assertion witness ids require a separate blueprint.

## 7. Acceptance

- [x] `snap.assertions.field("name").active()` returns the same records as the
  previous field active surface.
- [x] `snap.assertions.field("name").all()` returns active plus revoked records
  for that field.
- [x] `snap.assertions.active().where(...)` filters across all fields in the
  snapshot.
- [x] `snap.assertions.all().where(...)` can find revoked records across all
  fields in the snapshot.
- [x] `snap.assertions.by_id(asrt_id)` and `.by_ids(...)` work within snapshot
  scope.
- [x] `fg.assertions.active().where(...)` filters active records across the
  graph.
- [x] `fg.assertions.all().where(...)` filters active plus revoked records
  across the graph.
- [x] `fg.assertions.field(User.name).active()` filters graph records to the
  selected field.
- [x] `fg.assertions.field("name")` rejects string field names as ambiguous at
  graph scope.
- [x] `snap.assertions.field("name")` and
  `snap.assertions.field(User.name)` both work for the snapshot entity type.
- [x] `AssertionRecord` includes `entity_type`, `field_name`, `pred_id`, and
  `e_ref`.
- [x] `AssertionRecord` shape is the same for single-cardinality and
  multi-cardinality fields.
- [x] SDK `AssertionRecord.is_revoked` is removed as a pure derivative of
  `not is_active`; SDK docs/tests stop exposing it.
- [x] Field names that collide with manager methods are reachable through
  `.field("active")`.
- [x] Removed/renamed old field surfaces have clear tests and docs.
- [x] `quickstart/assertions.md` is rewritten around the unified assertion
  collection manager vocabulary.
- [x] `quickstart/namespace-map.md` expands the `fg.assertions` entry to cover
  `active`, `all`, `field`, `by_id`, and `by_ids`.
- [x] `quickstart/read-write.md` forward pointers to the assertion records page
  remain accurate.
- [x] SDK module docs describe the unified assertion collection manager model.

## 8. Implementation Plan

1. Add red/guard tests for the unified assertion manager API and context fields.
2. Introduce field-scoped assertion collection object with `active()` and
   `all()` methods returning `AssertionRecordSet`.
3. Replace snapshot `AssertionNamespace` with an explicit manager exposing
   `field`, `active`, `all`, `by_id`, and `by_ids`.
4. Extend graph `_SDKAssertionsManager` with `active`, `all`, and `field`.
5. Extend assertion record construction to include context fields.
6. Decide whether to remove SDK `AssertionRecord.is_revoked` as derived status
   surface, and update tests/docs if removed.
7. Decide and implement the field-property hard cut or aliases for old
   `.active` / `.history` surfaces.
8. Add explicit negative tests for deferred Query/assertion composition so the
   slice does not accidentally imply Query returns assertion witnesses.
9. Update SDK docs and official quickstart assertions page.
10. Run targeted assertion record tests, official docs baseline tests, and
   read/write SDK suites.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/official/kernel/quickstart/assertions.md`
- `docs/official/kernel/quickstart/namespace-map.md`

## 10. Outcome / Deviations

Final API shape:

- Field, snapshot, and graph assertion access now share manager vocabulary:
  `field(...)`, `active()`, `all()`, `by_id(...)`, and `by_ids(...)` where
  the verb is meaningful for that scope.
- `snap.assertions.field("name")` and `snap.assertions.field(User.name)` work
  for the snapshot entity type. Descriptors for another entity type are
  rejected.
- `fg.assertions.field(User.name)` works at graph scope; string field names
  are rejected at graph scope as ambiguous.
- `AssertionRecord` now carries `entity_type`, `field_name`, `pred_id`, and
  `e_ref`.

Hard cuts:

- Removed `snap.assertions.<field>` attribute dispatch.
- Removed field-level `.active` and `.history` properties; callers use
  `.active()` and `.all()`.
- Removed SDK `AssertionRecord.is_revoked`; revoked/inactive checks use
  `not record.is_active`.

Accepted limitations:

- Graph-wide `fg.assertions.active()` / `.all()` use eager ledger scans in
  this slice. Pagination, streaming, and pushed-down filtering remain future
  work.
- Query/Search composition remains deferred. Query-returned entity snapshots
  still do not carry assertion witness records, and
  `AssertionRecordSet.match(query)` remains absent.

Verification:

- `PYTHONPATH=src python -m unittest -v kernel.tests.test_sdk_assertion_collection_scope`
  = 15 OK.
- `PYTHONPATH=src python -m unittest -v kernel.tests.test_official_kernel_docs_baseline`
  = 7 OK.
- `PYTHONPATH=src python -m unittest discover -s src/kernel/tests`
  = 2214 OK, 1 skipped.
