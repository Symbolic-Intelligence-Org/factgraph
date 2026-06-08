# Evidence 重做:穷尽逐条件解释模型(`EvidenceGraph` body 换芯)

> **本文件状态**: draft (2026-06-05); 设计探索 / 初稿; 待进一步细化,可能重开一份文档。
>
> **权威边界 (per `workflow/design/design-points/README.md`)**:
> 一个 design-point 是**候选设计 / 非权威参考**。它仅当被一个 adopted decision、一个 implemented blueprint、当前模块 docs、或 `architecture_principles.md` 引用时才成为约束。本文件描述的均为**提案**,尚未实现,**不得**据此认为代码已存在。

- First draft: 2026-06-05
- Last updated: 2026-06-05(envelope + body + EvidenceAtom 收敛:form/verdict/atom_id/negated;Fact/Source 改名;support 扁平;去 Computed/Grounded/Negated/Site)
- Scope: 用穷尽逐条件结构重做 evidence/解释层的 **内容(payload)**;沿用 `Explanation` + `EvidenceGraph` 外壳,按 `layout_hint` 把 `paths` 分成 `tree`(native/souffle/problog)| `timeline`(pyreason);旧扁平 `nodes/edges` payload 被取代(去留见 §8)。
- Parent / 相关:
  - [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md)(解释层路线)
  - [`entity-repr-templates-and-inspect.zh.md`](entity-repr-templates-and-inspect.zh.md)(L3 渲染:`repr` 模板把 `EvidenceAtom` 渲染成自然语言)
  - [`evaluate-result-flatten-and-query-style.zh.md`](evaluate-result-flatten-and-query-style.zh.md)(rule_expr / 单分支 explain 现状)
- 触发动机:多轮实测确认现有 `EvidenceGraph` 是**获胜单分支快照**——失败分支零痕迹、失败时 `evidence=None`、`ast_form` 恒 `single`。用户要的是**同时解释成功与失败、逐条件最终状态、保留 rule_expr 拓扑**的用户面解释。

---

## §1 问题:现有 evidence 是"获胜单分支快照"

实测(本 session,native 路径,`/tmp` 探针,只读未改码)三次确认:

1. **join 失败拿不到 mismatch**:整体失败时 `explain` 返回 `failure_class="closed_head_false"`、`evidence=None`。
2. **成功经 OR 时,失败分支零痕迹**:`(region=us) | (region=eu)`、seed `eu`,成功行的 evidence 里 `'us'` 分支完全不出现;`conclusion.alternative_paths = {"mode":"winning_path_only","omitted_count":None}`;`rule_expr.engine_meta.ast_form = "single"`(OR 被压平)。
3. **根因**:解释走的是 **evaluation 捕获**(`ProofReceipt` 只为获胜分支构造,`_support_capture` 取 `_require_selected_branch`)。

→ evaluation 天生只记获胜单线。要"成功/失败统一 + 全展开",**解释不能复用 evaluation 路径**,需要一条**专门的、穷尽逐条件**的链路。

## §2 核心决策

1. **解释 = 专门的穷尽逐条件探查器**:遍历 rule_expr 每条分支、每个原子,**逐个独立求值并记录各自最终状态(不短路)**,成功/失败统一覆盖。这是三条路中**唯一可行的**:
   - **evaluation 路径不可复用**:evaluation 天生短路、只记获胜分支(§1 已实测:`ProofReceipt` 只为获胜分支构造,OR 失败分支零痕迹,失败时 `evidence=None`);结构上就无法产出逐 atom 三态;
   - **引擎层内嵌方案不可行**:在 Datalog/ProbLog 程序里手写 `why_not_*(X, Reason, …)` / `proof_step(X, StepN, …)` 子句必须与主规则**手动同步**——主规则改一个条件,这两套子句都要跟着改,易脆、不可维护;
   - **Python 侧探查器是唯一自动化路径**:直接遍历 `Rule.when` AST(`tuple[Atom,…]` 已结构化)+ 复用 `diagnose_runtime._eval_*` 逐原子求值器,**不改引擎程序、天然与规则保持同步**。新 evidence 结构的逐 atom 三态(Holds / Fails / NotReached)、全分支覆盖、join 状态可见,以这条链路为前提——无它,新结构的粒度不可达。
2. **保壳换芯**:保留 `Explanation` + `EvidenceGraph` 外壳;把 `EvidenceGraph` 的 `paths`(旧 `nodes/edges/root_node_id/support_kind`)换成穷尽逐条件结构;原独立的 `EvidenceReport` **并入 `EvidenceGraph`**。
3. **按 rule_expr 原样组织**(and/or 拓扑),**不摊平成 DNF 执行形态、不排执行序**;每个 atom 只挂**最终状态**。
4. **无"推理步(step)"概念**:组织原语是"结构 + 每节点状态",不是执行序。

## §3 结构定义(提案,v1 收敛版)

层级:`Explanation`(状态壳)→ `EvidenceGraph`(容器 / `layout_hint` 判别 / 单主体)→ `paths: tuple[EvidenceTree | EvidenceTimeline]` →〔tree〕`EvidenceTree`(一条路径 = 一个 proof)→ `EvidenceRule`(head 亦是)→ `EvidenceAtom`(条件 + 最终状态);join 作 `EvidenceRule` 间链接。

```python
# ===== 外壳(沿用现状,仅 evidence 不变式放宽,见 §8 第 0 条)=====
@dataclass(frozen=True)
class Explanation:
    status: Literal["passed", "failed", "unsupported", "invalid_request"]
    evidence: "EvidenceGraph | None"        # ★放宽:non-None iff status ∈ {passed, failed}
    row: "EvaluateRow | None"
    result_id: str | None
    failure_class: "ExplanationFailureClass | None" = None
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
    # repr:@property(lazy / 私有 _repr_cache),非构造字段

# ===== 容器(并入原 EvidenceReport;旧 nodes/edges/root_node_id/support_kind → paths)=====
@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str                             # native / souffle / problog / pyreason
    layout_hint: Literal["tree", "timeline"]
    subject_binding: Mapping[str, Any]      # 在解释谁(如 {person: alice});一个 explain = 一个主体(实证:per-row)
    paths: tuple["EvidenceTree | EvidenceTimeline", ...]   # 原 body;tree 引擎=多条推理路径;pyreason=时序(通常 1 条)
    certainty: "Certainty | None" = None    # 聚合后的最终不确定度(problog 跨多路径的最终概率);Certainty.kind↔raw_kind
    metadata: Mapping[str, Any] = MappingProxyType({})
    # 不变式:paths 元素全 EvidenceTree(layout=="tree")或全 EvidenceTimeline(layout=="timeline")

@dataclass(frozen=True)
class EvidenceTree:                         # 一条推理路径(= 一个 proof);native / souffle / problog
    tree_id: str
    status: Literal["holds", "fails", "not_reached"]
    # holds   = 该路径所有条件成立
    # fails   = prober 求值过,不成立
    # not_reached = prober 主动跳过整棵树(OR 分支优化);rules/joins 为空
    rules: tuple["EvidenceRule", ...]       # 含 head(role="head");not_reached 时为空
    joins: tuple["EvidenceJoin", ...]       # not_reached 时为空
    certainty: "Certainty | None" = None    # 该路径的不确定度(problog 单证明概率)

@dataclass(frozen=True)
class EvidenceTimeline:                     # 一条时序;pyreason
    status: Literal["holds", "fails"]       # pyreason 顺序求值,无 not_reached 概念
    events: tuple["EvidenceAtom", ...]      # 时间序(EvidenceAtom 复用,带 timestep);update 链由顺序表达
    certainty: "Certainty | None" = None

@dataclass(frozen=True)
class EvidenceRule:                         # rule occurrence;head 是 role="head"
    occurrence_alias: str
    rule_id: str
    role: Literal["body", "head"]
    status: Literal["holds", "fails", "not_reached"]
    # holds       = 所有 atoms holds
    # fails       = 至少一个 atom Fails(其余可 Holds/NotReached)
    # not_reached = 所有 atoms 均 NotReached(派生状态,atoms 仍填充;≠ tree.not_reached)
    ports: Mapping[str, Any]                # port_name → 该 occurrence 此行的解析值(镜像 Rule.ports,带值);join 引用它
    atoms: tuple["EvidenceAtom", ...]       # not_reached 时内容全为 NotReached verdict

# ===== 叶子:EvidenceAtom =====
@dataclass(frozen=True)
class EvidenceAtom:
    form:    "Fact | Compare | Builtin"     # 判定什么(3 个真实叶子)
    verdict: "Holds | Fails | NotReached"   # 判定结果(各带所需)
    atom_id: str                            # 真实约定:c{case}.c{cond}:{pred|kind}
    negated: bool = False                   # 单原子 \+;多原子 Not([..]) v1 不富解释(见 §8)
    timestep: int | None = None             # 仅 pyreason
    # repr 派生(__str__),非字段

# —— form(各自合身;exists 是 :exists 上的 Fact)——
@dataclass(frozen=True)
class Fact:     predicate: str; terms: tuple["Operand", ...]
@dataclass(frozen=True)
class Compare:  op: str; lhs: "Operand"; rhs: "Operand"                 # op ∈ eq/ne/gt/ge/lt/le
@dataclass(frozen=True)
class Builtin:  op: str; args: tuple["Operand", ...]; result: "Operand" # op ∈ add/sub/neg/addc/mulc;映射 AST 的 BuiltinAtom

# —— verdict(三态,各带所需)——
@dataclass(frozen=True)
class Holds:      certainty: "Certainty"; support: tuple["Source", ...] = ()   # support 仅 Fact 用;Compare/Builtin 为 ()
@dataclass(frozen=True)
class Fails:      certainty: "Certainty"                                       # "为何/差多少" → repr 现算,不存
@dataclass(frozen=True)
class NotReached: blocked_by: str | None                                      # 卡住它的上游 atom_id

# —— Operand(Term 三形态;BoundVar 区别于授权层 where_ast.Var)——
@dataclass(frozen=True)
class BoundVar:  name: str; value: Any | None; bound_by: str | None    # value=None=未绑定;bound_by=绑定它的 atom_id
@dataclass(frozen=True)
class Const:     value: Any                                            # 原 Lit;对齐 AST 的 Const
@dataclass(frozen=True)
class Aggregate: kind: str; target: "Operand | None"; filter: Any; value: Any | None  # count/sum/min/max/mean(分组折叠)

@dataclass(frozen=True)
class Source:    ref: str; field: str; value: Any; meta: Mapping[str, Any]  # 落地它的断言(原 GroundFact);meta 含 asrt_id/来源/时间

@dataclass(frozen=True)
class Certainty: lo: float; hi: float; kind: Literal["boolean", "probabilistic", "possibilistic"] = "boolean"
    # __str__ → ✓ / ✗ / 0.73 / [0.6, 0.9]

@dataclass(frozen=True)
class PortRef:                              # 镜像 substrate 的 RulePortRef:指向某 occurrence 的某 port
    occurrence: str                         # occurrence_alias
    port: str                               # port_name

@dataclass(frozen=True)
class EvidenceJoin:                         # 两个 rule occurrence 在各自一个 port 上等同
    left: PortRef
    right: PortRef
    held: bool                              # = (left port 值 == right port 值);共享值/不匹配值从两端 EvidenceRule.ports 解析,不另存
```

**命名/取舍说明:**
- `Pred → Fact`(友好;exists = `:exists` 上的 Fact);`GroundFact → Source`(避免与 `Fact` 撞);`Lit → Const`(对齐 AST)。
- `Builtin` 保留(对齐 AST `BuiltinAtom`,跨层零歧义;不直观由 repr 化解 `z = x+y`)。
- **`Member`(InAtom)不进 form**:`in` 是列表成员、当前**不支持列表**;它在 AST/runtime 是 latent(裸 IR 可进),用户写不出来。
- **`support` 扁平 `tuple[Source]`**:去掉 `Grounded/Derived` 包装、也去掉 `| EvidenceGraph`(见 §4/§8:v1 无内联派生)。2 操作数不混淆——每操作数的来源在自己 `BoundVar.bound_by` 上。
- **三层 holds 对称**:`EvidenceAtom.verdict` / `EvidenceRule.status` / `EvidenceTree.status` 每层都有显式判定,消费者无需 walk 子层来判断上层是否成立。`EvidenceRule.status` 虽可从 atoms 派生,但显式存使渲染和摘要直接可用。`EvidenceAtom.verdict` 刻意保持三值(`Holds|Fails|NotReached`)而非二值——`NotReached(blocked_by)` 区分了"条件计算了但不成立"与"上游变量未绑定、条件甚至无法计算",两者诊断意义不同。`EvidenceTree` 层聚合 = 所有 rules holds AND 所有 joins held(join 是跨 rule 约束,不进任何单个 rule)。
- **`engine_meta`**:节点尽量不带;字段全提升为一等。只留"真正引擎专属、暂未结构化"的机制(见 §5 PyReason)。
- **迁移面**:外壳(`graph_id/engine/layout_hint/metadata` + `Explanation`)保留 → 只读外壳的消费者不动;只 `paths` 换芯 → 只 `paths` 消费者(`walk_evidence`/adapters/audit/测试)迁移。比"全改名"爆炸半径小。

## §4 关键语义(均经本 session 确认或推导)

- **镜像 rule_expr,不摊平**:OR → 多个 `EvidenceTree`(路径);每条路径内是它那条合取(rules + atoms + joins)。
- **三层 `not_reached` 语义各异**:
  - `EvidenceTree.status = "not_reached"`:prober **主动跳过**整棵 OR 分支树(volitional);`rules/joins` 为空;记录"这条分支没有被求值"。
  - `EvidenceRule.status = "not_reached"`:prober 求值过该 rule 的所有 atom,但**全部因上游变量未绑定而 NotReached**(派生);`atoms` 仍填充(内容全是 `NotReached` verdict);`"求值了但全受阻"` ≠ tree-level 的 `"没求值"`。
  - `EvidenceAtom.verdict = NotReached(blocked_by)`:单个 atom 因上游 binder 失败而无法求值;`blocked_by` 指向卡点 atom_id。
  - **快速扫描路径**:看 tree/rule/atom 各层 status 即可定位;只有需要追溯原因时才进 atoms。
- **verdict 三态**:`Holds(certainty, support) | Fails(certainty) | NotReached(blocked_by)`,**各带所需**。`Fails` 不存 reason("为何/差多少"由 `repr` 从 form+操作数现算)。`NotReached` 来自数据依赖(上游 binder 失败 → 变量未绑定 → 无法求值),`blocked_by` 指卡点 atom_id。
- **Builtin 是计算非判定**:结果落 `Builtin.result`,verdict 用 `Holds`(算出)或 `NotReached`(参数未绑定);**不设 `Computed` 变体**。
- **compare 中性**:`Compare(op, lhs, rhs)`,操作数自带 `value`;"required/actual" 是 repr 解读(`Const` 侧读作 required)。
- **negation 用 `negated: bool`**:单原子 `\+` 翻转(inner 无事实 → 否定 Holds;inner 有 → 否定 Fails)。**多原子 `Not([a,b])` 支持但罕见,v1 不富解释(范围声明,§8)**;**整条规则否定不支持**(需 ruleref,被禁)。
- **head 也是 rule**(已验证 `head: Rule`):用 `EvidenceRule(role="head")`;结论含义/verdict 在 `EvidenceGraph`/`Explanation` 顶层。
- **多途径 = `paths` 里多个 `EvidenceTree`**:`holds ⟺ 任一路径 holds`;失败时每条路径也在,逐 atom 看为何不成立。problog 的最终概率 = 跨多路径聚合,存 `EvidenceGraph.certainty`(实证:`ProbLogTraceV0.answers` 是 tuple、`answer_count`)。
- **不确定度走 `Certainty` 载体**:native → `Certainty(1,1,"boolean")`(✓)/`Certainty(0,0,"boolean")`(✗);problog → `Certainty(p,p,"probabilistic")`;pyreason → `Certainty(l,u,"possibilistic")`。聚合由引擎算,存 `EvidenceGraph.certainty`。
- **atom_id 是真实 condition_key**:`c{case}.c{cond}:{pred|kind}`(`_support.py:212/226`);`bound_by` / `blocked_by` 都引用 atom_id。
- **v1 无内联派生 ⇒ 无递归、无环**:ruleref 被禁 → 单次 evaluate 无 rule 内递归;多步派生经 ledger 跨 round 暂存 → 派生结论以 `Source`(ledger 事实)出现,**不内联子证明**。故 v1 `support` 只到 `Source`,无 `EvidenceGraph` 子图、无 `derived_support` 递归、**环护栏不触发**(随未来 derived-support 再做)。
- **可操作(reeval)是外部函数,不焊进节点**:atom 是纯数据(form + 操作数 + support),re-run / what-if 由外部 `reeval(atom, overrides, store)` 复用 `diagnose_runtime` 的 `_eval_*`,**只覆盖 per-atom/operand 层**;整条 rule 的 what-if = 重新 `evaluate()`,不进 evidence 模型。

### 范例(`eligible`,carol 在察看期 → fails)

```
EvidenceGraph(engine="native", layout_hint="tree", subject={X: carol})   # Explanation.status="failed"
└ paths = [ EvidenceTree(status="fails")                     # 一条路径(= 一个 proof)
      └ EvidenceRule(role="head", atoms=[
          Fact("person:exists",[carol])              → Holds(✓, support=[Source(carol,"person:exists",None,…)])
          Fact("full_time",[carol])                  → Holds(✓, support=[Source(...)])
          Fact("user:tenure",[carol, M])             → Holds(✓, support=[Source(carol,"user:tenure",24,…)])
          Compare("ge", BoundVar("M",24,"c0.c2:user:tenure"), Const(12)) → Holds(✓)
          Fact("on_probation",[carol]) negated=True  → Fails(✗)   ← carol 在察看期,\+ 失败:失败定位在此
          Fact("training_complete",[carol])          → Holds(✓, support=[...])
        ])
```
- 若 carol **无 tenure 记录**:`Fact("user:tenure")` → `Fails`,其后 `Compare("ge", BoundVar("M", value=None), …)` → `NotReached(blocked_by="c0.c2:user:tenure")`(三值)。
- `repr` 现算:`"age 24 ≥ 12 ✓"` / `"NOT on_probation(Alice) ✗"` / `"M ≥ 12 — 未求值(上游 c0.c2 未绑定)"`。

## §5 引擎范围

**native + souffle + problog 共用 `tree` 形态(`paths: tuple[EvidenceTree]`,每条 = 一个 proof → `EvidenceRule/Atom`)**:
- problog:结构与 native/souffle 同构,只多**概率项** → 落 `EvidenceTree.certainty`(`Certainty(p,p,"probabilistic")`;`p=0` 即 false)。聚合(disjoint-sum)引擎算,最终概率存 `EvidenceGraph.certainty`。
- souffle/problog 的**多步派生(IDB,派生谓词链)**需要 `derived_support` 子图——但现代路径禁 ruleref → **v1 不产生内联派生**;该能力随 §8 的 derived-support 一并未来再做。

**PyReason:用 `timeline` 形态(`EvidenceTimeline`);节点可共用,结构是时间流,因果需一层 parser**:
- 节点共用:uncertainty → `EvidenceAtom.verdict.certainty = Certainty(l,u,"possibilistic")`;时间 → `timestep`。
- 结构不同:事件按 `(component_type, component, label)` 串成**时间链**,非合取树。
- **因果缺口(已量化)**:PyReason 无结构化 trace API,`get_rule_trace` 只返回 2 张 pandas DataFrame(官方确认);`Clause-N` 列是 grounded 组件的 list/tuple **文本**,`"Occurred Due To"` 是规则。→ 需一层**轻量 grounding parser**(解析 `Clause-N` 文本 + 用我们可控命名回映射到 entity ref)。**是"解析引擎输出",非"重构因果"**;有界、确定性,但耦合引擎输出格式(随版本维护)。
- 决策待定:PyReason 走"统一 + 时序扩展字段",还是"专属变体"。

**legacy `RuleRef` / `Inference` 路径:范围外**(现代 application `Rule` 禁 ruleref)。

## §6 已验证的 shipped 事实(grounding / 三段式 triage 基础)

| 主题 | 事实 | 出处 |
|---|---|---|
| head 是 Rule | `head: Rule`(ports + when + desc) | evaluate_result.py:155 |
| 现代路径无 rule-in-rule | application Rule 拒 `RuleRefAtom`;`build_application_rule` `allow_ruleref:False` | rule.py:287-288;application_rule.py:65 |
| 真实叶子 atom 类型 | PredAtom / CmpAtom(eq/ne/gt/ge/lt/le) / InAtom / BuiltinAtom(add/sub/neg/addc/mulc) / NotAtom | where_ast.py:31-100 |
| NotAtom 是组合子 | `NotAtom.body: WhereExpr`(AndExpr\|OrExpr)→ 包子表达式,非叶子;`Not(body: list)` 多原子可写 | where_ast.py:68-71;expr.py:238/302 |
| Aggregate 是操作数 | `Term = Var \| Const \| AggregateAtom`(count/sum/min/max/mean) | where_ast.py:74-96 |
| InAtom 无 SDK 授权语法 | 仅裸 IR/透传可进;`in` = 列表成员、当前不支持列表 | where_ast.py:209;match_runtime.py:316 |
| atom_id 约定 | `make_pred_condition_key`/`make_non_fact_step_key` → `c{case}.c{cond}:{pred\|kind}` | _support.py:205-226 |
| explain 是获胜单分支 | `alternative_paths.mode="winning_path_only"`;`ast_form="single"`(硬编码) | evaluate_result.py:963,991 |
| 失败无证据 | `closed_head_false` + `evidence=None` | 实测 + store.py:2525-2534 |
| diagnose 定位失败原子 | `(case_index, failed_atom_index, attempted_binding)`;逐原子求值器 `_eval_*` | diagnose_runtime.py:187-217,260-302 |
| 原子状态数据已存在 | `ProofReceipt`:pred_witnesses(asrt_ids)/ non_fact_steps(kind/status/details) | _support_capture.py:71-91;evaluate_result.py:1241-1313 |
| join 端口已捕获 | `RuleExprJoinMaterialization(left/right occurrence.port)` | rule_expr_lowering.py:140-158 |
| adapters 跑真引擎 | souffle 子进程 `.dl`;problog 子进程 `--trace`;pyreason 真库 | runner.py:86-93;problog_engine.py:20-33;pyreason/runner.py:348 |
| pyreason 无结构化 trace | `get_rule_trace`→2 DataFrame;`Clause-N`=grounded 文本 | 官方 docs;provenance.py:262-288 |
| 通用不确定度载体 | `raw_kind`(probabilistic/possibilistic)+`bound`(区间) | evaluate_result.py:1491-1499 |
| timestamp 一等字段 | `EvidenceNode.timestamp`,pyreason 已用 | pyreason/provenance.py:194 |
| F-EG-1 环检测(现状) | DFS,`path` 命中即 raise;`visited` 重访(DAG/共享)允许 | evidence_graph.py:106-126 |

## §7 复用 vs 新增

- **复用**:`Rule.when` AST;`diagnose_runtime` 逐原子求值器(`_eval_pred/eq/cmp/not/in`);`view_facts`/`witness_facts`;`occurrence_map`+`join_materializations`;native `ProofReceipt`/`RuleTraceInvocation`;`raw_kind/bound` 载体;`timestamp` 字段;condition_key 约定(`atom_id`)。
- **新增**:穷尽逐条件探查器(全分支全原子、不短路);`EvidenceGraph(subject_binding, paths)` + `EvidenceTree(status∈holds/fails/not_reached)`(一条路径=一个 proof)/`EvidenceTimeline` + `EvidenceRule(status∈holds/fails/not_reached, ports, atoms)` + `EvidenceAtom` + `Fact/Compare/Builtin` + `Holds/Fails/NotReached` + `BoundVar/Const/Aggregate` + `Source` + `Certainty` + `PortRef` + `EvidenceJoin`;三层 status 三值(语义各异);中性 compare 提取;atom 三态 verdict;negation flag;多路径(多 `EvidenceTree`)装配;`reeval(atom, overrides, store)` 外部薄函数(复用 `_eval_*`,只 per-atom 层);PyReason grounding parser。
- **未来(随 derived-support 一并)**:`support` 的 `| EvidenceGraph`(钻入派生事实的子证明)+ 对应的 ancestor 追踪 / back-ref 环护栏。

## §8 范围、缺口与开放问题

0. **★必改不变式(关键)**:`Explanation.evidence non-None` 现状 `iff status == passed`,**必须放宽到 `iff status ∈ {passed, failed}`**——否则失败时 `evidence=None`,"解释失败"目标落空。`status` 仍是 passed/failed 判定;只有 `unsupported / invalid_request` 才无 body(仅 errors)。
1. **旧 `EvidenceGraph` nodes/edges 的去留**:**目标是完全删除**。旧扁平结构是 evaluation-capture 产物,和新穷尽结构在语义上不兼容——保留两套是负担。执行节奏:① native 先实现新 `paths` 结构 → 验证 → ② adapter(souffle/problog/pyreason)跟进各自迁移 → ③ 旧 `nodes/edges/root_node_id/support_kind` 字段删除。中间窗口期旧字段可标 deprecated,但不维护语义;不做"用户面新 / 审计旧"双轨。
2. **PyReason 因果 parser**:解析 `Clause-N` + 命名回映射;变体 vs 时序扩展待定。
3. **审计 vs 解释**:"富解释"与"不可变可重放取证记录"是两个目标;新结构可序列化,但是否完整取代 audit 需单独确认。
4. **多原子否定 `Not([a,b])`**:语法支持但罕见;v1 `negated: bool` 只富解释单原子;多原子 v1 不建模(需要时再加结构形态)。
5. **derived-support 与环**:v1 **不产生**内联派生(ruleref 禁)→ 无递归、无环,**v1 不需要环护栏**;一旦未来加 `support | EvidenceGraph`(钻入派生证明),再补 ancestor 追踪 + back-ref(复用 F-EG-1 的 `path` 思路,**遇重访发 back-ref、不抛错、不无限**)。
6. **爆炸半径**:旧 `EvidenceGraph/Node/Edge` 被 adapters、audit、`walk_evidence`、round events、大量测试引用——换 body 需逐个安置。

## §9 与 entity-repr / explanation-roadmap 的关系

- `EvidenceAtom` 的 `repr`(`__str__` 派生)由 [`entity-repr-templates-and-inspect.zh.md`](entity-repr-templates-and-inspect.zh.md) 的 `%CLS/%ENT/%FLD` 模板产生。数据层(本文件)保持中性,repr 是其投影。
- 本文件是 [`explanation-completion-roadmap.zh.md`](explanation-completion-roadmap.zh.md) 在"解释结构"维度的具体化。

## §10 后续

- 本文件为**初稿**;下一步:与用户进一步细化(范围 i/ii/iii、PyReason 变体决策、Aggregate.filter 细节),**可能重开一份文档**。
- 细化收敛后,动核心子系统需按工作流:**先 preflight 审计(读全部消费者 + 旧 vs 新 triage 表)→ blueprint → 用户授权后实现**。本文件 §6 即 preflight 的事实基础。
- 未经授权不写实现代码。
