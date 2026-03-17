# SDK Read/Write and Ingest Reference (Current Implementation)

Scope: `store.py`, `facade.py`, `batch.py`, `ingest.py`

## 1. Choosing a Write Entry

| Scenario | Recommended API | Notes |
| --- | --- | --- |
| Build object graph, preview, replay/export | `sdk.batch()` | Supports `preview()`, `commit()`, wire plan |
| Edit an existing entity with known identity | `sdk.edit(...)` | Clear write intent |
| External batch import with diagnostics | `sdk.ingest(...)` | Item-level validation, collect-and-stop |
| Lowest-level direct assertion writes | `sdk.ref/set/add/retract` | Most flexible, least opinionated |

## 2. Building `SDKStore`

```python
sdk = SDKStore.from_schema_classes([User, Country, LivesIn])
```

File-backed ledger:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, LivesIn],
    ledger_path="./data/ledger.db",
)
```

To make explain artifacts readable across later `SDKStore` instances as well, you can also provide:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, LivesIn],
    ledger_path="./data/ledger.db",
    artifact_store_root="./data/artifacts",
)
```

Stable contract:
- `classes` must be a non-empty `list[Entity subclass]`; `from_schema_classes(...)` / `schema_preflight_from_classes(...)` raise `SDKSchemaError`, while `SDKStore(...)` constructor-path checks raise `SDKStoreError`.
- `ledger` and `ledger_path` are mutually exclusive.
- `ledger_path` records `schema_digest` when the ledger is opened/created, and validates it on reopen.
- `artifact_store_root` is an optional `str`; when provided it enables sidecar-backed explain artifact readback, while omitting it keeps the default in-process explain registry behavior.
- `default_row_format` affects only `sdk.run(rule, ...)`; allowed values are `"tuple"` / `"dict"` (default `"dict"`).
- `FACTPY_ROW_FORMAT` is read and cached at `SDKStore` initialization time (not re-read on every `run()` call).
- Resolving to `"tuple"` emits `DeprecationWarning`; prefer `"dict"`.

## 3. Low-Level Writes (`ref/set/add/retract`)

### 3.1 `sdk.ref(...)`

- Builds canonical `idref_v1` from identity values.
- Supports `Identity.default` and `default_factory="uuid4"`.
- Missing/unknown identity keys fail with `SDKStoreError`.

### 3.2 `sdk.set(...)` / `sdk.add(...)`

```python
sdk.set(User.age, user_ref, 31, meta={"source": "hr"})
sdk.add(User.name, user_ref, "Alicia", meta={"source": "hr"})
```

Stable contract:
- Value type is validated against schema `type_domain`.
- If the current `SDKStore` already knows the identity values for `e_ref`, matching identity predicates are materialized before the field write; arbitrary external canonical `idref_v1` values are not enough to guarantee this backfill.
- Low-level `set/add` do not strongly enforce cardinality; cardinality guards are mainly provided by batch/edit/ingest facades.

### 3.3 `sdk.retract(...)`

```python
sdk.retract(asrt_id, meta={"trace_id": "fix-1"})
```

- Append-only revoke (no physical delete of claim rows).
- Returns the revoker assertion id; re-retracting an already revoked assertion returns the existing revoker id, while unknown assertions raise.

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

- `single` fields only allow `.set(...)` (wrong op raises `SDKStoreError` in `sdk.batch()`, and `CardinalityError` in `sdk.edit()`).
- `multi` fields only allow `.add(...)` (wrong op raises `SDKStoreError` in `sdk.batch()`, and `CardinalityError` in `sdk.edit()`).
- Batch managed-handle retract is by assertion id: `.retract(assertion_id=...)` (positional argument is also supported); `sdk.edit()` `FieldEditor` uses `.retract(asrt_id=...)`.
- Identity fields expose read-only guards; `set/add/retract` fail.
- Incomplete identity causes immediate `SDKStoreError` on writes; bind missing identity first via `bind(...)`.

### 4.3 Wire plan

- `plan.export(sdk) -> WireBatchPlan`
- `WireBatchPlan.to_json()/from_json(...)`
- `WireBatchPlan.apply(sdk, strict_schema=True)`

`sdk_batch_plan_v1` notes:
- Wire ops no longer carry `dims/fact_key`.
- `cardinality` uses `single|multi`.
- Wire export (`to_json`/`export`) rejects raw `idref_v1` token values; use same-tx handles for entity references.

## 5. Read and Edit (`get/find/edit`)

### 5.1 `sdk.get(...)`

```python
snap = sdk.get(User, user_id="u1", locale="zh")
```

- Identity kwargs only.
- Returns `EntitySnapshot | None`.
- Snapshot from `get` has `identity_available=True`.

### 5.2 `sdk.find(...)`

```python
rows = sdk.find(User, age=30, limit=20)
```

Stable contract:
- `limit` must be a non-negative integer.
- Filter keys must be entity identity or field names.
- If identity filters are used, all identity fields are required.
- `temporal_view` parameter is not supported.

Filter semantics:
- `single`: exact equality.
- `multi`: containment (`expected in tuple_value`).
- Entity-ref fields accept either canonical `ref` or `EntitySnapshot` (`.ref` is used).

### 5.3 `sdk.edit(...)`

```python
with sdk.edit(User, user_id="u1", locale="zh") as user:
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

### 6.2 `snapshot.assertions.<field>`

- `.active`: currently non-revoked assertions
- `.history`: full history (including revoked assertions)
- `.at(t)`: business-time filter on active assertions  
  `valid_from <= t` and (`valid_to` missing or `valid_to > t`)
- `.version(v)`: version filter on active assertions (`version == v`)

Boundaries:
- Missing `valid_from` is excluded from `.at(t)`.
- Missing `version` is excluded from `.version(v)`.
- `.at(t)` validates ISO 8601 for both input and assertion meta fields.
- `.version(v)` accepts only `str|int` (`bool` is invalid).
- `snapshot.assertions` covers only `Field` attributes, not `Identity` attributes.

## 7. Ingest (`sdk.ingest(...)`)

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

## 8. Provenance Validation (`sdk.validate_provenance`)

```python
report = sdk.validate_provenance(obj, standard="derivation_v1")
```

Inputs:
- `CandidateSet`
- `dict` (currently flat-key contract)

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
