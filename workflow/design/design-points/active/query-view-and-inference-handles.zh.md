# Query / View / Inference Handles Design Note

- Status: working / future blueprint input
- Authority: non-authoritative reference note; not current implementation truth
- Created: 2026-05-14
- Source Context:
  - `docs/blueprints/archive/2026-05-13_assertion-collection-scope-access.md`
  - `docs/blueprints/archive/2026-05-13_assertion-collection-scope-access.audit.md`
- Related Current Docs:
  - `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
  - `src/kernel/sdk/docs/04_api_surface.en.md`
  - `docs/official/kernel/quickstart/assertions.md`

## 1. 摘要

这份 note 把 assertion collection scope 设计中被明确 deferred 的一段想法
单独提出来：`Query`、view、`AssertionRecordSet` 和 `Inference` 的关系。

核心判断是：

```text
Query/Search 和 Inference 应该是两类不同权柄。

Query/Search 负责找到已经存在的东西，并可进一步形成 assertion-id view。
Inference 负责产生或证明一个 candidate / conclusion，并携带 evidence 权柄。
```

这不是当前实现行为。当前实现中：

- `Query` 返回 entity snapshots、scalar values 或 mapping rows。
- Query-returned `EntitySnapshot` 不携带 assertion witness records。
- `AssertionRecordSet.match(query)` 不存在。
- Frozen assertion view 是 assertion id set，不是可直接执行 query 的 scoped graph。

这份 note 的价值在于保留下一步设计方向：当我们想把“查找现有事实”和“推理生
成结论”分得更清楚时，view 可以成为 Query/Search 和 assertion selection 之间的
中间权柄。

## 2. 当前实现边界

### 2.1 Query 当前不是 assertion-returning surface

当前 `Query` 的结果语义是读取投影：

```text
Query(head=..., where=...) -> rows / EntitySnapshot / scalar values
```

它回答的是：

```text
当前 store 中哪些绑定满足 pattern？调用者要返回哪些投影？
```

它不回答：

```text
哪些 assertion ids 见证了这条 row？
```

因此当前 Query 结果不能直接进入：

```text
query rows -> asrt_ids -> AssertionRecordSet.where(...)
```

这条链路需要新的 witness 语义。

### 2.2 AssertionRecordSet 当前是 assertion selection DSL

`AssertionRecordSet` 已经承担了 assertion 集合上的链式选择：

```python
fg.assertions.active().where(source="seed").all()
snap.assertions.field("name").all().where(trace_id="import-001").one()
fg.assertions.by_ids(view.asrt_ids).where(value="Alice")
```

它的强项是对已经拿到的 assertion collection 做缩小、确认和终端选择。

它不是 general query engine。它也不执行 `Query`。

### 2.3 Frozen view 当前只是 id-set container

当前 frozen assertion view 的语义很窄：

```text
FrozenAssertionView = name + frozenset[asrt_id]
```

读取方式是：

```python
view = fg.views.get("review")
records = fg.assertions.by_ids(view.asrt_ids)
```

它不是 snapshot projection，不是 read policy，也不是 new FactGraph。

这一点在 assertion-collection slice 中被锁住：view-scoped
`.active()` / `.all()` / `.field(...)` 不属于当前实现。

## 3. 设计灵感：Query/Search 生成 view，view 再进入 assertion selection

我们讨论过一个自然但尚未实现的组合模型：

```text
original fg
  -> run Query/Search
  -> witness asrt_ids
  -> frozen view / scoped graph
  -> assertions.active().where(...).all()
```

它的用户心智是：

```text
先用 Query/Search 找到匹配项；
再把这些匹配项对应的 assertion ids 固化成一个 view；
再用 AssertionRecordSet 的链式 where / at / version / by_id 做精筛。
```

这比把所有条件都塞进一个大 Query 更符合当前 SDK 的分层：

- Query/Search：找到存在项，确定 candidate universe。
- View：保存或传递 assertion-id universe。
- AssertionRecordSet：在 assertion universe 上做用户可读的选择。
- Inference：产生或证明一个新 conclusion/candidate，不只是 search。

## 4. View 的理解：不是 projection，而是 fact/assertion universe handle

这个方向下，view 最重要的概念不是“显示哪些字段”，而是：

```text
一个被命名、可传递、可复用的 fact/assertion universe handle。
```

也就是说，view 可以作为 Query/Search 与后续处理之间的边界对象：

```text
Query/Search result witnesses -> view.asrt_ids -> assertion selection
```

但这不等于当前 `FrozenAssertionView` 已经是 scoped graph。未来如果要支持：

```python
scoped_fg = fg.from_view(view)
scoped_fg.assertions.active().where(...)
```

那是另一层 API，需要回答：

- scoped graph 是否只限制 facts，还是也限制 schema / registry / rules？
- scoped graph 中 `fg.read.find(...)` 是否只看 view universe？
- scoped graph 中 `fg.evaluate(...)` 的 fact universe 如何定义？
- view 中 revoked assertion 如何处理？
- view 是否可组合、相交、相减？

在没有这些答案前，最稳的语义仍然是：

```python
fg.assertions.by_ids(view.asrt_ids)
```

也就是 view 只是 assertion id container。

## 5. Query/Search 与 Inference 的权柄划分

### 5.1 Query/Search 权柄

Query/Search 的权柄应该围绕“存在项”：

```text
input: pattern / filters / optional universe
output: rows, snapshots, scalar values, or future witness ids
```

如果未来增加 witness，它也应该表达为：

```text
row + witness assertions
```

而不是把 Query 变成 Inference。

可能方向：

```python
rows = fg.query.match(query, witnesses=True)
view = fg.views.create("matched", asrt_ids=rows.asrt_ids)
records = fg.assertions.by_ids(view.asrt_ids).where(source="seed")
```

或：

```python
records = fg.assertions.active().match(query).where(source="seed")
```

这些只是方向，不是当前 API。

### 5.2 Inference 权柄

Inference 的权柄应该围绕“结论”：

```text
input: body pattern + conclusion head
output: CandidateSet / proof-backed conclusion / support handle
```

它不是单纯找已有事实。它可以：

- 证明一个 claim；
- 生成一个 candidate fact；
- 携带 support / provenance / evidence；
- 选择是否 accept 回 ledger。

因此 Inference 的结果权柄不是 view，而是 candidate / support。

### 5.3 两者的边界

简化心智模型：

| Surface | Question | Result Handle |
| --- | --- | --- |
| Query/Search | 当前有哪些存在项匹配？ | rows / snapshots / future witness ids |
| View | 这些 assertion ids 组成哪个 universe？ | frozen id set |
| AssertionRecordSet | 在这个 assertion universe 内如何精筛？ | selected assertion records |
| Inference | 哪个结论可由证据支持或生成？ | candidate / support / provenance |

## 6. 为什么不应该在 assertion-collection slice 中实现

assertion-collection slice 已经做了一个重要收敛：

```text
field / snapshot / graph scopes share AssertionRecordSet verbs.
```

如果同一 slice 同时实现 Query witness 或 scoped graph，会混合两个问题：

1. assertion collection surface cleanup；
2. Query/Search fact-universe design。

这会让实现不容易 review，也容易偷偷把 Query 变成 evidence/inference surface。

因此那次 slice 加了负向测试：

- Query-returned snapshots 仍不携带 assertion records。
- `AssertionRecordSet.match(query)` 仍不存在。

这些测试的作用是防止 scope creep，而不是否定未来设计。

## 7. 未来蓝图需要先回答的问题

如果要启动 Query/View/Search follow-up，建议先锁以下问题：

1. Query witness 的最小形状是什么？
   - per-row `asrt_ids`？
   - per-field witness map？
   - proof-like support artifact？
2. Query witness 是否只对 native Query 有效？
3. witness rows 是否包含 revoked assertions？
4. view 是否仍然是 id set，还是要升级为 fact-universe object？
5. `fg.read.find(...)` 是否应该接收 view/universe 参数？
6. `fg.evaluate(...)` 是否应该接收 view/universe 参数？
7. `AssertionRecordSet.match(query)` 是不是过早把 query engine 塞进 record set？
8. Query/Search 是否需要从 `fg.eval.run(query)` 中迁出，形成独立 namespace？

## 8. 文档动作建议

短期文档应该保持当前行为清晰：

- `Query` 返回 rows / snapshots / scalars，不返回 assertion witnesses。
- Frozen view 通过 `fg.assertions.by_ids(view.asrt_ids)` 读取。
- Inference 返回 candidate/support，不是 search result。

中期可开独立 blueprint：

```text
Query/Search witness and view-universe composition
```

该 blueprint 应该引用本 note，并明确它不是 assertion collection surface 的
补丁，而是 Query/Search 与 Inference 权柄划分的设计工作。

