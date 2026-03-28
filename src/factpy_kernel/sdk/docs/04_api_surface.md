# SDK API Surface 索引（当前实现）

本页对齐 `factpy_kernel/sdk/__init__.py` 的公开导出与核心类方法。

## 1. 顶层导出（`from factpy_kernel.sdk import ...`）

### 1.1 Schema / Store / Registry

- `Entity`
- `Field`
- `Identity`
- `SDKStore`
- `SDKRegistry`

补充：
- plain `Entity` 实例实现了调试友好的 `__repr__()`；输出按声明顺序展示 identity 与 field 值，未赋值 `Field` 显示为 `None`。

### 1.2 DSL

- `Body`
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

- `from_schema_classes(..., ledger=None, ledger_path=None, artifact_store_root=None, default_row_format=None)`
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
- `from_schema_classes(...)` / `schema_preflight_from_classes(...)` 的 `classes` 校验错误抛 `SDKSchemaError`（`SDKStore(...)` 构造器路径对应为 `SDKStoreError`）。
- `SDKStore.__init__(..., artifact_store_root=None)` 与 `from_schema_classes(..., artifact_store_root=None)` 都支持 sidecar-backed explain artifact readback；若已显式传入 `store=...`，构造器上的 `artifact_store_root` 会被忽略。
- `run(...)` 支持 Rule/Query，不支持 Derivation。
- `run(rule, view=...)` 支持具名/内联视图；Query 路径不支持 `view` 与 `return_display_meta`。
- `evaluate(...)` 显式拒绝 `view` 与 `temporal_view`。
- `evaluate(..., engine_options={...})` 支持 engine run-time 配置；该参数是 call-time only，不进入 `Derivation` / authoring payload。
- `evaluate(mode="native", engine_options={...})` 会显式报错；engine_options 的 key 校验与默认值由目标 adapter 负责。
- `run(rule)` 的 `row_format` 优先级：调用参数 > `default_row_format` > `FACTPY_ROW_FORMAT` > `"dict"`。
- `FACTPY_ROW_FORMAT` 在 `SDKStore` 初始化时读取并缓存。
- `row_format="tuple"` 仍可用但会触发 `DeprecationWarning`。
- Query 默认返回 `list[dict]`；支持 `row_format="instance"`（仅 head 为单个 `Entity(var)`）。
- Query 使用非法 `row_format`、instance 模式 head 不匹配、或对 Derivation 调用 `run(...)`，都会抛 `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`。
- `accept(CandidateSet, ...)` 只接受一个位置参数；支持 `approved_by`/`note`/`dry_run`/`identity_override`（也可通过 `meta_overrides` 传）。

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
  - `set(...)`、`add(...)`、`retract(*, asrt_id=..., meta=...)`（关键字参数）

## 5. Batch 相关对象

- `SDKBatchTx`
  - `entity(...)`、`preview(...)`、`commit(...)`、`save(...)`
  - context manager `__exit__` 不自动 commit/rollback
- `BatchPlan`
  - `ops`、`warnings`、`export(sdk)`、`to_json(sdk)`、`apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`、`to_json()`、`from_dict(...)`、`from_json(...)`、`apply(sdk, strict_schema=True)`

补充：
- batch 托管句柄的撤销方法是 `ManagedFieldHandle.retract(assertion_id, ...)`（参数名为 `assertion_id`，也支持位置参数）。

## 6. Query / Derivation 运行速查

### 6.1 Query

- `sdk.run(Query(...)) -> list[dict]`（默认）或 `list[EntitySnapshot|None]`（`row_format="instance"` 且 head 仅单个 `Entity(var)`）
- `on_missing` / `on_type_mismatch`: `error|skip|null`
- Query field head 只支持 schema 的 `single` 字段

### 6.2 Derivation

- `sdk.evaluate(Derivation(...), mode="native|souffle|problog|pyreason") -> list[CandidateSet]`
- 旧名 `python|engine` 传入会明确报错并提示新名称
- `head` 形态决定 candidate kind
- `head=[...]` 支持 evaluate 展平输出
- `CandidateSet.confidence`：`problog` 为概率 `float`，`pyreason` 为 lower bound `float`，`native/souffle` 为 `None`
- `sdk.accept(...)` / `sdk.accept_many(...)` 负责写入与幂等
- `engine_ext`：共享的 definition-time 引擎语义 carrier；可挂在 `Rule.engine_ext` 或 `Derivation.engine_ext`（如 `PyReasonRuleExt(timestep_delay=1)`），必须继承 `EngineExtBase`
- `engine_options`：`sdk.evaluate(..., engine_options={"timesteps": 5})` 传递运行时配置，call-time only，不进入 Derivation 或 Ledger
- `mode="native"` 拒绝非空 `engine_options`
- 语义 annotation：PyReason 结果自动生成 `pyreason/semantic/*`，ProbLog 结果生成 `problog/semantic/probability`；accept 后需显式调用 `persist_pyreason_annotations()` 或 `persist_problog_annotations()` 完成持久化
