# SDK 读写与 Ingest 参考（v1）

范围：`src/factpy_kernel/sdk/store.py`、`facade.py`、`batch.py`、`ingest.py`

## 1. 选哪个写入入口

| 场景 | 推荐 API | 说明 |
| --- | --- | --- |
| 构造对象图、预览计划、序列化回放 | `sdk.batch()` | 支持 `preview()`、wire plan |
| 已知完整 identity，改一个已存在实体 | `sdk.edit(...)` | 语义最明确 |
| 外部脚本批量写入，或只有 `ref + asrt_id` | `sdk.ingest(...)` | item 级诊断，适配导入流程 |
| 想直接落 ledger | `sdk.ref/set/add/retract` | 低层 API，灵活但约束少 |

## 2. SDKStore 构建与基础属性

```python
sdk = SDKStore.from_schema_classes([User, Country, LivesIn])
```

- `sdk.store`
- `sdk.ledger`
- `sdk.schema_ir`

如需文件持久化，推荐直接使用：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, LivesIn],
    ledger_path="./data/ledger.db",
)
```

说明：
- `ledger_path` 会恢复同一个 Ledger 文件中的历史数据。
- 首次创建时会写入 `schema_digest`；后续恢复会做 digest 校验。
- 若你需要自己构造 `Ledger(...)`，仍可走 `ledger=...` 高级入口；但不要和 `ledger_path` 同时传。

## 3. 低层写入：`ref / set / add / retract`

### 3.1 `sdk.ref(...)`

- 按 identity 生成 `idref_v1`。
- 支持 `Identity.default` 与 `default_factory="uuid4"`。
- 传入未知 identity 字段或缺少必填 identity 会抛 `SDKStoreError`。

### 3.2 `sdk.set(...)` / `sdk.add(...)`

```python
sdk.set(User.country, user_ref, "de")
sdk.add(User.aliases, user_ref, "Alice")
```

- 支持 `dims`（dict 或 list/tuple）与 `meta`。
- 类型、dims 形状由 schema 校验（通过 `_rest_terms_for_field` 路径）。
- 注意：这两个低层方法本身不做字段 cardinality 强约束。

### 3.3 `sdk.retract(...)`

```python
sdk.retract(asrt_id, meta={"trace_id": "fix-1"})
```

- append-only revoke，不删除原 claim。
- 返回 revoker assertion id（或 `None`）。

## 4. 批处理：`sdk.batch()`

### 4.1 常用流程

```python
with sdk.batch(meta={"trace_id": "seed"}) as tx:
    alice = tx.entity(User, source_system="APP", source_id="u1")
    de = tx.entity(Country, source_system="ISO3166", source_id="DE")

    alice.country.set(de)       # handle 依赖
    alice.name.add("Alice")

    plan = tx.preview()
    result = tx.commit()
```

### 4.2 cardinality 约束（batch handle）

- functional 字段：`.set(...)`
- multi 字段：`.add(...)`
- `.retract(assertion_id=...)` 按断言撤销
- 错误调用抛 `SDKStoreError`

### 4.3 preview / wire plan

- `plan.ops`
- `plan.export(sdk) -> WireBatchPlan`
- `plan.to_json(sdk)`
- `plan.apply(sdk)`
- `WireBatchPlan.apply(sdk, strict_schema=True)`

说明：
- 对 `is_record=True` 且发生写入的 handle，会自动补 `record_exists` 写入 op。
- wire plan 导出不接受直接写 raw `idref_v1` 作为 value；实体关联值应通过 handle 建依赖。

## 5. 读取与编辑：`get / find / edit`

### 5.1 `sdk.get(...)`

```python
snap = sdk.get(User, source_system="APP", source_id="u1")
```

- 仅接受 identity kwargs。
- 不存在返回 `None`。
- 返回快照时 `identity_available=True`，且 `identity` 可直接用于 `sdk.edit(...)`。

### 5.2 `sdk.find(...)`

```python
rows = sdk.find(User, country="de", temporal_view="current", limit=10)
```

- `temporal_view`: `"record"` 或 `"current"`。
- field 过滤是 AND 语义。
- functional 字段按“相等”匹配。
- multi/temporal 字段按“包含”匹配（expected 在 tuple 中）。
- entity-ref 字段过滤可传 `ref` 或 `EntitySnapshot`（自动取 `.ref`）。

当前限制：
- dims 字段过滤暂不支持（抛 `SDKSchemaError`）。
- 若传 identity 过滤，必须提供该实体完整 identity。

identity 回填行为：
- `find` 无 identity filter 路径：`identity_available=False`。
- `find` 有完整 identity filter 路径：`identity_available=True`。

### 5.3 `sdk.edit(...)`

```python
with sdk.edit(User, source_system="APP", source_id="u1") as user:
    user.country.set("de")
    user.name.add("Alicia")
```

- 目标不存在抛 `EntityNotFoundError`。
- context manager：无异常自动 commit；有异常自动 rollback（不吞异常）。
- `commit()`/`rollback()` 后 editor 关闭，再操作抛 `EditorClosedError`。

## 6. `EntitySnapshot` 与断言视图

### 6.1 基础属性

- `snapshot.ref`
- `snapshot.entity_type`
- `snapshot.identity_available`
- `snapshot.identity`
- `snapshot.<field>`
- `snapshot.assertions.<field>`

快照只读，赋值抛 `FrozenSnapshotError`。

### 6.2 当前值形态

- functional：单值或 `None`
- multi/temporal：`tuple[...]`
- dimmed 字段：`tuple[DimensionedValue, ...]`

### 6.3 断言级字段

- `snapshot.assertions.<field>.active`
- `snapshot.assertions.<field>.history`
- `snapshot.assertions.<field>.chosen`
  - 仅无 dims 的 functional 字段可用，否则抛 `CardinalityError`

## 7. Ingest：`sdk.ingest(...)`

### 7.1 当前支持 item 形态（dict）

```python
{"kind": "set", "field": User.country, "e_ref": user_ref, "value": "de", "dims": {...}, "meta": {...}}
{"kind": "add", "field": User.name, "e_ref": user_ref, "value": "Alicia", "meta": {...}}
{"kind": "retract", "asrt_id": "....", "meta": {...}}
```

### 7.2 校验与写入语义

- SDK 先做整批预检，收集 `items[i].*` 诊断。
- 若存在任一 `severity="error"`，整批不写（collect-and-stop）。
- warning 不阻塞写入。

### 7.3 meta 规则

- 顶层 `meta` 与 item `meta` 合并（item 覆盖顶层）。
- hard reserved keys：`ingested_at`、`ingest_key`、`revoked_asrt_id`。
- 顶层或 item `meta` 命中 hard reserved key 会报错（顶层直接抛，item 进入 diagnostics error）。
- 默认 `allow_sensitive_meta=False` 时，语义敏感键（如 `derived_rule_id`、`run_id`）给 warning。

### 7.4 `IngestResult`

- `written_assertion_ids`
- `skipped_count`
- `duplicate_count`
- `warnings`
- `diagnostics`
- `diagnostics_contract_version`

## 8. Provenance 验证：`sdk.validate_provenance(...)`

```python
report = sdk.validate_provenance(obj, standard="derivation_v1")
```

支持输入：
- `CandidateSet`
- `dict`（当前按扁平键读取）

必填键（`derivation_v1`）：
- `derived_rule_id`
- `derived_rule_version`
- `run_id`
- `support_kind`
- `support_digest`（`sha256:<hex>`）

可选键：
- `schema_digest`
- `policy_digest`
  - 格式异常给 warning，不直接报 error。

返回：
- `ValidationReport.ok`
- `ValidationReport.warnings`
- `ValidationReport.errors`
- `ValidationReport.diagnostics_contract_version`
