# Read / Write Namespace、Snapshot 结构与 Assertion 精确选择

Status: working / non-authoritative
Authority: 研究笔记。当前实现真相仍以 `src/kernel/sdk/`、`src/kernel/application/`、`src/kernel/core/` 及 `src/kernel/sdk/docs/` 为准。本文用于沉淀用户文档解释方式，未来可反哺 SDK docs，但它本身不是 release 契约。

## 1. 这份文档要解释什么

FactGraph 的 SDK 看起来像一个很普通的对象 API：

```python
ref = fg.read.ref(User, user_id="u-1", locale="en")
fg.write.set(User.name, ref, "Alice")

snap = fg.read.get(User, user_id="u-1", locale="en")
print(snap.name)
```

但它的底层不是“数据库行被覆盖”的模型，而是 append-only fact ledger：

- `read` namespace 负责定位、观察、筛选、选择；
- `write` namespace 负责追加新 assertion，或追加一个 revocation assertion；
- `EntitySnapshot` 不是一个可变 ORM object，而是某个时间点读出来的只读事实视图；
- `retract(asrt_id)` 撤销的是一条具体 assertion，不是“删除某个 entity 的某个值”。

这意味着一个真实的撤销操作不应该写成：

```python
# 不存在这种 API，也不应该存在这种默认语义
fg.write.retract(User.name, ref, value="Alice")
```

因为这会留下一个危险问题：如果同一个字段下有多条 `"Alice"` assertion，应该撤哪一条？全部撤销吗？第一条吗？最新一条吗？FactGraph 的选择是保持 write-side 精确：**用户先在 read-side 找到一条确定的 assertion，再把它的 `asrt_id` 交给 `write.retract(...)`。**

本文要讲的就是这条链路：

```text
read.get / read.find
  -> EntitySnapshot
    -> FieldAssertions
      -> AssertionRecordSet
        -> AssertionRecord.asrt_id
          -> write.retract(asrt_id)
```

## 2. FactGraph 的 CRUD 不是表格 CRUD

在传统 CRUD 想象里，一个 entity 可能像一行表：

```text
User row
  user_id = "u-1"
  name = "Alice"
```

更新名字就是改掉这一格，删除名字就是把这一格清空。

FactGraph 的事实模型不同。一个 entity coordinate 下面挂的是一组 append-only assertions：

```text
User(user_id="u-1", locale="en") -> idref_v1

field: name
  asrt-001: value="Alice", source="seed", active
  asrt-002: value="Alice Liddell", source="hr", active
  asrt-003: revokes asrt-001, source="manual-fix", active
```

所以：

- `set(...)` / `add(...)` 不是原地覆盖底层 ledger row，而是追加一条新的 assertion；
- `retract(...)` 不是物理删除，而是追加一条撤销记录；
- 原始 assertion 仍然可以在 history / audit 里被看见；
- 当前视图如何选择一个 scalar value，是 read-side view policy 的问题，不等同于底层只有一个值。

这也是为什么 `asrt_id` 是一等重要对象。它不是 entity id，而是某条事实 assertion 的 id。一个 entity 可以有很多字段，一个字段可以有很多 assertion，每条 assertion 都有自己的 `asrt_id`。

## 3. `read` namespace：定位、观察、筛选

`read` namespace 的核心职责是把用户从 schema-level 概念带到可观察的 snapshot。

### 3.1 `fg.read.ref(...)`

`ref(...)` 生成一个 canonical entity ref：

```python
ref = fg.read.ref(User, user_id="u-1", locale="en")
```

这个 `ref` 是 opaque token。用户可以把它交给 `write.set(...)` / `write.add(...)`，但不应该解析它的字符串结构。

从抽象层次看：

```text
Identity coordinate
  -> idref_v1 ref
    -> write-side target for field assertions
```

### 3.2 `fg.read.get(...)`

`get(...)` 读取一个完整 coordinate：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")
```

返回：

```text
EntitySnapshot | None
```

它适合“我知道我要哪个具体 coordinate”的场景。比如 `User(user_id="u-1", locale="en")` 和 `User(user_id="u-1", locale="zh")` 是两个不同 coordinate，`get(...)` 应该明确指向其中一个。

### 3.3 `fg.read.find(...)`

`find(...)` 是筛选多个 snapshots：

```python
rows = fg.read.find(User, user_id="u-1")
```

它可以用于 primary anchor 级读取，也可以组合 field filters：

```python
engineers = fg.read.find(User, tags="engineer")
alice_domains = fg.read.find(User, user_id="u-1")
alice_engineers = fg.read.find(User, user_id="u-1", tags="engineer")
```

返回：

```text
list[EntitySnapshot]
```

这里要注意：`find(...)` 返回的是多个 complete snapshots，而不是一个“logical entity aggregate”对象。每个 `EntitySnapshot` 仍然对应一个 full coordinate，并且 snapshot 里的 assertion records 仍然属于那个 coordinate。

## 4. `write` namespace：追加 assertion，或撤销 assertion

`write` namespace 的核心职责是产生 ledger 变化。

### 4.1 `fg.write.set(...)`

`set(...)` 用于 single-cardinality field：

```python
name_asrt_id = fg.write.set(
    User.name,
    ref,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001"},
)
```

返回值是新写入 assertion 的 `asrt_id`：

```text
name_asrt_id -> "asrt-..."
```

用户应该把这个返回值理解成“这次写入的事实 id”。如果之后要精确撤销这次写入，最直接的方式就是保存它。

### 4.2 `fg.write.add(...)`

`add(...)` 用于 multi-cardinality field：

```python
tag_asrt_id = fg.write.add(
    User.tags,
    ref,
    "engineer",
    meta={"source": "profile", "trace_id": "import-001"},
)
```

它同样返回 persisted `asrt_id`。

### 4.3 `fg.write.edit(...)`

`edit(...)` 是编辑器风格的写入入口。它适合把多个 field 操作组织成一个更接近对象编辑的流程：

```python
with fg.write.edit(User, user_id="u-1", locale="en") as user:
    user.name.set("Alice", meta={"source": "hr"})
    user.tags.add("engineer", meta={"source": "profile"})
```

在这个模型里，读写边界仍然没有改变：editor 负责产生写操作；如果你要撤销历史里的某一条 assertion，仍然需要一个明确的 `asrt_id`。

### 4.4 `fg.write.retract(...)`

`retract(...)` 的签名语义是：

```python
revoker_asrt_id = fg.write.retract(target_asrt_id, meta={"trace_id": "fix-001"})
```

这里有两个 id：

```text
target_asrt_id   -> 被撤销的原 assertion
revoker_asrt_id  -> 这次撤销动作本身产生的新 assertion id
```

如果目标已经被撤销，当前实现可能返回 `None`，表示没有再产生新的撤销 assertion。

重要的是：`retract(...)` 接收的是 `asrt_id`，不是 entity ref，也不是 `(field, value)` selector。

```python
fg.write.retract(ref)          # 错：ref 是 entity coordinate，不是 assertion id
fg.write.retract("Alice")      # 错：value 不是 assertion id
fg.write.retract(target.asrt_id)  # 对：明确撤销一条 assertion
```

## 5. `EntitySnapshot` 的完整层级

`EntitySnapshot` 是 read-side 返回的只读视图。它不是一条 assertion，而是某个 entity coordinate 下的一组 field views 和 assertion histories。

可以用这张结构图理解：

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
   ├─ snap.field("name")              -> FieldAssertions
   └─ snap.assertions.name            -> FieldAssertions

FieldAssertions
├─ .active                            -> AssertionRecordSet
├─ .history                           -> AssertionRecordSet
├─ .at("2026-05-01T00:00:00Z")        -> AssertionRecordSet
└─ .version(3)                        -> AssertionRecordSet

AssertionRecordSet
├─ tuple-compatible behavior
│  ├─ len(records)
│  ├─ records[0]
│  ├─ records[:2]
│  ├─ for record in records
│  └─ records + other_records
│
└─ selection helpers
   ├─ .where(...)
   ├─ .one()
   ├─ .all()
   └─ .first()

AssertionRecord
├─ asrt_id
├─ value
├─ is_active
├─ is_revoked
└─ meta                              -> AssertionMeta

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

它适合“展示当前值”。但它不适合做精确撤销，因为 scalar view 不告诉你“这个值来自哪一条 assertion”。

### 5.2 Assertion view

需要精确选择 assertion 时，进入 assertion view：

```python
snap.field("name")
snap.assertions.name
```

两者等价。前者适合动态 field name，后者适合静态属性访问。

```python
name_assertions = snap.field("name")
same = snap.assertions.name
```

### 5.3 `.active` / `.history` / `.at(...)` / `.version(...)`

`FieldAssertions` 有四个主要读入口：

```python
snap.field("name").active
snap.field("name").history
snap.field("name").at("2026-05-01T00:00:00Z")
snap.field("name").version(3)
```

它们都返回 `AssertionRecordSet`。

语义上：

- `.active`：当前未撤销的 assertions；
- `.history`：完整历史，包括 active 和 revoked；
- `.at(t)`：按 business-time 可见性筛选，命中 `meta.raw["valid_from"]` / `meta.raw["valid_to"]`；
- `.version(v)`：按 assertion metadata 中的 `meta.raw["version"]` 选择。

`.at(t)` 不看 `ingested_at`。`ingested_at` 是系统写入时间，也就是这条 assertion 何时进入 ledger；`valid_from` / `valid_to` 是业务有效时间，也就是这条 fact 在业务语义上从什么时候到什么时候有效。当前实现使用的是半开区间：

```text
valid_from <= t and (valid_to is missing or valid_to > t)
```

如果一条 assertion 没有 `valid_from`，它不会被 `.at(t)` 命中。`valid_to == t` 也不会命中，因为右边界是开区间。

为什么 `.at(...)` 和 `.version(...)` 是方法，而不是提前挂好的四个 tuple？

因为它们需要参数。`active` 和 `history` 是已经确定的集合；`at(t)` 和 `version(v)` 是“基于某个输入做一次筛选”。所以合理结构是：

```text
active/history  -> property
at/version      -> method returning AssertionRecordSet
```

### 5.4 这不是 whole-graph view

这里的 `.active`、`.history`、`.at(t)`、`.version(v)` 都挂在一个 `FieldAssertions` 上：

```python
snap.field("name").active
snap.field("name").history
snap.field("name").at("2026-05-01T00:00:00Z")
snap.field("name").version(3)
```

也就是说，它们是在问：

```text
这个 snapshot 的这个 field 下，哪些 assertion 处于 active/history/某个业务时间点/某个 version？
```

它们不是 graph-level API。当前没有：

```python
fg.read.active(...)
fg.read.at("2026-05-01T00:00:00Z")
fg.view.at("2026-05-01T00:00:00Z")
```

`ViewSpec` 也不是这个含义。当前 `ViewSpec` 主要描述 legacy projection policy，例如是否只看 active assertions、按 `confidence` 选择、或偏好某个 `source`。它不能表达 “整个 graph 在业务时间点 t 的 temporal snapshot”。

新的 frozen assertion view model 把 `fg.views` 的长期语义对齐为 “named frozen assertion-id selection”：一个 view 名字对应一组创建时冻结的 `asrt_id`。但这个 first slice 仍然不把 frozen view 接入 snapshot projection 或 rule/runtime projection。也就是说：

```python
view = fg.views.get("review_set")      # FrozenAssertionView
records = fg.assertions.by_ids(view.asrt_ids)
```

这是 record-level readback。它不是：

```python
fg.read.find(User, view="review_set")  # frozen view 目前会被拒绝
fg.run(rule, view="review_set")        # frozen view 目前会被拒绝
```

所以当前能力分层是：

```text
ViewSpec
  -> legacy active/conflict projection policy compatibility
  -> not a business-time graph snapshot

FrozenAssertionView
  -> named frozen assertion-id membership
  -> read back via fg.assertions.by_ids(...)
  -> not snapshot/rule projection in the current slice

FieldAssertions.at(t)
  -> field-level assertion filter
  -> uses meta.raw["valid_from"] / meta.raw["valid_to"]
```

如果未来需要 whole-graph point-in-time view，应该作为单独能力设计，而不是把 `FieldAssertions.at(t)` 误认为已经提供了 graph-level temporal view。

## 6. `AssertionRecordSet` 语法全集

`AssertionRecordSet` 是 tuple-compatible returned object。它不是新的 top-level SDK export；用户通常不需要 import 它。你只会从 snapshot assertion paths 上拿到它。

### 6.1 它像 tuple 一样工作

现有 tuple 习惯仍然成立：

```python
records = snap.field("tags").active

len(records)
records[0]
records[:2]

for record in records:
    print(record.value)
```

切片、拼接和乘法仍然保留 helper 类型，所以可以继续链式筛选：

```python
subset = records[:5]
target = subset.where(source="seed").where(value="engineer").one()
```

如果你想拿回普通 tuple，使用：

```python
plain = records.all()
```

### 6.2 `.where(...)`

`.where(...)` 做 read-side assertion selection：

```python
records.where(value="Alice")
records.where(source="seed")
records.where(trace_id="import-001")
records.where(confidence=0.95)
records.where(version=3)
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

这表示：同时满足 value、source、trace_id 的 assertion 必须正好一条。

`version=...` 是 `AssertionMeta.raw["version"]` 的便利筛选。`valid_from` / `valid_to` 也在 `AssertionMeta.raw` 中，但它们不通过 `.where(valid_from=...)` 暴露为快捷参数；业务时间切片应该使用 `.at(t)`。更一般的 metadata 用 `meta={...}`：

```python
snap.field("name").history.where(meta={"version": 3, "batch": "b1"})
```

### 6.3 显式 `None` 和省略条件不同

这是一个容易误解的点：

```python
records.where()
```

表示不按这些维度过滤。

```python
records.where(source=None)
```

表示筛选 `record.meta.source is None` 的 records。也就是说，显式传入 `None` 是一个真实过滤条件；不传才是不参与过滤。

### 6.4 `.one()`

`.one()` 是最适合 destructive / mutation 前使用的选择器：

```python
target = records.where(value="Alice", source="seed").one()
```

它要求当前集合里正好有一条 record：

- 0 条：抛出 SDK error；
- 2 条或更多：抛出 SDK error；
- 1 条：返回那条 `AssertionRecord`。

这就是 `retract` 前的 “are you sure” 机制。不是靠 UI 弹窗确认，而是靠数据选择语义确认：**你给出的筛选条件必须唯一定位一条 assertion。**

### 6.5 `.first()`

`.first()` 返回第一条，空集合返回 `None`：

```python
preview = records.where(source="seed").first()
```

它适合 UI preview、debug、非破坏性浏览。不建议用它来驱动 `retract`：

```python
# 不推荐：first() 没有 exactly-one 保护
target = records.where(value="Alice").first()
if target is not None:
    fg.write.retract(target.asrt_id)
```

如果你要撤销，优先用 `.one()`。

### 6.6 `.all()`

`.all()` 返回普通 tuple：

```python
all_seed_records = records.where(source="seed").all()
```

它适合传给只接受 plain tuple 的旧工具，或明确不想继续使用 helper 方法的场景。

## 7. 专业 retract 模式

推荐模式是四步：

```text
1. read.get / read.find 取得 snapshot
2. 进入某个 field 的 assertion history / active set
3. 用 where(...).one() 精确选择一条 assertion
4. 把 target.asrt_id 交给 write.retract(...)
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

- 它没有猜测 assertion id；
- 它没有靠 `records[0]` 假设顺序；
- 它没有把 value 当作唯一身份；
- 它要求筛选条件唯一定位一条 assertion；
- 它把 selection 放在 read-side，把 mutation 放在 write-side。

## 8. 常见场景

### 8.1 写入后立即保存 `asrt_id`

最直接的方式是在写入时保存返回值：

```python
name_asrt_id = fg.write.set(
    User.name,
    ref,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001"},
)
```

如果你的业务流程知道“后续可能撤销这次写入”，保存 `name_asrt_id` 是最干净的。

### 8.2 事后从 history 找回 `asrt_id`

如果写入时没有保存 id，可以从 snapshot history 找：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")

target = (
    snap.assertions.name
    .history
    .where(value="Alice", source="seed")
    .one()
)

fg.write.retract(target.asrt_id)
```

### 8.3 用 metadata 缩小选择

如果 value 不唯一，就加 metadata：

```python
target = (
    snap.field("tags")
    .history
    .where(
        value="engineer",
        source="profile-import",
        trace_id="run-2026-05-11",
        meta={"batch": "b7"},
    )
    .one()
)
```

这比 `records[0]` 更专业，因为它把“为什么是这一条”的业务依据写进代码。

### 8.4 `.one()` 抛错时该怎么办

`.one()` 抛错通常是好事：它阻止你在不确定时执行 mutation。

如果是 0 条：

- 检查 value 是否写错；
- 检查你查的是 `.active` 还是 `.history`；
- 检查 `source` / `trace_id` / `meta` 是否过窄；
- 检查 snapshot coordinate 是否正确。

如果是多条：

- 增加 `source`、`trace_id`、`confidence`、`version` 或 `meta` 条件；
- 或把结果展示给人工选择；
- 不要改用 `records[0]` 绕过问题。

### 8.5 `read.find(...)` 与 retract

如果你只有 primary anchor，可以先用 `find(...)` 找到多个 coordinate：

```python
snaps = fg.read.find(User, user_id="u-1")
```

然后逐个 snapshot 做 assertion selection：

```python
for snap in snaps:
    target = snap.field("tags").active.where(value="engineer").first()
    if target is not None:
        print(snap.identity, target.asrt_id)
```

注意：这里使用 `.first()` 只是在 preview。真正 retract 前应该让用户或业务规则选定唯一 coordinate，并在那个 coordinate 内使用 `.one()`：

```python
snap = fg.read.get(User, user_id="u-1", locale="en")
target = snap.field("tags").active.where(value="engineer", source="profile").one()
fg.write.retract(target.asrt_id)
```

## 9. 不推荐的写法

### 9.1 Magic assertion id

```python
fg.write.retract("asrt-abc-123")
```

除非这个 id 来自真实写入返回值或 read-side `AssertionRecord.asrt_id`，否则这只是一个 magic string。文档和 demo 不应该教这种模式。

### 9.2 `records[0]` 驱动撤销

```python
records = snap.field("name").history.where(value="Alice")
fg.write.retract(records[0].asrt_id)
```

这段代码的问题不是“不能运行”，而是它没有说明为什么第 0 条就是正确目标。顺序不是业务确认机制。

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

### 9.3 按 value 直接删除

```python
# 不存在，也不推荐设计成默认语义
fg.write.retract(User.name, ref, value="Alice")
```

这会把“选择哪一条 assertion”的责任塞进 write-side。FactGraph 当前保持更清楚的分工：read-side 选择，write-side 按 id 撤销。

## 10. Snapshot 与底层 audit 数据的关系

底层 ledger / audit 数据可以看成更接近表格形态：每条 assertion 都有 id、predicate、entity ref、value、metadata、revocation 状态等。

SDK 的 `EntitySnapshot` 是对这些底层记录的用户侧组织方式：

```text
ledger assertion rows
  -> group by entity coordinate
    -> group by schema field
      -> expose scalar view + assertion records
```

所以可以说：

- 底层数据可以被组织成 `EntitySnapshot`；
- 用户通过 `EntitySnapshot` 可以重新拿到 assertion-level 信息；
- 但二者不是完全对称的“来回转换对象”。

`EntitySnapshot` 是 read model，不是 ledger row 本身。它帮用户把底层事实按 schema 组织起来，但不会把所有底层细节都变成可写对象。真正的 mutation 仍然通过 `write` namespace。

这也是 read/write 分离的价值：read model 可以越来越友好，write model 仍然保持审计上的精确和保守。

## 11. 数据文件导入、读取与 CRUD

FactGraph 可以从数据文件或外部数据源导入事实，然后继续用 read/write API 操作这些事实。概念流程是：

```text
external rows / files
  -> ingest / write assertions
    -> ledger
      -> read snapshots
        -> select assertion records
          -> write more assertions or retract by asrt_id
```

导入后的事实不会变成“普通表格行”被原地改写。它们仍然是 assertions：

- 导入产生 assertion ids；
- read 可以看到这些 assertions；
- 后续修正可以追加新 assertion；
- 后续撤销可以通过 `asrt_id` 精确撤销旧 assertion。

这是一种专业化做法，尤其适合需要 provenance、audit、history、conflict handling 的系统。它比简单 CRUD 更啰嗦，但换来的是：每一次写入和撤销都有记录，每一个当前值背后都能追溯到 assertion。

## 12. 设计边界与未来可能性

当前行为刻意保持几个边界：

- `AssertionRecordSet` 是 returned-object helper，不是 top-level `kernel.sdk` export；
- `fg.read.*` 没有新增 `assertions(...)` namespace 方法；
- `fg.write.retract(...)` 仍然只接收 `asrt_id`；
- `retract(AssertionRecord)` overload 暂未提供；
- predicate DSL / fuzzy retract 不在当前行为内。

未来可以重新讨论的方向包括：

- 是否让 `fg.write.retract(record)` 作为 `fg.write.retract(record.asrt_id)` 的便利写法；
- 是否为 UI 场景提供更强的 selection review object；
- 是否为 batch 操作提供更集中的 assertion selection reporting。

但这些都应该建立在当前原则上：**不让 write-side 自动猜测用户要撤销哪一条 assertion。**

## 13. 文档启示

未来把本文内容迁移到正式 SDK docs 时，建议坚持几条表达：

- 说 `set/add` 返回 `asrt_id`，不要只展示副作用；
- 说 `retract` 接收 `asrt_id`，不要把它和 `set/add` 的 entity ref 参数并列；
- 展示 `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord` 层级；
- 用 `.where(...).one()` 教 exactly-one selection；
- 不用 magic assertion id 作为正常示例；
- 不用 `records[0]` 作为 retract 教学；
- 把 `.first()` 限定在 preview / browse 场景；
- 明确 `AssertionRecordSet` 是 tuple-compatible，但比 plain tuple 多了 selection helpers。

如果用户记住一句话，可以是：

```text
read side 负责找到“哪一条 assertion”，write side 只负责撤销这个明确的 asrt_id。
```
