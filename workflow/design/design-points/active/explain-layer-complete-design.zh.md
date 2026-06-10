# Explain + EvaluateResult Layer 完整设计:穷尽逐条件证明 + Repr 渲染 + DTO 接缝

> **本文件状态**: draft (2026-06-08); 合并文档;由以下两份 design-point 整合而成(原文件已归档至 `workflow/design/design-points/archive/`):
> - `evidence-proof-model.zh.md` (2026-06-05 初稿,穷尽逐条件证明结构)
> - `entity-repr-templates-and-inspect.zh.md` (2026-06-04 初稿,repr 模板与渲染)
>
> **整合目的**:两份文档交叉耦合(repr 依赖 EvidenceAtom 结构;atom 渲染依赖 schema DSL),分散设计导致隐性冲突;整合后统一视图并强制解决设计张力。
>
> **权威边界 (per `workflow/design/design-points/README.md`)**:
> design-point 是候选设计 / 非权威参考。实现必须通过 decision → blueprint → impl 下游消费链。

- First draft (合并版): 2026-06-08
- Scope: `EvidenceGraph` body 换芯(穷尽逐条件结构)+ Repr 模板层(schema DSL + 渲染管线)+ `EvaluateResult`/`EvaluateRow`/`Claim`/`EvidenceRef` DTO 前置地基(query-style head 解耦)
- Parent / 相关:
  - [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) — 解释层路线(§0 摘取定位信息;原文保留,涵盖 D5-D21 未来条目)
  - [`archive/evaluate-result-flatten-and-query-style.zh.md`](../archive/evaluate-result-flatten-and-query-style.zh.md) — result DTO 重设计原文件(**已归档**);有效内容已合并入本文件 §3.1-§3.3/§9/§10.0/§13;旧 §3.9/§4.7 部分已被本文件 supersede

---

## §0 背景定位:Explain 路线图中的位置

> 本节合并自 [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) §1-§2/§6.2/§6.6 的相关部分。路线图原文保留完整内容,涵盖 D5-D21 等尚未设计的未来条目。

### §0.1 已 ship 的 Explainability Surface

| Milestone | 内容 |
|---|---|
| T8-A | 14-key metadata + `run_id` envelope |
| T8-B-1/2 | native Form 1 + Souffle Form 1 |
| T8-C-1 | ProbLog row provenance graphs(`PROBLOG_PROVENANCE_KIND` / `EDGE_DERIVES`) |
| T10-1 | ProbLog `uncertainty_projection`(default reject + 4 policies + interval reject) |
| T10-2/3 | PyReason canonical semantics(C74/C77/C78) |
| T8-D rounds 1-5 | user quickstart 闭合;Adapter module docs 对齐 |

### §0.2 本文件在路线图中的位置

本文件实现了 `explanation-completion-roadmap.zh.md` §2 中的 **D4 atom-complete probing**,并为 **D5 Why-not** 奠定实现基础:

| 路线图条目 | Tier | 本文件状态 |
|---|---|---|
| D4 atom-complete probing | Tier B(作为 D5 impl strategy) | **已设计** — 穷尽逐条件探查器(§2-§8) |
| D21 desc-driven NL explain | Tier B | **已决(R7)** — `Rule.desc → Rule.repr`;渲染层 §5/§12 |
| D5 Why-not / counterfactual | Tier S | **未设计** — 本文件 prober 是其实现前提 |
| D11 PyReason Form 2 evidence | Tier S | **部分决策** — R5 确定 EvidenceTimeline 形态;grounding parser 细节待定 |
| D1 fg.diagnose SDK shell | Tier A | **未设计** — prober 稳定后的薄壳 |

> 路线图原对 D4 的定位是"Tier B,作为 D5 的 implementation strategy"。本文件将其升格为独立设计对象——因为 D4 的输出(EvidenceGraph 穷尽结构)本身即是核心用户面价值,不仅仅是 D5 的内部手段。

### §0.3 本文件不覆盖的路线图条目

以下条目在 `explanation-completion-roadmap.zh.md` 中有独立设计入口,不在本文件范围:

| 条目 | 说明 |
|---|---|
| D5 Why-not / counterfactual | 下一个高价值目标;以本文件 prober 为前提 |
| D1 fg.diagnose SDK shell | 内部 diagnose 已 ship;SDK 薄壳后续做 |
| D6/D7 Salience / Shapley | Attribution 层,独立设计链 |
| D15/D18 Aggregate 扩展 | 表达层,独立设计链 |
| D20 Match witness | 与 EvidenceRef node identity 相关,独立设计 |
| D11 PyReason Form 2 细节 | grounding parser 实现细节,在 R5 基础上另立 blueprint |

---

## §1 问题:现有 evidence 是"获胜单分支快照"

实测(native 路径,只读)三次确认:

1. **join 失败拿不到 mismatch**:整体失败时 `explain` 返回 `failure_class="closed_head_false"`、`evidence=None`。
2. **成功经 OR 时,失败分支零痕迹**:`(region=us) | (region=eu)`,seed `eu` 成功,evidence 里 `us` 分支完全不出现;`alternative_paths.mode="winning_path_only"`;`ast_form="single"`(OR 被压平)。
3. **根因**:解释走 evaluation 捕获(`ProofReceipt` 只为获胜分支构造)。evaluation 天生只记获胜单线。

→ 要"成功/失败统一 + 全展开",**解释不能复用 evaluation 路径**,需要专门的穷尽逐条件链路。

---

## §2 核心决策

1. **解释 = 专门的穷尽逐条件探查器**:这是三条路中**唯一可行的**:
   - **evaluation 路径不可复用**:天生短路、只记获胜分支;结构上无法产出逐 atom 三态;
   - **引擎层内嵌方案不可行**:手写 `why_not_*/proof_step` 子句必须手动同步主规则,易脆;
   - **Python 侧探查器是唯一自动化路径**:遍历 `Rule.when` AST + 复用 `diagnose_runtime._eval_*`,不改引擎程序、天然与规则保持同步。无它,新结构的粒度不可达。

2. **保壳换芯**:保留 `Explanation` + `EvidenceGraph` 外壳;把 `EvidenceGraph` 的 body 换成穷尽逐条件结构;原 `EvidenceReport` 并入 `EvidenceGraph`。

3. **按 rule_expr 原样组织**(and/or 拓扑),不摊平成 DNF 执行形态;每个 atom 只挂最终状态。

4. **无"推理步(step)"概念**:组织原语是"结构 + 每节点状态",不是执行序。

5. **Prober 是独立 explain 路径**,不做成 `evaluate(flag=probe=True)`;evaluate 的 contract 是产出成功 rows,prober 的 contract 是解释所有 branch/atom 的三态。

---

## §3 类型 Schema

层级:`Explanation`(状态壳)→ `EvidenceGraph`(容器)→ `paths: tuple[EvidenceTree | EvidenceTimeline]` →〔tree〕`EvidenceTree`(一条路径 = 一个 proof)→ `EvidenceRule`→ `EvidenceAtom`(条件 + 最终状态)。

```python
# ===== 外壳(沿用现状,仅 evidence 不变式放宽,见 §9.0)=====
@dataclass(frozen=True)
class Explanation:
    status: Literal["passed", "failed", "unsupported", "invalid_request"]
    evidence: "EvidenceGraph | None"        # ★放宽:non-None iff status ∈ {passed, failed}
    row: "EvaluateRow | None"
    result_id: str | None
    failure_class: "ExplanationFailureClass | None" = None
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

# ===== 容器(并入原 EvidenceReport;旧 nodes/edges → paths)=====
@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str                             # native / souffle / problog / pyreason
    layout_hint: Literal["tree", "timeline"]
    subject_binding: Mapping[str, Any]
    paths: tuple["EvidenceTree | EvidenceTimeline", ...]
    certainty: "Certainty | None" = None
    metadata: Mapping[str, Any] = MappingProxyType({})

@dataclass(frozen=True)
class EvidenceTree:
    tree_id: str
    status: Literal["holds", "fails", "not_reached"]
    # holds       = 该路径所有条件成立
    # fails       = 至少一条 rule fails
    # not_reached = 所有 rules 均 not_reached(自底向上聚合);rules/joins 仍填充
    rules: tuple["EvidenceRule", ...]
    joins: tuple["EvidenceJoin", ...]
    certainty: "Certainty | None" = None

@dataclass(frozen=True)
class EvidenceTimeline:
    status: Literal["holds", "fails"]       # pyreason 顺序求值,无 not_reached
    events: tuple["EvidenceAtom", ...]
    certainty: "Certainty | None" = None

@dataclass(frozen=True)
class EvidenceRule:
    occurrence_alias: str
    rule_id: str
    role: Literal["body", "head"]
    status: Literal["holds", "fails", "not_reached"]
    # holds       = 所有 atoms holds
    # fails       = 至少一个 atom Fails
    # not_reached = 所有 atoms 均 NotReached(派生;atoms 仍填充;≠ tree.not_reached)
    ports: Mapping[str, Any]
    atoms: tuple["EvidenceAtom", ...]

@dataclass(frozen=True)
class EvidenceAtom:
    form:    "Fact | Compare | Builtin"
    verdict: "Holds | Fails | NotReached"
    atom_id: str                            # c{case}.c{cond}:{pred|kind}
    repr_text: str | None = None            # prober assembly 时烘焙的自然语言短语(见 §5.4)
    negated: bool = False
    timestep: int | None = None             # 仅 pyreason

@dataclass(frozen=True)
class Fact:     predicate: str; terms: tuple["Operand", ...]
@dataclass(frozen=True)
class Compare:  op: str; lhs: "Operand"; rhs: "Operand"
@dataclass(frozen=True)
class Builtin:  op: str; args: tuple["Operand", ...]; result: "Operand"

@dataclass(frozen=True)
class Holds:      certainty: "Certainty"; support: tuple["Source", ...] = ()
@dataclass(frozen=True)
class Fails:      certainty: "Certainty"
@dataclass(frozen=True)
class NotReached: blocked_by: str | None   # atom_id of expected binder; None = no prior binder

@dataclass(frozen=True)
class BoundVar:  name: str; value: Any | None; bound_by: str | None
@dataclass(frozen=True)
class Const:     value: Any
@dataclass(frozen=True)
class Aggregate: kind: str; target: "Operand | None"; filter: Any; value: Any | None

@dataclass(frozen=True)
class Source:    ref: str; field: str; value: Any; meta: Mapping[str, Any]

@dataclass(frozen=True)
class Certainty:
    lo: float; hi: float
    kind: Literal["boolean", "probabilistic", "possibilistic"] = "boolean"
    # __str__ → ✓ / ✗ / 0.73 / [0.6, 0.9]

@dataclass(frozen=True)
class PortRef:
    occurrence: str   # occurrence_alias
    port: str

@dataclass(frozen=True)
class EvidenceJoin:
    left: PortRef
    right: PortRef
    held: bool
```

### §3.1 DTO 接缝:EvaluateResult / EvaluateRow / Explanation

> 合并自 [`evaluate-result-flatten-and-query-style.zh.md`](../archive/evaluate-result-flatten-and-query-style.zh.md) §3.1-§3.5。该文件 §3.9(旧 EvidenceGraph nodes/edges 3-tier DAG)和 §4.7(旧 DAG walker)已被本文件 §3/§4 的 `paths: EvidenceTree | EvidenceTimeline` 模型 supersede,不在此合并。

`EvidenceGraph` 属于 `Explanation.evidence`,**不属于** `EvaluateRow`。

```python
@dataclass(frozen=True)
class EvaluateResult:
    rows: tuple[EvaluateRow, ...]
    result_id: str
    head: Rule
    engine: str
    evaluated_at: object
    engine_meta: Mapping[str, Any]        # {engine_version, adapter_version, ...}
    fingerprint: ResultFingerprint        # 全部 provenance digest 折叠(原 6 个顶层字段)

@dataclass(frozen=True)
class ResultFingerprint:
    expr_digest: str; rule_set_digest: str; view_snapshot_digest: str
    config_digest: str | None; result_digest: str; run_id: str

@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, object]        # {port_name: term}(已简化,原 {pred_id, terms[]})
    kind: RowKind                          # 原 Claim.kind
    digest: str                            # 原 Claim.digest;content-address
    closed_head_digest: str                # 原 EvidenceRef.closed_head_digest;replay key
    certainty: "Certainty | None" = None  # 原 raw_kind + bound 合并;同 EvidenceTree.certainty 类型
    # repr / label 不在 row 上 — view concern 归 Explanation

# Claim DTO → 删除
# EvidenceRef DTO → 删除;cross-process handle 改用 (result_id, row_id) pair
```

`Explanation.row: EvaluateRow | None` 直接持 row 引用(无 wrapper)。`Explanation.evidence: EvidenceGraph | None` 持新 paths 结构(§3)。两者通过 `result_id` 与父 `EvaluateResult` 关联。

**bindings 形态简化**:当前 `row.bindings = {pred_id: "user:region", terms: [{kind, value}, ...]}` 改为 `{port_name: term}` 命名 map:

```python
# 目标形态
row.bindings = {
    "user":   {"kind": "entity_ref", "value": "idref_v1:User:..."},
    "region": {"kind": "literal", "tag": "string", "value": "US"},
}
# user 直接 row.bindings["user"];不需要 positional → port_name 心理体操
# pred_id 从 bindings 删除(已在 EvaluateResult.head.id)
# term 内部仍是 {kind, value, tag?} typed dict
```

**query-style head(`rule.id` 自由 + arity check opt-in)**:`fg.eval.evaluate(rule, ...)` 行为调整:

- `rule.id` 可以是任意合法字符串(`"adult_in_us"` / `"find_us_users"` 均 OK)
- `head` 不再被 lookup 成 schema predicate;evaluator 只用 `head.ports` 决定 result 行形态
- arity check 转为 **opt-in**:仅当 `head.id` **恰好 match** 某 schema predicate 时才校验 `len(head.ports) == len(arg_specs)`;不 match 时纯 query 风格,跳过校验
- `core/store/_evaluate.py:150-157` 的两条 raise 改为 opt-in 路径
- **向后兼容**:原有 `id="user:region"` match-predicate 风格仍走 opt-in 校验路径,新 `id="adult_in_us"` 自由风格自动 skip 校验

> arity mismatch 策略(Q-D,**已决 Option A**):matched-predicate 端口数不符 → reject;free-form head(不匹配任何 predicate)→ query-style,跳过校验。

### §3.2 迁移边界与兼容说明

**`Explanation` 字段迁移**(删除旧 wrapper 字段):

| 旧字段 | 替换为 | 说明 |
|---|---|---|
| `Explanation.claim` | `Explanation.row: EvaluateRow` | row 直接引用 |
| `Explanation.raw_kind` / `bound` | `explanation.row.certainty` | 通过 row 访问 |
| `Explanation.evidence_ref_id` | — 删除 | 无独立用途 |
| `Explanation.row_id` | `explanation.row.row_id` | 通过 row 访问 |
| `explanation.claim.repr` | — 删除 | repr 是 view concern,归 Explanation/renderer |

**内部 access path 更新**:`sdk/store.py` `_explain` 内的 closed-head replay:
- 旧:`evidence_ref.closed_head_digest`
- 新:`row.closed_head_digest`

**`fg.audit` 不受影响**:`fg.audit.explain` / `conflicts` / `diff_proof_frames` 直接绑 ledger Claim(`asrt_id`/`pred_id`/`e_ref`),与 application protocol Claim 完全无关,0 改动。

**EvaluateRow 跨进程序列化**:EvaluateRow frozen + 所有字段可序列化(除 `_result_resolver`,D17 已标 `compare=False`);跨 process handle 改用 `(result_id, row_id)` pair,无需 EvidenceRef wrapper。

**Breaking surface 清单(SDK consumer)**:

```
from factgraph.sdk import Claim       → EvaluateRow(或 deprecated alias)
from factgraph.sdk import EvidenceRef → EvaluateRow(或 deprecated alias)
row.claim.kind / .digest              → row.kind / row.digest
row.claim.name                        → result.head.id
row.claim.arguments                   → row.bindings
row.evidence_ref.closed_head_digest   → row.closed_head_digest
row.evidence_ref.ref_id               → 删除(派生)
result.expr_digest / rule_set_digest / ...  → result.fingerprint.*
result.engine_version / adapter_version     → result.engine_meta["..."]
Explanation.claim                     → Explanation.row
Explanation.evidence_ref_id           → 删除
```

shipped tests 需更新约 30-50 处 access path。兼容 alias 策略:首次 release 标 `DeprecationWarning`,下一 minor cycle 删除。

---

## §4 关键语义

- **镜像 rule_expr,不摊平**:OR → 多个 `EvidenceTree`;每条路径内是合取(rules + atoms + joins)。
- **三层 `not_reached` 统一语义(自底向上聚合)**:
  - `EvidenceAtom.verdict = NotReached(blocked_by)`:单 atom 因上游变量未绑定无法求值;`blocked_by` 指向期望 binder 的 atom_id(`None` = 该分支无任何 prior binder)。这是 not_reached 的**根源**。
  - `EvidenceRule.status = "not_reached"`:所有 atoms 均 NotReached → 聚合上浮;`atoms` 仍填充(内容全是 NotReached verdict)。
  - `EvidenceTree.status = "not_reached"`:所有 rules 均 not_reached → 进一步聚合;`rules/joins` 仍填充。**无"prober 主动跳过分支"语义** — prober 是穷尽的,不 volitionally skip 任何分支;not_reached 只从 atom 层自底向上传播。
- **`NotReached` 只由变量未绑定触发**:前序 atom `Fails` **不**触发后续 atom 的 `NotReached`;只要后续 atom 的依赖变量已绑定,prober 继续求值(穷尽)。
- **三层 holds 对称**:每层显式 status,消费者无需 walk 子层推断上层。
- **Builtin 是计算非判定**:结果落 `Builtin.result`,verdict 用 `Holds`(算出)或 `NotReached`(参数未绑定);不设 `Computed` 变体。
- **compare 中性**:`Compare(op, lhs, rhs)`;操作数自带 value;"required/actual" 是 repr 解读层的事。
- **negation**:`negated: bool` 标记;**单原子与多原子 `Not([..])` 均富解释**(Batch C 对齐 souffle 契约):单原子 `!<body>`,多原子 `!(a && b)` / `!((a && b) || c)`,实体/float 内层经统一渲染器,无 `$` 内部 var、无 raw tuple。〔原"多原子 v1 不富解释"已被实现超越,2026-06-10 更新〕
- **head 也是 rule**:用 `EvidenceRule(role="head")`。
- **多路径**:`paths` 里多个 `EvidenceTree`;holds ⟺ 任一路径 holds。
- **v1 无内联派生**:ruleref 被禁 → 无递归无环;`support` 只到 `Source`,无子图。

---

## §5 Repr 渲染层

> **合并自 `entity-repr-templates-and-inspect.zh.md`**。本节设计 atom 的自然语言渲染机制。

### §5.1 两类措辞来源

| 来源 | 覆盖范围 |
|---|---|
| **Schema DSL `Field.repr` / `Identity.repr`** | 字段谓词 atom(`pred:field(subj, val)`)→ 领域措辞由 schema 作者声明 |
| **渲染器级默认表** | 其余所有 atom(exists / Compare / Builtin / Aggregate / not …)→ 内建通用措辞 |

边界标准:**有没有对应 schema 字段**。`==` / `max` 这类无 schema 字段,归渲染器默认表。

### §5.2 Schema DSL 设计

```python
class Country(Entity):
    code: str = Identity(repr="%ENT has code %FLD")
    language: "Language" = Field(repr="%ENT's language is %FLD")

    class Meta:
        repr = "%CLS %code"                  # 实体 label — 只引用 identity 字段

class User(Entity):
    user_id: str = Identity(repr="%ENT has id %FLD")
    name: str = Field(repr="%ENT's name is %FLD")
    country: Country = Field(repr="%ENT lives in %FLD")
    age: int = Field(repr="%ENT is %FLD years old")

    class Meta:
        repr = "%CLS %user_id"              # → "User u-1"
```

**占位符语法(已锁定)**:

| 占位 | 含义 | 用在 |
|---|---|---|
| `%CLS` | EntityClass 名 | Meta.repr / Field.repr / Identity.repr |
| `%ENT` | 主体实体 → 其类型的 Meta.repr label | Field.repr / Identity.repr;**Meta.repr 禁用(循环)** |
| `%FLD` | 当前字段值;entity-ref 递归用 Meta.repr,标量直印 | Field.repr / Identity.repr;**仅当前字段,禁引他字段** |
| `%<field_name>` | 当前实体某 identity 字段值 | Meta.repr |

**Meta.repr 约束(已锁定)**:只能引用 identity 字段。理由:identity 不可变 + 恒在 → 任何时刻解析忠实且完整,无漂移。代价:label 由 identity 值构成(`"User u-1"` 而非 `"User Alice"`);若需友好名,把字段设为 `Identity()`。不设逃生口。

**默认 label**(未定义 `Meta.repr` 时):`"<EntityCls> <第一个 Identity 字段值>"`。

**校验时机**:类定义时 — `%ENT` 出现在 Meta.repr、`%FLD` 引用非当前字段、保留词撞字段名,均报错。

### §5.3 渲染流程(两遍)

1. **解析遍**:对每个 entity-ref 用其类型 `Meta.repr` + identity 值解析出 label(identity-only 约束保证此遍永远成功)。
2. **渲染遍**:用解析后 label 渲染各 atom。identity 谓词 atom(其字段出现在 Meta.repr 中)可**折叠**,不单独成句。

**目标输出形态**:
```
<Alice speaks English> because          ← conclusion: Rule.repr + head 端口绑定
  ├─ User u-1 lives in Country US       ← Fact atom: Field.repr + Meta.repr label
  ├─ Country US's language is Language en
  └─ User u-1 is 30 years old  (age ≥ 5)
```

### §5.4 R1/R2:渲染结果存储位置(已决)

**原文档冲突已解决**:两份原始文档假设不同(evidence-proof-model 倾向计算派生;entity-repr 倾向 build-time 烘焙)。合并后决策如下:

**已决:存储方案,字段名 `repr_text`**

- `EvidenceAtom.repr_text: str | None` — prober assembly 时烘焙写入,DTO 离线可读。
- 字段名选 `repr_text` 而非 `value_summary`:与整个 repr 层命名对齐(见 §12 repr 命名体系);明确表达"已渲染文本"而非"值摘要"。
- Walker(`Explanation.repr_text`)读 `repr_text` 直接打印,无需 schema 句柄;Stateless renderer。

**烘焙时机(R2)**:在 `application/explain/` prober assembly 步骤,不在 `evaluate_result.py`。Schema 在 prober 运行时恒在场,保证烘焙总能成功。

### §5.5 R3:Conclusion/Atom label 来源(已决)

**已决:允许不同来源,不强求统一**

| 层 | 措辞来源 | 示例 |
|---|---|---|
| Conclusion(head) | `Rule.repr` 模板 + head 端口绑定 | "Alice speaks English" |
| Atom(body) | `Field.repr` / `Identity.repr` + Meta.repr entity label | "User u-1 lives in Country US" |

两者风格不同是设计选择,不是缺陷:conclusion 是 rule 作者写的领域语言;atom 是 schema 作者写的字段措辞。两条来源各司其职。

### §5.6 R4:D-prose 流畅散文渲染(已决形态)

**已决:新增 `narrate()` / `repr(style="prose")`,不替换结构化 `repr_text`**

- `Explanation.repr_text`:缩进树,保持现有结构化 contract;machine-walkable。
- `Explanation.narrate()`:未来新增,流畅 because 散文;复用同一批 `repr_text` 短语,只改合成方式。
- 两 walker 共用 build-time 烘焙数据,无重复 schema 调用。

具体 prose 渲染映射(节点 → 散文元素)留作该 slice 实施时细化,不在本文件锁定。


### §5.7 渲染器级默认表

> **措辞已对齐 shipped(2026-06-10 conformance rework)**:实现选择了更简洁/运算符化措辞 + souffle 对齐的 `!` 否定;下表反映实际渲染,非早期提案。

| Atom 类型 | 默认措辞(shipped) |
|---|---|
| `<Type>:exists(x)` | `<pred_id>(<entity label>)`(通用谓词回落,无特化措辞) |
| `eq` | "%1 equals %2" |
| `ne` | "%1 does not equal %2" |
| `ge` / `gt` / `le` / `lt` | "%1 >= %2" / "%1 > %2" / "%1 <= %2" / "%1 < %2" |
| 聚合 `max/min/sum/mean` | "%agg of %target"(如 "sum of amount") |
| 聚合 `count` | "count" |
| `in` | "%1 is in (%2, …)" |
| `not(body)` | 单原子 `!<body>`;AND `!(a && b)`;OR-of-AND `!((a && b) \|\| c)`(对齐 souffle 契约;`EvidenceAtom.negated=True`) |
| `BuiltinAtom` / arithmetic | `<kind>(<operands…>)` 回落 |
| identity atom(出现在 Meta.repr 中) | **折叠**(与 label 冗余) |

---

## §6 引擎范围

**native / souffle / problog → `tree` 形态** (`paths: tuple[EvidenceTree]`):
- problog:结构与 native/souffle 同构,多概率项 → `EvidenceTree.certainty(Certainty(p,p,"probabilistic"))`;聚合存 `EvidenceGraph.certainty`。
- v1 无内联派生 → souffle/problog 的多步派生能力(IDB)暂不产生子图。

**PyReason → `timeline` 形态** (`EvidenceTimeline`):
- 因果缺口:PyReason 无结构化 trace API,需轻量 grounding parser 解析 `Clause-N` 文本。
- **已决(R5)**:PyReason 用 `EvidenceTimeline` 作为独立容器结构,复用 `EvidenceAtom(timestep=...)` 作为叶节点;timeline 是独立结构(按时序组织 events),atom leaf 复用公共类型。parser 细节(Clause-N 文本解析)留作实施阶段确认。

---

## §7 已验证的 Shipped 事实

| 主题 | 事实 | 出处 |
|---|---|---|
| head 是 Rule | `head: Rule`(ports + when + desc) | evaluate_result.py:155 |
| 现代路径无 rule-in-rule | application Rule 拒 `RuleRefAtom` | rule.py:287-288 |
| 真实叶子 atom 类型 | PredAtom / CmpAtom / InAtom / BuiltinAtom / NotAtom | where_ast.py:31-100 |
| Aggregate 是操作数 | `Term = Var \| Const \| AggregateAtom` | where_ast.py:74-96 |
| atom_id 约定 | `c{case}.c{cond}:{pred\|kind}` | _support.py:205-226 |
| explain 是获胜单分支 | `winning_path_only`;`ast_form="single"` | evaluate_result.py:963,991 |
| 失败无证据 | `closed_head_false` + `evidence=None` | store.py:2525-2534 |
| diagnose 逐原子求值器 | `_eval_pred/eq/cmp/not/in` | diagnose_runtime.py:187-302 |
| join 端口已捕获 | `RuleExprJoinMaterialization(left/right occurrence.port)` | rule_expr_lowering.py:140-158 |
| AND lowering → flat branch | `rule1 & rule2` → atoms 合并为单一 flat branch;join 物化为 `CmpAtom(op="eq")` 追加在末尾 | rule_expr_lowering.py `_concat_branches`:745-763 |
| pyreason 无结构化 trace | `get_rule_trace` → 2 DataFrame | provenance.py:262-288 |
| problog 多 proof | `ProbLogTraceV0.answers: tuple`;多 proof = 多 `EvidenceTree` | provenance.py |
| v1 环检测不触发 | DFS 环检测存在但 v1 无 RuleRefAtom → 不触发;v2 内联派生时才激活 | rule_expr_lowering.py(F-EG-1) |

---

## §8 复用 vs 新增

**复用**:`Rule.when` AST;`diagnose_runtime._eval_*` 逐原子求值器;`view_facts/witness_facts`;`occurrence_map + join_materializations`;`Certainty` 载体(原 `raw_kind`/`bound` 合并);`timestamp` 字段;condition_key 约定。

**新增**:穷尽逐条件探查器(`application/explain/`);`EvidenceTree/EvidenceTimeline/EvidenceRule/EvidenceAtom/Fact/Compare/Builtin/Holds/Fails/NotReached/BoundVar/Const/Aggregate/Source/Certainty/PortRef/EvidenceJoin`;三层 status 三值;`ProbeEnv(bindings, bound_vars, binder_by_var)`;schema DSL `Field(repr=)/Identity(repr=)/Meta.repr`;`render_entity_repr` 应用层纯函数;渲染器默认表。

**Schema DSL 新增**(前置 slice,Prober 之前):`Field/Identity` 加 `repr=` 参数 + Entity `class Meta: repr` + 校验逻辑 + schema IR `repr` 字段存储。

**未来(v2)**:`support | EvidenceGraph`(内联派生子证明)+ 环护栏;`blocked_by` 扩展为 `tuple[BlockedDependency]`(per-var + reason 三分类)。

---

## §9 范围、缺口与开放问题

**已锁定决策**:

| 决策 | 结论 |
|---|---|
| Prober 是独立路径 | 不做成 evaluate flag |
| Prober 模块位置 | `application/explain/`(新建) |
| `EvidenceGraph` 在 `Explanation` | 不放 `EvaluateRow` |
| `EvidenceRef` 不复活 | EvaluateRow 保留 `closed_head_digest` |
| `NotReached` 触发条件 | 仅变量未绑定;前序 Fails 不触发 |
| Meta.repr identity-only | 硬性约束,无逃生口 |
| `%ENT/%FLD/%CLS` 占位语法 | 已锁 |
| v1 无内联派生 | ruleref 禁,无环,无子图 |
| `EvidenceRef` | 不复活 |
| `EvidenceAtom.repr_text` 字段 | 存储;prober assembly 烘焙(R1/R2) |
| Conclusion/atom label 来源不同 | 接受;各司其职(R3) |
| D-prose → `narrate()` | 新增,不替换 `repr`(R4) |
| PyReason → `EvidenceTimeline` + `EvidenceAtom` 复用 | 已决(R5) |
| `not_reached` 自底向上聚合 | 无 volitional skip;纯聚合语义(R6) |

**已决定但需更新原文档**:

0. **★必改不变式**:`Explanation.evidence non-None` 放宽到 `iff status ∈ {passed, failed}`。
1. **旧 `nodes/edges` 完全删除**:目标是完全删除;执行节奏:native 先 → adapters → 删字段。
2. ~~**多原子 `Not([..])` v1 不富解释**:范围声明。~~ 〔2026-06-10 已超越:Batch C 对多原子 Not 富解释,见 §4 negation / §5.7〕
3. **v1 环护栏不触发**:ruleref 禁 → 无递归无环。

**已知爆炸半径**:旧 `EvidenceGraph/Node/Edge` 被 adapters、audit、`walk_evidence`、round events、大量测试引用 — 换 body 需逐个安置。

**DTO 层爆炸半径**:shipped tests 中约 30-50 处 `row.claim.*` / `row.evidence_ref.*` / `result.expr_digest` 等 access path 需更新。

**仍未锁的问题**:

| ID | 问题 | 倾向 |
|---|---|---|
| Q-A | `RowKind` 在 query-style 下是否调整(删 `fact_triple` / 加 `query_row` / promote `projection`)? | 未锁 |
| Q-B | `build_application_rule` auto-prepend `:exists` 在 query-style/explain prober 下是保留/opt-out/删除? | 未锁;见 §13.2 |
| Q-C | `Claim`/`EvidenceRef` deprecated alias 保留多长?`result.expr_digest` 等是否提供 `__getattr__` fallback? | 倾向:首次 release 标 DeprecationWarning,下一 minor cycle 删除 |
| ~~Q-D~~ | δ arity mismatch 策略 | **已决(Option A)**:`head.id` 匹配 schema predicate 但端口数不符 → 继续 reject;free-form(不匹配)head 才走 query-style。向后兼容,防止 typo 被静默宽容。 |

**已决待落地(实施时执行)**:

| ID | 内容 | 说明 |
|---|---|---|
| **R7** | `Rule.desc → Rule.repr` 改名 + deprecated alias 过渡 | 见 §12;alias 过渡周期同 Q-C |
| **Certainty** | `EvaluateRow.raw_kind + bound` 合并为 `certainty: Certainty \| None` | 见 §3.1;与 `EvidenceTree.certainty`/`Holds.certainty` 共享类型;supersede 原 evaluate-result §3.3 raw_kind/bound 形态。引擎映射(preflight 锁定):native→`Certainty(1,1,"boolean")`/`Certainty(0,0,"boolean")`;problog→`Certainty(p,p,"probabilistic")`;pyreason→`Certainty(l,u,"possibilistic")` |
| **ResultFingerprint** | named sub-object(Option A)而非 `Mapping[str,str]` | 已决 Option A;见 §3.1 |
| **EvidenceRef-lite** | 不保留 cross-process 轻量 wrapper | 已决;`(result_id, row_id)` pair 替代;见 §3.2 |

---

## §10 实施 Slice 建议

### §10.0 DTO 前置切片(EvaluateResult / EvaluateRow flatten)

以下切片是 explain-layer S0-S6 的前置地基,需先于或同期执行:

```
α  Claim/EvidenceRef 冗余字段删除:删 Claim.name/arguments / EvidenceRef.row_id/fact_digest/ref_id/result_id
   → deprecated property fallback;不破坏现有 user code
β  ResultFingerprint sub-object 折叠:新增 ResultFingerprint DTO;原 6 个顶层 digest 字段改 deprecated @property
   → 同时 engine_version/adapter_version → engine_meta Mapping
γ  Claim/EvidenceRef wrapper 撤销 + 字段平铺:kind/digest → row;closed_head_digest → row
   → row.claim / row.evidence_ref 保留作 deprecated property 一个 release cycle
   → Explanation.claim → Explanation.row:EvaluateRow | None
ζ  bindings 形态简化:{pred_id, terms[]} → {port_name: term} map
   → 旧形态保留 deprecated 属性 1 cycle
δ  query-style head decoupling:_evaluate.py:148-157 find_schema_pred 改 optional lookup
   → arity check only-when-matched;matched-but-wrong-arity → reject(Option A,已决)
```

推荐顺序:**α → β → γ → ζ → δ**。α/β 低风险先做;γ 依赖 α/β 清理冗余;ζ 独立可并行;δ 最后(依赖前置 row 清理成熟)。

### §10.1 Explain-layer 切片(repr + prober)

```
S0  Rule.desc → Rule.repr alias migration(独立 slice,可与 α 并行)
S1  Schema DSL:Field(repr=)/Identity(repr=)/Meta.repr + 占位符校验 + 默认 label
S2  Schema IR:repr 字段 + Meta.repr 存储 + render_entity_repr 应用层纯函数
S3  Prober 主体:application/explain/ + ProbeEnv + 主循环 + atom probe + EvidenceTree 装配
S4  渲染集成:EvidenceAtom.repr_text 烘焙进 prober assembly + 渲染器默认表
S5  native 路径接通:Explanation.evidence non-None iff passed/failed + 旧 nodes/edges deprecated
S6  adapters 迁移:souffle / problog / pyreason 各自迁移到新 paths 结构
S7  旧 nodes/edges/root_node_id/support_kind 字段删除
```

§10.0 是前置地基;§10.1 S0 可与 §10.0 α 并行;S3(prober 主体)建议在 γ/ζ 完成后开始(prober 使用 EvaluateRow 结构)。

---

## §11 与其他设计文档的关系

- [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md):本文件是该路线图在"解释结构"维度的具体化;路线图的 D5/D11 等条目的 schema 实现细节在本文件。D21 desc-driven explain 由 `Rule.repr`/`repr_text` 承接(不走旧 desc_lines / walker)。
- [`archive/evaluate-result-flatten-and-query-style.zh.md`](../archive/evaluate-result-flatten-and-query-style.zh.md):有效内容已合并入本文件;旧 §3.9/§4.7(3-tier DAG + walker)已被 supersede。**已归档**。
- [`rule-namespace-rulespec-redesign.zh.md`](rule-namespace-rulespec-redesign.zh.md):本文件 **supersede** 其 §3.6/§4.7(`rule.id` ↔ pred_id 解耦那一支,见本文件 §3.1 query-style head);建议在该文件加 supersede 标注。
- [`entity-exists-claim-emission-gap.zh.md`](entity-exists-claim-emission-gap.zh.md):`build_application_rule` auto-prepend `:exists` 行为在 query-style 下角色变化(见 §9 Q-B);两份文档在 query-style 范式选定后需同步审视。
- **已归档文档**:`evidence-proof-model.zh.md` / `entity-repr-templates-and-inspect.zh.md` — R1-R7 全部锁定后已归档至 `workflow/design/design-points/archive/`。

### §11.1 对已有 ADR / INV 的边界声明

- **INV-6 application-first runtime authority**:本设计不破坏 INV-6。全部改动在 `factgraph.application.protocol` + `factgraph.sdk` 两层;`ResultFingerprint` / 平铺后 `EvaluateRow` / 调整后 `Explanation` 都是 application protocol DTO,SDK 仅 re-export。无 SDK 反向依赖,无 substrate 上移。
- **D17/D19 supersede 边界**:本设计 supersede 部分 D17(Claim/EvidenceRef wrapper 形态 + 字段集)+ 部分 D19(digest 字段位置 → ResultFingerprint;hash 算法不变)。`INV-6` 等更顶层 commitment 保留不变。
- **ADR-IC §4.4.2 `:exists` transitional guard**:query-style 下 `:exists` Claim 的角色需补 ADR 决定(retire vs 保留 co-emission);见 §9 Q-B。

---

---

## §12 Repr 命名体系 + R7:Rule.desc → Rule.repr

### §12.1 整个 repr 层的命名一览

| 字段/属性 | 含义 |
|---|---|
| `Field.repr` / `Identity.repr` | schema 字段对应 atom 的措辞**模板** |
| `Meta.repr` | 实体 label 的**模板** |
| `Rule.repr`(提案) | rule conclusion 的措辞**模板**(当前字段名为 `Rule.desc`) |
| `EvidenceAtom.repr_text` | prober assembly 后烘焙好的 atom **渲染文本**(`str \| None`) |
| `Explanation.repr_text` | walker 组装出来的结构化多行解释**文本**(`tuple[str, ...] \| None`) |
| `Explanation.narrate()` | (未来) prose 风格解释 |

统一原则:**`repr` 表示模板(template);`repr_text` 表示已渲染文本(rendered output)**。`repr_text` 在 atom 层是单行字符串,在 Explanation 层是多行 tuple — 语义一致,类型因层级不同。

### §12.2 R7:`Rule.desc → Rule.repr` — 已决

Codex 建议将 `Rule.desc` 改名为 `Rule.repr`,以与 `Field.repr` / `Meta.repr` 对齐,让整个"如何读成人话"的入口统一叫 `repr`。

**支持改名的理由**:
- 概念一致:所有"措辞模板"都叫 `repr`,无分裂。
- `desc`("description")语义模糊;`repr`("representation template")更精确。

**需要考虑的约束**:
- `Rule.desc: str | None` 已在 shipped 公开 API 中(`src/factgraph/application/protocol/rule.py`);`render_desc(bindings)` 方法也已 ship。
- 改名是 breaking change,需要 deprecated alias 过渡。
- `Rule.desc` 在 `evaluate_result.py:740`(closed-head carry-over)、`explanation-completion-roadmap §6.6`(D21 desc-driven NL)等多处被引用,改名需要逐一更新。

**迁移方案(如果决定改名)**:
1. `Rule.repr` 作为 canonical 字段;
2. `Rule.desc` 作为 deprecated alias — 构造时接受,内部归一到 `repr`;
3. `Rule.render_desc(bindings)` → `Rule.render_repr(bindings)`,旧方法保留并 warning;
4. 文档新写法全部用 `repr`。

**已决:纳入本次 blueprint 周期**。迁移方案按上述四步执行。作为独立 slice(S0 之前或 S0 内),体量小,不 block 主体 prober 实施。

---

---

## §13 代码锚点(实施参考)

合并自 `evaluate-result-flatten-and-query-style.zh.md §8`。

| 文件 | 行 | 说明 |
|---|---|---|
| `application/protocol/evaluate_result.py:86-101` | Claim 定义 | α/γ 删除目标 |
| `application/protocol/evaluate_result.py:103-116` | EvidenceRef 定义 | α/γ 删除目标 |
| `application/protocol/evaluate_result.py:119-157` | EvaluateRow 定义 + D17 invariant 校验 | γ/ζ 改造目标 + 删除 invariant 校验 |
| `application/protocol/evaluate_result.py:162-256` | EvaluateResult 定义 + 7 digest/id 字段 | β 改造目标(→ ResultFingerprint) |
| `core/store/_evaluate.py:148-157` | `find_schema_pred` + arity check 两条 raise | δ 改造目标(→ opt-in) |
| `sdk/store.py:_explain` | `evidence_ref.closed_head_digest` access | §3.2 迁移:改为 `row.closed_head_digest` |
| `application/protocol/rule.py` | `Rule.desc` / `render_desc` | S0(R7)改造目标(→ `Rule.repr`/`render_repr`) |
| `audit/evidence_graph.py` | `NodeKind` / `EdgeKind` / `_build_*_evidence_graph` | S5/S7 改造目标(旧 nodes/edges 删除) |
| `docs/quickstart/evaluate_and_evidence.md §5.1` | 结构图漏列 souffle | 独立 docs drift fix(可独立 commit) |

---

*End of explain-layer-complete-design.zh.md (2026-06-08, merged from evaluate-result)*
