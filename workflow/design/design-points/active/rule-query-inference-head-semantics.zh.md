# Rule / Query / Inference Head Semantics Design Note

- Status: working / future optimization direction
- Authority: non-authoritative reference note; not current implementation truth
- Created: 2026-05-12
- Intended Use: post-release redesign input
- Related Current Docs:
  - `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
  - `src/kernel/sdk/docs/04_api_surface.en.md`
  - `src/kernel/application/protocol/derivation.py`

## 1. 摘要

这份文档记录一次关于 `Rule` / `Query` / `Inference` 三层定位的设计讨论。
结论不是“当前实现错误”，而是：

```text
三者的执行语义基本可用，但产品心智模型存在错位。
```

当前三者共享一套 `where` / branch / atom 语言，但用户面对的是三个不同
构造类和三种不同结果面：

| Surface | Shape | 当前定位 | 结果 |
| --- | --- | --- | --- |
| `Query` | `head + where` | 读取、pattern match、projection | rows / entity snapshots |
| `Rule` | `select + where + id/version` | 命名关系模板，可 `RuleRef` 复用 | rows；可有 rule trace |
| `Inference` | `head + where + id/version` | 生成或证明一个结论 | `CandidateSet[]` + evidence/provenance pointer |

问题主要出在 “head-like” surface 的语义重叠：

- `Query.head` 实际是 projection / return contract。
- `Rule.select` 实际是 relation signature / exposed columns。
- `Inference.head` 实际是 conclusion / goal / candidate target。

因此用户会自然地问：为什么不能只定义一套 pattern，然后在调用时决定是
query、run rule、还是 prove / infer？

## 2. Release Stance

这部分不建议阻塞近期发布。

原因：

- 当前行为有明确文档和测试边界。
- 这不是一个小命名修补，而是会牵动 SDK mental model、evidence API、
  `CandidateSet` 命名、Rule trace / candidate evidence tree 关系，以及
  possibly public protocol 的 redesign。
- 发布前若强行改，风险高于收益。
- 更务实的做法是先保持 current behavior，发布后用独立 blueprint 处理。

近期只应做两类低风险动作：

1. 在文档中更清楚地区分 projection、relation signature、conclusion。
2. 如有必要，在教程层面推荐“论点证明”使用 `Inference` 的 conclusion head，
   并说明 candidate 不一定需要 accept 到数据库。

## 3. 当前三层的真实边界

### 3.1 Query

`Query` 是读取面。它回答：

```text
在当前 store 中，哪些绑定满足这个 pattern？我想返回哪些字段或实体？
```

它的 `head` 不是真正的逻辑 head，而是返回契约：

```python
Query(
    head=[User(u), User.name(locale=loc, name=nm)],
    where=[User(u), u.locale == loc, u.name == nm],
)
```

这里的 `head` 更接近：

```text
projection = [User(u), User.name(...)]
```

它不产生 `CandidateSet`，也不进入 evidence tree / accept lifecycle。

### 3.2 Rule

`Rule` 是命名关系。它回答：

```text
我把一个 pattern 命名成一个可复用关系，并暴露哪些列？
```

```python
Rule(
    id="q_user_country",
    version="1.0.0",
    select=[u, c],
    where=[LivesIn(li), li.user == u, li.country == c],
    expose=True,
)
```

`select` 不是 conclusion，而是这个 named relation 的 signature：

```text
q_user_country(u, c) :- LivesIn(li), li.user = u, li.country = c
```

它可以被 `RuleRef` 引用，也可以直接 `run(rule)` 得到 rows。Rule 还有单独
的 rule trace 生态，但它不是 candidate evidence tree 的根。

### 3.3 Inference

`Inference` 是 conclusion / goal 面。它回答：

```text
如果 body 成立，我要证明或生成哪个结论？
```

```python
Inference(
    id="claim.supported",
    version="1.0.0",
    where=[...],
    head=Claim.supported(claim=c, supported=True),
)
```

这个 `head` 才是传统意义上最接近 rule head 的东西。它会生成
`CandidateSet`，并通过 `support_digest` / `support_kind` 指到
`SupportArtifact` 或 provenance envelope。candidate 可以被 accept，也可以只
作为 proof-backed result 被查看。

## 4. Head 相关的核心碰撞

### 4.1 同名 `head` 承载了两种不同语义

`Query.head` 和 `Inference.head` 用户表面相似，但意义不同：

```text
Query.head     = return projection
Inference.head = conclusion / proved statement
```

这会导致用户误以为 Query 也应该能产生 evidence，或者 Inference 只是另一种
query。实际上 current implementation 中，只有 inference candidate 才进入
完整 evidence / provenance pipeline。

### 4.2 `Rule.select` 避开了 head 名称，但没有避开心智混淆

`Rule.select` 命名上比 `head` 更像 projection，但 Rule 又可以被 `RuleRef`
当作 relation 使用，所以它同时像：

- query template
- relation definition
- reusable rule body
- what-if rule mutation target

这使得 `Rule` 的产品定位最容易摇摆。更准确的概念名可能是
`RelationRule`、`NamedRelation` 或 `PredicateTemplate`，但当前不建议发布前改名。

### 4.3 Inference 的 `head` 让“论点证明”变得可行，但表达上反常识

我们之前讨论过，“derivation / inference 不只是推出新数据库事实”，它也可以
用于证明一个以 fact 形式表达的论点。例如：

```text
Claim.supported(claim_123, True)
Requirement.satisfied(req_007, True)
Obligation.violated(control_9, True)
Finding.severity(finding_3, "high")
```

这些结论不一定要 accept 到数据库。candidate 本身已经可以作为
proof-backed answer。这个方向是成立的，但它要求用户把“判断”建模成一个
entity field / predicate head，而不是自由证明任意 formula。

这与 SMT / AWS ARC 风格不同：ARC 更像是把 policy 当作公式集合，然后在调用时
给 claim；当前系统更像是把 claim 编译进 `Inference.head`。

## 5. CandidateSet 的命名漂移

当前 `CandidateSet` 已经超越“待写入的新 fact”：

```text
CandidateSet =
  conclusion payload
  + run identity
  + stable candidate key
  + support/provenance pointer
  + confidence summary
  + accept lifecycle state
```

因此在“论点证明”场景里，它更像：

```text
ProofResult / InferenceResult / SupportedConclusion
```

继续叫 candidate 的问题是，用户容易误解为必须 `accept()` 才有价值。事实上，
对于 judgment / claim proof，evaluate 后得到的 candidate 就已经是一个可消费
结果，accept 只是把它写回 store 的额外选择。

## 6. Evidence 的归属问题

当前 evidence tree 的主要入口是：

```text
Inference -> CandidateSet -> support_digest -> candidate_evidence_tree
```

这使 evidence tree 的根是 candidate result，而不是自由 standing proof。

这个模型有实际优势：

- 每个 result 都有稳定 identity。
- evidence 可以和 accept lifecycle、audit package、candidate key 绑定。
- recursive `RuleRef` support 可以挂在 candidate evidence tree 下。

但它也带来产品心智成本：

- 用户想“查看一个 query 的证明路径”时没有自然入口。
- Rule trace 和 candidate evidence tree 是两套东西。
- what-if / check 接近 proof workflow，但仍然围绕 `Inference`。

未来可以考虑把概念重心从 candidate 调整为 result/proof：

```text
InferenceResult
  value / conclusion
  support pointer
  evidence tree
  accept state (optional)
```

这样 candidate 只是 result 的一种 lifecycle state，而不是整个 explainability
生态的唯一概念入口。

## 7. 可能的未来模型

一个更清晰的长期方向可能是先统一 body / pattern，再分离 execution surface：

```text
Pattern / PolicyTemplate:
  where / branches / atoms

Execution surfaces:
  fg.query(pattern, projection=...)
  fg.rule(pattern, select=..., id=..., expose=...)
  fg.infer(pattern, conclusion=..., id=...)
  fg.check(pattern, claim=..., binding=...)
```

或者保守一点，不引入新类，只在文档和 facade 上改口径：

```text
Query.head       -> documented as projection
Rule.select      -> documented as relation signature
Inference.head   -> documented as conclusion / goal
CandidateSet     -> documented as proof-backed inference result
Evidence tree    -> documented as result explanation
```

发布后若要真正 redesign，可以分阶段：

1. 文档先改名词，不改 API。
2. 新增 facade，例如 `fg.evidence.tree(candidate_or_result)`。
3. 新增 alias / helper，例如 `Conclusion(...)` 或 `Goal(...)`，不破坏旧
   `Inference.head`。
4. 再评估是否需要统一 `Rule` / `Query` / `Inference` 构造器。

## 8. 风险和不变量

未来如果采用 “body-only template + call-time head / claim” 的模型，需要处理：

- head 变量是否都被 body 绑定。
- conclusion schema lowering 何时发生。
- candidate key 是否包含 call-time head。
- audit record 如何记录 `template_id + callsite_goal`。
- RuleRef memo / trace / recursion key 是否也要包含 projection/head。
- evidence root 如何区分 body support 和 conclusion projection。
- accept lifecycle 如何绑定到 late-bound conclusion。

这些都说明这不是发布前适合动的大块。

## 9. 当前建议

当前建议是：

```text
不改实现；先发布；把这个问题作为 post-release API / evidence redesign 输入。
```

发布前若需要补充文档，只补“解释性文档”，不要调整 public behavior：

- 明确 `Query.head` 是 projection。
- 明确 `Rule.select` 是 relation signature。
- 明确 `Inference.head` 是 conclusion / goal。
- 明确 candidate 可以不 accept，尤其适合“论点证明”场景。
- 明确 evidence tree 当前绑定在 candidate / inference result 上，而不是所有
  query / rule run 都有统一 tree。
