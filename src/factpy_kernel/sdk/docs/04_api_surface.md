# SDK API Surface 索引（v1）

本页是 `from factpy_kernel.sdk import ...` 与核心类公开方法的速查索引。

## 1. 顶层导出（`factpy_kernel/sdk/__init__.py`）

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
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### 1.3 Schema 编译与预检

- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### 1.4 Ingest / Provenance

- `IngestResult`
- `ValidationReport`

### 1.5 错误类型

- `SDKSchemaError`
- `SDKStoreError`
- `SDKRegistryError`
- `EntityNotFoundError`
- `FrozenSnapshotError`
- `CardinalityError`
- `EditorClosedError`

## 2. `SDKStore` 公开方法（核心）

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

## 4. Facade 返回对象（常用）

- `EntitySnapshot`
  - `ref`
  - `entity_type`
  - `identity_available`
  - `identity`
  - `assertions`
  - `field(name)`
- `EntityEditor`
  - `preview()`
  - `commit(meta=...)`
  - `rollback()`
  - `ref`
  - `entity_type`
- `FieldEditor`
  - `set(...)`
  - `add(...)`
  - `retract(asrt_id=..., meta=...)`

## 5. Batch 相关对象（常用）

- `SDKBatchTx`
  - `entity(...)`
  - `preview(...)`
  - `commit(...)`
  - `save(...)`
- `BatchPlan`
  - `ops`
  - `warnings`
  - `export(sdk)`
  - `to_json(sdk)`
  - `apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`
  - `to_json()`
  - `from_dict(...)`
  - `from_json(...)`
  - `apply(sdk, strict_schema=True)`

## 6. `Derivation.materialize_as` 用法速查（`fact` vs `record`）

| 模式 | 写入目标 | `head` 常见写法 | 典型场景 | 关键约束 |
|---|---|---|---|---|
| `fact` | 业务谓词断言（例如 `user:speaks(user, language)`） | `User.speaks(user=u, language=l)`（Field head） | 将推导结果写回既有业务字段 | schema 必须有目标谓词（未定义 `User.speaks` 时不能写 `user:speaks`） |
| `record` | reified record（`Record:exists` + 角色谓词） | `Speaks(user=u, language=l)`（Entity head） | 需要关系节点可挂属性/追踪 | 建议显式 `id_policy`；部分 schema-aware 场景可自动推导 |

补充边界：
- `head=User(...)` 属于 Entity head，不是业务谓词 head；与 `materialize_as="fact"` 组合通常会走“record 投影”路径。
- 对业务 fact 物化，优先使用 Field head（`SomeEntity.some_field(...)`）或显式 `target + head_vars`。
- `sdk.evaluate(...)` 返回 `list[CandidateSet]`；`sdk.accept(...)` 一次接收一个 `CandidateSet`。

延伸阅读：
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`（Derivation DSL 与 head 规则）
