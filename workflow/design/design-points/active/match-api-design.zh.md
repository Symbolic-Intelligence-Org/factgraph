# Match API Design — Query Migration / Read-Side Pattern Matching

- Status: active design point
- Created: 2026-05-26
- Last Updated: 2026-05-26
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
- 用 **EntityCls 作为 match 的"head"**(投影目标 entity 类);
- 用 `Rule.ports` 定义匹配 row 内部的 binding contract;
- 返回 **`tuple[EntityCls snapshot, ...]`**,与 `fg.read.find(...)` 同 shape;
- 保留旧 `Query` 为兼容 / 迁移对象,不作为新主路径;
- 为后续 `fg.eval.run` hard-cut 提供 replacement direction,但本设计不删除 `run`。

## 2. Mental Model

**Match 的本质是 evaluate-style format,但 head 是单一 EntityCls,执行通过 pattern matching 而非 inference engine**。

### 2.1 与 evaluate 同构

```
evaluate(template, head=projection_rule, semantics=..., view=...) -> EvaluateResult
match    (EntityCls, template,                              ...) -> tuple[snapshot, ...]
```

二者结构同构:
- **Template body** 描述匹配的 pattern
- **Head 投影目标** 决定 row 的核心 identity
- **附加约束 / 配置** 在调用时传入

差异:

| | `evaluate` | **`match`** |
|---|---|---|
| Head | application `Rule`(projection target predicate) | **单一 EntityCls** |
| Execution | inference engine(derives new claims) | **pattern matching**(finds existing snapshots) |
| Output | `EvaluateResult`(rows with `Claim` + `EvidenceRef`) | `tuple[EntityCls snapshot, ...]` |
| Semantics | optional probabilistic wrappers | deterministic |
| Witness | EvidenceGraph(可追溯) | 不暴露(v0.2 deferred) |
| Side effects | rows can `accept()` to persist | read-only |

### 2.2 与 read.find 同 namespace shape

```
read.get  (EntityCls, **identity_kwargs)                 -> snapshot \| None
read.find (EntityCls, **field_kwargs)                    -> tuple[snapshot, ...]
read.match(EntityCls, template, **port_constraints)      -> tuple[snapshot, ...]
read.ref  (EntityCls, **identity_kwargs)                 -> idref_v1 token
```

`read` namespace 完全统一:

- 第一参数永远是 `EntityCls`
- 关键字参数为 filter / constraint
- 无 chain 累积(每次 call 都 single-shot)
- 返回 native Python collection(tuple / single value / None / token)

**Read 是 single-call namespace**,不像 `assertions` 走 chain pattern(`field(...).active.where(...).at(...)...`)。Match 遵守此约束。

### 2.3 Match 回答什么 / 不回答什么

回答:

> 当前 snapshot / attached view 里,有哪些 `EntityCls` instance 已经满足这个 template pattern?

**不**回答:
- 这个结论是否可证明(→ evaluate / explain)
- 为什么 fail(→ failed Explanation envelope / why-not)
- 哪些 evidence tree 支持推导(→ EvidenceGraph)
- 哪些 assertion 是 witness(→ future witness bridge)

## 3. Public Entry

v0.2 签名:

```python
fg.read.match(
    entity_cls: type[Entity],
    template: Rule | RuleExpr,
    *,
    limit: int | None = None,
    **port_constraints: Any | Field,
) -> tuple[EntitySnapshot, ...]
```

参数语义:

- `entity_cls`(positional,必填)— **match 的 head**;决定投影目标和返回 item type
- `template`(positional,必填)— `Rule` 或 `RuleExpr`,定义匹配 body
- `limit`(kw-only,optional)— 结果 cap(safety knob)
- `**port_constraints`(kwargs)— port name 作为 key,literal value 或本类 Field descriptor 作为 value

返回:

- `tuple[entity_cls 的 snapshot, ...]`,**distinct**(不重复)
- 与 `read.find` 返回 shape 完全一致
- 直接 iterable / indexable / `len(...)`,无 wrapper DTO

示例:

```python
us_users = fg.read.match(User, user_in_region, region="US")

for user in us_users:
    print(user.user_id, user.region)

if not us_users:
    print("no match")

first_three = us_users[:3]
```

## 4. Template Contract

### 4.1 `Rule`

单个 application `Rule` 是基础 template:

```python
with vars("u", "region") as (u, region):
    user_in_region = build_application_rule(
        id="user:region",
        where=[User(u), User(u).region == region],
        ports={"user": u, "region": region},
    )

us_users = fg.read.match(User, user_in_region, region="US")
```

`where` 描述匹配条件;`ports` 描述 row 内部的 binding contract;Match 用 EntityCls 投影到对应 port。

**`Rule.head` 在 match 语境完全不参与**。`Rule.head` 是 evaluate-side projection target;match 用 EntityCls 替代该角色。

### 4.2 `RuleExpr`

`RuleExpr` 是多模板组合形态:

```python
u_ = user_in_region.as_("u_")
o_ = order_in_region.as_("o_")
expr = (u_ & o_).join_by_ports("region")

users_with_orders = fg.read.match(User, expr)
orders_with_users = fg.read.match(Order, expr)
```

EntityCls 选择投影方向。**同一个 expr 可被多个 match call 复用,EntityCls 不同 → 投影不同**。

v0.2 不接受 bare list / tuple:

```python
fg.read.match(User, [R1, R2])              # 不接受
fg.read.match(User, RuleExpr.all(R1, R2))  # OK
fg.read.match(User, R1 & R2)               # OK
```

理由:list/tuple 无法表达 AND/OR 语义,且与 `RuleExpr.all/any` 重复。

### 4.3 Legacy `Query`

旧 `Query(head, where, ...)` 是 read-side projection object,无 `ports` contract。

| Aspect | Legacy `Query` | Application `Rule` |
|---|---|---|
| Output contract | `head` projection | `ports` |
| Body | `where` | `where` |
| Identity | runtime-derived query digest | application rule id/version |
| Match role | compatibility / migration only | primary v0.2 template |

T11.2.7 不把 `Query` 作为 `fg.read.match(...)` 主模板。compatibility adapter 留给 future implementation blueprint 决定。

## 5. EntityCls as Match Head

EntityCls 在 match 中扮演 "head" 的角色 — 决定投影目标。

### 5.1 EntityCls 必须唯一映射到 template 中一个 entity_ref port

每个 port 有 `PortType(kind, entity_type)`:

- `entity_ref` port — 绑定 Entity 实例,有 `entity_type` 元数据
- `value` port — 绑定 raw value

`read.match(User, template, ...)` 的投影规则:

> Template 必须**恰好一个** port 的 `port_type` 是
> `(kind="entity_ref", entity_type="User")`。该 port 是投影 source。
> 返回 distinct User snapshots(同一 User 出现在多 row 不重复)。

### 5.2 错误处理

| 情况 | 错误 |
|---|---|
| Template 无 entity_ref port matching EntityCls | `SDKStoreError: template has no entity_ref port of type 'User'` |
| Template **多个** entity_ref ports matching EntityCls | `SDKStoreError: ambiguous projection — template has multiple User-typed ports: [...]` |
| EntityCls 不是 `Entity` 子类 | `SDKStoreError: read.match(EntityCls, ...) expects Entity subclass, got '...'` |

### 5.3 跨 entity tuple 返回不支持(v0.2)

不能用一次 `read.match` 同时拿 `(User, Order)` pair:

```python
# 不支持(v0.2 显式 non-goal)
pairs = fg.read.match((User, Order), expr)

# 想要 pair 必须两次 match 或走 evaluate
us_users  = fg.read.match(User, expr, region="US")
us_orders = fg.read.match(Order, expr, region="US")
# 用户自行 zip 或 cross-reference
```

这是 v0.2 的 deliberate trade-off:换取 read namespace 的 single-call 统一性,
multi-entity 关联留 evaluate 路径或后续 cycle。

### 5.4 Pattern Connectivity Requirement

#### 5.4.1 问题

Rule 的 `__post_init__`(`rule.py:91`)仅强制 port Var 必须在 `where` 中**出现**,
但不保证 port Var 之间通过 atoms 形成 connected graph。换言之,以下 rule 合法:

```python
# port Var 在 where 中存在,但 u 与 r 在 body 中无连接
with vars("u", "r") as (u, r):
    disconnected = build_application_rule(
        id="user:region:disconnect",
        where=[
            User(u),         # User existence
            Region(r),       # Region existence
            # NO atom connecting u and r
        ],
        ports={"user": u, "region": r},
    )
```

若直接执行:

```python
fg.read.match(User, disconnected, region="US")
# Cartesian product:对每个 User u,只要存在 Region r=="US",均纳入结果
# → 返回 ALL Users(只要至少存在一个 region 为 "US" 的 Region 实例)
```

由于 match 投影到 `EntityCls snapshot` 后丢失了所有非 EntityCls port 的 bindings,
**cartesian product 维度对 user invisibly 隐藏**。这是 silent failure mode,
比 evaluate(返回 EvaluateRow 含全部 port bindings,user 可视觉检测)更危险。

#### 5.4.2 强制约束(Match Runtime Invariant)

Match runtime 在执行 pattern matching 之前,**必须**验证 template 的
**effective body**(`template.where atoms` ∪ F-expression synthetic atoms)
形成 connected pattern:

> Projected EntityCls 的 port Var 与每个 constrained port 的 port Var,
> 必须**在同一 connected component** 内。

若不在,raise:

```text
SDKStoreError: ports {'user', 'region'} are not transitively connected
through template body — match would produce cross-product results.
Add a body atom linking these ports (e.g., User(u).region == r), or
use RuleExpr.join_by_ports to express the join explicitly.
```

#### 5.4.3 算法

```
1. 收集 effective body atoms:
   atoms = template.where atoms ∪ synthetic atoms from F-expression kwargs

   synthetic atoms from kwargs:
   - literal kwarg `region="US"`        → CmpAtom(r_var, Const("US"))
   - F-expression `region=User.tag`     → CmpAtom(r_var, FieldAccess(u_var, "tag"))

2. 构造 Var-graph:
   - nodes = 所有出现在 atoms 中的 Vars
   - edges = 同一 atom 内的 Var 两两相连
   - 注意:Const / FieldAccess 等非 Var term 不创造 edge

3. Connected components(union-find / DFS):
   将所有 Vars 划分为若干 component

4. Verify:
   - projected_var = EntityCls 投影的 port Var
   - constrained_vars = 所有 kwarg-constrained port 的 Vars
   - 必须 ∀ v ∈ {projected_var} ∪ constrained_vars,v 与 projected_var 在同一 component

5. 失败 → raise SDKStoreError;成功 → 继续 pattern matching
```

#### 5.4.4 Edge Cases

| Case | Connectivity check 结果 |
|---|---|
| Single Rule,body 紧密 connected,所有 port 在同一 component | ✓ pass |
| Single Rule,body 有 disconnected island(本节示例)| ✗ raise |
| RuleExpr 通过 `.join_by_ports("region")` 连接 | ✓ pass(join 创 cross-occurrence edge) |
| RuleExpr 通过 `.join(constraint)` 连接 | ✓ pass(constraint 创 edge) |
| RuleExpr `R1 & R2` 无 join,无 shared port | RuleExpr 层 reject 在前(ambiguous port reject 或类似);match 不到此步 |
| Literal kwarg `region="US"` | Synthetic atom 仅涉及 `r_var` 自身,**不**新增 Var-graph edge;不能"救"原本 disconnected 的 body |
| F-expression kwarg `region=User.tag` | Synthetic atom 涉及 `r_var` 与 `u_var`,**新增** edge;可"救"某些 disconnected case |

#### 5.4.5 与 evaluate 的差异(deliberate)

`fg.eval.evaluate(...)` 当前**不强制** pattern connectivity check。在
disconnected body 下,evaluate 同样会产生 cartesian product,但:

- Evaluate 返回 `EvaluateResult` / `EvaluateRow`,含所有 port bindings
- User 可以视觉检查每行,识别 cartesian 配对
- Silent failure 风险**显著低于** match 的 flat snapshot 投影

v0.2 仅 match 强制 connectivity check 是 deliberate decision:
- Match 是新 API,initial 严格门槛低成本
- Evaluate 已 ship,加 invariant 需 backward-compat 评估
- Match flat 投影让 silent cartesian 后果更严重 → 需要更早 fence

Evaluate 同步加 check 留 future cycle 评估(parent §6 task split 期间或更晚)。

## 6. Output Shape

### 6.1 返回 type

```python
return type: tuple[EntityCls snapshot, ...]
```

- 永远 `tuple`(不可变,materialized)
- Items 是 EntityCls 的 entity snapshot(`fg.read.get(EntityCls, ...)` 同 type)
- **Distinct**(template body 允许多 row 绑定同一 User → 输出去重)
- 直接 iterable / indexable / `len(...)` / `[:n]` slice / `bool(...)` empty check

### 6.2 与 `read.find` shape 对齐

```python
# find:简单字段过滤
us_users_a = fg.read.find(User, region="US")

# match:同 EntityCls,同输出 shape,template 表达更复杂 pattern
us_users_b = fg.read.match(User, user_in_region, region="US")

assert type(us_users_a) == type(us_users_b)  # 同 shape
```

`find` = direct field filter(无 join);`match` = rule-pattern filter(可表达 join、跨 entity)。**最终都返回 `tuple[EntityCls snapshot, ...]`**。

### 6.3 无 wrapper DTO

v0.2 显式**不**引入:

- `MatchResult` / `MatchView` / `MatchRow` / `ProjectedMatchView` 等 wrapper
- `.first()` / `.one()` / `.all()` / `.count()` chain 方法
- `.where(...)` / `.limit(n)` / `.select(...)` chain 方法

返回 `tuple` 自带 Python 原生操作:

| 用户意图 | 操作 |
|---|---|
| 第一个 | `result[0] if result else None` |
| 全部 | `result`(本身就是 tuple) |
| 数量 | `len(result)` |
| 唯一 | `assert len(result) == 1; user = result[0]` |
| 截前 N | `result[:n]` |
| 存在 | `bool(result)` 或 `if result:` |

## 7. Constraint Composition

### 7.1 Kwargs 接受两种 value 类型

```python
fg.read.match(User, template, region="US",            tag=User.region)
#                              ^^^^^^^^^^^^           ^^^^^^^^^^^^^^^^
#                              literal value          own-class Field descriptor (F-expression)
```

| Kwarg RHS 类型 | 语义 | Example |
|---|---|---|
| **Literal**(int/str/float/bool/idref token/None) | port 值 = literal | `region="US"` |
| **EntityCls 自身 `Field` descriptor** | port 值 = matched entity 该 field 的值 | `region=User.region` |
| 其他 EntityCls 的 Field(e.g. `Order.region` 在 `match(User, ...)`) | **raise** | 指引用户走 `RuleExpr.join_by_ports` |
| Var / Atom / Rule 等 SDK 内部对象 | **raise** | "kwargs accept only literal or own-class Field descriptor" |

### 7.2 Literal kwargs 语义

```python
fg.read.match(User, user_in_region, region="US")
```

合成 atom:`port_var("region") == Const("US")`

- 等价 SQL `WHERE region = 'US'`
- 与 `read.find(User, region="US")` 同语义

### 7.3 Own-class Field kwargs 语义(F-expression equivalent)

```python
fg.read.match(User, user_tagged, region=User.tag)
```

合成 atom:`port_var("region") == FieldAccess(matched_user_var, "tag")`

- 等价 SQL `WHERE region = tag`(同 entity 跨字段比较)
- Django ORM `F('tag')` equivalent
- 实用 use case:port name ≠ entity field name 时,显式 bind 到 entity 的另一字段

### 7.4 跨 entity Field 拒绝

```python
# 不支持:用 RuleExpr 表达
fg.read.match(User, template, region=Order.region)
# → SDKStoreError: "cross-entity field constraints must use RuleExpr.join_by_ports / .join, not kwargs"

# 正确方式:
expr = (u_ & o_).join_by_ports("region")
fg.read.match(User, expr, region="US")
```

理由:跨 entity field 等值 = implicit join。Join 应通过 `RuleExpr` 显式表达,不混入 kwargs。

### 7.5 Port name 验证

```python
fg.read.match(User, template, foo="bar")
# → SDKStoreError: "port 'foo' not declared by template (ports: ['user', 'region'])"
```

Kwargs 必须命名 template 已声明的 port。

### 7.6 Implementation Mechanism — Synthetic Constraint Composition

**Rule 数据完全不可变**。Kwargs 在 match runtime **合成额外约束 atoms**,与 template body 通过 RuleExpr-style AND **组合在一起**:

```
template body atoms ∧ synthetic kwarg atoms = match constraint set
                                              ↓
                                              pattern matcher (no inference engine)
                                              ↓
                                              row bindings
                                              ↓
                                              distinct EntityCls snapshots (via projection port)
```

性质:

- ✓ `Rule` 对象 immutable;digest invariant 保持
- ✓ 无 inference engine 介入;match 是 pure constraint solving
- ✓ 复用 `RuleExpr` 已有 `&` composition idiom
- ✓ Body 已含同一约束时,合成约束 idempotent(无副作用)

### 7.7 单 call,无 chain 累积

所有约束**一次性**传入,无 `.where(...)` 累积:

```python
# v0.2:single call
fg.read.match(User, template, region="US", active=True)

# 不支持:chain
fg.read.match(User, template).where(region="US").where(active=True)
```

理由:`read` namespace 是 single-call(对齐 `find` / `get` / `ref`)。Chain 累积 pattern 是 `assertions` namespace 的专属(`.field(...).active.where(...)`)。

## 8. View Scope

Match 遵循 T11.1 attach-time view scoping:

```python
fg = FactGraph.attach(db, schema_classes=[User], view=view)
us_users = fg.read.match(User, user_in_region, region="US")
# 匹配限制在 view 的 asrt_id universe 内
```

Method-level `view=` 不支持(与 T11.1 / Q5 一致):

```python
fg.read.match(User, template, view=view)
# → SDKStoreError: "method-level view= not supported; use FactGraph.attach(db, view=view) instead"
```

`view` 不是 port name — 即使 template 没有 `view` port,该 kwarg 也作为 reserved name 触发 attach-only hint。

## 9. Witness / Assertion Boundary

v0.2 match 返回 entity snapshot,**不暴露 witness assertion ids**。

Deferred 到 future cycle:

```python
fg.read.match(...).as_assertions()    # → witness asrt_ids
fg.read.match(...).witnesses()        # → 同上
fg.read.match(...).to_view()          # → 用 witnesses 构造 Database view
```

理由:
- Witness rows 需要 assertion-id 语义
- Assertion witnesses 可能成为 EvidenceGraph / Explanation 的输入
- 跨 parent §9 RuleExpr × evidence joins 与 T6/T7 evidence cycle 边界

v0.2 用户若需 assertion record,继续走 `fg.assertions.*` 直接 API。

## 10. Relationship to `fg.eval.run`

本设计锁定 replacement direction:

```python
# legacy
result = fg.eval.run(query_value)

# v0.2 替代:
fg.read.match(EntityCls, rule_or_expr, **constraints)
```

**不**删除 `fg.eval.run`。Deletion 留 future hard-cut,需:

1. `fg.read.match(...)` 运行时实现 land
2. docs migrate query/run examples → match
3. compatibility / migration notes reviewed
4. release policy 显式 authorize

## 11. Relationship to `facade.py`

T11.2.5 发现 dirty `facade.py` 改动(property-style assertion access + `AssertionRecordSet.__call__` compatibility)。

本 match 设计**不**返回 `AssertionRecordSet`,因此**不依赖** facade.py 改动:

- `facade.py` 可作为独立 assertion ergonomics slice land(`T11.2.6`),或 user stash/revert
- Match design 不再绑定 facade.py 决策

## 12. Deferred Items

| Item | Deferred to |
|---|---|
| Runtime implementation of `fg.read.match(...)` | Future implementation blueprint |
| Cross-entity tuple return(`match((User, Order), expr)`) | Future or evaluate-route |
| Legacy `Query` adapter path | Future compatibility decision |
| Query persistence(`fg.queries.save/load/list`) | Lifecycle / asset cycle |
| Witness assertion ids(`.as_assertions()` / `.witnesses()` / `.to_view()`) | Evidence / witness design |
| Method-level `view=` | v2 only if user demand appears |
| Snapshot-at-tx matching(`at=` / `as_of`) | Database snapshot cycle |
| Streaming / lazy iterator | Future performance cycle |
| Pagination(`offset=` / `cursor=`) | Future API expansion |
| Cross-entity Field kwargs(`Order.region` in `match(User, ...)`) | 与 RuleExpr.join 重叠,留 RuleExpr layer |
| Aggregate match(`.count_only()` / `.exists()`) | Future optimization |
| RuleExpr × evidence joins | Parent §9 / evidence cycle |
| Service / OpenAPI match endpoint | Future service design |

## 13. Commitments

| ID | Commitment |
|---|---|
| M1 | Public namespace target is `fg.read.match(EntityCls, template, **kwargs)`. |
| M2 | EntityCls is positional, required, must be `Entity` subclass. |
| M3 | EntityCls 扮演 match 的 "head" 角色 — 投影目标 entity 类。 |
| M4 | Template 必须恰好一个 entity_ref port 匹配 EntityCls(unique projection)。 |
| M5 | v0.2 templates are application `Rule` and `RuleExpr`(no bare list/tuple)。 |
| M6 | Legacy `Query` is compatibility/deferred, not the new primary template。 |
| M7 | `Rule.head` 在 match 中不参与;EntityCls 替代该角色。 |
| M8 | Match is **pattern matching**, not inference. No inference engine involvement。 |
| M9 | Return shape is `tuple[EntityCls snapshot, ...]`, distinct, materialized。 |
| M10 | No wrapper DTO(no `MatchResult` / `MatchView` / `MatchRow`)。 |
| M11 | No chain methods(`.where` / `.limit` / `.select` / `.first` / `.one` / `.all` / `.count`)— `read` namespace 是 single-call。 |
| M12 | Kwargs 接受 literal 或 own-class Field descriptor;其他 raise。 |
| M13 | Own-class Field kwarg = F-expression equivalent(同 entity 跨字段约束)。 |
| M14 | Cross-entity Field kwarg → raise,指引 RuleExpr.join_by_ports / .join。 |
| M15 | Implementation mechanism: synthetic constraint atoms composed with template body via RuleExpr-style AND at match runtime;Rule data immutable。 |
| M16 | Match follows attach-time view scope; method-level `view=` rejected。 |
| M17 | Witness/assertion-returning match is deferred(v0.2 only snapshots)。 |
| M18 | Cross-entity tuple return(`match((User, Order), expr)`)is v0.2 non-goal。 |
| M19 | `fg.eval.run` deletion is **not** part of T11.2.7;replacement direction locked。 |
| M20 | Dirty `facade.py` assertion ergonomics are **independent** of this match design。 |
| M21 | Match runtime enforces **pattern connectivity**: projected EntityCls port Var and all kwarg-constrained port Vars must be in the same connected component of effective body atoms(template body ∪ F-expression synthetic atoms)。Disconnected templates raise `SDKStoreError` before pattern matching runs。这是 v0.2 deliberate safety invariant,unique to match(evaluate 同步 check 留 future cycle)。 |
