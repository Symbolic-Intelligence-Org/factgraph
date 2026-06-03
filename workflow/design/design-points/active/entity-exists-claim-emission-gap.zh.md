# Entity `:exists` Claim 发射缺失(未来工作)

- Status: working / **current mode locked**(`fg.entities.create` 不 emit `:exists` claim,SDK 无 manual emit 路径)/ **future direction open**(emission 策略待定)
- Authority: candidate design / non-authoritative reference;现状描述属实,未来方向属设计空间
- First draft: 2026-06-03
- Last updated: 2026-06-03
- Scope: `<EntityType>:exists` Claim 在 `fg.entities.create` 后**不存在于 ledger 中**,导致 `build_application_rule(...)` + Entity-DSL 编译产物(它会 auto-prepend `PredAtom("User:exists", [u])`)在 evaluate 时不产生 row
- Parent: 与 [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md) / [`fields-iterable-value-batch.zh.md`](fields-iterable-value-batch.zh.md) / [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md) 同级;均属 SDK 用户面 ergonomic 设计空间
- Design intent: 把"用户面 canonical 写法 `build_application_rule(when=[User(u).field == v])` 在 shipped 里 evaluate 出 0 row"这件 friction 从用户面文档(`docs/quickstart/evaluate_and_evidence.md`)抽出来,作为 future work 记录;同时澄清 [`data_model.md`](../../../../docs/quickstart/data_model.md) §1.1 中"`:exists` auto-emitted on first `fg.entities.create`"的描述是 design intent,与 shipped 不符

---

## §1 现状

### §1.1 ledger 内容(实证)

```python
class User(Entity):
    user_id: str = Identity()
    region: str = Field()

fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.region, alice, "US")

list(fg.ledger.find_claims())
# [Claim(pred_id="user:user_id", ...),
#  Claim(pred_id="user:region", ...)]
# 注意:没有 Claim(pred_id="User:exists", ...)
```

### §1.2 Entity-DSL 编译产物

`build_application_rule(when=[User(u).region == r])` 经 lowering 后:

```python
rule.when
# (PredAtom(pred_id="User:exists", terms=[Var("u")]),         # ← auto-prepended
#  PredAtom(pred_id="user:region", terms=[Var("u"), Var("r")]))
```

Auto-prepend 发生在所有 `Entity(var)` / `Entity(var).field == v` / `Entity(var).field op v` 形态上,**无论 body 是否显式包含 `Entity(var)` 单独 atom**。

### §1.3 Evaluate 结果

```python
result = fg.eval.evaluate(rule, head=rule)
result.count()   # → 0
```

原因:`when[0]` 的 `PredAtom("User:exists", [u])` 在 ledger 中找不到匹配 claim,整个 body 不满足。

### §1.4 现有 SDK manual emit 路径(无)

- `fg.commit_assertions(...)` 仅 `FactGraph.attach(db)` Mode B 可用(per [`load_and_save.md`](../../../../docs/quickstart/load_and_save.md))
- `FactGraph.create + entities.create + fields.set` 默认路径无 `emit_exists=` flag
- `Ledger.append_assertion(...)` 是 core 层 API,SDK 未 re-export

## §2 与文档描述的差距

### §2.1 [`data_model.md`](../../../../docs/quickstart/data_model.md) §1.1

> **`:exists` Claim** | `<EntityType>:exists` (e.g., `User:exists`) | auto-emitted on first `fg.entities.create` | only via `fg.entities.delete` — direct retract raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`

"auto-emitted on first `fg.entities.create`" 是 **design intent**,与 shipped 不符。实证显示 `fg.entities.create` 后 ledger 仅含 Identity Claim(`user:user_id`),无 `:exists`。该 doc 行需要在 emission 落地或被显式 defer 后重新校准。

### §2.2 [`docs/official/kernel/quickstart/rules-and-inferences.md`](../../../../docs/official/kernel/quickstart/rules-and-inferences.md) §"Choosing the right head"

> ```python
> result = fg.eval.evaluate(user_exists, head=user_exists)
> assert result.first().claim.name == "User:exists"
> ```

实证 `result.first()` 返回 `None`,`assert` 失败。该示例假设 `User:exists` 在 ledger,但 shipped 不 emit。该 doc 块在 emission 落地前需要标注或重写。

### §2.3 [`src/factgraph/application/schema_runtime.py`](../../../../src/factgraph/application/schema_runtime.py) §58

> `<EntityType>:exists` Claim pred_ids — existence-claim transitional guard per ADR-IC §4.4.2.
> NOT part of INV-7c (per ADR-IC §4.4.2: `:exists` is not in idref_v1 hash compute).
> `:exists` co-emission and may retire when Step 2+ removes `:exists` per ADR-IC §4.4.2.

"co-emission" 暗示 `:exists` 应当跟 Identity Claim 一起 atomically emit。但实证 shipped 行为是 **不 emit**。"may retire when Step 2+ removes `:exists`" 暗示存在一个 Step 2 计划 —— 该计划的 status 与本 gap 的解决方案相关(emit vs. retire 是互斥的两条路)。

## §3 用户当下的 friction

### §3.1 `build_application_rule` canonical 路径 yields 0 rows

```python
# User-facing canonical 写法:
with vars("u", "r") as (u, r):
    rule = build_application_rule(
        id="user:region",
        when=[User(u).region == r],
        ports={"user": u, "region": r},
    )
result = fg.eval.evaluate(rule, head=rule)
# result.count() == 0   ← unexpected
```

用户写 [`rules.md`](../../../../docs/quickstart/rules.md) 推荐的 canonical 形式 → 0 row,**没有任何错误信息**指引根因。

### §3.2 唯一 workaround 是 advanced 形式

绕开 auto-prepend 必须用 [`rules.md`](../../../../docs/quickstart/rules.md) §2.6 advanced 路径直接构造 `Rule(when=tuple[PredAtom, ...])`:

```python
u, r = Var(name="u"), Var(name="r")
rule = Rule(
    id="user:region",
    when=(PredAtom(pred_id="user:region", terms=[u, r]),),  # 不含 User:exists
    ports={"user": u, "region": r},
)
result = fg.eval.evaluate(rule, head=rule)
# result.count() == 1
```

这违反 §2.6 "99% 的情况下,`build_application_rule(...)` 是正确的入口" 的定位。

## §4 候选方向

### §4.1 方向 A — 在 `fg.entities.create` emit `:exists`

落实 `data_model.md` §1.1 和 `schema_runtime.py:58` 描述的 design intent。

**未锁问题**:
1. 跨现有 ledger(已有 entity 但无 `:exists`)的 migration 策略
2. emit 在 application 层还是 SDK 层?(per INV-6 application-first)
3. 跟 Mode B `commit_assertions` 路径 emit 行为一致性
4. asrt_id 生成策略 — content-derived(`{pred_id}:{e_ref}`)还是 random
5. retract 行为 — 是否走 `:exists` transitional guard (`EXISTENCE_CLAIM_TRANSITIONAL_GUARD`)

### §4.2 方向 B — 从 `build_application_rule` lowering 移除 `User:exists` auto-prepend

让编译产物只含用户写的 atom,不自动添加存在性约束。

**未锁问题**:
1. 语义差异 — 用户写 `User(u)` 是否仍隐含"u 必须是已存在 User"?
2. 跟 `fg.entities.match(...)` 已有 entity-existence 检查的关系
3. 对 ProbLog / PyReason adapter 影响(它们消费 lowered atoms)
4. 跟 ADR-IC §4.4.2 "Step 2+ 移除 `:exists`" 计划的一致性

### §4.3 方向 C — 在 native evaluator implicit derive `:exists`

让 evaluator 看到任何 `entity:field` claim 时,implicit treat 它对应的 `Entity:exists` 为 true,不需要 ledger 中显式存在 `:exists` claim。

**未锁问题**:
1. 语义边界 — Identity Claim 是否足以触发 implicit exists?Field Claim 呢?
2. 跨 ProbLog / PyReason adapter 一致性
3. native engine 单点 vs. 所有 engine 共同行为

### §4.4 方向 D — 维持现状,显式标注用户面"build_application_rule 不能直接 evaluate"

明示 `build_application_rule` 是"future-form for evaluate, current-form for inspect/match",evaluate 路径用户需手工构造或走 Inference (legacy)。

**未锁问题**:
1. 跟 [`rules.md`](../../../../docs/quickstart/rules.md) §2.6 "99% build_application_rule" 定位冲突
2. 跟 explanation roadmap D11 / D20 / D21 等其它"shipped 跟 design 不符"的 ergonomic gap 同源,但本项跨入"功能不可用"等级,影响更大

### §4.5 路径权衡

| 方向 | INV-6 兼容 | breaking surface | 用户体验改善 |
|---|---|---|---|
| A. emit `:exists` | ✓(application 层 emit) | 低(纯加 claim,不改 API) | ★★★(canonical 写法直接 work) |
| B. 移除 auto-prepend | ✓(纯 SDK lowering 改) | 中(语义微变 — 用户面 `User(u)` 不再隐含存在性检查) | ★★(简化 lowering 但用户需要显式写 entity existence atom) |
| C. native implicit derive | ✓(纯 engine 行为) | 低(纯 evaluation 改) | ★★(canonical 直接 work,但跨引擎一致性需要单独验证) |
| D. 显式标注 | ✓(只动文档) | 0 | ★(用户被迫走 advanced 路径) |

倾向 **A**(吻合 design intent,代价最低)。

## §5 当前位置的边界

| 属于本 design-point | 不属于 |
|---|---|
| `<EntityType>:exists` Claim 是否 / 何时 emit | `:exists` Claim 在 Identity 体系中的语义角色(在 [`identity-mechanism-redesign.zh.md`](identity-mechanism-redesign.zh.md))|
| `build_application_rule(...)` lowering 中 entity-existence atom 的 auto-prepend 行为 | application Rule 整体 lowering pipeline(在 [`rules.md`](../../../../docs/quickstart/rules.md) §2.6 + ADR-API)|
| 与 [`data_model.md`](../../../../docs/quickstart/data_model.md) §1.1 / [`rules-and-inferences.md`](../../../../docs/official/kernel/quickstart/rules-and-inferences.md) 的 doc 差距 | doc 重写本身(那是各章节的 docs-vs-shipped drift fix 工作)|
| Native engine 是否 implicit derive `:exists` | ProbLog / PyReason adapter 是否 implicit derive(那是 adapter-level 决策)|

## §6 关联代码锚点

- `src/factgraph/application/entity_write.py:323` — `:exists Claims` 注释("legacy" 措辞暗示 emit 状态)
- `src/factgraph/application/entity_write.py:448` — `:exists` co-emission 路径描述
- `src/factgraph/application/schema_runtime.py:58-62` — `<EntityType>:exists` pred_ids + ADR-IC §4.4.2 transitional guard + "may retire" 注释
- `src/factgraph/sdk/dsl/expr.py` — `Entity(var)` / `Entity(var).field` 编译入口(`build_entity_dsl_call` / `ExistsAtom`)
- `src/factgraph/sdk/dsl/application_rule.py` — `build_application_rule(...)` 主入口,auto-prepend 发生处
- `src/factgraph/sdk/store.py` — `_evaluate` / `_inspect_rule` 主路径,无 `:exists` implicit derive

## §7 关联文档

- 用户面 evaluate 文档:[`docs/quickstart/evaluate_and_evidence.md`](../../../../docs/quickstart/evaluate_and_evidence.md) §1.1(`build_application_rule` canonical 写法 + shipped-status 警告 + §2.1 direct Rule workaround)
- 用户面 data model:[`docs/quickstart/data_model.md`](../../../../docs/quickstart/data_model.md) §1.1("auto-emitted on first `fg.entities.create`" 是 design intent,与 shipped 不符)
- 用户面 rule:[`docs/quickstart/rules.md`](../../../../docs/quickstart/rules.md) §2.6(direct `Rule(...)` 构造 — 当前唯一让 evaluate 出 row 的路径)
- 历史 ADR:`ADR-IC §4.4.2` — `:exists` 不在 idref_v1 hash 中,Step 2+ 计划提到 "retire `:exists`"
- 同类 ergonomic gap:
  - [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md)(`Rule` 命名 + branch_id 匿名化)
  - [`fields-iterable-value-batch.zh.md`](fields-iterable-value-batch.zh.md)
  - [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md)
- 同类设计未来工作:[`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) §6.6 (D21 desc-driven NL explain)
