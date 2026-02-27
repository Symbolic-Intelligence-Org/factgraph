# SDK API Surface Index (v1)

Quick index of `from factpy_kernel.sdk import ...` and major public APIs.

## 1. Top-Level Exports

### Schema / Store / Registry
- `Entity`
- `Field`
- `Identity`
- `SDKStore`
- `SDKRegistry`

### DSL
- `Rule`
- `RuleRef`
- `Derivation`
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### Schema Helpers
- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### Ingest / Provenance
- `IngestResult`
- `ValidationReport`

### Errors
- `SDKSchemaError`
- `SDKStoreError`
- `SDKRegistryError`
- `EntityNotFoundError`
- `FrozenSnapshotError`
- `CardinalityError`
- `EditorClosedError`

## 2. `SDKStore` Main Methods

- `from_schema_classes(...)`
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
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

## 3. `SDKRegistry` Main Methods

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

## 4. Common Facade Return Objects

- `EntitySnapshot`
  - `ref`, `entity_type`, `identity_available`, `identity`, `assertions`, `field(name)`
- `EntityEditor`
  - `preview()`, `commit(meta=...)`, `rollback()`, `ref`, `entity_type`
- `FieldEditor`
  - `set(...)`, `add(...)`, `retract(asrt_id=..., meta=...)`

## 5. Batch Objects

- `SDKBatchTx`
  - `entity(...)`, `preview(...)`, `commit(...)`, `save(...)`
- `BatchPlan`
  - `ops`, `warnings`, `export(sdk)`, `to_json(sdk)`, `apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`, `to_json()`, `from_dict(...)`, `from_json(...)`, `apply(sdk, strict_schema=True)`

