# Evidence Tree Design — Rainbird-Style v1

- Status: working / draft skeleton (Phase A, 2026-05-18)
- Authority: non-authoritative reference note; not current implementation truth
- Created: 2026-05-18(Phase A skeleton 落地;§4-§12 / §14 [SKELETON pending] 待 Phase B)
- Parent: `rule-expression-and-proof-attempt.zh.md`(主文档 §7 已 stub 化,引用本文档)
- Sibling: `database-view-fg-layered-architecture.zh.md`(view 4-layer 子系统设计)
- Scope: 基于 Rainbird Rule-instance-level granularity 的 v1 evidence tree 设计;承接主文档 §3-§5 已锁 Rule / RuleExpr / Head / API 架构
- Current Truth Note (2026-05-22): this note remains future-design input, not
  the current implementation contract. Current shipped evidence behavior lives
  in `src/factgraph/audit/docs/02_evidence_graph.md`,
  `src/factgraph/audit/docs/03_audit_package_contract.md`, and
  `docs/official/kernel/quickstart/evidence.md`. S1-S6 / I10-A10 style seams
  remain future design topics unless migrated into module docs or a scoped
  blueprint.

## 目录

```text
§1   立场与边界                                       [Phase A 落地]
§2   词汇表(含 Rainbird 词汇映射)                    [Phase A 落地]
§3   架构定义(承接主文档 §5.8 / 原 §7.1-§7.4)         [Phase A 落地]
§4   EvidenceNode / EvidenceEdge schema + engine_meta  [Phase B-1 落定 2026-05-18,C82-C89 + C91 + C106;Wave 2 C127-C129 root/aggregate metadata]
§5   Source Taxonomy(3-enum,2026-05-19 Wave 1/Wave 2 修订) [Phase B-2 落定;C107-C109 + C121 + C126]
§6   Quantitative Metrics(carrier-only)              [Phase B-3 落定 2026-05-18,C110-C113;raw_kind+bound 唯一 canonical carrier;数学聚合 deferred 至 §8]
§7   Explain Orchestrator(流程 / 调度)                [Phase B-5 落定 2026-05-19,C130-C135;8-step pipeline + dispatch + validator gate]
§8   Evidence Tree Topology(格式 / 结构)              [Phase B-4 落定 + Wave 1/Wave 2 修订 + Aggregate topology 补;C114-C119 + C123/C124 + C129 + C136]
§9   Failure-Side Handling(C81 已修订锁定 2026-05-18)  [Wave 2 #3 failure envelope 落地;C125]
§10  Audit Channel(v1)                              [SKELETON pending — Phase B]
§11  Rendering(沿用 audit/evidence_graph.py)         [SKELETON pending — Phase B]
§12  Rainbird 对照下的产品边界声明                    [Phase B-6 落定 2026-05-19,C137;§12.1-§12.5 5 维度 + §12.6 commitment]
§13  设计承诺 Commitments(C79-C137)                  [§7 orchestrator C130-C135 + §8.10 aggregate topology C136 + §12 product boundary C137]
§14  显式 Deferred Items                              [SKELETON pending — Phase B]
```

---

## 1. 立场与边界

### 1.1 v1 定位:Rainbird-level + 我们 8 项优势

**对齐 Rainbird** Rule-instance-level granularity:
- 每 closed_head → 单 EvidenceGraph
- 成功侧 atom-complete tree(per fired Rule 的 conditions / atoms 全列)
- Source taxonomy(3-enum,详 §5)
- Lazy/on-demand explain via `row.explain()` / `result[i].explain()` 等价 Rainbird factID-based entry;`row.close()` + `fg.eval.explain(expr, head=closed_head)` 保留为 advanced manual path

**超出 Rainbird(我们 v1 兑现)**:

| # | 优势 | v1 兑现方式 |
|---|---|---|
| O1 | EvidenceGraph 自带 cycle 检测 | 已 ship `audit/evidence_graph.py:95-115` |
| O2 | probabilistic / possibilistic 严谨范式 | `raw_kind` + `bound`,不引入 1-100 certainty factor |
| O3 | stateless evaluation | evidence 跨进程可比(canonical digest);Rainbird 是 session-bound |
| O4 | AND-only Rule cleaner | 成功侧不存在"未评估的 OR 后续"问题(per 主文档 C9)|
| O5 | shipped renderer + 2 layouts | `audit/evidence_graph.py:render_evidence_graph_html` tree + timeline |
| O6 | `atom_id` 稳定身份(主文档 C19)| evidence 锚到 atom 粒度;Rainbird 仅 factID + factKey |
| O7 | canonical digest 跨进程稳定(主文档 C68 / §5.8.5)| evidence 可作 durable audit artifact |
| O8 | EvidenceGraph 是 DAG(允许分叉,禁止环)| shipped `audit/evidence_graph.py:95-115` cycle 检测但允许多边汇聚同一节点;天然支持 ProbLog 多 derivation path 加权聚合(详 §6 / §8 [pending]);Rainbird CF model + 传统 proof tree 都不直接支持分叉聚合 |

**主受众**:**dev / author / auditor**(沿用 Rainbird 立场 + 我们 alpha 期 dev tool 定位);**不针对** end-user UI(NL narrative 走 head.desc 模板渲染,不走 LLM)。

### 1.2 v1 显式不做(deferred,详 §14 [pending])

| 不做 | 触发条件(v2+)|
|---|---|
| atom-complete failure-side probing(每 atom 打 violated 标)| 用户明确需求"failed 时每 atom 状态"|
| impact % decomposition(Shapley / 加权累加)| 用户需要 attribution analysis |
| salience condition weights | 跨 condition 权重出现实际诉求 |
| session log channel(Rainbird `/interactions/` 等价)| 出现 session-style interactive flow |
| LLM-derived NL explain | head.desc 模板渲染不够 |
| per-fact ACL(x-evidence-key 等价)| multi-tenant 服务部署 |
| PyReason Form 2 evidence(时间步)| Form 2 设计独立推进 |
| Why-not / counterfactual analysis | 用户出现明确 attribution / what-if 需求 |
| Eager / Lazy 切换(目前 eager)| evidence > 10MB 或渐进 UI 需求 |
| Why-provenance(SAT-based minimal fact set)| 学术族算法成熟 + 用户需求成形 |
| **Atom-level 失败定位**(top-down goal-regression / abduction)| 替代 v1 lossy 单点 locator;大事实库下 single-locator 启发式不稳定(`diagnose_runtime.py:220-257` 6 caveats);v2+ 设计基于 closed_head 自顶向下回溯"还差哪些 fact" 的算法(参 Bourhis-Lutz-Krötzsch 2024 / Elhalawati 2022 why-not provenance)|
| **`fg.diagnose` SDK 表面**(shipped application-layer 保留作 internal/legacy)| 与上一项绑定;v1 SDK **不公开** diagnose;v2+ 公开新 API(可能命名 `fg.eval.why_not` 或 `fg.eval.unsatisfiable_witness`)|

### 1.3 与主设计文档引用关系

**Parent**:`rule-expression-and-proof-attempt.zh.md`(主文档持有 Rule / RuleExpr / Head / API 设计权威)
- 主文档 §3 / C1-C21, C45-C48: Rule paradigm
- 主文档 §4 / C23-C35, C49-C51: RuleExpr
- 主文档 §5 / C52-C78: Head + `.eval` namespace
- 主文档 §7 已 stub 化,详细 evidence 设计权威在本文档

**Sibling**:`database-view-fg-layered-architecture.zh.md`(view 4-layer 架构,独立子系统)

**本文档 owner 范围**:
- Phase 2 evidence tree 详细 schema(本文档 §4 [pending])
- Source taxonomy 与色彩(本文档 §5 [pending])
- 三策略 dispatch + orchestrator 设计(本文档 §7 [pending])
- 成功 / 失败树形态(本文档 §8 / §9 [pending])
- §7.12 status 归属(已迁至本文档 §13.2)

---

## 2. 词汇表(本文档锁死)

### 2.1 已 ship 的(沿用 `audit/evidence_graph.py`,本节锁定权威定义来源)

| 词 | 定义 | 来源 |
|---|---|---|
| `EvidenceGraph` | 跨引擎统一 evidence 容器(`graph_id` / `engine` / `root_node_id` / `nodes` / `edges` / `support_kind` / `layout_hint` / `metadata`)| `audit/evidence_graph.py:60` |
| `EvidenceNode` | graph 中节点;3 node_kind | `audit/evidence_graph.py:24` |
| `node_kind` | `NODE_CONCLUSION` / `NODE_PREMISE` / `NODE_SEED` | `audit/evidence_graph.py:11-13` |
| `EvidenceEdge` | graph 中有向边;3 edge_kind | `audit/evidence_graph.py:42` |
| `edge_kind` | `EDGE_SUPPORTS` / `EDGE_DERIVES` / `EDGE_UPDATES` | `audit/evidence_graph.py:15-17` |
| `layout_hint` | `tree` / `timeline` | `audit/evidence_graph.py:8-9` |
| `support_kind` | graph-level 类别(目前 free-form `str`)| `audit/evidence_graph.py:68` |
| `engine_meta` | node / edge 上 `Mapping[str, Any]` 扩展字段 | `audit/evidence_graph.py:34, 51` |

### 2.2 本文档新引入(锁定时间见对应章节)

| 词 | 定义 | 锁定章节 |
|---|---|---|
| `source` | `NODE_SEED.engine_meta.source`(3-enum)| §5 |
| `closed_head` | Phase 2 entry handle = `open_head.where` + literal atoms from `row.bindings` | §3.1 |
| `Explanation` | Phase 2 result DTO(7 字段;沿用主文档 §5.8.3)| §3.1 |
| AtomKindSpec | atom kind 扩展 registry 接口 | §4 [pending] |
| 三策略 dispatch | S1 IR replay / S2 engine probe / S3 library API per engine | §7 [pending] |

### 2.3 与 Rainbird 词汇映射

| Rainbird | 本设计 | 备注 |
|---|---|---|
| `factID` | `row_id`(audit linking)+ `closed_head`(entry handle)| 我们拆为两个语义 |
| `sessionID` | (无 v1 等价 — stateless 设计) | — |
| `source` 6-enum(rule / answer / injection / datasource / knowledgemap / synthesis)| `source` 3-enum(详 §5)| 删 `answer` / `synthesis`(范式差);NAF 不再作为 source |
| `fact.certainty`(1-100)| `raw_kind` + `bound` | 范式不同(详 §6 [pending])|
| `salience`(condition weight)| (v2 deferred,§14)| — |
| `impact`(% contribution)| (v2 deferred,§14)| — |
| `ruleMaxCertainty`(rule cap)| SemanticsProfile `rule_params.cap` | 同位置语义 |
| `rule.bindings` | `bindings`(同名) | — |
| `rule.conditions` | `NODE_PREMISE` × atom 数 | atom-complete 在成功侧 |
| `condition.factID`(递归入口)| `EDGE_SUPPORTS` 链 + `NODE_SEED` `asrt_id` | server-side 一次性返回(非 lazy)|
| `GET /evidence/{factID}/{sessionID}` | `row.explain()` / `result[i].explain()` | API 形态不同(OOP row-bound vs HTTP factID);manual replay 用 `fg.eval.explain(expr, head=closed_head)` |
| `GET /interactions/{sessionID}` | (v2 deferred — session log)| — |
| `POST /nl/explain` | `head.desc` 模板渲染(主文档 C60)| 不走 LLM |
| `x-evidence-key` | (v2 deferred — ACL)| — |
| `expression.wasMet` | (v1 无 — 失败侧不打 violated 标;v1 不提供 atom-level 失败定位)| 见 §9 |

### 2.4 词汇消歧(本文档与主文档共用 / 各自专用)

| 词 | 主文档 owner | 本文档 owner | 备注 |
|---|---|---|---|
| `Rule` / `RuleExpr` / `head` / `closed_head` / `Var` / `Atom` | ✓ | 引用 | 主文档 §3-§5 锁 |
| `EvaluateRow` / `EvaluateResult` / `Explanation` | 字段 schema | 内部 evidence 字段(`evidence: EvidenceGraph \| None`)| 主文档 §5.8.2/§5.8.3 锁 schema;本文档锁 evidence 内部 |
| `EvidenceGraph` / `EvidenceNode` / `EvidenceEdge` | 引用 | ✓ | 已 ship `audit/evidence_graph.py` |
| `source` / `AtomKindSpec` / `engine_meta key namespace` | 引用 | ✓ | 本文档 §4-§5 新引入 |
| `fg.diagnose` / `DiagnoseAtomLocator` | application/protocol/derivation_diagnose.py 已 ship | **v1 SDK 表面不公开**(internal/legacy 保留);C81 修订后 explain 不依赖 diagnose | v2+ 替代设计:§14 D1/D2 |

---

## 3. 架构定义(承接主文档 §5.8 / 原 §7.1-§7.4 re-aligned 内容)

> 本节内容承接 Step 0(2026-05-17)re-align 工作,**完整迁入** 主文档原 §7.1-§7.4。

### 3.1 三阶段(Phase 1 / Transition / Phase 2)+ Diagnose 并行通道

```text
Phase 1: 物化 / 推理 → row 候选 (fast, sparse)
    fg.eval.evaluate(expr, head=open_head, engine, semantics) -> EvaluateResult
    EvaluateResult.rows: tuple[EvaluateRow, ...]
    不在此阶段构造完整 evidence;仅消费 engine 原生的 row witness

Transition: live row → explain request
    row = result[i] / result.first()
    row carries non-serializable resolver back to EvaluateResult context

Phase 2: 单 live row → 按需 evidence (slow, atom-complete success-side)
    row.explain() -> Explanation
    Explanation.evidence: EvidenceGraph | None  (per 主文档 §5.8.3 / C67)
    FactGraph 主导 atom-level evidence 构造,可借引擎库 per-atom probe
    不依赖 engine 的 row+atom 粒度 native trace(参 Nemo --trace 模式;详 §7 / §8 [pending])

Advanced manual replay:
    closed_head = row.close()
    fg.eval.explain(expr, head=closed_head, engine, semantics) -> Explanation

v1 不引入失败定位 API(C81 锁定 2026-05-18):
    explanation.status == "failed" -> explanation.evidence = None
    v1 不提供 atom-level 失败定位;v2+ 设计 top-down goal-regression API
    现存 application-layer fg.diagnose / DiagnoseAtomLocator 保留 internal/legacy,SDK 不公开
    (详 §14 D1/D2 deferred 项)
```

**核心承诺**:
- **完整 evidence 不在 Phase 1 计算** — row 生成时不构造完整证据树,避免无谓开销
- **Phase 2 evidence 由 FactGraph 主导构造** — 不强求 engine 给 row+atom 粒度 native trace;实现可借引擎库 per-atom probe(类 Nemo `--trace` 模式,详 §7 [pending])
- **Phase 2 按需触发** — 用户对 live row 调 `row.explain()`;`row.close()` + `fg.eval.explain(expr, head=closed_head)` 仅是 advanced/manual replay
- **失败态 evidence=None** — `fg.eval.explain` 不在 failed 态承载 lossy 失败信息(C81 锁定 2026-05-18,详 §13.2 / §9)

### 3.2 参考系统验证(materialize-first, explain-on-demand)

这条"materialize first, explain on demand" 模式与商业 KG / inference 产品标准一致:

| 系统 | Phase 2 入口 | 模式 |
|---|---|---|
| **RDFox**(Oxford)| SPARQL `EXPLAIN` extension | backward-chaining proof reconstruction on demand |
| **Ontotext GraphDB** | `Proof.calculateProof(triple)` plugin | derivation tree on demand |
| **Stardog** | `EXPLAIN` query mode / `WHY <triple>` | JSON proof tree on demand |
| **Rainbird** | `GET /analysis/evidence/{factID}/{sessionID}` | client-driven recursive walk |
| **Nemo** | CLI `nmo --trace` | tree / DAG output(JSON 三 layout)|

商业 KG / Datalog 系统**都**采用两阶段模式 — 这条架构有先例支撑,**不是本设计的独创**。

**Verified-mechanism 参照**(继承 Step 0 调研成果,2026-05-17):
- Nemo `--trace` 生产级 atom-level proof tree
- EvonNemo DAG caching 验证 53MB 量级 JSON 可承载
- Bourhis-Lutz-Krötzsch 复杂度理论:我们 AND-only Rule + 浅嵌套 RuleExpr 落在 highly tractable 区
- Rainbird Rule-instance-level granularity 为 v1 设计目标对照(详 §12 [pending])

### 3.3 Rule 对象 Phase 2 introspection 能力(沿用主文档 C16)

| 能力 | API | 用途 |
|---|---|---|
| 遍历 atoms | `rule.atoms` 有序 tuple | Phase 2 interpreter 走每个 atom |
| atom 稳定身份 | `atom.atom_id` 形如 `<rule_id>:atom_<index>`(主文档 C19)| evidence DTO 锚点;跨 rule 不冲突;positional,顺序由构造时决定 |
| 单 atom 求值 | `rule.eval_atom(atom_id, bindings) -> AtomEvalResult` | Phase 2 求值原语(reference 形态)|
| 保留 authoring AST | Rule 构造后不丢字段 | Phase 2 evidence 构造源 |
| desc 渲染 | `rule.render_desc(bindings) -> str` | "the user u-2 is active" |

**实现自由度**:`rule.eval_atom(atom_id, bindings)` 是 reference 形态;Phase 2 实现**不强制**只走此原语 — 也可生成 per-atom probe 程序调引擎(Souffle subprocess / `problog.query()` Python API / Nemo `--trace` 子调用)。三策略 dispatch 详 §7 [pending]。

### 3.4 用户面 evidence 形态示例

```python
# Phase 1
result = fg.eval.evaluate(expr, head=open_head)

# 选行 → 直接解释该 result fact / claim
row = result.first()

# Phase 2 — 按需
explanation = row.explain()

# 渲染(已 ship,audit/evidence_graph.py:118)
from factgraph.audit.evidence_graph import render_evidence_graph_html

if explanation.status == "passed":
    html = render_evidence_graph_html(explanation.evidence)
    # 成功 case:展示 atom-complete derivation tree
    # 例:"因为 u-2 是 User 且 u-2.status = active,且 u-2.region = US,
    #     所以 active_user_in_US 成立"

elif explanation.status == "failed":
    # 业务失败:binding 不成立
    # explanation.evidence = None(per C81 / §9)
    # v1 不提供 atom-level 失败定位 — `fg.diagnose` SDK 表面不公开
    # 失败定位算法(top-down goal-regression / why-not)v2+ deferred(详 §1.2 / §14)
    # 此处用户能拿到的信号:failure_class / checked_scope / suggested_next_steps

elif explanation.status == "unsupported":
    # 引擎技术性不支持(non-business error)
    # explanation.evidence = None
    # explanation.errors 给出 error codes / messages(如 EVIDENCE_LOOKUP_MISS)
    for err in explanation.errors:
        print(err.code, err.message)

elif explanation.status == "invalid_request":
    # 输入格式错(schema-level error)
    # explanation.evidence = None
    # explanation.errors 给出 schema 错误细节(如 UNKNOWN_VARIABLE_IN_BINDING)
    for err in explanation.errors:
        print(err.code, err.message)
```

---

## 4. EvidenceNode / EvidenceEdge schema + engine_meta key namespace

### 4.1 设计立场

- **不扩展 shipped node_kind / edge_kind**(沿用 3+3:`NODE_CONCLUSION` / `NODE_PREMISE` / `NODE_SEED` / `EDGE_SUPPORTS` / `EDGE_DERIVES` / `EDGE_UPDATES`)
- **所有扩展数据走 `engine_meta`**(`Mapping[str, Any]`,free-form per shipped schema;本节锁定 key namespace 约定)
- **顶层字段(`label` / `value_summary` / `component`)有强填充规约**(§4.2)
- **AtomKindSpec registry** 提供 atom kind 扩展点(§4.7),v1 内置 9 IR kinds(详主文档 §10.1)

**理由**:
- shipped `audit/evidence_graph.py` 已稳定;扩展 node_kind 会破坏现有 renderer / 序列化 / cycle 检测
- engine_meta 已是 `MappingProxyType` 不可变 + 任意 jsonable(可放结构化数据)
- 约定 key 优于扩展 schema — 灵活性 + 向后兼容

### 4.2 EvidenceNode 顶层字段填充规约

| node_kind | `label`(用户面 narrative)| `value_summary`(二级描述)| `component`(机器锚点)|
|---|---|---|---|
| `NODE_CONCLUSION` | `rule.desc` 绑定态渲染(per 主文档 C5)`<br>` 例:"user u-2 is active" | quantitative signal(若有):`"p=0.85"`(由 `raw_kind="probabilistic", bound=(0.85,0.85)` 渲染) / `"bound=[0.6,0.8]"` / `""` | `rule_id`(template_id;非 alias) |
| `NODE_PREMISE` | atom 自动 narrative `<br>` 例:`"u-2.status == 'active'"` | `"satisfied"`(v1 失败侧无 evidence,故恒为 satisfied)| `atom_id`(per C19:`<rule_id>:atom_<index>`) |
| `NODE_SEED` | fact 简洁描述 `<br>` 例:`"User(u-2)"` / `"region(u-2, DE)"` | `source` 值 + 标识 `<br>` 例:`"ledger:Asrt#123"` / `"inline:literal"` / `"inferred:Rule_X"` | source-specific:`"ledger:<asrt_id>"` / `"constant:<hash>"` / `"inferred:<rule_id>:<fact_digest>"`(NAF 不进 NODE_SEED,详 §5.2.1 / C121)|

**渲染语义**:
- shipped `render_evidence_graph_html` 已自动消费 `label` / `value_summary` / `component`,无需修改
- atom 自动 narrative 由 `AtomKindSpec.narrative_generator` 生成(§4.7)
- desc 绑定态渲染遵循主文档 §3.7 / C5 `%port_name` 插值规则

### 4.3 NODE_CONCLUSION engine_meta keys

| key | 类型 | 必需 | 含义 |
|---|---|---|---|
| `rule_id` | `str` | ✓ | 该 Rule 的 template id |
| `is_head` | `bool` | ✓ | 是否 root(head's conclusion)= True;intermediate Rule = False |
| **`explained_claim_ref`** | `dict \| None` | ✓ **root only**(is_head=True 时必填)| **Claim reference**(2026-05-19 Wave 1 修订,详 §4.3.1)— primary `Claim` 在主文档 `EvaluateRow.claim`;evidence 节点仅引用(row_id + evidence_ref_id + claim_digest + claim_repr_cache)|
| **`quantitative_explanation`** | `dict \| None` | ✓ **root only**(is_head=True 时必填)| **Quantitative transparency**(Wave 2 #6;详 §4.3.2)— 明示 v1 只承载 engine reported carrier,不提供 decomposition / impact |
| **`alternative_paths`** | `dict \| None` | ✓ **root only**(is_head=True 时必填)| **OR / multi-path visibility**(Wave 2 #9;详 §4.3.3)— 明示 v1 默认 winning-path-only,未展示分支数量可选 |
| `alias` | `str \| None` | ✗ | RuleExpr occurrence alias(仅当 ≠ rule_id 时填,per C28)|
| `bindings` | `dict[str, Any]` | ✓ | 该 Rule firing 的 closed bindings(JSON-friendly)|
| `desc_template` | `str \| None` | ✗ | 原始 `%port_name` 模板,for audit(label 是已渲染版,此处保留模板)|
| `content_digest` | `str` | ✓ | 该 Rule 的 canonical content_digest(per 主文档 C68 / §5.8.5)|
| `version` | `str \| None` | ✗ | rule.version 字段(per 主文档 C4)|
| `path_index` | `int \| None` | ✗ | ProbLog 多 derivation path 时,该 conclusion 所属 path 序号(0-based)|
| `aggregation_rule` | `Literal["noisy_or", "product", "independent_sum"] \| None` | ✗ | 多 path 聚合规则;详 §8 [pending](数学 deferred,§6 仅锁 carrier)|
| **(主文档 §5.8.2 / EvaluateRow 继承,Canonical Quantitative — §6.2 / C110)** | | | |
| `raw_kind` | `Literal["probabilistic", "possibilistic"] \| None` | ✗ | **唯一 canonical** quantitative carrier(C110);ProbLog 点概率 → `"probabilistic"`;deterministic → `None` |
| `bound` | `tuple[float, float] \| None` | ✗ | **唯一 canonical** interval carrier;ProbLog 点概率 `p` → `(p, p)` degenerate;deterministic → `None`;**禁止** `(1.0,1.0)` 表示"逻辑满足"(C111)|
| **(Adapter-native debug — non-contract,§6.5 / C113)** | | | |
| `native_probability` / `problog_raw_probability` / `<engine>_native_*` | `Any \| None` | ✗ | **debug-only**,**non-contract**;canonical 不消费 / 不参与 digest;禁止作 fallback / 主数据源 |

#### 4.3.1 `explained_claim` 引用 `row.claim`(C122 修订 2026-05-19)

> **设计更新**:Claim 一等表示**上提至主文档 §5.8.2 `EvaluateRow.claim`**(Wave 1 重整;详主文档 `Claim` 类定义)。**NODE_CONCLUSION.engine_meta 不再持有 primary `explained_fact`**;改为引用 row 的 claim,避免双写漂移。

**修订后的 NODE_CONCLUSION root field**(替代原 `explained_fact`):

```python
explained_claim_ref: dict = {
    "row_id": str,               # 必填:back-ref 到 EvaluateRow.row_id
    "evidence_ref_id": str,      # 必填:回引 EvaluateRow.evidence_ref.ref_id
    "claim_digest": str,         # 必填:row.claim.digest snapshot(durable copy for self-contained serialization)
    "claim_repr_cache": str,     # 必填:row.claim.repr snapshot(durable rendering hint;avoid lazy re-evaluation)
}
```

**为什么不直接 inline `Claim` dict**:
- Source-of-truth 在 EvaluateRow.claim(Wave 1 设计)
- evidence node 内 inline 会**双写漂移**(若 row.claim 修订,evidence 节点失同步)
- 退化为 reference(`row_id` + `evidence_ref_id` + 必要 cache)实现 self-contained 序列化 + lookup 回 row

**典型例**(`active_us` Rule):
```json
{
    "row_id": "row-1",
    "evidence_ref_id": "ref:abc...",
    "claim_digest": "claim:def...",
    "claim_repr_cache": "active_user_in_US(user='u-2')"
}
```

**渲染层**(`render_evidence_graph_html` 等)直接消费 `claim_repr_cache`,不需要 row 反查;**audit 验证**(跨进程一致性检测)用 `claim_digest` 对比 row.claim.digest。

**Phase C 实现责任**:orchestrator 从 row.evidence_ref + row.claim 派生本字段;不重新计算 claim;**双驻 metadata 来源 = EvaluateRow.claim**(per §8.2.1 metadata source-of-truth invariant)。

#### 4.3.2 root `quantitative_explanation`(C127,Wave 2 #6)

**设计目标**:把 "有无解释强度" 作为 root-level contract 明说,避免用户把 `raw_kind/bound` 误读成 Rainbird-style impact / salience decomposition。

```python
quantitative_explanation: dict = {
    "mode": "engine_reported",              # engine_reported | not_applicable
    "carrier": {
        "raw_kind": "probabilistic" | "possibilistic" | None,
        "bound": tuple[float, float] | None,
    },
    "decomposition": "not_available_v1",    # v1 不提供 per-condition attribution
}
```

**规则**:
- deterministic case:`mode="not_applicable"`, `carrier.raw_kind=None`, `carrier.bound=None`, `decomposition="not_available_v1"`
- ProbLog / PyReason case:`mode="engine_reported"`, carrier 必须等于 root `raw_kind/bound`
- `quantitative_explanation` **不**参与 probability math;它是透明声明层,数学聚合仍 deferred(D6/D7/D15)

#### 4.3.3 root `alternative_paths`(C129,Wave 2 #9)

**设计目标**:v1 仍只渲染成功 / winning path,但 root 必须明示这个边界,避免用户误以为 evidence graph 展示了全部 OR 分支 / 全部失败分支。

```python
alternative_paths: dict = {
    "mode": "winning_path_only",            # v1 唯一必填模式
    "omitted_count": int | None,            # engine 可知时填;未知填 None
}
```

**规则**:
- 单 path deterministic case:`omitted_count=0`
- OR / ProbLog multi-path engine 知道未展示分支数时填具体整数
- engine 不暴露完整候选数时填 `None`,但 `mode` 仍必须存在
- 失败分支 / 未满足 OR branch 的可视化属于 §14 D14 / D18 之后的扩展

### 4.4 NODE_PREMISE engine_meta keys

| key | 类型 | 必需 | 含义 |
|---|---|---|---|
| `atom_id` | `str` | ✓ | `<rule_id>:atom_<index>` 形式(主文档 C19)|
| `atom_kind` | `str` | ✓ | atom kind 字符串(per AtomKindSpec registry,§4.7);v1:`pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in` / `not` / `add` / `sub` / `neg` 等 |
| `atom_index` | `int` | ✓ | atom 在 Rule.atoms 内位置(与 atom_id 后缀一致)|
| `parent_rule_id` | `str` | ✓ | 该 atom 归属 Rule 的 template_id |
| `reason` | `dict` | ✓ | per atom_kind 结构化 reason(详 §4.5)|
| **(主文档 §5.8.2 / EvaluateRow 继承,Canonical Quantitative — §6.2 / C110)** | | | |
| `raw_kind` | `Literal["probabilistic", "possibilistic"] \| None` | ✗ | **唯一 canonical** quantitative carrier(C110);atom-level 传递;deterministic atom → `None` |
| `bound` | `tuple[float, float] \| None` | ✗ | **唯一 canonical** interval carrier;ProbLog atom-level 点概率 `p` → `(p, p)` 若 adapter 提供;deterministic atom → `None`(不写 `(1.0,1.0)`)|
| **(Adapter-native debug — non-contract,§6.5 / C113)** | | | |
| `native_probability` / `<engine>_native_*` | `Any \| None` | ✗ | **debug-only**;canonical 不消费 |

### 4.5 NODE_PREMISE.reason 子结构(per atom_kind + reason kind 4-enum)

> v1 命中 9 IR atom kinds(详主文档 §10.1 / C97)+ ArithExpr / AggregateExpr expression forms(详主文档 §10.6 / C98-C105)+ AtomKindSpec registry 兼容扩展(§4.8)。

#### 4.5.1 reason `kind` 4-enum(C106)

| reason.kind | 触发场景 | 内部 schema 状态 |
|---|---|---|
| `comparison` | atom LHS / RHS 都是 Literal / Var / AttrRef(无 ArithExpr / AggregateExpr)| v1 完整 |
| `arith_comparison` | atom LHS 或 RHS 含 ArithExpr(无 AggregateExpr)| v1 完整 |
| `aggregate_comparison` | atom LHS 或 RHS 含**单一** AggregateExpr(无 ArithExpr 嵌入 AggregateExpr)| v1 完整 |
| `compound_comparison` | 复合(ArithExpr 内嵌 AggregateExpr;双侧均含表达式;多 AggregateExpr 兄弟组合等)| **v1 仅 kind 名预留**,内部 schema **v1.x deferred**(详 §14 D14)|

#### 4.5.2 reason `kind="comparison"` schema(基础 atom)

| atom_kind | reason 字段 | 例 |
|---|---|---|
| `pred` | `{"kind": "comparison", "matched_witness_asrt_id": str, "fact_tuple": tuple, "pred_id": str}` | `{kind: "comparison", matched_witness_asrt_id: "Asrt#123", fact_tuple: ("u-2", "active"), pred_id: "User_status"}` |
| `eq` / `ne` | `{"kind": "comparison", "compared_values": [left, right], "operator": "eq"|"ne"}` | `{kind: "comparison", compared_values: ["active", "active"], operator: "eq"}` |
| `gt` / `ge` / `lt` / `le` | `{"kind": "comparison", "compared_values": [left, right], "operator": ">"|">="|"<"|"<="}` | `{kind: "comparison", compared_values: [25, 20], operator: ">"}` |
| `in` | `{"kind": "comparison", "value": Any, "collection": list}` | `{kind: "comparison", value: "US", collection: ["US", "CA", "DE"]}` |
| `not`(NAF success) | `{"kind": "comparison", "naf": {"negated_atom_repr": str, "search_scope": Literal, "counterexample_count": int}, "negated_inner_kind": str, "negated_inner_reason": None}` | `{kind: "comparison", naf: {negated_atom_repr: "banned(u-2)", search_scope: "projected_view", counterexample_count: 0}, negated_inner_kind: "pred", negated_inner_reason: null}`(NAF success = inner failed = inner reason null)|

#### 4.5.3 reason `kind="arith_comparison"` schema(含 ArithExpr)

```python
{
    "kind": "arith_comparison",
    "lhs_eval": {
        "form": "arith" | "literal" | "var" | "attr",
        "expr": "User(u).age * 0.7 + 5",          # string repr
        "computed": 37.48,                          # 计算值;若错误,值 None
        "operand_values": {"age": 46.4},            # 涉及的 vars / attrs
        "error_kind": None | "division_by_zero",    # C98 div-by-zero 等
        "divisor_value": None | 0,                  # 仅 division_by_zero 时
        "divisor_repr": None | "User(u).count",     # 仅 division_by_zero 时
    },
    "rhs_eval": {同上结构},
    "comparison": {
        "op": "<" | ">" | "==" | "!=" | "<=" | ">=",
        "lhs_value": Any,                           # 若 error 则 None
        "rhs_value": Any,
        "status": "satisfied" | "violated",
        "violated_reason": None | "numeric_compare" | "arithmetic_error",
    },
}
```

**div-by-zero 例**:
```python
{
    "kind": "arith_comparison",
    "lhs_eval": {
        "form": "arith",
        "expr": "User(u).total / User(u).count",
        "computed": None,
        "operand_values": {"total": 5000, "count": 0},
        "error_kind": "division_by_zero",
        "divisor_value": 0,
        "divisor_repr": "User(u).count",
    },
    "rhs_eval": {"form": "literal", "expr": "0.5", "computed": 0.5},
    "comparison": {
        "op": ">",
        "lhs_value": None,
        "rhs_value": 0.5,
        "status": "violated",
        "violated_reason": "arithmetic_error",
    },
}
```

#### 4.5.4 reason `kind="aggregate_comparison"` schema(含单 AggregateExpr,用户提议形态)

> **结构边界声明**(2026-05-19 补 — §8.10 / C136 协同):本节锁 aggregate 的 **reason 数据载体**(单 NODE_PREMISE 内的 explanation envelope);**aggregate 的拓扑形态**(NODE_PREMISE 数量 / 是否展开 contributor sub-NODE_SEED / edge 出入度)在 **§8.10** 独立锁定。
>
> **v1 关键规约**:`aggregate_comparison` reason **是 v1 的唯一解释载体**;`contributors` envelope 内 `count` + 状态 flags **不**等同于 contributor facts 作为 evidence tree nodes;**contributors 个体不是 v1 tree nodes**,除非未来 `mode="embedded"` 落地(v2+ deferred,详 §14 D18)。

```python
{
    "kind": "aggregate_comparison",
    "aggregate": {
        "aggregate_kind": "sum",                    # count / sum / min / max / mean
        "target_repr": "Order(o).amount",
        "filter_repr": ["Order(o).buyer == u-2"],   # filter atoms string list
        "matched_count": 10243,                     # view-projected count (C103)
        "contributors": {                           # C128: v1 count-only envelope
            "mode": "omitted_v1",                   # omitted_v1 | lazy | embedded
            "count": 10243,
            "handle": None,
        },
        "aggregate_result": 1234567.89,             # 或 None if empty_set
        "empty_set": False,                         # C101:min/max/mean 空 set → True + result=None
        "no_value": False,                          # AggregateNoValue 标志(min/max/mean empty 时 True)
        "error_kind": None | "aggregate_target_type_error",  # C102
        "offending_value": None | Any,              # C102:非 numeric target 时
        "offending_value_type": None | "str" | ...,
    },
    "comparison": {
        "op": ">" | "==" | "<" | "!=" | ">=" | "<=",
        "lhs_value": Any,                            # aggregate_result 通常作 LHS
        "rhs": Any,                                  # 比较值
        "status": "satisfied" | "violated",
        "violated_reason": None | "numeric_compare" | "aggregate_no_value" | "aggregate_type_error",
    },
}
```

**Empty set 例**(C101):
```python
{
    "kind": "aggregate_comparison",
    "aggregate": {
        "aggregate_kind": "min",
        "target_repr": "Order(o).amount",
        "filter_repr": ["Order(o).buyer == u_no_orders"],
        "matched_count": 0,
        "contributors": {"mode": "omitted_v1", "count": 0, "handle": None},
        "aggregate_result": None,
        "empty_set": True,
        "no_value": True,
    },
    "comparison": {
        "op": ">",
        "lhs_value": None,
        "rhs": 100,
        "status": "violated",
        "violated_reason": "aggregate_no_value",
    },
}
```

**Target type 错例**(C102):
```python
{
    "kind": "aggregate_comparison",
    "aggregate": {
        "aggregate_kind": "sum",
        "target_repr": "Order(o).status",         # 用户错把 string field 用于 sum
        "filter_repr": ["Order(o).buyer == u-2"],
        "matched_count": 3,
        "contributors": {"mode": "omitted_v1", "count": 3, "handle": None},
        "aggregate_result": None,
        "empty_set": False,
        "no_value": False,
        "error_kind": "aggregate_target_type_error",
        "offending_value": "active",
        "offending_value_type": "str",
    },
    "comparison": {
        "op": ">",
        "lhs_value": None,
        "rhs": 1000,
        "status": "violated",
        "violated_reason": "aggregate_type_error",
    },
}
```

**contributors envelope(C128)**:
- `mode="omitted_v1"`:v1 默认形态,只保证 `count == matched_count`,不返回 matched facts
- `mode="lazy"`:预留 lazy fetch;`handle` 必填且可用于后续 fetch contributors
- `mode="embedded"`:预留小集合内嵌;v1 不要求实现
- `contributors.count` 必须等于 `matched_count`;不再使用 lossy boolean contributor flag

#### 4.5.5 reason `kind="compound_comparison"`(v1 schema 预留)

> **v1 状态**:`compound_comparison` reason kind 名预留,**内部 schema v1.x deferred**(详 §14 D14)。

触发场景:
- `agg_sum(...) / agg_count(...) > 100`(ArithExpr 含两个 AggregateExpr siblings)
- `agg_sum(Order.amount * 0.7) > User.threshold + 50`(双侧均含表达式)
- 多层嵌套(ArithExpr ⊃ ArithExpr ⊃ AggregateExpr 等)

**v1 fallback 行为**:
- evaluator 正常计算;`compound_comparison` kind 标记
- 内部字段 v1 写为 lossy 形态:`{"kind": "compound_comparison", "lhs_repr": "...", "rhs_repr": "...", "lhs_value": ..., "rhs_value": ..., "status": ..., "_v1_lossy": True}`
- v1.x trigger:用户复合表达式场景成熟 + 用户面调试需求

#### 4.5.6 v1 reason 表达范围(C81 协同)

- v1 失败侧无 NODE_PREMISE(per C81;evidence 仅在 status=passed 时存在)
- 因此 v1 reason **永远表达"为何 satisfied"**,不表达 "为何 violated"
- **例外**:atom 单点 satisfied 但内部含 atom-level error(div-by-zero / aggregate type error)→ reason 含 `error_kind`(C98 / C102),但**整个 evidence tree 仍是 passed**(因为整个 Rule 在排除 error env 后仍有 satisfying envs)。**Phase C 实现注意**:error env 不进 evidence tree,只有 valid env 的 evidence 进树
- v2+ 失败侧设计(D1/D2)需独立 reason 子结构(top-down goal-regression 产物,与 v1 reason 形态不同)

#### 4.5.7 §4.5 设计承诺 Commitments(C106)

| # | 承诺 |
|---|---|
| C106 | **NODE_PREMISE.reason `kind` 4-enum**:`comparison`(基础)/ `arith_comparison`(含 ArithExpr)/ `aggregate_comparison`(含单 AggregateExpr)/ `compound_comparison`(复合,v1 仅 kind 名预留 + 内部 schema v1.x deferred 详 §14 D14);`aggregate_comparison` shape 锁定(`aggregate.matched_count` + `contributors` envelope(C128) + `empty_set: bool` + `no_value: bool` + `error_kind` 可选);`arith_comparison` 含 div-by-zero 时 `error_kind="division_by_zero"` + `divisor_value` + `divisor_repr`(C98 协同);aggregate target type 错时 `error_kind="aggregate_target_type_error"` + `offending_value` + `offending_value_type`(C102 协同);v1 反馈 only success-side(C81 协同,Phase C 实现注意 error env 不进树)|

### 4.6 NODE_SEED engine_meta keys

| key | 类型 | 必需 | 含义 |
|---|---|---|---|
| `source` | `Literal["ledger_assertion", "inline_constant", "inferred_intermediate"]` | ✓ | 3-enum source taxonomy(详 §5)|
| `asrt_id` | `str \| None` | ✗ | Ledger assertion id(仅 source=ledger_assertion)|
| `pred_id` | `str \| None` | ✗ | predicate id(仅 source=ledger_assertion)|
| `fact_tuple` | `tuple \| None` | ✗ | 匹配的具体 fact 元组 |
| `assertion_origin` | `Literal["import", "manual_write", "external_datasource", "system_injection", "user_input"] \| None` | ✗ | ledger assertion origin 子分类(C126;仅 source=ledger_assertion;未知时 None)|
| `source_ref` | `str \| None` | ✗ | 上游来源引用(C126;如 import batch id / external URI / session answer id;未知时 None)|
| `literal_value` | `Any \| None` | ✗ | inline literal 值(仅 source=inline_constant)|
| `derived_from_rule_id` | `str \| None` | ✗ | 中间结论的上游 Rule id(仅 source=inferred_intermediate)|
| **(deferred,§14 D8)** | | | |
| `version` | `str \| None` | ✗ | ledger 版本(audit 用,v2+ trigger)|

### 4.7 EvidenceEdge engine_meta keys(扩展 shipped `rule_label`)

| key | 类型 | 必需 | 含义 |
|---|---|---|---|
| (shipped) `rule_label` | `str \| None` | ✗ | 已 ship `audit/evidence_graph.py:50` |
| `rule_id` | `str \| None` | ✗ | 跨边 traceability(指向 owning Rule)|
| `path_index` | `int \| None` | ✗ | ProbLog 多 path 时标记该边所属 path |

**典型 edge_kind 使用**:
- L1 NODE_CONCLUSION ← L2 NODE_CONCLUSION:`EDGE_SUPPORTS`,`rule_label` = parent Rule template_id
- L2 NODE_CONCLUSION ← L3 NODE_PREMISE:`EDGE_SUPPORTS`,`rule_label` = owning Rule template_id  
- L3 NODE_PREMISE ← L4 NODE_SEED:`EDGE_SUPPORTS`,`rule_label` = None
- `EDGE_DERIVES`:v1 暂不使用(PyReason Form 2 预留)
- `EDGE_UPDATES`:v1 暂不使用(temporal 时间步预留)

### 4.8 AtomKindSpec registry 接口

```python
# kernel/application/evidence_runtime/atom_kinds.py(v1 实现位置)

@dataclass(frozen=True)
class AtomKindSpec:
    """v1 atom kind 扩展点。"""
    
    kind: str                                # 例 "pred", "gt", "in"
    description: str                         # 人可读说明
    ir_arity: int                            # IR tuple 长度(含 kind 头)
    
    narrative_generator: Callable[
        [tuple, dict[str, Any]],             # (atom_tuple, bindings)
        str,                                 # narrative 字符串
    ]
    
    reason_extractor: Callable[
        [tuple, dict[str, Any], dict],       # (atom_tuple, bindings, view_facts)
        dict[str, Any],                      # reason dict
    ]
    
    supported_engines: frozenset[str]        # {"souffle", "problog", "native"} 子集
```

**registry 操作**:
```python
_REGISTRY: dict[str, AtomKindSpec] = {}

def register_atom_kind(spec: AtomKindSpec) -> None: ...
def get_atom_kind(kind: str) -> AtomKindSpec: ...
def list_atom_kinds() -> tuple[str, ...]: ...
```

**v1 公开范围**:
- v1 SDK 表面 **不公开** registry(internal `kernel.application` 层)
- 用户**不可**自定义 atom kind v1;v1.x 触发条件 = 用户出现明确"自定义谓词 / functor"需求
- v1 内置 9 IR kinds(详主文档 §10.1)+ ArithExpr / AggregateExpr expression forms(详主文档 §10.6)

### 4.8.5 内置 AtomKindSpec Responsibility Table(D-2 lite)

> 9 个 v1 IR atom kinds + 2 个 expression forms 各自的 reason 责任范围;**Phase C 实现伪代码不在此锁定**(避免 implementation spec drift),仅列 responsibility scope。

| atom_kind / form | reason 责任 scope |
|---|---|
| `pred` | witness lookup + matched fact tuple + asrt_id(来自 engine adapter native witness) |
| `eq` / `ne` | resolved lhs / rhs values + operator |
| `gt` / `ge` / `lt` / `le` | numeric comparison values + operator |
| `in` | tested value + allowed set summary(集合 > 10 显示 first 10 + total count) |
| `not` | satisfied case:no counterexample found(NAF 成功;无 inner reason)|
| **ArithExpr(在 comparison)** | `evaluation_trace` 数组(per ArithExpr sub-op)+ arithmetic `error_kind`(div-by-zero etc.,C98 协同)|
| **AggregateExpr(在 comparison)** | `matched_count` + `aggregate_result` + `contributors {mode,count,handle}` envelope + `empty_set` / `no_value` / `error_kind` flags(C101 / C102 / C106 / C128 协同)|

**narrative 责任**(verily lite):
- 默认每 atom_kind 用 string repr 渲染 atom narrative(e.g., `"u.status == 'active'"` for eq)
- Rule.desc(C4)在 NODE_CONCLUSION 渲染(主文档 §3.7 / C5);atom-level 默认无 user-defined desc(v1)

**实现自由度**(v1 锁定):
- 具体 `narrative_generator` / `reason_extractor` 函数实现 **Phase C 落地**,不在本节文档锁
- 测试基线:每个 atom kind 至少 1 个 satisfied case + 1 个 violated case(后者验证 evaluator 行为,但 v1 evidence 仅 satisfied 进树)

### 4.9 v1 atom kinds 名单(已迁出至主文档)

> **迁移 note**(2026-05-18):v1 IR 9 atom kinds canonical 名单 + adapter 实现状态 已**迁出**至主文档 `rule-expression-and-proof-attempt.zh.md` **§10 Atom Language 闭合**(C97)+ **§8 引擎能力对照与 lower 策略**(C96 adapter gaps)。
>
> **本节仅持有 evidence-specific 接口**:
> - AtomKindSpec registry **interface 类定义** → §4.8
> - per atom_kind 的 **evidence 字段格式**(narrative + reason 结构)→ §4.5 NODE_PREMISE.reason
>
> **跨文档引用**:
> - "v1 有哪些 atom kinds?" → 主文档 §10.1
> - "Souffle / ProbLog adapter 支持哪些?" → 主文档 §8.3
> - "arith / 字符串 / 时间 / 聚合 deferred?" → 主文档 §10.2
>
> **原 C90 内容**(本节 atom kinds list)已迁出主文档 §10 / C97;evidence doc 不再持有 C90,§13.3 commitments 表已同步去除。

### 4.10 §4 设计承诺 Commitments(C82-C89,evidence-specific)

> **Phase B-1 迁移 note**(2026-05-18):原 C90(v1 atom kinds 名单)已迁出至主文档 §10 / C97。本节仅持有 evidence-specific 8 commitments(C82-C89)+ §4.11.4 持有 C91。

| # | 承诺 |
|---|---|
| C82 | **不扩展** shipped `audit/evidence_graph.py` 3 node_kind + 3 edge_kind;所有扩展走 `engine_meta` key namespace(本节 §4.3-§4.7 锁定)|
| C83 | EvidenceNode 顶层字段填充规约:`label` = 用户面 narrative(L2/L3 自动渲染);`value_summary` = 二级描述(确定性 / satisfaction);`component` = 机器锚点(rule_id / atom_id / source-specific)— §4.2 锁定 |
| C84 | `NODE_CONCLUSION.engine_meta` keys:`rule_id` / `is_head` / `bindings` / `content_digest`(必需)+ `alias` / `desc_template` / `version` + `raw_kind` / `bound` canonical quantitative carrier + ProbLog `path_index` / `aggregation_rule`(详 §4.3)|
| C85 | `NODE_PREMISE.engine_meta` keys:`atom_id` / `atom_kind` / `atom_index` / `parent_rule_id` / `reason`(必需)+ `raw_kind` / `bound` canonical quantitative carrier(详 §4.4);不引入独立 `probability` 字段 |
| C86 | `NODE_PREMISE.reason` 子结构 per atom_kind 锁定(v1 IR 9 kinds:pred / eq / ne / gt / ge / lt / le / in / not — 名单详主文档 §10.1 / C97);v1 reason **永远表达"为何 satisfied"**,失败侧无 reason(C81 + §4.5)|
| C87 | `NODE_SEED.engine_meta` keys:`source` 必需(3-enum,详 §5)+ source-specific 可选字段(asrt_id / pred_id / fact_tuple / assertion_origin / source_ref / literal_value / derived_from_rule_id);ledger 版本字段 `version` 是 §14 D8 deferred(详 §4.6)|
| C88 | `EvidenceEdge.engine_meta` 扩展 shipped `rule_label`,加 `rule_id` + ProbLog `path_index`;v1 仅用 `EDGE_SUPPORTS`,`EDGE_DERIVES` / `EDGE_UPDATES` 预留 PyReason Form 2(详 §4.7)|
| C89 | `AtomKindSpec` registry 是 v1 atom kind 扩展点,**internal `kernel.application` 层**;v1 SDK 表面**不公开**;用户自定义 atom kind 是 v1.x deferred(详 §4.8)|

> **C90 → 主文档 §10 / C97**(v1 IR canonical atom kinds = 9 个,详主文档)

### 4.11 Engine Portability:Grammar 对照表 + Evidence Tree 类型决策

#### 4.11.1 Per-engine Evidence Tree 类型决策(NOT 分类)

**决策**:**不**给每引擎独立 EvidenceTree 类。沿用 shipped `EvidenceGraph`(3 node_kind + 3 edge_kind)+ per-engine `engine_meta` + `layout_hint` 分流。

**理由**(grounded shipped 已 ship 转换器):

| 引擎 | shipped 转换器位置 | layout |
|---|---|---|
| Souffle | `adapters/souffle/provenance.py:123` `souffle_proof_tree_to_evidence_graph()` | `LAYOUT_TREE` |
| ProbLog | `adapters/problog/provenance.py:283` `problog_trace_to_evidence_graph()` | `LAYOUT_TREE` |
| PyReason | `adapters/pyreason/provenance.py:229` `pyreason_trace_to_evidence_graph()` | **`LAYOUT_TIMELINE`** |

**架构层次**:
- schema:同一 EvidenceGraph(3+3,不分引擎)
- engine_meta:per-engine 自定义 keys(已 §4.3-§4.7 锁定)
- layout:`LAYOUT_TREE`(Souffle / ProbLog)/ `LAYOUT_TIMELINE`(PyReason)
- converter:per-engine 函数(shipped 3 个,Phase C 直接复用)

PyReason 的"时序结构非常不一样" 是**布局差异**,不是**类型差异** — `LAYOUT_TIMELINE` + node `timestamp` 字段(shipped `audit/evidence_graph.py:33`)已支撑。

#### 4.11.2 Grammar 原生支持对照表(已迁出至主文档 §8.2)

> **迁移 note**(2026-05-18):Grammar 原生支持对照表已**迁出**至主文档 `rule-expression-and-proof-attempt.zh.md` **§8.2 Grammar 原生支持对照表**(C94)。
>
> **跨文档引用**:"我这条 Rule 能跑在哪些引擎?" → 主文档 §8.2 + §8.3 adapter 状态。
>
> **原 C92 内容**已迁出主文档 §8 / C94;evidence doc 不再持有 C92。

#### 4.11.3 Negation 语义差异(已迁出至主文档 §8.4)

> **迁移 note**(2026-05-18):Negation 跨引擎语义差异 + lowering matrix 已**迁出**至主文档 `rule-expression-and-proof-attempt.zh.md` **§8.4 Negation 语义差异 + lowering matrix**(C95)。
>
> **关键概要**:v1 IR `not` 在 Form 1(Souffle `!atom` / ProbLog `\+atom`)内 2-valued NAF over derivation 语义等价;PyReason `~atom` interval-valued + closed_world 与 Form 1 本质不同,不进 v1 IR(详主文档 §8.4)。
>
> **原 C93 内容**已迁出主文档 §8 / C95;evidence doc 不再持有 C93。

#### 4.11.4 §4.11 设计承诺(C91)

| # | 承诺 |
|---|---|
| C91 | **不**给每引擎独立 EvidenceGraph 类;沿用 shipped(`audit/evidence_graph.py:60`)+ `layout_hint` 区分时序 / 树 + per-engine `engine_meta` keys + shipped 3 个 per-engine converters(`adapters/{souffle,problog,pyreason}/provenance.py`)|

> **C92 / C93 迁移 note**:原 C92(grammar 对照表)/ C93(negation 符号 + lowering)已迁出至主文档 §8(C94 / C95);本节仅持有 evidence-specific 的 C91(per-engine evidence tree 类型决策)。

### 4.12 Field Source Crosswalk(D-1 light)

> 主文档 §5.8.2 / §5.8.5 已锁 EvaluateRow / EvaluateResult 字段来源 + digest 规则;evidence doc §4.3-§4.7 已锁 engine_meta key 集合。**本节仅消除剩余 stitching / source 歧义**,不重复主文档已锁内容。

#### 4.12.1 模糊点排查(只列剩余歧义,不列已锁字段)

| 模糊字段 | v1 锁定 source | 理由 |
|---|---|---|
| `NODE_CONCLUSION.engine_meta.bindings` | **从 `EvaluateRow.bindings` 注入 closed_head(通过 `row.explain()` 内部 closure 或 advanced `row.close()`)**;**非** explain runtime 重新评估 | C64 / C66 已锁 row live resolver 行为;evidence runtime 仅消费,不重算 |
| `NODE_PREMISE.engine_meta.reason.matched_witness_asrt_id`(`pred` only)| **engine adapter native witness 优先**(Souffle:`_ParsedWitnessRow.witness_atoms`,`adapters/souffle/engine_eval.py:37`);**fallback ledger 反查**(`find_claims(pred_id, fact_tuple)`)若 adapter 无 witness | 优先用 engine 给的(zero-cost);仅 ProbLog / 失败 case fallback |
| `NODE_CONCLUSION.engine_meta.raw_kind/bound`(ProbLog)| engine adapter 点概率来源(`candidate.confidence` 等)规范化为 `raw_kind="probabilistic", bound=(p,p)` | ProbLog 不再暴露独立 `probability` 字段;Souffle deterministic 时不填 |
| `NODE_CONCLUSION.engine_meta.path_index` / `aggregation_rule`(ProbLog multi-path)| engine adapter computed(详 §6 [pending] aggregation rule + §8 [pending] 多 path tree)| v1 单 path 默认 path_index=0;multi-path 见 §8 |
| `NODE_PREMISE.engine_meta.raw_kind/bound`(ProbLog atom-level)| ProbLog adapter 若提供 atom-level 点概率则规范化为 `raw_kind="probabilistic", bound=(p,p)`;未提供则不填 | deterministic atom **不**写 `(1.0,1.0)`;避免把逻辑满足误写成概率 certainty |

#### 4.12.2 核心 stitching invariants(v1 锁定)

| invariant | 描述 |
|---|---|
| **Bindings 数据来源 = `EvaluateRow.bindings`** | Phase 1 → Phase 2 唯一桥;evidence runtime **不重新评估 binding**,仅消费 closed_head 注入 |
| **Fact witness 来源 = engine adapter native witness** | Souffle 现有(line 37 / 366);ProbLog adapter 工作(Phase C ~50 行 fallback ledger 反查)|
| **Atom-level reason = `AtomKindSpec.reason_extractor`** | per atom kind 各自函数;输入 `(atom, bindings, view_facts)`;详 §4.8.5 responsibility table |
| **Quantitative 字段统一 `raw_kind/bound`** | ProbLog 点概率、ProbLog 区间投影、PyReason bound 都走同一 carrier;Souffle / native deterministic 不填(详 §6 [pending])|

#### 4.12.3 NODE_SEED engine_meta source

详 §5 source taxonomy 3-enum 锁定后填(`ledger_assertion` / `inline_constant` / `inferred_intermediate`)。NAF 不再产生 NODE_SEED,在 NODE_PREMISE.reason.naf 表达。

### 4.13 End-to-End Worked Examples(D-3)

> 2 个 walkthrough 验证 design 闭合:**Souffle/native S1 replay** + **ProbLog enrichment**。

#### 4.13.1 Example 1:Souffle/native(S1 replay)Datalog 直通

**用户面**:
```python
with vars("u") as (u,):
    active_us = Rule(
        id="active_us",
        desc="user %user is active in US",
        where=[
            User(u).status == "active",
            User(u).region == "US",
        ],
        ports={"user": u},
    )

# Phase 1
result = fg.eval.evaluate(active_us, head=Rule.projection("user"), engine="souffle")
# result.rows = [EvaluateRow(
#     bindings={"user": "u-2"}, raw_kind=None, bound=None, 
#     row_id="run-1:abc123"
# )]

# Phase 2
row = result.first()
explanation = row.explain()
# explanation.status = "passed"
# explanation.evidence = EvidenceGraph(...) per below
```

**evidence 树形态**:
```
NODE_CONCLUSION  "active_us:closed:run-1:abc123"  [root, is_head=True]
  label: "user u-2 is active in US"
  value_summary: ""                        # deterministic (no probability)
  component: "active_us"
  engine_meta:
    rule_id="active_us"
    is_head=True
    bindings={"user": "u-2"}              # 源自 EvaluateRow.bindings
    content_digest="<hash>"
    engine="souffle"
│
├─ EDGE_SUPPORTS ← NODE_PREMISE  "active_us:atom_0"
│    label: "u-2.status == 'active'"
│    value_summary: "satisfied"
│    component: "active_us:atom_0"
│    engine_meta:
│      atom_id="active_us:atom_0"
│      atom_kind="eq"
│      atom_index=0
│      parent_rule_id="active_us"
│      reason:
│        kind="comparison"
│        compared_values=["active", "active"]
│        operator="eq"
│   │
│   └─ EDGE_SUPPORTS ← NODE_SEED  "ledger:Asrt#42"
│        label: "User(u-2).status = active"
│        value_summary: "ledger:Asrt#42"
│        component: "ledger:Asrt#42"
│        engine_meta:
│          source="ledger_assertion"   # 详 §5 pending
│          asrt_id="Asrt#42"
│          pred_id="user_status"
│          fact_tuple=("u-2", "active")
│
└─ EDGE_SUPPORTS ← NODE_PREMISE  "active_us:atom_1"
     label: "u-2.region == 'US'"
     ... (similar shape to atom_0)
     └─ EDGE_SUPPORTS ← NODE_SEED "ledger:Asrt#84"
          ...
```

**Phase 2 orchestrator 关键流程**(指导 Phase C 实现):

```text
1. Phase 1 (Souffle native):
   - evaluate_store_engine() 跑 Souffle
   - 输出: rows = [(bindings, witness_atoms)] 
     witness_atoms = [(user_status, Asrt#42), (user_region, Asrt#84)]
     (来自 _ParsedWitnessRow at line 37, parsed at line 366)

2. Transition:
   - row.explain() 通过 row._result_resolver 回到 EvaluateResult context
   - orchestrator 内部把 "u-2" 字面化进 closed_head.where

3. Phase 2 orchestrator (新写, Phase C):
   - 构造 root NODE_CONCLUSION:
       engine_meta.bindings ← EvaluateRow.bindings  
       engine_meta.content_digest ← closed_head.content_digest
       label ← Rule.desc 渲染 with bindings
   
   - For each atom in closed_head.where:
       AtomKindSpec.reason_extractor(atom, bindings, view_facts) → reason dict
       构造 NODE_PREMISE with atom_id / atom_kind / reason
       
   - For each `pred` atom:
       从 witness_atoms 找 matching asrt_id
       构造 NODE_SEED with source="ledger_assertion" / asrt_id

   - 织 EDGE_SUPPORTS:root ← premise[0..n];premise ← seed (per pred)

4. Output: Explanation(status="passed", evidence=EvidenceGraph(...))
```

**Failed case 示意**:
- 若 row 不满足(例:Souffle 找不到 region(u-2, "US"))→ Phase 1 不产 row → Phase 2 不触发
- 若用户手工构造 closed_head 但 atom 不满足 → explain status="failed" + evidence=None(per C81)
- 失败定位走 diagnose(v1 SDK 不公开)

#### 4.13.2 Example 2:ProbLog enrichment

**用户面**(同 Rule,加 ProbLog semantics):
```python
result = fg.eval.evaluate(
    active_us,
    head=Rule.projection("user"),
    engine="problog",
    semantics=ProbLogSemantics(rule_params={"active_us": ProbLogRuleParams(derived_bound=(0.7, 0.7))}),
)
explanation = result.first().explain()
# explanation.evidence: EvidenceGraph 与 Example 1 同构,但 engine_meta 加 canonical raw_kind/bound 字段
```

**evidence 树差异(vs Example 1)**:
```
NODE_CONCLUSION  "active_us:closed:run-2:def456"  [root]
  label: "user u-2 is active in US"
  value_summary: "p=0.7"                  # raw_kind="probabilistic", bound=(0.7,0.7) 的显示 shorthand
  engine_meta:
    rule_id="active_us"
    is_head=True
    bindings={"user": "u-2"}
    engine="problog"                       # ← 不是 "souffle"
    raw_kind="probabilistic"               # ← canonical quantitative carrier
    bound=(0.7, 0.7)                       # ← ProbLog 点概率 p 规范化为 [p,p]
    path_index=0                           # ← v1 默认单 path
    aggregation_rule=None                  # ← 单 path, no aggregation
│
├─ EDGE_SUPPORTS ← NODE_PREMISE "active_us:atom_0"  (与 Example 1 同构)
│    engine_meta:
│      ... (atom_id / atom_kind / reason 同 Example 1)
│      raw_kind=None                       # ← deterministic atom 不写 (1.0,1.0)
│      bound=None
│
└─ EDGE_SUPPORTS ← NODE_PREMISE "active_us:atom_1"  (与 Example 1 同构)
     ...
```

**核心差异 vs Souffle case**:

| 维度 | Souffle | ProbLog |
|---|---|---|
| Root quantitative 字段 | 不填 | `raw_kind="probabilistic", bound=(0.7,0.7)`(rule_params / adapter 规范化)|
| Root value_summary | `""` | `"p=0.7"` |
| Atom-level quantitative | 不填 | deterministic atom 不填;若 adapter 提供点概率则同样写 `raw_kind="probabilistic", bound=(p,p)` |
| Witness source | engine native `witness_atoms` | engine candidate score 规范化为 `raw_kind/bound` + fallback ledger 反查(adapter Phase C 工作)|

**"ProbLog enrichment, not core" 含义**:
- v1 explain **核心流程 = atom-by-atom evaluation**(S1 replay 同 Souffle / native)
- ProbLog adapter trace / SDD 是 **enrichment 字段**(注入 engine_meta `raw_kind/bound` / `path_index`),**不是 v1 explain 主路径**
- 不强求 ProbLog adapter 输出完整 SDD(Sentential Decision Diagram)
- 多 derivation path case 详 §8 [pending];v1 单 path 是默认
- v2+ 若 ProbLog 用户需 SDD 完整 dump,加独立 schema 扩展(详 §14 D14)

#### 4.13.3 关键 design invariants(2 例验证)

1. **EvidenceGraph schema 同构**(Souffle / ProbLog)— 仅 engine_meta 字段差异;NODE_CONCLUSION / NODE_PREMISE / NODE_SEED 三 kinds + EDGE_SUPPORTS 织法一致
2. **Bindings 来源唯一**(从 EvaluateRow,非重算)— C-stitching invariant 1
3. **Atom-level evaluation 走 AtomKindSpec.reason_extractor** — engine 透明(同函数,view_facts 跨 engine 一致 snapshot per C103)
4. **`raw_kind / bound` 是唯一 canonical quantitative enrichment**,非核心 evidence 结构 — ProbLog 点概率是 `(p,p)` 的 degenerate interval,Form 1 与 Form 2 区别集中在此

---

## 5. Source Taxonomy(3-enum)

> **本节状态**:Phase B-2 落定 2026-05-18,Wave 1/Wave 2 于 2026-05-19 修订。NODE_SEED engine_meta.source 字段(C87/C107)3-enum 严格锁定 + 与 Rainbird 6-enum 映射 + Color coding + ledger provenance(C126)规约。

### 5.1 立场:严格 3-enum + 比 Rainbird 严谨

- v1 NODE_SEED **必填** `source` 字段(per C87)
- 3-enum **strict validation**(2026-05-19 修订:NAF 退出 source layer,详 §5.2.1);运行期 `source` 不在 3 值之一 → `EvidenceValidationError`(构造期 raise)
- 设计原则:**比 Rainbird 严谨** — Rainbird 6-enum 但 SDK 中是 free-form string(`evidence.go:20, 75`,无 enum 约束),我们用 strict Literal
- 扩展触发:超出 3-enum 的 source 类型 → v1.x deferred(详 §5.6)

### 5.2 v1 3-enum 详细定义(2026-05-19 修订)

| source | 含义 | 出现场景 | 配套 engine_meta 字段(C87)|
|---|---|---|---|
| **`ledger_assertion`** | 来自本地 Ledger 的 asrt_id 事实 | Souffle / native / ProbLog pred atom 匹配 Ledger 事实(**最常见,~95% case**)| `asrt_id` (str, 必填)<br>`pred_id` (str)<br>`fact_tuple` (tuple)<br>**`assertion_origin`** (Literal \| None, 可选,C126)<br>**`source_ref`** (str \| None, 可选,C126)|
| **`inferred_intermediate`** | RuleExpr 链上游 Rule 的中间结论(非 Ledger 事实)| 当 pred atom 匹配的是上游 Rule 推出的派生 fact,而非 base assertion | `derived_from_rule_id` (str, 必填,上游 Rule.id)<br>`derived_fact_repr` (str)<br>`upstream_evidence_graph_id` (str, 可选,跨 evidence 链接)|
| **`inline_constant`** | closed_head 或 Rule 内 literal binding 注入的常量 | 当 Rule 有显式 `Var("x") == "abc"` 字面值且需展示为独立 NODE_SEED(罕见,~5% case) | `literal_value` (Any, 必填)<br>`binding_var` (str, 可选,绑定的 Var 名)|

#### 5.2.1 NAF 从 source 退出 → 入 NODE_PREMISE.reason(2026-05-19 锁定)

**修订理由**(产品视角):NAF(`not(p)` 满足)**不是 fact source**,是**闭世界 / 作用域下的证明状态**。把 absence 建成 `NODE_SEED` 用户会读成"有一条负事实",误导。

**新表达**(详 §4.5.2 `not` atom_kind reason):
```python
NODE_PREMISE (atom_kind="not", satisfied case)
  engine_meta.reason = {
      "kind": "comparison",
      "naf": {
          "negated_atom_repr": "banned(u-2)",
          "search_scope": "projected_view" | "rule_expr_scope" | ...,
          "counterexample_count": 0,
      },
      "negated_inner_kind": "pred",
      "negated_inner_reason": None,    # NAF success = inner failed = 无 reason
  }
```

NAF 案例**无 NODE_SEED**(absence 不需要 seed);NAF 表述完全在 premise.reason 内。

**search_scope 锁定语义**(critical):
- 含义:**当前 projected view + 当前 RuleExpr evaluation scope 内** 未找到 counterexample
- **不含义**:一阶逻辑全域证明 / 跨 view / 跨 expr 的存在性证明
- Phase C orchestrator 实现必须显式传 scope

**Rainbird 映射变更**(详 §5.3):`synthesis` → **v1 不映射**(v1.x 若实现广义 synthesis 再映射)。

#### 5.2.2 `ledger_assertion.assertion_origin` + `source_ref`(C126,Wave 2 #4)

**设计目标**:把 Rainbird 的 coarse `knowledgemap` source 细分到 audit 可用的 assertion origin,但不要求 Ledger v1 已经完整保存所有上游 metadata。

```python
ledger_assertion engine_meta = {
    "source": "ledger_assertion",
    "asrt_id": "Asrt#42",
    "pred_id": "user_status",
    "fact_tuple": ("u-2", "active"),
    "assertion_origin": "import" | "manual_write" | "external_datasource" | "system_injection" | "user_input" | None,
    "source_ref": str | None,
}
```

**origin enum**:
- `import`:批量导入 / 文件导入产生的 assertion
- `manual_write`:开发者或 operator 直接写入 Ledger
- `external_datasource`:外部数据源同步
- `system_injection`:系统内部注入,非用户回答
- `user_input`:用户交互回答 / 表单输入
- `None`:Ledger 当前没有 origin metadata;v1 允许留空,但字段位置锁定

**source_ref 规则**:
- 可指向 import batch id、外部 URI、datasource row id、session answer id 等
- v1 只要求 JSON string or None;不规定 URI scheme
- `assertion_origin is None` 时 `source_ref` 通常也为 None;若历史数据只有 ref 没有 origin,允许保留 `source_ref`

#### 5.2.3 `inline_constant` NODE_SEED 建议(避免碎片化)

**Phase C 实现建议**(非 schema 锁定):
- **不**对每个 literal 强制建 NODE_SEED
- 仅当 literal 对 **root / head closure 或关键 binding** 有解释价值时建 seed
- 否则 evidence 树会因每个 `Var("x") == "literal"` 都额外加节点而碎片化
- 决策权在 Phase C orchestrator;v1 设计文档不强制 always-on
- 触发器示例:`closed_head` 内 port binding 字面值(用户视角的"输入 fact")可建 seed;Rule 内部辅助常量(中间计算值)不建

**互斥规则**:
- 每个 NODE_SEED 的 `source` **必且仅 1 个值**(不允许 multi-source)
- per-source 必填字段缺失 → 构造期 `EvidenceValidationError`
- per-source 不允许字段填入 → 构造期 warning(不 raise,但 schema 检查会标记)

### 5.3 与 Rainbird 6-enum 映射

Rainbird 6 sources:`rule` / `knowledgemap` / `answer` / `injection` / `datasource` / `synthesis`

| Rainbird source | 本设计 v1 3-enum 映射 | 处理理由 |
|---|---|---|
| `knowledgemap`(已知 KG 事实) | → **`ledger_assertion`** | 概念等价(本地持久化的"已知事实")|
| `rule`(rule-derived fact) | → **`inferred_intermediate`** | 概念等价(中间推导事实)|
| `synthesis`(optional condition 桥接) | → **v1 不映射**(2026-05-19 修订)| NAF 已退出 source layer 入 NODE_PREMISE.reason(§5.2.1);广义 synthesis(optional condition)v1.x deferred(详 §14 D15)|
| `injection`(外部注入) | → **(v1 无对应,v1.x deferred)** | v1 无 `fg.inject` API;若 v1.x 加入,enum 增 `external_injection` |
| `answer`(用户问答响应) | → **(v1 无对应,v2+ deferred)** | v1 无 session / Q&A flow(详 §14 D8 session log)|
| `datasource`(外部数据源) | → **(v1 无对应,v2+ deferred)** | v1 无外部 view backend integration |

**核心差异**:
- 我们 v1 收口为 3 个,聚焦 Form 1(Datalog-style)核心场景
- `inline_constant` 是**我们独有**(Rainbird 无对应)— 显式标注 literal 来源,提升 audit 透明度
- Rainbird 3 个 v1 不引入(answer / injection / datasource)— 等用户实际场景出现

### 5.4 Color Coding(扩展 shipped `audit/evidence_graph.py:_node_palette`)

shipped `_node_palette` 函数(`audit/evidence_graph.py:507-512`)目前 per node_kind 给色:
- `NODE_CONCLUSION` → 深蓝 `#375a7f`
- `NODE_PREMISE` → 紫 `#7c4d9d`
- `NODE_SEED` → 深绿 `#2e7d32`(所有 source 同色)

**v1 扩展**:`NODE_SEED` 按 source 着色,对齐 Rainbird color 心智模型:

| source | 本设计 v1 color(RGB hex)| 对齐 Rainbird 色 | 心智 |
|---|---|---|---|
| `ledger_assertion` | **橙 `#d97e3a`** | `knowledgemap` 的 orange | "已知 KG 事实" |
| `inferred_intermediate` | **深绿 `#2e7d32`**(shipped 默认色,保留 backward compat) | `rule` 的 dark blue(我们用绿区分以避与 NODE_CONCLUSION 混淆) | "推导出来的事实" |
| `inline_constant` | **浅绿 `#88c87c`** | `inject` 的 light green | "显式注入的常量" |

**实现路径**(Phase C):
```python
# audit/evidence_graph.py 扩展 _node_palette 签名
def _node_palette(node_kind: str, source: str | None = None) -> tuple[str, str, str]:
    if node_kind == NODE_CONCLUSION:
        return ("#375a7f", "#375a7f", "#f0f6fb")
    if node_kind == NODE_SEED:
        if source == "ledger_assertion":
            return ("#d97e3a", "#d97e3a", "#fdf2e8")
        if source == "inferred_intermediate":
            return ("#2e7d32", "#2e7d32", "#eef7ef")
        if source == "inline_constant":
            return ("#88c87c", "#88c87c", "#f0f8ee")
        return ("#2e7d32", "#2e7d32", "#eef7ef")  # fallback
    return ("#7c4d9d", "#7c4d9d", "#f5f0ff")  # NODE_PREMISE
```

**渲染调用点**:`_render_tree_node` / `_render_timeline_card` 读 `node.engine_meta.get("source")` 注入 palette。

**Phase C 工作量**:~30 行(扩展 `_node_palette` 签名 + 调用点更新);测试基线:per source 渲染 visual snapshot。

### 5.5 互斥与必填规则(strict validator)

构造期(EvidenceGraph 构造时)校验:

```python
def _validate_node_seed_source(node: EvidenceNode) -> None:
    if node.node_kind != NODE_SEED:
        return
    source = node.engine_meta.get("source")
    if source not in {"ledger_assertion", "inferred_intermediate", "inline_constant"}:
        raise EvidenceValidationError(
            f"NODE_SEED.engine_meta.source '{source}' not in v1 3-enum"
        )
    # per-source 必填字段
    if source == "ledger_assertion":
        if "asrt_id" not in node.engine_meta:
            raise EvidenceValidationError("ledger_assertion source requires asrt_id")
        origin = node.engine_meta.get("assertion_origin")
        if origin is not None and origin not in {
            "import", "manual_write", "external_datasource", "system_injection", "user_input"
        }:
            raise EvidenceValidationError("ledger_assertion assertion_origin not in v1 enum")
    if source == "inferred_intermediate" and "derived_from_rule_id" not in node.engine_meta:
        raise EvidenceValidationError("inferred_intermediate source requires derived_from_rule_id")
    if source == "inline_constant" and "literal_value" not in node.engine_meta:
        raise EvidenceValidationError("inline_constant source requires literal_value")
    # 注:NAF 已退出 source layer(2026-05-19);NAF 案例在 NODE_PREMISE.reason 表达,无 NODE_SEED
```

**Phase C 实现位置**:`audit/evidence_graph.py` 内部 `__post_init__` 加 validator(沿用现有 cycle 检测 + node_id 唯一性检测同位置)。

### 5.6 v1.x 扩展候选(deferred,详 §14 D14-D19)

| 候选 source | v1.x 触发 | Rainbird 对应 |
|---|---|---|
| `external_injection` | `fg.inject` API 引入(v1.x feature)| Rainbird `injection` |
| `user_answer` | session-style Q&A flow 引入 | Rainbird `answer`(同 D8 session log)|
| `external_datasource` | 外部 view backend 集成 | Rainbird `datasource` |
| `synthesis_optional` | optional condition 桥接(广义 synthesis)| Rainbird `synthesis`(广义) |

**enum 演进策略**:v1 严格 3-enum;v1.x 添加新 value **追加,不重命名旧 value**(保持 forward compat);v2+ 视需求重整。

### 5.7 §5 设计承诺 Commitments(C107-C109)

| # | 承诺 |
|---|---|
| C107 | **(2026-05-19 修订)** NODE_SEED.engine_meta.source 严格 **3-enum**(`ledger_assertion` / `inferred_intermediate` / `inline_constant`);per-source 必填字段锁定(详 §5.2 表);构造期 strict validator raise `EvidenceValidationError`;**比 Rainbird 严谨**(Rainbird 6-enum 是 free-form string);**NAF 退出 source layer 入 NODE_PREMISE.reason**(§5.2.1);非 NODE_SEED 不要求 source 字段 |
| C108 | **(2026-05-19 修订)** Rainbird 6-enum → 本设计 **3-enum** 映射:`knowledgemap` → `ledger_assertion`;`rule` → `inferred_intermediate`;`synthesis` / `answer` / `injection` / `datasource` → **v1 不映射,v1.x deferred**(详 §14);v1 NAF 在 NODE_PREMISE.reason 而非 source |
| C109 | **NODE_SEED color coding 按 source 区分**(3 色,2026-05-19 修订):`ledger_assertion` 橙 `#d97e3a` / `inferred_intermediate` 深绿 `#2e7d32`(shipped 默认色) / `inline_constant` 浅绿 `#88c87c`;NAF 不再拥有 source 色;扩展 `_node_palette(node_kind, source=None)` 签名 Phase C 工作 ~30 行;沿用 NODE_CONCLUSION / NODE_PREMISE 现有色 |

### 5.8 §5 显式 deferred 项

| 项 | 触发条件 |
|---|---|
| `external_injection` source(对应 `fg.inject` API)| v1.x `fg.inject` feature 引入 |
| `user_answer` source | session-style Q&A flow(同 §14 D8 session log)|
| `external_datasource` source | 外部 view backend 集成 |
| `synthesis_optional` source(广义 synthesis,Rainbird 模式)| optional condition 桥接需求 |
| `_node_palette` source-aware 调用点更新 | Phase C 实现(~30 行,沿用 shipped 渲染管线)|

---

## 6. Quantitative Metrics(carrier-only,无数学聚合)

> **本节状态**:Phase B-3 落定 2026-05-18。**只锁 quantitative carrier 字段形态**,**不**设计数学聚合 / 概率组合规则(那些 deferred 到 §8 ProbLog 分叉设计或 v2+ aggregation rule)。

### 6.1 立场:唯一 canonical carrier — 严格隔离

- **唯一 canonical quantitative carrier** = `raw_kind` + `bound`(主文档 §5.8.2 / C64 落地 EvaluateRow)
- canonical schema(EvaluateRow / Explanation / EvidenceGraph)**不引入** 独立 public `probability` / `confidence` / `certainty` 字段
- 所有 quantitative 表达(ProbLog 点概率 / interval / PyReason possibilistic / Rainbird certainty factor)**统一规范化** 为 `raw_kind` + `bound`
- **本节只锁 carrier**;数学(noisy_or / SDD aggregation / weight propagation)**deferred** 到 §8 [pending] 或 v2+

### 6.2 v1 表达规则(canonical lock)

| 引擎 / 场景 | raw_kind | bound | 备注 |
|---|---|---|---|
| **ProbLog 点概率 `p=0.8`** | `"probabilistic"` | `(0.8, 0.8)` | **degenerate interval**(`lo == hi`)|
| **ProbLog 区间投影**(lo ≠ hi)| `"probabilistic"` | `(lo, hi)` | |
| **PyReason possibilistic interval** | `"possibilistic"` | `(lo, hi)` | Form 2 范围 |
| **PyReason 点 certainty**(罕见)| `"possibilistic"` | `(c, c)` | 同 degenerate |
| **Souffle / native deterministic** | `None` | `None` | **关键:不写 `(1.0, 1.0)`** |
| **Rainbird-style certainty(1-100)** | — | — | **拒绝引入**(O2)|

**核心 invariant**:
- `(raw_kind, bound)` 是 atom-level 同 EvaluateRow-level 同义的 carrier
- `raw_kind=None` ⇔ `bound=None`(逻辑等价,**禁止** `raw_kind=None, bound=(0.5, 0.5)` 等不一致 case)
- 构造期校验:`raw_kind is None XOR bound is None` → `QuantitativeCarrierError`

### 6.3 为什么 `(1.0, 1.0)` deterministic 是禁止的

deterministic atom(逻辑确定满足)**不应** 表达为 `bound=(1.0, 1.0)`:

| 表达 | 语义 |
|---|---|
| `raw_kind=None, bound=None` | "逻辑满足"(deterministic;无 quantitative dimension)|
| `raw_kind="probabilistic", bound=(1.0, 1.0)` | "概率 certainty = 1.0"(probabilistic;point estimate 是 1.0)|

两者**语义不同**:
- 前者:atom 在逻辑层成立,无概率维度(Souffle / native)
- 后者:atom 在概率模型里 point estimate 为 1.0(ProbLog 中确定性概率事实 `1.0::p(...)` 是这种)

**v1 禁止混淆**:逻辑成立 = `None / None`;概率 = 1.0 = `"probabilistic", (1.0, 1.0)`(罕见但合法)。

### 6.4 Renderer Shorthand 规则(value_summary 渲染)

NODE_CONCLUSION / NODE_PREMISE 的 `value_summary` 字段(per §4.2 顶层填充规约)按以下规则渲染:

| 条件 | value_summary |
|---|---|
| `raw_kind="probabilistic" AND bound[0] == bound[1]` | `"p={value}"`(e.g., `"p=0.8"`)|
| `raw_kind="probabilistic" AND bound[0] != bound[1]` | `"p∈[{lo}, {hi}]"`(e.g., `"p∈[0.6, 0.9]"`)|
| `raw_kind="possibilistic"` | `"[{lo}, {hi}]"`(e.g., `"[0.6, 0.9]"`)|
| `raw_kind=None`(deterministic)| `""`(空字符串,不显示 quantitative summary)|
| 失败 case(C81 evidence=None)| N/A(无 EvidenceGraph 节点)|

**Phase C 实现位置**:
- `audit/evidence_graph.py` 内部 `_format_value_summary(raw_kind, bound)` 辅助函数(~15 行)
- NODE_CONCLUSION / NODE_PREMISE 构造时调用

### 6.5 Adapter-Native Debug Fields(non-contract 例外)

允许 adapter 在 `engine_meta` 中**额外**记录 native 字段作调试用:

| 字段 | 类型 | 用途 |
|---|---|---|
| `engine_meta.native_probability` | `float \| None` | ProbLog adapter 原始 probability 输出(对比 `bound[0]` 是否一致 — debug)|
| `engine_meta.problog_raw_probability` | `float \| None` | 同上,显式命名(便于 grep / debug)|
| `engine_meta.pyreason_raw_bound` | `tuple \| None` | PyReason adapter 原始 bound(Form 2 调试)|
| `engine_meta.adapter_debug_*` | `Any` | 任意 adapter-prefixed 调试字段 |

**规则**(C113):
- 这些字段**non-contract** — canonical schema(EvaluateRow / Explanation / 公开 EvidenceGraph 文档)**不消费,不依赖**
- 命名建议 `engine_meta.<engine_name>_native_*` 或 `engine_meta.adapter_debug_*`(避免与 canonical 字段命名冲突)
- 不参与 cross-engine evidence 比对 / digest 计算
- 不进入 `value_summary` 渲染
- **不暴露** 给用户面 SDK(`Explanation.evidence` 暴露 `EvidenceGraph` 整体,用户可读但**文档化为 audit-only,not API contract**)
- 调试用途:adapter implementer 验证规范化一致性(`native_probability` vs `bound[0]`)

**反 anti-pattern**:**禁止** 把 `native_probability` 作为 fallback / 主数据源 — canonical 路径必须经 `raw_kind + bound`(避免双写漂移)。

### 6.6 §6 NOT 在本节锁定(deferred)

| 项目 | Defer 到 |
|---|---|
| **聚合规则**(noisy_or / SDD aggregation / product / independent_sum)| §8 [pending] success tree(ProbLog 多 path 加权)+ §10.6 AggregateExpr(C99 / aggregation kind)|
| **概率传播**(child → parent 的 bound 计算)| §8 [pending] success tree 形态;v1 默认 engine adapter 给出 |
| **Path-level vs Atom-level vs Root-level bound 区别** | §4.13.2 Example 2 已示意(Atom 默认 None / Root 来自 engine);完整规约 §8 [pending]|
| **`salience` / `impact` / `ruleMaxCertainty` 数学**(若 v1.x 加入)| 详 §14 D6 / D7 / D15 |
| **跨引擎 bound 等价性**(同 Rule 在 Souffle 跑 vs ProbLog 跑结果是否可比)| v2+ multi-engine 一致性设计 |

**关键立场**:**§6 仅锁 carrier 字段形态**,数学聚合 / 规则推导 / 跨 engine 一致性**全 deferred**。这保证 §6 不会和其他章节冲突。

### 6.7 §6 设计承诺 Commitments(C110-C113)

| # | 承诺 |
|---|---|
| C110 | **唯一 canonical quantitative carrier = `raw_kind` + `bound`**;canonical schema(EvaluateRow / Explanation / EvidenceGraph)**不引入** 独立 public `probability` / `confidence` / `certainty` 字段;所有 quantitative 表达(ProbLog 点概率 / interval / PyReason possibilistic)**统一规范化** 为 `raw_kind + bound`;构造期校验 `raw_kind XOR bound` 同 None → `QuantitativeCarrierError`(详 §6.2)|
| C111 | **ProbLog 点概率 = degenerate interval**:`raw_kind="probabilistic", bound=(p, p)`;**deterministic** 表达为 `raw_kind=None, bound=None`;**禁止** 用 `bound=(1.0, 1.0)` 表示"逻辑满足"(避免与"概率 certainty=1.0"混淆,详 §6.3)|
| C112 | **Renderer shorthand 规则**(value_summary 渲染):probabilistic + degenerate → `"p={value}"`;probabilistic + interval → `"p∈[lo, hi]"`;possibilistic → `"[lo, hi]"`;None → `""`(详 §6.4);Phase C 实现位置 `audit/evidence_graph.py:_format_value_summary` |
| C113 | **Adapter-native debug fields 例外**:允许 `engine_meta.native_probability` / `engine_meta.problog_raw_probability` / `engine_meta.<engine>_native_*` 作 adapter 调试用;**non-contract**,canonical schema 不消费 / 不依赖 / 不参与 digest;**禁止**作 fallback 或主数据源(防双写漂移,详 §6.5)|

### 6.8 §6 显式 deferred 项

详 §6.6 表 + §14 D6 / D7 / D15。

---

## 7. Explain Orchestrator(流程 / 调度)

> **本节状态**:Phase B-5 落定 2026-05-19。本节回答"`row.explain()` / `fg.eval.explain(...)` 收到请求后,系统怎么生成 EvidenceGraph?";**不**重新定义用户 API(API 锁主文档 §5.8.2-§5.8.3 C64-C66),**不**重新定义 target format(§8 锁)。

### 7.1 立场:Orchestrator 是 producer,不重新定义 schema / API

- §7 = **producer pipeline**:把 user input(row 或 closed_head)→ Explanation 输出
- §7 **消费**:主文档 §5.8.2 API + §8 target topology + §4 schema + §5 source + §6 quantitative carrier
- §7 **不产生**:新 schema / 新 API / 新 commitment 形态(只锁 pipeline 步骤 + dispatch 行为 + validator gate)
- 每步明示**输入 / 输出 / 失败路径**,Phase C 实现照此 wire

### 7.2 8-step Pipeline 总览

```
              ┌──────────────────────────────────────────┐
              │ user call: row.explain() | fg.eval.explain(...)
              └──────────────┬───────────────────────────┘
                             ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 1: Resolve entry                               │  →  raise DetachedRowError on detached row
   │   • live row → _result_resolver() → EvaluateResult │
   │   • manual closed_head → caller-provided context    │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 2: Validate request/context                    │  →  failure_class on business failure
   │   • row_not_in_result / stale_row(digest 漂移)     │  →  errors on schema/engine technical failure
   │   • closed_head_false / insufficient_closed_bindings│
   │   • engine capability(unsupported)                  │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 3: Prepare evidence context                    │
   │   • projected view(project_view_facts)              │
   │   • witness index(per-engine adapter native)        │
   │   • closed bindings(from row / closed_head)         │
   │   • semantics profile                               │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 4: Choose strategy                             │
   │   • S1 IR replay(默认 / Souffle / native)         │
   │   • S2 engine-native probe(advanced opt-in)        │
   │   • S3 library API enrichment(ProbLog 概率)        │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 5: Build topology                              │  →  per §8 4-layer + seed reuse + ProbLog multi-path
   │   • Layer 0 root NODE_CONCLUSION                    │
   │   • Layer 1 Rule firing NODE_CONCLUSION × N         │
   │   • Layer 2 atom NODE_PREMISE × Σ atoms             │
   │   • Layer 3 witness NODE_SEED × matched facts       │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 6: Extract reasons + Stitch seeds              │
   │   • AtomKindSpec.reason_extractor(per atom kind)   │
   │   • AggregateExpr contributors envelope             │
   │   • NAF reason in NODE_PREMISE.reason.naf           │
   │   • Seed dedup table(同 fact → 同 NODE_SEED)       │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 7: Validate EvidenceGraph                      │  →  gate fail → status="unsupported" + errors
   │   • schema_version present                          │  →  NOT partial graph
   │   • required keys per node_kind / source / reason   │
   │   • shipped cycle check(audit/evidence_graph.py:95) │
   │   • metadata 双驻 from EvaluateResult context       │
   └──────────────┬─────────────────────────────────────┘
                  ▼
   ┌────────────────────────────────────────────────────┐
   │ Step 8: Return Explanation                          │
   │   • passed: evidence=EvidenceGraph                  │
   │   • failed / unsupported / invalid_request:        │
   │     evidence=None + failure_class or errors        │
   └────────────────────────────────────────────────────┘
```

**Pipeline 性质**:
- **single-pass**,无回退(任一 step 失败 → 短路返回 Explanation)
- **deterministic**:同 input + 同 context = 同 EvidenceGraph(digest 跨进程稳定)
- **stateless per call**:每次 explain 独立(不复用 cross-call cache;v1 default)

### 7.3 Step 1:Entry Resolution(2 个入口分流)

| Entry | 入口形态 | Resolve 行为 |
|---|---|---|
| **主路径**:`row.explain()` / `result[i].explain()` | `row._result_resolver` 非 None | resolver() 返回 EvaluateResult,extract context |
| **Manual / Advanced**:`fg.eval.explain(expr, head=closed_head, engine, semantics)` | caller 直接传 (expr, closed_head, engine, semantics)+ **manual context minimum**(详 §7.3.1)| 构造**临时 EvaluateResult-equivalent context**(无 row,binds 来自 closed_head literal atoms)|
| **Detached row**:`row.explain()` 在 `row._result_resolver=None` | resolver None | **raise `DetachedRowError`**;**不**进入 Explanation pipeline |

**关键 invariant**(C130):
- Live row entry 与 manual closed_head entry 在 Step 3+ 走**同一 pipeline**(差异仅 Step 1 resolver)
- DetachedRowError 是 **Python exception**,**不**进 failure_class enum(C131)
- Manual closed_head 必须 caller 自行验证 row context;无 result back-ref 时 stale_row 检测降级到 closed_head_false

#### 7.3.1 Manual Path Context Minimum Contract(C135 协同,2026-05-19 补)

> **设计意图**:`fg.eval.explain(expr, head=closed_head, ...)` 不能让 caller 缺字段就跑;否则 C135 "metadata 双驻 source-of-truth" 在 manual path 上变模糊(无 EvaluateResult 可借鉴)。**caller 必须提供或派生** 7 个最低字段,orchestrator 据此构 temporary context。

**Manual path 7 个 minimum required fields**:

| 字段 | 来源 / 派生 | 用途 |
|---|---|---|
| `engine` | caller 显式传 | 选 adapter |
| `semantics` | caller 显式传 | semantics profile(可 None;deterministic case)|
| `expr_digest` | caller 派生或显式传(`RuleExpr.content_digest` per C34)| 漂移检测 + metadata |
| `rule_set_digest` | caller 派生或显式传(expr 内 Rule content_digests canonical join)| Rule 字段漂移检测 |
| `view_snapshot_digest` | caller 显式传(指明用哪个 fact snapshot)| fact 漂移检测 + metadata |
| `evaluated_at` | caller 显式传(用此 fact snapshot 的时间)| audit timestamp |
| `closed_head_content_digest` | caller 派生或显式传(`closed_head.content_digest`)| closed head identity |

**衍生字段**(orchestrator 自行派生,非 caller 责任):
- `engine_version` / `adapter_version`:adapter 报告
- `rule_content_digest`:open head Rule(若 caller 区分 open / closed)或 closed_head.content_digest
- `semantics_digest`:`semantics` 派生(若非 None)
- `result_id` / `row_id` / `claim_digest` / `evidence_ref_id`:**manual path 这 4 个填 `None` / `null`**(无 EvaluateResult / EvaluateRow 实体)— 后续 metadata 字段 schema 允许 None 在 manual path

**违反**(min 字段缺失)→ `Explanation(status="invalid_request", errors=MANUAL_CONTEXT_INCOMPLETE)`(per §7.4 technical validation 分流)。

**Phase C 实现**:orchestrator Step 1 manual path 分支构 temporary context object;Step 7 validator gate 校验 metadata 字段时 — manual path 4 个 row-/result-referencing 字段允许 None,其他 11 字段必填(C135 协同)。

### 7.4 Step 2:Validation(business vs technical 分流)

**Business failure**(`status="failed"` + `failure_class`,per C125):

| 检查 | failure_class | 触发条件 |
|---|---|---|
| Row 不在 result 内 | `row_not_in_result` | `row.evidence_ref.result_id != result.result_id`(orchestrator 不轻信用户传的 row)|
| Digest 漂移 | `stale_row` | `row.evidence_ref.closed_head_digest` vs 当前 closed_head 重计算 mismatch;或 view_snapshot_digest / rule_set_digest mismatch |
| Closed head 不成立(manual)| `closed_head_false` | manual path 用户传的 closed_head 在 current view 评估为 false |
| 闭合 binding 不完整 | `insufficient_closed_bindings` | head.ports 未全绑定 literal(典型 manual path 错误)|
| 无对应 row | `no_matching_row` | 内部 resolver 用 row_id 查找未命中(`result[id]` 之类内部查找,或 manual caller 传入指向不存在的 row identity);**public API 不暴露 row_id 字符串入口**,这一态主要由 advanced replay path 触发 |

**Technical failure**(`status="unsupported"` / `"invalid_request"` + `errors`):

| 检查 | status | error code |
|---|---|---|
| Engine 不支持 atom kind | `unsupported` | `ENGINE_ATOM_KIND_UNSUPPORTED` |
| Witness lookup 失败(adapter bug)| `unsupported` | `EVIDENCE_LOOKUP_MISS` |
| 输入 shape 错误(non-Rule head 等)| `invalid_request` | `INVALID_HEAD_TYPE` |
| Engine / semantics 不自洽(C69)| `invalid_request` | `ENGINE_SEMANTICS_MISMATCH` |

**关键 invariant**:**不混淆 business vs technical**(C125)。`engine_no_witness` 不进 `failed.failure_class`,走 `unsupported.errors`。

### 7.5 Step 3:Prepare Evidence Context

**输入**:已 validated request(live row + resolved EvaluateResult,或 manual closed_head + context)

**准备工作**:

| 资源 | 来源 | 用途 |
|---|---|---|
| `view_facts: dict[pred_id, list[tuple]]` | `project_view_facts(store.ledger, schema_ir)`(shipped `core/view/projector.py:117`)| Step 4 IR replay / Step 6 fact lookup |
| `witness_index: dict[(pred_id, fact_tuple), asrt_id]` | per-engine adapter native witness(Souffle `_ParsedWitnessRow.witness_atoms` / ProbLog fallback ledger 反查 via `find_claims`)| Step 6 seed stitching |
| `closed_bindings: dict[var, value]` | row.bindings(live)/ closed_head.where literal atoms(manual)| Step 4-6 evaluation |
| `semantics_profile` | EvaluateResult.semantics(live)/ caller 传入(manual)| Step 4 strategy + Step 6 quantitative |

**Phase C 实现**:本步 idempotent;同 input 同 output(不引入 randomness / time-dependent 行为)。

### 7.6 Step 4:Strategy Dispatch(S1 / S2 / S3)

**3 个策略职责**(C133):

| 策略 | 职责 | 触发条件 | engine 适用 |
|---|---|---|---|
| **S1 IR replay** | **core / default**:用 FactGraph 自身 `_eval_*_atom` per-atom 重放,构造 evidence | 总是先跑 | Souffle / native(原生 fit);ProbLog(replay 同 view,probability 走 S3 enrich)|
| **S2 engine-native probe** | optional / advanced:用 engine subprocess / 库做单 atom probe,获得 native witness | Adapter opt-in;典型用 Souffle subprocess 跑 derived rule 验证 | Souffle(完全)/ ProbLog(部分)|
| **S3 library API enrichment** | enrichment:per-atom probability / 量化字段补充 | ProbLog only(必须用此路径拿概率) | ProbLog `problog.query()` per atom |

**典型 dispatch 矩阵**:

| Engine | 策略组合 |
|---|---|
| Souffle / native | **S1 only**(IR replay 完全自洽)|
| ProbLog | **S1 + S3**(S1 构 evidence 结构,S3 enrich `raw_kind` / `bound`)|
| PyReason(Form 2 范围,本文档不锁)| **S1 only,pred-only**(详 §4.11 / C92)|

**S2 在 v1 不强制**(Phase C 可选实现);用户无需触发 S2 — Phase C orchestrator 决策。

### 7.7 Step 5:Graph Construction(per §8 topology)

**Build per §8 4-layer 序列**:

1. **Layer 0 root**:`NODE_CONCLUSION` for closed_head;engine_meta 含 `explained_claim_ref`(C122)+ `quantitative_explanation`(C127)+ `alternative_paths`(C129)
2. **Layer 1 intermediate**(若 expr 含多 Rule):`NODE_CONCLUSION` × N,per fired Rule
3. **Layer 2 atom premises**:`NODE_PREMISE` × Σ atoms across all fired Rules
4. **Layer 3 seeds**:`NODE_SEED` × witness facts(per source 3-enum)

**Seed dedup**(per C118 §8.7):
- orchestrator 维护 `seed_table: dict[(source, identity_key), node_id]`
- 同一 fact 跨多 atom 仅 1 个 NODE_SEED
- `identity_key` per source:`asrt_id`(ledger) / `literal_digest`(inline_constant)/ `(rule_id, fact_digest)`(inferred_intermediate)

**ProbLog multi-path**(per C119 §8.9):
- Detection:S3 enrichment 阶段若 ProbLog 报多 derivation 同 bindings
- Build:Layer 1 多 NODE_CONCLUSION,`engine_meta.path_index` 区分
- Root aggregate `raw_kind` / `bound` + `aggregation_rule`(数学 deferred)

**Form 1 edge_kind**:**仅 `EDGE_SUPPORTS`**(per C115 §8.3 / §8.8 inferred_intermediate);`EDGE_DERIVES` / `EDGE_UPDATES` 留 Form 2。

### 7.8 Step 6:Reason Extraction + Seed Stitching

**Per-atom reason extraction**(per §4.5 + AtomKindSpec.reason_extractor):

| atom_kind | extraction 行为(指 §4.8.5 responsibility table)|
|---|---|
| `pred` | witness lookup(witness_index 反查 asrt_id)+ matched fact tuple |
| `eq` / `ne` / `gt` / `ge` / `lt` / `le` | resolved lhs / rhs values + operator |
| `in` | tested value + allowed set summary |
| `not`(NAF success) | reason.naf: `{negated_atom_repr, search_scope, counterexample_count=0}`(per C121,**NAF 不进 NODE_SEED**)|

**ArithExpr 在 comparison RHS / LHS**(per C98 §10.6.2):reason `kind="arith_comparison"` + `evaluation_trace`;div-by-zero → `error_kind="division_by_zero"` + violated。

**AggregateExpr 在 comparison RHS / LHS**(per C99 §10.6.3):reason `kind="aggregate_comparison"` + `aggregate` envelope + `contributors {mode, count, handle}`(C128;v1 mode=`"omitted_v1"`,handle=None,count=matched_count)。

#### 7.8.1 AggregateExpr orchestrator 行为(per §8.10 / C136)

> **关键差异**:Aggregate premise **不走** 普通 `pred → witness seed` 路径(§8.10.3 拓扑表)。Orchestrator Step 6 对 aggregate premise 的处理是**特殊分支**。

**Aggregate orchestrator 路径**(Step 6 内分支):

```text
For each NODE_PREMISE:
  if atom is AggregateExpr-bearing comparison:
    # ── Aggregate branch ──
    reason = aggregate_reason_extractor(atom, closed_bindings, view_facts)
      where reason fills:
        - aggregate_kind / filter_repr
        - matched_count(用 Step 3 frozen snapshot count,**不**重查)
        - contributors = {mode: "omitted_v1", count: matched_count, handle: None}  ← v1 hard-coded
        - aggregate_result / empty_set / no_value / error_kind
        - comparison fields(lhs/rhs/op/status)
    skip seed stitching                          # ← v1 不展开 contributor seeds
    skip seed dedup table 注册                    # ← aggregate 不参与 seed reuse
    construct EDGE_SUPPORTS (premise → parent conclusion);**no** outgoing edges
    
  elif atom is pred:
    # ── Normal pred branch(原有路径)──
    reason = pred_reason_extractor(...)
    seed stitching:witness_index 反查 asrt_id → 构造 NODE_SEED(查 dedup table)
    construct EDGE_SUPPORTS (premise → conclusion + seed → premise)
    
  else:
    # eq / ne / gt / ge / lt / le / in / not / arith_comparison
    reason = corresponding extractor(...)
    no seed stitching needed(constraint-only atoms,no fact witness)
```

**Key invariants(C136 协同)**:
- Aggregate premise:**0 outgoing edges**(无 NODE_SEED 关联);仅 1 incoming `EDGE_SUPPORTS` (来自父 NODE_CONCLUSION)— wait,**1 outgoing edge to parent**(per §8.3 edge direction: from=premise, to=parent);**0 incoming edges from seeds**(无 sub-seed)
- `contributors.mode` v1 锁 `"omitted_v1"`;**禁止** orchestrator 写 `"lazy"` / `"embedded"`(v1 schema gate raise)
- `matched_count` 来源 **必须**是 Step 3 prepared context(frozen snapshot);Step 6 **禁止重查** view_facts 算 count(C103 invariant)
- Aggregate premise **不进 seed dedup table**(per C118 `seed_table`:`(source, identity_key) → node_id`;aggregate 无 sub-seed,无 identity_key)

**Seed stitching**(普通 pred 路径):对每个 **pred atom** NODE_PREMISE,通过 witness_index 找 asrt_id,构造 NODE_SEED(若不在 dedup table 中)+ EDGE_SUPPORTS。**Aggregate premise 跳过此 stitching**(per 上文)。

### 7.9 Failure Routing Matrix(across steps)(C132)

**`status="passed"` 才构造 EvidenceGraph**;其他 3 态**全部 `evidence=None`**(C81)。本节是**跨 step 的失败映射表**(任一 step 短路返回路径),非单一 step 内容。

| Pipeline 阶段 | 失败可能 | 映射 |
|---|---|---|
| Step 1 entry resolve | Detached row | **raise `DetachedRowError`**(不进 Explanation)|
| Step 2 validation | business failure | `Explanation(status="failed", failure_class=..., checked_scope=..., suggested_next_steps=..., evidence=None)` |
| Step 2 validation | technical failure | `Explanation(status="unsupported" or "invalid_request", errors=..., evidence=None)` |
| Step 3-6 build | engine-side failure(adapter raise)| `Explanation(status="unsupported", errors=...)` |
| Step 7 graph validation | gate fail | `Explanation(status="unsupported", errors=GRAPH_VALIDATION_FAILED, evidence=None)`(**不**返回 partial graph,per C134)|
| Step 8 success | — | `Explanation(status="passed", evidence=EvidenceGraph, ...)` |

**关键 invariant**:
- C131:DetachedRowError 是 Python exception,**绝不进** failure_class
- C134:graph validation gate 失败 = `unsupported` + errors,**绝不**返回 partial / corrupted graph
- C132:`passed` ⇔ `evidence != None`(双向 iff,per C81)

### 7.10 Step 7 Validator Gate(详细)

**Phase C strict validator 检查清单**(在 Step 7 跑;不达标即 reject):

| Gate 项 | 检查内容 |
|---|---|
| **schema_version** | `EvidenceGraph.metadata.schema_version == "1.0"`;不存在 → reject(C124)|
| **node_id uniqueness** | shipped `audit/evidence_graph.py:78-79` 已强制 |
| **edge_id uniqueness** | shipped `audit/evidence_graph.py:81-83` 已强制 |
| **root_node_id 在 nodes 内** | shipped `audit/evidence_graph.py:85-87` 已强制 |
| **edge endpoints 在 nodes 内** | shipped `audit/evidence_graph.py:89-93` 已强制 |
| **cycle check** | shipped `audit/evidence_graph.py:95-115` DFS 已强制 |
| **per node_kind required keys** | C82-C89 + C122 + C127 + C129(NODE_CONCLUSION root 必填 `explained_claim_ref` / `quantitative_explanation` / `alternative_paths`)|
| **NODE_SEED.source 3-enum** | C107 / C121(`ledger_assertion` / `inferred_intermediate` / `inline_constant`)|
| **NODE_SEED per-source required fields** | C107 + C126(ledger_assertion 必填 asrt_id;assertion_origin 可 None)|
| **NODE_PREMISE.reason.kind 4-enum** | C106(`comparison` / `arith_comparison` / `aggregate_comparison` / `compound_comparison`)|
| **AggregateExpr `contributors.count == matched_count`** | C128 invariant |
| **Form 1 仅 `EDGE_SUPPORTS`** | C115;Form 2 才允许 `EDGE_DERIVES` / `EDGE_UPDATES` |
| **metadata 15 必填 fields** | C123(schema_version / evaluated_at / engine / engine_version / adapter_version / rule_content_digest / closed_head_content_digest / expr_digest / rule_set_digest / view_snapshot_digest / semantics_digest / result_id / row_id / claim_digest / evidence_ref_id)|

**Validator 失败行为**:**reject**(return `Explanation(status="unsupported", errors=GRAPH_VALIDATION_FAILED)`),**不**返回 partial / silently-skipped EvidenceGraph(C134)。

**双驻 source-of-truth check**(C135):
- metadata fields 必须 derive 自 EvaluateResult context(或 manual context if applicable)
- orchestrator **不**独立计算 metadata fields(否则双写漂移)
- Phase C 实现:metadata 从单一 evaluated context object 写,debug assertion 校验

### 7.11 §7 设计承诺 Commitments(C130-C135)

| # | 承诺 |
|---|---|
| **C130** | **Orchestrator 入口两类**:**主路径 `row.explain()` / `result[i].explain()`** via `_result_resolver` 解析 EvaluateResult context;**Advanced `fg.eval.explain(expr, head=closed_head, engine, semantics)`** caller 自带 context(无 row back-ref);两入口在 Step 2-8 走同一 pipeline,差异仅 Step 1 resolution(详 §7.3)|
| **C131** | **Detached row 直接 raise `DetachedRowError`**(Python exception);**不**进入 `Explanation.failure_class` enum;不调用 pipeline Step 2+;明示**编程错误**(用户错误传 detached row)与**业务失败**(stale_row 等)分离 |
| **C132** | **`status="passed"` ⇔ `evidence != None`**(双向 iff,per C81);failed / unsupported / invalid_request **全部 `evidence=None`**;orchestrator Step 8 拼装时严格遵循;**禁止**任何中间态 partial / corrupt EvidenceGraph 返回 |
| **C133** | **Strategy dispatch 三策略锁定**:**S1 IR replay = core / default**(总是先跑,Souffle/native/ProbLog 全适用);**S2 engine-native probe = optional advanced**(adapter opt-in;v1 可不实现);**S3 library API enrichment = ProbLog only**(per-atom probability via `problog.query()`);典型矩阵:Souffle / native = S1 only;ProbLog = S1 + S3(详 §7.6)|
| **C134** | **Graph validation gate 必跑**(Step 7);gate 失败 → `Explanation(status="unsupported", errors=GRAPH_VALIDATION_FAILED)`,**不**返回 partial graph;validator 强制 14 项检查(详 §7.10);**禁止 silently-skipped** validator(防止 schema drift)|
| **C135** | **EvidenceGraph.metadata 双驻 source-of-truth invariant**(per C123):metadata 15 字段必须 derive 自单一 evaluated context object(EvaluateResult or manual context);orchestrator **不允许独立 / 二次计算** metadata 字段;Phase C 实现 debug assertion 校验 metadata 与 EvaluateResult fields 跨字段一致 |

### 7.12 §7 显式 deferred 项

| 项 | 触发条件 |
|---|---|
| **S2 engine-native probe v1 实现**(Souffle subprocess based)| 用户出现明确"verify via engine 而非 IR replay" audit 需求 |
| **Cross-engine evidence consistency check**(同 Rule 在 Souffle vs ProbLog 跑 evidence 结构对比)| v2+ multi-engine 一致性设计 |
| **Lazy / streaming pipeline**(Step 5-6 按需 build,大 evidence 不一次性 materialize)| evidence > 10MB 或渐进 UI(§14 D12)|
| **Cross-result evidence stitching**(多 result 拼接同一 evidence tree)| 用户场景出现 |
| **Orchestrator caching**(stateless v1;v2 跨 explain 调用复用 view_facts 等)| 性能瓶颈出现 |

---

## 8. Evidence Tree Topology(格式 / 结构)

> **本节状态**:Phase B-4 落定 2026-05-19。本节负责回答"最终产出的 EvidenceGraph 长什么样?";**format-only**,**不**包括如何生成(生成流程见 §7)。

### 8.1 立场:format-first vs orchestrator separation

- **§8 是"长什么样"**(target shape):envelope / node_id / edge direction / tree-DAG / per-engine 形态 / JSON example
- **§7 是"怎么生产"**(producer pipeline):validate / dispatch / build / stitch
- 设计顺序:**先锁 §8 target,§7 orchestrator 每一步服务于 §8 目标格式**(避免空泛流程)

### 8.2 Envelope:沿用 shipped `EvidenceGraph` + audit reproducibility metadata(C123)

**所有 v1 evidence 共享同一 envelope**(`audit/evidence_graph.py:60`):

```python
@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str                       # 全局唯一 id
    engine: str                         # "souffle" / "native" / "problog" / "pyreason"
    root_node_id: str                   # 树/DAG 根
    nodes: tuple[EvidenceNode, ...]     # 不可变
    edges: tuple[EvidenceEdge, ...]
    support_kind: str                   # passed / passed_with_probability / etc.
    layout_hint: str                    # LAYOUT_TREE(Form 1)/ LAYOUT_TIMELINE(Form 2)
    metadata: Mapping[str, Any]         # 顶级 metadata — v1 必填 audit fields(详 §8.2.1)
```

**Per-engine layout_hint**:
- Form 1(Souffle / native / ProbLog)→ `LAYOUT_TREE`
- Form 2(PyReason temporal)→ `LAYOUT_TIMELINE`

**graph_id 命名**:`"<engine>:<run_id>:<closed_head.content_digest_short>"`(deterministic,跨进程稳定)。

#### 8.2.1 `metadata` 必填 audit reproducibility fields(C123,Wave 1 2026-05-19)

**产品立场**(响应 #7):"durable audit evidence" 是我们对 Rainbird 的核心 strict-superset 承诺(O7)。复现 context 必须 v1 落地,**不能 deferred**。否则 evidence 看似 stateless 但**实际不可复现**(ledger 变 / rule 版本变 / adapter 版本变都会"无声"使 evidence 失效)。

**Source-of-Truth 锁定**(Wave 1 修订 2026-05-19):

> **EvaluateResult is the live context source. EvidenceGraph.metadata is a durable snapshot copied from EvaluateResult. The orchestrator writes both from the same evaluated context object.**

- **Source of truth = evaluation context**(orchestrator 持有的单一 evaluated context object)
- **EvaluateResult.* fields**:live runtime access(`result.engine` / `result.view_snapshot_digest` 等)
- **EvidenceGraph.metadata**:durable snapshot copy(JSON 离开 EvaluateResult 后 self-contained)
- **不**两处独立 source:orchestrator 从单一 context 写两处,**不允许两处分别计算 / 演进**(双写漂移防护)

**v1 必填字段**(`EvidenceGraph.metadata`):

| field | 类型 | 来源 | 用途 |
|---|---|---|---|
| **`schema_version`** | `str` | 锁定 `"1.0"`(v1) | 长期 schema 演进 anchor;C124 |
| **`evaluated_at`** | str (ISO 8601) | `EvaluateResult.evaluated_at` | 何时生成此 evidence |
| **`engine`** | str | 同 EvidenceGraph.engine(重复一处便于 metadata-only 消费)| Engine identifier |
| **`engine_version`** | str | adapter 报告 | 引擎版本(例 `"problog-2.2.4"`)|
| **`adapter_version`** | str | factpy-kernel package version | adapter 实现版本 |
| **`rule_content_digest`** | str | open Rule.content_digest(C68) | rule 漂移检测 anchor |
| **`closed_head_content_digest`** | str | closed_head.content_digest(C68)| closed head identity |
| **`expr_digest`** | str | `EvaluateResult.expr_digest` | RuleExpr 结构漂移检测 |
| **`rule_set_digest`** | str | `EvaluateResult.rule_set_digest` | expr 内 Rule 内容集合漂移检测 |
| **`view_snapshot_digest`** | str | projected view 数据 digest | fact 漂移检测 anchor |
| **`semantics_digest`** | str \| None | semantics wrapper(C68)| semantics 漂移检测 |
| **`result_id`** | str | `EvaluateResult.result_id` | live context 回引 |
| **`row_id`** | str | `EvaluateRow.row_id` | row identity |
| **`claim_digest`** | str | `EvaluateRow.claim.digest` | 被解释 Claim identity |
| **`evidence_ref_id`** | str \| None | `EvaluateRow.evidence_ref.ref_id` | factID 等价 lightweight ref |

**可选 metadata**(Phase C / 用户面 enrichment):
- `factgraph_version` / `python_version` / `host_info` 等(audit 取证用)

**漂移检测 invariant**(Phase C orchestrator 责任):
- 用户 v2 复现 evidence 时,renderer / consumer 用 metadata digests 与当前环境对比
- digest 不一致 → 显式 warning(不 raise)— 用户决定接受 stale evidence vs re-run
- 主文档 §5.8.5 C68 digest 协议同源

#### 8.2.2 Schema Versioning Lite(C124,Wave 1)

**v1 strict-lite**:
- `EvidenceGraph.metadata.schema_version = "1.0"` **必填**;不在 enum 中 raise
- `NODE_*.engine_meta.contract_schema_version` 可选(推荐),未填默认 `"1.0"`
- **Phase C validator 必须校验**:metadata.schema_version + node_kind 必填 keys + source enum(per C107) + reason.kind enum
- **未知 contract keys**(在 contract namespace 内出现未文档化字段)→ v1 warning,不 raise
- **缺失 required keys**(per node_kind 必填字段)→ raise `EvidenceValidationError`

#### 8.2.3 Contract vs Debug 字段分层(C124 协同)

**doc-level 锁定**(2026-05-19 Wave 1):

**Contract fields**(canonical schema 部分,digest-relevant,跨进程 deterministic):
- 所有本文档 §4.3-§4.7 表中 ✓ 必需字段
- 所有本文档 §4.5 reason kinds + sub-schemas
- 所有本文档 §5 source enum + per-source 必填字段
- 所有本文档 §6 raw_kind + bound carrier

**Debug fields**(non-contract,digest-excluded):
- `engine_meta.native_probability` / `<engine>_native_*`(per §6.5 / C113)
- `engine_meta.adapter_debug_*`(任意 prefix)
- `engine_meta.<adapter>_internal_*`

**Validator 规则**:
- contract field 必填 / 类型校验 / enum 校验:**Phase C raise**
- debug field 任意 shape:**Phase C 允许,不参与 digest**
- 命名约定:**debug 字段**必须 `engine_meta.native_*` / `engine_meta.<engine>_*` / `engine_meta.adapter_debug_*` 之一 prefix(grep 友好)

**v1.x 演进路径**:若用户 / adapter 大量 debug field 出现,v1.x 可 restructure 为显式分层:
```python
engine_meta: {
    "contract_schema_version": "1.0",
    "contract": {...},
    "debug": {...},
}
```
v1 不强制 restructure(避免破坏 shipped `audit/evidence_graph.py` consumers)。

### 8.3 Edge Direction Contract(锁定)

shipped `audit/evidence_graph.py:98` `adjacency[edge.to_node_id].append(edge.from_node_id)`:

```
edge: from_node_id  ──supports──>  to_node_id
       (child / 下游 premise)         (parent / 上游 conclusion)
```

**Phase 1 锁定 invariant**:
- `EDGE_SUPPORTS`:**from = premise / seed**,**to = conclusion**(读法 "premise supports conclusion")
- `EDGE_DERIVES`:Form 2 PyReason,**from = source state**,**to = derived state**(temporal derivation)
- `EDGE_UPDATES`:Form 2 PyReason,**from = old state**,**to = new state**(state mutation across timesteps)

**渲染含义**:tree layout renders root 在顶;timeline layout renders 按 timestamp 横排。

### 8.4 node_id / edge_id 命名规则(deterministic)

**node_id 命名 scheme**(per node_kind):

| node_kind | source | id pattern |
|---|---|---|
| `NODE_CONCLUSION`(root,head)| — | `"conclusion:head:{closed_head.id}"` |
| `NODE_CONCLUSION`(intermediate Rule firing)| — | `"conclusion:rule:{rule_id}:p{path_index}"` (multi-path) 或 `"conclusion:rule:{rule_id}"` (single-path)|
| `NODE_PREMISE`(atom)| — | `"premise:{atom_id}"` 其中 atom_id = `"<rule_id>:atom_<index>"` (per C19) |
| `NODE_SEED` | `ledger_assertion` | `"seed:ledger:{asrt_id}"` |
| `NODE_SEED` | `inferred_intermediate` | `"seed:inferred:{upstream_rule_id}:{fact_digest_short}"` |
| `NODE_SEED` | `inline_constant` | `"seed:literal:{value_digest_short}"` |

**edge_id 命名**:`"edge:{from_node_id}->{to_node_id}"`(shipped 要求 unique,简单且 deterministic)。

**同一 fact 跨 atoms 复用同一 NODE_SEED**(详 §8.7);因此同一 seed.node_id 可有多个 incoming edges。

### 8.5 Form 1 Single-Path Tree Topology(Souffle / native / 单 path ProbLog)

**4 层结构**(典型 case;与 §4.13.1 Example 1 一致):

```
Layer 0 (root):        NODE_CONCLUSION   "conclusion:head:{closed_head.id}"
                       ↑ EDGE_SUPPORTS
Layer 1 (Rule firing): NODE_CONCLUSION × N  "conclusion:rule:{rule_id}"  (per expr 内 Rule)
                       ↑ EDGE_SUPPORTS
Layer 2 (atoms):       NODE_PREMISE × Σ atoms  "premise:{atom_id}"
                       ↑ EDGE_SUPPORTS
Layer 3 (seeds):       NODE_SEED × matched facts  (per source)
```

**当 expr = 单 Rule**(C35):Layer 1 退化(head = expr 的唯一 Rule);Layer 0 = Layer 1。

**当 head = `Rule.projection(...)` 纯 projection**(C56):Layer 0 root 自身无 atoms;直接 EDGE_SUPPORTS 到 expr 的 Rule 的 Layer 1 nodes。

### 8.6 Form 1 Composition:AND / OR / Join

#### 8.6.1 AND(Rule body 内 atoms 之间)

**Rule 内 atoms 都 AND**(C9 strict AND-only):
- NODE_CONCLUSION ← multiple EDGE_SUPPORTS ← multiple NODE_PREMISE
- **所有 NODE_PREMISE 都必须 satisfied**(v1 只 passed evidence,所以 N atoms = N premises 全部 satisfied)

#### 8.6.2 OR(RuleExpr `|` 组合)

**RuleExpr OR 在 evidence 体现为**:
- 多个 `Rule.conclusion` NODE_CONCLUSION 候选,**仅满足的那个**进 evidence(v1 passed-only)
- **未满足的 OR 分支** 在 v1 **不显示**(对齐 Rainbird "OR logic later conditions may never be evaluated or shown",§7.5 verified-mechanism)
- 多 OR 分支同时满足时:**v1 选第一个 satisfied**(passed 已足够;穷举所有可选 path → §14 D14 compound 范围)

**rationale**:OR 路径选择不属于 evidence 范围;evidence 只解释"这条成立 path 为什么成立"。

**Root visibility contract(C129)**:
- root `NODE_CONCLUSION.engine_meta.alternative_paths.mode` 必填 `"winning_path_only"`
- `omitted_count` 可知时填整数;未知时填 `None`
- renderer 可用该字段显示 "其他路径未展开" 的轻量提示,但 v1 不构造失败 / 未选分支节点

#### 8.6.3 Join(RuleExpr `.join(...)` port 联接)

**RuleExpr join 在 evidence 体现为**:
- 两个 RuleExpr 子 NODE_CONCLUSION 之间**无显式 join edge**(C30 join 是 Rule 间 binding constraint,不引入 evidence node)
- Join 的物质表现:**共享 NODE_SEED**(per §8.7 seed reuse)— 同 port 上的同一 fact 实例既支撑 Rule_a 的 atom 又支撑 Rule_b 的 atom
- 用户面 narrative:可在 root NODE_CONCLUSION.engine_meta.bindings 看到 join 后的 unified bindings

### 8.7 Seed Reuse Rule(同 fact 跨 atoms / 跨 Rules)

**锁定**:同一 fact(同一 asrt_id 或同一 literal value 或同一 derived fact)在 evidence 中**仅 1 个 NODE_SEED**,有**多个 incoming edges**。

**例**:`Rule_a` 的 atom_0 需要 `User(u-2)`;`Rule_b` 的 atom_3 也需要 `User(u-2)`(per Asrt#7):
```
Rule_a:atom_0 ──supports──┐
                          ↓
                      seed:ledger:Asrt#7  (单 NODE_SEED,多 incoming)
                          ↑
Rule_b:atom_3 ──supports──┘
```

**好处**:
- 减少冗余(N atoms 共用同 fact = 1 seed,非 N seeds)
- 自然形成 DAG(symbolic graph,reflects RuleExpr 内部 binding 共享)
- 渲染时 UI 可显示 "1 fact, used by N atoms"

**Phase C 实现**:orchestrator 维护 seed dedup table(`(source, identity_key) → node_id`);构造 evidence 时按 key 复用。

### 8.8 Inferred Intermediate Representation(双重身份)

**当 atom 匹配的事实来源于上游 Rule(非 Ledger)**:

```
upstream Rule_a (derives fact F)
    NODE_CONCLUSION  "conclusion:rule:Rule_a"  ─supports─> NODE_SEED "seed:inferred:Rule_a:F_digest"
                                                              ↑ supports
downstream Rule_b uses F as pred witness
    NODE_PREMISE "premise:Rule_b:atom_2"  ←supports─ NODE_SEED (above)
                                                              ↑ supports
                                              NODE_CONCLUSION "conclusion:rule:Rule_b"
```

**双重身份**:
- 对 Rule_a:它的 NODE_CONCLUSION 是 derivation 终点(通过 `EDGE_SUPPORTS` 链接到下游 NODE_SEED;**Form 1 仅 `EDGE_SUPPORTS`**,per C115)
- 对 Rule_b:它产生的 NODE_SEED 是 Rule_b 的 witness(`source="inferred_intermediate"`)
- **2 个 node:1 个 NODE_CONCLUSION(Rule_a 的)+ 1 个 NODE_SEED(Rule_b 视角的 witness)**;通过 derived_from_rule_id 字段链接

**EDGE_DERIVES 在 Form 1 不使用**(2026-05-19 锁定):
- Form 1(Souffle / native / ProbLog)inferred_intermediate 也走 `EDGE_SUPPORTS`(语义:"Rule_a 的 conclusion supports 下游 witness seed")
- `EDGE_DERIVES` 保留给 **Form 2 PyReason temporal**(跨 timestep state derivation)— 详 §8.11 / C115
- v1 设计简化:Form 1 evidence 单一 edge_kind(`EDGE_SUPPORTS`),便于 renderer / consumer 处理

**v1 简化**:若 Rule_a 在同一 expr 内 transparently 展开,evidence 树**完整展开**(NODE_CONCLUSION 也在树内);若 Rule_a 来自外部 view 物化(不在 expr 内),evidence 仅 NODE_SEED(referencing Rule_a 的 derivation in external scope)。

### 8.9 ProbLog Multi-Path DAG Enrichment

**单 path case**(典型,§4.13.2 Example 2):**与 §8.5 4 层结构同构**,仅 engine_meta 加 `raw_kind/bound/path_index=0/aggregation_rule=None`。

**多 path case**(同一 head 多种 derivation):
```
                NODE_CONCLUSION  "conclusion:head:{closed_head.id}"
                  engine_meta:
                    raw_kind="probabilistic"
                    bound=(0.85, 0.85)             # aggregate noisy-or 结果
                    aggregation_rule="noisy_or"
                    path_count=2
                       │
        ┌──────────────┼──────────────┐
        ↓                              ↓
  NODE_CONCLUSION                NODE_CONCLUSION
  "conclusion:rule:R1:p0"        "conclusion:rule:R1:p1"
  path_index=0                   path_index=1
  raw_kind="probabilistic"        raw_kind="probabilistic"
  bound=(0.7, 0.7)                bound=(0.5, 0.5)
       │                                │
   [premise/seed subtree 0]          [premise/seed subtree 1]
   (different witness facts)         (alternative derivation)
```

**关键 conventions**:
- 同一 Rule 的 multi-path:Layer 1 NODE_CONCLUSION 加 `path_index` suffix in node_id
- Root NODE_CONCLUSION 持 aggregate bound + aggregation_rule
- 每 path 自己的 sub-tree;witness 不必跨 path 共享(可独立 seed)
- aggregation_rule 数学计算 **deferred 到 §6.6 / §14 D15**

**v1 默认 single-path**;multi-path 当 ProbLog adapter 返回多 candidate 同 bindings 时触发(Phase C 检测)。

### 8.10 Aggregate Premise Topology(2026-05-19 补 — §4.5.4 reason schema 与 §8 topology 闭环)

> **缺口闭合**:§4.5.4 已锁 `aggregate_comparison` reason schema(数据形态),但 §8 4-layer topology 未明示 aggregate NODE_PREMISE 的 seed 取舍。本节锁 v1 aggregate premise 在 evidence tree 内的拓扑形态,**防 3 种实现 anti-pattern**:误当普通 atom 找单 seed / 完全不接 seeds / 展开所有 contributors。

#### 8.10.1 立场

- AggregateExpr 在 evidence 内 = **单 NODE_PREMISE,reason 携 aggregate envelope**(per C99 / C106 / C128)
- v1 **不展开** contributor facts 为 sub-`NODE_SEED`;contributors 通过 `{mode, count, handle}` envelope 标注存在性 + 数量,**不**列具体 fact 个体
- **边界明示**:v1 解释 aggregate result + comparison verdict;**不保证**展示 contributing facts 个体

#### 8.10.2 Aggregate NODE_PREMISE 拓扑形态(锁定)

以 `agg_sum(Order.amount where Order.buyer == u-2) > 1000` 为例:

```
parent NODE_CONCLUSION (containing Rule firing)
  ↑ EDGE_SUPPORTS
NODE_PREMISE  "premise:{atom_id}"
  atom_kind         不映射到 9 IR kinds(comparison atom kind 如 "gt");
                    aggregate-ness 在 reason.kind 表达
  reason:
    kind = "aggregate_comparison"           # per §4.5.4 / C106
    aggregate:
      aggregate_kind     = "sum"            # count / sum / min / max / mean
      filter_repr        = ["Order.buyer == u-2"]
      matched_count      = 10243            # view-projected snapshot count (C103)
      contributors       = {                # per C128
        mode  = "omitted_v1",
        count = 10243,                       # == matched_count(C128 invariant)
        handle = null,                        # v1 无 fetch
      }
      aggregate_result   = 1234567.89
      empty_set          = false
      no_value           = false
      error_kind         = null
    comparison:
      lhs_value          = 1234567.89
      rhs                = 1000
      op                 = ">"
      status             = "satisfied"

NODE_SEED 数量:0(v1 default;不展开)
EDGE_SUPPORTS:仅 1 个,指向 parent conclusion;无 outgoing 边到 seed
```

#### 8.10.3 拓扑差异 vs pred premise

| 维度 | pred NODE_PREMISE | aggregate NODE_PREMISE |
|---|---|---|
| 关联 NODE_SEED 数量 | 1(asrt_id witness)| **0**(v1 default)|
| reason 关键字段 | `matched_witness_asrt_id` 单值 | `aggregate.matched_count` 集合摘要 |
| 出度 `EDGE_SUPPORTS` 到 seed | 1 | 0 |
| 入 seed dedup table | ✓(共享 fact 合并)| ✗(无 sub-seed 可 dedup)|
| reason.kind | `comparison` | `aggregate_comparison` |

#### 8.10.4 v1 contributor mode 锁定(C128 协同)

| `mode` | v1 状态 | 形态 |
|---|---|---|
| `omitted_v1` | **v1 唯一合法 default** | `count` 必填 = matched_count;`handle = null` |
| `lazy` | **v1.x deferred**(详 §14 D18)| `count` + `handle` 非 null;evidence tree 形态不变,handle 供后续 fetch |
| `embedded` | **future v2+**(可能不实现)| 展开 NODE_SEED × matched_count;**大集合风险大**,需 size cap |

**v1 严格 invariant**:
- 仅 `mode="omitted_v1"` 合法;其他 mode → `EvidenceValidationError`(Step 7 gate)
- `contributors.count == matched_count`(双向);mismatch → reject(C128)
- `handle == null`(v1);非 null → reject(防伪 v1.x mode)

#### 8.10.5 matched_count snapshot invariant(C103 协同)

- `matched_count` = **view-projected snapshot count**(项目 view_facts 时的 count)
- 来源:Step 3 evidence context prep 调 `project_view_facts(...)` 时算并冻结
- **禁止** Step 6 reason extraction 重查 / 重计数(防 ledger 漂移导致 evidence inconsistency)
- 与 `EvaluateResult.view_snapshot_digest` 绑定:同 snapshot 同 count(跨进程 deterministic)
- Phase C 实现:matched_count 在 context object 中 frozen,Step 6 仅消费

#### 8.10.6 v1 explanation 边界明示

| 维度 | v1 aggregate evidence | v1 不做(deferred)|
|---|---|---|
| **量值解释**(aggregate result)| ✓ 显示 1234567.89 | — |
| **Comparison verdict**(satisfied / violated)| ✓ | — |
| **Filter 条件可读**(filter_repr)| ✓ string list | — |
| **Empty set / no value / error 状态** | ✓ explicit flags | — |
| **Contributor facts 个体展示** | ✗ | v1.x lazy(D18)/ future embedded |
| **Per-contributor verdict / breakdown** | ✗ | aggregate 仅集合属性,**非 v2** |
| **Aggregate decomposition / attribution**(哪 contributor 最重要)| ✗ | v2+ Shapley / impact(§14 D7)|

#### 8.10.7 与 §4.5.4 / §8.5 的闭环关系

- **§4.5.4** = aggregate **reason 数据 schema**(字段类型 / 必填 / invariants)
- **§8.10**(本节)= aggregate **evidence tree 拓扑形态**(NODE_PREMISE 数量 / NODE_SEED 关系 / edge 出入度)
- **§8.5** = Form 1 单 path tree(pred premise 主导)— aggregate premise 是 §8.5 4-layer 内的**变体**,**不是新 layer**
- 闭环结果:reason schema(§4.5.4)+ topology constraint(§8.10)= aggregate evidence v1 完整定义,**实现无歧义**

#### 8.10.8 完整示例:`sum(order.amount where order.user_id == u.id) > 1000`

**用户面 authoring**:
```python
with vars("u", "o") as (u, o):
    big_buyer = Rule(
        id="big_buyer",
        desc="user %user is a big buyer",
        where=[
            User(u),
            agg_sum(Order(o).amount, where=[Order(o).user_id == User(u).id]) > 1000,
        ],
        ports={"user": u},
    )
```

**evaluate → row → explain**(假设 user `u-2` 有 10243 个 Order,总和 1234567.89):
```python
result = fg.eval.evaluate(big_buyer, head=Rule.projection("user"), engine="souffle")
# result.rows[0]:row_id="row-1", claim=Claim(...), bindings={"user": "u-2"}, ...

explanation = result[0].explain()
# explanation.evidence: EvidenceGraph(per below)
```

**EvidenceGraph 形态**(关键 nodes / edges):

```text
NODE_CONCLUSION  "conclusion:head:big_buyer:closed:row-1"   [root]
  engine_meta:
    rule_id="big_buyer", is_head=true,
    explained_claim_ref={row_id="row-1", evidence_ref_id="ref:...", ...},
    bindings={"user": "u-2"}
    
  ↑ EDGE_SUPPORTS
  
NODE_CONCLUSION  "conclusion:rule:big_buyer"                [Layer 1 — single Rule firing]
  engine_meta: rule_id="big_buyer", is_head=false, bindings={"user": "u-2"}
  
  ↑ EDGE_SUPPORTS (× 2;Rule 内 2 atoms)
  
┌─────────────────────────────────────────────────────────────┐
│ NODE_PREMISE  "premise:big_buyer:atom_0"   [User(u) pred]   │
│   atom_kind="pred"                                          │
│   reason.kind="comparison"                                  │
│   reason.matched_witness_asrt_id="Asrt#100"                 │
│   reason.fact_tuple=("u-2",)                                │
│                                                             │
│   ↑ EDGE_SUPPORTS                                           │
│   NODE_SEED "seed:ledger:Asrt#100"                          │
│     source="ledger_assertion", asrt_id="Asrt#100",          │
│     pred_id="User", fact_tuple=("u-2",)                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ NODE_PREMISE  "premise:big_buyer:atom_1"   [aggregate > 1000]│
│   atom_kind="gt"                                            │
│   reason.kind="aggregate_comparison"   ← §4.5.4              │
│   reason.aggregate:                                         │
│     aggregate_kind="sum"                                    │
│     target_repr="Order(o).amount"                           │
│     filter_repr=["Order(o).user_id == u-2.id"]              │
│     matched_count=10243                                     │
│     contributors={                                          │
│       mode="omitted_v1",   ← C128 / C136 v1 锁定             │
│       count=10243,         ← == matched_count(双向 invariant)│
│       handle=null,                                          │
│     }                                                       │
│     aggregate_result=1234567.89                             │
│     empty_set=false, no_value=false, error_kind=null        │
│   reason.comparison:                                        │
│     lhs_value=1234567.89, rhs=1000, op=">",                 │
│     status="satisfied"                                      │
│                                                             │
│   ❌ NO outgoing EDGE_SUPPORTS to NODE_SEED                  │
│   ❌ NO contributor NODE_SEED nodes for 10243 orders        │
│   ❌ NOT entered in seed dedup table                        │
└─────────────────────────────────────────────────────────────┘
```

**关键 contrast(pred premise vs aggregate premise)**:

| 维度 | atom_0 (pred `User(u)`) | atom_1 (aggregate `sum>1000`)|
|---|---|---|
| atom_kind | `pred` | `gt`(comparison atom,RHS 含 AggregateExpr)|
| reason.kind | `comparison` | `aggregate_comparison` |
| outgoing EDGE_SUPPORTS | 1(→ seed Asrt#100)| **0** |
| NODE_SEED 关联 | 1 个(asrt_id witness)| **0** |
| 进 seed dedup table | ✓ | ✗ |
| matched_count 用法 | N/A(单 witness)| **`= contributors.count`**(10243)|
| 用户面看到 | "User(u-2) 来自 Asrt#100" | "sum=1234567.89 over 10243 matched orders > 1000 ✓" |

**evidence 大小估计**:此例 4 nodes(1 head conclusion + 1 rule firing + 2 premises)+ 1 seed = 5 nodes。**若全展开 10243 contributors → 10248 nodes,~1MB+ JSON**,违反 v1 size budget(C136 v1 `mode="omitted_v1"` 避免此)。

### 8.11 Form 2 PyReason Temporal Topology(sketch + 主体 deferred)

> **本节状态**:**sketch only**;详细 Form 2 设计独立推进(详 §14 D11)。

**Form 2 与 Form 1 关键差异**(基于 shipped `audit/evidence_graph.py:_render_timeline_layout`):

| 维度 | Form 1(Souffle/native/ProbLog)| Form 2(PyReason)|
|---|---|---|
| `layout_hint` | `LAYOUT_TREE` | **`LAYOUT_TIMELINE`** |
| 主要 EDGE kinds | `EDGE_SUPPORTS` only | `EDGE_SUPPORTS` + **`EDGE_DERIVES`** + **`EDGE_UPDATES`** |
| 时间维度 | absent | NODE.timestamp 字段(shipped `audit/evidence_graph.py:33`)|
| 状态更新 | absent | bound update over timesteps(EDGE_UPDATES) |
| typical node 配置 | conclusion + premise + seed | conclusion / atom 在每个 timestep + state update events |

**Form 2 evidence tree shape sketch**:

```
LAYOUT_TIMELINE grid:
  rows = component(rule_id / atom_id / 等)
  cols = timestep(0, 1, 2, ...)
  cells = NODE_CONCLUSION / NODE_PREMISE / NODE_SEED at (component, timestep)
  edges:
    EDGE_SUPPORTS:  premise → conclusion(同时间步)
    EDGE_DERIVES:   state derived from earlier state(跨时间步,e.g., "popular_at_t+1 derives popular_at_t + Friends + owns")
    EDGE_UPDATES:   bound mutation(同 component 跨时间步)
```

**详细 Form 2 schema**(timestep / time_window / bound update semantics)**完整 deferred** 到独立 Form 2 设计文档(详 §14 D11)。

### 8.12 完整 JSON Example(canonical reference)

**Example**:Souffle Form 1,Rule = `active_us`(同 §4.13.1):

```json
{
  "graph_id": "souffle:run-1:abc123",
  "engine": "souffle",
  "root_node_id": "conclusion:head:active_us_closed_run-1:abc123",
  "support_kind": "passed",
  "layout_hint": "tree",
  "metadata": {
    "schema_version": "1.0",
    "evaluated_at": "2026-05-19T12:00:00Z",
    "engine": "souffle",
    "engine_version": "souffle-2.4.1",
    "adapter_version": "factpy-kernel-0.1.0",
    "rule_content_digest": "sha256:abc...",
    "closed_head_content_digest": "sha256:def...",
    "expr_digest": "sha256:expr...",
    "rule_set_digest": "sha256:ruleset...",
    "view_snapshot_digest": "sha256:view...",
    "semantics_digest": null,
    "result_id": "result-1",
    "row_id": "row-2",
    "claim_digest": "sha256:claim...",
    "evidence_ref_id": "ref:abc..."
  },
  "nodes": [
    {
      "node_id": "conclusion:head:active_us_closed_run-1:abc123",
      "node_kind": "conclusion",
      "component": "active_us",
      "label": "user u-2 is active in US",
      "value_summary": "",
      "engine_meta": {
        "rule_id": "active_us",
        "is_head": true,
        "bindings": {"user": "u-2"},
        "content_digest": "sha256:def...",
        "raw_kind": null,
        "bound": null,
        "explained_claim_ref": {
          "row_id": "row-2",
          "evidence_ref_id": "ref:abc...",
          "claim_digest": "sha256:claim...",
          "claim_repr_cache": "active_user_in_US(user='u-2')"
        },
        "quantitative_explanation": {
          "mode": "engine_reported",
          "decomposition": "not_available_v1"
        },
        "alternative_paths": {
          "mode": "winning_path_only",
          "omitted_count": null
        }
      }
    },
    {
      "node_id": "premise:active_us:atom_0",
      "node_kind": "premise",
      "component": "active_us:atom_0",
      "label": "u-2.status == 'active'",
      "value_summary": "satisfied",
      "engine_meta": {
        "atom_id": "active_us:atom_0",
        "atom_kind": "eq",
        "atom_index": 0,
        "parent_rule_id": "active_us",
        "reason": {
          "kind": "comparison",
          "compared_values": ["active", "active"],
          "operator": "eq"
        }
      }
    },
    {
      "node_id": "premise:active_us:atom_1",
      "node_kind": "premise",
      "component": "active_us:atom_1",
      "label": "u-2.region == 'US'",
      "value_summary": "satisfied",
      "engine_meta": {
        "atom_id": "active_us:atom_1",
        "atom_kind": "eq",
        "atom_index": 1,
        "parent_rule_id": "active_us",
        "reason": {
          "kind": "comparison",
          "compared_values": ["US", "US"],
          "operator": "eq"
        }
      }
    },
    {
      "node_id": "seed:ledger:Asrt#42",
      "node_kind": "seed",
      "component": "ledger:Asrt#42",
      "label": "User(u-2).status = active",
      "value_summary": "ledger:Asrt#42",
      "engine_meta": {
        "source": "ledger_assertion",
        "asrt_id": "Asrt#42",
        "pred_id": "user_status",
        "fact_tuple": ["u-2", "active"]
      }
    },
    {
      "node_id": "seed:ledger:Asrt#84",
      "node_kind": "seed",
      "component": "ledger:Asrt#84",
      "label": "User(u-2).region = US",
      "value_summary": "ledger:Asrt#84",
      "engine_meta": {
        "source": "ledger_assertion",
        "asrt_id": "Asrt#84",
        "pred_id": "user_region",
        "fact_tuple": ["u-2", "US"]
      }
    }
  ],
  "edges": [
    {
      "edge_id": "edge:premise:active_us:atom_0->conclusion:head:active_us_closed_run-1:abc123",
      "from_node_id": "premise:active_us:atom_0",
      "to_node_id": "conclusion:head:active_us_closed_run-1:abc123",
      "edge_kind": "supports",
      "rule_label": "active_us",
      "engine_meta": {"rule_id": "active_us"}
    },
    {
      "edge_id": "edge:premise:active_us:atom_1->conclusion:head:active_us_closed_run-1:abc123",
      "from_node_id": "premise:active_us:atom_1",
      "to_node_id": "conclusion:head:active_us_closed_run-1:abc123",
      "edge_kind": "supports",
      "rule_label": "active_us",
      "engine_meta": {"rule_id": "active_us"}
    },
    {
      "edge_id": "edge:seed:ledger:Asrt#42->premise:active_us:atom_0",
      "from_node_id": "seed:ledger:Asrt#42",
      "to_node_id": "premise:active_us:atom_0",
      "edge_kind": "supports",
      "engine_meta": {}
    },
    {
      "edge_id": "edge:seed:ledger:Asrt#84->premise:active_us:atom_1",
      "from_node_id": "seed:ledger:Asrt#84",
      "to_node_id": "premise:active_us:atom_1",
      "edge_kind": "supports",
      "engine_meta": {}
    }
  ]
}
```

**典型 size**:此例 ~1.5KB;真实场景 evidence 多在 5-20KB 范围;deep multi-rule expr 上限 ~100KB(用户超出需 §14 D14 lazy fetch)。

### 8.13 §8 设计承诺 Commitments(C114-C119 + C136)

| # | 承诺 |
|---|---|
| C114 | **EvidenceGraph envelope 沿用 shipped `audit/evidence_graph.py:60`**;Form 1 用 `LAYOUT_TREE`,Form 2 用 `LAYOUT_TIMELINE`;`graph_id` 命名 `"<engine>:<run_id>:<digest_short>"` deterministic 跨进程稳定(详 §8.2)|
| C115 | **Edge direction contract**:`from_node_id` = premise / child / 下游,`to_node_id` = conclusion / parent / 上游;读法 "from supports to";Form 1 仅 `EDGE_SUPPORTS`;Form 2 加 `EDGE_DERIVES` / `EDGE_UPDATES`(详 §8.3)|
| C116 | **node_id / edge_id 命名 scheme 锁定**(详 §8.4):`conclusion:head:{...}` / `conclusion:rule:{...}:p{path_index}` / `premise:{atom_id}` / `seed:{source}:{key}` / `edge:{from}->{to}`;deterministic + per node_kind / source 显式编码 |
| C117 | **Form 1 4-layer topology**:Layer 0 root NODE_CONCLUSION head / Layer 1 NODE_CONCLUSION × Rule firing / Layer 2 NODE_PREMISE × atoms / Layer 3 NODE_SEED × witness;AND-only 内部组合(C9);OR / Join 通过 RuleExpr 层 vs evidence 层 mapping 锁定(详 §8.5 / §8.6);v1 OR 不展示未满足分支(对齐 Rainbird),但 root `alternative_paths` 必须声明 winning-path-only 边界(C129)|
| C118 | **Seed reuse rule**:同一 fact(asrt_id / literal / inferred fact)**仅 1 个 NODE_SEED**,**多 incoming edges**(详 §8.7);Phase C orchestrator 维护 seed dedup table(`(source, identity_key) → node_id`)|
| C119 | **ProbLog multi-path DAG enrichment**(详 §8.9):同 head 多 derivation 表达为 Layer 1 多 NODE_CONCLUSION + `path_index` suffix;root NODE_CONCLUSION 持 aggregate `bound` + `aggregation_rule`;aggregation 数学 deferred 至 §6.6 / §14 D15;**v1 默认 single-path**,multi-path 仅 ProbLog adapter 返回多 candidate 同 bindings 时触发 |
| **C136** | **(Phase B-6 补 2026-05-19)** **Aggregate Premise Topology**(详 §8.10,§4.5.4 reason schema 与 §8 topology 闭环):AggregateExpr 在 evidence 内 = **单 NODE_PREMISE + 0 NODE_SEED**(v1 default);v1 仅合法 `contributors.mode="omitted_v1"`,`count == matched_count`,`handle = null`;**禁止**展开 contributor facts 为 sub-NODE_SEED(v1.x lazy / future embedded deferred);`matched_count` 是 view-projected snapshot count(C103),Step 3 frozen,Step 6 不重查;**防 3 anti-pattern**:误当普通 atom 找单 seed / 完全不接 seeds / 展开所有 contributors |

### 8.14 §8 显式 deferred 项

| 项 | 触发条件 |
|---|---|
| **Form 2 PyReason temporal 完整 schema**(timestep / time_window / bound update semantics)| Form 2 独立设计文档(§14 D11)|
| **ProbLog aggregation_rule 数学**(noisy_or / SDD / product)| §6.6 / §14 D15 |
| **OR 全分支显示**(未满足 path 也展示)| §14 D14 compound case |
| **Inferred intermediate cross-expr 模式**(上游 Rule 不在 expr 内时的 NODE_SEED 表达)| 用户外部 view 物化场景 |
| **Lazy node loading / pagination**(大型 evidence > 100KB)| §14 D18 |

---

## 9. Failure-Side Handling(C81 + C125 已锁定)

### 9.1 锁定决策(C81 修订)

- `status == "passed"` → `evidence: EvidenceGraph` 非 None
- `status` 其余 3 态(`failed` / `unsupported` / `invalid_request`)→ `evidence = None`

详 §13.2.4 C81 完整文本。

### 9.2 修订理由

`DiagnoseAtomLocator` 单点信息是 **lossy abstraction**(详 `diagnose_runtime.py:220-257` 6 个 caveat):
1. multi-env 视角下"失败 atom"取决于 envs 走到何处,非"真正问题 atom"
2. 不同 query binding 同 Rule 报不同 atom
3. multi-branch 时只报"走得最远"那条,其他丢失
4. `attempted_binding` 是字典序代表,非 informative
5. schema 不支持 multi-mode 失败表达(`list[FailureMode]`)
6. nested atoms(NAF / compound)退化到 top-level

**大事实库下 single-locator 启发式不稳定**(可能存在成百上千失败 candidate,任选其一作"答案"是 arbitrary)。explain 不在 failed 态承载 lossy 信息,避免误导用户以为 atom_k 是"真正问题"。

### 9.3 与 Rainbird 失败 404 对比

| 系统 | failed 时返回 |
|---|---|
| Rainbird | 404 evidence not found |
| **本设计 v1** | `Explanation(status="failed", evidence=None, ...)` + `failure_class` / `checked_scope` / `suggested_next_steps` envelope |

两者都不提供 atom-level hint;我们的优势是**显式 status 信号 + failure envelope** 取代 HTTP 404,同时保持 business failure 与 technical errors 分离(详主文档 §5.8.3 / C125)。

### 9.4 失败定位的 v2+ 路径

- `fg.diagnose` SDK 表面 v1 不公开
- v2+ 设计 top-down goal-regression / why-not 算法(详 §14 D1/D2)
- 触发条件:用户出现明确"为什么我这条 binding 推不出来"诉求 + 大事实库下 single-locator 启发式不稳定

### 9.5 Failure envelope(C125,Wave 2 #3)

`status="failed"` 时:
- `failure_class` 必填 5-enum:`no_matching_row` / `closed_head_false` / `stale_row` / `row_not_in_result` / `insufficient_closed_bindings`
- `checked_scope` 填 digest 对比信息(result / row / claim / closed_head / view / semantics)
- `suggested_next_steps` 填 lightweight hint tuple
- `evidence` 仍为 `None`

`status="unsupported"` / `status="invalid_request"` 时:
- `failure_class = None`
- 技术原因进入 `errors`
- 不混入 business failed 状态

**非目标**:本 envelope **不是** DiagnoseAtomLocator,不输出 atom_id / attempted_binding / single failing atom。

---

## 10. Audit Channel(v1)

> **本节状态**:Phase B design lock(2026-05-27 / T6)。本节定义 v1
> audit channel 的**sessionless**契约:一个 `EvaluateResult` envelope、一个
> row-bound `Explanation`、以及可 roundtrip 的 `EvidenceGraph.metadata`
> 共同构成 v1 audit record。它不是 Rainbird `/interactions/` session log,
> 也不是 cryptographic provenance channel。

### 10.1 v1 audit channel 的三层

| 层 | 载体 | v1 职责 | 非职责 |
|---|---|---|---|
| **Result envelope** | `EvaluateResult` | 记录本次 evaluate run 的 immutable identity、engine、schema/view/semantics digest、rows 与 result digest | 不记录用户 session transcript;不保证 append-only log |
| **Row explanation** | `Explanation` | 把单个 `EvaluateRow` 的 passed/failed/unsupported/invalid_request 状态、claim、carrier、checked scope、errors/warnings 归一到一个 envelope | 不把 failed 状态伪装成 partial evidence graph |
| **Durable graph metadata** | `EvidenceGraph.metadata` | 对 passed row 的 graph copy 单一 row/result context,供 audit package / renderer / JSON roundtrip 稳定消费 | 不承诺完整 derivation topology;不暴露 match witnesses |

v1 的重要取舍是 **sessionless**:audit record 是 evaluation result 的 deterministic
envelope,而非用户交互过程的 transcript。Rainbird `/interactions/` 风格的 session
channel 留到 D8。

### 10.2 Envelope-level audit fields

这些字段属于 `EvaluateResult` / `Explanation` envelope,不是全部复制进
`EvidenceGraph.metadata`:

| 字段 | 来源 | 必需性 | 用途 |
|---|---|---|---|
| `result_id` | `EvaluateResult.result_id` | required | result envelope primary id;也复制到 graph metadata |
| `run_id` | `EvaluateResult.run_id` | required | single evaluate invocation id;**当前不复制到 graph metadata** |
| `evaluated_at` | `EvaluateResult.evaluated_at` | required | evaluate timestamp;复制为 JSON-safe metadata value |
| `result_digest` | `EvaluateResult.result_digest` | required | complete result envelope digest;复制到 graph metadata |
| `head` | `EvaluateResult.head` / `Explanation.claim` | required | evaluate-side projection target and row claim context |
| `engine` | `EvaluateResult.engine` | required | engine identity;复制到 graph metadata |
| `engine_version` | `EvaluateResult.engine_version` | optional | engine version;复制到 graph metadata |
| `adapter_version` | `EvaluateResult.adapter_version` | optional | adapter version;复制到 graph metadata |
| `expr_digest` | `EvaluateResult.expr_digest` | required | expression/template digest;复制到 graph metadata |
| `rule_set_digest` | `EvaluateResult.rule_set_digest` | required | rule set digest;复制到 graph metadata |
| `view_snapshot_digest` | `EvaluateResult.view_snapshot_digest` | required | db/view snapshot bridge(T11.2);复制到 graph metadata |
| `semantics_digest` | `EvaluateResult.semantics_digest` | optional | semantics profile digest;复制到 graph metadata |

**设计锁**:`run_id` 保持 envelope-level audit 字段。T6 不要求把它复制进
`EvidenceGraph.metadata`;若 future consumer 需要 graph-only run grouping,必须走新的
blueprint 明确激活。

### 10.3 `EvidenceGraph.metadata` v1 字段表

当前 passed row graph copy 以下单一 row/result context:

| 字段 | 来源 | 说明 |
|---|---|---|
| `result_id` | `EvaluateResult.result_id` | graph 所属 result |
| `row_id` | `EvaluateRow.row_id` | explained row |
| `evidence_ref_id` | `EvaluateRow.evidence_ref.ref_id` | row evidence reference id |
| `claim_digest` | `EvaluateRow.claim.digest` | row claim digest |
| `closed_head_digest` | `EvaluateRow.evidence_ref.closed_head_digest` | closed head digest |
| `expr_digest` | `EvaluateResult.expr_digest` | evaluated expression digest |
| `rule_set_digest` | `EvaluateResult.rule_set_digest` | evaluated rule set digest |
| `view_snapshot_digest` | `EvaluateResult.view_snapshot_digest` | db/view snapshot digest bridge |
| `semantics_digest` | `EvaluateResult.semantics_digest` | semantics profile digest or `None` |
| `result_digest` | `EvaluateResult.result_digest` | full result digest |
| `engine` | `EvaluateResult.engine` | engine id |
| `engine_version` | `EvaluateResult.engine_version` | engine version or `None` |
| `adapter_version` | `EvaluateResult.adapter_version` | adapter version or `None` |
| `evaluated_at` | `EvaluateResult.evaluated_at` | JSON-safe timestamp value |

T8 implementation **不得 silently drop** any v1 metadata field above. Adding a new
metadata key is allowed only when a T8/T10 blueprint declares producer, consumer,
and backward compatibility impact.

### 10.4 Validation and roundtrip contract

v1 audit validation has two layers:

1. **DTO construction validation**: `EvidenceGraph` rejects unsupported
   `layout_hint`, duplicate node/edge ids, missing root node, edge endpoints not
   present in `nodes`, and cycles.
2. **Envelope sufficiency validation**: row-sourced passed graphs must include
   enough metadata to connect back to `EvaluateResult`, `EvaluateRow`, claim,
   closed head, expression, rule set, view snapshot, semantics, engine, and
   result digest.

Serialization uses `evidence_graph_to_dict(...)` / `evidence_graph_from_dict(...)`.
The v1 roundtrip contract is:

- dict roundtrip preserves graph identity, node/edge ids, layout hint, support
  kind, and metadata values after JSON-safe normalization;
- roundtrip must re-run the constructor validation above;
- invalid graph rows fail closed with a validation error; callers must not render
  partially reconstructed graphs.

### 10.5 Immutability / signature stance

v1 relies on:

- frozen DTO dataclasses;
- shallow-frozen `engine_meta` and `metadata` mappings;
- deterministic ids/digests carried by `EvaluateResult` / `EvaluateRow`;
- JSON roundtrip validation at audit/package boundaries.

v1 **does not** provide:

- cryptographic signature over evidence graphs;
- append-only session/channel log;
- tamper-evident storage ledger for evidence exports;
- per-fact ACL redaction channel.

These remain explicit deferred items:session log D8, per-fact ACL D10, and
signature/tamper-evident channel v2+ governance.

### 10.6 Audit package boundary

The audit package may persist or export `EvidenceGraph` as a durable graph
record. That durable graph is:

- an engine-bound provenance artifact normalized to the shared renderer shape;
- allowed to preserve engine truth in `engine_meta` without flattening it;
- optional for engines/features that do not yet expose graph provenance;
- consumed by reference renderers and audit readers, not by business logic.

The audit package must not treat absence of a rich graph as failed business
truth. For v1, minimal passed row graphs remain valid when they satisfy DTO and
metadata validation.

### 10.7 v2+ deferred audit channels

| Deferred | Trigger | Boundary |
|---|---|---|
| Session log channel(Rainbird `/interactions/` equivalent) | user-facing interactive diagnostic flows need replay | separate session/audit design;not implicit in `EvidenceGraph.metadata` |
| Graph signature / tamper-evident envelope | regulated audit or external artifact verification demand | new signature fields + key governance blueprint |
| Per-fact ACL / redaction metadata | multi-tenant service deployment | security/service design;not part of local DTO shape |
| Graph-only run grouping | consumers need `run_id` without `EvaluateResult` envelope | explicit metadata extension blueprint |

---

## 11. Rendering(沿用 shipped audit/evidence_graph.py)

> **本节状态**:Phase B design lock(2026-05-27 / T6)。本节定义
> `audit.evidence_graph` reference renderer 的边界。它是 debug / audit
> inspection utility,不是 product UI contract。Product UI 可以使用同一
> `EvidenceGraph` DTO,但不继承 reference renderer 的 visual layout 责任。

### 11.1 Renderer 分层

| 层 | 入口 | 职责 | 非职责 |
|---|---|---|---|
| **Reference renderer** | `render_evidence_graph_html(graph)` | 生成 standalone HTML fragment;用于 audit package、debug、doc examples、developer inspection | 不提供 full page shell;不承诺 product-grade interaction/virtualization |
| **Roundtrip helpers** | `evidence_graph_to_dict(...)` / `evidence_graph_from_dict(...)` | JSON-safe durable / test / package boundary | 不执行 semantic enrichment;不补丢失的 engine provenance |
| **Product UI** | downstream custom renderer | 可按产品需求做 folding、search、progressive loading、accessibility、visual design | 不得改变 graph truth;不把 UI grouping 写回 DTO |

Reference renderer 的目标是 **truthful and boring**:只展示 graph 已有的 nodes,
edges,metadata,engine_meta。它不推断缺失 provenance、不生成新 reasoning、不把 failed
business 状态展示成 partial graph。

### 11.2 Layout mode matrix

| `layout_hint` | 推荐用途 | 适合数据 | 不适合数据 | v1 status |
|---|---|---|---|---|
| `tree` | 默认 derivation / support view | native / Souffle-style acyclic support tree;single root row explanation;minimal row graph | time-step dense evidence;many repeated component updates | shipped |
| `timeline` | temporal / update-oriented view | PyReason Form 2 future evidence;node timestamp present;component repeated over time | non-temporal proof tree with no timestamps;deep dependency inspection | shipped renderer,Form 2 producer deferred |

若 producer 没有强理由,默认 `layout_hint="tree"`。`timeline` 是可用 renderer mode,但
timeline 的 rich producer contract 仍等 PyReason Form 2 evidence cycle。

### 11.3 Tree layout contract

Tree layout:

- starts at `root_node_id`;
- follows the current edge convention where incoming edges to a node are rendered
  as supporting branches;
- sorts child/support edges deterministically by renderer sort key;
- renders node label, component, value summary, and relevant engine metadata;
- must preserve DAG truth:shared support nodes may converge in graph identity even
  if the simple HTML fragment repeats visual branches for readability.

Tree renderer error handling:

- invalid `layout_hint` is rejected by DTO construction before rendering;
- missing root / duplicate ids / cycles are DTO validation errors, not renderer
  warnings;
- a valid graph with one root and zero edges is a normal minimal evidence graph.

### 11.4 Timeline layout contract

Timeline layout:

- groups cards by `timestamp` / component when timestamps are present;
- may render `timestamp=None` nodes in a fallback column/bucket;
- renders incoming-edge annotation when edges exist;
- is intended for temporal engine evidence, not as a general proof-tree
  replacement.

Timeline renderer is allowed to be sparse. Absence of timestamps is not a graph
validation error; it only reduces timeline readability. Product UI may choose to
fallback to tree layout when timeline data is too sparse.

### 11.5 Empty, minimal, and invalid graphs

| Case | Reference renderer behavior | Product UI guidance |
|---|---|---|
| **Minimal valid graph**(1 node,0 edges) | render a single-node graph | treat as successful but low-detail evidence |
| **Empty graph**(0 nodes) | impossible under DTO validation because `root_node_id` must exist | show validation error if encountered from untrusted external JSON |
| **Invalid graph**(duplicate ids,missing endpoint,cycle) | constructor / `from_dict` raises before rendering | do not attempt partial render;show diagnostic error |
| **Unsupported explanation**(`evidence=None`) | no renderer call | show `Explanation.errors` / unsupported state instead |

Reference renderer must not invent placeholder nodes to make invalid input
look valid.

### 11.6 Large graph guidance

No shipped runtime threshold exists today. T6 defines the reference renderer
guideline:

- **large** = more than `250` nodes or more than `500` edges;
- reference renderer may emit a warning/banner or metadata note before rendering;
- reference renderer should not silently truncate;
- reference renderer should not refuse a graph solely because it is large unless
  the host environment imposes resource limits;
- product UI may set stricter thresholds and should prefer custom folding,
  search, progressive disclosure, or virtualization.

This is design guidance, not a new DTO invariant. T8/T9 may tune threshold
numbers if implementation evidence shows different practical limits.

### 11.7 JSON roundtrip and renderer inputs

Rendering should accept an already constructed `EvidenceGraph`. Durable package
or external JSON input should first pass through `evidence_graph_from_dict(...)`,
which reruns DTO validation. The safe path is:

```text
external/durable row -> evidence_graph_from_dict(...) -> render_evidence_graph_html(...)
```

Do not render unvalidated dicts directly.

### 11.8 Custom UI obligations

Custom renderers may choose any UI shape, but they must preserve these graph
truth boundaries:

- `graph_id`, `root_node_id`, node ids, and edge ids remain identifiers, not
  display labels;
- `node_kind` / `edge_kind` enums retain semantic meaning;
- `engine_meta` remains namespaced engine detail;do not flatten engine-specific
  keys into cross-engine guarantees;
- `metadata` remains audit context, not user-facing business copy;
- UI grouping/folding/search state is view state and must not be written back
  into the `EvidenceGraph` DTO.

This keeps the Rainbird-aligned product stance:we provide a trustworthy evidence
carrier and a reference visualization, while applications own their product UI.

---

## 12. Rainbird 对照下的产品边界声明(Product Boundary Declaration)

> **本节状态**:Phase B-6 落定 2026-05-19。**§12 不是一份简单"差异矩阵",而是"对照 Rainbird 把 v1 evidence service 的产品边界讲清楚"**:对齐什么 / 有意不同什么 / 哪里超出 / 哪里不覆盖 / 给用户什么承诺。这层声明把前 §1-§11 的设计决策**收束为用户面可读的 expectation contract**。

### 12.1 对齐点(Rainbird-aligned mental model)

我们对 Rainbird 的核心心智**完全采纳**(详 §1.1 / §2.3):

| 对齐维度 | Rainbird | 本设计 v1 |
|---|---|---|
| **fact/claim-centric explanation** | factID → fact → explain | `row.claim` → `row.explain()`(Wave 1 row-centric API,C130)|
| **success-side evidence tree** | passed fact 才有 proof tree;failed 是 404 | `status="passed"` 才构造 EvidenceGraph(C81 / C132)|
| **row / fact 作为解释入口** | result returns factID,client 拿 ID 调 explain | `result[i]` returns live row;`row.explain()` 直接产 Explanation |
| **source / provenance 可渲染** | source taxonomy(6-enum)+ color coding | source 3-enum(C107)+ color coding(C109)|
| **rule firing + premise + seed 三层心智** | fact → rule.conditions[] → child factIDs | NODE_CONCLUSION → NODE_PREMISE → NODE_SEED 4-layer topology(C117)|

**总结**:在 evidence service 的**用户面心智**上,我们**与 Rainbird 同构**;差异仅在内部 schema 严格度与 Python OOP 表达。

### 12.2 有意不同点(Intentional Divergences)

5 个**故意**与 Rainbird 不同的设计决策(非疏忽,非未来收回):

| 维度 | Rainbird | 本设计 v1 | 决策理由 |
|---|---|---|---|
| **API 形态** | HTTP-style `GET /evidence/{factID}/{sessionID}` | **Python OOP `row.explain()`**(C130) | Python SDK 用户基础;OOP 比 procedural 更自然;sessionless |
| **EvidenceGraph schema** | free-form(SDK 是 lossy wrapper,详 §1 调研报告 2.4)| **contract-strict schema**(§4 / C82-C89 + C124 contract vs debug 分层) | 双写漂移防护;Phase C validator 强校验;evidence 是 audit artifact 不是 ad-hoc dict |
| **NAF 语义位置** | `synthesis_naf` 作 fact source(SDK 暗示"有一条负事实")| **NAF 入 NODE_PREMISE.reason.naf**(C121);**不**进 NODE_SEED | absence ≠ fact;NAF 是闭世界证明状态,不是 fact source |
| **Aggregation 展开度** | `sumObjects` / `countRelationshipInstances` 等 list functions 隐式展开 contributing facts(SDK 但 UI 不明确) | **count-only envelope**(C128 / C136):`{mode="omitted_v1", count, handle=null}`;**不**展开 contributor seeds | 真实业务 aggregate 常达 10k+ facts,展开 evidence 爆 MB+;v1 简洁优先 |
| **Failure 表达** | 404 evidence not found;`/interactions/` 给 session chronology | **`status="failed"` + envelope diagnostic**(C125):failure_class 5-enum + checked_scope + suggested_next_steps | 比 404 更结构化;比 DiagnoseAtomLocator 单点 hint 更诚实(不伪 atom-level 精度) |

**总结**:这 5 处不同**是产品设计抉择,不是 Rainbird 妥协**。每处都有明确理由,Phase C 实现需理解。

### 12.3 我们 strictly stronger than Rainbird(6 项产品级 strict superset)

| # | 维度 | 本设计 v1 优势 | Rainbird 对应 |
|---|---|---|---|
| 1 | **Audit metadata 双驻 + reproducibility** | EvidenceGraph.metadata 15 必填 fields(C123 + C135);view_snapshot_digest / rule_set_digest / semantics_digest 跨进程稳定 | session-bound;无显式 reproducibility digest |
| 2 | **Strict source enum** | 3-enum Literal + per-source 必填字段 + 构造期 validator(C107)| free-form string;SDK 不 enforce taxonomy |
| 3 | **Live / Detached row contract** | row 有显式 _result_resolver plumbing;Detached 状态 raise DetachedRowError(C130 / C131)| HTTP API 无此区分;客户端误调可静默失败 |
| 4 | **Validator gate 禁 partial graph** | Step 7 强校验 + gate fail → unsupported,**绝不**返回部分 / 损坏 graph(C134) | 无显式 validator gate;SDK 可能反序列化 lossy schema |
| 5 | **Aggregate topology 明确** | §8.10 锁:单 NODE_PREMISE + 0 NODE_SEED + count-only envelope(C136)| Rainbird list functions 行为隐式;contributor 展开度文档不充分 |
| 6 | **Quantitative carrier ⊥ math decomposition** | raw_kind + bound 唯一 canonical carrier(C110-C113);impact / salience 分离 defer | Rainbird 把 certainty(1-100)/ salience / impact 混在 reason 内,概念耦合 |

**总结**:6 项是 v1 **超越 Rainbird** 的具体技术承诺,Phase C 必须实现以保证 evidence service 的**产品级严谨度**。

### 12.4 我们 strictly less than Rainbird(5 项故意 deferred / v1 不覆盖)

| # | 维度 | Rainbird 提供 | 本设计 v1 不覆盖 | v2+ 触发条件 |
|---|---|---|---|---|
| 1 | **Atom-level why-not** | DiagnoseAtomLocator 单 atom locator(虽然 lossy)| **不提供**(C81 修订:failed → evidence=None;只给 envelope diagnostic)| 用户出现真实 "为什么这个 binding 推不出" 诉求 + top-down algorithm 成熟(详 §14 D1/D2)|
| 2 | **未命中 OR 分支 / 完整规则空间** | UI 可展示 alternative paths | **仅显示 winning path**(C129 / §8.6.2);alternative_paths.omitted_count 提示 | 复杂 compound case 用户体验诉求(§14 D14)|
| 3 | **Quantitative impact / salience attribution** | per-condition impact %(虽不完全严谨)| **不提供**;quantitative_explanation.decomposition="not_available_v1"(C127)| 用户出现 attribution analysis 诉求 + Shapley / weighted sum 收敛(§14 D7)|
| 4 | **Aggregation contributor lazy / embedded** | list-function evidence 可展开个体 facts(虽不一致)| **仅 count-only envelope**(C136);`mode="omitted_v1"` v1 唯一 | 大 audit 场景 + lazy fetch handle 机制(§14 D18)|
| 5 | **Cross-session replay** | factID + sessionID 可重新调用 explain | **依赖 manual `fg.eval.explain(expr, head=closed_head, ...)`**(主文档 §5.8.3 advanced path)| user 实际场景:跨进程 / 跨会话 audit replay 频繁(详主文档 §5.8.3 advanced)|

**总结**:5 项是 v1 **诚实承认不做** — 不假装做了一个 lossy 版本(避免 DiagnoseAtomLocator-style 误导)。v2+ 各有明确触发条件,**不是无限期搁置**。

### 12.5 用户承诺边界(User Commitment Boundary)

**给用户最直接的 evidence 期望**(可贴在 SDK docstring / README):

| 承诺 | 含义 | 锁定位置 |
|---|---|---|
| **passed → EvidenceGraph;else → None** | `status="passed"` 必有完整 evidence tree;`failed` / `unsupported` / `invalid_request` 三态 evidence 都是 None(无 partial / placeholder)| C81 / C132 |
| **failed 给 diagnostic envelope,不给 evidence tree** | `failed` 时:`failure_class`(5-enum)+ `checked_scope`(digest 漂移分析)+ `suggested_next_steps`(用户行动建议);**不**有 atom-level why-not tree | C125 |
| **v1 解释"为何这个 row 成立",不解释"为何其他可能都不成立"** | evidence 是 winning-path-only;OR alternatives / 未触发 rules 不展示 | C129 §8.6.2 |
| **Aggregate v1 解释 aggregate result,不解释每个 contributor 的完整 proof** | aggregate premise 给 result + matched_count + filter_repr,**不**展开 N 个 contributor sub-trees | C128 / C136 |
| **Evidence 是 durable audit artifact**(跨进程稳定 + reproducible) | metadata 15 fields 含 digest;同 view_snapshot + 同 rule_set → 同 EvidenceGraph(deterministic)| C123 / C135 |
| **Row.explain() 仅在 live row 上工作** | row 从 EvaluateResult 取出时是 live;JSON 反序列化得到的是 detached row → DetachedRowError | C130 / C131 |
| **Manual replay 必须提供 7 字段 minimum context** | `fg.eval.explain(expr, head=closed_head, ...)` advanced path 需 engine / semantics / expr_digest / rule_set_digest / view_snapshot_digest / evaluated_at / closed_head_content_digest | §7.3.1 / C135 |

**总结**:7 条用户面 contract,Phase C 实现 + SDK 文档 + 用户教育的 single source of truth。

### 12.6 §12 设计承诺 Commitments(C137)

| # | 承诺 |
|---|---|
| **C137** | **(Phase B-6 落定 2026-05-19)** §12 Product Boundary Declaration 是 v1 evidence service 用户面 expectation contract 的 single source of truth;§12.1-§12.5 对齐点 / 有意不同 / strict stronger / strict less / user commitment 五维度声明在 SDK docstring / README / 用户教程**保持一致**(措辞可调,语义不改);**user commitment 7 条**(§12.5)是 release announcement 必须显示对齐项;违反 §12 边界(如悄悄打破 "passed → EvidenceGraph;else → None")需新 commitment 修订 §12,不允许"实现一致但文档不改"| §12.1-§12.5 |

### 12.7 §12 与其他章节的引用关系

§12 是**收束章节**,引用前面所有章节:

| § | 引用关系 |
|---|---|
| §1.1 / §1.2 | 8 项优势 → §12.3 strict stronger 6 项的具体技术承诺 |
| §2.3 | Rainbird 词汇映射 → §12.1 对齐点 + §12.2 有意不同 |
| §4 / §5 / §6 | schema 设计 → §12.3 strict stronger #2 (source enum) / #6 (quantitative carrier) |
| §7 / §8 | orchestrator + topology → §12.3 strict stronger #3 (live/detached) / #4 (validator gate) / #5 (aggregate topology) |
| §9 / §14 | failure handling + deferred → §12.4 strict less 5 项 |
| §13 | commitments → §12.5 user commitment boundary 7 条的承诺锚点 |

§12 **不**引入新设计;它是把分散在 §1-§11 的产品决策**收束为用户面表达**。

---

## 13. 设计承诺 Commitments

### 13.1 主文档保留的 evidence 相关承诺(本文档引用,不重新编号)

| # | 承诺 | 主文档位置 |
|---|---|---|
| C15 | Phase 1(候选生成,engine sparse)+ Phase 2(按需 evidence,FactGraph 构造)两阶段架构 | §3.13(已迁本文档 §3.1)|
| C16 | Rule.atoms / atom_id / eval_atom / render_desc 是 Phase 2 最小 introspection 表面 | §3.13(已迁本文档 §3.3)|
| C19 | atom_id 格式 `<rule_id>:atom_<index>` | §3.13 |
| C60 | head.desc 在 §7 evidence 中作为 rule-level narrative 顶部 anchor;遵循 §3.7 / C5 desc 渲染规则;强烈建议(非强制)用户填写 | §5.11(主文档 §5.6)|
| C61 | `.eval` namespace 收编 explain(顶层 fg.check / fg.diagnose 删除并合入);fg.check 改名为 fg.eval.explain | §5.11 |
| C62 | `fg.eval.evaluate(expr, head=Rule, engine=..., semantics=...)` 签名升级 | §5.11 |
| C63 | `fg.eval.run` Phase 1 deprecated/frozen | §5.11 |
| C64 | `EvaluateRow` 6 canonical data fields + non-data `_result_resolver`;live row 支持 `.explain()` / `.close()`,detached row raise `DetachedRowError`;CandidateSet 在 SDK 表面废弃 | §5.8.2 |
| C65 | `EvaluateResult` 是 frozen evaluation session envelope;13 data fields shared audit/reproducibility context + 容器协议;`__getitem__` / `__iter__` / `.first()` 返回 live bound row | §5.8.2 |
| C66 | Explain API 两入口:`row.explain()` / `result[i].explain()` 主路径 + `fg.eval.explain(expr,head=closed_head)` advanced/manual replay;`row.close()` 是 advanced introspection | §5.8.3 |
| C67 | `Explanation` 4-state status 沿用 CheckStatus;evidence 统一为 EvidenceGraph | §5.11 |
| C68 | digests 计算规则(row_id / row_digest / result_digest / bindings_digest / expr_digest)| §5.11 |
| C69 | `.eval` 跨 engine / semantics 一致性;不 warn 不 reject | §5.11 |
| C70 | `fg.eval.why_not` v1 PENDING | §5.11 |

### 13.2 §7.12 status 归属(本文档 owner,从主文档迁出)

#### 13.2.1 决策

**`Explanation.status` 留 Explanation 顶层**,**不**移入 EvidenceGraph。

#### 13.2.2 核心论据(grounded)

`Explanation` 4 个 status 中,**`unsupported` / `invalid_request` 两态强制 `evidence=None`**(主文档 §5.8.3 已规约;本文档 §3.1 "evidence 不在失败态构造" 承诺)。status 必须有独立于 evidence 的载体,否则被迫:

- 伪造 placeholder `EvidenceGraph` 来"补齐"字段 → 违反 §3.1
- 开辟第二个传递通道 → 实质是 status 回到 Explanation 父层(绕远路)

故 status 必留 Explanation。

#### 13.2.3 语义层次区分

| 字段 | 归属 | 语义 |
|---|---|---|
| `Explanation.status` | answer envelope(回答的元数据)| 4-state engine 回答生命周期(passed / failed / unsupported / invalid_request)|
| `EvidenceGraph.support_kind` | proof structure(已 ship `audit/evidence_graph.py:60`)| evidence 内部支持结构类别(passed / failed 两态下都有有意义取值)|

两层正交。`status` 是"答没答"(快速分流字段),`support_kind` 是"怎么答的内部结构"(evidence 内部 metadata)。**不合并**。

#### 13.2.4 C79-C81 承诺

| # | 承诺 |
|---|---|
| C79 | `Explanation.status` 留在 Explanation 顶层,**不**移入 EvidenceGraph;4-state engine 回答生命周期(passed / failed / unsupported / invalid_request)沿用主文档 §5.8.3 / C67 |
| C80 | `EvidenceGraph.support_kind`(已 ship `audit/evidence_graph.py:60`)与 `Explanation.status` **不重复也不冲突**:status = engine 回答生命周期(answer envelope);support_kind = evidence 内部支持结构类别(proof structure);两层正交 |
| C81 | **(修订正式锁定 2026-05-18)** `status == "passed"` → `evidence: EvidenceGraph` 非 None;**其余 3 态(`failed` / `unsupported` / `invalid_request`)→ `evidence` 必为 `None`**;**禁止**构造 placeholder EvidenceGraph 来"补齐"字段。**修订理由**:`DiagnoseAtomLocator` 单点信息是 lossy(`diagnose_runtime.py:220-257` 有 6 个 caveat:multi-env 视角、单 candidate 输出、字典序代表、nested-atom 退化等),大事实库下不稳定;explain 不在 failed 态承载 lossy 失败信息。**v1 SDK 不公开 `fg.diagnose`** — application-layer DTO 保留 internal/legacy;v2+ 设计 top-down goal-regression 失败定位 API(详 §1.2 / §14 deferred)|

### 13.3 本文档 v1 新增承诺(C82-C89 + C91 + C106 已锁,C107+ pending)

> **Phase B-1 迁移 note**(2026-05-18):原 C90 / C92 / C93 已**迁出**至主文档 §8 / §10(重新编号为 C94 / C95 / C96 / C97)。**Phase B-1+ ArithExpr / AggregateExpr 落定** 2026-05-18:C98-C105(8 项)在主文档 §10.6 锁定;**C106 evidence reason kind 4-enum** 在本文档 §4.5 锁定。

| # | 承诺 | 所在章节 |
|---|---|---|
| C82 | 不扩展 shipped 3 node_kind + 3 edge_kind;扩展走 `engine_meta` | §4.1 |
| C83 | EvidenceNode 顶层字段(`label` / `value_summary` / `component`)填充规约 | §4.2 |
| C84 | `NODE_CONCLUSION.engine_meta` keys 集合(+ ProbLog 专用)| §4.3 |
| C85 | `NODE_PREMISE.engine_meta` keys 集合(+ ProbLog 专用)| §4.4 |
| C86 | `NODE_PREMISE.reason` 子结构 per atom_kind(v1 9 IR kinds);v1 仅表达"satisfied" | §4.5 |
| C87 | `NODE_SEED.engine_meta` keys 集合;`source` 3-enum 必需;ledger provenance 字段位置锁定 | §4.6 |
| C88 | `EvidenceEdge.engine_meta` 扩展;v1 仅 `EDGE_SUPPORTS`,`EDGE_DERIVES` / `EDGE_UPDATES` 预留 | §4.7 |
| C89 | `AtomKindSpec` registry internal-only;v1 SDK 表面不公开;用户自定义 v1.x deferred | §4.8 |
| ~~C90~~ | **迁出至主文档 §10 C97**(v1 IR canonical atom kinds 名单)| ~~§4.9~~ → 主文档 §10.1 |
| C91 | 不分每引擎 EvidenceGraph 类;沿用 shipped + `layout_hint` 区分时序/树 + per-engine engine_meta + shipped 3 converters | §4.11.1 |
| ~~C92~~ | **迁出至主文档 §8 C94**(Grammar 原生支持对照表)| ~~§4.11.2~~ → 主文档 §8.2 |
| ~~C93~~ | **迁出至主文档 §8 C95**(Negation 符号统一 + lowering matrix)| ~~§4.11.3~~ → 主文档 §8.4 |
| **C106** | **NODE_PREMISE.reason `kind` 4-enum**(`comparison` / `arith_comparison` / `aggregate_comparison` / `compound_comparison`)+ `aggregate_comparison` shape 锁定 + `contributors {mode,count,handle}` / `empty_set` / `no_value` / `error_kind` flags + compound 内部 schema v1.x deferred(§14 D14)| §4.5.7 |
| **C107** | **NODE_SEED.engine_meta.source 严格 3-enum**(`ledger_assertion` / `inferred_intermediate` / `inline_constant`)+ per-source 必填字段 + 构造期 strict validator;比 Rainbird 严谨 | §5.7 |
| **C108** | **Rainbird 6-enum → 本设计 3-enum 映射锁定**(`knowledgemap` → `ledger_assertion`;`rule` → `inferred_intermediate`;`synthesis` / `answer` / `injection` / `datasource` v1.x+ deferred;NAF 在 reason layer)| §5.7 |
| **C109** | **NODE_SEED color coding 按 source 区分**(对齐 Rainbird 心智):3 色 hex 锁定(`#d97e3a` / `#2e7d32` / `#88c87c`);Phase C 扩展 `_node_palette(node_kind, source)` 签名 | §5.7 |
| **C110** | **唯一 canonical quantitative carrier = `raw_kind` + `bound`**;canonical schema 不引入 public `probability` / `confidence` / `certainty`;`raw_kind XOR bound` 同 None | §6.7 |
| **C111** | ProbLog 点概率 = degenerate interval `bound=(p,p)`;deterministic = `None/None`;禁止 `bound=(1.0,1.0)` 表示"逻辑满足" | §6.7 |
| **C112** | Renderer shorthand 规则(value_summary):`"p=v"` / `"p∈[lo,hi]"` / `"[lo,hi]"` / `""` | §6.7 |
| **C113** | Adapter-native debug fields(`engine_meta.native_probability` 等)允许但 non-contract;canonical 不消费 / 不参与 digest;**禁止作 fallback 或主数据源** | §6.7 |
| **C114** | EvidenceGraph envelope 沿用 shipped + Form 1 `LAYOUT_TREE` / Form 2 `LAYOUT_TIMELINE` + graph_id 命名 deterministic | §8.13 |
| **C115** | Edge direction `from = premise/child, to = conclusion/parent`;Form 1 仅 `EDGE_SUPPORTS`;Form 2 加 `EDGE_DERIVES`/`EDGE_UPDATES` | §8.13 |
| **C116** | node_id / edge_id 命名 scheme(deterministic,per node_kind + source 显式编码)| §8.13 |
| **C117** | Form 1 4-layer topology + AND-only 内部 + OR 仅显示满足分支 + join 通过 seed reuse 物质化 | §8.13 |
| **C118** | Seed reuse rule(同 fact 仅 1 NODE_SEED,多 incoming edges)+ Phase C orchestrator dedup table | §8.13 |
| **C119** | ProbLog multi-path DAG(path_index suffix + aggregate bound at root + aggregation_rule)+ v1 默认 single-path | §8.13 |
| **C120** | **(Wave 1/row-centric 修订 2026-05-19)** ~~EvidenceHandle 13 字段~~ → **EvidenceRef 5 字段**(`ref_id` / `result_id` / `row_id` / `fact_digest` / `closed_head_digest`);shared context 上提至 EvaluateResult(共 13 字段,详 C65);用户主流程 `row.explain()` / `result[i].explain()`,**不直接持有 ref**;EvidenceRef 仅为 row-local audit/ref plumbing;**invariant**:`ref.fact_digest == row.claim.digest` | 主文档 §5.8.2 |
| **C121** | **NAF 从 source layer 退出 入 NODE_PREMISE.reason**(Wave 1 修订);`source` **3-enum**;NAF `not(p)` 满足 case **无 NODE_SEED**,仅 NODE_PREMISE.reason.naf 字段表达;C107-C109 同步修订 | §5.2.1 / §4.5.2 / §5.7 |
| **C122** | **(Wave 1 修订 2026-05-19)** ~~explained_fact 一等在 NODE_CONCLUSION~~ → **Claim 一等表示上提至主文档 `EvaluateRow.claim`**(详主文档 C64);evidence root NODE_CONCLUSION 仅持 `explained_claim_ref`(row_id + evidence_ref_id + claim_digest + claim_repr_cache);避免双写漂移 | §4.3.1 |
| **C123** | **(Wave 1 修订 2026-05-19)** EvidenceGraph.metadata audit reproducibility fields v1 必填(同前);**source-of-truth 锁定**:EvaluateResult 是 live context source,EvidenceGraph.metadata 是 durable snapshot copy;orchestrator 从单一 evaluated context object 写两处,**不允许独立演进**(双写漂移防护)| §8.2.1 |
| **C124** | **Schema versioning lite + contract/debug 分层**(Wave 1 doc-level):metadata.schema_version 必填 "1.0";contract fields 列表锁定;debug fields(`engine_meta.native_*` / `<engine>_*` / `adapter_debug_*`)non-contract / digest-excluded;v1.x 可演进至显式 `engine_meta.contract / debug` 嵌套结构 | §8.2.2 / §8.2.3 |
| **C125** | **(Wave 2 #3 / row-centric 修订 2026-05-19)** `Explanation` envelope 加 failure 字段:`failure_class`(5-enum,**仅 status="failed" 填**:`no_matching_row` / `closed_head_false` / `stale_row` / `row_not_in_result` / `insufficient_closed_bindings`)/ `checked_scope`(digest 对比 dict)/ `suggested_next_steps`(hint tuple);`DetachedRowError` 是 Python programming error,不进 failure_class;**business semantic** 与 technical error(unsupported / invalid_request 走 errors)严格分离;**不**是 DiagnoseAtomLocator,避免 atom-level 误导(详主文档 §5.8.3)| 主文档 §5.8.3 |
| **C126** | **(Wave 2 #4 落地 2026-05-19)** `NODE_SEED.engine_meta.source="ledger_assertion"` 增 `assertion_origin` Literal \| None(`import` / `manual_write` / `external_datasource` / `system_injection` / `user_input`) + `source_ref` str \| None;Ledger 无 metadata 时允许 None,但字段位置和 validator 锁定 | §4.6 / §5.2.2 / §5.5 |
| **C127** | **(Wave 2 #6 落地 2026-05-19)** root `NODE_CONCLUSION.engine_meta.quantitative_explanation` 必填;v1 只声明 `engine_reported` carrier 与 `decomposition="not_available_v1"`,不提供 impact / salience attribution | §4.3.2 |
| **C128** | **(Wave 2 #8 落地 2026-05-19)** aggregate contributor 的旧 boolean flag 删除,替换为 `contributors {mode,count,handle}` envelope;v1 默认 `mode="omitted_v1"`,lazy / embedded 为预留形态;`contributors.count == matched_count` | §4.5.4 / §4.5.7 |
| **C129** | **(Wave 2 #9 落地 2026-05-19)** root `NODE_CONCLUSION.engine_meta.alternative_paths` 必填;v1 `mode="winning_path_only"`,`omitted_count` 可知则填整数,未知填 None;不构造失败 / 未选 OR 分支节点 | §4.3.3 / §8.6.2 / §8.13 |
| **C130** | **(Phase B-5 落定 2026-05-19)** Orchestrator 入口两类:主路径 `row.explain()` / `result[i].explain()` via `_result_resolver`;Advanced `fg.eval.explain(expr, head=closed_head, ...)` caller 自带 context;两入口 Step 2-8 同 pipeline | §7.3 |
| **C131** | **(Phase B-5)** Detached row → `raise DetachedRowError`(Python exception);**不**进 Explanation.failure_class;编程错误与业务失败分离 | §7.3 / §7.9 |
| **C132** | **(Phase B-5)** `status="passed"` ⇔ `evidence != None`(双向 iff per C81);其余 3 态 evidence=None;**禁止 partial / corrupt graph** | §7.9 |
| **C133** | **(Phase B-5)** Strategy dispatch 三策略:S1 IR replay = core/default;S2 engine-native probe = optional advanced;S3 library API enrichment = ProbLog only;典型矩阵 Souffle/native=S1,ProbLog=S1+S3 | §7.6 |
| **C134** | **(Phase B-5)** Graph validation gate 必跑(Step 7);gate fail → `status="unsupported"` + `GRAPH_VALIDATION_FAILED`;**不**返回 partial graph;14 项 validator 检查锁定 | §7.10 |
| **C135** | **(Phase B-5)** EvidenceGraph.metadata 双驻 source-of-truth(承 C123):metadata 15 字段 derive 自单一 evaluated context;**orchestrator 不允许独立 / 二次计算**;Phase C debug assertion 校验跨字段一致 | §7.10 |
| **C136** | **(Phase B-6 补 2026-05-19)** Aggregate Premise Topology(§4.5.4 reason schema 与 §8 topology 闭环):AggregateExpr 在 evidence 内 = 单 NODE_PREMISE + 0 NODE_SEED(v1 default);v1 仅合法 `contributors.mode="omitted_v1"` + `count==matched_count` + `handle=null`;`matched_count` 是 view-projected snapshot count(C103),Step 3 frozen | §8.10 |
| **C137** | **(Phase B-6 落定 2026-05-19)** **Product Boundary Declaration**(详 §12):§12.1-§12.5 5 维度声明(对齐点 / 有意不同 / strict stronger / strict less / user commitment)是 v1 evidence service 用户面 expectation contract 的 single source of truth;SDK docstring / README / 用户教程**保持语义一致**;**user commitment 7 条**(§12.5)是 release announcement 必须显示对齐项;违反 §12 边界需新 commitment 修订 §12,不允许"实现一致但文档不改"| §12.1-§12.6 |

**主文档持有的相关 commitments**(本文档引用):

| # | 承诺 | 主文档位置 |
|---|---|---|
| C94 | Grammar 原生支持对照表(Form 1 unified 9 kinds × 3 engines)| §8.2 / §8.5 |
| C95 | Negation 符号统一 `not` + lowering matrix | §8.4 / §8.5 |
| C96 | Adapter 实现 gaps(Souffle/ProbLog `ne` + arith adapter)| §8.3 / §8.5 |
| C97 | v1 IR canonical 9 atom kinds(`pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in` / `not`)| §10.1 / §10.4 |
| **C98** | **ArithExpr expression form**(+ div-by-zero atom violated)| §10.6.2 / §10.6.10 |
| **C99** | **AggregateExpr expression form**(+ 5 v1 kinds)| §10.6.3 / §10.6.10 |
| **C100** | **Aggregate filter restrictions**(+ not body 递归限制)| §10.6.4 / §10.6.10 |
| **C101** | **Empty set + AggregateNoValue 语义**(fail-stop,不参与 binding)| §10.6.5 / §10.6.10 |
| **C102** | **Aggregate numeric target type**(C102 修订版:构造期 + 运行期双层校验)| §10.6.6 / §10.6.10 |
| **C103** | **Aggregate snapshot 语义**(matched_count = view-projected)| §10.6.7 / §10.6.10 |
| **C104** | **Aggregate variable scoping**(correlated outer + local internal)| §10.6.8 / §10.6.10 |
| **C105** | **Aggregate result binding**(eq behavior iff result ≠ NoValue)| §10.6.9 / §10.6.10 |

---

## 14. 显式 Deferred Items

> **本节状态**:Phase A 锁定 11 项 deferred(承自 §1.2 + 2026-05-18 决议追加);Phase B 推进时补 trigger 条件 + scope sketch 细节。

### 14.1 失败定位类(v1 显式不做)

| # | 项目 | v2+ trigger | 算法族 |
|---|---|---|---|
| D1 | **`fg.diagnose` SDK 表面公开**(shipped application-layer 保留 internal)| 用户出现明确"为什么 binding 推不出"诉求 + 当前 single-locator 不够用 | 替换为 top-down(详 D2)|
| D2 | **top-down goal-regression failure diagnosis**(替代 v1 lossy 单点 locator)| 大事实库下 single-locator 启发式不稳定 | Bourhis-Lutz-Krötzsch 2024 + Elhalawati 2022 why-not provenance |
| D3 | Why-provenance(SAT-based minimal fact set)| 学术族算法成熟 + 用户需求成形 | SAT 编码 + minimal hitting set |
| D4 | atom-complete failure-side probing(每 atom 打 violated 标)| 用户明确需求"failed 时每 atom 状态"| 自实现 eager probe(参 R2-C 调研方向)|
| D5 | Why-not / counterfactual analysis | 用户出现明确 attribution / what-if 需求 | 反事实推理算法 |

### 14.2 量化 / 概率类(v1 收敛)

| # | 项目 | v2+ trigger |
|---|---|---|
| D6 | `salience`(condition weight,Rainbird 等价)| 跨 condition 权重出现实际诉求 |
| D7 | `impact` % decomposition(Shapley / 加权累加)| 用户需要 attribution analysis |

### 14.3 通道扩展类(v1 不引入)

| # | 项目 | v2+ trigger |
|---|---|---|
| D8 | session log channel(Rainbird `/interactions/` 等价)| 出现 session-style interactive flow |
| D9 | LLM-derived NL explain | head.desc 模板渲染不够 |
| D10 | per-fact ACL(`x-evidence-key` 等价)| multi-tenant 服务部署 |

### 14.4 Evidence Schema 扩展类(Phase B-1+ 新增)

| # | 项目 | v2+ trigger |
|---|---|---|
| D14 | **`compound_comparison` reason 内部 schema 完整化**(ArithExpr ⊃ AggregateExpr 多重嵌套 case;双侧均含表达式;多 AggregateExpr siblings 组合等)| 用户复合表达式场景成熟 + 调试需求 |
| D15 | **AggregateExpr v1.x 扩展 kinds**(`any` / `all` / `isSubset` / `join` / `first` / `last` / `sort` / `group_by`)| 用户业务诉求 + adapter 实现成熟 |
| D16 | **ArithExpr v1.x 扩展 operators**(`%` / `**` / 位运算 / 字符串拼接)| 用户业务诉求 |
| D17 | **Overflow / NaN / inf protection**(`OverflowProtectionError` / `NaNCheckError`)| 用户出现实际数值异常诉求 |
| D18 | **Aggregate matched_facts materialization beyond count-only envelope**(v1 已锁 `contributors {mode,count,handle}`;默认 `mode="omitted_v1"`;lazy / embedded 取数实现 deferred)| 用户需要 contributing facts 展开 |
| D19 | **Aggregate target implicit cast**(string-to-numeric 等)| 用户场景实际出现 |

### 14.5 引擎扩展类

| # | 项目 | v2+ trigger |
|---|---|---|
| D11 | PyReason Form 2 evidence(时间步)| Form 2 设计独立推进;timeline layout 已 ship 可承载 |
| D12 | Eager / Lazy 切换(目前 eager)| evidence > 10MB 或渐进 UI 需求 |
| D13 | Nemo 作为 backend opt-in(Datalog 翻译层)| 用户真实 Datalog-only 大规模负载 + audit 要求严格 match engine |

### 14.6 deferred 项 → §1.2 映射

§1.2 概述表与本节 D1-D19 一一对应;§1.2 是入门级别概述,本节是 lookup 表。
