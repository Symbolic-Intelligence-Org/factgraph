# SDK Read/Write and Ingest Reference

Scope: `store.py`, `facade.py`, `batch.py`, `ingest.py`. For the
introductory walkthrough see [`00_user_guide.en.md`](00_user_guide.en.md);
for the API index see [`04_api_surface.en.md`](04_api_surface.en.md).

In the snippets below, `fg = FactGraph.create(schema_classes=[...])`.
The public API is split by navigation key. Flat top-level shortcuts and the
old `fg.read.*` / `fg.write.*` managers were removed in Slice 3a.

| Layer | Namespace | Methods |
|---|---|---|
| Entity | `fg.entities.*` | `get`, `where`, `match`, `ref`, `create`, `delete`, `exists`, `edit` |
| Field | `fg.fields.*` | `set`, `add`, `retract`, `delete`, `get` |
| Assertion | `fg.assertions.*` | `where`, `by_id`, `by_ids`, `retract`, `active`, `all` |
| Schema / ingest | `fg.schema.*` | `register`, `extend`, `apply`, `ingest`, `validate_provenance` |

`fg.batch(...)` remains a top-level transaction builder rather than a write
manager method.

## 1. Choosing a Write Entry

| Scenario | Recommended API | Notes |
| --- | --- | --- |
| Build object graph, preview, replay/export | `fg.batch()` | Supports `preview()`, `commit()`, wire plan |
| Materialize an entity anchor bundle | `fg.entities.create(...)` | Eagerly emits the complete Identity Claim bundle; user-facing paths no longer emit new `<EntityType>:exists` Claims |
| Edit an existing entity with known identity | `fg.entities.edit(...)` | Clear write intent |
| External batch import with diagnostics | `fg.schema.ingest(...)` | Item-level validation, collect-and-stop |
| Write or clear one field | `fg.fields.set / add / retract / delete` | Schema-aware Layer 2 writes |
| Retract a specific assertion id | `fg.assertions.retract(...)` | Layer 3; Identity Claims and legacy `:exists` Claims are protected |

## 2. Building `FactGraph`

```python
fg = FactGraph.create(schema_classes=[User, Country, LivesIn])
```

File-backed ledger:

```python
fg = FactGraph.create(
    schema_classes=[User, Country, LivesIn],
    ledger_path="./data/ledger.db",
)
```

To make explain artifacts readable across later `FactGraph` instances as well, you can also provide:

```python
fg = FactGraph.create(
    schema_classes=[User, Country, LivesIn],
    ledger_path="./data/ledger.db",
    artifact_store_root="./data/artifacts",
)
```

Stable contract:
- `classes` must be a non-empty `list[Entity subclass]`; `from_schema_classes(...)` / `schema_preflight_from_classes(...)` raise `SDKSchemaError`, while `SDKStore(...)` constructor-path checks raise `SDKStoreError`.
- `ledger` and `ledger_path` are mutually exclusive.
- `ledger_path` records `schema_digest` when the ledger is opened/created, and validates it on reopen.
- `artifact_store_root` is an optional `str`; when provided it enables sidecar-backed explain artifact readback, while omitting it keeps the default in-process explain registry behavior.
- `default_row_format` and `FACTPY_ROW_FORMAT` are legacy row-dispatch
  settings. T5 public evaluation uses `fg.eval.evaluate(...)` and returns
  `EvaluateResult`.

## 3. Direct Namespace Writes

### 3.1 `fg.entities.ref(...)`

- Builds canonical `idref_v1` from identity values.
- Requires the complete Form I `Identity()` bundle.
- Missing/unknown identity keys fail with `SDKStoreError`.

### 3.2 `fg.fields.set(...)` / `fg.fields.add(...)`

```python
age_asrt_id = fg.fields.set(User.age, user_ref, 31, meta={"source": "hr"})
name_asrt_id = fg.fields.add(User.name, user_ref, "Alicia", meta={"source": "hr"})
```

Stable contract:
- `set(...)` and `add(...)` return the persisted assertion id (`asrt_id`).
- Value type is validated against schema `type_domain`.
- If the current `SDKStore` already knows the identity values for `e_ref`, matching identity predicates are materialized before the field write; arbitrary external canonical `idref_v1` values are not enough to guarantee this backfill.
- Low-level `set/add` do not strongly enforce cardinality; cardinality guards are mainly provided by batch/edit/ingest facades.

### 3.3 `fg.fields.retract(...)` / `fg.assertions.retract(...)`

```python
fg.fields.retract(User.name, user_ref, "Alice", meta={"trace_id": "fix-1"})
fg.assertions.retract(asrt_id, meta={"trace_id": "fix-1"})
```

- Append-only revoke (no physical delete of claim rows).
- `fg.assertions.retract(...)` returns the revoker assertion id; re-retracting an already revoked
  assertion returns the existing revoker id.
- Unknown or invalid assertion ids raise `SDKStoreError`; unknown
  assertion ids use `code="ASSERTION_NOT_FOUND"`. The underlying core
  `WriteProtocolError` is preserved as `__cause__` for debugging.
- Identity Claims raise `INV_7C_IDENTITY_PROTECTED`. Legacy
  `<EntityType>:exists` Claims, when present in older ledgers or
  compatibility paths, raise `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`.

## 4. Batch Writes (`sdk.batch()`)

### 4.1 Typical flow

```python
with sdk.batch(meta={"trace_id": "seed"}) as tx:
    alice = tx.entity(User, user_id="u1", locale="zh")
    alice.name.add("Alice")
    alice.age.set(30)

    plan = tx.preview()
    result = tx.commit()
```

Additional semantics:
- Batch meta merge precedence is `commit_meta > field_op_meta > entity_meta > batch_meta`.
- `with sdk.batch() as tx:` context manager does not auto-commit or auto-rollback; you must call `commit()` explicitly.

### 4.2 Cardinality and identity constraints

- `single` fields only allow `.set(...)` (wrong op raises `SDKStoreError` in `fg.batch()`, and `CardinalityError` in `fg.entities.edit()`).
- `multi` fields only allow `.add(...)` (wrong op raises `SDKStoreError` in `fg.batch()`, and `CardinalityError` in `fg.entities.edit()`).
- Batch managed-handle retract is by assertion id: `.retract(assertion_id=...)` (positional argument is also supported); `fg.entities.edit()` `FieldEditor` uses `.retract(asrt_id=...)`.
- Identity fields expose read-only guards; `set/add/retract` fail.
- `tx.entity(...)` requires the complete identity bundle: every `Identity()` value must be supplied at handle creation.
- `bind(...)` does not add or alter identity fields.
- Incomplete identity causes immediate `SDKStoreError` on field operations, preview, or commit; provide the full identity bundle first.

### 4.3 Wire plan

- `plan.export(sdk) -> WireBatchPlan`
- `WireBatchPlan.to_json()/from_json(...)`
- `WireBatchPlan.apply(sdk, strict_schema=True)`

`sdk_batch_plan_v1` notes:
- Wire ops no longer carry `dims/fact_key`.
- `cardinality` uses `single|multi`.
- Wire export (`to_json`/`export`) rejects raw `idref_v1` token values; use same-tx handles for entity references.

## 5. Entities Read and Edit

### 5.1 `fg.entities.get(...)`

```python
snap = fg.entities.get(User, user_id="u1", locale="zh")
```

- Identity kwargs only.
- Returns `EntitySnapshot | None`.
- Snapshot from `get` has `identity_available=True`.

### 5.2 `fg.entities.where(...)`

```python
rows = fg.entities.where(User, age=30, limit=20)
```

Stable contract:
- `limit` must be a non-negative integer.
- Filter keys must be entity identity or field names.
- Identity filters may be partial, including primary-only filters; combine
  them with field filters when you need AND semantics.
- `view=` is not accepted on `find(...)`. Frozen assertion views are read
  back via `fg.views.get(name).asrt_ids` plus
  `fg.assertions.by_ids(...)`, not by passing a view to snapshot reads.
- `policy=` is removed. Read-time confidence/display aggregation is not a
  public SDK surface.
- `temporal_view` parameter is not supported.

Filter semantics:
- `single`: exact equality.
- `multi`: containment (`expected in tuple_value`).
- Entity-ref fields accept either canonical `ref` or `EntitySnapshot` (`.ref` is used).

### 5.3 `fg.entities.edit(...)`

```python
with fg.entities.edit(User, user_id="u1", locale="zh") as user:
    user.age.set(31)
    user.name.add("Alicia")
```

Stable contract:
- Missing target entity -> `EntityNotFoundError`.
- Normal context exit -> commit; exception path -> rollback.
- Reusing a closed editor -> `EditorClosedError`.

## 6. `EntitySnapshot` and Assertion Views

### 6.1 Snapshot value shape

- `single` field: scalar or `None`
- `multi` field: `tuple[...]`
- Snapshot is immutable (`FrozenSnapshotError` on writes)
- `single` is a read-side scalar view only; writes do not auto-prune older assertions.

### 6.2 `snapshot.assertions.field(...)`

- `.active`: currently non-revoked assertions as an `AssertionRecordSet`
- `.all`: active plus revoked assertions as an `AssertionRecordSet`
- `.history`: deprecated compatibility alias for `.all`; it warns only when
  `FACTGRAPH_WARN_DEPRECATED=1`
- `.at(t)`: shortcut for `.active.at(t)`, filtering active
  assertions by business valid time
  `valid_from <= t` and (`valid_to` missing or `valid_to > t`)

Legacy call forms such as `.active()` and `.all()` remain accepted; the returned
`AssertionRecordSet` is callable and returns itself.

`AssertionRecordSet` is tuple-compatible (`len(...)`, indexing, and
iteration still work) and adds read-side selection helpers:

```python
target = snapshot.assertions.field("name").history.where(
    value="Alice",
    _meta={"source": "seed"},
).one()
fg.assertions.retract(target.asrt_id)

same = snapshot.assertions.field("name").history.by_id(target.asrt_id).one()
```

The same helpers work on whatever assertion set you start from:

```python
snapshot.assertions.name.active.where(_meta={"source": "seed"})
snapshot.assertions.name.history.at("2026-05-01T00:00:00Z")
snapshot.assertions.name.history.where(_meta={"version": "v1"})
snapshot.assertions.name.history.by_id(asrt_id)
```

Boundaries:
- Missing `valid_from` is excluded from `.at(t)`.
- `valid_to` is exclusive when present: `[valid_from, valid_to)`.
- `.at(t)` filters business valid time from `valid_from` / `valid_to`,
  not `ingested_at`.
- `.at(t)` validates ISO 8601 for both input and assertion meta fields.
- Version filtering is ordinary metadata filtering:
  `.where(_meta={"version": "v1"})`.
- `snapshot.assertions` covers only `Field` attributes, not `Identity` attributes.

## 7. Ingest (`fg.schema.ingest(...)`)

### 7.1 Supported item shapes

```python
{"kind": "set", "field": User.age, "e_ref": user_ref, "value": 31, "meta": {...}}
{"kind": "add", "field": User.name, "e_ref": user_ref, "value": "Alias", "meta": {...}}
{"kind": "retract", "asrt_id": "...", "meta": {...}}
```

### 7.2 Diagnostics behavior

- SDK pre-validates all items with `items[i].*` paths.
- Any `severity="error"` triggers collect-and-stop (whole batch is not written).
- Warnings do not block writes.
- After precheck, cache-resolvable `set/add/retract` items delegate to application `apply_ingest_request(...)`; when the target or entity_ref value cannot be recovered from the SDK identity cache, SDK conservatively falls back to the legacy write path.

### 7.3 Meta behavior

- Top-level `meta` and item `meta` merge; item keys override top-level keys.
- Hard-reserved keys: `ingested_at`, `ingest_key`, `revoked_asrt_id` (user writes are rejected).
- `ingest_key` idempotency material includes:
  `claim + source + source_loc + trace_id + valid_from + valid_to + version`

### 7.4 Result shape

`IngestResult`:
- `written_assertion_ids`
- `skipped_count`
- `duplicate_count`
- `warnings`
- `diagnostics`
- `diagnostics_contract_version`

## 8. Provenance Validation (`fg.schema.validate_provenance`)

```python
report = fg.schema.validate_provenance(obj, standard="derivation_v1")
```

Inputs:
- provenance/meta `dict` payloads

Required keys for `derivation_v1`:
- `derived_rule_id`
- `derived_rule_version`
- `run_id`
- `support_kind`
- `support_digest` (`sha256:<hex>`)

Output:
- `ValidationReport.ok`
- `ValidationReport.warnings`
- `ValidationReport.errors`
- `ValidationReport.diagnostics_contract_version`

---

## Annotation Store (Semantic Annotation Layer)

The Annotation Store is the canonical semantic annotation layer for facts. `meta_rows` remains available as the SDK selection / review mirror used by assertion filtering and returned `AssertionMeta`.

### Core Concepts

- **`AnnotationRow`**: `(asrt_id, namespace, category, key, kind, value, origin, derivation)`
- **namespace**: `shared` (framework-wide) / `pyreason` / `problog` / `souffle`
- **category**: `source` (provenance info) / `semantic` (fact truth semantics) / `derived` (computed summaries) / `operational` (status flags)
- **origin**: `observed` (directly recorded) / `derived` (computed by mapping function)

### Write Paths

1. **Shared path (automatic)**: `write_protocol.set_field()` projects whitelisted meta keys (for example `source`, `raw_kind`, and `bound`) into `annotation_rows`
2. **PyReason path**: `persist_pyreason_annotations(ledger, run_id, store, accept_result)` writes `pyreason/semantic/bound_lower`, `bound_upper`, etc. post-accept
3. **ProbLog path**: `persist_problog_annotations(ledger, run_id, store, accept_result)` writes `problog/semantic/probability` post-accept

### Read Paths

- `ledger.find_annotations(asrt_id=..., namespace=..., category=...)` — query by criteria
- Audit package automatically exports `assertion_annotations.jsonl`
- Static HTML assertion detail pages automatically render annotation panels grouped by namespace

### Relationship to meta_rows

`meta_rows` is a selection / review mirror. Canonical semantic consumers should read the Annotation Store, while `AssertionRecordSet.where(_meta=...)` and `AssertionRecord.meta.raw` continue to use `meta_rows`.

Raw uncertainty note:

- user-authored raw uncertainty uses paired meta:

  ```python
  fg.fields.set(
      Risk.level,
      ref,
      "elevated",
      meta={"raw_kind": "probabilistic", "bound": [0.2, 0.8]},
  )
  ```

- `raw_kind` must be exactly `"probabilistic"` or `"possibilistic"`
- `bound` must be a two-element JSON list; numeric `int` / `float` elements
  are accepted, bools and numeric strings are rejected, and the stored value is
  normalized to floats
- both keys must be provided together
- the write produces:
  - `shared/semantic/raw_kind`
  - `shared/semantic/bound`
  - mirrored `meta.raw_kind`
  - mirrored `meta.bound`
- user-authored `probability`, `bound_lower`, and `bound_upper` meta are
  rejected. Those names are reserved for adapter projection / output lanes.

Adapter notes:

- for accepted ProbLog facts, `problog/semantic/probability` is the
  engine-native semantic lane
- ProbLog export reads in this order:
  1. `problog/semantic/probability`
  2. `shared/semantic/probability`
  3. default `1.0`
- `shared/semantic/probability` can still exist as an adapter/internal
  annotation, but it is not the user-facing raw uncertainty write contract
- `confidence` and `confidence_source` are removed user-authored write meta
  keys; use `raw_kind` and `bound` for uncertainty inputs
