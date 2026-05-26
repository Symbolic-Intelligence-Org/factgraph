# Match API Design — Query Migration / Read-Side Pattern Matching

- Status: active design point
- Created: 2026-05-26
- Owner cycle: T11.2.7
- Related blueprint: `workflow/blueprints/active/2026-05-26_t11-2-7-match-api-design.md`
- Parent source: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §6
- Scope: v0.2 match API shape only. Runtime implementation is deferred.

## 1. 目的

旧 `Query` 机制一直处在"有运行时能力,但没有新公共 API 归宿"的状态。
T5/T11 之后,公开 API 已经转向 application `Rule` / `RuleExpr`、`EvaluateResult`
和 attach-time view scope,但 `match / evaluate / prove` 三任务划分仍未正式写入
parent essay §6。

本设计只锁定 **read-side match** 的 v0.2 形状:

- 用 `Rule` / `RuleExpr` 作为匹配模板;
- 用 `Rule.ports` 定义输出;
- 返回用户可直接消费的 snapshot / value,而不是 evaluate-like result envelope;
- 保留旧 `Query` 为兼容 / 迁移对象,不作为新主路径;
- 为后续 `fg.eval.run` hard-cut 提供 replacement direction,但本设计不删除 `run`。

## 2. Mental Model

| Surface | Input | Filter style | Returned item |
|---|---|---|---|
| `fg.read.find(...)` | Entity class | field kwargs | Entity snapshot |
| `fg.assertions...where(...)` | Assertion record set | assertion/meta predicates | `AssertionRecord` |
| `fg.read.match(...)` | `Rule` / `RuleExpr` template | port kwargs + `.where(...)` | port values: entity snapshots or raw values |

Match 是读取面(pattern search),不是推理面。它回答:

> 当前 snapshot / attached view 里,有哪些已经存在的项满足这个模板?

它不回答:

- 这个结论是否可证明;
- 为什么失败;
- 哪些 evidence tree 支持推导;
- 哪些 assertion witness 参与了匹配。

这些属于 evaluate / explain / evidence / future witness bridge。

## 3. Public Entry

v0.2 目标形状:

```python
fg.read.match(template, **port_constraints) -> MatchView
```

其中:

- `template` 是唯一必填 positional 参数;
- `template` 必须是 application `Rule` 或 `RuleExpr`;
- `**port_constraints` 用 port name 作为 keyword;
- 控制参数不放在 keyword 中,避免和 port name 冲突;
- 控制行为使用链式方法,例如 `.where(...)`, `.limit(n)`, `.select(...)`,
  `.one()`, `.first()`, `.count()`。

示例:

```python
matches = fg.read.match(user_in_region, region="US")

for row in matches:
    print(row.user.user_id, row.region)

for user in fg.read.match(user_in_region, region="US").select("user"):
    print(user.user_id)
```

## 4. Template Contract

### 4.1 `Rule`

单个 application `Rule` 是基础模板。

```python
with vars("u", "region") as (u, region):
    user_in_region = build_application_rule(
        id="user:region",
        where=[User(u), User(u).region == region],
        ports={"user": u, "region": region},
    )
```

`where` 描述匹配条件,`ports` 描述输出 contract。
Match 不使用 Query-style `head`,也不使用 evaluate-side projection target。

### 4.2 `RuleExpr`

`RuleExpr` 是多模板组合形态。

```python
expr = RuleExpr.all(user_in_region, order_in_region)

for user, order in fg.read.match(expr, region="US").select("user", "order"):
    ...
```

v0.2 不接受 bare list / tuple:

```python
fg.read.match([R1, R2])        # not a public shape
fg.read.match(RuleExpr.all(R1, R2))
fg.read.match(R1 & R2)
```

原因: list/tuple 无法表达 AND / OR 语义,且与 `RuleExpr.all(...)` /
`RuleExpr.any(...)` 重复。

### 4.3 Legacy `Query`

旧 `Query(head, where, ...)` 是 read-side projection object,但它没有
application `Rule.ports` contract。

区别:

| Aspect | Legacy `Query` | Application `Rule` |
|---|---|---|
| Output contract | `head` projection | `ports` |
| Body | `where` | `where` |
| Identity | runtime-derived query digest | application rule id/version |
| Evidence/proof role | none | evaluate/prove can use Rule separately |
| Match role | compatibility / migration only | primary v0.2 template |

T11.2.7 不把 `Query` 作为新 `fg.read.match(...)` 主模板。若需要兼容,
应由后续 implementation blueprint 显式决定是否提供 adapter path。

## 5. Output Model

### 5.1 Ports Determine Output

Match 输出完全由 template ports 决定:

- entity-ref port -> resolved entity snapshot;
- value port -> raw value;
- multiple ports -> row / tuple projection.

`Rule.head` / legacy `Query.head` / evaluate-side head 不参与 match output。

```python
for row in fg.read.match(user_in_region):
    row.user      # User snapshot
    row.region    # raw value
```

### 5.2 `MatchView`

`MatchView` 是 thin, chainable collection,不是 evaluate-like result envelope。
用户可以知道它的名字,但日常不需要解析 envelope。

Required v0.2 surface:

```python
view.where(**port_constraints) -> MatchView
view.limit(n: int) -> MatchView
view.first() -> MatchRow | None
view.one() -> MatchRow
view.all() -> tuple[MatchRow, ...]
view.count() -> int
view.select(*port_names: str) -> ProjectedMatchView
```

`.where(...)` 可重复调用,约束累积:

```python
active_us_users = (
    fg.read.match(user_in_region)
    .where(region="US")
    .where(active=True)
    .select("user")
)
```

### 5.3 `MatchRow`

`MatchRow` 可作为内部 / 轻量公开类型存在,但设计目标是 attribute access 让
wrapper 几乎消失。

Required row behavior:

```python
row.user          # attribute access by port name
row["user"]       # dict-style fallback
```

Entity port resolution lazily returns snapshots. Value ports return raw bound
values.

### 5.4 `.select(...)`

`.select(...)` 是让 row wrapper 消失的主入口:

```python
fg.read.match(user_in_region, region="US").select("user")
# iterable of User snapshots

fg.read.match(user_in_region).select("user", "region")
# iterable of (User snapshot, region value)
```

Single-port projection returns direct values / snapshots.
Multi-port projection returns tuples in requested order.

## 6. Constraints

### 6.1 Direct kwargs

Primary form:

```python
fg.read.match(user_in_region, region="US")
```

This is intentionally not:

```python
fg.read.match(rule=user_in_region, ports={"region": "US"})
```

Rationale:

- `template` is the only required object and should remain positional;
- port constraints are the user's mental model;
- `ports={...}` makes a simple filter feel like an engine API.

### 6.2 Control Knobs

Control knobs use chain methods:

```python
fg.read.match(user_in_region, region="US").limit(10)
fg.read.match(user_in_region).select("user").one()
```

v0.2 should avoid keyword control parameters such as `limit=` because port names
are user-defined and may collide.

## 7. View Scope

Match follows T11.1 attach-time view scope:

```python
fg = FactGraph.attach(db, schema_classes=[User], view=view)
fg.read.match(user_in_region)
```

Method-level `view=` remains intentionally unsupported:

```python
fg.read.match(user_in_region, view=view)  # not v0.2
```

If implementation later exposes an error message, it should mirror the T11.1
read/evaluate hint:

> method-level view= not supported; use FactGraph.attach(db, view=view) instead

## 8. Witness / Assertion Boundary

v0.2 match returns snapshots / values. It does not expose witness assertion ids.

Deferred:

```python
fg.read.match(...).as_assertions()
fg.read.match(...).witnesses()
fg.read.match(...).to_view()
```

Reason:

- witness rows require assertion-id semantics;
- assertion witnesses may become input to EvidenceGraph / explanation work;
- this crosses into §9 RuleExpr x evidence joins and T6/T7 evidence cycles.

Users who need assertion records in v0.2 continue to use assertion APIs directly.

## 9. Relationship to `fg.eval.run`

This design locks replacement direction:

```python
fg.read.match(rule_or_expr, ...)
```

It does **not** delete `fg.eval.run`.

Deletion remains a later hard-cut after:

1. `fg.read.match(...)` implementation lands;
2. docs migrate from run/query examples to match;
3. compatibility / migration notes are reviewed;
4. release policy explicitly authorizes the hard cut.

## 10. Relationship to `facade.py`

T11.2.5 found a dirty `facade.py` change around property-style assertion access
and `AssertionRecordSet.__call__` compatibility.

This match design does **not** require match to return `AssertionRecordSet`.
Therefore the dirty `facade.py` change is not required by match.

Allowed downstream decisions:

- land `facade.py` as a standalone assertion ergonomics slice if desired;
- stash/revert it before release if it is only a prototype;
- revisit it later if witness / assertion-returning match becomes active.

It should not be justified as part of v0.2 match API.

## 11. Deferred Items

| Item | Deferred to |
|---|---|
| Runtime implementation of `fg.read.match(...)` | Future implementation blueprint |
| Legacy `Query` adapter path | Future compatibility decision |
| Query persistence (`fg.queries.save/load/list`) | Lifecycle / asset cycle |
| Witness assertion ids | Evidence / witness design |
| `.as_assertions()` / `.to_view()` | Future witness bridge |
| Method-level `view=` | v2 only if user demand appears |
| Snapshot-at-tx matching (`at=` / `as_of`) | Database snapshot cycle |
| RuleExpr x evidence joins | Parent §9 / evidence cycle |
| Service / OpenAPI match endpoint | Future service design, not v0.2 design-only cycle |

## 12. Commitments

| ID | Commitment |
|---|---|
| M1 | Public namespace target is `fg.read.match(...)`. |
| M2 | v0.2 match templates are application `Rule` and `RuleExpr`. |
| M3 | Bare list/tuple template inputs are not part of the public shape. |
| M4 | Legacy `Query` is compatibility/deferred, not the new primary template. |
| M5 | Output is determined by ports, not by Query/evaluate-style head. |
| M6 | Entity-ref ports resolve to entity snapshots; value ports return raw values. |
| M7 | `MatchView` is chainable and filterable with `.where(...)`. |
| M8 | `.select("port")` yields direct values/snapshots; multi-select yields tuples. |
| M9 | Port constraints use direct kwargs and chained `.where(...)`, not `ports={...}`. |
| M10 | Control knobs use chain methods to avoid port-name keyword conflicts. |
| M11 | Match follows attach-time view scope; method-level `view=` remains rejected. |
| M12 | Witness/assertion-returning match is deferred. |
| M13 | `fg.eval.run` deletion is not part of T11.2.7. |
| M14 | Dirty `facade.py` assertion ergonomics are independent of this match design. |
