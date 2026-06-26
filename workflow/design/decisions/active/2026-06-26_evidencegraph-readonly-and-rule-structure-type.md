# Decision: EvidenceGraph 只读派生定位 与 引擎中立的规则结构类型

- Status: adopted
- Created: 2026-06-26
- Last Updated: 2026-06-26
- Authority: design constraint;在实现 `fg.rules.structure` / 任何"静态规则结构"工作之前,锁定 EvidenceGraph 的定位与规则结构类型的边界。
- Inputs:
  - design-point [rule-structure-static-projection.zh.md](../../design-points/active/rule-structure-static-projection.zh.md)(§1–§5,Open Q1)
  - 用户-对话设计探索(2026-06-26,多轮 grounded passes;见上 design-point Inputs)
  - shipped:`evidence_tree.py`(EvidenceGraph/Tree/Timeline)、`rule_expr_lowering.py`(RuleExprLoweringPlan)、`rule_expr_inspect.py`(RuleExprInspect)
- Outputs / Downstream:
  - 一个 implementation blueprint:`fg.rules.structure(rule) -> RuleStructure`(harvest design-point §3 的类型契约)
- Related:
  - [explain-layer-complete-design.zh.md](../../design-points/active/explain-layer-complete-design.zh.md)
  - [rule-namespace-rulespec-redesign.zh.md](../../design-points/active/rule-namespace-rulespec-redesign.zh.md)
- Branch: `v0.2.0-factgraph-sync-2026-06-25`

> ADR 4-state:`proposed` → `adopted`(当前约束,留 `active/`)→ `superseded`/`withdrawn`(移 `archive/`)。转换显式;无 `adopted → proposed` 重开。

## 1. Inputs

来自 2026-06-26 的一系列 grounded 设计探索,收敛出两个 load-bearing 架构问题,需在任何"静态规则结构 / display↔explain 对位"实现之前锁定:(1)`EvidenceGraph` 到底是只读派生视图还是可操作结构?(2)规则的静态结构应复用 `EvidenceGraph` 类型,还是另立一个引擎中立类型?探索确立:lowering plan 引擎无关、是 explain 全部身份键的来源;`EvidenceTree` 在关系引擎间结构一致;`EvidenceTimeline` 仅 pyreason 产出(时序为运行时产物);`RuleExprInspect` 走未-DNF 作者树,不带 plan 键。

## 2. Scope

本 decision 锁定:

- `EvidenceGraph`(及 `EvidenceTree`/`EvidenceTimeline`)的**定位与边界**(只读派生 vs 可操作)。
- 规则**静态结构的类型归属**:复用 `EvidenceGraph` vs 独立引擎中立类型,以及二者如何对位。

## 3. Non-scope

不锁定(留给 implementation blueprint / design-point):

- `RuleStructure` 的**逐字段类型契约**(design-point §3.2 的草案;最终字段、`HeadClosure`、`FreeVar` 细节在 blueprint 定稿)。
- **命名**最终拍板(design-point §3.5 推荐 `RuleStructure` + `Structure*`;blueprint 确认)。
- `assemble_static_structure` 的**落点**与 `prober.py` 拆分粒度(design-point Q2)。
- pyreason/`EvidenceTimeline` 的 cross-model 语义映射形态(design-point Q4)。

## 4. Decision

### 4.1 EvidenceGraph 是只读派生投影,绝非 authoring substrate

`EvidenceGraph`(连同 `EvidenceTree`/`EvidenceTimeline`)是 **Rule 在一次具体求值下渲染出的影子**——只读派生视图,**不是**可操作/可 author 的结构。Rule(经 RuleExpr + 其 lowering plan)是唯一、量化、可求值的行为源。

- **合法操作(只读视图)**:render/walk/narrate、读字段取信息、纯图间 diff、for-display 的静态↔运行时叠加、限 audit 的序列化/replay。
- **越界(会使其成为 authoring substrate)**:任何 `evaluate(graph)`/`derive(graph)`/`graph→facts`;任何 `core/`(ledger/evaluate/derive)函数**接受 `EvidenceGraph` 参数**;公共"手搓图再喂下游"构造器;mutation;把 `evidence_graph_from_dict` 升格为公共 authoring 入口。
- **可复用 litmus**:任何能力,若"用户能否绕过 Rule、从它拿到行为/事实/verdict?"答案为"能",即越界。
- **机械明线**:加守卫/测试断言 `core/`/推导链**任何函数都不接受 `EvidenceGraph`(或 §4.2 的 `RuleStructure`)参数**——把明线从约定变成机制。

### 4.2 规则静态结构是一个**独立的引擎中立类型**,按共享 backbone 与 EvidenceGraph 对位

规则的静态结构**不复用 `EvidenceGraph` 类型**(后者引擎污染:`engine`/`Tree|Timeline` union/`verdict`/`certainty`/`timestep`)。它是一个**独立的、引擎中立的类型**(design-point 推荐名 `RuleStructure`),且:

- **共享 backbone**:`RuleStructure` 与 `EvidenceGraph` 都是**同一个 `RuleExprLoweringPlan` 的投影**;`EvidenceGraph` 本就从该 plan 装配。
- **按键对位,非同类型 zip**:对位发生在 branch-and-below,凭 plan 派生的身份键 `branch_id↔tree_id` / `occurrence_alias` / `atom_id` / `join_id`(单一来源 ⇒ 无漂移)。容器 id(`structure_id` per-rule vs `graph_id` per-run)**不是**对位键。
- **`Evidence*` 零改动**:`evidence_tree.py` 与其消费者(`narrate_evidence`/`walk_evidence`/`evidence_graph_to_dict`/audit DTO/runtime wrapper)**不动**——因为不混类型,无需 `Unevaluated` verdict / `engine` 放宽 / 边界拒收等"伪装中立"补丁。
- **范围 = Tree**:静态结构是 Tree 形;pyreason/`EvidenceTimeline` 的时序是运行时产物,**在节点恒等对位之外**(cross-model 语义映射,另议)。
- **`RuleStructure` 同样只读派生**:从 rule 经 lowering plan 投影,不得作 authoring 输入(同 §4.1 的 litmus 与机械明线)。

## 5. Rejected Alternatives

### Option (a): 复用 EvidenceGraph 作"verdict-less 静态图"(早期 Option B)
- **Why rejected**:需给运行时 `EvidenceGraph` 塞 `Unevaluated` verdict / `engine=null` / `FreeVar` / 边界拒收等补丁——把引擎污染的类型硬扮中立,违反"rule 引擎中立"原则,且 `paths` 的 `Tree|Timeline` union 在 rule 阶段无法确定(引擎模型决定)。

### Option (b): 让 EvidenceGraph 可操作(可构造/编辑/derive-from)
- **Why rejected**:`EvidenceGraph` 无求值语义(冻结、零方法、subject-bound、受 S5 不变式约束:`status∈{passed,failed} ⇔ evidence≠None`)。可操作即与 Rule 职能重叠("何不直接定义 EvidenceGraph"),坍塌 Rule↔Evidence 边界。

### Option (c): 独立类型但**不**共享 backbone(各自从作者树/plan 独立计算)
- **Why rejected**:这正是今天 `RuleExprInspect`(走未-DNF 作者树)与 `EvidenceGraph`(走 plan)的现状——身份键不同、无法对位、且会漂移。共享 `RuleExprLoweringPlan` 是消除漂移的关键。

## 6. Supporting Evidence

- `EvidenceGraph` 冻结、零方法、纯数据载体:`evidence_tree.py:154-166`。
- lowering plan 引擎无关:`rule_expr_lowering.py:836-850`;`engine` 仅作 label:`:324-327, :349`。
- `EvidenceGraph.paths` = 每 DNF 分支一棵 `EvidenceTree`,`tree_id=branch_id="c{idx}"`:`rule_expr_lowering.py:962` + `evidence_tree.py`(paths/tree 定义)。
- `RuleExprInspect` 走未-DNF 作者树、atom 键 `{rule.id}:atom_{idx}`:`rule_expr_inspect.py:343-354`、`rule.py:100`。
- `EvidenceTimeline` 仅 pyreason 产出(时序为运行时不动点产物):`adapters/pyreason/provenance.py:164, 224-226`。
- S5 不变式(evidence 存在性由求值定义):`src/factgraph/application/protocol/docs/README.md:139-146`。

## 7. Consequences

### 7.1 Downstream unblocking
解锁 `fg.rules.structure(rule) -> RuleStructure` 的 implementation blueprint(harvest design-point §3 的类型契约 + §5 的 slices 草图)。

### 7.2 Required follow-up actions(blueprint 必须做)
- 定义独立 `Structure*` 类型(§4.2),**不**改 `Evidence*`(§4.2)。
- `assemble_static_structure(plan)` 复用与 prober/assembler **相同**的身份键铸造(§4.2 对位)。
- 实装 §4.1 的**机械明线**守卫/测试(`core/`/推导链不收 `EvidenceGraph`/`RuleStructure`)。
- 文档化**节点恒等对位不变式** + EvidenceGraph 只读定位/litmus/Tree-only 边界。

### 7.3 No-retroactive boundary
本 decision 不改变任何 shipped 运行时行为;`EvidenceGraph` 与其消费者保持原状(§4.2 零改动)。

## 8. Acceptance Criteria

- [ ] `RuleStructure` 为独立引擎中立类型;`evidence_tree.py` 未被本工作改动。
- [ ] `fg.rules.structure(rule)` 与 `fg.eval.explain(<同规则>).evidence` 在 `branch_id`/`occurrence_alias`/`atom_id`/`join_id` 上节点恒等(native/souffle/problog)。
- [ ] 存在机械守卫/测试:`core/`/推导链无函数接受 `EvidenceGraph` 或 `RuleStructure`。
- [ ] pyreason explain 仍工作;Timeline 文档化为节点恒等对位之外。

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-06-26 | proposed | Decision drafted | 锁定 EvidenceGraph 只读定位(§4.1)+ 规则结构独立中立类型/按键对位(§4.2);来自 design-point rule-structure-static-projection 的 Q1。 |
| 2026-06-26 | adopted | Decision adopted | 用户授权"继续走 + 沿用 Codex-impl/Claude-gate/user-merge 模式";审议充分,锁定为当前约束。下游:实现 blueprint 2026-06-26_rule-structure-impl。 |
