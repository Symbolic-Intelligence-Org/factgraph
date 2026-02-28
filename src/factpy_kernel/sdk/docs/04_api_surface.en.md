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

- `from_schema_classes(..., ledger=None, ledger_path=None)`
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

Notes:
- `from_schema_classes(..., ledger_path="...")` is the recommended file-backed restore path.
- First creation writes `schema_digest`; later restores validate schema compatibility.

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

Notes (easy-to-misuse methods):
- `read_manifest()`: reads registry manifest index; if manifest file does not exist yet, returns default empty shape.
- `upsert_schema_ir(...)`: writes compiled `schema_ir` directly (bypasses `apply_schema_classes` path).
- `get_schema_entry()`: returns schema entry metadata (for example `path`), not the schema_ir payload itself.

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

## 6. `Derivation.materialize_as` Quick Guide (`fact` vs `record`)

| Mode | Write Target | Typical `head` Form | Typical Use Case | Key Constraint |
|---|---|---|---|---|
| `fact` | Business predicate assertion (for example `user:speaks(user, language)`) | `User.speaks(user=u, language=l)` (Field head) | Write derived results back to an existing business field | Target predicate must exist in schema (if `User.speaks` is not defined, you cannot write `user:speaks`) |
| `record` | Reified record (`Record:exists` + role predicates) | `Speaks(user=u, language=l)` (Entity head) | Need a relation node that can carry extra attributes/audit metadata | Explicit `id_policy` is recommended; some schema-aware paths can auto-derive it |

Boundary notes:
- `head=User(...)` is an Entity head, not a business predicate head; with `materialize_as="fact"` it usually enters the record-projection path.
- For business fact materialization, prefer a Field head (`SomeEntity.some_field(...)`) or explicit `target + head_vars`.
- `sdk.evaluate(...)` returns `list[CandidateSet]`; `sdk.accept(...)` takes one `CandidateSet` per call.

See also:
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.en.md` (Derivation DSL and head rules)
