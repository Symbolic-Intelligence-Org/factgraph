# Session Handoff — 2026-08-11 Meander × FactGraph 设计、纵向探测与下一阶段

> 角色：session continuity / operational memory。
>
> 本文不是 shipped capability、ADR、active blueprint 或产品授权。代码与模块文档仍是实现真相；正式决策仍以 adopted decision、scoped blueprint 及对应审计为准。

## 0. 快速恢复

本会话从 Meander 产品形态与 Agent 参与方式出发，逐步收敛到一条候选主链：

```text
Rule semantic ports
→ Policy
→ EvaluationQuery
→ FactGraphEvaluationBundle
→ Explain / limited replay
→ Meander Plan adapter
→ Agent 实测
```

当前并未开始生产 FactGraph 改造。已完成的是：

1. 市场、产品、架构与代码调研；
2. 统一设计候选及 28 子代理对抗审核；
3. finding 处置、v0.1.1 文本收敛和 Q1/Q2 决策链；
4. 一次 disposable、native-only 的 Meander Agent Query/Validation vertical probe；
5. 对 probe 结果、证据强度与下一阶段实施顺序的复核。

当前推荐不是“全面更新 FactGraph”，而是：

> 先实施一个私有、native-only、可回滚的 FactGraph 纵向切片；每个切片同时带测试。基础合同稳定后，再接 Meander A0/P0 adapter 和真实 Agent tool-call 测试。

## 1. 与早期原始会话导出的关系

早期完整线程快照位于：

- [`../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/README.md`](../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/README.md)
- [`../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/conversation.md`](../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/conversation.md)
- [`../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/messages.jsonl`](../session_exports/2026-08-10_meander-product-design_thread-019fdbfb/messages.jsonl)

该导出覆盖 93 turns / 313 条 User/Assistant 消息，截止 `2026-08-10T16:09:32.046Z`。本文承接其后尚未进入原始导出的设计与实验进度。

Thread ID：`019fdbfb-7dd8-7003-8ca8-ea0c5e32a388`。

## 2. 用户意图与必须保留的设计姿态

以下是后续工作不能丢失的上位意图：

1. **优化对象是 Meander 业务，不是为了优化 FactGraph 而优化 FactGraph。** FactGraph 的变化必须降低 Agent 使用规则、验证回答和解释结果的难度。
2. **当前仍是设计探索，不应把每次讨论都冒充正式决策。** 需要明确区分工作共识、待证伪假设、正式 ADR 和 shipped capability。
3. **奥卡姆剃刀。** 不无限扩展 Query、Scenario、Operator、Translator、UI、Replay、Action 等概念；只有被当前纵向链需要的能力才进入首个切片。
4. **最危险的产品假设仍是 Agent 能否稳定生成有意义的 Plan/Query。** 它尚未被真实模型测试。
5. **UI 不是独立装饰层。** UI、Explain、Policy tree、What-if 和业务状态语义相互咬合，但 UI 不进入第一个 FactGraph 切片。
6. **避免工作流官僚化。** 需要审计性，但不应把每个机械步骤拆成单独的人工授权。下一阶段采用一个短 decision、一个窄 blueprint、必要的 delta preflight 即可。
7. **保护 dirty worktree 和 sacred branches。** 不自动修改、清理、stash、reset、push 或 merge 用户已有工作。

## 3. 设计思路演化

### 3.1 Rule、semantic port 与 ontology

起始锚点是将 Rule 的 port 绑定到 ontology tree 上的 field 或 identity：

- Rule 不再像“海上漂浮、互相绑定的木筏”，而更像 ontology tree 上可复用的“树屋”；
- port binding 表示语义类别，不表示变量相等；
- 同一 Rule 中 `person1: Person.identity` 与 `person2: Person.identity` 仍是不同 occurrence/变量；
- Rule 是可复用逻辑组件，可能被看作 ontology/schema 的衍生语义模块；
- 中间变量仍是实现细节，公开 port 才是 Agent、Policy 和 Query 可寻址接口；
- semantic port 还可能支持从确定端点计算依赖锥和假设影响范围。

现有 shipped `Rule` 已有 `ports: Mapping[str, Var]`、推导式 `port_types`、`RuleOccurrence` 和 occurrence-qualified `RulePortRef`，但还没有目标设计所需的显式 ontology/field/identity/cardinality contract。

### 3.2 Rule、Policy、Package

当前工作模型：

- `Rule`：可复用、局部的逻辑组件；
- `Policy`：Rule/occurrence 的顶层业务组合，表达完整业务规则链；
- `Package`：Meander 侧面向 Agent/workspace 的不可变发布上下文，可包含 Policies、Rules、权限与说明；不是 FactGraph 原语。

旧 `RuleExpr` 是重要 lowering/兼容底座，但不直接等同于新 Policy：

- RuleExpr 的 `AND/OR`、join 和 projection/head 能力可被复用；
- `head` 被理解为弥补旧 RuleExpr 输出表达不足的 “last mile”；
- 新 Query 路径中 projection-only synthetic head 应成为 compiler 内部细节，不再要求 Agent 手工构造；
- 旧 `fg.eval.evaluate(expr, head=...)` 在首轮迁移中保持兼容，不立即删除。

Policy occurrence 共享一个 namespace：

```text
coworkers as pair
pair.person1
pair.person2.age
```

alias 解决同一 Rule 多次出现的 occurrence identity，不依赖 Rule 自身 ID 来区分两个实例。

### 3.3 Policy 中性与 Query 运行时目标

工作共识倾向于：

- Policy 定义完整业务逻辑，不为每个问题预设固定输出 port；
- Query 在运行时指定绑定和观察目标；
- Agent 根据问题选择 Policy、绑定输入、选择结果，而不是自己完成逻辑推理。

Query 的三个核心动词必须严格分开：

- `bind`：给 Policy occurrence port 提供输入约束；
- `select`：只投影/返回目标，不改变 Policy 真值；
- `expect`：在完整性条件允许时评价已产生结果，不进入 body，也不筛选 rows。

首轮 expectation 只考虑可闭合语义：

- `exists`；
- `contains_row`；
- incomplete/truncated 时显式 `underdetermined`，不能把未知吞成 false。

### 3.4 Query 统一假设

讨论过将 Query 视为统一目标构造框架，使以下对象共享调用层：

- 单 Rule；
- Policy；
- 复杂查询；
- Match 风格查询；
- 未来 Scenario/What-if overlay；
- 受限、只读、可审计的 Compute/Lookup Operator。

该假设只在调用、组合和审计层统一，不宣称逻辑 Rule、外部代码 Operator 和有副作用 Action 语义等价。

当前裁剪：Operator、What-if、Scenario、Action 均不进入首个 native slice；先验证 Rule → Policy → Query → Explain 主链。

### 3.5 Premise、Claim 与 Scenario

已经形成但尚未进入首轮实现的思路：

- 事实性运行时声明可统一为 premise/claim-like overlay；
- 规则变化是另一类 Policy overlay，不应与事实值覆盖混在一起；
- `SET/REPLACE`、`ADD`、`REMOVE/MASK`、absence/unknown/negation 必须有不同语义；
- “Alice 比 Bob 年长”这类关系假设不能被粗暴改写为一个字段值，仍是表达力与 grounding 风险；
- 新 Scenario 应基于 immutable EffectiveSnapshot，并与 Evaluate/Explain 使用同一执行主链；
- 旧公开 `fg.what_if` 已被移除，不是新 Scenario 的兼容约束。

Scenario/Premise 仍待 D09 等决策，明确不进入当前 FactGraph 首轮。

### 3.6 Agent 参与和权限维度

讨论过并保留两组互补维度。

参与/接入层：

- L0：被动 trace/输出观察与 Translator；
- L1：显式 `ValidationRequest` / tool / API；
- L2：可选 inline remediation callback；
- L3：Agent 原生生成 typed ClaimSet/Plan/Query。

Agent Policy 权限：

- A0：固定 Policy/Profile，Agent 只填 server-authorized slots；
- A1：从允许的 Package/Policy 中选择；
- A2：受限组合 Policy；
- 更高权限的自由构造保持实验性。

当前首个可实现产品切片应从 A0/P0 开始：固定 PolicyQueryContract，Agent 只提交它想绑定和查询的内容。

### 3.7 Translator 与 SourceRecord

调研后的候选输入路径仍有三种：

1. Agent 原生 typed emission；
2. Meander Translator 从文本提取 Claim/Query；
3. 人工或领域 adapter 构造。

Translator 引入 fidelity、上下文不共享、隐私、成本和 false `SUPPORTED` 风险。倾向 BYOK，但真实 Translator fidelity 仍未测试。

完整 `SourceRecord + SourceLocator` 仍是目标设计的重要边界：agent message、tool result、数据库记录和文档来源都应使用可对齐的来源条目；`source_spans` 不能只是任意字符串片段。但 SourceRecord、Translator 和 RAG 不进入首个 FactGraph slice。

## 4. 产品与市场研究状态

完整调研包位于：

```text
/Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/
```

它覆盖：Meander/FactGraph 代码审计、Translator、SourceRecord、L0–L3、Verify/Decide、市场/金融服务楔子、相邻产品和推荐 MVP。

对抗审核包位于：

```text
/Users/zhenzhili/obsidian_workspace/symb-Intelli./claude_report/
```

主审核使用 28 个子代理、83 条 findings。审核的两项独立结论应继续保留：

- 架构：`REVISE`，中央语义链未被否决；
- 产品授权：`STOP-except-discovery` / P-GATE 仍开放，技术可行性不能替代真实产品价值证据。

用户认为先前多轮调研已足够形成产品价值的方向判断，当前优先级是覆盖型案例和技术可行性，不要求马上接触 8–10 个目标账户。这是工作优先级选择，不等于公开 desk research 已证明付费意愿。

## 5. 统一设计、对抗审核与 v0.1.1

关键文件：

- [`../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md)
- [`../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md)

Review Freeze 形成过完整统一候选，但它不是生产授权。83 findings 经处置矩阵收敛为：

```text
32 ACCEPT
23 ACCEPT_WITH_NARROWING
16 NEEDS_DECISION
10 PHASED_LATER
2 REJECT_AS_MISREAD
```

SC-01 的准确状态：

> 非对称 `join × Any` 构造被允许，当前 lowering 行为可观察，但其语义未测试、未规格化。它既不是已证实 shipped bug，也不是有语义测试背书的有意设计。

v0.1.1 完成的是文本一致性和工作流收敛，不是产品代码落地。

## 6. Vertical Probe：范围、代码与终态

### 6.1 Git 坐标

截至本文写入前：

```text
repo:   /Users/zhenzhili/hnsm-backend
branch: v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11
HEAD:   61dee29b5007ed11c7fcbaae36b6f35059e88ba4
master: 854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0
```

重要 commits：

```text
cacc6901  freeze Step 2 fixtures/goldens/manifests/rubric
7a346faa  Step 3 facade + original primary run 15/20
caff2f5f  A′ fixes + separately-accounted verification sweep 20/20
870471b8  replay/local model projection readiness
22e040a5  disposition validator checkpoint
9b818490  first closure (later corrected)
28b5e029  closure correction to REVISE/THRESHOLD_UNMET
61dee29b  kill census / validator closure follow-up
```

实验资产位于：

- [`../../../tools/benchmarks/meander_qv_vertical_probe/`](../../../tools/benchmarks/meander_qv_vertical_probe/)
- [`../../blueprints/active/2026-08-11_meander-agent-query-validation-vertical-probe.md`](../../blueprints/active/2026-08-11_meander-agent-query-validation-vertical-probe.md)
- [`../../../tools/benchmarks/meander_qv_vertical_probe/reports/final_disposition.md`](../../../tools/benchmarks/meander_qv_vertical_probe/reports/final_disposition.md)

整个 probe 是 disposable、experimental、native-only；没有修改 shipped `src/**`、Meander 或邻接仓库。

### 6.2 唯一实质终态

当前 frozen evidence 对应：

```text
disposition             = REVISE
reason                  = THRESHOLD_UNMET
experiment_validity     = UNRESOLVED
architecture_hypothesis = NOT_CONTRADICTED
agent_dimension         = NOT_TESTED / UNRESOLVED
```

解释：

- 无 kill criterion 触发；
- 核心架构没有被证伪，也没有被完整证明；
- Step 3 exact-anchor exit 未实现/未证明；
- R0 aggregate 未满足；R1/R2 只有窄代表性证据；
- 两个真实模型臂从未运行；
- Translator、产品价值和 P-GATE 不在本 probe 范围。

### 6.3 原始 15/20 与修复后 20/20

原始 primary run 必须永久保留为 `15/20`。五个失败来自三个实现根因：

1. `A01-AUTH` forbidden fields 被字母排序，而 frozen golden 要求 submission order；
2. `SC12-P/AC21` static rejection 缺少 `structured_diagnostic` content class；
3. `E02/E03` Validation 错误地额外生成 `query_summary`。

在 fixtures、goldens、schema、rubric、scorer 字节不变的前提下修复三处实现后，同一 20-case corpus 的 verification sweep 达到 20/20。

最大诚实主张：

> Frozen native P0/A0 experimental contract 在三项实现修复后可全部实现，并且已知 20 例回归一致。它不是独立 holdout，不证明生产泛化、公共 API、跨引擎或 Agent 行为。

准确分类：两项 artifact/normalization 缺陷，一项 Query/Validation result-channel 语义实现缺陷；不是 engine/business inference 真值错误，但“零语义修复”的说法过强。

后续规则：

- 保留 20 例作为回归集；
- 在生产 FactGraph 提升前密封 6–9 个 fresh targeted holdout；
- holdout 只运行一次，失败不在同一集合上修后重计为独立通过；
- 可补 property/metamorphic tests，而不重新建立巨型实验。

### 6.4 已得到的形成性技术证据

已局部跑通：

- occurrence-qualified port/path；
- bind、All/Any、Compare/Unify、projection-only head；
- authored→lowered lineage 和 branch applicability；
- rows、complete/incomplete、exists、contains-row expectation、underdetermined 和 typed engine failure 区分；
- namespace collision、DNF cap、field-navigation grant/失败；
- live selected-row Explain；
- Q02 的窄 R1/R2 rowset/completeness；
- negative availability、mutation isolation 和现有兼容基线。

未证明：

- shipped/public API 和生产迁移；
- exact-anchor exit；
- query-summary/expectation 的真正 live Explain；
- R2 authored EvidenceGraph node identity；
- R3/R4；
- Soufflé/ProbLog parity；
- 性能、cutoff、规模；
- SC-01 最终语义选择；
- What-if/Premise；
- Agent/Translator。

### 6.5 Closure tooling 的剩余卫生问题

当前终态 tuple 对实际 evidence 可重算一致，但 `61dee29b` 的 validator/归档仍有未完成修正；这些不改变产品/架构结论：

1. `validate_declared()` 没有拒绝缺字段的 partial five-tuple；空 `{}` 可被接受；
2. STOP + `thresholds=None/list` 可在 `_agent()` 抛异常，没有完整实现所选 precedence；
3. blueprint 中 `K-SCOPE` 是 “STOP for hypothesis”，validator 尚未将其映射为 architecture contradiction；
4. durable byte count 随 closure commit 已陈旧，宜改为 commit-scoped measurement 或只证明低于 cap；
5. replay raw `pass:true` 与顶层 partial/unresolved 表述仍需消除歧义；
6. BYOK 未执行的直接前置因果应写 Step 3 exact-anchor/deterministic gate，不应把后置 replay 或模型结果本身写成先决原因。

建议将这些合并为一个零 engine/model 的最终 archive-hygiene commit，随后归档；不再扩成新实验。

## 7. 最新产品判断

本轮不是完整“产品验证”，而是技术合同纵向探测。当前可用的判断是：

| 维度 | 判断 |
|---|---|
| 中央技术方向 | 值得继续；未被证伪 |
| Rule/Policy/Query feasibility | 部分正向证据 |
| 生产就绪 | 尚未达到 |
| Agent Plan fidelity | 未测试 |
| Translator fidelity | 未测试 |
| 市场/付费证据 | 本轮未测试；P-GATE 保持开放 |

因此下一步可以进入 FactGraph 更新，但只能是**验证驱动的窄 native slice**，不能把整个 Review Freeze 当成生产蓝图。

## 8. 推荐更新计划

### 8.1 一个短前置裁决

只关闭四个会改变代码形状的问题：

1. semantic port descriptor 的最小形状，以及如何兼容现有 `Rule.ports: Mapping[str, Var]`；
2. SC-01 `join × Any` 采用 `branch_scoped` 还是 `reject_on_partial`；
3. `select/expect/completeness/zero-row` 的最小语义；
4. row/query-summary/expectation exact anchor 的身份及 digest inputs。

不要求一次关闭 D02–D18 全表。

### 8.2 五个 FactGraph 工程切片

#### F1 — Semantic Ports

- 保留现有 `Rule.ports` 外形与旧调用；
- 增加显式或可冻结的 ontology/field/identity/type/cardinality descriptor；
- 定义稳定 occurrence-qualified path；
- 验证 alias collision、ontology mismatch、port type mismatch 和旧 Rule compatibility。

#### F2 — Policy AST + Compiler + Lineage

- 新增最小 `Policy / All / Any / Occurrence / Unify / Compare`；
- lowering 到现有 RuleExpr/current native evaluator；
- projection-only synthetic head 仅作为内部 compiler artifact；
- authored node → DNF branch → lowered rule/atom 必须 machine-checkable；
- 覆盖 SC-01、SC-12、AC-21 和 DNF limit。

#### F3 — EvaluationQuery

- 定义 `bind/select/expect`；
- 首轮仅支持 rows、`exists`、`contains_row`；
- `select` 不改真值，`expect` 不进入 body/不筛选 rows；
- complete/incomplete/truncated/zero/underdetermined 分离；
- field navigation 必须经 Policy-owned materialization + explicit grant。

#### F4 — EvaluationBundle + Anchors + Lazy Explain

- 引入不可变 `FactGraphEvaluationBundle`；
- 捕获 resolved execution profile/config、snapshot、rules/policy/lowering/lineage digests；
- 定义 row/query-summary/expectation 三类 exact anchor；
- `row.explain()` 保持语法糖；canonical 入口面向 bundle + explicit target；
- 三类 target 都必须真正使用 live handle 验证；zero-row 禁止 implicit first row。

#### F5 — Native Vertical Integration + Limited Replay

- 先提供 internal/experimental `fg.eval.evaluate(query, config=...)`；
- 旧 `fg.eval.evaluate(expr, head=...)` 保持兼容；
- native-only，不先承诺 Soufflé/ProbLog parity；
- 运行现有 20-case regression、密封 6–9-case holdout、现有兼容测试；
- R0 三目标；R1/R2 只做 selected-row，比较 rowset/completeness/authored-node identity；
- 通过后才考虑公共 SDK/ADR，不在 F1–F4 提前发布。

### 8.3 两个 Meander 接入阶段

#### M1 — A0/P0 固定 Policy adapter

- Meander 生成/发布固定 `PolicyQueryContract`；
- Agent 只填写 server-authorized slots；
- plan v1 走 compatibility adapter；
- current/new evaluator shadow dual-run，旧路径仍为 truth；
- 不写 decision/latest/learning；
- 使用稳定后的真实 Query schema 做 Agent tool-call 测试。

#### M2 — 权限递增

顺序：

1. 固定 Policy 调用；
2. 允许从 Package 中选择 Policy；
3. 受限 Policy composition；
4. 最后才评估 Translator 和更高自由度的动态构造。

如果稳定 FactGraph 合同下 Agent 仍无法可靠生成 Query，应收缩 Agent 权限/合同，而不是继续扩张 FactGraph。

### 8.4 首轮明确排除

- What-if/Premise/Scenario；
- Operator/外部函数；
- Soufflé/ProbLog parity；
- Rule/Policy 数据库；
- Package persistence；
- Translator；
- Web UI；
- Action Middleware/Decide；
- 完整 historical replay；
- 多值 premise 和 Policy overlay。

## 9. 测试策略

测试与实现绑定，不再单独建立巨大 test program：

1. 每个 FactGraph slice：unit + protocol invariant + compatibility regression；
2. F2/F3：复用 20-case corpus 作为 regression；
3. F5：运行一次 6–9-case sealed holdout；
4. F4/F5：验证 exact anchors、三目标 live Explain、limited R1/R2；
5. F5 完成后：Meander A0 adapter + 实际 Agent tool loop；
6. 模型失败时先判断是 Agent contract/prompt 问题还是 deterministic result mismatch，不自动归因给 FactGraph。

Fresh holdout 建议覆盖：

- forbidden-field order 的排列不应成为公共正确性条件；
- 新的 static typed rejection；
- 相同 rows 下 Query vs Validation；
- complete-empty / incomplete-empty / non-empty；
- join × Any 所选语义的邻接形态；
- exact anchor 与 authored-node lineage。

## 10. 可并行与必须串行

可并行：

- F1 实现与 fresh holdout 的独立编写；
- F2 compiler 与 F3 DTO 的非集成部分（port/path 合同冻结后）；
- F4 anchor comparator 与 EvidenceGraph identity comparator；
- F3 后可用 frozen JSON 让 Meander 先写 adapter stub。

必须串行：

```text
semantic port/path contract
→ Policy lowering + total lineage
→ Query/result semantics
→ exact anchors + live Explain
→ native integration/holdout
→ Meander runtime adapter
→ real Agent test
```

## 11. 当前未决问题

下一次设计/实施 session 不应遗漏：

1. explicit semantic descriptor 是 `Rule` 内字段、sidecar contract，还是 schema-resolved frozen view；必须避免第二真值源；
2. SC-01 的两个候选语义如何最终裁定；
3. Policy AST 的最小 Python/JSON 表面，不应复制另一套不必要 DSL；
4. field navigation 是静态展开、compiler 注入 lookup，还是需要独立 operator；首轮只允许已授权 schema field；
5. exact anchor 的 canonical identity 是否跨 run、跨 snapshot、跨 compiler version；
6. EvaluationBundle 与当前 `EvaluateResult` 是包裹关系还是演进关系；
7. Rule/Policy 是否持久化：当前倾向 FactGraph 保持 library/value semantics，Meander Package/registry 负责产品持久化；尚未正式决定；
8. Agent 模型测试需要稳定 tool schema；当前 `.env` 据用户称已有 `OPENAI_API_KEY`，但双 provider arm 仍需要第二 provider 或明确降级为单臂 smoke；
9. UI 的 Policy tree、scenario coloring、approved/failed/unreached 和 source drill-down 待基础 DTO 稳定后再设计；
10. learning、Plan history 和 legacy adapter 必须保留原始版本语义，不可用新 Translator/Policy 回写重解释历史。

## 12. Git 与工作区边界

本文写入前观测到：

- 当前 branch：`v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`；
- `HEAD=61dee29b5007ed11c7fcbaae36b6f35059e88ba4`；
- sacred `master=854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0`；
- dirty baseline 为 112 项，属于用户及既有工作；
- 未 push、未 merge；
- probe 对 shipped `src/**` 零修改。

本 handoff 是新增 memory 文件，会使 untracked 计数增加；不要据此误判或清理既有 dirty baseline。

## 13. 下一 session 的最短启动指令

```text
先完整阅读：
1. workflow/memory/session_handoffs/2026-08-11_meander-factgraph-post-probe-session.md
2. tools/benchmarks/meander_qv_vertical_probe/reports/final_disposition.md
3. workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md

保持：
- 产品问题优先于 FactGraph 自我优化；
- 20 cases 是 regression，不是独立 holdout；
- 当前终态是 REVISE / NOT_CONTRADICTED / Agent NOT_TESTED；
- 不全面重构，不提前实现 What-if/Operator/UI/Translator；
- 先关闭四个窄阻塞决策，再按 F1–F5 → M1–M2 推进；
- 不修改用户 112 项 dirty baseline，不动 master，不 push/merge。

如果开始实施：先处理一次 closure archive hygiene，然后建立窄 native vertical slice；不要重新开启大型市场/架构调研。
```
