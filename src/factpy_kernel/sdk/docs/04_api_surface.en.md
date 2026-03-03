# SDK API Surface Index (Current Implementation)

This page tracks the public exports in `factpy_kernel/sdk/__init__.py` and the main class APIs.

## 1. Top-Level Exports (`from factpy_kernel.sdk import ...`)

### 1.1 Schema / Store / Registry

- `Entity`
- `Field`
- `Identity`
- `SDKStore`
- `SDKRegistry`

### 1.2 DSL

- `Rule`
- `RuleRef`
- `Derivation`
- `Query`
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### 1.3 Schema compile helpers

- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### 1.4 Ingest / Provenance

- `IngestResult`
- `ValidationReport`

### 1.5 Errors and error codes

- Error classes: `SDKSchemaError`, `SDKStoreError`, `SDKRegistryError`, `EntityNotFoundError`, `FrozenSnapshotError`, `CardinalityError`, `EditorClosedError`
- Exported codes:
  - `INVALID_ROW_FORMAT`
  - `QUERY_MISSING_REF`
  - `QUERY_TYPE_MISMATCH`
  - `QUERY_ALIAS_CONFLICT`
  - `QUERY_UNBOUND_VAR`
  - `QUERY_INVALID_ROW_FORMAT`
  - `QUERY_NOT_IMPLEMENTED`

## 2. `SDKStore` Public Methods

- `from_schema_classes(..., ledger=None, ledger_path=None, default_row_format=None)`
- `batch(...)`
- `get(...)`
- `find(...)`
- `edit(...)`
- `ingest(...)`
- `validate_provenance(...)`
- `ref(...)`
- `set(...)`
- `add(...)`
- `retract(...)`
- `run(...)`
- `evaluate(...)`
- `evaluate_compiled(...)`
- `accept(...)`
- `accept_many(...)`
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

Key boundaries:
- `from_schema_classes(...)` / `schema_preflight_from_classes(...)` class-validation failures raise `SDKSchemaError` (`SDKStore(...)` constructor-path checks raise `SDKStoreError`).
- `run(...)` supports Rule/Query and rejects Derivation.
- `evaluate(...)` explicitly rejects `temporal_view`.
- Rule `row_format` precedence: call-site > `default_row_format` > `FACTPY_ROW_FORMAT` > `"dict"`.
- `FACTPY_ROW_FORMAT` is read once at `SDKStore` initialization and cached.
- `row_format="tuple"` still works but emits `DeprecationWarning`.
- Query defaults to `list[dict]`; it also supports `row_format="instance"` (only for single `Entity(var)` head).
- Invalid Query `row_format`, incompatible head shape for `instance`, or calling `run(...)` with Derivation raises `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.
- `accept(CandidateSet, ...)` accepts exactly one positional candidate; supported sugar keys are `approved_by`/`note`/`dry_run`/`identity_override` (also via `meta_overrides`).

## 3. `SDKRegistry` Public Methods

- `apply_schema_classes(...)`
- `apply_authoring_bundle(...)`
- `read_manifest(...)`
- `upsert_schema_ir(...)`
- `register_rule_spec(...)`
- `register_rule(...)`
- `register_derivation_spec(...)`
- `register_derivation(...)`
- `get_schema_entry(...)`
- `list_rule_ids(...)`
- `list_derivation_ids(...)`
- `list_rule_versions(...)`
- `list_derivation_versions(...)`
- `list_apply_run_ids(...)`
- `list_apply_runs(...)`
- `show_apply_run(...)`
- `get_latest_rule_spec(...)`
- `get_latest_derivation_spec(...)`
- `read_rule_spec(...)`
- `read_derivation_spec(...)`

Notes:
- `register_derivation(...)` is currently single-head-oriented.
- For multi-head publishing, expand into multiple single-head derivations first.

## 4. Common Facade Return Objects

- `EntitySnapshot`
  - attributes: `ref`, `entity_type`, `identity_available`, `identity`, `assertions`
  - method: `field(name)`
- `EntityEditor`
  - `preview()`, `commit(meta=...)`, `rollback()`
  - attributes: `ref`, `entity_type`
- `FieldEditor`
  - `set(...)`, `add(...)`, `retract(*, asrt_id=..., meta=...)` (keyword-only)

## 5. Batch Objects

- `SDKBatchTx`
  - `entity(...)`, `preview(...)`, `commit(...)`, `save(...)`
  - context manager `__exit__` does not auto-commit or auto-rollback
- `BatchPlan`
  - `ops`, `warnings`, `export(sdk)`, `to_json(sdk)`, `apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`, `to_json()`, `from_dict(...)`, `from_json(...)`, `apply(sdk, strict_schema=True)`

Additional note:
- Batch managed-handle retract method is `ManagedFieldHandle.retract(assertion_id, ...)` (parameter name is `assertion_id`; positional arg is also supported).

## 6. Query / Derivation Runtime Quick View

### 6.1 Query

- `sdk.run(Query(...)) -> list[dict]` (default) or `list[EntitySnapshot|None]` (`row_format="instance"` with single `Entity(var)` head)
- `on_missing` / `on_type_mismatch`: `error|skip|null`
- Query field head supports only schema `single` fields

### 6.2 Derivation

- `sdk.evaluate(Derivation(...), mode="python|engine") -> list[CandidateSet]`
- `head` shape determines candidate kind
- `head=[...]` is supported in evaluate (flattened output)
- `sdk.accept(...)` / `sdk.accept_many(...)` handle writes and idempotency
