# Evaluate-result DTO flatten + query-style 范式重设计

- Status: working / **target form locked draft** —— 已具备升级为 ADR + blueprint 的成熟度
- Authority: candidate design / non-authoritative reference;现状描述属实,目标形态属计划落地的设计空间
- First draft: 2026-06-03
- Last updated: 2026-06-03
- Scope: `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` 整个 DTO 体系的扁平化重设计;`rule.id` 与 ledger predicate id 解耦(Datalog → query 范式转向);provenance digest 集中为 `ResultFingerprint` sub-object;`Claim.repr` 走 desc 模板渲染
- Parent: 与 [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md) / [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md) 并列,**superseding** `rule-namespace-rulespec-redesign §3.6 / §4.7`(`rule.id` ↔ pred_id 解耦那一支)
- Design intent: 把"evaluate-result DTO 体系存在大量被抽象空转的 wrapper、被 D17 强制 invariant 镜像出来的冗余字段、以及无独立消费者的 provenance digest"这些 friction 集中扁平化处理;同时把"rule head 强制为 ledger predicate id"这条 Datalog 范式根问题一起解决(因为后者是前者的根)。整体目标是让用户面 evaluate-result 体系**信息量不减、surface 显著瘦身、概念跟随 query 范式自然清爽**

---

> **2026-06-08 状态更新**
> - §3.1-§3.6(EvaluateResult/EvaluateRow/Claim/EvidenceRef DTO 重设计)和 §3.8(query-style head 解耦)的 DTO 接缝内容已合并入 [`explain-layer-complete-design.zh.md §3.1`](explain-layer-complete-design.zh.md)。
> - §3.9(旧 EvidenceGraph 3-tier nodes/edges DAG:NODE_RULE_EXPR / NODE_RULE / NODE_ATOM)和 §4.7(DAG walker 算法)已被 [`explain-layer-complete-design.zh.md`](explain-layer-complete-design.zh.md) §3/§4 的 `paths: EvidenceTree | EvidenceTimeline` 模型 **supersede**,不作为新实现目标。
> - §5(未锁问题)、§6(实施切片 α-ζ)、§7-§9(耦合/代码锚点/关联文档)仍作为历史参考有效;其中 §6 的 η(EvidenceGraph 3-tier nodes/edges 构建)和 ε(walker)切片已被新主文档 supersede,仅作历史 implementation record。

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

### §3.3 EvaluateRow — 平铺 Claim/EvidenceRef 字段,纯数据 DTO

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, object]              # {port_name: term} 直接 map(见 §3.6)
    kind: RowKind                                # 原 Claim.kind
    digest: str                                  # 原 Claim.digest
    closed_head_digest: str                      # 原 EvidenceRef.closed_head_digest
    raw_kind: Literal["probabilistic", "possibilistic"] | None
    bound: tuple[float, float] | None
    _result_resolver: Callable[[], EvaluateResult] | None

    # 显式 render 方法(不存为字段):
    def render_desc(self, head: Rule) -> str: ...
```

净减:
- `row.claim` 整层 wrapper / `row.evidence_ref` 整层 wrapper **都消失**
- 有用字段(kind/digest/closed_head_digest)平铺到 row
- 冗余字段(name/arguments/fact_digest/row_id/ref_id/result_id)全部删除
- **`repr` 不在 row 上** —— 它是 view 字段,移到 `Explanation`(§4.1);user 想要 row label 时显式调 `row.render_desc(head)`

EvaluateRow 现在是 **7 user-facing 字段 + 1 internal**,纯数据,无任何 view / presentation 字段。

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

### §3.7 `Explanation.repr` 走 walking EvidenceGraph 的多行 NL(承接 D21)

`repr` 是 **view concern**(展示用),不是 row 上的 data concern。当前 D17 把 `Claim.repr` eager 存在 row 上是错配 —— 渲染 / 展示是 `fg.eval.explain(...)` 的职责,应该住在 `Explanation` 上,且 lazy 求值。

**关键洞察**:`repr` 不应该只是 "head 一行 desc 渲染",而应该 **walk EvidenceGraph 生成多行"因为... 所以..." NL** —— 这才是真正的 explanation。详见 §3.9(EvidenceGraph 3 层 hierarchy 重设计)+ §4.7(walker renderer)。

目标形态:

```python
@dataclass(frozen=True)
class Explanation:
    ...
    repr: tuple[str, ...] | None    # ← multi-line NL, walked from evidence
                                    #   passed: 走 EvidenceGraph 渲染 "因为... 所以..."
                                    #   failed: 渲染 "为什么不"叙述
                                    #   unsupported / invalid_request: None
```

走 EvidenceGraph 的 walker 在 explain 时 lazy 调用,每一行对应 graph 一层(L1 RuleExpr → L2 Rule → L3 Atom → seed)的 desc-rendered text;详细 walker 算法见 §4.7。

这就是 [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) §6.6 (D21) 提议的 "Explanation.desc_lines 自动 populate" 的等价能力,但语义层级被收紧到"walk evidence hierarchy 而不是简单 head desc 渲染"。

### §3.8 query-style evaluate head — `head.id` 自由 + arity check opt-in

`fg.eval.evaluate(rule, head=rule)` 的行为变化:
- `rule.id` 可以是任意合法字符串(`"adult_in_us"` / `"find_us_users"` 都 OK)
- `head` 不再被 lookup 成 schema predicate;evaluator 只用 head.ports 决定 result 行形态
- arity check 转为 **opt-in**:只在 head.id **恰好** match 某个 schema predicate 时才校验 `len(head.ports) == len(arg_specs)`;不 match 时纯 query 风格,不校验
- 现 [`core/store/_evaluate.py:150-157`](../../../../src/factgraph/core/store/_evaluate.py) 的两条 raise 改为 opt-in 路径

向后兼容:原先 `id="user:region"` 这种 match-predicate 风格仍然 work(走 opt-in 校验路径);新加 `id="adult_in_us"` 风格现在也 work(skip 校验)。

### §3.9 EvidenceGraph 3 层 hierarchy 重设计

**Root insight**:user 写 rule 是 hierarchical 的(`RuleExpr` 组合 `Rule` 组合 `Atom`),evaluate 时每个引擎也都按这个 hierarchy 跑;但当前 EvidenceGraph 把 3 层平铺成 flat DAG,丢了语义层级。

#### §3.9.1 新 node_kind 枚举(5 类)

```python
NODE_CONCLUSION = "conclusion"     # 顶层结论(已存在,= head 渲染)
NODE_RULE_EXPR  = "rule_expr"      # L1: RuleExpr 组合点(AND / OR / single)— 新增
NODE_RULE       = "rule"           # L2: 一条参与的 Rule occurrence — 新增
NODE_ATOM       = "atom"           # L3: 某 Rule body 内一个 atom — 新增
NODE_SEED       = "seed"           # 底层 EDB fact / ledger claim(已存在)
NODE_PREMISE    = "premise"        # 保留作 ProbLog derivation chain 中间 atom 使用(已存在)
```

L1/L2/L3 三个新节点类型 + 原有 conclusion/seed 共同形成 5-tier 层级。每层 node 携 layer-specific `engine_meta`:

| Node | engine_meta 携 |
|---|---|
| `NODE_RULE_EXPR` | `ast_form: "and" / "or" / "single"`,`occurrence_count`, ... |
| `NODE_RULE` | `rule_id`, `version`, `occurrence_alias`, ... |
| `NODE_ATOM` | `atom_index`(在 rule body 里第几个), `atom_kind: "pred" / "cmp" / "not" / "in" / "builtin"`,`atom_status: "support" / "unsupport" / "not_visited" / "unknown"`, ... |
| `NODE_SEED` | `pred_id`, `asrt_id`, ... |

#### §3.9.2 新 edge_kind 枚举(语义化命名)

```python
EDGE_DERIVED_BY    = "derived_by"     # conclusion ← derived_by ← rule_expr
EDGE_USES          = "uses"           # rule_expr  ← uses        ← rule
EDGE_HAS_ATOM      = "has_atom"       # rule       ← has_atom    ← atom
EDGE_SUPPORTED_BY  = "supported_by"   # atom       ← supported_by← seed
EDGE_DERIVES       = "derives"        # 保留作 ProbLog provenance chain 中间步骤
EDGE_UPDATES       = "updates"        # 保留作 PyReason timeline bound update
```

**边方向约定**:`from_node_id` 是**"被支持者" / "上游"**,`to_node_id` 是**"支持者" / "下游"**。但**语义读法**反向 —— 读时按 edge_kind 的语义动词构句("X is derived_by Y" 读作"X 被 Y 支持")。

物理边方向例:
- conclusion ← derived_by ← rule_expr:edge `from=conclusion, to=rule_expr, edge_kind=derived_by`
- rule_expr ← uses ← rule:edge `from=rule_expr, to=rule, edge_kind=uses`
- rule ← has_atom ← atom:edge `from=rule, to=atom, edge_kind=has_atom`
- atom ← supported_by ← seed:edge `from=atom, to=seed, edge_kind=supported_by`

**Walker traversal direction**:从 `root_node_id`(conclusion)出发,按 `from_node_id → to_node_id` 方向走(顺向 edge 物理方向),自然从 L0 conclusion 递归到 L1 rule_expr → L2 rule → L3 atom → seed,符合"自顶向下解释"的 user mental model。

#### §3.9.3 完整例子 — 4-tier walk

对于 rule `adult_in_us` evaluate alice 成立:

```
EvidenceGraph (5 nodes, 4 edges):

  conclusion #u0  ─ derived_by ─→  rule_expr #ex1 (kind="single")
                                        │
                                        │ uses
                                        ▼
                                  rule #r0 (rule_id="adult_in_us")
                                        │
                                        │ has_atom (x3)
            ┌───────────────────────────┼───────────────────────────┐
            ▼                           ▼                           ▼
   atom #a0                  atom #a1                  atom #a2
   "User(u)" support         "User(u).age == age"      "age > 18"
   pred_id="User:exists"      pred_id="user:age"        cmp_op="gt"
            │                           │                   support (no seed)
            │ supported_by              │ supported_by
            ▼                           ▼
      seed #s0                    seed #s1
      "User:exists(alice)"        "user:age(alice, 25)"
```

#### §3.9.4 每引擎的 3-tier 填充能力

| Engine | L1 RULE_EXPR | L2 RULE | L3 ATOM | SEED | Notes |
|---|---|---|---|---|---|
| native | ✓ | ✓ | ✓ (atom_status 4 种全) | ✓ | shipped binding witness 已携 atom-level 命中信息 |
| souffle | ✓ | ✓ | ✓ | ✓ | `SOUFFLE_WITNESS_KIND` 跟 native 同走 Form 1 |
| problog | ✓ | ✓ | ✓ | ✓ | proof_trace 最丰富,L3 可携完整 derivation chain |
| pyreason | ✓ | ✓ | ⚠️ + timestep 维度 | ✓ | timeline / bound update 维度 deferred per D11 |

### §3.10 EvidenceGraph.engine 列举(souffle omission fix)

`EvidenceGraph.engine` 取自 `result.engine`([`evaluate_result.py:877`](../../../../src/factgraph/application/protocol/evaluate_result.py)),取值跟 `EvaluateResult.engine` 一致:

```python
engine: Literal["native", "souffle", "problog", "pyreason"]
```

`docs/quickstart/evaluate_and_evidence.md §5.1` 结构图当前漏列 `souffle`,需要一起 fix(纯 docs-vs-shipped drift,跟本设计可独立 commit)。

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

目标(修正版 — `row` 通过引用携带,`repr` 独立作 view 字段):
```python
class Explanation:
    status: ExplanationStatus

    # passed 时携完整数据:
    row: EvaluateRow | None              # ← 直接持完整 row(frozen,可序列化)
    evidence: EvidenceGraph | None       # ← 3-tier layered graph(见 §3.9)
    repr: tuple[str, ...] | None         # ← multi-line NL,walking evidence 渲染(见 §4.7)

    # 跨 process 必备 anchors:
    result_id: str | None

    # 失败语义:
    failure_class: ExplanationFailureClass | None
    checked_scope: Mapping[str, Any] | None
    suggested_next_steps: tuple[str, ...]

    # 不支持 / 输入非法:
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

关键变化(跟先前 flatten 提案对比):
- **删除** `row_kind` / `row_bindings` / `row_digest` / `row_id` 等 `row_*` inline 字段 —— 通过 `row` 引用统一访问
- **删除** `raw_kind` / `bound` —— 通过 `explanation.row.raw_kind` 取
- **删除** `closed_head_digest` inline 字段 —— 通过 `explanation.row.closed_head_digest` 取
- **新增** `repr: tuple[str, ...]` —— Explanation 的核心"输出",walking evidence 多行 NL
- **删除** `evidence_ref_id` —— 无独立用途

Net: Explanation 从 13 字段降到 **10 字段**,且每个字段都**真有独立语义**。

`status == "passed"` 时 `row` / `evidence` / `repr` 必非空;`failed` 时 `failure_class` 必非空;`unsupported` / `invalid_request` 时 `errors` 必非空。

### §4.2 `EvidenceGraph` node label / value_summary

当前 default fallback path 用 `label = row.claim.name`, `value_summary = row.claim.repr`([`evaluate_result.py:872-873`](../../../../src/factgraph/application/protocol/evaluate_result.py))。

目标:跟 §3.9 hierarchy 重设计同步:
- `NODE_CONCLUSION.label / value_summary` 用 head desc 模板渲染
- `NODE_RULE_EXPR.label` 用 ast_form,`value_summary` 用 RuleExpr 的 repr
- `NODE_RULE.label = rule.id`,`value_summary = rule.desc` 渲染
- `NODE_ATOM.label` 用 atom kind/pred_id,`value_summary` 描述具体 binding
- `NODE_SEED.label = pred_id`,`value_summary` 描述 ledger fact 内容

这把当前 `Claim.repr` 的 dict 打印彻底替换为 desc-rendered 文本,每层都自洽。

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

### §4.7 `Explanation.repr` walker — walking 3-tier evidence 生成多行 NL

承接 §3.7 提案 + §3.9 hierarchy。walker 算法:

```
walk(evidence_graph) -> tuple[str, ...]:
    lines = []
    visit(evidence_graph.root_node, depth=0)
    return tuple(lines)

visit(node, depth):
    indent = "  " * depth
    line = indent + render_node(node)        # 用 desc / engine_meta 渲染本节点
    lines.append(line)
    for edge in outgoing_edges(node):         # 顺向 from→to,即顶→底
        connector = edge_kind_to_connector(edge.edge_kind)
        # e.g. "derived_by" → "is derived by"
        # e.g. "uses" → "uses"
        # e.g. "has_atom" → "has atom"
        # e.g. "supported_by" → "is supported by"
        sub_line = (indent + "  ") + connector + " " + render_node_inline(edge.to_node)
        # recursive descent
        visit(edge.to_node, depth + 1)
```

**Walker output 例**(承接 §3.9.3 的 4-tier walk):

```
("User alice is adult",
 "  is derived by RuleExpr(single)",
 "    which uses Rule \"adult_in_us\"",
 "      which has atom User(u) — support",
 "        is supported by ledger fact User:exists(alice)",
 "      which has atom User(u).age == age — support, bound age=25",
 "        is supported by ledger fact user:age(alice, 25)",
 "      which has atom age > 18 — support (25 > 18, no seed)")
```

**Failed case** 也走同 walker,但 root node 是 `NODE_CONCLUSION` with `failure_class` 注释,atom-level node 的 `atom_status = "unsupport"` 时 renderer 切换措辞:

```
("User alice is adult — NOT concluded",
 "  failure_class: closed_head_false",
 "  which uses Rule \"adult_in_us\"",
 "    which has atom age > 18 — UNSUPPORT (age = 17, but required > 18)",
 "      atoms before this succeeded:",
 "        User(u) — support",
 "        User(u).age == age — support, bound age=17")
```

**Walker 实现位置**:application protocol 层(`factgraph.application.protocol.explanation_render.walk_evidence(...)`),lazy 在 `Explanation.__post_init__` 之后第一次访问 `.repr` 时调用并 cache(frozen dataclass 用 `object.__setattr__` cache 在 internal field 即可)。SDK 直接读 `explanation.repr` 拿到 tuple。

**桥接 D21**:这个 walker 就是 [`explanation-completion-roadmap.zh.md §6.6`](explanation-completion-roadmap.zh.md) 路径 C "`Explanation.desc_lines` 自动 populate" 的等价落地;D21 design-point 那条 deferred work 在本设计 Slice ε 一同关闭。

## §5 未锁问题(实施前需要决议)

### §5.1 `raw_kind` / `bound` 留在 row 还是上 Claim 等价物?

Datalog 模型下 raw_kind/bound 描述"derived fact 的 uncertainty",概念上属 Claim。Query 模型下没有 Claim,raw_kind/bound 自然就在 row 上。本设计目前放 row 上,Explanation 不重复 inline 这两字段(通过 `explanation.row.raw_kind` 访问)。

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

- 把 `Claim.kind` / `Claim.digest` 平铺到 `EvaluateRow.kind` / `.digest`
- 把 `EvidenceRef.closed_head_digest` 平铺到 `EvaluateRow.closed_head_digest`
- **`Claim.repr` 不移到 row**(repr 是 view concern,归 Explanation,见 Slice ε)
- `row.claim` / `row.evidence_ref` 保留作 deprecated property 一个 release cycle
- `Explanation.claim` 改为 `Explanation.row: EvaluateRow | None` 引用(详见 §4.1)

### Slice δ — query-style head decoupling(arity check opt-in)

- [`core/store/_evaluate.py:148-157`](../../../../src/factgraph/core/store/_evaluate.py) 的 `find_schema_pred` 改为 optional lookup
- arity check 改为 only-when-matched
- `WhereValidationError: target predicate not found` 改为 informational(query 风格自动 fallback)
- `rule.id` 校验只保留 "non-empty string"

### Slice ζ — `bindings` 形态简化

- row 构造时把 `{pred_id, terms[]}` 形态转 `{port_name: term}` map
- 旧形态保留作 deprecated 属性 1 个 cycle

### Slice η — EvidenceGraph 3-tier hierarchy(配 §3.9)

- 新增 `NODE_RULE_EXPR` / `NODE_RULE` / `NODE_ATOM` 3 个 node_kind(audit/evidence_graph.py)
- 新增 `EDGE_DERIVED_BY` / `EDGE_USES` / `EDGE_HAS_ATOM` / `EDGE_SUPPORTED_BY` 4 个 edge_kind
- 改造 `_build_passed_row_evidence_graph` / `_build_form1_evidence_graph` / `_build_problog_provenance_row_evidence_graph` 3 处 build path,各自产 3-tier 结构(per §3.9.4 表 — 每引擎能力)
- 现有 NODE_CONCLUSION / NODE_SEED 保留兼容,作为 hierarchy 顶/底两端
- node `engine_meta` 携 layer-specific 字段(rule_id / atom_index / atom_status / ...)

### Slice ε — `Explanation.repr` walker(配 §3.7 / §4.7,承接 D21)

- 实现 `factgraph.application.protocol.explanation_render.walk_evidence(graph) -> tuple[str, ...]`
- Walker 从 `evidence.root_node_id` 出发,顺向 edge 方向 DFS,每节点按 desc 模板 + edge_kind connector 渲染一行 NL
- failed Explanation 的 walker 切换措辞("UNSUPPORT" / "failure_class" 注释)
- `Explanation.__post_init__` 之后第一次 `.repr` 访问时 lazy 调用 walker + cache
- 关闭 D21 §6.6 路径 C deferred work
- **依赖 Slice η**(walker 走的是 layered graph) —— 须在 η 之后实施

每个 slice 独立可上线 + 可独立回滚 + 不阻塞下游。推荐顺序:**α → β → γ → ζ → η → ε → δ**。理由:
- α(冗余字段删除)/ β(fingerprint 折叠)low-risk,先做
- γ(wrapper 撤销)依赖 α / β 已经清理冗余,跟着做
- ζ(bindings 形态)是纯 row-level cleanup,可独立做
- η(EvidenceGraph 3-tier)是 evidence model 重设计,依赖前面 row/Claim 清理完成
- ε(walker)依赖 η 的 layered graph
- δ(query-style 范式)最后做,需要前面所有 slice 都已成熟

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
