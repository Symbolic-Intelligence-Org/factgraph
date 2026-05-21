# Rule Expression × Proof Attempt — Integrated Design Note

- Status: working / future blueprint input
- Authority: non-authoritative reference note; not current implementation truth
- Created: 2026-05-15
- Intended Use: future redesign input for Rule / RuleExpr / head / evaluate / prove / evidence
- Scope: 整合 "branch-first rule expression" 与 "engine proof attempt / why-not evidence" 两条设计线索为一份自包含设计文档
- Current Truth Note (2026-05-22): this note remains future-design input.
  Current user-facing behavior after Slice 7C is documented in
  `docs/official/kernel/quickstart/rules-and-inferences.md`,
  `docs/official/kernel/quickstart/persistence.md`, and
  `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`. In particular,
  filesystem registry adapters and saved rule/inference handles are removed;
  runtime examples using `RuleRegistry` / `registry=None` refer to in-memory
  rule composition, not filesystem registry persistence.
- Related Current Docs:
  - `docs/references/working/design-points/rule-query-inference-head-semantics.zh.md`
  - `docs/references/working/design-points/query-view-and-inference-handles.zh.md`
  - `docs/references/working/design-points/evidence-tree-rainbird-style-v1.zh.md`(2026-05-18 创建;持有 Phase 2 evidence 详细设计;原 §7 完整迁出)
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`(view 4-layer 子系统)
  - `docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md`

## 目录

```text
§1   摘要                                          [TBD,待 §3-§12 收敛后回头补]
§2   词汇表(锁死)                                  [TBD,同上]
§3   Rule:Branch-first atomic condition           [落地]
§4   RuleExpr:Rule 的组合表达                       [§4.1-§4.11 落地]
§5   Head + Evaluate / Explain API(head 是 Rule)   [落地;why_not + what_if + ports rename 等列 §5.12 deferred]
§6   三任务划分:match / evaluate / prove            [pending;view scope 参数简提,详锁见 arch doc §7.1]
§7   Evidence Tree(详细设计已迁出 — 独立文档)        [§7.1-§7.5 stub 落地;详 evidence-tree-rainbird-style-v1.zh.md]
§8   引擎能力对照与 lower 策略                       [Phase B-1 落定 2026-05-18,C94-C96 + §8.7/§8.8 lowering 子节 (Arith/AggregateExpr)]
§9   RuleExpr × Evidence 形状对齐(joins / alias)    [pending]
§10  Atom Language 闭合                              [Phase B-1 落定 2026-05-18,C97 + §10.6 ArithExpr/AggregateExpr expression forms (C98-C105)]
§11  ProofAttempt 数据模型                           [pending]
§12  显式 deferred 与下一步                          [pending]
```

---

## 3. Rule:Branch-first atomic condition

### 3.1 三句话设计承诺

1. **Rule 是最小条件单元** — 推理 / 解释 / 证据的最小可单独评估的对象就是一条 Rule,不再下钻
2. **Rule 内部仅表达 AND** — 多个 atom 的合取;OR 必须在 RuleExpr 层表达
3. **Rule 不携带 head / projection / claim** — 这些是 runtime 任务,在 RuleExpr 之上的运行入口给入

### 3.2 "Branch first" 的含义 — 哲学名,不是对象名

"Branch first" 是**设计哲学**的代号:
- 推理路径中的 alternative path(传统术语 branch)是**最小可解释单元**
- 把这个"最小路径"提升为用户一等公民,而不是让用户面对更大的 expression / inference
- 这是从 Rainbird "Why?" UX、ASP justification、Souffle proof-tree leaf、商业 KG(RDFox / Stardog / Ontotext)的 explanation surface 反推到的同一结论:用户问"为什么"时,系统要能指到一个 Rule + 它的 atoms

但 **user-facing 对象叫 `Rule`,不叫 `Branch`**(命名理由见 §3.8;`branch` 词的迁移路径见 §3.9)。

### 3.3 Rule 的最小形态

```python
with vars("u") as (u,):
    active_user = Rule(
        id="active_user",
        version="v1",
        desc="the user %user is active",
        where=[
            User(u).status == "active",    # unified binary fact:实体存在 + 字段约束
        ],
        ports={"user": u},
    )
```

**字段定义**:

| 字段 | 类型 | 必需 | 用途 |
|---|---|---|---|
| `id` | `str` | ✓ | 稳定 authoring identity,跨 session 不变,evidence anchor |
| `version` | `str \| None` | ✗ | free-form 版本(`"v1"` / `"1.0.0"` 等),不强制 semver / monotonic |
| `desc` | `str \| None` | ✗ | 自然语言模板,支持 `%port_name` 插值 |
| `where` | `list[Atom]` | ✓ | AND-only atom list;atom 形态详见 §10 |
| `ports` | `dict[str, Var]` | ✓ | 显式声明的对外接口 |

**禁止字段(验证器会拒绝)**:
- 无 `head` / `select` / `projection` — 进 RuleExpr 之上的运行时入口(§6)
- 无 `body` 字段名 — 用 `where`,与 SQL/Datalog 直觉一致

### 3.4 AND-only 强约束:不允许 Rule 内 OR / 不允许 expression-level NOT

一条 Rule 内部只表达合取:

```text
atom_1 AND atom_2 AND ... AND atom_n
```

被拒绝的写法:

```python
# REJECTED — Rule 不允许内嵌 OR
Rule(
    id="bad",
    where=[
        Or(User(u), Admin(u)),         # OR 不在 Rule 内部
        User(u).status == "active",
    ],
)
```

**承诺理由**:
- 若允许 Rule 内 OR,evidence 必须下钻到 Rule 内部子结构,违反"Rule 是最小解释单元"
- OR 在 RuleExpr.any(...) / `|` 运算符 层表达(§4)
- 简化 Phase 2 atom interpreter:平坦遍历,无 OR 嵌套

**Expression-level NOT 也不支持**:
- `~rule` / `not_(rule)` 在表达式层不实现
- 用户需要的 negation 通过 **atom-level** 实现(例如 `User(u).status != "banned"`,详见 §10)
- 这是 §4 RuleExpr 表达式层的承诺;§4 还会锁定其他 RuleExpr 防误用机制(`__bool__` raise / 文档警告)

### 3.5 Atom 的最小形态(unified binary fact 形态,v1 唯一 canonical)

> **v1 语法准则**:Rule body / head 内的每个 atom 形如 `EntityType(var-or-Ellipsis).field <op> value-or-Var-or-EntityRef`。`var.field` 裸访问、两行式 `EntityType(var), var.field == ...`、`Pred(...)` 均在 v1 **直接禁用,无 transition**。

允许:
```python
User(u)                            # 纯存在(无字段约束);u 可被其他原子引用
User(u).user_id == "u-2"           # 实体存在 + identity 等值约束
User(u).status == "active"         # 实体存在 + field 等值约束(typed by SemanticsProfile)
User(u).score > 0.5                # 实体存在 + field 比较(typed)
User(...).name == "alice"          # 匿名 binding(每个 `...` 独立 anonymous Var)
LivesIn(li).user == User(u)        # 跨 entity field 引用(RHS entity ref 隐式 ExistsAtom)
LivesIn(li).country == country     # field 与 Var(命名)比较
LivesIn(li).user == "u-2"          # field 直接比较字面值
```

禁止(v1 直接移除,无 transition):
```python
u.field == value                   # ✗ 裸 AttrRef 比较;LHS 必须是 EntityType(var).field
User(u), u.field == ...            # ✗ 两行分离形态;统一为 unified
Pred("user:status", u, "active")   # ✗ raw predicate atom;通过 EntityType(var).field 访问
lambda u: u.score * 2 > 1          # ✗ 任意 Python expression
custom_python_check(u)             # ✗ 未注册的自定义函数
some_global_var > 0                # ✗ 副作用 / 不可纯求值
other_rule(u)                      # ✗ 引用其他 Rule 作为 atom(立场 A 锁定,见 §3.6)
```

**Anonymous `...` 规则**(F1 / F2 锁定):
- `...` 是 Python 内置 Ellipsis,**无需 import**,直接使用
- 每个 `User(...)` 调用产生**全新** anonymous Var(同一表达式内多个 `...` 互不相同)
- Anonymous Var **不可声明为 port**(无名无法对外暴露)

**Lowering 机制**(F6 锁定):
- 复用现有 `ExistsAtom` / `AttrRef` / `CompareExpr` / `LogicVar` primitives
- 构造期 normalize:`User(u).field == value` 平展为 `[ExistsAtom(User, u), CompareExpr(AttrRef(u, "field"), "==", value)]`
- 构造期 dedup:对同 `(entity_type, var)` 的 ExistsAtom 去重,保留单份
- 新增 lowering case:CompareExpr 的 RHS 为 ExistsAtom 时,提取 Var 并把 ExistsAtom 加入 atoms 列表
- 预计新增 ~50-75 行,不重写 lowering 主干

**完整闭合在 §10 atom language closure(其余受限项细节);本节锁定 unified canonical 边界**。

### 3.6 ports:Rule 的对外接口 + Rule 间的唯一交互途径

`ports` 显式声明 Rule 暴露给外部的变量绑定:

```python
Rule(
    id="user_in_region",
    where=[User(u).region == region],
    ports={"user": u, "region": region},
)
```

**三类变量分工**:

| 类别 | 定义 | 外部可见性 |
|---|---|---|
| free variable | Rule.where 内出现的所有变量 | 内部概念 |
| port | `ports={...}` 中显式声明的变量 | ✓ 可被外部 bind/join/project |
| non-port free var | free var 中未列入 ports 的 | ✗ 内部 existential witness,不可 join |

**承诺**:
- **不自动收集 ports**;必须显式声明 — 自动 free-var 收集无法回答"哪些是外部接口"
- **ports ≠ head**;ports 说"可暴露什么",不说"必须返回什么"
- **port 类型自动从 atom 推断**(例如 `User(u)` 出现 → `u` 是 User type)
- **Rule 之间唯一的交互途径是 RuleExpr 组合 + port join**:
  - Rule.where 不允许引用其他 Rule 作为 atom(立场 A 锁定)
  - 同名 port 跨 Rule **不自动 join**;join 必须在 RuleExpr 层显式声明
  - 具体 join 语义在 **§4 RuleExpr** 锁定,预告如下(均预定为 §4 承诺,本节先存档):
    1. 同名 port **不自动 join**,默认为 independent existential variables(不 join = 不要求两个 Rule 的 "user" 指同一对象)
    2. join 用 occurrence alias + 显式约束:`a = rule_a.as_("a")` / `b = rule_b.as_("b")` / `(a & b).join(a.user == b.person)`
    3. `.join(...)` **只能附着在 AND group 上**;OR group / 单 Rule 上调用 → 构造期 raise `RuleExprError`
    4. `.join(...)` constraint 必须 **AND-spine reachable**(平展外层 AND 后,只可引用直接 Rule 子节点;不可引用 OR group 内部 Rule);违反时构造期 raise `RuleExprError`。简记:`(R1 & R2 & R3).join(...)` 可引用 R1/R2/R3;`(R1 & (R2|R3)).join(...)` **仅可引用 R1**(R2/R3 在 OR 内,不可引用)
    5. Path-dependent join 由用户显式 **distribute** 到各 OR 分支(例:`(R1 & R2).join(R1.user==R2.user) | (R1 & R3).join(R1.user==R3.user)`),不允许跨 OR 隐式传播
    6. 同一 Rule 在表达式中多次出现时**必须 `.as_(...)` 起 alias** 区分(默认 alias = `rule.id`,单次使用可省略)
    7. join 绑定到 **occurrence**,不绑定到 template(同一 Rule 的不同 occurrence 可有不同 join 约束)
    8. 未 join 的同名 port 由 `fg.rules.inspect(expr)` 暴露为 `unjoined_same_name_ports`(不 raise,只作 discoverability hint)
    9. evidence tree 同时显示 template id 与 occurrence alias

**Every-Proof-Path Reach Rule(AND-spine reachable 的等价直觉表达)**:

> `.join(...)` constraint 可以引用 Rule X,当且仅当 X 出现在该 RuleExpr 的"每一条成功证明路径"上。机械判定方式:平展外层 AND,得到 direct-AND-children 列表;列表中 Rule 节点可被引用,OR group 不可被引用。

**`.join(...)` 适用性举例**:

| 表达式 | `.join(...)` 可引用的 Rule |
|---|---|
| `(R1 & R2).join(...)` | R1, R2 |
| `(R1 & R2 & R3).join(...)` | R1, R2, R3 |
| `((R1 & R2) & R3).join(...)` | R1, R2, R3(associative flatten) |
| `(R1 & (R2 \| R3)).join(...)` | **仅 R1**(R2 / R3 在 OR 内,不可引用) |
| `(R1 & R2 & (R3 \| R4)).join(...)` | R1, R2(R3 / R4 在 OR 内) |
| `((R1 & R2) \| R3).join(...)` | **无**;外层是 OR group → `.join` 整体非法 |
| `(R1 \| R2).join(...)` | **无**;外层是 OR group → `.join` 整体非法 |
| `R1.join(...)` | **无**;单 Rule → `.join` 整体非法(自约束写进 `R1.where`) |

**Path-dependent join 必须显式 distribute**:

```python
# ✗ 非法:join 引用 OR 内部 R2
(R1 & (R2 | R3)).join(R1.user == R2.user)
# RuleExprError: R2 不是 every-proof-path 的成员

# ✓ 合法的等价写法 — distribute 到各 OR 分支
expr = (R1 & R2).join(R1.user == R2.user) | (R1 & R3).join(R1.user == R3.user)
```

distribute 的代价是 R1 在表达式里写两次,但 evidence 形状清晰("path A: R1+R2 satisfied with R1.user==R2.user" / "path B: R1+R3 satisfied with R1.user==R3.user")。这是**故意的代价** — 让 path-dependent semantics 显式化,而不是藏在 join 里。

**立场 A 锁定的理由**(立场 B 即"Rule 引用 Rule 作为 atom"被显式排除):
- 立场 B 会把 RuleExpr 部分语义偷渡进 Rule.where,造成两套表达式语言并存
- 立场 B 下 Rule 不再 atomic — evidence tree 必须下钻到被引 Rule 内部
- 立场 B 引入 cyclic Rule 依赖风险(A → B → A)
- 用户若需要"Rule X 的成立作为 Rule Y 的前置",**显式使用 RuleExpr 组合**

### 3.7 desc 渲染语义

#### 3.7.1 插值规则

- 模板用 `%port_name` 引用 port
- 引用未声明的 port → 构造时 reject
- render 时未绑定 → 输出 `<port_name>` 字面占位
- **v1 不支持** desc 引用 non-port 变量;若用户需要让变量出现在 desc,必须将其声明为 port(承担"暴露给 cross-rule join"的代价)
- **v2 deferred trigger**:当出现"renderable 但不可 join"的需求时,引入 `private_vars` 之类的机制

示例:

```python
Rule(
    id="active_user_in_region",
    desc="user %user is active in region %region",
    where=[User(u).status == "active", User(u).region == r],
    ports={"user": u, "region": r},
)

# 未绑定 render
"user <user> is active in region <region>"

# 已绑定 (user=u-2, region=US) render
"user u-2 is active in region US"
```

#### 3.7.2 desc 在 evidence 中的角色

desc 是用户面 narrative 的**模板源**:
- Phase 2 evidence 渲染时,desc 提供 rule-level 自然语言
- atom-level 由 atom 结构自动生成默认 narrative(`User(u)` → "u is a User";`User(u).status == "active"` → "u's status is active")
- **v1 不引入 atom-level desc**(已 deferred 至 v2)

### 3.8 命名:为什么是 `Rule` 而不是 `Branch`

**词汇分工(本文档锁死)**:

| 词 | 在本设计中的位置 |
|---|---|
| `Rule` | user-facing 一等对象,AND-only 条件块,本设计的主角 |
| `branch` / `path` | **内部 / evidence rendering 词汇**;不作为 SDK public 对象出现 |

**为什么不用 `Branch` 作 user 对象**:
- LP / KR 圈通用词是 `Rule`,用户直觉接近
- `Branch` 易被误读为控制流的"分支",而本设计的 Rule 是条件块,不是流程节点
- `Branch` 在系统内已有狭义 incumbent 用法(Track 1 shipped 的 `Branch(id=...)`,见 §3.9),复用会语义冲撞

**为什么仍保留 `branch` 词**:
- evidence tree 渲染 OR alternatives 时,`branch` 是合适的描述词("path A failed, path B succeeded")
- engine native carrier(Souffle proof-tree alternatives、ProbLog SDD OR-node)用 `branch` 表述更自然

### 3.9 与现行 shipped `Branch(id=...)` 的迁移关系

**当前 shipped**(Track 1 @ `origin/master 03f76380`,2026-05-12):

```python
fg.rules.inspect(rule_id) -> RuleInspect
RuleInspect.branches: list[Branch]            # Branch(id=..., atoms=[...])
```

`Branch` 在现行系统中是 **Rule body 内 alternative path 的稳定 inspect 身份**。

**本设计承诺**:
- **不在本轮重命名**现行 `Branch` 类 — 避免 breaking 已 ship 的 inspect API
- **重新定位**:
  - 在新 user-facing 表达层(`Rule` / `RuleExpr`),`Branch` 不出现
  - 在 evidence rendering / 内部 inspect,保留 `branch` 词汇
- 当现行 `Rule(select, where, head)` 被本设计的 new Rule 替代时,`Branch(id=...)` 自然转为 evidence DTO 内部字段或彻底消失

**迁移路径**:留给后续 blueprint 锁,不在本文档锁。本文档只承诺:**未来 user-facing 不会有 `Branch` 类**。

### 3.10 与现行 `Rule(select, where, head)` 的差异

| 维度 | 现行 Rule | 新 Rule(本设计) |
|---|---|---|
| 是否携带结果形状 | 是(`select` + `head`) | **否**(运行时给入) |
| 内部 OR | 允许(通过多 branch) | **不允许** |
| 最小解释单元 | rule + branch | **rule 自身** |
| persistence | `fg.rules.save/load` 可持久化 | **v1 不持久化**(用户在 Python 层自己持有);未来由 SavedRule 提供 |
| 与 Inference 关系 | 紧耦合(Rule body 进 Inference body) | **解耦**(Inference 是运行时入口,接受 RuleExpr) |

**关键认知**:
- 现行"Rule" 在新设计下被拆成 **Rule(纯条件)** + **RuleExpr(组合)** + **运行时入口(evaluate / prove / match)** 三个独立对象
- 新 Rule 与现行 Rule **不是同一个对象** — 命名必须有方案避免冲突

**命名冲突解法**(三选一,留给后续 blueprint 锁,本文档不锁):
- A. 完全替换:现行 Rule 改名为 `LegacyRule`,过渡期后删除
- B. 命名空间隔离:`kernel.sdk.v2.Rule` 与 `kernel.sdk.Rule` 共存
- C. 渐进扩展:现行 Rule 增加 `mode="atomic"` 进入新设计语义

本文档只承诺:**新 user 看到 `Rule` 就是 atomic AND-only,不能看到 `select` / `head` 字段**。

### 3.11 Rule 不可变(immutable after construction)

锁定:
- 构造后**所有字段不可改**
- "修改"必须产生新 Rule:`new_rule = rule.with_version("v2")` 这类 builder 模式
- atom 顺序在构造时确定,作为 atom_id 的位置锚点
- atom 顺序**不影响 evaluation 结果**(AND 可交换),但**影响 evidence rendering 顺序与 atom_id 分配**

### 3.12 v1 ephemeral composition — 无 NamedRuleExpr / 无 SavedRule

锁定:
- v1 **不提供** `NamedRuleExpr` / `SavedRule`
- 复合表达式(`(R1 & R2) | R3` 运算符形式 或 `RuleExpr.any(RuleExpr.all(R1, R2), R3)` 工厂形式,两者等价,详锁 §4)由用户在 **Python 层自己持有**(模块级变量 / 配置文件 / 用户自己的代码)
- 单个 Rule 仍是 stable / durable(有 id + version);复合是 ephemeral

**这不会失专业性,有先例**:
- SQLAlchemy `Q` objects / Django `Q` objects / GraphQL queries — 都是"Python 变量持有表达式,持久化由用户负责"
- Datalog 系统的"持久化单元"也是 Rule,不是 expression-of-rules

**v2 deferred triggers**(显式埋点,本文档不锁):
- 当用户开始要求"跨进程共享复合表达式" → 引入 SavedRule
- 当用户开始要求"UI 构造复合表达式" → 引入序列化层

### 3.13 本节设计承诺清单(锁定)

> **编号说明**:C22 是历史 gap(早期 `join_by` 承诺整合至 C10 时编号未回收);C23-C35 在 §4.10 表;**C36-C44 已迁出本文档**(view 设计移交 `database-view-fg-layered-architecture.zh.md` §7.1.8);C45-C48 是后续锁定的 atom 语法承诺,补在本表末尾(章节划分使然)。本文档剩余 commitments 总计 38 项(C1-C21 + C23-C35 + C45-C48)。

| # | 承诺 |
|---|---|
| C1 | Rule 是 AND-only atomic condition |
| C2 | Rule 内部不允许 OR;expression-level 也不支持 NOT |
| C3 | Rule 无 head / select / projection 字段 |
| C4 | Rule 支持 5 字段:`id` / `version` / `desc` / `where` / `ports`;version 与 desc 可选 |
| C5 | desc 用 `%port_name` 插值;未声明 port → reject;未绑定 → 输出 `<port_name>` 字面占位 |
| C6 | v1 不支持 desc 引用 non-port 变量;v2 deferred |
| C7 | ports 必须显式声明,不自动收集 |
| C8 | port 类型自动从 atom 推断 |
| C9 | Rule 之间不可通过 atom 引用交互(立场 A);唯一交互途径是 RuleExpr 组合 + port join(详锁 §4) |
| C10 | 同名 port 跨 Rule 不自动 join;`.join(...)` 仅 AND group 可调用且 constraint 必须 AND-spine reachable;具体 join 语义在 §4 锁定,§3.6 已预存档 |
| C11 | atom 形态:unified `EntityType(var).field == value` 为唯一 canonical(详见 §3.5);其余形态详锁 §10 |
| C12 | `Rule` 为 user-facing 名;`branch` 退为 evidence rendering 词汇 |
| C13 | 不重命名现行 shipped `Branch(id=...)` 类,只重新定位 |
| C14 | 新 Rule 与现行 Rule 不共名;命名冲突方案 deferred(blueprint 锁) |
| C15 | Phase 1(候选生成,engine sparse)+ Phase 2(按需 evidence,FactGraph 构造)两阶段架构(详见 §7.1 / §7.2)|
| C16 | Rule.atoms / atom_id / eval_atom / render_desc 是 Phase 2 的最小 introspection 表面(详见 §7.3 / §7.4)|
| C17 | Rule immutable after construction |
| C18 | atom 顺序:AND 可交换不影响语义;atom_id 与 evidence 顺序按位置 |
| C19 | atom_id 格式 `<rule_id>:atom_<index>` |
| C20 | v1 ephemeral composition;无 NamedRuleExpr / SavedRule |
| C21 | v1 不引入 atom-level desc(deferred) |
| C45 | `...`(Python Ellipsis)作 anonymous Var sentinel;每次出现独立生成 anonymous Var;anonymous Var 不可声明为 port |
| C46 | 两行式 `User(u), u.field == ...` 与 raw `Pred(..)` 在 v1 **直接移除**(alpha,无 transition) |
| C47 | head 与 body 通过 **外部 port name** 接口对齐(详锁 §5.3 / C54);Rule 内部 Var 名属于实现细节,不参与跨 Rule 对齐(封装原则) |
| C48 | Multi-head v1b:仅允许"同 entity 多 field" 形态;跨 entity multi-head 留 v2 |

### 3.14 本节显式 deferred 项

| 项目 | 触发条件(blueprint 入口) |
|---|---|
| desc `private_vars`(renderable 但不可 join 的内部变量)| 当出现明确"私有 desc 变量"需求 |
| atom-level desc | 当 rule-level desc + 自动 atom narrative 不够用 |
| SavedRule / NamedRuleExpr | 当跨进程共享 / UI 构造复合表达式需求出现 |
| Rule 命名冲突方案(A/B/C) | new Rule 引入实际 API 时 |
| 现行 `Branch(id=...)` 类的最终归宿 | new Rule 替代现行 Rule 完成时 |
| atom_id 是否升级到 content-hash(v1 是 positional)| 当 Rule.atoms 顺序稳定性出问题时 |
| 跨 entity multi-head | 当出现"一个 entity 推一组 fact + 另一 entity 也推 fact"的实际诉求(v1b 只支持同 entity 多 field) |
| `join_by(...)` sugar | 当用户社区反复出现 chain join 便利性诉求 |

---

## 4. RuleExpr:Rule 的组合表达

> **本节状态**:§4.1 - §4.11 落定。Batch 2/3 重构期间,原 §4.2 View / §4.3 Phase 1/2 / §4.4 introspection 暂存于本文末 Appendix(A.1 / A.2 / A.3),后续分别迁移至独立架构 doc 和 §7 Evidence 章。
>
> **本章焦点**:RuleExpr 是 Rule 的组合表达式;§4.1 - §4.11 锁定 RuleExpr 形态、运算符、防误用、occurrence alias、join 实施细节、inspect 表面、不可变性等。
>
> **架构层 deferred**:更深的 "Database / View 版本管理 / FG runtime" 四层抽象讨论移交独立设计文档 `database-view-fg-layered-architecture.zh.md`,本文档不重叠该 scope。

### 4.1 设计立场

`RuleExpr` 是用户**组合多个 Rule 后**得到的对象,表达 AND / OR 合成结构;不包含 head / projection / claim — head 在运行时入口(evaluate / prove / match)给入。

单个 `Rule` 在所有接受 RuleExpr 的 API 位置可**直接传入**(隐式视为单元素 AND group),用户无需手工 wrap。

### 4.2 Form C:运算符 + 工厂方法等价

两种 API 形式都允许,**语义完全等价**:

```python
# 运算符形式(简洁,推荐日常使用)
expr_a = R1 & R2 | R3
expr_b = (R1 & R2).join(R1.user == R2.user) | R3

# 工厂方法形式(programmatic 构造时使用)
expr_c = RuleExpr.any(RuleExpr.all(R1, R2), R3)
expr_d = RuleExpr.any(
    RuleExpr.all(R1, R2).join(R1.user == R2.user),
    R3,
)

# expr_a 与 expr_c 结构等价;expr_b 与 expr_d 结构等价
```

**运算符优先级**(Python 标准):
- `&` 紧于 `|`(`R1 & R2 | R3` = `(R1 & R2) | R3`)
- 括号显式分组优先

**关联性(associative flattening)**:
- `R1 & R2 & R3` 平展为 3-元 AND group
- `R1 | R2 | R3` 平展为 3-元 OR group
- `(R1 & R2) & R3` ≡ `R1 & (R2 & R3)` ≡ `R1 & R2 & R3`

**禁止形态**:
- `~R1` / `not_(R1)` — expression-level NOT 不支持(C2 / §3.4 已锁;negation 在 atom-level)

### 4.3 Form Y:内部类型不暴露

User-facing API 表面:
- `Rule` — 一等对象,显式 import
- `RuleExpr` — **仅作为 namespace**,提供 `.all(...)` / `.any(...)` 工厂方法
- `vars(...)` / `Identity` / `Field` / 等 schema 元素

内部类型(用户**不直接 import 也不直接构造**):
- `_RuleExpr`(base)
- `_AndGroup`
- `_OrGroup`

用户通过运算符或工厂方法间接得到 RuleExpr 实例。

**理由**:
- 减少 user-facing API 表面
- 内部类型可重构(重命名 / 拆分 / 合并)而不破坏 user code

### 4.4 防误用:`__bool__` raise

RuleExpr / Rule 都**禁止隐式 bool 转换**:

```python
# ✗ 抛 ExplicitBoolError
if (R1 & R2):
    ...
bool(R1 & R2)
all([R1, R2])     # all() 内部用 bool

# ✓ 必须显式
result = fg.eval.explain(R1 & R2)
if result.proved:
    ...
```

**理由**:
- `&` / `|` 是表达式构造,**不是** boolean `and` / `or`
- numpy / pandas 等也采用同样策略(Series `__bool__` raises ambiguity)
- 显式拒绝可避免静默错误

**实现**:`_RuleExpr.__bool__` 直接 `raise ExplicitBoolError(...)`;`Rule.__bool__` 同样 raise。

### 4.5 occurrence alias `.as_(...)`

同一 Rule 在表达式里可能出现多次(self-join 等场景),需要稳定区分。**occurrence alias** 是表达式 local 的身份。

**默认 alias = `rule.id`**(单次使用时可省略 `.as_(...)`):

```python
# 单次使用,默认 alias = "active_user"
expr = active_user & user_in_region
expr.join(active_user.user == user_in_region.user)
```

**多次使用必须显式 alias**:

```python
same_org = Rule(id="user_in_org", ...)
src = same_org.as_("src")
dst = same_org.as_("dst")
expr = (src & dst).join(
    src.org == dst.org,
    src.user != dst.user,
)
```

**承诺**:
- alias 是表达式 local 的(不同 RuleExpr 中可重复使用同名)
- alias **不影响** `rule.id`(template identity 稳定不变)
- 同表达式内 alias 必须唯一,违反时构造期 raise `RuleExprError`
- 同 Rule 在表达式中出现 ≥ 2 次且未显式 alias → 构造期 raise(强制显式)

### 4.6 Join 实施(落地 §3.6 预存档 10 条)

§3.6 已预存档的 10 条 join 规则全部在 §4(本章 §4.6 为主)落定为**构造期强约束**:

| §3.6 规则 | §4 实施位置 |
|---|---|
| #1 同名 port 不自动 join | 构造期不插入隐式约束 |
| #2 显式约束 `.join(a.port == b.port)` | `_AndGroup.join(*constraints)` 方法 |
| #3 `.join(...)` 仅 AND group 可调用 | 仅 `_AndGroup` 有 `.join` 方法;`_OrGroup` / `Rule` 调用 → 构造期 raise `RuleExprError` |
| #4 constraint AND-spine reachable | 构造期 traverse AST 验证;违反 raise `RuleExprError` |
| #5 Path-dependent distribute | 用户责任;SDK 不自动 distribute;文档显式警告 |
| #6 重复 Rule 必须 `.as_(...)` alias | 构造期检测(§4.5) |
| #7 join 绑定 occurrence | `_AndGroup` 内部按 alias 存约束 |
| #8 未 join 同名 port → inspect 暴露 | `fg.rules.inspect(expr).unjoined_same_name_ports` |
| #9 evidence tree 显示 template + alias | evidence DTO 字段:`template_id` + `alias`(§7 / §11 详锁) |

### 4.7 inspect 表面

`fg.rules.inspect(expr)` 返回 `RuleExprInspect` — RuleExpr 的**只读 projection**,服务 authoring-time 的结构、语义、渲染三类需求。

**核心立场**:
- inspect 表面**保持紧凑**;rich 信息聚合在 `occurrences` 内的 `OccurrenceInspect` 对象上,不开多个平行 dict
- `render()` 是 **authoring narrative**(表达式的意思),不是 **proof narrative**(表达式被证明了)— 后者由 §7 evidence DTO 提供
- inspect 是 authoring AST 的 read-only projection,**不是** §7 Phase 2 evidence interpreter 的 execution source

#### 4.7.1 顶层字段(精简核心模型)

| 字段 / 方法 | 类型 | 用途 |
|---|---|---|
| `ast` | 嵌套结构 | RuleExpr 的 AST(AND / OR / Rule 节点) |
| `occurrences` | `list[OccurrenceInspect]` | rich occurrence 对象列表;承载 desc / ports / atoms |
| `joins` | `list[JoinConstraint]` | 所有显式 join 约束(按 AND group 分组) |
| `unjoined_same_name_ports` | `list[dict]` | 未 join 的同名 port hint(discoverability,非 error) |
| `render(bindings=None)` | method → `str` | 自然语言渲染(模板态 / 绑定态) |
| `render_compact()` | method → `str` | 紧凑符号态,适合 log / debug |

#### 4.7.2 OccurrenceInspect(rich object)

```python
OccurrenceInspect:
    template_id: str              # 引用的 rule.id
    alias: str                    # 表达式内 occurrence alias(默认 = template_id)
    desc_template: str | None     # 原始 desc 模板(带 %port 插值标记)
    ports: list[str]              # 该 occurrence 暴露的 port 名列表
    atoms: list[AtomDescriptor]   # rule body 内 atom 的逐项分解
```

#### 4.7.3 AtomDescriptor(机器可读 structured fields + 人可读 summary)

```python
AtomDescriptor:
    atom_id: str                  # 形如 "<rule_id>:atom_<index>"
    kind: str                     # "entity_existence" / "field_eq" / "field_compare" / ...
    # structured fields(按 kind 提供;机器消费走这层)
    subject: str | None           # entity var 名(对于 entity_existence / field_*)
    entity_type: str | None       # 实体类型名(对于 entity_existence / field_*)
    field: str | None             # 字段名(对于 field_*)
    op: str | None                # 比较运算符("eq" / "gt" / "lt" / "ne" / ...)
    value: Any                    # 字面值或 Var 引用(对于 field_*)
    # 人可读(显示用)
    summary: str                  # 例:"user.status == 'active'"
```

**承诺**:
- `summary` 仅用于显示;**机器消费**(audit / evidence)**走 structured fields,绝不解析 summary**
- §7 Phase 2 evidence interpreter 与 inspect **共享 `atom_id` 与 AtomDescriptor schema**(同一份 authoring AST 的不同 projection)— inspect 不是 evidence interpreter 的 execution source

#### 4.7.4 Convenience properties(从 occurrences 推导,非主数据模型)

| Property | 推导规则 |
|---|---|
| `templates` | `[occ.template_id for occ in occurrences]` 去重 |
| `port_visibility` | `{occ.alias: occ.ports for occ in occurrences}` |

只读;数据真源是 `occurrences`。

#### 4.7.5 渲染语义

- `render()` / `render_compact()` 是**纯函数**:不触碰 ledger、不做 evaluation,仅渲染 authoring structure
- desc 插值规则**完全沿用 §3.7.1 / C5**:`%port` 引用 port;未声明 port → reject;未绑定 → 输出 `<port>` 占位
- Composition 渲染规则:
  - AND → `(... AND ...)`
  - OR → `(... OR ...)`
  - join → `... WHERE <constraint(s)>`
- 单 Rule 时 = 该 Rule 的 desc 渲染;组合时 = 子表达式 desc + composition 标记
- **render 不允许引用 non-port 变量**(沿用 §3.7.1 v1 限制 / C6)

#### 4.7.6 示例

```python
expr = (active_user & user_in_region).join(
    active_user.user == user_in_region.user
)
inspect = fg.rules.inspect(expr)

# rich occurrence
inspect.occurrences[0]
# OccurrenceInspect(
#     template_id="active_user",
#     alias="active_user",
#     desc_template="the user %user is active",
#     ports=["user"],
#     atoms=[
#         AtomDescriptor(
#             atom_id="active_user:atom_0", kind="entity_existence",
#             subject="user", entity_type="User",
#             field=None, op=None, value=None,
#             summary="exists User user",
#         ),
#         AtomDescriptor(
#             atom_id="active_user:atom_1", kind="field_eq",
#             subject="user", entity_type="User", field="status",
#             op="eq", value="active",
#             summary="user.status == 'active'",
#         ),
#     ],
# )

# 自然语言渲染(模板态)
inspect.render()
# "(the user %user is active) AND (user %user lives in region %region) WHERE %user is the same"

# 自然语言渲染(绑定态)
inspect.render(bindings={"user": "u-2", "region": "US"})
# "(the user u-2 is active) AND (user u-2 lives in region US)"

# 紧凑符号态
inspect.render_compact()
# "active_user(user) ∧ user_in_region(user, region)  [join: user]"

# convenience
inspect.templates
# ["active_user", "user_in_region"]
inspect.joins
# [JoinConstraint("active_user.user == user_in_region.user")]
```

### 4.8 RuleExpr 不可变 + 结构等价

**不可变**:
- 构造后字段不可改
- `.join(...)` 返回**新 RuleExpr**(原表达式不变)
- `.as_(...)` 返回新 occurrence,不修改原 Rule

**结构等价**:
- 两个 RuleExpr 结构相同 → `expr_a == expr_b` 为 True
- AND / OR 子节点顺序**不影响等价**(AND / OR 都是 commutative)
- 用于缓存 / 去重 / inspect 比较
- `__hash__` 基于结构;**同进程稳定**;v1 不承诺跨进程稳定

### 4.9 RuleExpr 与单 Rule 的 API 边界

所有接受 `RuleExpr` 的 API 位置**都接受单个 `Rule`**:

```python
fg.read.match(R1)                               # 单 Rule
fg.read.match(R1 & R2)                          # RuleExpr
fg.read.match(RuleExpr.all(R1, R2))             # RuleExpr 等价形式
```

> **注**:本节示例仅展示"单 Rule 隐式作 1-元 AND group"的类型边界。运行时具体 `head` / `engine` / `view` / `semantics` 等参数,以及 evaluate / prove 因需 head shape 而不在本节展示,完整签名详锁 **§6 三任务划分**。

- 单个 Rule 隐式视为 1-元 AND group
- 用户无需手工 `RuleExpr.all(R1)` wrap
- 反向不成立:RuleExpr 不能传入只接受 `Rule` 的 API(如 `fg.rules.save(...)` v1 只接受单 Rule)

### 4.10 §4 设计承诺清单(锁定)

| # | 承诺 |
|---|---|
| C23 | Form C:运算符 `&` / `\|` + 工厂方法 `RuleExpr.all/any(...)` 都允许,语义等价 |
| C24 | 运算符优先级 Python 标准(`&` 紧于 `\|`);括号显式分组 |
| C25 | AND / OR 关联性平展(associative flattening) |
| C26 | Form Y:内部类型 `_RuleExpr / _AndGroup / _OrGroup` 不暴露;用户通过运算符 / 工厂方法间接构造 |
| C27 | `RuleExpr.__bool__` + `Rule.__bool__` 都 raise `ExplicitBoolError`;禁止隐式 bool 转换 |
| C28 | occurrence alias `.as_(...)`;默认 alias = `rule.id`;同 Rule 多次出现必须显式 alias |
| C29 | alias 表达式 local;同表达式内必须唯一;不影响 `rule.id` |
| C30 | §3.6 预存档 10 条 join 规则全部在 §4(§4.6 为主)落定为构造期强约束 |
| C31 | `.join(...)` constraint AND-spine reachable 构造期验证,违反 raise `RuleExprError` |
| C32 | `fg.rules.inspect(expr)` 返回 `RuleExprInspect`(精简核心:`ast` / `occurrences` / `joins` / `unjoined_same_name_ports` + `render()` / `render_compact()`);`templates` / `port_visibility` 是从 `occurrences` 推导的 convenience property,非主数据模型 |
| C33 | RuleExpr immutable;`.join(...)` / `.as_(...)` 返回新对象 |
| C34 | RuleExpr 结构等价(commutative AND/OR 不影响);`__eq__` + `__hash__` 同进程稳定;不承诺跨进程稳定 |
| C35 | 单 Rule 在接受 RuleExpr 的 API 位置隐式视为 1-元 AND group;反向不成立 |
| C49 | `OccurrenceInspect` 是 rich object,聚合 `template_id` / `alias` / `desc_template` / `ports` / `atoms`;`templates` / `port_visibility` 作为只读 convenience 从 occurrences 推导 |
| C50 | `AtomDescriptor` 同时提供 structured fields(机器消费:`kind` / `subject` / `entity_type` / `field` / `op` / `value`)+ `summary`(显示);§7 Phase 2 evidence interpreter 与 inspect **共享 `atom_id` + descriptor schema**(同一份 authoring AST 的不同 projection,**inspect 不作为 evidence 的 execution source**) |
| C51 | `inspect.render()` / `render_compact()` 是 **authoring narrative**(不是 proof narrative);纯函数,不触碰 ledger;desc 插值遵循 §3.7.1 / C5(`%port` + `<port>` 占位);不允许引用 non-port 变量(C6) |

### 4.11 §4 显式 deferred 项

| 项目 | 触发条件 |
|---|---|
| 跨进程 RuleExpr serialization | 当 SavedRule 引入时(对应 §3.12 deferred) |
| RuleExpr `__hash__` 跨进程稳定保证 | 当 hash 用于跨进程缓存键时 |
| `RuleExpr.diff(other)` 结构 diff API | 当 inspect / debug 需要时 |
| RuleExpr 用作 `set` / `dict` key | 跟随跨进程 `__hash__` 稳定承诺 |
| 自定义 `RuleExprError` 错误码 / 错误信息表 | 当用户错误经验需要标准化时 |

---

## 5. Head:port-centric 接口规约(head 是 Rule)

### 5.0 设计立场:Body / Head 对偶性

借用竹筏隐喻:**RuleExpr 是散乱的竹筏(条件网),head 是你选来提起整个竹筏的木板;选不同木板得到不同视角,但竹筏本身没变**。

形式上:
- Rule 的 `where` 与 head 的 `where` 在底层 IR 是**同一种 atom 集合**;差别仅在使用时机
- `where` 在 Rule authoring 时写好,锚定"条件域"
- head 在 query / evaluate / prove 时给入,锚定"切面 / 输出接口"
- **head 不是新类型,head 本身就是一个 Rule**

LP 圈对应概念(参考):Datalog magic sets transformation;Prolog mode declarations;CLP constraint sets。

### 5.1 head 是 first-class Rule

```python
# 形式 1:复用已有 Rule
result = fg.eval.evaluate(expr, head=existing_rule)

# 形式 2:inline 定义新 Rule
result = fg.eval.evaluate(
    expr,
    head=Rule(
        id="_my_query",
        where=[
            User(Var("u")).user_id == "u-2",
            Var("state") == "worker",
        ],
        ports={"user": Var("u"), "state": Var("state")},
    ),
)
```

**承诺(C52)**:
- `head=` 参数只接受 Rule 对象,不接受 atom list / spec 对象 / 字符串
- head Rule 是**结构上的 Rule**,语法与构造规则与 §3 完全一致

### 5.2 head=existing Rule:身份校验

当 head 引用 expr 中已存在的 Rule:

```python
expr = rule_a & rule_b
fg.eval.evaluate(expr, head=rule_a)   # ✓ rule_a 在 expr 中,作为 projection 锚

# 同 id 不同内容(stale reference)
stale = Rule(id="rule_a", where=[...different content...])
fg.eval.evaluate(expr, head=stale)   # ✗ raise RuleExprError
```

**承诺(C53)**:
- 校验依据:**(id, content_digest) 同时匹配** = 同 Rule
- `content_digest` 由 `where` atoms + `ports` 结构计算(deterministic hash)
- 三种结果:
  - 同 id + 同 digest + 同 version → 视为同 Rule(projection-only,不重复 add)
  - 同 id + 同 digest + version 不同 → warn(可能 typo)
  - 同 id + digest 不同 → **raise**(stale reference / 用户错误)
- 不同 id → 视为独立 Rule(允许)

### 5.3 head=inline Rule:port name 严格对齐(封装边界)

Inline head Rule 的 `ports` 是与 expr 的对接锚:

```python
expr.declared_ports   # ["user", "active", "state"]

# ✓ 合法:head.ports keys ⊆ expr.declared_ports
head = Rule(
    id="_q",
    where=[Var("state") == "worker"],
    ports={"user": Var("u")},    # 外部 port "user" 在 expr.declared_ports 中
)

# ✗ 非法:head.ports keys 不在 expr 中
head_bad = Rule(
    id="_q",
    where=[...],
    ports={"foo": Var("u")},     # "foo" 不在 expr.declared_ports
)
fg.eval.evaluate(expr, head=head_bad)  # raise RuleExprError
```

**承诺(C54)— 封装原则**:
- 对齐**按外部 port name**(`ports` dict 的 **key**),不按内部 Var 名
- head.ports 的 keys **严格 ⊆ expr.declared_ports**
- 内部 Var 名(dict value)是 Rule 实现细节,**不参与对齐**(用户可自由命名)
- **理由**:port 是 Rule 的封装边界;内部 var 私有,外部 port 公开;唯有公开命名空间统一才能让不同 Rule 配合

**示例:Rule 内部 Var 名可任意,外部 port 名统一**

```python
# 两个 Rule 内部用不同名字,但都暴露 port "user"
rule_a = Rule(id="A",
              where=[User(Var("u")).x == 1],
              ports={"user": Var("u")})            # 内部 "u",外部 "user"
rule_b = Rule(id="B",
              where=[Order(Var("uid")).owner == Var("uid")],
              ports={"user": Var("uid")})           # 内部 "uid",外部 "user"

# 共同对外暴露 "user" 端口;内部 Var 名互不干扰
# 跨 Rule join 仍需要显式(C10:同名 port 不自动 join)
(rule_a & rule_b).join_by_ports("user")
```

### 5.4 head.where 无语法限制

head Rule **就是普通 Rule**;`where` 可以包含 §3.5 unified canonical 允许的所有 atom 形态:

```python
head = Rule(
    id="_complex_query",
    where=[
        User(Var("u")).user_id == "u-2",              # entity-mediated atom
        Var("active") == True,                          # direct port atom
        Country(Var("c")).name == "DE",                 # 跨 entity
        LivesIn(Var("li")).user == User(Var("u")),     # entity ref RHS
        # 任意 Rule body 合法的 atom 形态都可以
    ],
    ports={"user": Var("u")},
)
```

**承诺(C55)**:
- head.where 无任何 evaluate-specific 语法限制
- head 的核心**不在 where**,而在 ports(输出接口)
- where 提供附加约束(filter);ports 决定输出投影

### 5.5 head.ports 是输出接口

head Rule 的 `ports` 定义**evaluate 输出的形状**:

```python
head = Rule(
    id="_q",
    where=[User(Var("u")).user_id == "u-2"],
    ports={"user": Var("u"), "state": Var("state")},
)

result = fg.eval.evaluate(expr, head=head)
# 输出行的 keys = head.ports keys = {"user", "state"}
```

**承诺**:
- 输出行的列名 = head.ports 的 **keys**(外部名)
- v1 不支持 head 内 port name 重命名(`ports` key 与 expr port name 必须一致);**rename 在 result 后处理**(或 v2 引入)
- ports 为空 (`ports={}`)= 无输出列(纯验证用,见 §5.8.2 pending)

### 5.6 head.desc:用户面 narrative 锚点(evidence 的"第一印象")

head 作为 Rule(C52)**继承 Rule 的全套字段**,包括 `desc`(C4)。但 head.desc 有**特殊战略意义**:

- head.desc 是**用户对 query / proof 意图的自然语言表达**
- §7 evidence 渲染时,head.desc 作为 **rule-level narrative 顶部 anchor** 出现
- 用户看到 evidence 的**第一行**就是 head.desc 插值绑定态后的自然语言
- 后续 atom-level support / reject 解释挂在 head.desc 之下

**示例**:

```python
head = Rule(
    id="_q_is_worker",
    desc="check whether %user is a worker in region %region",
    where=[
        User(Var("u")).user_id == "u-2",
        Country(Var("c")).name == "DE",
        Var("state") == "worker",
    ],
    ports={"user": Var("u"), "region": Var("c")},
)

result = fg.eval.evaluate(expr, head=head)

# 假设 evidence 渲染(预告 §7):
# Top narrative(head.desc 绑定态):
#   "check whether u-2 is a worker in region DE"
# Atom-level support / reject 列表:
#   ✓ User(u-2) exists
#   ✓ user_id == u-2
#   ✓ Country(DE) exists
#   ✓ state == "worker"
```

**承诺(C60)**:
- head 作为 Rule(C52)自然支持 `desc` 字段(C4)
- head.desc 在 §7 evidence 中**作为 rule-level narrative 顶部 anchor**;遵循 §3.7 / C5 desc 渲染规则
- desc 是用户面 evidence 的"第一印象";**强烈建议(非强制)用户填写 head.desc 以提升 evidence 可读性**
- desc 字段本身可选(C4 沿用);未填 desc 时,evidence 顶部 fallback 到 head 的 atom-level 默认 narrative

### 5.7 `Rule.projection(*port_names)` sugar

用于纯 projection(无附加约束)的快捷构造:

```python
# 等价的两种写法
head_a = Rule.projection("user", "state")
head_b = Rule(
    id=f"_proj_<auto_hash>",
    where=[],
    ports={"user": Var("_proj_user_<hash>"), "state": Var("_proj_state_<hash>")},
)

result = fg.eval.evaluate(expr, head=Rule.projection("user", "state"))
# 输出 rows 含 "user", "state" 两列
```

**承诺(C56)**:
- v1 `Rule.projection(*port_names)` **只支持同名 projection**(positional 字符串列表)
- 内部 Var 名自动生成(用户不需关心)
- v2 才考虑 rename(`Rule.projection(out_user="user")` 之类),**v1 rename 由用户 post-process**

### 5.8 evaluate / explain / why_not API(`.eval` namespace 收编)

#### 5.8.1 `.eval` namespace 演化(策略 A: inherit + evolve)

**收编新 API**:`fg.check` / `fg.diagnose`(顶层)→ 全部并入 `fg.eval.explain`(check 改名为 explain;diagnose 失败分支自带诊断)。`fg.why_not`(顶层)**未决**,详见 §5.8.4。

**新 `.eval` 表面**:

```python
fg.eval.evaluate(expr, head=Rule, engine="...", semantics=...)          → EvaluateResult
result[i].explain()                                                     → Explanation  # 主路径
fg.eval.explain(expr, head=closed_Rule, engine="...", semantics=...)    → Explanation  # advanced/manual
fg.eval.inspect_semantics(semantics_obj)                                → preview(零改动)
# fg.eval.why_not(...) — PENDING,见 §5.8.4
```

**删除项**(alpha,直接断,无 transition):

| 删除 | 替代 / 理由 |
|---|---|
| `fg.eval.accept` / `accept_many` | 用户手动 `fg.batch()` write(per §5.7+ 设计哲学)|
| `engine_options=` 参数(evaluate)| semantics wrapper 完全替代(Track 3-post 已锁)|
| `registry=` 参数(evaluate SDK 表面) | SDK 表面隐藏;底层若需 advanced override 可保留 internal |
| `fg.check`(顶层)| 改名为 `fg.eval.explain` |
| `fg.diagnose`(顶层)| 功能并入 `explain`(failed 分支自带诊断 via evidence)|
| `fg.why_not`(顶层) | **PENDING** — 是否保留 / 迁移待定,见 §5.8.4 |

**Phase 1 deprecated**(保留功能,不再演进):

| Phase 1 状态 | Phase 3 删除条件 |
|---|---|
| `fg.eval.run` 保留 | 等 `read.match`(或等价 Rule 查询入口)在后续节锁定后,run 删除 |

**延后 refactor**:`fg.what_if.*` 四个 shells(`check_fact_overlay` / `check_rule_disable` / `check_rule_literal_replace` / `check_rule_add_condition`)— 等 explain 完成后单独 refactor;允许全部废弃(alpha,per §5 设计哲学)。

#### 5.8.2 `fg.eval.evaluate(expr, head=Rule, ...)` → EvaluateResult

```python
result = fg.eval.evaluate(
    expr,
    head=head_rule,                          # 必需,Rule 对象
    engine="problog",                        # 可选
    semantics=ProbLogSemantics(...),         # 可选,与 engine 自洽
)
# 返回 EvaluateResult(rich frozen 容器)
```

> **2026-05-19 Wave 1 设计更新**:撤销 13-field `EvidenceHandle` 设计;改用 Rainbird-style **result-fact-centric** 5-concept 模型(`EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` / `Explanation`)。`EvidenceHandle` 重命名为 `EvidenceRef` 并大幅简化为 5 字段;shared context 上提至 `EvaluateResult`,**避免 per-row 13-field 复制**。

**Claim**(Rainbird-style explained fact 一等表示;Wave 1 加入):

```python
@dataclass(frozen=True)
class Claim:
    """row 上的 first-class 被解释事实(Rainbird "result = fact" 心智)。

    kind 区分:
    - `fact_triple`:经典 S/R/O 三元组
    - `rule_head`:Rule.head 模板调用(name + arguments)
    - `aggregate_result`:聚合 head(name + filter args)
    - `projection`:纯 projection head(name + projected bindings)
    """
    kind: Literal["fact_triple", "rule_head", "aggregate_result", "projection"]
    name: str                                # rule_id / predicate_id / aggregate_kind
    arguments: Mapping[str, Any]             # var name → bound value(JSON-friendly)
    repr: str                                # human-readable(e.g., "active_user_in_US(user='u-2')")
    digest: str                              # canonical digest of (kind, name, arguments)
```

**EvidenceRef**(row-local opaque audit/ref plumbing;5 字段最小化):

```python
@dataclass(frozen=True)
class EvidenceRef:
    """row 级 evidence audit/ref handle(Rainbird factID 等价的内部结构化形态)。

    设计原则:lightweight,opaque-ish;shared context 不重复,通过 result_id 回引 EvaluateResult。
    用户主流程:`row.explain()` / `result[i].explain()`,不直接持有 ref。
    EvidenceRef 不作为 public explain 入口;仅用于 row identity / stale detection / durable audit linking。
    """
    ref_id: str                              # canonical digest of (result_id, row_id, fact_digest, closed_head_digest)
    result_id: str                           # → EvaluateResult.result_id(context 回引)
    row_id: str                              # → EvaluateRow.row_id
    fact_digest: str                         # **invariant:fact_digest == row.claim.digest**
    closed_head_digest: str                  # closed_head content_digest(per row 异)
```

**Contract**:`EvidenceRef.fact_digest == EvaluateRow.claim.digest`(构造期 invariant)。

**DetachedRowError**(programming error,非 business failure):

```python
class DetachedRowError(RuntimeError):
    """调用 .explain() / .close() 的 row 没有 live EvaluateResult resolver。"""
```

**EvaluateRow**(fact-centric;Wave 1 重整):

```python
@dataclass(frozen=True)
class EvaluateRow:
    """Result fact / decision claim — Rainbird result-object 等价物。

    Wave 1 重整:claim / evidence_ref 上提为一等字段;row 本身就是"被解释事实"。
    Row 有 live / detached 双状态:从 EvaluateResult 取出的 row 是 live;JSON 反序列化或手工构造的 row 是 detached。
    """
    # ──── Data fields(canonical,参与序列化 / digest / audit)────
    row_id: str                              # 格式见 §5.8.5
    bindings: Mapping[str, Any]              # head.ports key → value
    claim: Claim                             # 一等 fact 表示(Wave 1)
    raw_kind: Literal["probabilistic", "possibilistic"] | None = None
    bound: tuple[float, float] | None = None # 置信区间 [lo, hi];可能性区间
    evidence_ref: EvidenceRef                # row 级 evidence entry(Wave 1)

    # ──── Plumbing field(non-data,non-digest,non-serializable)────
    _result_resolver: Callable[[], "EvaluateResult"] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
        metadata={"contract": False, "serialize": False},
    )

    def explain(self) -> "Explanation":
        """主入口:解释该 row / claim。仅 live row 可用。"""
        if self._result_resolver is None:
            raise DetachedRowError(
                "row.explain() requires a live row obtained from EvaluateResult. "
                "This row is detached; use fg.eval.explain(expr, head=closed_head) for manual replay."
            )
        return self._result_resolver()._explain_row(self)

    def close(self) -> Rule:
        """Advanced introspection:返回该 row 对应的 closed head Rule。仅 live row 可用。"""
        if self._result_resolver is None:
            raise DetachedRowError(
                "row.close() requires a live row obtained from EvaluateResult."
            )
        return self._result_resolver()._close_row(self)

    def as_dict(self) -> dict[str, Any]:
        """仅 bindings — detached-safe data 视图。需要 meta 时用 dataclasses.asdict(row)。"""
        return dict(self.bindings)
```

**Row live / detached contract**:

| Row 状态 | 来源 | `.explain()` / `.close()` 行为 | data fields 访问 |
|---|---|---|---|
| **Live** | `EvaluateResult.__getitem__` / `__iter__` / `.first()` | ✓ 正常工作 | ✓ |
| **Detached** | JSON deserialize / pickle restore | ✗ raise `DetachedRowError` | ✓ |
| **Manually constructed** | `EvaluateRow(...)` 用户直接构造 | ✗ raise `DetachedRowError` | ✓ |

**序列化承诺**:
- row → JSON:仅 data fields(`row_id` / `bindings` / `claim` / `raw_kind` / `bound` / `evidence_ref`)
- row from JSON:detached state;`.bindings` / `.claim` / `.evidence_ref` 可读,`.explain()` / `.close()` 不可用
- `_result_resolver` 不参与 canonical digest / equality / hash / JSON serialization
- cross-session replay v1 走 `fg.eval.explain(expr, head=closed_head)` advanced/manual path

**EvaluateResult**(evaluation session envelope + shared audit/reproducibility context;Wave 1 重整):

```python
@dataclass(frozen=True)
class EvaluateResult:
    """Evaluation session 的 result set envelope。

    作为 **shared audit / reproducibility context source-of-truth**;EvidenceRef 通过 result_id 回引此处获取 context;EvidenceGraph.metadata 是此处 fields 的 durable snapshot copy。
    """
    result_id: str                           # session id,跨调用稳定 reference(canonical digest)
    run_id: str                              # 本次 evaluate 追踪 id
    rows: tuple[EvaluateRow, ...]
    head: Rule                                # evaluate 时用的(open)head
    engine: str                                # "souffle" / "native" / "problog" / "pyreason"
    engine_version: str | None                # adapter 报告(e.g., "problog-2.2.4")
    adapter_version: str | None                # factpy-kernel adapter 版本
    expr_digest: str                           # body RuleExpr **结构** digest(C34;composition 形态)
    rule_set_digest: str                       # body 内 N 个 Rule 的 content_digest canonical join hash;**与 expr_digest 正交**:expr 结构 vs Rule 字段内容
    view_snapshot_digest: str                  # projected view 数据 digest(fact 漂移检测 anchor)
    semantics_digest: str | None              # semantics wrapper digest(C68)
    evaluated_at: datetime
    result_digest: str                         # 结果摘要,见 §5.8.5

    # Internal row plumbing;public 主入口在 EvaluateRow.explain()/close()
    def _explain_row(self, row: EvaluateRow) -> "Explanation": ...
    def _close_row(self, row: EvaluateRow) -> Rule: ...

    # 容器协议
    def __iter__(self) -> Iterator[EvaluateRow]: ...
    def __len__(self) -> int: ...
    def __getitem__(self, idx: int) -> EvaluateRow: ...
    def first(self) -> EvaluateRow | None: ...
    def exists(self) -> bool: ...
    def count(self) -> int: ...
```

**Explain API 分层**(Wave 1 row-centric 修订):

```python
# 主入口(SDK 推荐,Rainbird-style)
row.explain() -> Explanation
result[2].explain() -> Explanation

# Advanced / 手工 closed head replay(完全脱离 live result session)
fg.eval.explain(expr: RuleExpr, *, head: Rule, engine, semantics) -> Explanation

# Advanced introspection
row.close() -> Rule
```

**承诺修订**:
- ~~`fg.eval.explain(handle: EvidenceHandle, ...)` 撤销~~;不提供 public `explain_ref`
- ~~`fg.eval.explain_closed(...)` 不引入~~;manual closed-head 统一使用 `fg.eval.explain(expr, head=closed_head)`
- 用户面 evidence service 主路径 = `row.explain()` / `result[i].explain()`;`closed_head` 不出现在主路径用户面
- `row.explain()` 内部通过 non-serializable `_result_resolver` 回到 owning `EvaluateResult`

**`row.close()` 行为**:

返回:**closed Rule**,等价于 `result.head + [literal atoms for each port from row.bindings]`,id 为 `f"{result.head.id}_closed_{row.row_id}"`。`row.close()` 是 advanced introspection,**不**是 evidence service 主路径。

**承诺**:
- evaluate 入口接受 `head=Rule(...)`(必需,**不接 row**);head 决定输出投影
- 输出 row columns = head.ports.keys()
- EvaluateResult / EvaluateRow data fields 都是 frozen,immutable;EvaluateRow 的 `_result_resolver` 是 non-data plumbing
- 行 identity 由 bindings 决定(同 bindings 同 row_id,详见 §5.8.5)

#### 5.8.3 Explain API + Explanation envelope(Wave 1 + Wave 2 修订)

**用户主流程**(SDK 推荐;Rainbird-style result-fact-centric):

```python
result = fg.eval.evaluate(expr, head=Head("active_user", ports={"user": u}))

# 主入口
explanation = result[2].explain()
# 或:
row = result.first()
explanation = row.explain()
```

**Advanced**(完全手工 closed head — 非 evidence service 主路径):

```python
closed_head = row.close()
explanation = fg.eval.explain(expr, head=closed_head, engine=..., semantics=...)
```

**API 分层承诺**(Wave 1):
- **主路径**:`row.explain()` / `result[i].explain()` — fact-centric,Rainbird 等价
- **Advanced manual replay**:`fg.eval.explain(expr, head=closed_head)` — for fully 手工 closed Rule / cross-session replay(不推荐用户面)
- **Advanced introspection**:`row.close()` — 查看 closed Rule;**不**是 evidence service 主路径(C66 修订)
- `EvidenceRef` 保留为 row-local audit/ref plumbing,**不是** public explain 入口

**Explanation envelope**(Wave 1 重整 + Wave 2 加 failure_class):

```python
@dataclass(frozen=True)
class Explanation:
    # ──── Core ────
    status: Literal["passed", "failed", "unsupported", "invalid_request"]
    evidence: EvidenceGraph | None     # 仅 status="passed" 非 None(per C81)
    claim: Claim                        # 被解释 fact(Wave 1;从 row.claim 传递)
    
    # ──── Context lineage(Wave 1)────
    result_id: str                      # 回引 EvaluateResult
    row_id: str | None                  # 来源 row(若有);manual fg.eval.explain(expr, head=closed_head) 时 None
    evidence_ref_id: str | None         # row.evidence_ref.ref_id(若来源 live row)
    
    # ──── Quantitative(Wave 1)────
    raw_kind: Literal["probabilistic", "possibilistic"] | None = None
    bound: tuple[float, float] | None = None
    
    # ──── Failure envelope(Wave 2 #3)— status != "passed" 时填 ────
    failure_class: Literal[
        "no_matching_row",                  # Phase 1 无 row 对应该目标
        "closed_head_false",                # 用户提供 / 恢复的 closed head 当前 snapshot 不成立
        "stale_row",                        # row digest 与当前 rule/view/semantics 不一致
        "row_not_in_result",                # row 不属于当前 EvaluateResult / run scope
        "insufficient_closed_bindings",     # 无法从 row/ref 形成完整 closed head(head.ports 未全绑定)
    ] | None = None                          # 仅 status="failed" 填
    
    checked_scope: Mapping[str, Any] | None = None  # 校验 context — engine / view_snapshot_digest / semantics_digest / rule_set_digest 对比结果;Wave 2 #3
    suggested_next_steps: tuple[str, ...] = ()       # 用户面 hint(Wave 2 #3);非 atom locator
    
    errors: tuple[ErrorDTO, ...] = ()        # status ∈ {"unsupported", "invalid_request"} 必填
    warnings: tuple[WarningDTO, ...] = ()
```

**failure_class 与 status 的对应**(Wave 2 修订):

| status | failure_class 允许值 | 例 |
|---|---|---|
| `passed` | None | normal success path;evidence 非 None |
| `failed` | 上述 5-enum 之一 | **business semantic** "binding/claim 不成立";不混进技术错 |
| `unsupported` | None;走 `errors` 字段(`EVIDENCE_LOOKUP_MISS` / `ENGINE_WITNESS_UNAVAILABLE` 等 error code) | **technical** 引擎能力不足 |
| `invalid_request` | None;走 `errors`(`UNKNOWN_VARIABLE_IN_BINDING` 等) | **technical** 输入 schema 错 |

**关键 invariant**(Wave 2):**`failure_class` 仅在 `status="failed"` 时填;`engine_no_witness` / `engine_error` / `invalid_binding` 等技术错不进 failed → 走 `unsupported` / `invalid_request` 的 `errors`**。这避免把"业务不成立"和"技术故障"混为同一态。

**示例 failed Explanation**(stale row):

```python
Explanation(
    status="failed",
    failure_class="stale_row",
    evidence=None,
    claim=Claim(kind="rule_head", name="active_us", ...),
    result_id="result-1",
    row_id="row-2",
    evidence_ref_id="ref:abc...",
    checked_scope={
        "engine": "souffle",
        "view_snapshot_digest_at_evaluate": "abc...",
        "view_snapshot_digest_current": "xyz...",   # mismatch detected
        "rule_set_digest_at_evaluate": "...",
        "semantics_digest_at_evaluate": "...",
    },
    suggested_next_steps=(
        "re-run evaluate to refresh rows against current view snapshot",
        "inspect ledger changes since result_id was generated",
    ),
)
```

**DetachedRowError 说明**:`row.explain()` / `row.close()` 在 detached row 上直接 raise `DetachedRowError`;这是 Python programming error,**不进入** `failure_class` enum。

**Status 语义**(沿用 `CheckStatus` 4-state):
- `passed`:engine 确认 head 成立,evidence 是 positive support tree
- `failed`:engine 确认 head 不成立,evidence 为 None;failure envelope 给出 row/closed-head 级失败类别(C81/C125)
- `unsupported`:engine 不支持(超出能力,例如 ProbLog 处理 PyReason-only 特性)
- `invalid_request`:输入 shape 错误

**evidence 统一表示**:
- passed 用 `EvidenceGraph` 类型(`audit/evidence_graph.py`)
- failed / unsupported / invalid_request:evidence 为 None(C81)
- **不分拆** evidence / why_not 字段;统一表面

**跨 engine / semantics 一致性**:
- evaluate 与 explain 都接受 `semantics=` wrapper
- Semantics wrapper 构造时**自洽绑定 engine**(`ProbLogSemantics → problog`,`PyReasonSemantics → pyreason`)
- 若用户用不同的 Semantics 在 evaluate / explain → 那是用户**显式选择**(语义不同),非冲突;**不发 warn**

#### 5.8.4 `fg.eval.why_not(...)` [PENDING — 未确定是否需要]

> **v1 PENDING**:`why_not` 是否仍为 first-class API 尚未决定。
>
> **当前未定项**:
> - explain 失败分支(`Explanation.status = "failed"` + `evidence = EvidenceGraph(why-not 结构)`)**已经覆盖** "为什么不成立" 的核心需求
> - 是否仍需要独立 `why_not` API(传 candidate 列表批量反事实分析)未明确
> - 现有 `fg.why_not(inference, candidates)` 是否完全废弃,还是迁移至 `fg.eval.why_not(expr, head, candidates)`,待**用户场景验证后决定**
> - 触发条件:explain 落定后,审查用户实际需要的"反事实"工作流是否被 explain 完全覆盖

**v1 保守策略**:
- 暂不在 `.eval` namespace 暴露 `why_not`
- 顶层 `fg.why_not` 也不保证保留(per C71 类似立场,允许全废弃)
- 如未来需要,作为 §7 evidence DTO 锁定后的扩展承诺

#### 5.8.5 row_id / digests 计算规则

```text
row_id          = f"{run_id}:{sha256_hex(canonical(bindings))[:16]}"
row_digest      = sha256_hex(canonical(bindings) + raw_kind + bound)   # 行的完整数据 hash
result_digest   = sha256_hex(concat(row_digests) + head.content_digest + engine + semantics_digest)
bindings_digest = sha256_hex(canonical(bindings))                       # 行的 bindings-only hash(可选辅助)
expr_digest     = expr.content_digest                                   # body expr 的结构 hash(C34)
```

**承诺**:
- **row_id** 复合格式:`<run_id>:<short_bindings_hash>` — 既能追溯 run,又能跨 run 比对同 bindings
- **row_digest** 包含 `raw_kind / bound`(行的完整数据)— 与 bindings_digest 区分
- **result_digest** 是 audit 元数据;**不参与 explain 运行时校验**(用户对比作可信度检查)
- **expr_digest** 在 close / explain 路径上用于校验上下文一致(若 explain 时传入 expr 的 content_digest 与 result.expr_digest 不匹配,raise)

**两种 hash 的边界(必须区分)**:

| 概念 | 用途 | 稳定性 |
|---|---|---|
| `__hash__`(Python 内置)| 容器 key(set / dict);RuleExpr `__eq__` 结构比较(C34) | **仅同进程稳定**;Python `PYTHONHASHSEED` 跨进程随机化 |
| `content_digest` / `row_digest` / `result_digest` / `bindings_digest` / `expr_digest`(canonical serialization)| audit / 跨进程 / 持久化对比 | **跨进程稳定**;基于 canonical bytes + sha256;deterministic |

**承诺(强化)**:
- 本节所有 `*_digest`(`content_digest` / `row_digest` / `result_digest` / `bindings_digest` / `expr_digest`)**均是 canonical serialization digest**,**跨进程 deterministic stable**(`sha256(canonical_bytes)` 风格)
- C34 `__hash__` 同进程稳定的承诺**仅适用于 Python 内置 `__hash__`**,不延伸到这些 digest;两者是**不同语义**
- digest 形态在 v1 实现时锚定到现有 `core/protocol/digests.py` 的 `sha256_hex` / `sha256_token` 工具(已 ship)

#### 5.8.6 `fg.eval.evaluate(expr)` / `explain(expr)` 无 head → raise

E2 沿用:**evaluate / explain 都必须显式 head**:

```python
fg.eval.evaluate(expr)              # ✗ raise RuleExprError("head=... required")
fg.eval.evaluate(expr, head=None)   # ✗ 同上
fg.eval.explain(expr)               # ✗ 同
fg.eval.explain(expr, head=None)    # ✗ 同
```

**用户想要 "all ports projection"** → 显式 `Rule.projection(*expr.declared_ports)`。

#### 5.8.7 Semantics wrapper 形态(per-rule sub-object)

evaluate / explain 的 `semantics=` 参数接受 engine-specific wrapper。新设计将 per-rule 参数收入 sub-object,与底层 `*RuleExt` 1:1 对齐(audit-friendly)。

##### A. PyReasonSemantics

```python
@dataclass(frozen=True)
class PyReasonRuleParams:
    derived_bound: tuple[float, float] | None = None
    atom_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    # atom_bounds key 必须是 **full atom_id**(C19 沿用),例:"rule_a:atom_0"
    # 不允许短名 "atom_0"(防跨 rule 冲突)
    timestep_delay: int | None = None


@dataclass(frozen=True)
class PyReasonSemantics:
    rule_params: dict[str, PyReasonRuleParams] = field(default_factory=dict)
    # key = Rule.id;head 与 body Rules 共用此 mapping(C52)

    default_derived_bound: tuple[float, float] | None = None
    default_timestep_delay: int = 0

    # 引擎迭代深度 — 与 fact 时间生命周期正交(详见 §5.8.7.C)
    iteration_count: int = 1

    temporal_projection: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    uncertainty_projection: dict[str, Any] = field(default_factory=dict)

    name: str | None = None
    fallback: str = "reject_unconfigured"
```

**字段命名理由**:
- `derived_bound`(替原 `head_bound`)— 避免与 `head=Rule` 参数混淆
- `atom_bounds`(替原 `body_predicate_bounds`)— "body" 已隐含 Rule.where 语义
- `timestep_delay` 保留(无歧义)

##### B. ProbLogSemantics(对称补全 uncertainty_projection)

```python
@dataclass(frozen=True)
class ProbLogRuleParams:
    derived_bound: tuple[float, float] | None = None
    # ProbLog 点概率 p 表达为 derived_bound=(p, p);
    # 不暴露独立 probability 字段,避免与 raw_kind/bound 双写漂移。


@dataclass(frozen=True)
class ProbLogSemantics:
    rule_params: dict[str, ProbLogRuleParams] = field(default_factory=dict)
    default_derived_bound: tuple[float, float] | None = None

    # 新增:与 PyReasonSemantics 字段对称
    uncertainty_projection: dict[str, Any] = field(
        default_factory=lambda: {
            "probabilistic": {"policy": "reject"},
            "possibilistic": {"policy": "reject"},
            "fallback": "reject_unconfigured",
        }
    )

    name: str | None = None
    fallback: str = "reject_unconfigured"
```

**`uncertainty_projection` schema**(严格遵循 `SemanticsProfile._normalize_uncertainty_projection`):

```text
{
    "<raw_kind>": {"policy": "<policy>"},   # 每种 raw_kind 一条
    "fallback": "<fallback_policy>",         # 全局 fallback(仅这一个键不指向 raw_kind)
}
```

| 字段 | 取值集合 |
|---|---|
| `<raw_kind>` key | `"probabilistic"` / `"possibilistic"` |
| `policy` 值 | `identity_probability` / `probability_interval` / `possibility_interval` / `lower` / `midpoint` / `upper` / `reject` |
| `fallback` 值 | `reject_unconfigured` / `warn_default` / `use_default` |

**默认 reject 两种 raw_kind 的理由**:
- midpoint 是强语义选择(`[0.2, 0.8] → 0.5`),不应静默默认
- possibilistic + midpoint 尤其危险(possibility ≠ probability,语义异种)
- 用户需显式 opt-in:
  ```python
  ProbLogSemantics(
      uncertainty_projection={
          "probabilistic": {"policy": "midpoint"},
      },
  )
  ```

**T6 三段承诺**(必须**全部完成**,不允许只做 SDK shell):
1. ✓ SDK shell:`ProbLogSemantics` 加 `uncertainty_projection` 字段
2. ✓ Lower:字段降到 `SemanticsProfile.uncertainty_projection`(已有 normalize 框架)
3. ✗ **ProbLog adapter 必须实际消费** `raw_kind + bound`(meta 字段),按 policy 投影为点概率 — **当前未实现**;v1 必须落实

##### C. temporal_projection 3 mode(只管 fact 时间生命周期)+ iteration_count 独立

**设计立场**:`temporal_projection` 现在**只决定 fact 的时间生命周期**(active_from / active_to);**引擎迭代深度**由独立字段 `iteration_count: int = 1` 控制 — 两者正交,不再混淆。

```python
# Mode 1: 禁用时间(fact 全局 valid,active_from=0, active_to=None)
{"mode": "none"}

# Mode 2: 从 fact 元数据自动计算(已实现机制)
{"mode": "fact_boundaries", "universe": ["2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z"]}

# Mode 3: 等长时间桶(新增,v1 需实现)
{"mode": "time_binned", "bin_size": "PT1H", "universe": [...]}
```

**`bin_size` 形态严格化**(T4):
- **仅接受 ISO 8601 duration**:`"P1D"` / `"PT1H"` / `"PT30M"` / `"PT15M"` 等
- **或极小白名单 short form**:`"1d"` / `"1h"` / `"15m"` / `"1m"`
- **拒绝**任意"人类可读"字符串(如 `"1 month"` — 月份长度歧义、时区/DST 问题)
- 内部 canonicalize 到 `timedelta`

**`iteration_count` 语义**(U1 / U3):
- PyReasonSemantics 顶级 int 字段(默认 1)
- 控制 PyReason 引擎跑的**推理迭代 round 数**;每个 round 应用所有规则一次
- **与 fact 时间生命周期正交**:即使 `temporal_projection={"mode": "none"}`,仍可设 `iteration_count=N` 让规则链 / 延迟规则完整传播
- 与 `timestep_delay`(per-rule)的关系:`iteration_count` 是引擎全局 round 总数;`timestep_delay` 是单规则在 body 满足后延后几 round 才 emit
- **ProbLogSemantics 不引入此字段**(ProbLog 是 fixpoint 引擎,一次跑完,无迭代深度概念)

**示例:无时间数据 + 多 round 推理**:
```python
PyReasonSemantics(
    temporal_projection={"mode": "none"},   # fact 时间无关
    iteration_count=5,                       # 但跑 5 round 让规则链传播
)
```

**示例:有时间数据 + 按小时分桶**:
```python
PyReasonSemantics(
    temporal_projection={
        "mode": "time_binned",
        "bin_size": "PT1H",
        "universe": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
    },
    iteration_count=24,   # 24 round(或更多让信息跨桶传播)
)
```

**旧名重命名(迁移,非现状改名)**:
- `fixed_timesteps`(旧 mode)→ **移除**,功能拆给 `iteration_count` 独立字段
- `valid_time_boundaries` → `fact_boundaries`(改名更准确)
- `time_binned` 是**新增功能**,v1 需要实现

##### D. 二级 fallback(per-rule lookup)

```text
查找 Rule R 的参数:
  1. semantics.rule_params[R.id] 命中 → 用该 RuleParams
  2. 缺该 Rule → wrapper-level default_*(default_derived_bound / default_timestep_delay)
  3. 仍缺 → engine 原生默认行为
```

`rule_params` 中含**不在 expr+head 范围的 Rule.id** → **stale ID raise**(per 之前 D2 锁定方向)

### 5.9 `.join_by_ports(*explicit_names)` 公开 SDK 方法

与 `.join(...)` 并列,作为按 port name 显式 join 的便捷方法:

```python
# 显式 port name 列表 — 与之前拒绝的 join_by("port") variadic-in-group 不同
expr = (rule_a & rule_b).join_by_ports("user", "active")

# 等价于:
expr = (rule_a & rule_b).join(
    rule_a.user == rule_b.user,
    rule_a.active == rule_b.active,
)
```

**承诺(C58)**:
- 接受**显式 port name 列表**(用户列出哪些 port 要 join)
- 加 Rule 后**不会 silent 改变此 list**(与 C22 拒绝 `join_by("name")` 的理由不冲突)
- 等价于按每个 name 在所有 occurrences 间生成 pairwise 约束

### 5.10 inspect.ports:rich PortInspect 辅助 head 构造

inspect 通过 ports 富信息辅助用户构造 head:

```python
inspect = fg.rules.inspect(expr)

inspect.ports
# list[PortInspect]
# [
#   PortInspect(
#       name="user",                # 外部 port name
#       kind="entity_ref",          # entity_ref / value
#       entity_type="User",         # 来源 entity
#       field=None,                  # entity ref 时为 None
#       value_type=None,
#   ),
#   PortInspect(
#       name="active",
#       kind="value",
#       entity_type="User",          # 来源 entity(active 是 User 的字段)
#       field="is_active",           # 来源 field
#       value_type="bool",
#   ),
# ]
```

**承诺(C59)**:
- inspect.ports 返回 `list[PortInspect]`,字段含 `name / kind / entity_type / field / value_type`
- 用户用 ports 信息构造 head:知道 port 类型与可用约束形态

#### 5.10.1 `inspect.is_closed` / `inspect.unbound_ports`(派生 utility)

inspect 在 ports 基础上派生**轻量 closedness check**,供用户在 explain 之前**预校验**:

```python
inspect = fg.rules.inspect(head_rule)

inspect.unbound_ports   # tuple[str, ...]   未字面绑定的 port 名集合
inspect.is_closed       # bool              派生:not unbound_ports

if inspect.is_closed:
    fg.eval.explain(expr, head=head_rule)   # ✓ 必通过 closed-head 校验
else:
    print("还缺这些 ports:", inspect.unbound_ports)
```

**架构定位**(必须明示):
- `is_closed` / `unbound_ports` **只是 inspect 的派生 utility**,不在 RuleExpr / Rule 类型上
- **不重新引入 Claim 架构中心**(避免回退到旧 §5 设计)
- 派生计算 read-only,无副作用

**v1 closed 判定规则**(严格,只收 2 类):

| 情形 | 模式 | 收吗 |
|---|---|---|
| (a) value port 字面值绑定 | `Var("p") == literal` | ✓ 收 |
| (b) entity-ref port 由 primary identity 锚定 | `EntityType(Var("p")).<primary_identity_field> == literal` | ✓ 收 |
| (c) 通用 field literal 约束 | `EntityType(Var("u")).field == literal`,ports 含名为 "field" 的 port | ✗ **不收**(field literal 不一定绑定该名 port,可能只是对 entity 的 filter) |
| (d) Transitive 等价 | `Var("a") == "x"; Var("b") == Var("a")` | ✗ **不收**(v2 deferred) |
| (e) 跨 port Var 等价 | `Var("a") == Var("b")` | ✗ **不收**(两端都未独立绑定) |

**复合 primary identity** 处理(若 EntityType 有多个 primary identity 字段):**全部** primary identity 字段都字面绑定 → entity 唯一确定 → port 算 closed;少一个 → 不算。

**关键 invariant**:
> `inspect.is_closed == True` **等价于** `fg.eval.explain(expr, head=that_rule)` **不会因 "head not closed" 而 raise**。

两者使用同一判定逻辑;invariant 在 v1 实施时是 testable 锚点。

### 5.11 §5 设计承诺清单(锁定)

| # | 承诺 |
|---|---|
| C52 | head 是 first-class Rule 对象;`head=` 只接受 Rule,不接受 atom list / spec |
| C53 | head=existing Rule 校验:(id, content_digest) 双匹配;digest 失配 → raise;version 失配 → warn |
| C54 | head.ports 的 **keys**(外部 port name)严格 ⊆ expr.declared_ports;auto-join 按 port name;内部 Var 名(dict value)不参与对齐(封装原则) |
| C55 | head.where 无 evaluate-specific 语法限制 — 普通 Rule body;head 核心在 ports 作输出接口 |
| C56 | `Rule.projection(*port_names)` sugar:v1 只同名 projection;rename v2 |
| C57 | `fg.eval.evaluate(expr)` 无 head → raise(E2 强制 explicit) |
| C58 | `.join_by_ports(*explicit_names)` 公开 SDK 方法;显式 port name 列表(无 silent change 风险) |
| C59 | inspect.ports 返回 rich `list[PortInspect](name / kind / entity_type / field / value_type)`;辅助用户构造 head |
| C60 | head 自然支持 `desc` 字段(C4 沿用);head.desc 在 §7 evidence 中作为 **rule-level narrative 顶部 anchor**;遵循 §3.7 / C5 desc 渲染规则;**强烈建议(非强制)用户填写** |
| C61 | `.eval` namespace 收编 `explain`(顶层 `fg.check` / `fg.diagnose` 删除并合入);`fg.check` 改名为 `fg.eval.explain`;`fg.why_not` 是否保留 PENDING(见 §5.8.4)|
| C62 | `fg.eval.evaluate(expr, head=Rule, engine=..., semantics=...)` 签名升级;**SDK 表面删除** `engine_options=` / `registry=`(底层若需保留作 internal);删除 `fg.eval.accept` / `accept_many` |
| C63 | `fg.eval.run` Phase 1 deprecated/frozen,签名不再演进;Phase 3 删除条件 = `read.match` 或等价查询入口锁定 |
| C64 | **(Wave 1/row-centric 修订 2026-05-19)** `EvaluateRow` 6 个 canonical data fields:`row_id` / `bindings` / `claim` / `raw_kind` / `bound` / `evidence_ref` + 1 个 non-data plumbing field `_result_resolver`;live row 支持 `.explain()` / `.close()`,detached / manual row 调用二者 raise `DetachedRowError`;`as_dict()` 返回 bindings only;**Claim 一等表示**(`fact_triple` / `rule_head` / `aggregate_result` / `projection` 4 kinds)|
| C65 | **(Wave 1/row-centric 修订 2026-05-19)** `EvaluateResult` 是 frozen evaluation session envelope + shared audit/reproducibility context source-of-truth;13 data fields(`result_id` / `run_id` / `rows` / `head` / `engine` / `engine_version` / `adapter_version` / `expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `semantics_digest` / `evaluated_at` / `result_digest`)+ 容器协议;`__getitem__` / `__iter__` / `.first()` 返回 live bound row;public explain 主入口不在 result 上 |
| C66 | **(Wave 1/row-centric 修订 2026-05-19)** Explain API 两入口分层:主路径 `row.explain()` / `result[i].explain()` Rainbird-style fact-centric;Advanced/manual `fg.eval.explain(expr, head=closed_head)` for fully 手工 closed Rule / cross-session replay;`row.close()` 仅 advanced introspection;**删除 public `fg.eval.explain_ref` 与 `fg.eval.explain_closed`** |
| C67 | `Explanation` 4-state status(passed / failed / unsupported / invalid_request)沿用 `CheckStatus`;evidence 统一为 `EvidenceGraph`(不拆 evidence / why_not 字段) |
| C68 | digests 计算规则:`row_id = "{run_id}:{sha256_short(bindings)}"`;`row_digest`(含 raw_kind/bound)/ `result_digest`(rows+head+engine+semantics)/ `bindings_digest`(可选)/ `expr_digest`(沿用 C34);**纯 audit metadata,不参与运行时校验** |
| C69 | `.eval` 跨 engine / semantics 一致性:Semantics wrapper 构造时**自洽绑定 engine**;evaluate 与 explain 用不同 Semantics 是显式选择,**不 warn 不 reject** |
| C70 | `fg.eval.why_not` v1 **PENDING**:explain 已覆盖"为何不成立"核心需求;是否仍需独立 API 待用户场景验证后决定;允许全废弃 |
| C71 | `fg.what_if.*` 四个 shells 延后 refactor;允许全部废弃(alpha,等 explain 完成后单独决策) |
| C72 | `inspect.is_closed` (bool) + `inspect.unbound_ports` (tuple[str, ...]) 作为派生 read-only utility(**仅在 inspect 上,不在 RuleExpr / Rule 类型上**;**不重新引入 Claim 架构中心**);v1 closed 判定**仅收 2 类**:(a) `Var("p") == literal` 或 (b) `EntityType(Var("p")).<primary_identity_field> == literal`(复合 primary identity 需全部字面绑定);通用 field literal / transitive 等价 / 跨 port Var 等价**不收**(v2 deferred);**invariant**:`inspect.is_closed=True` 等价于 explain head 必通过 closed-head 校验 |
| C73 | `*Semantics` per-rule 参数走 sub-object 形态:`rule_params: dict[Rule.id, *RuleParams]`(head 与 body Rules 共用此 mapping,C52);二级 fallback(rule_params → wrapper default_* → engine 原生);`rule_params` 含不在 expr+head 范围的 Rule.id → raise(stale ID) |
| C74 | `PyReasonRuleParams` 字段:`derived_bound` / `atom_bounds` / `timestep_delay`(避免 head/body 命名混淆);`atom_bounds` key **必须是 full atom_id**(`<rule_id>:atom_<index>`,C19 沿用),**不允许短名** |
| C75 | `PyReasonSemantics` / `ProbLogSemantics` wrapper 字段对称;两者都有 `uncertainty_projection`(T6);Wrapper-level default 字段:`default_derived_bound` / `default_timestep_delay`;ProbLog 点概率 `p` 也表达为 `raw_kind="probabilistic", bound=(p,p)` / `derived_bound=(p,p)`,不暴露独立 `probability` field |
| C76 | `ProbLogSemantics.uncertainty_projection` schema:`{"<raw_kind>": {"policy": "<policy>"}, "fallback": "<fallback_policy>"}`;v1 默认**保守 reject** 两种 raw_kind(`{"probabilistic": {"policy": "reject"}, "possibilistic": {"policy": "reject"}, "fallback": "reject_unconfigured"}`);midpoint 等强语义选择**必须用户显式 opt-in**;**T6 是三段承诺**:SDK shell + lower 到 SemanticsProfile + **ProbLog adapter 实际消费 `raw_kind + bound` 投影**(后者当前未实现,v1 必须落实) |
| C77 | `temporal_projection` **3 mode**(只管 fact 时间生命周期):`none` / `fact_boundaries`(从 fact 元数据自动)/ `time_binned`(等长时间桶,**新增需实现**);Mode `time_binned` 的 `bin_size` 严格化:**仅 ISO 8601 duration**(`P1D` / `PT1H` 等)+ 小白名单 short form(`1d` / `1h` / `15m` / `1m`);**拒绝任意人类可读字符串**(`"1 month"` 等歧义);旧名 `valid_time_boundaries` → `fact_boundaries`(重命名迁移)|
| C78 | PyReasonSemantics 顶级字段 **`iteration_count: int = 1`**,控制引擎推理迭代 round 总数;**与 fact 时间生命周期正交**(temporal_projection 不再含 fixed_steps mode);ProbLogSemantics **不引入此字段**(fixpoint 引擎一次跑完,无迭代深度概念) |

### 5.12 §5 显式 deferred / pending 项

| 项目 | 状态 |
|---|---|
| `fg.eval.why_not` 是否作 first-class API(还是完全废弃)| pending — explain 落定后审查用户场景是否被覆盖 |
| `fg.eval.run` Phase 3 删除 | 触发 = `read.match` 锁定 |
| `fg.what_if.*` 四个 shells 重构或废弃 | 触发 = explain 完成后单独决策 |
| head 内 ports 重命名机制(`Rule.projection(out_user="user")` 之类) | v2 deferred |
| head 与 expr 在跨 Rule 上下文的 Var 隔离审计 | pending(随 §7 evidence 同步 audit) |
| `EvaluateResult.explain(row)` 主入口 | 已落地为 Wave 1 API contract(C65/C66);不再 deferred |
| `inspect.is_closed` 判定扩展:通用 field literal constraint(情形 c)/ transitive equality(情形 d)/ 跨 port Var 等价(情形 e)| v2 视实际误判情况扩展;同时需 specify field-to-port 的解析规则 |
| `fixed_timesteps` / `valid_time_boundaries` 旧名 deprecation warning 期 | 若用户社区有遗留代码;alpha 期可直接 hard cut |
| `time_binned` 支持 open universe / auto-from-facts 推断 | 简化 ergonomic 触发 |
| `time_binned` + `fact_boundaries` 复合模式(混合机制)| 复杂时间场景 |
| ProbLog 是否引入 `temporal_projection`(虽 ProbLog 无原生时间)| 用户出现"时间感知 ProbLog" 用法 |
| 跨引擎 fact uncertainty projection 一致性 | engine swap / multi-engine 场景 |

---

## 7. Evidence Tree(详细设计已迁出 — 独立文档)

> **本章已完整迁出** 至独立设计文档:
>
> **`docs/references/working/design-points/evidence-tree-rainbird-style-v1.zh.md`**
>
> 创建于 2026-05-18(Phase A skeleton);状态:§1 立场 / §2 词汇 / §3 架构 / §13 承诺 落地,§4-§12 / §14 [SKELETON pending] 待 Phase B 推进。

### 7.1 迁出理由

- 主文档已 1500+ 行;evidence 详细设计预计 500-700 行,合并后过长
- Evidence 设计有独立生命周期(Rule / RuleExpr / Head 已锁,evidence 在演进)
- 模式与 `database-view-fg-layered-architecture.zh.md` 一致(view 子系统独立设计文档)
- 便于后续 PyReason Form 2 evidence 独立设计

### 7.2 本文档与 evidence 文档的引用关系

- **主文档**(本文档)持有 Rule / RuleExpr / Head / `.eval` namespace API 设计权威(§3-§5)
- **Evidence 文档** 持有 Phase 2 evidence tree 设计权威(自身 §3-§14)
- 主文档 C61-C70(`.eval` namespace + Explanation form)在 evidence 文档 §13.1 引用
- 主文档 **原 §7.12 / C79-C81**(status 归属决策)已**迁至** evidence 文档 §13.2

### 7.3 主文档保持的 evidence-touching 承诺(锁定不变)

| # | 承诺 | 主文档位置 |
|---|---|---|
| C15 | Phase 1 候选 + Phase 2 按需 evidence 两阶段架构 | §3.13 |
| C16 | Rule.atoms / atom_id / eval_atom / render_desc Phase 2 introspection 表面 | §3.13 |
| C19 | atom_id 格式 `<rule_id>:atom_<index>` | §3.13 |
| C60 | head.desc 在 evidence 顶部 narrative anchor | §5.11(主文档 §5.6)|
| C61-C70 | `.eval` namespace + evaluate / explain / EvaluateResult / Explanation form | §5.11 |
| C67 | Explanation 4-state status 沿用 CheckStatus;evidence 统一为 EvidenceGraph | §5.11 |

### 7.4 Phase A 迁出工作总结(2026-05-18 完成)

- 主文档原 §7.1-§7.4(Step 0 re-aligned 内容)→ 迁入 evidence 文档 §3
- 主文档原 §7.12(C79-C81 决策)→ 迁入 evidence 文档 §13.2
- 主文档原 §7.5-§7.13 占位章节 → 由 evidence 文档 §4-§14 [SKELETON pending] 替代
- C81 在 evidence 文档 §13.2.4 标有 **修订预告**(Phase B / §9 锁定时 expand 至 `failed` 也归 evidence=None;主文档 §7 stub 期间 C81 文字与原版保持兼容)

### 7.5 PyReason Form 2 evidence(时间步)

> **本节状态**:Phase A skeleton 阶段未推进;待 Form 1(Datalog-style)evidence 文档 Phase B 落定后,独立推进或并入 evidence 文档 §14 deferred 项目展开。

---

## 8. 引擎能力对照与 lower 策略

> **本节状态**:Phase B-1 迁入落定 2026-05-18(原 evidence-tree-rainbird-style-v1.zh.md §4.9 adapter 实现状态 + §4.11.2 grammar 对照 + §4.11.3 negation lowering 迁入本节)。引擎 evidence schema 仍由 evidence 文档持有(C82-C89 / C91)。

### 8.1 设计立场

- **v1 unified IR grammar 跨 Form 1 引擎 portable** — 用户 Rule.where 写法在 Souffle / ProbLog 之间保持一致,**不应出现 "engine X 能用 engine Y 不能" 的设计性差异**
- **PyReason 是 Form 2** — engine 原生只支持 `pred` + bounds + 时序 + `~atom`;v1 限 pred-only;Form 2 evidence + Form 2 grammar 独立设计
- **Adapter 实现 gaps** 是 Phase C 工作,非设计性差异;v1 实现阶段补齐

### 8.2 Grammar 原生支持对照表

> v1 IR atom kinds canonical 名单见 §10;本节锁定**跨引擎原生支持**。

| IR atom | Souffle 原生 | ProbLog 原生 | PyReason 原生 | v1 Form 1 portable | 备注 |
|---|---|---|---|---|---|
| `pred(User(u))` | ✓ `user(u)` | ✓ `user(u)` | ✓ `user(u) : [bounds]` | ✓ **三引擎都直通** | bound 标注是 PyReason 专属;Form 1 默认 `[1,1]` |
| `eq(u.status, "active")` | ✓ `s = "active"` | ✓ `s = active` 统一 | ✗ **engine-level 无原生**;必须预编码为 fact | ✓ Souffle / ProbLog | PyReason 用户需写 `is_active(u)` 派生 fact |
| `ne(u.region, "BAN")` | ✓ `r != "BAN"` | ✓ `R \== ban` | ✗ engine-level 无原生 | ✓ Souffle / ProbLog **(adapter gap 待补)** | 两 adapter 当前均未实现 dispatch;Phase C 工作 |
| `gt(u.age, 18)` | ✓ `age > 18` | ✓ `Age > 18` | ✗ engine-level 无原生 | ✓ Souffle / ProbLog | PyReason 用户需写 `age_gt_18(u)` 派生 fact |
| `ge / lt / le` | ✓ | ✓ | ✗ engine-level | ✓ Form 1 | 同上 |
| `in(u.region, ["US", "DE"])` | ✓ via `;` 析取 | ✓ `member/2` 或 `;` | ✗ engine-level | ✓ Form 1 | PyReason 不直通 |
| `not(banned(u))` | ✓ `!banned(u)` stratified NAF | ✓ `\+ banned(u)` Prolog NAF | △ `~banned(u)` 但**语义差**(详 §8.4)| ✓ Souffle / ProbLog | v1 IR `not` 不映射 PyReason `~` |

**用户 v1 portability 规则**:
- **Form 1 Rules**(用 9 kinds)→ **Souffle ↔ ProbLog 直通**(完成 adapter `ne` gap 后);PyReason **不支持非 pred kinds**
- **PyReason Rules**(v1 限 pred-only)→ Form 2 设计未到位前,用户写 PyReason 适配的 Rules 要预先派生为 pred(如 `is_active(u)` 取代 `u.status == "active"`)
- **混合用法**:同一 Rule 用 Form 1 grammar 后在 PyReason engine 上跑 → adapter 抛 `PyReasonWhereCompileError`(不静默)

### 8.3 Adapter 实现状态(grounded 核查 2026-05-18)

| atom kind | Souffle adapter(`adapters/souffle/where_compile.py`)| ProbLog adapter(`adapters/problog/problog_export.py`)| PyReason adapter(`adapters/pyreason/where_compile.py`)|
|---|---|---|---|
| `pred` | ✓ line 445 / 668 / 906 / 1089 | ✓ line 213 | ✓ line 117 |
| `eq` | ✓ line 469 / 676 / 925 / 1094 | ✓ line 238 | ✗ raise line 129-130 |
| **`ne`** | **✗ 未实现**(IR schema 声明但 dispatch 缺失;`package.py:36` 列出但 `where_compile.py` 无 dispatch)| **✗ 未实现** | ✗ raise(其他全 raise generic line 135-137)|
| `gt` / `ge` / `lt` / `le` | ✓ line 517 / 696 / 883-889 / 971 / 1104 | ✓ line 243 | ✗ raise |
| `in` | ✓ line 498 / 686 / 954 / 1100 | ✓ line 249 | ✗ raise |
| `not` | ✓ line 553 / 707 / 1114 | ✓ line 259 | ✗ raise line 131-132 |
| `add` / `sub` / `neg` / `addc` / `mulc`(IR-internal,ArithExpr lower 目标)| ✓ line 720-740 / 1030-1042 | **✗ 未实现** | ✗ raise |
| **ArithExpr(`+` / `-` / `*` / `/`)in eq/gt/... RHS / LHS**(§10.6.2)| ✓ via add/sub/neg/mulc lowering | **✗ 未实现** — 需 `is/2` 重写 ~100 行 | ✗ N/A(Form 2)|
| **AggregateExpr(count/sum/min/max/mean)in eq/gt/... RHS / LHS**(§10.6.3)| ✓ Souffle 原生 `count`/`sum`/`min`/`max`/`mean` aggregate body | **✗ 未实现** — 需 `findall/3` + list predicates ~150 行 | ✗ N/A(Form 2)|

**v1 实现 gaps 清单**(Phase C 工作):
1. **Souffle adapter `ne` dispatch**(~50 行)— 复用现有 `eq` lowering 模式,改 operator
2. **ProbLog adapter `ne` dispatch**(~50 行)— 用 Prolog `\==`
3. **Souffle adapter ArithExpr lower wire**(~50 行)— 已有 add/sub/neg/mulc 5 个 sub-kinds dispatch,需把 ArithExpr 树形 lower 到 3-address 形态接入
4. **ProbLog adapter ArithExpr dispatch**(~100 行)— 用 `is/2` 计算 RHS;支持 div-by-zero 软失败(per C98)
5. **Souffle adapter AggregateExpr lower wire**(~150 行)— 已有原生 count/sum/min/max/mean,需 wire 到新 AggregateExpr lowering + filter clause embedding
6. **ProbLog adapter AggregateExpr dispatch**(~150 行)— `findall/3` + `length/2` / `sum_list/2` / `min_list/2` / `max_list/2` + 自定义 mean(derived from sum/count)+ AggregateNoValue 处理
7. **PyReason adapter 维持 pred-only**(不补;Form 2 独立设计)

**Phase C 工作量预估**:~550 行总(Souffle ~250 / ProbLog ~350)。

**`add` / `sub` / `neg` / `addc` / `mulc` 5 sub-kinds 状态**:**IR-internal**(用户不直接构造;ArithExpr lower 时生成);Souffle 已 ship;ProbLog v1.x deferred(待 ArithExpr 整体 v1 ship 后这 5 sub-kinds 在 ProbLog 也通过 ArithExpr 路径间接 ship)。

### 8.4 Negation 语义差异 + lowering matrix

**符号统一**(v1 IR):用 `not(atom)`(英语单词,与各 engine 原生符号解耦)

**Lowering matrix**:

| Engine | 映射符号 | 语义 |
|---|---|---|
| Souffle | `!atom` | **2-valued stratified NAF**;atom 无 derivation → success;stratification 强制(circular negation 禁止)|
| ProbLog | `\+ atom` | **Prolog NAF over derivation**;goal 失败 → success;**不否定概率值**(关键 — `\+ 0.7::p(a)` 不变成 `0.3`)|
| PyReason | (**v1 不映射**)| 若映射:`~atom`,但需 `add_closed_world_predicate(...)` 显式声明;semantics 是 interval-valued(`[0,0]` 才算 success);**与 Form 1 boolean NAF 本质不同** |

**关键结论**:
- v1 IR `not` 在 **Form 1**(Souffle / ProbLog)内**语义等价**(都是 2-valued NAF over derivation)— **统一符号 `not` 安全**
- ProbLog NAF **不否定概率值**(important caveat:用户需理解 `\+0.7::p(a)` 是判 derivation 失败,不是 1-0.7=0.3)
- PyReason `~` **不进 v1 IR**(Form 2 独立设计;PyReason v1 用 pred-only Rules,无 `not`)
- 文档应**显式标注**:Form 1 `not` 在 closed-world 假设下成立

### 8.5 §8 设计承诺 Commitments(C94-C96)

| # | 承诺 |
|---|---|
| C94 | **Grammar 原生支持对照表锁定**(详 §8.2):Form 1 unified 9 kinds **Souffle ↔ ProbLog 直通**(adapter `ne` gap 待 Phase C 补);PyReason 限 pred-only(Form 2 独立设计,本节不锁);用户使用前查表对照,Rule 跨 Form 1 engine portable 保证 |
| C95 | **Negation 符号统一为 `not`**(v1 IR);Lowering matrix:Souffle `!atom` / ProbLog `\+atom`(Form 1 内 2-valued NAF over derivation 语义等价;ProbLog 不否定概率值);**PyReason `~atom` 不进 v1 IR**(语义本质不同,interval-valued + closed_world);Form 2 设计单独锁定 PyReason negation(详 §8.4)|
| C96 | **Adapter 实现 gaps 清单**(Phase C v1 工作):Souffle `ne` + ProbLog `ne` 补 dispatch(~100 行总,复用现有 eq lowering 模式);arith(`add` / `sub` / `neg` / `addc` / `mulc`)v1.x deferred(ProbLog adapter 不支持 `is/2`,需重写)— 触发条件 = ProbLog adapter 升级 + 用户实际算术原子诉求(详 §8.3)|

### 8.6 § 8 显式 deferred 项

| 项目 | 触发条件 |
|---|---|
| ~~arith atom kinds adapter 实现~~ → **已 promoted v1**(C98 ArithExpr,详 §10.6.2) | — |
| **ArithExpr overflow / NaN / inf protection**(`OverflowProtectionError` / `NaNCheckError`)| 用户出现实际数值异常诉求(v1 沿用 Python 默认行为)|
| **Aggregate `mod` operator + 其他 ArithExpr operators**(`%` / `**` / 位运算)| 用户出现实际数值运算诉求 |
| **Compound case full ArithExpr-AggregateExpr 多重嵌套**(C106 `compound_comparison` reason 内部 schema 完整化)| 用户出现复合表达式实际诉求 |
| **Aggregate implicit cast / parse**(string-to-numeric 等)| 用户出现实际场景 |
| **AggregateExpr v1.x 扩展 kinds**:`any` / `all` / `isSubset` / `join` / `first` / `last`(详主文档 §10.2)| 用户业务诉求 |
| PyReason engine 扩展支持 Form 1 grammar(预编码翻译机制)| Form 2 设计完成后评估是否值得加 |
| 字符串 atom kinds(contains / startswith / matches)| 用户业务场景需求 |
| 时间 atom kinds(between / before / after)| 时序业务出现 |
| Per-engine evidence schema 差异化(超出 layout_hint 区分)| 现 layout_hint + engine_meta 不够用时 |

### 8.7 ArithExpr Lowering(per engine)

> 锁定的语法形态详 §10.6.2(C98);本节描述 per-engine adapter lowering 策略,无新 commitment。

**Souffle**:
- 已有 5 sub-kinds(add/sub/neg/addc/mulc)dispatch(`adapters/souffle/where_compile.py:720-740, 1030-1042`)
- ArithExpr 树形 → 3-address sub-atoms(lowering pass at IR layer);Souffle 已支持
- div(`/`):Souffle 用 `number_eq` + `number_div`;**div-by-zero 处理**:Souffle 默认行为是 number_div(x, 0, _) silently fails(无 derivation)→ 符合 C98 "atom violated 不抛 exception"

**ProbLog**:
- adapter 当前无 ArithExpr dispatch(Phase C 工作,~100 行)
- ArithExpr 树形 → ProbLog `is/2`(`X is Y + Z`)
- div(`/`):ProbLog 用 `/` 在 `is/2` 内;**div-by-zero 处理**:ProbLog `is/2` 抛 `evaluation_error(zero_divisor)` → adapter catch 转为 NoValue / atom violated(符合 C98)
- ArithExpr lower 策略:递归 traverse 表达式树,生成 `X1 is ...`, `X2 is ...`, 最终 `RESULT is f(X1, X2, ...)` 序列

### 8.8 AggregateExpr Lowering(per engine)

> 锁定的语法形态详 §10.6.3(C99);本节描述 per-engine adapter lowering 策略,无新 commitment。

**Souffle**:
- 原生支持 `count` / `sum` / `min` / `max` / `mean` 在 aggregate body(`count : { ... }` syntax)
- adapter 当前无 AggregateExpr dispatch(Phase C 工作,~150 行)
- AggregateExpr → Souffle aggregate body:`Var("v") = sum X : { filter_atoms }`
- filter clause → aggregate body 内 atoms
- empty set:Souffle aggregate over empty body 返回 0 for count/sum;min/max/mean 无值时 binding 失败 → adapter wrap 为 NoValue 符合 C101

**ProbLog**:
- 原生支持 `findall/3`(标准 Prolog),但无单一 aggregate primitive
- adapter 工作流(~150 行):
  - `findall(TargetExpr, BodyConjunction, List)` 收集匹配
  - `length(List, Count)` / `sum_list(List, Sum)` / `min_list(List, Min)` / `max_list(List, Max)` 聚合
  - `mean` 自定义:sum_list + length 后 `Mean is Sum / Count`(注意 div-by-zero)
  - empty list:adapter 检测 length=0 → 对应 kind 行为(count/sum=0,min/max/mean=NoValue)

**PyReason**:
- 原生不支持 aggregates(Form 2 范围,本节不锁)
- adapter v1 raise 错误(同其他非 pred kinds)

### 8.9 Aggregate Empty Set Behavior Convergence

跨 engine 的 empty set 行为 **必须收敛** 到 C101 锁定的语义:
- count / sum:返回 0(numeric)— Souffle / ProbLog 自然行为一致
- min / max / mean:返回 AggregateNoValue sentinel — **adapter wrap 工作**:
  - Souffle min/max over empty body 不绑定 result → adapter 检测并产出 NoValue
  - ProbLog `min_list([], _)` 失败 → adapter catch 并产出 NoValue
  - 用户面统一(NoValue 始终不参与 binding,致 comparison violated)

**Phase C 实现验证清单**:Souffle / ProbLog adapter empty set test cases(unit tests 必备)。

---

## 10. Atom Language 闭合

> **本节状态**:Phase B-1 迁入落定 2026-05-18(原 evidence-tree-rainbird-style-v1.zh.md §4.9 v1 9 atom kinds 名单迁入)。

### 10.1 v1 IR canonical atom kinds(9 kinds)

| kind | ir_arity | 例 narrative | 用例 |
|---|---|---|---|
| `pred` | 3(`("pred", pred_id, terms)`)| `"User(u-2)"` / `"region(u-2, DE)"` | 实体存在 / 关系匹配 |
| `eq` | 3(`("eq", lhs, rhs)`)| `"u-2.status == 'active'"` | 等值约束 |
| `ne` | 3(`("ne", lhs, rhs)`)| `"u-2.region != 'BAN'"` | 不等约束 |
| `gt` | 3(`("gt", lhs, rhs)`)| `"u-2.age > 18"` | 大于比较 |
| `ge` | 3(`("ge", lhs, rhs)`)| `"u-2.age >= 21"` | 大于等于 |
| `lt` | 3(`("lt", lhs, rhs)`)| `"u-2.score < 100"` | 小于比较 |
| `le` | 3(`("le", lhs, rhs)`)| `"u-2.score <= 50"` | 小于等于 |
| `in` | 3(`("in", var, collection)`)| `"u-2.region in ['US', 'DE']"` | 集合成员 |
| `not` | 2(`("not", inner_atoms)`)| `"not banned(u-2)"` | NAF 否定(stratified)|

**关键性质**:
- `ne / gt / ge / lt / le / in` 是**约束 atom**(过滤 envs);不引入新 Var 绑定
- `pred` 是**扩展 atom**(绑定新 Var + 过滤 envs)
- `not` 是**嵌套 atom**(内部含一组 atoms;Form 1 内 2-valued NAF semantics)
- `eq` 兼具**约束 + 绑定**(若 LHS / RHS 任一是未绑定 Var,则绑定)

**IR 表示形式**:`("kind", ...)` tuple,详 `src/factgraph/core/rules/where_eval.py`。

### 10.2 v1.x 扩展候选(deferred)

| 类别 | atom kinds | 触发条件 |
|---|---|---|
| 算术 | `add` / `sub` / `neg` / `addc` / `mulc` | ProbLog adapter 升级 + 用户算术原子诉求(详 §8.5 / C96)|
| 字符串 | `contains` / `startswith` / `endswith` / `length` / `matches`(正则)| 用户业务字符串需求 |
| 时间 / 日期 | `between` / `before` / `after` | 时序业务需求(可降到比较 atom)|
| 聚合 | `count` / `sum` / `mean`(v2+)| 大规模聚合诉求 |
| 自定义 functor | 用户定义谓词 | 用户自定义谓词诉求(详 evidence doc §4.8 AtomKindSpec registry)|

### 10.3 v1 不包含 atom kinds 的理由

| 不在 v1 的 kind | 理由 |
|---|---|
| `arith` 类 | ProbLog adapter 未实现 `is/2`;违反"Form 1 跨 engine portable" 原则;v1.x 待 ProbLog 升级 |
| `ruleref` | **旧范式遗物**(主文档 §3.6 / C9 已 hard-cut);新 paradigm Rule 间交互**唯一通过 RuleExpr 组合 + port join**;不出现 ruleref atom |
| 字符串 / 时间 / 聚合 | 业务实用性确认前不引入;adapter 实现成本中高 |
| `~atom`(PyReason interval-valued NAF)| 语义与 Form 1 boolean NAF 本质不同;Form 2 独立设计(详 §8.4 / C95)|

### 10.4 §10 设计承诺 Commitments(C97)

| # | 承诺 |
|---|---|
| C97 | **v1 IR canonical atom kinds = 9 个**(`pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in` / `not`,详 §10.1);ir_arity 与 IR tuple 形态固定;`arith` 类 v1.x deferred(ProbLog adapter 限制);字符串 / 时间 / 聚合 v1.x+ deferred;`ruleref` **不存在**(per C9 新 paradigm);`~atom` PyReason interval-valued NAF 不进 v1 IR(详 §8 + evidence doc §4.11.1 / C91)|

### 10.5 §10 显式 deferred 项

详 §10.2(扩展候选 + 触发条件)。

### 10.6 ArithExpr / AggregateExpr Expression Forms(C98-C105 锁定)

> **本节状态**:Phase B-1 锁定 2026-05-18。表达式形态 + 语义全锁;具体 engine lowering 详 §8.7 / §8.8;evidence reason 形态详 evidence-tree-rainbird-style-v1.zh.md §4.5 / C106。

#### 10.6.1 立场:表达式 vs Atom Kind

- ArithExpr / AggregateExpr 是 **value-producing expressions**(产值表达式),**不是 atom kinds**
- 自身**无 truth value**;true/false 来自包裹的 comparison atom(eq / ne / gt / ge / lt / le)
- atom kind 空间保持 9 个(C97 不变);表达式只是 LHS / RHS 的内容形态扩展

#### 10.6.2 ArithExpr 形态(C98)

**v1 operators**:`+` / `-` / `*` / `/`(Python operator overloading)

**用户面 authoring**(Python ergonomic):
```python
where=[
    User(u),
    User(u).score < User(u).age * 0.7 + 5,    # gt atom + nested ArithExpr RHS
    Var("total") == User(u).a + User(u).b,    # eq atom + ArithExpr RHS(binding)
]
```

**IR shape**(扩展 eq / gt / ne / etc 的 LHS / RHS):
- 接受 `Literal` / `Var` / `AttrRef` / `ArithExpr` / `AggregateExpr`(嵌套)
- ArithExpr 内部:`("add", left, right)` / `("sub", left, right)` / `("mul", left, right)` / `("div", left, right)`

**Div-by-zero 语义(锁定)**:
- 构造期:**不拒绝**(denominator 可能是 runtime Var)
- evaluate / match 路径:atom violated;**不抛 process-level exception**;不污染 env;其他 envs 继续
- explain 路径:NODE_PREMISE.reason 含 `error_kind: "division_by_zero"` + `divisor_value` + `divisor_repr`(详 evidence doc C106)

**其他算术异常**:
- overflow / NaN / inf 沿用 Python 行为(v1)
- 显式 protection(`OverflowProtectionError` / `NaNCheckError`)v1.x deferred

#### 10.6.3 AggregateExpr 形态(C99)

**v1 5 kinds**:`count` / `sum` / `min` / `max` / `mean`

**用户面 authoring**:
```python
where=[
    User(u),
    Var("total") == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
    Var("total") > 1000,
    Var("count") == agg_count(Order(o), where=[Order(o).buyer == u]),
    agg_mean(Order(o).amount, where=[Order(o).buyer == u]) > 100,
]
```

**IR shape**:
```python
# AggregateExpr 是 value-producing,出现在 comparison atom LHS / RHS
("agg_sum", target_expr, filter_atoms)
("agg_count", target_expr, filter_atoms)
("agg_min", target_expr, filter_atoms)
("agg_max", target_expr, filter_atoms)
("agg_mean", target_expr, filter_atoms)
```

**自身无 truth value**:`agg_sum(...)` 单独不构成 atom;必须出现在 comparison(`agg_sum(...) > 1000`)或 eq binding(`Var("v") == agg_sum(...)`)。

#### 10.6.4 Aggregate Filter Restrictions(C100)

**Filter clause 形态**:`list[Atom]`(flat,无 OR group)

**允许 atom kinds**(9 IR kinds 子集 — pred / eq / ne / gt / ge / lt / le / in / **not**):

| filter 顶层 atom kind | 允许? |
|---|---|
| pred / eq / ne / gt / ge / lt / le / in / not | ✓ |
| Rule reference / ruleref | ✗ |
| RuleExpr 嵌套 | ✗ |
| AggregateExpr | ✗(filter 内不可含聚合)|
| ArithExpr | ✗(filter atoms 必须纯 scalar 比较,LHS/RHS 仅 Var / Literal / AttrRef)|

**`not` body 递归限制**(防绕过):

| not body atom kind | 允许? |
|---|---|
| pred / eq / ne / gt / ge / lt / le / in(8 kinds)| ✓ |
| **`not`**(嵌套 not)| **✗**(v1 简化;`not(not(p))` 用 `p` 等价写法)|
| Rule / RuleExpr / AggregateExpr / ArithExpr | ✗ |
| OR group | ✗(body 必须 flat list)|

**违反 → 构造期 raise `AggregateValidationError`**(消息含具体违反点 + filter atom 位置)

#### 10.6.5 Empty Set + AggregateNoValue 语义(C101)

| AggregateExpr kind | empty set 结果 | 类型 |
|---|---|---|
| `count` | `0` | int(合法值)|
| `sum` | `0` | numeric(合法值)|
| `min` / `max` / `mean` | `AggregateNoValue` | sentinel(单例)|

**`AggregateNoValue` 行为**(锁定):
- **不参与任何 binding**(`Var("v") == NoValue` → atom violated,v 保持 unbound)
- **任何 comparison 含 NoValue → violated**(`NoValue > x` / `NoValue == x` / `NoValue != x` 均 false / violated)
- **不抛异常,不污染 env**(其他 envs 继续)
- **JSON 序列化**:推荐 `{"__aggregate_no_value__": true}` marker(避免与 null 混淆)

**ArithExpr 内 NoValue 传播**:若 ArithExpr operand 为 NoValue → 整个 ArithExpr 结果为 NoValue(传染性,fail-stop)

#### 10.6.6 Numeric Target Type(C102 修订版)

**sum / mean target 必须 numeric**。

**构造期校验**:
- 若 target 静态显然不是 numeric-producing expression(例如 target 是 string literal / 已知 non-numeric AttrRef)→ raise `AggregateValidationError`
- 若 target 静态无法确定(例如 target 是 untyped Var)→ 不拒绝,留运行期判定

**运行期校验**:
- 若某个 matched row 的 target value 非 numeric / 非 bool:
  - evaluate / match 路径:当前 aggregate-containing atom **violated**,**不污染 env,不中断其他 env**
  - explain 路径:reason 含:
    - `error_kind="aggregate_target_type_error"`
    - `offending_value`(具体非 numeric 值)
    - `offending_value_type`(Python type repr)
    - `target_repr`(target expression 文本)

**count / min / max** 对 target 类型放宽:
- `count` 不取 target value,只数 matched rows
- `min` / `max` 接受 numeric + date + 任何 orderable(`<` 可比类型)
- 违反 orderable → 运行期 `aggregate_target_type_error`

**implicit cast / parse v1.x deferred**(详 §10.5)

#### 10.6.7 Snapshot Semantics(C103)

`matched_count` = view-projected fact rows count(与 `project_view_facts` 一致)。

- **不**是 ledger 原始 assertion 数(否则同 fact 多 assertion 时 double-count)
- evaluator 在 projected view 上算 count(C103 锁定 evaluator 行为)
- 与 read snapshot 心智一致(per 主文档 §5 read pathway)

#### 10.6.8 Variable Scoping(C104)

Aggregate filter 中两类变量:

| 类型 | 定义 | 作用域 |
|---|---|---|
| **Correlated outer var** | 在 aggregate 出现处已绑定(来自外层 Rule.where 早期 atoms)| filter 内可引用,值由外层 env 注入 |
| **Aggregate-local var** | filter 内新引入(未在外层绑定)| **仅 aggregate 内部可见**;不泄漏外层 env |

**示例**:
```python
where=[
    User(u),                                                      # u 外层绑定
    Var("total") == agg_sum(
        Order(o).amount,                                          # o aggregate-local
        where=[Order(o).buyer == u]                                # u correlated, o local
    ),
    # 此处 o 不可见(已 out-of-scope)
    User(u).other_field == "x",                                   # u 仍可见
]
```

**违反**(filter 内新 var 试图泄漏外层)→ 构造期 `AggregateVariableScopeError`

#### 10.6.9 Result Binding(C105 修订版)

`Var("v") == AggregateExpr(...)` 行为:

```python
if aggregate_result is AggregateNoValue:
    # atom violated;v 保持 unbound;env 不变
    return []  # 无 extension
elif v is unbound in current env:
    # 沿用 _eval_eq_atom:bind v = aggregate_result
    new_env = {**env, v: aggregate_result}
    return [new_env]
else:
    # v 已绑定:equality check
    if env[v] == aggregate_result:
        return [env]
    else:
        return []  # violated
```

**关键**:NoValue 永远 fail-stop;binding 仅在 result 是 concrete value 时发生。

#### 10.6.10 §10.6 Commitments(C98-C105)

| # | 承诺 |
|---|---|
| C98 | **ArithExpr** 是 value-producing expression(非 atom kind);出现在 comparison atom(eq/ne/gt/ge/lt/le)的 LHS / RHS;v1 operators:`+` / `-` / `*` / `/`(Python operator overloading);算术语义与 Python 一致 **除 div-by-zero 例外**;**div-by-zero**:构造期不拒绝;evaluate 路径 atom violated 不抛 process exception 不污染 env;explain 路径 reason 含 `error_kind="division_by_zero"`(详 evidence doc C106);overflow / NaN / inf 沿用 Python v1 行为,显式 protection v1.x deferred |
| C99 | **AggregateExpr** 是 value-producing expression(非 atom kind);出现在 comparison atom LHS / RHS;v1 kinds:`count` / `sum` / `min` / `max` / `mean`;agg 自身无 truth value(true/false 来自包裹 comparison 或 eq binding)|
| C100 | **Aggregate filter clause** v1 形态 = flat `list[Atom]`(无 OR group);允许 atom kinds:9 IR scalar kinds(pred / eq / ne / gt / ge / lt / le / in / not);**禁止 in filter atoms 或 sub-position**:Rule 引用 / RuleExpr 嵌套 / aggregate 嵌套 / ArithExpr 在 filter scalar 位置;**`not` body 递归限制**:仅 8 kinds(去 `not` 嵌套)/ 无 OR group / 无 AggregateExpr / 无 ArithExpr / 无 Rule;违反 → 构造期 `AggregateValidationError` |
| C101 | **Empty set 语义**:count/sum → 0(合法 numeric);min/max/mean → `AggregateNoValue` sentinel(单例);**AggregateNoValue 不参与 binding**(unbound Var == NoValue → 不绑定);**任何 comparison 含 NoValue → violated**;不抛异常,不污染 env;**ArithExpr 内 NoValue 传染**(operand NoValue → 结果 NoValue);JSON 序列化用 `{"__aggregate_no_value__": true}` marker |
| C102 | **Aggregate numeric target type**:sum/mean target 必须 numeric;**构造期**:静态显然非 numeric → `AggregateValidationError`;静态未知留运行期;**运行期**:matched row target 非 numeric/bool → evaluate 路径 atom violated 不污染 env;explain 路径 reason 含 `error_kind="aggregate_target_type_error"` + `offending_value` + `offending_value_type` + `target_repr`(详 evidence doc C106);count target 无类型约束;min/max 接受 orderable;implicit cast v1.x deferred |
| C103 | **Aggregate snapshot 语义**:matched_count = view-projected fact rows count(与 `project_view_facts` 一致);**非** ledger 原始 assertion count;evaluator 在 projected view 上算 |
| C104 | **Aggregate variable scoping**:filter 引用外层已绑定 vars = correlated;filter 内新 vars = aggregate-local,仅 aggregate 内部可见,**不泄漏外层 env**;违反 → 构造期 `AggregateVariableScopeError` |
| C105 | **Aggregate result binding**:`Var("v") == AggregateExpr(...)` 行为:if result is `AggregateNoValue` → atom violated,v 保持 unbound,env 不变;elif v unbound → bind v = result(沿用 `_eval_eq_atom`);elif v bound → equality check;**NoValue 永远 fail-stop**(C101 协同)|
