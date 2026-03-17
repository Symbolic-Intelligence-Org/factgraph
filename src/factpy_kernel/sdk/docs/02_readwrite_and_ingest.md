# SDK 读写与 Ingest 参考（当前实现）

范围：`store.py`、`facade.py`、`batch.py`、`ingest.py`

## 1. 写入口选择

| 场景 | 推荐 API | 说明 |
| --- | --- | --- |
| 构造对象图、预览计划、导出回放 | `sdk.batch()` | 支持 `preview()`、`commit()`、`WireBatchPlan` |
| 已知完整 identity，编辑已存在实体 | `sdk.edit(...)` | 语义最明确，自动 commit/rollback |
| 外部批量导入（item 级诊断） | `sdk.ingest(...)` | 适合脚本导入，支持 collect-and-stop |
| 最低层直接写断言 | `sdk.ref/set/add/retract` | 灵活但抽象最低 |

## 2. SDKStore 构建

```python
sdk = SDKStore.from_schema_classes([User, Country, LivesIn])
```

文件持久化：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, LivesIn],
    ledger_path="./data/ledger.db",
)
```

如需让 explain artifact 也能跨后续 `SDKStore` 实例读回，可同时指定：

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, LivesIn],
    ledger_path="./data/ledger.db",
    artifact_store_root="./data/artifacts",
)
```

稳定合约：
- `classes` 必须是非空 `list[Entity 子类]`；`from_schema_classes(...)` / `schema_preflight_from_classes(...)` 路径抛 `SDKSchemaError`，`SDKStore(...)` 构造器路径抛 `SDKStoreError`。
- `ledger` 与 `ledger_path` 互斥。
- `ledger_path` 在打开/创建 ledger 时即记录 `schema_digest`，后续恢复会做 digest 校验。
- `artifact_store_root` 为可选 `str`；提供后会启用 sidecar-backed explain artifact readback，省略则保持默认的进程内 explain registry。
- `default_row_format` 仅影响 `sdk.run(rule, ...)`；合法值为 `"tuple"` / `"dict"`（默认 `"dict"`）。
- `FACTPY_ROW_FORMAT` 在 `SDKStore` 初始化时读取并缓存；不是每次 `run()` 动态读取。
- 解析为 `"tuple"` 时会触发 `DeprecationWarning`，建议统一改为 `"dict"`。

## 3. 低层写入（`ref/set/add/retract`）

### 3.1 `sdk.ref(...)`

- 按 identity 生成 canonical `idref_v1`。
- 支持 `Identity.default` 与 `default_factory="uuid4"`。
- identity 缺失或有未知字段会抛 `SDKStoreError`。

### 3.2 `sdk.set(...)` / `sdk.add(...)`

```python
sdk.set(User.age, user_ref, 31, meta={"source": "hr"})
sdk.add(User.name, user_ref, "Alicia", meta={"source": "hr"})
```

稳定合约：
- 值类型按 schema `type_domain` 校验。
- 若 `e_ref` 对应的 identity 值已被当前 `SDKStore` 记录，写入前会补写对应 identity predicate；任意外部 canonical `idref_v1` 不保证可自动物化。
- 低层 `set/add` 不做强 cardinality 约束；cardinality 约束主要由 batch/edit/ingest facade 提供。

### 3.3 `sdk.retract(...)`

```python
sdk.retract(asrt_id, meta={"trace_id": "fix-1"})
```

- append-only revoke，不删除原 claim。
- 返回 revoker assertion id；重复撤销已撤销断言时返回已有 revoker id，未知断言直接报错。

## 4. 批处理（`sdk.batch()`）

### 4.1 常见流程

```python
with sdk.batch(meta={"trace_id": "seed"}) as tx:
    alice = tx.entity(User, user_id="u1", locale="zh")
    alice.name.add("Alice")
    alice.age.set(30)

    plan = tx.preview()
    result = tx.commit()
```

补充语义：
- batch meta 合并优先级：`commit_meta > field_op_meta > entity_meta > batch_meta`。
- `with sdk.batch() as tx:` 的 context manager 不会自动 commit/rollback；需要显式调用 `commit()`。

### 4.2 cardinality 与 identity 约束

- `single` 字段只能 `.set(...)`（`sdk.batch()` 路径用错抛 `SDKStoreError`；`sdk.edit()` 路径用错抛 `CardinalityError`）。
- `multi` 字段只能 `.add(...)`（`sdk.batch()` 路径用错抛 `SDKStoreError`；`sdk.edit()` 路径用错抛 `CardinalityError`）。
- batch 托管句柄撤销按断言 ID：`.retract(assertion_id=...)`（也支持位置参数）；`sdk.edit()` 的 `FieldEditor` 形态是 `.retract(asrt_id=...)`。
- identity 字段暴露只读 guard，`set/add/retract` 会报错。
- identity 不完整时，写操作会立即报 `SDKStoreError`，需先 `bind(...)` 补齐。

### 4.3 Wire plan

- `plan.export(sdk) -> WireBatchPlan`
- `WireBatchPlan.to_json()/from_json(...)`
- `WireBatchPlan.apply(sdk, strict_schema=True)`

协议要点（`sdk_batch_plan_v1`）：
- wire op 不再携带 `dims/fact_key`。
- `cardinality` 使用 `single|multi`。
- wire 导出（`to_json`/`export`）不接受 raw `idref_v1` 字符串值；实体引用应使用同 tx 句柄关系。

## 5. 读取与编辑（`get/find/edit`）

### 5.1 `sdk.get(...)`

```python
snap = sdk.get(User, user_id="u1", locale="zh")
```

- 只接受 identity kwargs。
- 返回 `EntitySnapshot | None`。
- `get` 返回的快照 `identity_available=True`。

### 5.2 `sdk.find(...)`

```python
rows = sdk.find(User, age=30, limit=20)
```

稳定合约：
- `limit` 必须是非负整数。
- 过滤字段必须属于该实体的 identity 或普通字段。
- identity 过滤一旦使用，必须提供该实体全部 identity 字段。
- 不支持 `temporal_view` 参数。

匹配语义：
- `single`：相等匹配。
- `multi`：包含匹配（`expected in tuple_value`）。
- 实体引用字段可传 `ref` 或 `EntitySnapshot`（自动取 `.ref`）。

### 5.3 `sdk.edit(...)`

```python
with sdk.edit(User, user_id="u1", locale="zh") as user:
    user.age.set(31)
    user.name.add("Alicia")
```

稳定合约：
- 目标不存在抛 `EntityNotFoundError`。
- 正常退出自动 commit；异常退出自动 rollback。
- editor 关闭后复用抛 `EditorClosedError`。

## 6. `EntitySnapshot` 与断言视图

### 6.1 快照值

- `single` 字段：标量或 `None`
- `multi` 字段：`tuple[...]`
- 快照只读，赋值抛 `FrozenSnapshotError`
- `single` 仅是读取侧单值视图；写入不会自动清理旧断言。

### 6.2 `snapshot.assertions.<field>`

- `.active`：当前未撤销断言
- `.history`：完整历史（含已撤销）
- `.at(t)`：active 集合上按业务时间过滤  
  `valid_from <= t` 且（`valid_to` 缺失或 `valid_to > t`）
- `.version(v)`：active 集合上按 `version == v` 过滤

边界：
- 缺失 `valid_from` 的断言不会命中 `.at(t)`。
- 缺失 `version` 的断言不会命中 `.version(v)`。
- `.at(t)` 会校验 ISO 8601（输入和断言 meta 都校验）。
- `.version(v)` 仅接受 `str|int`（`bool` 非法）。
- `snapshot.assertions` 仅覆盖 `Field` 字段，不覆盖 `Identity` 字段。

## 7. Ingest（`sdk.ingest(...)`）

### 7.1 item 形态（dict）

```python
{"kind": "set", "field": User.age, "e_ref": user_ref, "value": 31, "meta": {...}}
{"kind": "add", "field": User.name, "e_ref": user_ref, "value": "Alias", "meta": {...}}
{"kind": "retract", "asrt_id": "...", "meta": {...}}
```

### 7.2 诊断语义

- SDK 先预检全量 item，诊断路径使用 `items[i].*`。
- 任一 `severity="error"` => 整批不写（collect-and-stop）。
- warning 不阻塞写入。

### 7.3 meta 语义

- 顶层 `meta` 与 item `meta` 合并，item 同名键覆盖顶层。
- hard reserved：`ingested_at` / `ingest_key` / `revoked_asrt_id`（用户不可写）。
- 去重相关（`ingest_key`）物料包含：
  `claim + source + source_loc + trace_id + valid_from + valid_to + version`

### 7.4 返回结构

`IngestResult`：
- `written_assertion_ids`
- `skipped_count`
- `duplicate_count`
- `warnings`
- `diagnostics`
- `diagnostics_contract_version`

## 8. Provenance 校验（`sdk.validate_provenance`）

```python
report = sdk.validate_provenance(obj, standard="derivation_v1")
```

输入支持：
- `CandidateSet`
- `dict`（当前按扁平键读取）

`derivation_v1` 必填键：
- `derived_rule_id`
- `derived_rule_version`
- `run_id`
- `support_kind`
- `support_digest`（`sha256:<hex>`）

返回：
- `ValidationReport.ok`
- `ValidationReport.warnings`
- `ValidationReport.errors`
- `ValidationReport.diagnostics_contract_version`
