# Read / Write、Snapshot、Assertion Selection 与 Frozen View 的统一理解

Status: working / non-authoritative
Authority: 研究笔记。当前实现真相仍以 `src/kernel/sdk/`、`src/kernel/application/`、`src/kernel/core/` 和 `src/kernel/sdk/docs/` 为准。本文用于沉淀解释方式和后续蓝图输入，不是 release contract。
Last updated: 2026-05-11

Related implementation / docs:

- `src/kernel/sdk/facade.py`
- `src/kernel/sdk/store.py`
- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/blueprints/archive/2026-05-10_assertion-selection-crud-ergonomics.md`
- `docs/blueprints/archive/2026-05-11_frozen-assertion-view-model.md`

## 1. 核心心智模型

FactGraph 不是一个表格 CRUD 系统。它更接近一个 append-only fact ledger：

```text
entity coordinate
  -> field assertion
    -> assertion identity (`asrt_id`)
      -> value + metadata + revocation state
```

用户在 SDK 里看到的是三层互相关联、但职责不同的视角：

```text
FactGraph / SDKStore
├─ as entity collection
│  ├─ fg.read.ref(...)
│  ├─ fg.read.get(...)
│  ├─ fg.read.find(...)
│  └─ fg.write.set/add/edit/retract(...)
│
├─ as assertion-id view registry
│  ├─ fg.views.create/update/delete/get/list(...)
│  └─ FrozenAssertionView(asrt_ids=frozenset[str])
│
└─ as assertion readback surface
   ├─ fg.assertions.by_id(asrt_id)
   └─ fg.assertions.by_ids(asrt_ids)

EntitySnapshot
├─ scalar field view: snap.name
├─ identity/ref metadata: snap.identity / snap.ref
└─ field assertion collections:
   ├─ snap.field("name")
   └─ snap.assertions.name
```

这个模型里最重要的分工是：

- `read` 负责定位 entity、观察 snapshot、选择 assertion；
- `write` 负责追加 assertion 或撤销某个明确 assertion；
- `views` 负责命名一组冻结的 `asrt_id` membership；
- `assertions` 负责从 `asrt_id` 反查 assertion record；
- `ViewSpec` 暂时保留为 legacy projection-policy compatibility，而不是 frozen view membership 本身。

一句话版：

```text
read side 找到“哪一条 assertion”，write side 只撤销这个明确的 asrt_id；
views side 保存“哪些 assertion ids 属于这个命名集合”。
```

## 2. 为什么 FactGraph 的 CRUD 不是表格 CRUD

传统表格 CRUD 会把 entity 想象成一行：

```text
User row
  user_id = "u-1"
  name = "Alice"
```

FactGraph 的底层不是“覆盖这一行的某一列”，而是追加事实：

```text
User(user_id="u-1", locale="en") -> idref_v1

field: name
  assertion A: value="Alice", source="seed", active
  assertion B: value="Alice Liddell", source="hr", active
  assertion C: revokes assertion A, source="manual-fix", active
```

因此：

- `set(...)` / `add(...)` 追加一条新的 field assertion，并返回这条 assertion 的 `asrt_id`；
- `retract(asrt_id)` 追加一条 revocation assertion，而不是物理删除原 assertion；
- 原 assertion 仍可在 history / audit 中被看到；
- scalar field 的“当前值”是 projection / read model，不是底层只有一个值。

这种做法更啰嗦，但它是专业化系统需要的取舍：每次写入、冲突、撤销和来源都可追踪。

## 3. `read` namespace：entity 层的定位与读取

### 3.1 `fg.read.ref(...)`

`ref(...)` 从 entity identity coordinate 生成 opaque `idref_v1` entity ref：

```python
ref = fg.read.ref(User, user_id="u-1", locale="en")
```

这个 ref 是 write-side 的 entity target：

```python
name_id = fg.write.set(User.name, ref, "Alice")
tag_id = fg.write.add(User.tags, ref, "engineer")
```

不要解析 ref 的字符串结构。它是 SDK / substrate 之间的 opaque coordinate token。

### 3.2 `fg.read.get(...)`

`get(...)` 读取一个完整 entity coordinate：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")
```

返回：

```text
EntitySnapshot | None
```

它适合“我知道完整 coordinate”的场景。`User(user_id="u-1", locale="en")` 和 `User(user_id="u-1", locale="zh")` 是不同 coordinate。

当前 `get(...)` 不接受 `view=`。

### 3.3 `fg.read.find(...)`

`find(...)` 返回多个 snapshots：

```python
rows = fg.read.find(User, user_id="u-1")
```

它支持 partial identity filters 和 field filters 的 AND 组合：

```python
fg.read.find(User, user_id="u-1")
fg.read.find(User, tags="engineer")
fg.read.find(User, user_id="u-1", tags="engineer")
```

返回：

```text
list[EntitySnapshot]
```

每个 `EntitySnapshot` 仍对应一个完整 coordinate。`find(...)` 不返回 logical entity aggregate。

`find(..., view=...)` 当前有两种语义边界：

- legacy `ViewSpec` 或 legacy view name：保留原有 projection-policy compatibility；
- `FrozenAssertionView` 或 frozen view name：当前 slice 明确拒绝，并指向 `fg.views.get(name).asrt_ids` + `fg.assertions.by_ids(...)` 的 record-level readback 路径。

## 4. `write` namespace：追加 assertion 与撤销 assertion

### 4.1 `set(...)` 与 `add(...)` 返回 `asrt_id`

`set(...)` 用于 single-cardinality field：

```python
name_asrt_id = fg.write.set(
    User.name,
    ref,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001"},
)
```

`add(...)` 用于 multi-cardinality field：

```python
tag_asrt_id = fg.write.add(
    User.tags,
    ref,
    "engineer",
    meta={"source": "profile", "trace_id": "import-001"},
)
```

两个方法都返回 persisted `asrt_id`。如果业务流程知道之后可能撤销这次写入，保存这个 id 是最直接、最可靠的方式。

### 4.2 `edit(...)`

`edit(...)` 是对象编辑风格的 write facade：

```python
with fg.write.edit(User, user_id="u-1", locale="en") as user:
    user.name.set("Alice", meta={"source": "hr"})
    user.tags.add("engineer", meta={"source": "profile"})
```

它仍然在底层产生 assertions。它不是 ORM dirty object，也不改变 `retract(asrt_id)` 的精确撤销原则。

### 4.3 `retract(asrt_id)`

`retract(...)` 接收的是 assertion id：

```python
revoker_asrt_id = fg.write.retract(
    target_asrt_id,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)
```

这里有两个 id：

```text
target_asrt_id   -> 被撤销的原 assertion
revoker_asrt_id  -> 这次撤销动作本身产生的新 assertion id
```

如果目标已经被撤销，当前实现可能返回 `None`，表示没有再产生新的 revocation assertion。

错误心智模型：

```python
fg.write.retract(ref)          # 错：ref 是 entity coordinate，不是 assertion id
fg.write.retract("Alice")      # 错：value 不是 assertion id
fg.write.retract(User.name, ref, value="Alice")  # 不存在，也不应作为默认语义
```

推荐心智模型：

```python
target = snap.field("name").history.where(value="Alice", source="seed").one()
fg.write.retract(target.asrt_id)
```

这就是 read/write 分离的“are you sure”机制：write-side 不猜测用户想删哪条，read-side 必须先唯一定位目标 assertion。

## 5. `EntitySnapshot` 的完整层级

`EntitySnapshot` 是 read model。它把底层 ledger assertions 按 entity coordinate 和 schema field 组织成用户可读结构。

```text
EntitySnapshot
├─ scalar field view
│  ├─ snap.name
│  └─ snap.tags
│
├─ identity / coordinate metadata
│  ├─ snap.identity
│  ├─ snap.identity_available
│  ├─ snap.entity_type
│  └─ snap.ref
│
└─ assertion access
   ├─ snap.field("name")       -> FieldAssertions
   └─ snap.assertions.name     -> FieldAssertions

FieldAssertions
├─ .active                     -> AssertionRecordSet
├─ .history                    -> AssertionRecordSet
├─ .at(t)                      -> AssertionRecordSet
└─ .version(v)                 -> AssertionRecordSet

AssertionRecordSet
├─ tuple-compatible behavior
│  ├─ len(records)
│  ├─ records[0]
│  ├─ records[:2]
│  ├─ for record in records
│  ├─ records + other_records
│  └─ records * 2
│
└─ selection helpers
   ├─ .where(...)
   ├─ .at(t)
   ├─ .version(v)
   ├─ .by_id(asrt_id)
   ├─ .one()
   ├─ .first()
   └─ .all()

AssertionRecord
├─ asrt_id
├─ value
├─ is_active
├─ is_revoked
└─ meta                       -> AssertionMeta

AssertionMeta
├─ source
├─ trace_id
├─ ingested_at
├─ confidence
├─ approved_by
├─ note
├─ derived_rule_id / derived_rule_version
├─ candidate_id / candidate_key / candidate_kind
└─ raw
   ├─ valid_from
   ├─ valid_to
   ├─ version
   └─ other user / system metadata
```

### 5.1 Scalar field view

最短路径是：

```python
snap.name
```

它适合展示当前值，但不适合撤销，因为它不告诉你这个值来自哪条 assertion。

### 5.2 Field assertion view

精确选择 assertion 时进入 field-level assertion view：

```python
snap.field("name")
snap.assertions.name
```

两者等价。前者适合动态 field name；后者适合静态属性访问。

## 6. `AssertionRecordSet`：统一的 assertion 集合操作

`AssertionRecordSet` 是 tuple-compatible returned object。它不是 top-level `kernel.sdk` export；用户通常不需要 import 它。

### 6.1 像 tuple 一样工作

```python
records = snap.field("tags").active

len(records)
records[0]
records[:2]

for record in records:
    print(record.value)
```

切片、拼接、乘法保留 helper 类型，所以后续还能继续 `.where(...)`：

```python
target = records[:5].where(source="seed").where(value="engineer").one()
```

如果需要普通 tuple：

```python
plain = records.all()
```

### 6.2 `.where(...)`

`.where(...)` 根据 value / metadata 筛选当前 record set：

```python
records.where(value="Alice")
records.where(source="seed")
records.where(trace_id="import-001")
records.where(confidence=0.95)
records.where(version="v1")
records.where(meta={"batch": "b1"})
```

多个条件是 AND：

```python
target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed", trace_id="import-001")
    .one()
)
```

`version=...` 是 `record.meta.raw["version"]` 的便利筛选。更一般的 raw metadata 用 `meta={...}`。

显式 `None` 和省略条件不同：

```python
records.where()             # 不按 source 过滤
records.where(source=None)  # 筛选 record.meta.source is None
```

### 6.3 `.active` / `.history` 是 base set

`active` 和 `history` 当前仍挂在 `FieldAssertions` 上：

```python
snap.field("name").active
snap.field("name").history
```

它们的语义是选择 base set：

- `.active`：当前未撤销的 assertions；
- `.history`：完整历史，包括 active 和 revoked。

它们不是 `AssertionRecordSet` 上的通用 filter。也就是说，当前没有：

```python
snap.field("name").history.active
```

这种写法不成立，因为 `history` 已经是一个 record set。

### 6.4 `.at(t)`：业务有效时间，不是 ingest time

`.at(t)` 过滤当前 record set 中在业务时间点 `t` 有效的 assertions：

```python
visible = snap.field("name").history.at("2026-05-01T00:00:00Z")
```

它命中的是：

```text
record.meta.raw["valid_from"]
record.meta.raw["valid_to"]
```

不是：

```text
record.meta.ingested_at
```

`ingested_at` 是 assertion 进入 ledger 的系统时间。`valid_from` / `valid_to` 是业务有效时间。

当前语义是半开区间：

```text
valid_from <= t and (valid_to is missing or valid_to > t)
```

因此：

- 缺少 `valid_from` 的 record 不被 `.at(t)` 命中；
- `valid_to == t` 不命中；
- `valid_to` 缺失表示右侧开放。

这回答了一个容易混淆的问题：`.at("2026-05-01T00:00:00Z")` 是问“这个时间点上哪些 assertions 有效”，不是问“这个时间区间内是否曾经有效”。

如果要回答区间问题，例如“这个 assertion 是否在 `[start, end)` 期间任意时间有效”，当前没有专门的 high-level helper。可以先用 `.history` 拿 record，再按 `valid_from` / `valid_to` 自己做 interval overlap；如果这个需求变常见，应另开蓝图设计 `.overlaps(start, end)` 或类似 helper。

### 6.5 `FieldAssertions.at(t)` 是 compatibility shortcut

当前有两种写法：

```python
snap.field("name").at("2026-05-01T00:00:00Z")
snap.field("name").active.at("2026-05-01T00:00:00Z")
```

它们等价。`FieldAssertions.at(t)` 是兼容快捷方式，定义为 active base set 上的 `.at(t)`。

如果你想在完整历史中按业务时间筛选，应显式写：

```python
snap.field("name").history.at("2026-05-01T00:00:00Z")
```

### 6.6 `.version(v)`

`.version(v)` 按 `record.meta.raw["version"] == v` 筛选当前 record set：

```python
v1_records = snap.field("name").history.version("v1")
```

`FieldAssertions.version(v)` 同样是 compatibility shortcut，等价于：

```python
snap.field("name").active.version("v1")
```

### 6.7 `.by_id(asrt_id)`

`.by_id(asrt_id)` 在当前 record set 内按 assertion id 精确筛选：

```python
target = snap.field("name").history.by_id(name_asrt_id).one()
```

它返回的仍是 `AssertionRecordSet`，所以可以继续 `.one()`、`.first()` 或 `.all()`。

### 6.8 `.one()` / `.first()` / `.all()`

`.one()` 要求正好一条：

```python
target = records.where(value="Alice", source="seed").one()
```

- 0 条：抛 SDK error；
- 多条：抛 SDK error；
- 1 条：返回 `AssertionRecord`。

`.first()` 返回第一条，空集合返回 `None`。它适合 preview / browse，不适合 destructive mutation。

`.all()` 返回普通 tuple。

## 7. `fg.views`：从 projection policy 走向 frozen assertion view

这部分是 2026-05-11 frozen assertion view model 的核心更新。

### 7.1 长期概念：View 是 named frozen assertion-id selection

长期概念上，FactGraph view 是：

```text
name -> frozen set of asrt_id strings
```

也就是：

```python
fg.views.create("review_set", asrt_ids=[name_asrt_id, tag_asrt_id])
view = fg.views.get("review_set")

view.asrt_ids  # frozenset[str]
```

`FrozenAssertionView` 的 membership 是创建或 update 时冻结的 `frozenset[str]`：

- 去重；
- 不保留顺序作为 public API；
- 允许空集合；
- 默认不做 ledger existence check；
- revoked assertions 仍然可以是 valid members；
- `FrozenAssertionView` 是 returned-object surface，不在 `kernel.sdk.__all__` 中。

### 7.2 `asrts=[...]` 是便利输入，membership 仍是 id

也可以从 objects 创建：

```python
target = snap.field("name").history.where(value="Alice", source="seed").one()
fg.views.create("review_set", asrts=[target])
```

任何对象只要暴露 `.asrt_id` 即可作为 convenience input。真正进入 view membership 的只有 `asrt_id`，不是 value、meta、active state 或对象 payload。

### 7.3 `update(...)` 是整体替换

```python
fg.views.update("review_set", asrt_ids=[other_asrt_id])
```

当前 first slice 没有 `patch(...)` / `diff(...)`：

```python
fg.views.patch(...)  # 不支持
fg.views.diff(...)   # 不支持
```

如果未来需要多人 review workflow 或增量更新 workflow，可以单独设计 patch/diff。

### 7.4 Legacy `ViewSpec` 仍然保留

当前 SDK 仍支持 legacy projection-policy view：

```python
from kernel.core.store.types import ViewSpec

spec = ViewSpec(active=True, confidence_strategy="max")

fg.views.create("preferred_names", spec)
fg.views.update("preferred_names", spec)
fg.views.get("preferred_names")  # ViewSpec
fg.views.list()                  # dict[str, ViewSpec | FrozenAssertionView]
```

这是 compatibility surface。`ViewSpec` 的长期命名可能更接近 `ProjectionSpec`，因为它描述的是冲突/活跃 projection policy，而不是 assertion universe membership。但当前不会移除或重命名它。

因此现在 `fg.views` registry 是混合读回：

```text
legacy entry          -> ViewSpec
frozen assertion view -> FrozenAssertionView
```

## 8. `fg.assertions`：从 frozen view 反查 records

`FrozenAssertionView` 只保存 `asrt_id` membership。要看具体 records，走 `fg.assertions`：

```python
view = fg.views.get("review_set")
records = fg.assertions.by_ids(view.asrt_ids)
```

也可以单条查：

```python
record = fg.assertions.by_id(name_asrt_id)
if record is not None:
    print(record.value, record.meta.source)
```

当前 `fg.assertions` 是 top-level read-only assertion namespace，只提供 by-id lookup：

```text
fg.assertions.by_id(asrt_id)       -> AssertionRecord | None
fg.assertions.by_ids(asrt_ids)     -> AssertionRecordSet
```

它不提供 graph-wide enumeration：

```python
fg.assertions.active      # 不支持
fg.assertions.history     # 不支持
fg.assertions.where(...)  # 不支持
fg.assertions.at(...)     # 不支持
fg.assertions.version(...)# 不支持
```

这是刻意的第一刀：先闭合 frozen view readback 链路，不把 SDK 变成 graph-wide assertion query language。

`by_ids(...)` 接受任意 `Iterable[str]`，所以可以直接传 `FrozenAssertionView.asrt_ids`。未知 id 默认跳过；当前没有 `strict=` 参数。

返回 records 使用现有 `AssertionRecord` shape，不额外增加 `entity_type`、`field_name`、`pred_id`、`ref` 或 identity context。更丰富的 graph assertion record 是后续蓝图问题。

## 9. Frozen view 不等于 snapshot/rule projection

这是当前最容易误读的边界。

Frozen assertion view 是 named membership：

```text
review_set -> frozenset({asrt_id1, asrt_id2, ...})
```

它当前不会自动变成：

```text
“只用这些 assertions 投影 EntitySnapshot”
“只用这些 assertions 运行 rule”
“整个 graph 的 temporal / active view”
```

当前行为：

```python
view = fg.views.get("review_set")
records = fg.assertions.by_ids(view.asrt_ids)  # 支持
```

但：

```python
fg.read.find(User, view="review_set")  # frozen view 当前拒绝
fg.run(rule, view="review_set", return_display_meta=True)  # frozen view 当前拒绝
fg.evaluate(..., view="review_set")  # view 参数一直拒绝
```

legacy `ViewSpec` 路径仍保留：

```python
fg.read.find(User, view="preferred_names")  # legacy ViewSpec name
fg.run(rule, view="preferred_names", return_display_meta=True)
```

换句话说：

```text
FrozenAssertionView
  -> record-level readback
  -> not snapshot projection in this slice
  -> not rule/runtime assertion-universe scoping in this slice

ViewSpec
  -> legacy projection-policy compatibility
  -> not frozen membership
```

这个边界避免把 membership 和 projection 混在一起。未来如果要支持 view-scoped reads 或 rule/runtime integration，应单独开蓝图，因为那会牵涉 entity visibility、field scalar projection、history exposure 和 runtime fact universe。

## 10. 专业 retract 模式

推荐流程：

```text
read.get / read.find
  -> EntitySnapshot
    -> field assertion set
      -> where(...).one()
        -> target.asrt_id
          -> write.retract(target.asrt_id)
```

完整例子：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")
if snap is None:
    raise LookupError("User coordinate not found")

target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed", trace_id="import-001")
    .one()
)

revoker_asrt_id = fg.write.retract(
    target.asrt_id,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)
```

这段代码的专业性在于：

- 没有 magic assertion id；
- 没有靠 `records[0]` 假设顺序；
- 没有把 value 当作唯一身份；
- 筛选条件必须唯一定位一条 assertion；
- selection 在 read-side，mutation 在 write-side。

如果你在写入时已经保存了 `asrt_id`，可以直接撤销：

```python
name_asrt_id = fg.write.set(User.name, ref, "Alice", meta={"source": "seed"})
fg.write.retract(name_asrt_id)
```

如果你从 frozen view 做 review：

```python
view = fg.views.get("review_set")
records = fg.assertions.by_ids(view.asrt_ids)

target = records.where(value="Alice", source="seed").one()
fg.write.retract(target.asrt_id)
```

## 11. 不推荐的写法

### 11.1 Magic assertion id

```python
fg.write.retract("asrt-abc-123")
```

除非这个 id 来自真实写入返回值、`AssertionRecord.asrt_id` 或可信导入，否则它只是 magic string。文档和 demo 不应把它作为正常路径。

### 11.2 `records[0]` 驱动撤销

```python
records = snap.field("name").history.where(value="Alice")
fg.write.retract(records[0].asrt_id)
```

这段代码的问题不是不能运行，而是没有解释为什么第 0 条就是正确目标。顺序不是业务确认机制。

更好的写法：

```python
target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed", trace_id="import-001")
    .one()
)
fg.write.retract(target.asrt_id)
```

### 11.3 按 value 直接删除

```python
fg.write.retract(User.name, ref, value="Alice")
```

当前没有这种 API，也不建议作为默认语义。它会把“选择哪一条 assertion”的责任塞进 write-side，容易不小心撤销多条或撤错一条。

## 12. 底层 ledger、snapshot 与 view 的关系

底层 ledger 可以想象成接近表格的 assertion rows：

```text
asrt_id
entity ref
predicate / field
value
metadata
revocation state
```

`EntitySnapshot` 是把这些底层 rows 按 entity coordinate 和 schema field 组织后的 read model：

```text
ledger assertion rows
  -> group by entity coordinate
    -> group by schema field
      -> expose scalar view + assertion records
```

`FrozenAssertionView` 则是另一种组织方式：

```text
ledger assertion rows
  -> select by exact asrt_id membership
    -> name the frozen membership set
      -> read back records by id
```

所以底层数据和 SDK 对象不是完全对称的“互相转换”：

- 底层 rows 可以被组织成 snapshots；
- snapshots 可以暴露 assertion records；
- frozen views 可以保存 assertion id membership；
- `fg.assertions.by_ids(...)` 可以从 ids 找回 records；
- 但 `EntitySnapshot` / `FrozenAssertionView` 都不是可写 ledger row 本身。

mutation 仍然通过 `write` namespace 完成。

## 13. 关于 graph-level、entity-level、field-level view 的层级

当前实现里，这些概念仍然是分层的：

```text
Graph / FactGraph level
├─ entity collection operations
│  └─ fg.read.* / fg.write.*
├─ view registry
│  └─ fg.views.*
└─ assertion by-id readback
   └─ fg.assertions.by_id/by_ids

EntitySnapshot level
└─ field assertion collections
   ├─ snap.field("name")
   └─ snap.assertions.name

Field level
└─ AssertionRecordSet operations
   ├─ active/history base sets
   └─ where/at/version/by_id filters
```

一个更统一的未来抽象可能是：

```text
fg.assertions              -> graph-level assertion collection
snap.assertions            -> entity-level assertion collection
snap.field("name").records -> field-level assertion collection
```

三者共享同一套 `.where(...)` / `.at(...)` / `.version(...)` / `.by_id(...)` / `.one()` / `.all()` 操作。

但当前 first slice 没有做到这一点。它只做了两件低风险事情：

1. field-level `AssertionRecordSet` 具备完整 filter / terminal helpers；
2. graph-level 只提供 by-id readback，避免 graph-wide enumeration 和 richer record shape。

这不是否认统一抽象的价值，而是把高风险部分拆出去：

- graph-wide enumeration 需要性能和索引策略；
- graph-level records 可能需要 entity / field / predicate context；
- entity-level whole-snapshot `snap.assertions.where(...)` 需要定义跨 field 的 record shape；
- view-scoped snapshot reads 需要定义 entity visibility 和 scalar projection。

这些适合后续蓝图，而不是混入 frozen view first slice。

## 14. 数据文件导入、读取与 CRUD

FactGraph 可以从数据文件或外部数据源导入事实，然后继续用 read/write API 操作这些事实。概念流程是：

```text
external rows / files
  -> ingest / write assertions
    -> ledger
      -> read snapshots
        -> select assertion records
          -> write more assertions or retract by asrt_id
```

导入后的事实不会变成普通表格行被原地改写。它们仍然是 assertions：

- 导入产生 assertion ids；
- read 可以看到这些 assertions；
- 后续修正可以追加新 assertion；
- 后续撤销可以通过 `asrt_id` 精确撤销旧 assertion；
- frozen view 可以保存某次 review / import / audit 选中的 assertion ids。

这是一种专业化做法，尤其适合 provenance、audit、history、conflict handling、human review 和 reproducibility。

## 15. 设计边界与未来可能性

当前已经支持：

- `set/add` 返回 `asrt_id`；
- `retract(asrt_id)` 精确撤销；
- `EntitySnapshot.field(...).active/history/at/version`；
- `AssertionRecordSet.where/at/version/by_id/one/first/all`；
- `fg.views.create/update(..., asrt_ids=[...])`；
- `fg.views.create/update(..., asrts=[...])`；
- `FrozenAssertionView.asrt_ids`；
- `fg.assertions.by_id/by_ids(...)`；
- legacy `ViewSpec` compatibility。

当前刻意不支持：

- `retract(AssertionRecord)` overload；
- predicate DSL / fuzzy retract；
- `fg.views.patch(...)` / `fg.views.diff(...)`；
- dynamic predicate view；
- graph-wide `fg.assertions.where(...)`；
- entity-level `snap.assertions.where(...)` across all fields；
- richer graph assertion record context；
- `strict=` mode for `fg.assertions.by_ids(...)`；
- frozen view scoped `fg.read.find(...)`；
- frozen view scoped `fg.run(...)` / `fg.evaluate(...)` / `project_view_facts(...)`。

这些不是“忘了做”，而是被有意拆成后续设计问题。原因是它们会改变更深层的语义：projection、runtime fact universe、record shape、性能模型或 write-side safety。

## 16. 文档表达建议

正式 SDK docs 里应持续坚持这些表达：

- `set/add` 返回 `asrt_id`；
- `retract` 接收 `asrt_id`，不是 entity ref；
- `records[0]` 不是专业 retract 模式；
- `.where(...).one()` 是 destructive action 前的 exactly-one selection；
- `.first()` 只适合 preview / browse；
- `.at(t)` 是 business-time point filter，使用 `valid_from` / `valid_to`，不是 `ingested_at`；
- `ViewSpec` 是 legacy projection-policy compatibility；
- `FrozenAssertionView` 是 named frozen assertion-id selection；
- frozen view 的当前 readback 路径是 `fg.assertions.by_ids(view.asrt_ids)`；
- frozen view 当前不驱动 snapshot projection 或 rule/runtime assertion-universe scoping。

如果用户只记住一句话：

```text
FactGraph 不是“改一行表”，而是“追加和选择 assertions”；view 命名一组 assertion ids，snapshot 组织 entity 下的 assertions，retract 只撤销明确的 asrt_id。
```
