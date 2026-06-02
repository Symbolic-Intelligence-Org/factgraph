# Fields 批量写法:iterable value(未来工作)

- Status: working / **current mode locked**(scalar-value only)/ **future direction open**(iterable batch surface 未定)
- Authority: candidate design / non-authoritative reference;现状描述属实,未来方向属设计空间
- First draft: 2026-06-02
- Last updated: 2026-06-02
- Scope: `fg.fields.set / add / retract` 的 value 形参契约;multi-cardinality field 上的批量写入便利写法;与 `fg.batch` / `EntityEditor` 的边界
- Parent: 与 [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md) 同级;均属 SDK 用户面 ergonomic 设计空间
- Design intent: 把"`fg.fields.add(User.tags, alice, ['reviewer', 'admin'])` 当前会失败"这件事从用户面文档(`docs/quickstart/three_layer_api.md`)抽出来,作为未来工作记录;若未来加 iterable-value batch 写法,此 doc 是起点

---

## §1 当前模式:scalar-value only

`fg.fields.set / add / retract` 当前**只接受单个标量 value**,不接受 iterable / list / tuple / set。这点与 field 的 cardinality 无关 —— single-cardinality 和 multi-cardinality field 上的行为一致。

具体调用形态:

```python
# 合法
fg.fields.set(User.name, alice, "Alice")              # single field, scalar
fg.fields.add(User.tags, alice, "engineer")           # multi field, scalar element
fg.fields.retract(User.tags, alice, "engineer")       # multi field, scalar element

# 当前全部失败:SDKStoreError("string field expects str")
fg.fields.set(User.tags, alice, ["a", "b"])
fg.fields.add(User.tags, alice, ["a", "b"])
fg.fields.retract(User.tags, alice, ["a", "b"])

# 单元素 list 也失败
fg.fields.add(User.tags, alice, ["solo"])
```

错误是统一的 `SDKStoreError("<type> field expects <type>")`,来自 SDK 边界的 coerce 层。

## §2 现状的来源

两个组合约束。

### §2.1 `_coerce_sdk_value_to_tag` 的严格 isinstance 检查

每个标量 tag(`string` / `int` / `bool` / `bytes` / `time` / `uuid` / `float64` / `entity_ref`)在 `src/factgraph/sdk/store.py:3216-3262` 都做严格类型校验,任何非该类型的 value(包括包了一层的 list)立即 raise。

### §2.2 Multi-cardinality field 的 type_domain 是**元素** tag

`tags: list[str] = Field()` 在 schema 解析(`src/factgraph/sdk/schema.py:518`)产生:

```python
_AnnotationPlan(type_domain="string", cardinality="multi", ...)
```

注意 `type_domain="string"`,**不是** `"list[string]"`。这意味着 coerce 层看到的 tag 永远是元素类型,所以一个 multi field 的 add 流经的 coerce 仍然是 `_coerce_sdk_value_to_tag("string", value)`,list 会被拒绝。

这是一个一致性设计 —— ledger 的 `claim_args` 表本身按元素粒度展开,SDK 上层不做 list-aggregate 抽象;但从用户视角看,"我有一个 list 想批量写入"就需要多次调用。

## §3 用户当下的 workaround

### §3.1 多次调用

```python
for tag in ["engineer", "reviewer", "admin"]:
    fg.fields.add(User.tags, alice, tag)
```

每次调用是一个独立的 application-layer write,产生一个独立的 `asrt_id`,可独立 retract。

### §3.2 在 `fg.batch(...)` context 内聚合

```python
with fg.batch(meta={"trace_id": "import-001"}) as batch:
    for tag in ["engineer", "reviewer", "admin"]:
        batch.fields.add(User.tags, alice, tag)
```

batch context 把多次调用聚合到一个 transaction(同一 head_tx_id),失败回滚。这是当前**唯一**的原子批量路径。

### §3.3 `EntityEditor` 内多次 add(单 entity 多 field 的场景)

```python
with fg.entities.edit(User, user_id="u-1") as user:
    user.field("name").set("Alice")
    user.field("tags").add("engineer")
    user.field("tags").add("reviewer")
```

EntityEditor 也提供 transaction 边界,但同样不接受 list value。

## §4 未来设计空间(开放问题,无结论)

### §4.1 期望的 API 形态

如果未来支持 iterable-value batch,最直接的 surface 扩展是:

```python
fg.fields.set(field, e_ref, [v1, v2, v3])       # multi field 上的批量替换
fg.fields.add(field, e_ref, [v1, v2, v3])       # multi field 上的批量追加
fg.fields.retract(field, e_ref, [v1, v2, v3])   # multi field 上的批量撤销
```

也可能用独立方法名(`set_many` / `add_many` / `retract_many`)来避免与单值版本混淆。

### §4.2 待定语义

| Op | 单 value 当前语义 | iterable 模式下的待定语义 |
|---|---|---|
| `set` | 追加一个新 active claim(single field 上 snapshot 投影取最新) | 替换为该 list(撤销所有旧 active + 写入所有新)? 还是逐个 set? |
| `add` | 追加一个新 active claim(multi field 上) | 逐个 add(每个元素一个 asrt_id);整个调用原子? |
| `retract` | 撤销唯一匹配 `(field, e_ref, value)` 的 active claim | 逐个匹配并撤销;fail-fast 还是 best-effort(类似 `fg.fields.delete`)? |

### §4.3 返回值形态

单值版本目前返回单个 `str`(`asrt_id`)。iterable 模式下:

- 返回 `list[str]`(批量 asrt_id)?
- 返回 `list[str | None]`(retract 的 None 表示未匹配)?
- 与单值版本同签名 → 调用方需根据 value 类型分流(违反 Python 一般做法)

### §4.4 原子性

iterable batch 写入应当是单一 transaction(同一 `head_tx_id`)还是 N 个独立 transaction?当前 `fg.batch(...)` 提供原子聚合,iterable-value 是否冗余取决于是否要替代 batch 路径。

### §4.5 与 single-cardinality 的关系

`fg.fields.set(User.name, alice, ["A", "B"])` —— single field 上传 list 是否合法?

- **方案 a**:拒绝 —— iterable 模式只对 multi field 开启
- **方案 b**:接受 —— 视作"按顺序覆盖" 但 single field 上"按顺序覆盖"等同于只写入最后一个,语义模糊
- **方案 c**:接受为 type error —— single field 的 type_domain 是元素 tag,coerce 层维持现状

### §4.6 与 `fg.batch(...)` 的关系

`fg.batch` 已经覆盖了"多个独立 write 一个 transaction"的需求。iterable-value 的增量价值是:

- 调用更短(一行 vs 一个 with-block + 循环)
- 但增加了 SDK surface 复杂度,且 op 语义不直观(尤其 set/retract 的 list 行为待定)

如果未来 ergonomic 方向是 OpenAI-style top-level client(参见 [feedback memory](../../../../../.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_sdk_ergonomics_redesign_target.md)),iterable-value 可能不再是 top priority —— context-managed batch 更符合 SDK 一般风格。

## §5 当前位置的边界

| 属于本 design-point | 不属于 |
|---|---|
| `fg.fields.*` value 形参的 iterable 接受性契约 | `fg.batch(...)` 现状(已稳定,有独立设计) |
| Multi-cardinality field 的批量写入便利写法未来空间 | Multi-cardinality field 本身的语义(`add` vs `set` 在 multi 上的差异) |
| iterable 模式下三个 op(set/add/retract)的语义待定项 | snapshot 投影 / active 视图 / record-set 这些读侧 API |
| 与 `fg.batch` / `EntityEditor` 的边界 | EntityEditor 内 field-level API 的扩展(那是另一份设计) |

## §6 关联代码锚点

- `src/factgraph/sdk/store.py:784-795` — `_SDKFieldsManager.add(field, e_ref, value, ...)` 当前签名
- `src/factgraph/sdk/store.py:797-830` — `_SDKFieldsManager.retract(...)`(单 value 匹配)
- `src/factgraph/sdk/store.py:2151-2208` — `_apply_field_mutation` 把单 value 包成单个 `FieldMutation`
- `src/factgraph/sdk/store.py:2210-2236` — `_build_application_write_value` 走到 `_coerce_sdk_value_to_tag`
- `src/factgraph/sdk/store.py:3216-3262` — `_coerce_sdk_value_to_tag` 的严格 isinstance 检查(拒绝 list 的源头)
- `src/factgraph/sdk/schema.py:495-518` — multi-cardinality field 的 `type_domain = inner.type_domain`(元素 tag)
- `src/factgraph/application/protocol/entity_write.py:30-52` — `FieldMutation` 的 `WriteValue` 类型(application 层接受 `JSONValue`,允许 list,但 SDK 边界先拒绝)

## §7 关联文档

- 三层 API 用户面文档:[`docs/quickstart/three_layer_api.md`](../../../../docs/quickstart/three_layer_api.md) §3(Layer 2 Fields)
- Schema 用户面文档:[`docs/quickstart/schema_definition.md`](../../../../docs/quickstart/schema_definition.md)
- Data model 用户面文档:[`docs/quickstart/data_model.md`](../../../../docs/quickstart/data_model.md)
- 同级 design-point:[`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md)
