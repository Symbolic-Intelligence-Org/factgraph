# SDK Read/Write + Ingest Reference (v1)

This document describes the current behavior of read/write SDK APIs in `src/factpy_kernel/sdk`.

## 1. Choose the write entry

| Scenario | Recommended API | Why |
| --- | --- | --- |
| Build object graph, preview, replay wire plan | `sdk.batch()` | Handle-based staging + `preview()`/`to_json()` |
| Edit one known entity (identity available) | `sdk.edit()` | Focused context manager, auto-commit/rollback |
| Scripted writes or only `ref + asrt_id` available | `sdk.ingest()` | Dict-based write items, no identity lookup |
| Low-level direct write | `sdk.set/add/retract` | Immediate writes, no staging |

## 2. `sdk.batch(...)`

### 2.1 Core flow

```python
with sdk.batch(meta={"source": "seed"}) as tx:
    alice = tx.entity(Person, source_id="u1")
    de = tx.entity(Country, source_id="DE")

    alice.name.add("Alice")
    alice.country.set(de)  # handle reference

    plan = tx.preview()
    result = tx.commit()
```

### 2.2 Field op cardinality

- `functional` field: `.set(...)` only
- `multi` field: `.add(...)` only
- `temporal` field: not writable via batch handle in v1
- `retract`: `.retract(assertion_id="...")`

Wrong cardinality calls raise `SDKStoreError` on batch handles.

### 2.3 Dependency closure

- `preview(..., include_deps=True)` / `commit(..., include_deps=True)` include referenced handles automatically.
- With `include_deps=False`, missing dependencies raise `SDKStoreError` during `preview()`/`commit()`.

### 2.4 Wire plan caveat

`plan.to_json(sdk)` rejects raw `entity_ref` token values in staged set/add ops.
For replayable wire plans, relation values should be staged via handles (`tx.entity(...)` objects), not raw idref strings.

## 3. `sdk.get(...)` / `sdk.find(...)`

### 3.1 `sdk.get(entity_cls, **identity)`

- Accepts only identity kwargs.
- Returns `EntitySnapshot | None`.
- For identity fields with `default_factory="uuid4"`, caller must pass explicit value.

### 3.2 `sdk.find(entity_cls, ..., **filters)`

Supported kwargs:

- identity fields
- declared entity fields

Filter semantics:

- functional field: exact match on current value
- multi/temporal field: contains match on current tuple
- entity-ref field: exact match on idref token
  - passing `EntitySnapshot` filter value is supported and mapped to `.ref`

Important behavior:

- If any identity filters are provided, all identity fields must be provided, otherwise `SDKSchemaError`.
- `temporal_view` supports `"record"` and `"current"`.
- dims-field filtering is currently unsupported and raises `SDKSchemaError`.

## 4. `EntitySnapshot`

### 4.1 Read-only contract

- `snapshot.ref`: canonical idref token
- `snapshot.entity_type`: schema entity type name
- direct assignment is forbidden (`FrozenSnapshotError`)

### 4.2 Identity hints

- `snapshot.identity_available: bool`
- `snapshot.identity: dict[str, Any]`

If `identity_available` is `True`, `sdk.edit(Type, **snapshot.identity)` is stable.
If `False`, use `ingest` path (`retract/set` by `ref` + `asrt_id`).

### 4.3 Field values

- functional without dims: scalar or `None`
- multi/temporal without dims: `tuple[...]`
- dimmed fields: tuple of `DimensionedValue(value=..., dims=...)`

### 4.4 Assertions API

```python
snap.assertions.name.active
snap.assertions.name.history
snap.assertions.country.chosen
```

- `.chosen` is valid only for functional fields without dims.
- `.chosen` on `multi`, `temporal`, or dimmed functional fields raises `CardinalityError`.

## 5. `sdk.edit(...)`

```python
with sdk.edit(Person, source_id="u1") as user:
    user.country.set("de")
    user.name.add("Alicia")
    user.name.retract(asrt_id="asrt_xxx")
```

Behavior:

- Requires identity kwargs (same input style as `get`)
- Target must exist, else `EntityNotFoundError`
- Context manager semantics:
  - no exception: auto `commit()`
  - exception: auto `rollback()`
- After `commit()`/`rollback()`, editor is closed; later ops raise `EditorClosedError`

`FieldEditor` cardinality:

- `.set(...)` only for functional fields
- `.add(...)` only for multi fields
- temporal fields are not writable via `FieldEditor` in v1
- `.retract(asrt_id="...")` explicit by assertion id

## 6. `sdk.ingest(...)`

### 6.1 Item schema (current dict-based shape)

- `{"kind": "set", "field": <Field>, "e_ref": str, "value": Any, "dims"?: ..., "meta"?: dict}`
- `{"kind": "add", "field": <Field>, "e_ref": str, "value": Any, "dims"?: ..., "meta"?: dict}`
- `{"kind": "retract", "asrt_id": str, "meta"?: dict}`

### 6.2 Validation and write behavior

- SDK pre-validates all items and collects diagnostics (`items[i].*` path format).
- If any diagnostic has `severity="error"`, whole batch is not written (collect-and-stop).
- Warnings do not block writes.

### 6.3 Meta checks

- Hard reserved keys: `ingested_at`, `ingest_key`, `revoked_asrt_id`
- Top-level `meta` with hard-reserved keys raises `SDKStoreError` immediately.
- Item-level invalid `meta` is reported as per-item diagnostics error.

Sensitive semantic keys (for example `derived_rule_id`, `run_id`, `support_digest`) produce warnings by default.
Use `allow_sensitive_meta=True` to suppress these warnings.

### 6.4 `IngestResult`

- `written_assertion_ids: list[str]`
- `skipped_count: int`
- `duplicate_count: int`
- `warnings: list[dict]`
- `diagnostics: list[dict]`
- `diagnostics_contract_version: int`

## 7. `sdk.validate_provenance(...)`

Supported input:

- `CandidateSet`
- `dict` (meta-like payload)

Current standard: `standard="derivation_v1"`

Returns `ValidationReport`:

- `ok: bool`
- `warnings: list[dict]`
- `errors: list[dict]`
- `diagnostics_contract_version: int`

## 8. Known v1 boundaries

- No `sdk.create(...)` yet.
- No `sdk.save(plain_entity)` / `snapshot.to_entity()` write-back workflow.
- Ingest item type is still dict-based (TypedDict/dataclass intentionally deferred).
