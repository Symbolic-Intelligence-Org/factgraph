# Rule namespace redesign: application 层重命名为 RuleSpec(未来工作)

- Status: working / **current mode locked**(application `Rule` 占名 + SDK 必须用 `build_application_rule(...)`)/ **future direction open**(rename to `RuleSpec` + SDK shadow `Rule`)
- Authority: candidate design / non-authoritative reference;现状描述属实,未来方向属设计空间
- First draft: 2026-06-02
- Last updated: 2026-06-03(加入 `Claim` 同名占用 + `rule.id` 强制 predicate id 两类 instance)
- Scope: `factgraph.application.protocol.Rule` 与 `factgraph.sdk.build_application_rule(...)` 之间的层级与命名分裂;user-facing SDK Rule namespace 的重设计;扩展覆盖 RuleExpr OR `branch_id` 匿名化、`Claim` cross-layer 同名占用、`rule.id` 强制为 ledger predicate id 三类同源 ergonomic gap
- Parent: 与 [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md) / [`fields-iterable-value-batch.zh.md`](fields-iterable-value-batch.zh.md) 同级;均属 SDK 用户面 ergonomic 设计空间
- Design intent: 把"`Rule(when=[User(u), ...])` 直接构造不被支持,必须经 `build_application_rule(...)` 这条 lowering 显式可见"、"`RuleExpr` OR `branch_id` 是合成 `c{idx}`,丢失 Rule.id / occurrence alias 语义"、"`Claim` 在 `factgraph.core.store.ledger` 和 `factgraph.application.protocol.evaluate_result` 两层都存在但字段不同"、"`rule.id` 被强制 match ledger predicate id,user 不能自由命名"四类同源 friction 从用户面文档(`docs/quickstart/rules.md` / `docs/quickstart/engines_and_configs.md` / `docs/quickstart/evaluate_and_evidence.md` / `docs/quickstart/data_model.md`)抽出来,作为 SDK 命名与层级重设计的 future direction 记录

---

## §1 当前模式:application `Rule` 占名 + SDK 必须经 `build_application_rule(...)`

`factgraph.application.protocol.Rule` 是 frozen DTO,`when` 只接 core atoms(`PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom`),拒绝 SDK DSL 形态(`User(u)` / `User(u).field == v` / `Pred(...)` / `Case` / 裸 `AttrRef`)。

`factgraph.sdk.build_application_rule(...)` 是 SDK 层 ergonomic factory,做 4 件事:
1. Lower Entity-DSL atoms → core atoms
2. Reject 不支持的形态(OR branch list, `Case`, raw `Pred`, 裸 `AttrRef`)
3. Canonicalize `Var` instances(同名 → 同 canonical Var,支持跨 occurrence join)
4. Validate `ports`(non-empty + 每个 port var 必须在 `when` 出现)

**`factgraph.sdk.__init__.py`** 把 application `Rule` 顶层 re-export:

```python
from factgraph.application.protocol import (
    ...
    Rule,                # = factgraph.application.protocol.Rule(application DTO)
    ...
)
ApplicationRule = Rule   # legacy alias
```

也就是说 user `from factgraph.sdk import Rule` 拿到的是 **application 层 DTO**,而**不是** ergonomic shell。

## §2 现状的根源(三条强约束)

### §2.1 INV-6 application-first runtime authority(架构 invariant)

来自 [`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md):

> 所有新增 runtime capability 先以 DTO + pure function 形式落在 `factgraph.application` 层;SDK 仅作为 product surface / ergonomic shell,**不携带 substrate**。

层级关系:`factgraph.sdk` → `factgraph.application` → `factgraph.core`,反向依赖(application → sdk)被显式 reject。

具体到 Rule:`Rule.__post_init__` 不允许 import / 引用 SDK 层的 `ExistsAtom` / `CompareExpr`,否则 application 反向依赖 SDK。

### §2.2 命名占用

application 层 DTO **直接占用了 "Rule" 这个最直观的名字**,这跟 codebase 已有的 SDK-shell / application-DTO 命名模式**不一致**:

| application 层(canonical DTO) | SDK 层(user-facing ergonomic shell) |
|---|---|
| `SemanticsProfile` | `ProbLogSemantics` / `PyReasonSemantics` |
| `EntityWriteCommand` | `FactGraph.entities.create / fields.set / ...` |
| `EvaluateResult` / `EvaluateRow` / `Explanation` | (consumed via `fg.eval.evaluate(...).first()` 等访问) |
| **`Rule` ← 占了用户最想要的名字** | **(无 — 只能叫 `build_application_rule(...)`)** |

`SemanticsProfile` 是命名良性的:application 层用中性名,SDK 层 `ProbLogSemantics` / `PyReasonSemantics` 拿到 `*Semantics` 这个 user-facing 名字空间。

Rule 是命名占名的:application 层抢了 `Rule`,SDK 层无路可走,只能用更长的 `build_application_rule(...)`。

### §2.3 historical 路径

Track 1 Branch identity + rule inspect(2026-05-12,`milestone/branch-identity-rule-inspect-2026-05-12 @ 03f76380`)把 application protocol `Rule` shipped 时,采用了"application-first per 项目固定原则 + SDK alias `kernel.sdk.Rule`"这个候选(per archived design-point `rule-expression-and-proof-track-plan.zh.md` TPQ-1)。当时的决策是直接使用 `Rule` 作为 application 层 class 名,SDK alias 只是 re-export,这导致今天 SDK 无独立 ergonomic shell class 可用。

## §3 用户当下的 friction

### §3.1 第一次撞墙:直接 `Rule(when=[Entity-DSL])`

```python
with vars("u", "age") as (u, age):
    rule = Rule(
        id="adult",
        when=[User(u), User(u).age == age, age > 18],   # ← Entity-DSL syntax
        ports={"user": u, "age": age},
    )
# RuleValidationError: when must be non-empty tuple[Atom, ...]   (list rejected)
#                      / when[0] must be one of PredAtom/CmpAtom/InAtom/BuiltinAtom/NotAtom
```

用户从 quickstart 看完 `build_application_rule(...)`,自然假设 `Rule(...)` 也能接 Entity-DSL —— 实际不能。这是 user mental model 第一次撞硬边界。

### §3.2 第二次撞墙:Inference 承接性缺失

Inference(legacy)接受 `when=[Pred(...) / Case(...) / SDK DSL atoms]`,新 Rule + RuleExpr 设计**故意不承接**这个形态。但 user 看 `from factgraph.sdk import Rule, Inference` 两个并列 import,自然预期它们 API 一致 —— 实际 `Inference(when=[...])` 接受 list of SDK DSL,`Rule(when=tuple)` 只接 core atoms tuple。

### §3.3 第三次撞墙:命名分裂

`fg.entities.create(...)` / `fg.fields.set(...)` / `fg.eval.evaluate(...)` 这些 user-facing API 都用 short ergonomic 名字。唯独 rule 构造要写 `build_application_rule(...)` 这种暴露 internal layer 名字的形态。

### §3.4 第四次撞墙:RuleExpr OR `branch_id` 匿名化

构造 RuleExpr OR 表达式时,user 自然期望分支用 operand 的 identity(Rule.id / occurrence alias)命名:

```python
r_us = build_application_rule(id="in_us", when=[...], ports={"user": u})
r_de = build_application_rule(id="in_de", when=[...], ports={"user": u})
expr = r_us | r_de

fg.eval.evaluate(expr, head=..., config=ProbLogConfig(
    case_probabilities={"in_us": 0.7, "in_de": 0.3}   # ← user intuition
))
# SDKStoreError: unknown branch id 'in_us' for ProbLogConfig.case_probabilities
```

Shipped 行为只接受 `{"c0": 0.7, "c1": 0.3}` —— branch_id 由 lowering 合成。Source([`src/factgraph/application/protocol/rule_expr_lowering.py:720-723`](../../../../src/factgraph/application/protocol/rule_expr_lowering.py)):

```python
def _assign_branch_ids(branches: tuple[RuleExprLoweringBranch, ...]) -> tuple[...]:
    if not branches:
        raise RuleExprError("RuleExpr lowering produced no branches")
    return tuple(replace(branch, branch_id=f"c{idx}") for idx, branch in enumerate(branches))
```

3 个具体问题:

- **匿名性**:`c0` / `c1` 不读取任何 user-written 信息(operand 的 Rule.id 是 `"in_us"` / `"in_de"`,occurrence alias 在 `RuleExprInspect.occurrences` 里可见,但 `branch_id` 全部丢弃)
- **顺序敏感(silent fail)**:`r_us | r_de` 和 `r_de | r_us` 在 `case_probabilities` 视角是完全不同的(`c0` 和 `c1` 含义反转),但调用代码无任何 type-level 信号 —— `{"c0": 0.7, "c1": 0.3}` 在两种 expression 顺序下都不会报错,只是默默改变概率分配
- **承接性缺失**:Inference 用 `Case([...], id="seed_path")` 让 branch_id 有显式 author-written 语义;RuleExpr 把这条 ergonomic 路径丢掉了

这第四次撞墙跟前三次同类(shipped 架构 self-consistent,user mental model 撞硬边界),但跟 `Rule` 命名分裂是不同维度的 friction —— `Rule` 是声明层 namespace 问题,`branch_id` 是组合层 identity 派生问题。共同收纳在本 design-point 是因为两者:① 都属 RuleExpr / Rule 组合 surface 的同一族 SDK ergonomic gap,② 候选 fix 都不破坏 INV-6 application-first(只动 SDK 层 lowering 默认)。

### §3.5 第五次撞墙:`Claim` cross-layer 同名占用

两个**不同 module / 不同字段集**的 `Claim` class 都叫 `Claim`:

| 路径 | Module | 字段 | user 在哪儿见到 |
|---|---|---|---|
| ledger Claim | `factgraph.core.store.ledger.Claim` | `asrt_id, pred_id, e_ref, rest_terms` | `fg.ledger.find_claims()` 返回(参见 [`data_model.md §1`](../../../../docs/quickstart/data_model.md)) |
| protocol Claim | `factgraph.application.protocol.evaluate_result.Claim` | `kind, name, arguments, repr, digest` | `EvaluateRow.claim` 字段;SDK `from factgraph.sdk import Claim` re-export 的就是它(参见 [`evaluate_and_evidence.md §2.4`](../../../../docs/quickstart/evaluate_and_evidence.md)) |

具体撞墙形态:

```python
from factgraph.sdk import Claim
# user 期望:这是 ledger.Claim?还是 result-side?
# 实证:是 protocol.evaluate_result.Claim,不是 ledger.Claim

isinstance(row.claim, Claim)            # True — protocol Claim
isinstance(fg.ledger.find_claims()[0], Claim)  # False — that's ledger.Claim
```

User 读到 `row.claim` 时无法仅凭名字判定是"on-disk Claim"还是"result-side projection";要看字段(`asrt_id` 在?还是 `kind` 在?)才能 disambiguate。这跟 §3.1-§3.3 `Rule` 命名占用**完全同源** —— application protocol 层占用了 user-facing 的"Claim"名,ledger 层另一个不同字段集的同名 class 与之共存。

`Claim` 不同于 §3.4 branch_id 一类的 identity-derivation 问题,但跟 §3.1-§3.3 是**同一种 cross-layer naming 占用 friction**,候选 fix 也走同样的"重命名 application/internal 层 + 保留 user-facing 名给 SDK 那个"模式(见 §4.7)。

### §3.6 第六次撞墙:`rule.id` 强制为 ledger predicate id

> **Superseded by [`evaluate-result-flatten-and-query-style.zh.md`](evaluate-result-flatten-and-query-style.zh.md) §2.1 + §3.8 + Slice δ**(2026-06-03)。后者把 `rule.id` 解耦放进 query-style 范式转向的整体设计里 —— `head.id` 自由 + arity check opt-in,不再需要本节单独提的 `head_pred_id` 字段方案。本节内容保留作历史 friction 记录。

构造一条 Rule 时直觉是 `rule.id` 是 rule 的自由命名(如别的 rule engine 习惯的 `"is_adult"` / `"find_us_users"` / `"discount_calc"`)。但 shipped 拒绝这种形态:

```python
rule = Rule(
    id="find_us_users",       # ← 看起来很 normal 的 rule name
    when=(PredAtom(pred_id="user:region", terms=[u, r]),),
    ports={"user": u, "region": r},
)
fg.eval.evaluate(rule, head=rule)
# WhereValidationError: target predicate not found: find_us_users
```

Shipped 强制要求 `rule.id` **必须 match 某个已知的 ledger predicate id**(`entity:field` 或 `Entity:exists` 形态),否则 evaluate 直接拒绝。**rule identity 跟 ledger predicate identity 被强制重合**。

3 个具体问题:

- **rule 命名不自由**:user 想给 rule 一个语义清晰的名字(`"is_adult"`)就被拒,只能用 `entity:field` 形态(`"user:adult_flag"`)
- **观感泄露 internal 概念**:`row.bindings["pred_id"]` 永远长得像 `"user:region"`,user 误以为它"指某条 fact",其实那是 rule 自己的 id;同样 `EvaluateResult.head.id` / `row.claim.name` 都是这种形态
- **同 predicate 多 rule 命名空间冲突**:两条逻辑不同但 head 落同一 predicate 的 rule(`"user:adult_flag"` 的两种算法)只能靠 `version` 区分,或不得不写到不同 predicate 下

这第六次撞墙跟 §3.1-§3.3 `Rule` 命名占用、§3.5 `Claim` cross-layer 占名是同一家族 —— **shipped 把 user-facing identifier 强制绑到 internal layer 概念**。候选 fix 路径见 §4.7(配本节)。

## §4 未来设计空间:RuleSpec 重命名 + SDK 真 `Rule` shadow class

### §4.1 目标形态

```
factgraph/application/protocol/rule.py
    class RuleSpec:                            # ← 重命名(原 Rule)
        # frozen DTO,接 core atoms,不变
        when: tuple[Atom, ...]
        ports: Mapping[str, Var]
        version: str | None
        desc: str | None

factgraph/sdk/rule.py                          # ← 新文件
    class Rule:                                # ← user 看的唯一 Rule
        @classmethod
        def build(cls, *, id, when=[User(u), ...], ports={...},
                  version=None, desc=None) -> RuleSpec:
            # 调用现有 build_application_rule lowering
            ...

        @classmethod
        def from_atoms(cls, *, id, when=(PredAtom(...),), ports=...,
                       version=None, desc=None) -> RuleSpec:
            # 直接 RuleSpec(...) 构造
            ...

        def __new__(cls, **kwargs) -> RuleSpec:
            # 直接 Rule(...) 调用,自动 dispatch 到 .build(...)
            return cls.build(**kwargs)
```

User 视角统一:
- `Rule(when=[User(u), ...])` ← natural ergonomic 入口
- `Rule.build(when=[...])` ← 显式 named
- `Rule.from_atoms(when=(...))` ← 显式 raw atom 入口

返回值都是 `RuleSpec`(application DTO),下游 API(`fg.rules.inspect` / `fg.eval.evaluate` / `RuleExpr` 组合 / `match`)消费 `RuleSpec`,user 不需要直接接触 `RuleSpec` 这个名字。

INV-6 完全保留:`RuleSpec` 仍然不知道 SDK,所有 lowering 由 SDK `Rule` shadow class 承担。

### §4.2 命名候选评估

| 候选 | 评价 | 决议 |
|---|---|---|
| **`RuleSpec`** | 跟 `EmitSpec` / `SchemaAddResult` 等 `*Spec` 系列命名风格一致;user 一看就知是 specification | **adopted** |
| `RuleDef` | 直观,GraphQL-style;但 codebase 无 `*Def` 系列,引入新命名约定 | 备选 |
| `RuleIR` | 强调 intermediate representation;过于技术性 | rejected |
| `CompiledRule` | 暗示"未编译 Rule",反而误导(谁是源?) | rejected |
| `RuleEntity` | ⚠️ 与 `factgraph.sdk.Entity` schema base class 冲突 | rejected |
| `RuleTemplate` | 与 desc template 的 "template" 用法冲突 | rejected |
| `RuleStatement` | Datalog 风格;codebase 无 "statement" 约定 | rejected |

### §4.3 候选实施路径

**路径 A — RuleSpec 重命名 + SDK 真 Rule shadow class(本设计 preferred)**

- application:`Rule` → `RuleSpec`,所有 application-internal 引用跟着改
- SDK:新建 `factgraph.sdk.rule.Rule` shadow class,带 `.build()` / `.from_atoms()` / `__new__`
- SDK exports:`factgraph.sdk.Rule` 指向 shadow,新增 `factgraph.sdk.RuleSpec` export(advanced 路径)
- legacy:`build_application_rule(...)` 保留,内部转发到 `Rule.build(...)`,标 `DeprecationWarning`(可选)
- `ApplicationRule = Rule` alias 移除或重定义为 `ApplicationRule = RuleSpec`

**路径 B — 候选 (2) 的 SDK wrapper class(保留 application "Rule" 名字)**

- application:`Rule` 不变
- SDK:新建 wrapper class(必须用 import alias `_AppRule`)
- 命名 namespace 仍然有冲突,SDK 内部代码 readability 受损
- 比路径 A 改动小,但 ergonomic 改善有限

**路径 C — minimum surface(只重命名 `build_application_rule`)**

- application:不变
- SDK:`build_application_rule(...)` 加一个更短 alias(`compile_rule(...)` / `make_rule(...)`)
- 不解决"直接 `Rule(...)` 调用"问题
- 几乎不改 codebase,但只是 cosmetic

| 路径 | INV-6 兼容 | user ergonomic 收益 | breaking surface | 实施成本 |
|---|---|---|---|---|
| A (RuleSpec + SDK Rule) | ✓ | ★★★ | high(public Rule re-points) | high |
| B (SDK wrapper) | ✓ | ★★ | low | medium |
| C (rename factory) | ✓ | ★ | low | low |

### §4.4 待定设计问题(路径 A 展开)

1. **`Rule(...)` 直接调用 dispatch 策略**:用 `__new__` 转 classmethod、还是 metaclass 拦截、还是 documented `Rule.build()` only(不允许 `Rule(...)`)?
2. **`from_atoms` 跟 `RuleSpec(...)` 关系**:`Rule.from_atoms(...)` 应该是 `RuleSpec(...)` 的薄壳,还是真做额外 validation?
3. **`fg.rules.inspect(Rule)` vs `fg.rules.inspect(RuleSpec)`**:两者都能 inspect,还是 inspect 只接受 RuleSpec(因为 Rule 不是 value,是 factory)?
4. **`isinstance(x, Rule)` 语义**:用户写 `isinstance(rule_value, Rule)` 时 should be True or False?(rule_value 实际是 RuleSpec)
5. **`Inference` 的承接**:Inference 是否也跟着 SDK shadow → RuleSpec-like canonical DTO 重构,还是保持 legacy 不动?
6. **migration**:`from factgraph.sdk import Rule` 的语义改变,如何文档化 + warning + 兼容期?

### §4.5 子设计:RuleExpr `branch_id` 派生(配 §3.4)

**目标形态**:RuleExpr OR lowering 默认从 operand 的 identity 派生 `branch_id`,而不是合成 `c{idx}`。让 `r_us | r_de` 在 `case_probabilities={"in_us": ..., "in_de": ...}` 下 just works。

**候选派生优先级(precedence)**:

```
1. RuleOccurrence alias  (user 显式写 r.as_("alias") 时取 alias)
2. Rule.id               (默认,operand 是 application Rule 时取它)
3. fallback "c{idx}"     (派生冲突或 anonymous projection 时保留)
```

**未锁设计问题**:

1. **嵌套 RuleExpr**:`(a|b)|c` flatten 后,内层 `a|b` 的 branch_id 派生策略 — 仍走 alias/Rule.id,还是 concat(如 `"a|b"`)?
2. **同 rule 多次出现且无 alias**:`r|r` 时两个分支的 Rule.id 相同会冲突,如何 fallback(`r#0` / `r#1`?或强制要求 alias?)
3. **跟 Inference `Case.id` 的兼容**:Inference 的 branch_id namespace 是用户面 explicit 字符串(`"seed_path"`);RuleExpr 派生后是否合并到同一 namespace?如果合并,Rule.id 跟 Case.id 同名冲突如何处理?
4. **migration**:已经依赖 `c0` / `c1` 的 user 代码迁移(如果有)— 是否提供 backward-compat alias?
5. **unknown branch_id 错误信息**:列出 known ids 时显示派生 alias 还是 `c{idx}`?(目前显示 lowered 形式,user 看到的是 `c0` 不是 `in_us`,即使他在配置里写的就是 `in_us`)

**候选实施路径**:

| 路径 | 描述 | 代价 |
|---|---|---|
| α. 完全替换:派生作 default,`c{idx}` 仅 fallback | 最干净 user mental model,但破坏现有 `c0`/`c1` 调用 | 中等(`_assign_branch_ids` 重写 + reconciliation 改造 + 测试更新) |
| β. 双 namespace:同时接受派生 id 和 `c{idx}` | 兼容现有代码,user 新写可以用派生 | 低(reconciliation lookup 加 fallback 路径) |
| γ. 显式 opt-in:加 `ProbLogConfig(case_probabilities=..., branch_id_strategy="derived")` kwarg | 安全保守,但增 API surface | 低 但 ergonomic 收益受限 |

**Tier**: B(与本 design-point §4 RuleSpec 重命名同一 ergonomic 等级,跟 D21 desc-explain / `fields-iterable-value-batch` 同类)。

### §4.6 子设计:`Claim` 重命名(配 §3.5)

**目标形态**:解决 `factgraph.core.store.ledger.Claim` 与 `factgraph.application.protocol.evaluate_result.Claim` 跨层同名占用。

```
factgraph/core/store/ledger.py
    class Claim:              # ← 保留原名(就是 ledger row,叫 Claim 合适)
        asrt_id: str
        pred_id: str
        e_ref: str
        rest_terms: list[tuple[str, Any]]

factgraph/application/protocol/evaluate_result.py
    class ResultClaim:        # ← 重命名(原 Claim)
        kind: ClaimKind
        name: str
        arguments: Mapping[str, Any]
        repr: str
        digest: str

# SDK
factgraph.sdk.Claim → ResultClaim   # 保留 user-facing "Claim" 名给最 user-visible 的那个
                                     # 或保留 alias `Claim = ResultClaim` 一段时间
```

**命名候选评估**(application protocol 那个 class 的新名):

| 候选 | 评价 | 决议 |
|---|---|---|
| **`ResultClaim`** | 紧凑;明示 "result-side projection";`row.claim: ResultClaim` 读得通顺;跟 ledger Claim 区别清楚 | preferred |
| `EvaluateRowClaim` | 准确但过长;`row.claim: EvaluateRowClaim` 啰嗦 | 备选 |
| `ClaimProjection` | "projection" 字眼在 `ClaimKind` 枚举里已经用作一个 kind 值(`Rule.projection(...)` 产出),易混淆 | rejected |
| `EvalClaim` | 紧凑但 `EvalClaim` 跟 `fg.eval` namespace 风格不一致;太抽象 | rejected |
| `DerivedClaim` | 误导 — 字段 `kind="fact_triple"` 时它源自 ledger fact,不是 "derived" | rejected |
| `ProtocolClaim` | 暴露 internal layer 名;违反 SDK 隐藏层级原则 | rejected |
| `ClaimDTO` | DTO 后缀在 codebase 内不一致(`Claim` / `EvidenceRef` / `Explanation` 都不带);引入新命名约定 | rejected |

`ResultClaim` 与 §4.2 `RuleSpec` 是平行选择 — 都用 description-of-role 命名(Spec / Result),与 codebase 已有 `EmitSpec` / `EvaluateResult` 系列一致。

**未锁设计问题**:

1. **SDK re-export 策略**:`from factgraph.sdk import Claim` 是保留作 deprecated alias、还是直接换 `from factgraph.sdk import ResultClaim`?保留 alias 兼容性高但延长 ambiguity 期。
2. **`EvaluateRow.claim` 字段 attribute 名**:保留 `.claim` 让 `row.claim` 写法不变(只是 type 改了)还是改成 `.result_claim`?保留更兼容,attribute 名跟 class 名解耦。
3. **`Explanation.claim` 字段同步**:`Explanation.claim: Claim | None` 也用同一 class,rename 时一起改还是分开?一起改更一致。
4. **跟 §3.5 ledger Claim 的关系**:ledger Claim 是否也要重命名(如 `LedgerRow` / `LedgerClaim`)?**不**建议 — ledger Claim 就是 atomic ledger row,叫 Claim 是描述性的,且 user 通常不直接接触(走 `fg.ledger.find_claims()` 才见)。
5. **跟 `ClaimKind` enum 的关系**:enum 名是否也要改(`ResultClaimKind`?)?保留 `ClaimKind` 更紧凑,enum value `"projection"` 跟 `Rule.projection` 同名是另一个 confusing point(可选 future work)。

**候选实施路径**:

| 路径 | 描述 | 代价 |
|---|---|---|
| ε. rename + 保留 SDK `Claim` deprecated alias | 兼容现有 user code,平滑 migration;同步 rename `EvaluateRow.claim` type annotation | 中等 |
| ζ. rename + 立即移除 alias | breaking change | 低改动,高兼容代价 |
| η. 保留现状,文档显式标注两个 Claim 的区别(就像 `evaluate_and_evidence.md §2.4` 的 callout 那样)| 0 代码改动 | 0 / 长期 maintenance burden;不解决根本 friction |

**Tier**: B(与本 design-point §4 RuleSpec 重命名同一 ergonomic 等级)。

### §4.7 子设计:`rule.id` 与 ledger predicate id 解耦(配 §3.6)

> **Superseded by [`evaluate-result-flatten-and-query-style.zh.md`](evaluate-result-flatten-and-query-style.zh.md) §3.8 + Slice δ**(2026-06-03)。后者选择"`head.id` 自由 + arity check opt-in"路径(本节候选路径 φ 的等价),**不**引入本节路径 τ 的 `head_pred_id` 显式字段。下面的候选路径表和未锁问题保留作设计空间记录,但实施层面以后者为准。

**目标形态**:让 `rule.id` 是 rule 的**自由命名**,跟 head 落到哪个 predicate 解耦:

```python
rule = Rule(
    id="find_us_users",                                # ← user-defined name
    head_pred_id="user:is_us_user",                    # ← 显式 head target
    when=[...],
    ports={...},
)
fg.eval.evaluate(rule, head=rule)
# OK — rule.id 跟 head_pred_id 分开,各司其职
```

**候选实施路径**:

| 路径 | 描述 | 代价 |
|---|---|---|
| **τ. 加显式 `head_pred_id` 字段** | `Rule` 数据增加一字段,`evaluate` 用 `head_pred_id` 作 target,`rule.id` 自由 | 中等(Rule schema + evaluator 入口改)|
| υ. 不动 Rule schema,在 SDK 层加 `Rule.build(id=..., head=...)` wrapper 帮 user 选择 | 兼容性强,但 user 仍需理解 internal "id == pred_id" 巧合 | 低 但 ergonomic 收益有限 |
| φ. 让 `rule.id` 可以是任意字符串,evaluator 自动从 head 的 `PredAtom` 推 target pred_id | 不引入新字段,但隐式行为更多 | 低,但失去显式锚点 |
| χ. 保留现状,显式文档化 `rule.id` 实际就是 head pred_id | 0 代码改动,长期 maintenance burden | 0 / 高 |

**未锁设计问题**:

1. **跟 `head.id == head_pred_id` 的一致性**:`evaluate(rule_expr, head=...)` 的 `head` 参数本质是"哪个 rule 的 head 是输出";head_pred_id 应该让 `head.head_pred_id` 是 reconciliation 的 key,而不是 `head.id`?
2. **跟 `content_digest` 关系**:`content_digest` 当前 hash 包含 rule.id;如果 rule.id 解耦,digest 是否还稳定?
3. **跟 `:exists` emission 关系** (cross-ref [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md)):如果 Rule head 不再强制 entity:field 形态,`Entity:exists` 的 emission 路径是否要重新审视?
4. **migration**:已有 user code 假定 `rule.id == pred_id`(参 `data_model.md §1` / `rules.md` 例子)是否平滑可改?
5. **跟 RuleExpr `head=` reconciliation**(§3.4 / §4.5):`head_pred_id` 引入后,`head.id == occurrence.rule_id` 这条 inline 检测变成 `head.head_pred_id == occurrence.head_pred_id` 吗?

**Tier**: B(与本 design-point §4 RuleSpec 重命名同一 ergonomic 等级;跟 D21 desc-explain / `fields-iterable-value-batch` 同类)。

### §4.8 与其他设计的耦合

- 与 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md):无直接耦合,Rule 重命名不影响 Identity 语义
- 与 [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) D21 desc-driven explain:无直接耦合,但属同类"shipped 架构对,user mental model 体验有 friction"的 ergonomic gap
- 与 archived [`rule-expression-and-proof-track-plan.zh.md`](../archive/rule-expression-and-proof-track-plan.zh.md) TPQ-1:本设计 supersede TPQ-1 当年选择的"application-first per 项目固定原则 + SDK alias `kernel.sdk.Rule`"决策,提议 SDK alias 升级为独立 shadow class
- 与 [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md):并列的 shipped-vs-intent friction;`Claim` 命名问题(§3.5 / §4.6)跟 `:exists` Claim 不 emit 问题都涉及 Claim 概念,但是不同维度 — 前者是 cross-layer 同名,后者是 emission 缺失

## §5 当前位置的边界

| 属于本 design-point | 不属于 |
|---|---|
| application `Rule` 与 SDK 层 ergonomic shell 之间的命名/层级 friction | INV-6 application-first principle 本身(已锁,不在重设计 scope) |
| `RuleSpec` 命名候选评估 + 路径 A/B/C 实施权衡 | `Rule.when` 内部 atom 类型(`PredAtom` / `CmpAtom` etc.)的形态 |
| Inference 的 mental-model 承接性问题(§3.2) | Inference 本身的 legacy lifecycle(在 `docs/quickstart/rules.md` §6.1) |
| SDK `Rule.build` / `.from_atoms` / `__new__` dispatch API 表面 | RuleExpr / RuleOccurrence / RulePortRef 的**类名**(那是另一个 redesign scope) |
| RuleExpr OR `branch_id` 的派生 ergonomics(§3.4 / §4.5)| `branch_id` 在 evaluation 内部(non-config 路径)的用法 |
| `Claim` cross-layer 同名占用(§3.5 / §4.6)— 重命名 application protocol Claim 为 `ResultClaim` | `:exists` Claim emission(在 [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md));`ClaimKind` enum 重命名(future work,与 `Rule.projection` 冲突);ledger `Claim` class 名字本身(它就是 atomic row,叫 Claim 合适) |
| `rule.id` ↔ ledger predicate id 强制重合(§3.6 / §4.7)— 引入 `head_pred_id` 或等价机制让 `rule.id` 自由 | 任意 rule lifecycle / versioning 语义重设计(那是另一个 redesign scope) |

## §6 关联代码锚点

- `src/factgraph/application/protocol/rule.py:52-167` — `class Rule` 当前 application DTO 定义
- `src/factgraph/sdk/dsl/application_rule.py:46-82` — `build_application_rule(...)` 当前 SDK factory
- `src/factgraph/sdk/__init__.py:33-49` — application Rule 在 SDK 顶层 re-export(`Rule` + `ApplicationRule`)
- `src/factgraph/sdk/dsl/__init__.py:6-10` — `Pred` / `Not` / `agg_*` 等 SDK DSL atom factory
- `src/factgraph/sdk/dsl/expr.py:181-211` — `ExistsAtom` / `PredAtom` (SDK DSL form) / `CompareExpr` 等 SDK 层 atom 表示
- `src/factgraph/core/rules/where_ast.py:32-71` — `PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom` 等 core atom 类型
- `src/factgraph/application/protocol/rule_expr_lowering.py:720-723` — `_assign_branch_ids(...)` 当前合成 `c{idx}` 的入口(§3.4 / §4.5 修改目标)
- `src/factgraph/sdk/store.py:3352-3360` — `case_probabilities` 校验拒 unknown branch_id 的位置
- `src/factgraph/sdk/store.py:3562` — `case_indexes = {branch.branch_id: index for ...}`,reconciliation 实际使用 lowered `branch_id` 的位置
- `src/factgraph/core/store/ledger.py:22` — ledger `Claim`(`asrt_id` / `pred_id` / `e_ref` / `rest_terms`,§3.5 cross-layer 占名的一边,**保留原名**)
- `src/factgraph/application/protocol/evaluate_result.py:86` — application protocol `Claim`(`kind` / `name` / `arguments` / `repr` / `digest`,§3.5 cross-layer 占名的另一边,§4.6 重命名目标)
- `src/factgraph/sdk/__init__.py:35` — `Claim` SDK re-export 当前指向 protocol Claim(§4.6 rename 后 alias / 同步重命名)
- `src/factgraph/core/store/_evaluate.py:157` — `head_vars length must match target arg_specs` 校验(§3.6 head arity ↔ predicate id 强制 reflection 的入口)
- `src/factgraph/core/rules/where_eval.py` — `WhereValidationError: target predicate not found: <id>` 抛出位置(§3.6 rule.id ↔ ledger predicate id 强制重合的 enforcement 点)

## §7 关联文档

- 用户面 Rule 文档:[`docs/quickstart/rules.md`](../../../../docs/quickstart/rules.md) §2.6(直接 `Rule(...)` 构造的边界 + 与 `build_application_rule` 的 trade-off table)
- 用户面 engine/config 文档:[`docs/quickstart/engines_and_configs.md`](../../../../docs/quickstart/engines_and_configs.md) §3.2(`case_probabilities` 的 branch_id 来源表 + RuleExpr 走 `c{idx}` 的 shipped 行为)
- 用户面 evaluate 文档:[`docs/quickstart/evaluate_and_evidence.md`](../../../../docs/quickstart/evaluate_and_evidence.md) §2.4(`Claim` cross-layer name-collision warning callout)
- 用户面 data model 文档:[`docs/quickstart/data_model.md`](../../../../docs/quickstart/data_model.md) §1(ledger `Claim` 4-tuple 的文档化)
- 架构原则源:[`workflow/foundations/architecture_principles.md §2.1 Layer authority`](../../../foundations/architecture_principles.md)
- INV-6 引用 ADRs(reject 反向依赖 SDK 案例):
  - [`workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`](../../decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md) §3 / §4 reject reasons
  - [`workflow/design/decisions/active/2026-05-29_q-sys-b-revokes-migration-decision.md`](../../decisions/active/2026-05-29_q-sys-b-revokes-migration-decision.md) §4.1 lowering 路径
- 历史 TPQ-1 决策:[`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md`](../archive/rule-expression-and-proof-track-plan.zh.md) §T1.1(本设计提议 supersede 部分)
- 同级 design-point:
  - [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md)
  - [`fields-iterable-value-batch.zh.md`](fields-iterable-value-batch.zh.md)
- 同类 ergonomic gap(在 explanation-completion-roadmap):D21 desc-driven explain([`explanation-completion-roadmap.zh.md §6.6`](explanation-completion-roadmap.zh.md))
