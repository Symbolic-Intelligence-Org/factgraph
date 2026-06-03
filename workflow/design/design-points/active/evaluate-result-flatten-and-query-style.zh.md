# Evaluate-result DTO flatten + query-style 范式重设计

- Status: working / **target form locked draft** —— 已具备升级为 ADR + blueprint 的成熟度
- Authority: candidate design / non-authoritative reference;现状描述属实,目标形态属计划落地的设计空间
- First draft: 2026-06-03
- Last updated: 2026-06-03
- Scope: `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` 整个 DTO 体系的扁平化重设计;`rule.id` 与 ledger predicate id 解耦(Datalog → query 范式转向);provenance digest 集中为 `ResultFingerprint` sub-object;`Claim.repr` 走 desc 模板渲染
- Parent: 与 [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md) / [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md) 并列,**superseding** `rule-namespace-rulespec-redesign §3.6 / §4.7`(`rule.id` ↔ pred_id 解耦那一支)
- Design intent: 把"evaluate-result DTO 体系存在大量被抽象空转的 wrapper、被 D17 强制 invariant 镜像出来的冗余字段、以及无独立消费者的 provenance digest"这些 friction 集中扁平化处理;同时把"rule head 强制为 ledger predicate id"这条 Datalog 范式根问题一起解决(因为后者是前者的根)。整体目标是让用户面 evaluate-result 体系**信息量不减、surface 显著瘦身、概念跟随 query 范式自然清爽**

---

## §1 当前模式 — D17-T5.1 锁定的 Datalog-style + wrapper 嵌套

### §1.1 字段总览

```
EvaluateResult (13 user-facing fields)
├── rows: tuple[EvaluateRow, ...]
├── result_id, run_id                              # 2 identifiers
├── head: Rule
├── engine, engine_version, adapter_version        # 3 engine fields
├── expr_digest, rule_set_digest,
│   view_snapshot_digest, config_digest            # 4 provenance digests
├── evaluated_at
├── result_digest                                  # 1 master digest
└── _schema_index, _row_close_builder,             # 4 internal plumbing
    _row_support_artifacts, _row_provenance_envelopes

EvaluateRow (7 fields)
├── row_id, bindings, raw_kind, bound, _result_resolver  # 5 row-level
├── claim: Claim                                          # wrapper 1
└── evidence_ref: EvidenceRef                             # wrapper 2

Claim (5 fields)
├── kind, name, arguments, repr, digest

EvidenceRef (5 fields)
├── ref_id, result_id, row_id, fact_digest, closed_head_digest
```

总计:user-facing 25 字段 + 4 internal。

### §1.2 跟 ledger 层的 Datalog-style 绑定

`EvaluateRow` 被锁定为"`(rule body, ledger fact-set)` 满足绑定 → 在 head 的 predicate 下产出一条 fact"的载体。这条假设贯穿整个 DTO 体系:

- `Rule.id` 必须 match 某个已注册的 ledger predicate(`WhereValidationError: target predicate not found: <id>` 来自 [`core/store/_evaluate.py:150`](../../../../src/factgraph/core/store/_evaluate.py))
- `len(head.ports)` 必须 = predicate 的 arg_specs count(`head_vars length must match target arg_specs` 来自 [`_evaluate.py:157`](../../../../src/factgraph/core/store/_evaluate.py))
- `Claim.kind` 用 `"fact_triple"` / `"rule_head"` 等 Datalog 概念分流
- `Claim.name` = predicate id
- `Claim.arguments` = derived fact 的 term tuple
- `EvidenceRef.fact_digest` = 该 derived fact 的 content-address(== `Claim.digest`)
- `EvidenceRef.closed_head_digest` = closed-head Rule 的 content-address(用于 replay)

D17 §4.4 line 169 的原话:"D17 keeps the public eval claim in application protocol to avoid exposing ledger row shape as the user-facing explained fact." —— 当时的 intent 是把 row 当作"被解释的 fact",所以围绕"fact identity"建了 Claim wrapper,围绕"fact's evidence anchor"建了 EvidenceRef wrapper。

## §2 决策动机 — 4 类 friction 串成同一根藤

### §2.1 `rule.id` 强制 ledger predicate id 的 friction(撞墙实证)

```python
rule = Rule(
    id="find_us_users",     # ← 普通 rule 名字
    when=(PredAtom(pred_id="user:region", terms=[u, r]),),
    ports={"user": u, "region": r},
)
fg.eval.evaluate(rule, head=rule)
# WhereValidationError: target predicate not found: find_us_users
```

3 个用户面后果:
- rule 不能语义化命名(`"is_adult"` / `"find_us_users"` 都 reject)
- `row.bindings["pred_id"]` / `row.claim.name` / `result.head.id` 全都长得像 `"user:region"`,user 误以为"指某条 fact",其实只是 rule 自身的 id
- 多 rule 同 head predicate 时只能靠 `version` 区分

`build_application_rule(...)` 接受 free-form id(`rules.md` `adult_in_us` 例子),但 `evaluate` 时就拒。**问题不在命名,在 Datalog 范式本身**。

### §2.2 `Claim` wrapper 80% 字段冗余(name/arguments 重复 row.bindings + head.id)

| 字段 | 跟谁重复 |
|---|---|
| `Claim.name` | == `EvaluateResult.head.id` == `row.bindings["pred_id"]`(同 result 内所有 row 永远相同) |
| `Claim.arguments` | == `row.bindings`(几乎一字不差,只是 wrap 在不同名字下) |
| `Claim.kind` | 同 result 内通常恒定;形态上是 result-level 信息,被 D17 放 row-level |
| `Claim.repr` | 实现差(`"<name>{<dict 打印>}"`),应该走 desc 模板渲染但当前没用 |
| `Claim.digest` | **唯一不可替代字段**;cross-run dedup 用 |

Wrapper 实际承担的功能只有 `digest`(content-address)和 `repr`(label,待修)两个,其他 3 字段是 Datalog 模型 by-product。

### §2.3 `EvidenceRef` wrapper 80% 字段冗余(D17 invariant 镜像)

| 字段 | 跟谁重复 |
|---|---|
| `EvidenceRef.row_id` | == `EvaluateRow.row_id`(D17 [`evaluate_result.py:135-136`](../../../../src/factgraph/application/protocol/evaluate_result.py) 强制 invariant) |
| `EvidenceRef.fact_digest` | == `Claim.digest`(D17 [`evaluate_result.py:137-138`](../../../../src/factgraph/application/protocol/evaluate_result.py) 强制 invariant) |
| `EvidenceRef.result_id` | == 父 `EvaluateResult.result_id`(只在跨 process 序列化时不冗余) |
| `EvidenceRef.ref_id` | 可派生(其他 4 个字段的复合 hash);无独立逻辑消费者 |
| `EvidenceRef.closed_head_digest` | **唯一不可替代字段**;`fg.eval.explain(expr, head=closed_head)` replay key |

Wrapper 实际承担的功能只有 `closed_head_digest` 一个,其他 4 字段是 D17 自描述 serialization 选择的副产物(本身并无 cross-process consumer 实证 — 见 §2.5)。

### §2.4 EvaluateResult 7 个 digest/id 字段无独立消费者(实证 grep)

| 字段 | 实证消费点 | 用作 |
|---|---|---|
| `expr_digest` | [`evaluate_result.py:1163`](../../../../src/factgraph/application/protocol/evaluate_result.py)、[`:1252`](../../../../src/factgraph/application/protocol/evaluate_result.py)、[`sdk/store.py:2535`](../../../../src/factgraph/sdk/store.py) | 全是 metadata snapshot 进 dict;**无独立逻辑分支** |
| `rule_set_digest` | 同上 3 处 | 同上,跟 expr_digest **总是一起** snapshot |
| `view_snapshot_digest` | 同上 3 处 + 2 处 test assertEqual | 同上 |
| `config_digest` | 同上 3 处 | 同上 |
| `result_digest` | 仅 [`:1167`](../../../../src/factgraph/application/protocol/evaluate_result.py) metadata 打包 + `__post_init__` 校验 | **几乎无消费** |
| `run_id` | 仅 [`:198`](../../../../src/factgraph/application/protocol/evaluate_result.py) 校验;其他 `run_id` 实际是 `CandidateSet.run_id` 不是 result | **几乎无消费** |
| `result_id` | 被 `EvidenceRef.result_id` 引用 + metadata snapshot | 有用作 anchor |

7 个里 4 个总是一起 snapshot 进 dict,没有任何 consumer 做"expr_digest 变了没?"这种独立判断 —— 它们是 audit/provenance 数据,被消费的方式是"打包传走",不是"单独读取做判断"。

### §2.5 没有任何 cross-process EvidenceRef serialization 消费者实证

D17 §4.5 把 EvidenceRef 标记为"cross-process serializable handle",但实证 grep:
- `fg.audit.*` 都不接 EvidenceRef
- `fg.eval.explain(expr, head=closed_head)` 接 Rule 不接 EvidenceRef
- 测试代码不存在"序列化 EvidenceRef → 跨 process 传输 → 反序列化 → re-explain"模式

也就是说 EvidenceRef 的 cross-process 价值是**理论上的、为未来场景预留的**,**没有实际使用者**。这降低了它作为独立 DTO 的合理性。

### §2.6 4 件 friction 的共同根源

Datalog 模型 = "rule head 是一个 ledger predicate, row 是该 predicate 下的 derived fact" 这一假设 → 所有 friction 都从此生:
- §2.1 rule.id 必须是 predicate id —— **直接** Datalog 约束
- §2.2 Claim 围绕"fact identity"建,name/arguments 是 fact 的属性 —— Datalog by-product
- §2.3 EvidenceRef 围绕"fact's evidence anchor"建,fact_digest 是 fact 的镜像 —— Datalog by-product
- §2.4 provenance digest 用于 audit "what was the fact derived from?" —— Datalog 风格 audit 需求

**根不动,枝叶清不干净**。

## §3 目标形态(具体 schema,可直接实施)

### §3.1 EvaluateResult — 13 user-facing → 7 user-facing + 1 sub-object

```python
@dataclass(frozen=True)
class EvaluateResult:
    rows: tuple[EvaluateRow, ...]
    result_id: str                              # 主要稳定 anchor
    head: Rule
    engine: str
    evaluated_at: object
    engine_meta: Mapping[str, Any]              # {engine_version, adapter_version, ...}
    fingerprint: ResultFingerprint              # 折叠所有 provenance digest

    # internal plumbing 字段不变
    _schema_index: ...
    _row_close_builder: ...
    _row_support_artifacts: ...
    _row_provenance_envelopes: ...

    # 6 个 navigation 方法(__iter__ / __len__ / __getitem__ / first / exists / count)
```

减字段:`expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id` / `engine_version` / `adapter_version` 折叠成 `fingerprint` + `engine_meta`,EvaluateResult top-level surface 从 13 减到 7。

### §3.2 ResultFingerprint — 新增,集中所有 provenance digest

```python
@dataclass(frozen=True)
class ResultFingerprint:
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    config_digest: str | None
    result_digest: str
    run_id: str
```

访问路径:`result.fingerprint.expr_digest` 等。所有 audit / provenance metadata snapshot 仍然能从这里取出,只是 EvaluateResult top-level 不被它们污染。

### §3.3 EvaluateRow — 平铺 Claim/EvidenceRef 字段

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, object]              # {port_name: term} 直接 map(见 §3.6)
    kind: RowKind                                # 原 Claim.kind
    repr: str                                    # 原 Claim.repr,改用 desc 渲染(§3.7)
    digest: str                                  # 原 Claim.digest
    closed_head_digest: str                      # 原 EvidenceRef.closed_head_digest
    raw_kind: Literal["probabilistic", "possibilistic"] | None
    bound: tuple[float, float] | None
    _result_resolver: Callable[[], EvaluateResult] | None
```

净减:`row.claim` 整层 wrapper / `row.evidence_ref` 整层 wrapper 都消失;有用字段(kind/repr/digest/closed_head_digest)平铺到 row;冗余字段(name/arguments/fact_digest/row_id/ref_id/result_id)全部删除。

### §3.4 `Claim` DTO — 删除

跨 DTO 引用的字段(`Explanation.claim` 等)改为 inline EvaluateRow 关键字段(见 §4.1)。

### §3.5 `EvidenceRef` DTO — 删除

跨 process serialization 由 EvaluateRow 直接负责(EvaluateRow 是 frozen,可序列化;`_result_resolver` 不可序列化但 D17 已 mark `compare=False, hash=False`,序列化时自然 drop)。

### §3.6 `bindings` 形态简化为 `{port_name: term}` map

当前:
```python
row.bindings = {
    "pred_id": "user:region",
    "terms": [
        {"kind": "entity_ref", "value": "idref_v1:User:..."},
        {"kind": "literal", "tag": "string", "value": "US"},
    ],
}
```

目标:
```python
row.bindings = {
    "user":   {"kind": "entity_ref", "value": "idref_v1:User:..."},
    "region": {"kind": "literal", "tag": "string", "value": "US"},
}
```

User 直接 `row.bindings["user"]` 拿值,不用做 positional → port_name mental gymnastics。`pred_id` 从 bindings 删除(已经在 `EvaluateResult.head.id`)。term 内部仍是 `{kind, value, tag?}` typed dict(保持类型信息)。

### §3.7 `row.repr` 用 desc 模板渲染(承接 D21)

当前 `row.claim.repr` = `"user:region{'pred_id':'user:region','terms':[...]}"`(dict 打印,无用)。

目标 `row.repr` = `head.desc` template 用本 row 的 bindings 渲染后的字符串。例如 head.desc = `"User %user is in %region"` + row.bindings = `{user: alice_ref, region: "US"}` → `row.repr = "User alice is in US"`。

这就是 [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) §6.6 (D21) 提议的 "Explanation.desc_lines 自动 populate" 的等价能力,放在 `row.repr` 这个位置自然落地。

### §3.8 query-style evaluate head — `head.id` 自由 + arity check opt-in

`fg.eval.evaluate(rule, head=rule)` 的行为变化:
- `rule.id` 可以是任意合法字符串(`"adult_in_us"` / `"find_us_users"` 都 OK)
- `head` 不再被 lookup 成 schema predicate;evaluator 只用 head.ports 决定 result 行形态
- arity check 转为 **opt-in**:只在 head.id **恰好** match 某个 schema predicate 时才校验 `len(head.ports) == len(arg_specs)`;不 match 时纯 query 风格,不校验
- 现 [`core/store/_evaluate.py:150-157`](../../../../src/factgraph/core/store/_evaluate.py) 的两条 raise 改为 opt-in 路径

向后兼容:原先 `id="user:region"` 这种 match-predicate 风格仍然 work(走 opt-in 校验路径);新加 `id="adult_in_us"` 风格现在也 work(skip 校验)。

## §4 下游消费者的影响 & migration

### §4.1 `Explanation` — `claim` 字段平铺

当前:
```python
class Explanation:
    status: ExplanationStatus
    evidence: EvidenceGraph | None
    claim: Claim | None              # ← wrapper
    result_id: str | None
    row_id: str | None
    evidence_ref_id: str | None       # ← 跟 row.evidence_ref.ref_id 对应
    raw_kind: RawKind | None
    bound: tuple[float, float] | None
    failure_class: ...
    checked_scope: ...
    suggested_next_steps: ...
    errors: ...
    warnings: ...
```

目标:
```python
class Explanation:
    status: ExplanationStatus
    evidence: EvidenceGraph | None
    # claim 字段平铺:
    row_kind: RowKind | None
    row_bindings: Mapping[str, object] | None
    row_repr: str | None
    row_digest: str | None
    closed_head_digest: str | None      # 原 evidence_ref.closed_head_digest
    result_id: str | None
    row_id: str | None
    # evidence_ref_id 删除(原本只是 self-reference,无独立用途)
    raw_kind: RawKind | None
    bound: ...
    failure_class: ...
    checked_scope: ...
    suggested_next_steps: ...
    errors: ...
    warnings: ...
```

`Explanation.status == "passed"` 时 `row_kind` / `row_bindings` / `row_repr` / `row_digest` 必非空;`failed` 时全部 None。

### §4.2 `EvidenceGraph` node label / value_summary

当前:`label = row.claim.name`, `value_summary = row.claim.repr`

目标:`label = result.head.id`(rule id), `value_summary = row.repr`(desc 渲染)

### §4.3 `fg.eval.explain` 内部对 closed_head_digest 的读取路径

当前:`evidence_ref.closed_head_digest`
目标:`row.closed_head_digest`(直接读)

[`sdk/store.py:_explain`](../../../../src/factgraph/sdk/store.py) 内部的 closed-head replay 路径需要更新 access path。

### §4.4 `fg.audit` —— 跟 ledger 直接绑,**不受影响**

`fg.audit.explain(target)` / `conflicts(target)` / `diff_proof_frames(...)` 都跟 ledger Claim(`asrt_id` / `pred_id` / `e_ref` / `rest_terms`)直接绑,与本设计 application protocol Claim 完全无关。这部分 0 改动。

### §4.5 跨 process serializable

EvaluateRow 本身已经是 frozen + 字段都 serializable(除 `_result_resolver` D17 已 mark `compare=False`)。把字段平铺后,EvaluateRow 直接是"自描述 row" —— 序列化保留所有 audit 信息(`row.digest` 等价 fact_digest,`row.closed_head_digest` 等价 replay key),反序列化后没有任何信息损失。

替代 EvidenceRef.ref_id 作 cross-process handle 的角色:用 `(result_id, row_id)` pair —— 任何 row 都自带 row_id,parent result_id 在 row 反序列化时由调用方提供(或编进序列化 payload top-level)。

### §4.6 现有 SDK consumer 的 breaking surface 清单

- `from factgraph.sdk import Claim` —— 失效,改为 `EvaluateRow`(或 deprecated alias 一段时间)
- `from factgraph.sdk import EvidenceRef` —— 失效,改为 `EvaluateRow`(或 deprecated alias)
- `row.claim.name` —— 失效,改为 `result.head.id`
- `row.claim.arguments` —— 失效,改为 `row.bindings`
- `row.claim.kind` / `row.claim.repr` / `row.claim.digest` —— 改为 `row.kind` / `row.repr` / `row.digest`
- `row.evidence_ref.closed_head_digest` —— 改为 `row.closed_head_digest`
- `row.evidence_ref.ref_id` —— 删除(派生)
- `row.evidence_ref.result_id` —— 改为 `result.result_id`(via row._result_resolver)
- `row.evidence_ref.fact_digest` —— 改为 `row.digest`
- `result.expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id` —— 改为 `result.fingerprint.*`
- `result.engine_version` / `adapter_version` —— 改为 `result.engine_meta["..."]`
- `Explanation.claim` —— 改为 inline 字段(`row_kind` / `row_bindings` 等)
- `Explanation.evidence_ref_id` —— 删除

shipped tests 需要更新约 30-50 处 access path(grep 估计)。需要 backward-compat alias 期决定见 §5.4。

## §5 未锁问题(实施前需要决议)

### §5.1 `raw_kind` / `bound` 留在 row 还是上 Claim 等价物?

Datalog 模型下 raw_kind/bound 描述"derived fact 的 uncertainty",概念上属 Claim。Query 模型下没有 Claim,raw_kind/bound 自然就在 row 上。本设计目前放 row 上。

未锁:Explanation 上的 `raw_kind` / `bound` 是否要重命名 `row_raw_kind` / `row_bound`?

### §5.2 `ResultFingerprint` sub-object 还是直接 `Mapping[str, str]`?

- Option A:`ResultFingerprint` 命名 sub-object —— 类型安全、IDE 提示好、扩展加字段不破坏 API
- Option B:`result.fingerprint: Mapping[str, str]` —— 最 dict-friendly、易序列化、无 sub-object 增 boilerplate

倾向 A(类型安全 + 跟其他 application protocol DTO 风格一致)。

### §5.3 query-style head 的 arity check 是 reject / warn / silent skip?

当 `rule.id` match 一个 schema predicate 但 `len(rule.ports) != arg_specs`,3 种选择:
- A. 仍 reject(保持现行严格)
- B. warn + 走 query 风格
- C. silent skip arity check + 走 query 风格

倾向 B —— 保留 schema 协调能力,但不强制。

### §5.4 backward compat alias 保留多久?

- `from factgraph.sdk import Claim, EvidenceRef` 保留 alias 多长?
- `row.claim` / `row.evidence_ref` 是否保留作 deprecated property?
- `result.expr_digest` 等是否提供 `__getattr__` fallback 到 `result.fingerprint.expr_digest`?

倾向:首次 release 标 `DeprecationWarning`,下一 minor cycle 删除。

### §5.5 `closed_head_digest` 在 row 上 vs `EvidenceRef`-lite 取舍?

如果用户在 cross-process 序列化场景里希望"只携 replay key,不携整 row",可以保留一个 `EvidenceRef`-lite wrapper 只含 `closed_head_digest` + `result_id` + `row_id`。但 §2.5 实证没有这样的 consumer 存在。

倾向:不保留 wrapper,反正 row 序列化全部一起带。如果有真 cross-process 需求再补。

### §5.6 `:exists` Claim 跟新 row.kind 的关系

`Claim.kind` 当前 4 种:`fact_triple` / `rule_head` / `aggregate_result` / `projection`。新 `RowKind` 在 query 风格下:
- `fact_triple` 还需要吗?query 风格下 row 不必是 fact triple
- `projection` 该 promote 为 first-class(因为 `Rule.projection(...)` 终于能作 evaluate head)
- 是否新增 `query_row` 一类?

未锁。

### §5.7 跟 [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md) 的耦合

`build_application_rule(User(u).field == v)` auto-prepend `User:exists` 这个行为,在 query-style 下还要不要保留?如果 `head.id` 不需要 match predicate,`User:exists` prepend 失去硬约束意义,只剩"语义上要求 entity 存在"这条软约束。

未锁:auto-prepend 是去掉、保留、还是改成 opt-out kwarg?

## §6 实施切片(blueprint 候选)

按 risk-low → risk-high 排序,可独立 / 可合并:

### Slice α — Claim/EvidenceRef 冗余字段删除(low risk,不改范式)

- 删 `Claim.name`(改为 deprecated property fallback 到 head.id)
- 删 `Claim.arguments`(改为 deprecated property fallback 到 row.bindings)
- 删 `EvidenceRef.row_id`(改为 deprecated property fallback 到 row.row_id)
- 删 `EvidenceRef.fact_digest`(改为 deprecated property fallback 到 row.claim.digest)
- 删 `EvidenceRef.ref_id`(改为 deprecated property computed on-the-fly)
- 删 `EvidenceRef.result_id`(改为 deprecated property fallback)

净结果:wrapper 仍存在,内部冗余清掉。**不破坏现有 user code**(走 deprecated property fallback)。

### Slice β — `ResultFingerprint` sub-object 折叠

- 新增 `ResultFingerprint` DTO
- `EvaluateResult` 加 `fingerprint: ResultFingerprint` 字段
- 原 6 个 top-level digest 字段改为 `@property` fallback 到 `fingerprint.*`(deprecated)
- 同时 `engine_version` / `adapter_version` → `engine_meta` Mapping

### Slice γ — Claim / EvidenceRef wrapper 撤销 + 字段平铺

- 把 `Claim.kind` / `Claim.repr` / `Claim.digest` 平铺到 `EvaluateRow.kind` / `.repr` / `.digest`
- 把 `EvidenceRef.closed_head_digest` 平铺到 `EvaluateRow.closed_head_digest`
- `row.claim` / `row.evidence_ref` 保留作 deprecated property 一个 release cycle
- `Explanation.claim` 平铺为 inline `row_kind` / `row_bindings` / 等字段

### Slice δ — query-style head decoupling(arity check opt-in)

- [`core/store/_evaluate.py:148-157`](../../../../src/factgraph/core/store/_evaluate.py) 的 `find_schema_pred` 改为 optional lookup
- arity check 改为 only-when-matched
- `WhereValidationError: target predicate not found` 改为 informational(query 风格自动 fallback)
- `rule.id` 校验只保留 "non-empty string"

### Slice ε — `row.repr` 用 desc 渲染(承接 D21)

- row 构造时调用 `head.render_desc(row.bindings)` 填充 `row.repr`
- `Claim.repr` deprecated property 路由到 `row.repr`
- 实施 D21 design-point §6.6 路径 C(`Explanation.desc_lines` 自动 populate)的等价能力

### Slice ζ — `bindings` 形态简化

- row 构造时把 `{pred_id, terms[]}` 形态转 `{port_name: term}` map
- 旧形态保留作 deprecated 属性 1 个 cycle

每个 slice 独立可上线 + 可独立回滚 + 不阻塞下游。推荐顺序:α → β → γ → ζ → ε → δ。δ 最后做因为它是范式转向,需要前面所有 slice 都已成熟。

## §7 跟其他设计的耦合

### §7.1 Supersede 关系

本设计 **supersede** 部分 [`rule-namespace-rulespec-redesign.zh.md §3.6 / §4.7`](rule-namespace-rulespec-redesign.zh.md) (`rule.id` 与 ledger predicate id 解耦那一支)。建议在那份文档加 supersede 标注,原 §3.6/§4.7 内容移出或链接到本文。

### §7.2 跟 [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md) 的关系

`build_application_rule(User(u).field == v)` 的 auto-prepend `User:exists` 行为受本设计影响。详见 §5.7。两份 design-point 在 query-style 范式选定后需要同步审视。

### §7.3 D21 desc-driven explain([`explanation-completion-roadmap.zh.md §6.6`](explanation-completion-roadmap.zh.md))

D21 §6.6 路径 C 是"`Explanation.desc_lines: tuple[str, ...]` 在 explain 时自动 populate"。本设计 Slice ε(`row.repr` 用 desc 渲染)就是 D21 的等价落地点 —— 在 `EvaluateRow.repr` 这个位置自然实现,不需要为 Explanation 单开 desc_lines 字段。

### §7.4 ADR-IC §4.4.2 `:exists` Claim transitional guard

ADR-IC §4.4.2 关于 `:exists` Claim 的 transitional guard,query-style 下其角色重新审视。需要补 ADR 决定是 retire 还是保留 `:exists` co-emission。

### §7.5 INV-6 application-first runtime authority

本设计 **不破坏** INV-6 —— 全部改动在 `factgraph.application.protocol` + `factgraph.sdk` 两层,没有 SDK 反向依赖、没有 substrate 上移。`ResultFingerprint` / 平铺后的 `EvaluateRow` / 调整后的 `Explanation` 都是 application protocol DTO,SDK 仅 re-export。

### §7.6 跟 archived design-point(`rule-expression-and-proof-track-plan.zh.md` 等)的关系

T5 wave 当时的 D17 / D18 / D19 / D20 / D21 决策构成了当前体系。本设计 supersede 部分 D17(Claim/EvidenceRef wrapper 形态)+ 部分 D19(digest 字段分布),但保留 INV-6 application-first 等更顶层的设计 commitment。具体 supersede 边界:
- D17 §4.4 "Claim 字段集" → 字段集变 + wrapper 撤销
- D17 §4.5 "EvidenceRef 字段集" → 字段集变 + wrapper 撤销
- D19 "digest source-of-truth" 部分 → 字段位置变(到 ResultFingerprint),hash 算法不变

## §8 关联代码锚点

- [`src/factgraph/application/protocol/evaluate_result.py:86-101`](../../../../src/factgraph/application/protocol/evaluate_result.py) — application protocol `Claim` 定义(§3.4 删除目标)
- [`src/factgraph/application/protocol/evaluate_result.py:103-116`](../../../../src/factgraph/application/protocol/evaluate_result.py) — `EvidenceRef` 定义(§3.5 删除目标)
- [`src/factgraph/application/protocol/evaluate_result.py:119-157`](../../../../src/factgraph/application/protocol/evaluate_result.py) — `EvaluateRow` 定义 + D17 invariant 校验(§3.3 改造目标 + 删除 invariant 校验)
- [`src/factgraph/application/protocol/evaluate_result.py:162-256`](../../../../src/factgraph/application/protocol/evaluate_result.py) — `EvaluateResult` 定义 + 7 digest/id 字段(§3.1 / §3.2 改造目标)
- [`src/factgraph/application/protocol/evaluate_result.py:258-327`](../../../../src/factgraph/application/protocol/evaluate_result.py) — `Explanation` 定义(§4.1 改造目标)
- [`src/factgraph/application/protocol/evaluate_result.py:1163-1166`](../../../../src/factgraph/application/protocol/evaluate_result.py) — provenance metadata snapshot 现行消费点 1(§2.4 实证)
- [`src/factgraph/application/protocol/evaluate_result.py:1245-1254`](../../../../src/factgraph/application/protocol/evaluate_result.py) — provenance metadata snapshot 现行消费点 2(§2.4 实证)
- [`src/factgraph/sdk/store.py:2529-2537`](../../../../src/factgraph/sdk/store.py) — provenance metadata snapshot 现行消费点 3(§2.4 实证)
- [`src/factgraph/core/store/_evaluate.py:148-157`](../../../../src/factgraph/core/store/_evaluate.py) — 当前 schema lookup + arity check(§3.8 / Slice δ 改造目标)
- [`src/factgraph/sdk/__init__.py:33-49`](../../../../src/factgraph/sdk/__init__.py) — SDK 顶层 re-export(§4.6 deprecated alias 落点)
- [`src/factgraph/audit/evidence_graph.py:27-72`](../../../../src/factgraph/audit/evidence_graph.py) — `EvidenceNode` / `EvidenceEdge` / `EvidenceGraph` 定义(§4.2 label/value_summary 改造路径)
- [`src/factgraph/sdk/store.py:2463-2517`](../../../../src/factgraph/sdk/store.py) — `_explain` 内部对 `closed_head_digest` 的读路径(§4.3 改造点)

## §9 关联文档

- 用户面 evaluate-evidence 文档:[`docs/quickstart/evaluate_and_evidence.md`](../../../../docs/quickstart/evaluate_and_evidence.md)(本设计落地后整章重写)
- 用户面 rule 文档:[`docs/quickstart/rules.md`](../../../../docs/quickstart/rules.md)(`Rule.projection(*names)` 在 query-style 后真正能作 evaluate head;§2.4 描述需更新)
- 用户面 engine/config 文档:[`docs/quickstart/engines_and_configs.md`](../../../../docs/quickstart/engines_and_configs.md)(`config_digest` 跟 `result.fingerprint.config_digest` 路径更新)
- 数据模型文档:[`docs/quickstart/data_model.md`](../../../../docs/quickstart/data_model.md)(`Claim` 命名冲突自动缓解 —— application protocol Claim 删除后,只剩 ledger Claim 一个 class)
- 历史 T5 决策:`workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`(本设计 supersede 部分 §4.3 / §4.4 / §4.5)
- 历史 T5 决策:`workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`(digest 算法仍 owns 这份;字段位置由本设计变)
- 同类 ergonomic gap:
  - [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md)(RuleSpec 重命名 + branch_id 派生 + Claim 命名占名)
  - [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md)(`:exists` Claim emission 缺失)
  - [`fields-iterable-value-batch.zh.md`](fields-iterable-value-batch.zh.md)
  - [`schema-mutation-additive-only.zh.md`](schema-mutation-additive-only.zh.md)
- D21 desc-driven explain:[`explanation-completion-roadmap.zh.md §6.6`](explanation-completion-roadmap.zh.md)(本设计 Slice ε 等价落地)
