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
- `accept_many(...)`
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

补充：
- `from_schema_classes(..., ledger_path="...")` 是当前推荐的 file-backed 恢复入口。
- 首次创建 ledger 文件时会写入 `schema_digest`；后续恢复会做一致性校验。

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
| 无 `head`（`target + head_vars`） | fact-only 路径（兼容） | fact candidates |

### 6.2 `CandidateSet` 与 accept

- `sdk.evaluate(...)` 返回 `list[CandidateSet]`，关键字段包括：
  - `candidate_id`（per-run 句柄）
  - `candidate_key`（跨 run 稳定键）
  - `candidate_kind`（`fact` / `entity`）
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
