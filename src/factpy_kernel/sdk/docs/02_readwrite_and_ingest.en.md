# SDK Read/Write + Ingest Reference (v1)

Scope: `store.py`, `facade.py`, `batch.py`, `ingest.py`

## 1. Choosing a Write Entry

| Scenario | Recommended API |
|---|---|
| Build graph + preview/replay | `sdk.batch()` |
| Edit one known entity | `sdk.edit(...)` |
| External scripted writes / only `ref + asrt_id` | `sdk.ingest(...)` |
| Minimal direct write | `sdk.ref/set/add/retract` |

## 2. Low-Level Writes

- `sdk.ref(...)`: builds canonical `idref_v1` from identity (supports defaults and `uuid4` factory path).
- `sdk.set(...)`, `sdk.add(...)`: type/dims validation is enforced; cardinality is not strongly enforced at this layer.
- `sdk.retract(...)`: append-only revoke by `asrt_id`.

## 3. `sdk.batch()`

- `tx.entity(...)` creates/reuses managed handles by `e_ref`.
- `preview()` builds a read-only plan.
- `commit()` applies plan writes.
- `to_json(sdk)` / wire replay available through `WireBatchPlan`.

Cardinality on managed field handles:
- functional -> `.set(...)`
- multi -> `.add(...)`
- retract -> `.retract(assertion_id=...)`

Dependency closure:
- default `include_deps=True`
- `include_deps=False` fails at preview/commit if dependencies are missing.

## 4. `sdk.get/find/edit`

### `sdk.get(...)`
- identity kwargs only
- returns `EntitySnapshot | None`
- snapshot from `get` has `identity_available=True`

### `sdk.find(...)`
- supports `"record"` / `"current"` temporal view
- supports `limit`
- unknown filters raise `SDKSchemaError`
- if identity filters are used, all identity fields are required
- dims filtering is currently unsupported

Filter semantics:
- functional: exact match
- multi/temporal: containment match
- entity_ref: canonical ref exact match (`ref` or snapshot accepted)

### `sdk.edit(...)`
- requires identity
- missing entity -> `EntityNotFoundError`
- context exit without exception -> commit
- context exit with exception -> rollback
- closed editor reuse -> `EditorClosedError`

`FieldEditor` cardinality:
- wrong set/add usage -> `CardinalityError`

## 5. Snapshot + Assertion View

- Snapshot values:
  - functional -> scalar/None
  - multi/temporal -> tuple
  - dimmed -> tuple of `DimensionedValue`
- Assertion view:
  - `.active`
  - `.history` (ledger history; not controlled by `temporal_view`)
  - `.chosen` (non-dim functional only)

## 6. `sdk.ingest(...)`

Supported item shapes:
- `set`: `field`, `e_ref`, `value` (+ optional `dims`, `meta`)
- `add`: `field`, `e_ref`, `value` (+ optional `dims`, `meta`)
- `retract`: `asrt_id` (+ optional `meta`)

Diagnostics behavior:
- SDK pre-validates all items.
- Any diagnostics `severity="error"` => collect-and-stop (whole batch not written).
- warnings do not block writes.

Meta behavior:
- top-level invalid meta can raise immediately (`SDKStoreError`)
- item-level invalid meta goes to diagnostics
- sensitive keys produce warnings by default

`IngestResult`:
- `written_assertion_ids`
- `skipped_count`
- `duplicate_count`
- `warnings`
- `diagnostics`
- `diagnostics_contract_version`

## 7. `sdk.validate_provenance(...)`

- input: `CandidateSet` or dict (flat-key shape)
- standard: `derivation_v1`
- output: `ValidationReport`
- validation-only; no ledger writes

