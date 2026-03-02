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
- `Query`
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
- `INVALID_ROW_FORMAT`
- `QUERY_MISSING_REF`
- `QUERY_TYPE_MISMATCH`
- `QUERY_ALIAS_CONFLICT`
- `QUERY_UNBOUND_VAR`
- `QUERY_INVALID_ROW_FORMAT`
- `QUERY_NOT_IMPLEMENTED`

## 2. `SDKStore` 公开方法（核心）

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

补充：
- `from_schema_classes(..., ledger_path="...")` 是当前推荐的 file-backed 恢复入口。
- 首次创建 ledger 文件时会写入 `schema_digest`；后续恢复会做一致性校验。
- `default_row_format` 仅影响 `sdk.run(rule, ...)` 的默认返回形态（`tuple`/`dict`）；默认是 `dict`。
- 解析后的 `row_format` 若为 `tuple` 会触发 `DeprecationWarning`（兼容期保留）。
- 环境变量 `FACTPY_ROW_FORMAT` 会在 `SDKStore` 初始化时读取一次并缓存。

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

补充（易误用方法）：
- `read_manifest()`：读取 registry manifest 索引；manifest 不存在时返回默认空结构。
- `upsert_schema_ir(...)`：直接写入已编译 `schema_ir`（跳过 `apply_schema_classes`）。
- `get_schema_entry()`：只返回 schema entry 元数据（如 `path`），不是 schema_ir 内容本体。
- Derivation 多 head（`head=[...]`）目前仅 `sdk.evaluate(...)` 运行时路径支持；`register_derivation(...)` 仍是单 head 注册语义。

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

## 6. Derivation 速查（v2）

### 6.1 `head` 决定默认路径

| `head` 形态 | 默认行为 | evaluate 输出 |
|---|---|---|
| `EntityType(...)` | entity 路径 | 1 个 entity candidate + 依赖 fact candidates |
| `EntityType.field(...)` | fact 路径 | fact candidates |
| `head=[H1, H2, ...]` | 按 head 顺序展开多个单 head 计划 | `list[CandidateSet]`（按 head 顺序展平） |
| 无 `head`（`target + head_vars`） | fact-only 路径（兼容） | fact candidates |

### 6.2 `CandidateSet` 与 accept

- `sdk.evaluate(...)` 返回 `list[CandidateSet]`，关键字段包括：
  - `candidate_id`（per-run 句柄）
  - `candidate_key`（跨 run 稳定键）
  - `candidate_kind`（`fact` / `entity`）
- 多 head `evaluate` 下，所有候选共享同一个 `run_id`。
- `sdk.accept(...)` 一次接收一个候选；有依赖图时优先使用 `sdk.accept_many(..., mode=\"atomic\")`。

延伸阅读：
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`（Derivation DSL 与 head 规则）

## 7. 常用调用模板（v2）

### 7.1 fact derivation

```python
with vars("p", "c") as (p, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=p, country_copy=c),
        where=[Pred("person:country", p, c)],
    )

cands = sdk.evaluate(drv, mode="python")
fact = next(c for c in cands if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 7.2 entity derivation（有依赖关系）

```python
with vars("u", "l") as (u, l):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        head=Speaks(user=u, language=l),
        where=[Pred("person:country", u, "de"), Pred("user:lang_pref", u, l)],
    )

cands = sdk.evaluate(drv, mode="python")
rows = sdk.accept_many(cands, mode="atomic")
```

### 7.3 identity 不完整时

```python
entity = next(c for c in cands if c.candidate_kind == "entity")
sdk.accept(entity, identity_override={"source_id": "u-001"})
```

不再使用 `materialize_as` / `id_policy`。

## 8. `sdk.run(...)` 分发与 `row_format`（v2）

### 8.1 分发规则

- `run(rule, ...)`：Rule 查询路径（当前已实现）
- `run(derivation, ...)`：直接报错，提示改用 `sdk.evaluate(...)`
- `run(query, ...)`：Query 运行路径已实现（lowering + where_eval + 批量 hydrate + contract apply）

### 8.2 `row_format` 适用范围

- 仅 Rule 路径支持 `row_format`
- Query 路径固定返回 `list[dict]`，传 `row_format` 会报 `QUERY_INVALID_ROW_FORMAT`

### 8.3 `row_format` 三层优先级

`调用参数 > SDKStore.default_row_format > FACTPY_ROW_FORMAT > "dict"`

合法值仅：`"tuple"` / `"dict"`。  
解析结果为 `"tuple"` 时会发出 `DeprecationWarning`，提示后续版本移除。  
非法值报 `SDKStoreError(code="INVALID_ROW_FORMAT")`。

## 9. `Query` DSL（Step 5）

### 9.1 构造形态（当前已实现）

- `Query(head=Entity(var), where=[...])`
- `Query(head=[Entity(var1), Entity(var2)], where=[...])`
- `Query(head=Entity.field(...), where=[...])`

### 9.2 静态校验（当前已实现）

- `head` 非法形态在构造期抛 `SDKDSLError`
- `head -> return_contract` 推导在构造期完成
- alias 冲突抛 `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`
- where 未绑定变量抛 `SDKDSLError(code="QUERY_UNBOUND_VAR")`
- where 校验使用 `initial_bound_vars`（由 `head` 变量集传入）

### 9.3 运行态状态（当前行为）

- Query lowering 已实现为 `QueryPlan(query_id, rule_ast, return_contract, ...)`
- `query_id` 规则：`__query__:<16hex>`，由 head/where/temporal_view/return_mode/on_missing/on_type_mismatch/schema_digest 的 canonical payload 生成
- field head 在 lowering 阶段会做 schema 校验：拒绝 `multi` 或 `dims` 字段投影
- Query 运行态执行链路：`where_eval(bindings) -> 批量 hydrate -> 合约应用`
- `on_missing` / `on_type_mismatch` 支持：`error | skip | null`
- `on_missing="error"` 报 `QUERY_MISSING_REF`；`on_type_mismatch="error"` 报 `QUERY_TYPE_MISMATCH`
