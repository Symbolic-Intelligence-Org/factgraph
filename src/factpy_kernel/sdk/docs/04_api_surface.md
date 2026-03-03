# SDK API Surface 索引（当前实现）

本页对齐 `factpy_kernel/sdk/__init__.py` 的公开导出与核心类方法。

## 1. 顶层导出（`from factpy_kernel.sdk import ...`）

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

### 1.3 Schema 编译辅助

- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### 1.4 Ingest / Provenance

- `IngestResult`
- `ValidationReport`

### 1.5 错误与错误码

- 错误类：`SDKSchemaError`、`SDKStoreError`、`SDKRegistryError`、`EntityNotFoundError`、`FrozenSnapshotError`、`CardinalityError`、`EditorClosedError`
- 导出错误码：
  - `INVALID_ROW_FORMAT`
  - `QUERY_MISSING_REF`
  - `QUERY_TYPE_MISMATCH`
  - `QUERY_ALIAS_CONFLICT`
  - `QUERY_UNBOUND_VAR`
  - `QUERY_INVALID_ROW_FORMAT`
  - `QUERY_NOT_IMPLEMENTED`

## 2. `SDKStore` 公开方法

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

关键边界：
- `run(...)` 支持 Rule/Query，不支持 Derivation。
- `evaluate(...)` 显式拒绝 `temporal_view`。
- `run(rule)` 的 `row_format` 优先级：调用参数 > `default_row_format` > `FACTPY_ROW_FORMAT` > `"dict"`。
- Query 固定返回 `list[dict]`，不接受 `row_format`。

## 3. `SDKRegistry` 公开方法

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

说明：
- `register_derivation(...)` 当前按单 head 语义编译发布。
- 如需发布多 head，建议在调用方先拆成多个单 head derivation。

## 4. Facade 返回对象

- `EntitySnapshot`
  - 属性：`ref`、`entity_type`、`identity_available`、`identity`、`assertions`
  - 方法：`field(name)`
- `EntityEditor`
  - `preview()`、`commit(meta=...)`、`rollback()`
  - 属性：`ref`、`entity_type`
- `FieldEditor`
  - `set(...)`、`add(...)`、`retract(asrt_id=..., meta=...)`

## 5. Batch 相关对象

- `SDKBatchTx`
  - `entity(...)`、`preview(...)`、`commit(...)`、`save(...)`
- `BatchPlan`
  - `ops`、`warnings`、`export(sdk)`、`to_json(sdk)`、`apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`、`to_json()`、`from_dict(...)`、`from_json(...)`、`apply(sdk, strict_schema=True)`

## 6. Query / Derivation 运行速查

### 6.1 Query

- `sdk.run(Query(...)) -> list[dict]`
- `on_missing` / `on_type_mismatch`: `error|skip|null`
- Query field head 只支持 schema 的 `single` 字段

### 6.2 Derivation

- `sdk.evaluate(Derivation(...), mode="python|engine") -> list[CandidateSet]`
- `head` 形态决定 candidate kind
- `head=[...]` 支持 evaluate 展平输出
- `sdk.accept(...)` / `sdk.accept_many(...)` 负责写入与幂等
