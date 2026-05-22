# Market Alignment Guide: AML 合规产品化方向

- Status: draft
- Type: guidance (概念指导文档，不直接驱动实施，为子蓝图提供方向约束)
- Created: 2026-04-03
- Last Updated: 2026-04-03
- Related Docs:
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
  - [2026-03-31_ontology-feasibility-analysis.md](./2026-03-31_ontology-feasibility-analysis.md)
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-04-03_market-alignment-guide.audit.md](./2026-04-03_market-alignment-guide.audit.md)

---

## 1. Problem

FactPy 是一个 auditable reasoning framework，核心引擎能力（证据树、规则追踪、置信度推理、审计导出）已经过多轮蓝图落地验证。但目前缺乏将这些能力对齐到具体合规市场痛点的系统性分析。

本文档基于三类市场信号：
1. **监管执法案例**：UK FCA 2025 年对 Monzo (£21M)、Barclays (£42M)、Nationwide (£44M) 的 AML 处罚
2. **从业者反馈**：Reddit AML/合规社区关于 AI 工具可审计性、关闭理由库、置信度分层的讨论
3. **专家访谈**：即将进行的与 Stellantis Bank CCO / 反洗钱报告官 Stefan Wieland 的访谈，以及此前关于分析师工作流的讨论

目的是：**诚实评估**当前代码实际能交付什么、哪些只是具备基础但离产品化有距离、哪些完全没有——以此指导后续子蓝图的优先级。

## 2. Goals

- 逐条对照市场痛点，基于代码验证给出能力矩阵（✅ 已有 / ⚠️ 有基础但不足 / ❌ 没有）
- 记录每个评估结论的代码依据（文件 + 行号），避免把"设计意图"误写为"已落地能力"
- 为后续产品化子蓝图提供优先级参考
- 收录外部市场情报的原始上下文，供后续引用

## 3. Non-Goals

- 不制定具体实施计划（那是子蓝图的事）
- 不修改任何代码
- 不把市场需求直接转化为功能规格
- 不评估商业模式或定价策略

## 4. 方法论声明

本文档的每个"系统能力"判断都经过以下流程：
1. 直接阅读源代码（非文档、非蓝图设想）
2. 验证函数签名、数据结构、实际返回值
3. 区分"代码中存在的能力"和"可以基于现有代码扩展的能力"
4. 对不确定的地方标注"待验证"

---

## 5. 市场信号汇总

### 5.1 FCA 执法案例（2025 年）

**事件**：FCA 在 2025 年对三家机构开出 AML 相关罚款，总计超过 £107M。2025 全年 AML 相关罚款超过 £124M。

**⚠️ 事实修正（2026-04-03 调研核实）**：
- 此前版本称三笔罚款为"协调性监管推进"——**不准确**。Monzo（7月7日）和 Barclays（7月14日）时间相近，但 Nationwide 是 12月12日，相隔五个月。FCA 未将三者描述为协调行动。准确表述为"执法趋势"。
- Barclays 金额为 **£42M**（非此前误写的 £43M），其中 £39.3M 针对 Stunt & Co 客户关系，£3.1M 针对 WealthTek。

**三笔罚款的具体发现**：

| 机构 | 金额 | 日期 | 核心问题 | 性质 |
|------|------|------|----------|------|
| Monzo | £21M | 2025-07-07 | CDD 程序未收集账户目的、预期交易模式、职业、财富来源。地址验证失败（申请人使用"10 Downing Street"等虚假地址）。2020-2022 年间违反 VREQ 开设超 34,000 个高风险账户 | 快速增长的金融科技超出了自身控制能力 |
| Barclays | £42M | 2025-07-14 | 未对两个特定客户（Stunt & Co、WealthTek）收集充分信息。Stunt & Co 一年内收到来自已知洗钱操作的 £46.8M。未回应触发事件（法院命令、警方搜查、董事被控洗钱） | **特定客户关系管理失败**，非企业级控制缺陷 |
| Nationwide | £44.1M | 2025-12-12 | 个人活期账户的 CDD 和客户风险评估系统性失败（2016-2021）。TM 依赖狭窄的回顾性规则和高阈值，不适应演变的洗钱类型。一客户 8 天内存入 £26M 欺诈性 Covid 休假款项未被发现 | 企业级系统性忽视 |

**关键区别**：三家机构的失败性质**不同**。Monzo 是增长超出控制、Barclays 是特定客户关系管理失败、Nationwide 是五年系统性忽视。不应简单归为同一类问题。

**共性痛点（跨案例提取，标注适用范围）**：

| 编号 | 痛点 | 主要适用 | 含义 |
|------|------|----------|------|
| F1 | TM 规则未随风险类型演变而调优 | Nationwide（最直接） | 规则存在但没有维护周期 |
| F2 | CDD 数据采集不充分/不一致 | Monzo、Nationwide | 同一标准未被一致执行 |
| F3 | 对触发事件的响应失败 | Barclays（最直接） | 外部信号（法院命令等）未被纳入升级路径 |
| F4 | 纸面控制与实际操作的差距 | 全部三家 | 审查员要的是执行证据，不是流程文档 |

**对我们的启示**：FCA 的执法趋势明确要求"可证明的、可审计的控制有效性证据"。这是真实的市场信号——但需要注意 Barclays 案例提醒我们，不是所有 AML 失败都是系统性的，特定客户关系管理是另一个维度。

来源：
- [FCA Final Notice - Monzo](https://www.fca.org.uk/publication/final-notices/monzo-bank-limited.pdf)
- [FCA Press Release - Barclays £42M](https://www.fca.org.uk/news/press-releases/fca-fines-barclays-42-million-poor-handling-financial-crime-risks)
- [AML Intelligence - Nationwide £44M](https://www.amlintelligence.com/2025/12/breaking-fca-fines-nationwide-44m-for-inadequate-financial-crime-controls/)
- [AML Watcher - Top FCA Fines 2025](https://amlwatcher.com/blog/top-fca-fines-in-2025-and-key-enforcement-findings/)

### 5.2 从业者反馈（Reddit AML/合规社区）

**关于 AI 工具可审计性的讨论**：

核心问题：审查员问"你的系统怎么决定这个客户是低风险的"，如果答案是"AI 说的"加上一堆不可解释的东西，那就是一个等着被发现的责任。

关键观察：
- 供应商实施团队经常无法解释为什么阈值设在某个值——"那是默认值"
- 大多数团队问起模型权重校准时"房间就安静了"
- 有人在找"per-decision evidence and replay"能力，几乎找不到

**关于关闭理由库的讨论**：

来自一位资深分析师的反馈：
- 如果合规团队写好关闭理由然后硬塞给分析师，分析师不信任、会自己改，因为他们不相信审查员拉出那条具体警报时这些语言能站住脚
- 如果分析师参与共建关闭理由库（基于他们实际审查过的警报），采纳率高得多
- 关键是前 20-30 条关闭理由要从真实工作中长出来，然后分析师遇到不匹配的模式时标记出来，库从真实工作中自然增长

**关于置信度分层的反馈**：
- 二元 flag/no-flag 是大多数团队卡住的地方，因为分析师对每个标记的警报做同样的调查
- 置信度分数 + 推理依据至少能让分析师在 Tier-2 内部做优先级判断
- 不完整数据是大多数误报的来源——不是因为规则不好，而是喂给规则的数据缺了字段，系统默认标记

### 5.3 专家访谈线索

**联系人 A**（匿名，每周可碰面）：
- 愿意在非工作时间（周一周二各 5 小时以外）协助
- 对商业模式构建和工具有经验
- 对范畴论有兴趣 → 可推动本体论方向（参见 `2026-03-31_ontology-feasibility-analysis.md`）

**联系人 B**：Stefan Wieland，Stellantis Bank CCO / 反洗钱报告官
- 直接面对 BaFin/ECB 审查
- 同时负责 DORA 合规
- 能验证：审查员实际要看什么、TM 规则调优周期实操、供应商决策逻辑审计的市场需求强度

**建议访谈问题**（供后续准备用）：
1. 审查员来了之后，具体要你展示什么？（验证审计导出格式是否足够）
2. 你现在的 TM 规则调优周期是什么？谁负责？（验证规则生命周期管理需求）
3. 对供应商的决策逻辑审计，你们现在怎么做的？（验证可解释性的市场需求强度）
4. DORA 对 ICT 风险管理和第三方供应商审计的具体要求是什么？（验证审计报告格式需求）
5. 你见过哪些供应商能做到 per-decision evidence trail？（竞品情报）

### 5.4 竞品可解释性分析（2026-04-03 调研）

**调研方法**：对 7 家主要 AML/合规供应商的可解释性能力进行调研，重点关注"实际交付什么"而非营销声明。

#### 5.4.1 供应商概览

| 供应商 | 可解释性交付 | LLM 使用 | 形式化溯源？ |
|--------|-------------|----------|-------------|
| **Lucinity** | RAG 源引用 + AI 操作审计日志 + 双 LLM 交叉验证 | 是（GenAI Copilot "Luci"） | 否 |
| **NICE Actimize** | 声称"可追溯到底层数据点"，未公开具体格式 | 是（X-Sight ActOne 代理层） | 否 |
| **Featurespace** | 每个警报附带 reason codes + 模型治理文档 | 否（传统 ML + 行为分析） | 否 |
| **ComplyAdvantage** | 每个决策附带自然语言推理 + 声称不可变审计追踪 | 可能（未确认） | 否 |
| **Napier AI** | 特征贡献 + 源记录关联 + 全链透明 | **明确反对 LLM 决策**（CTO 公开表态） | 否 |
| **SymphonyAI Sensa** | 三个专用代理（摘要/叙述/网络研究）+ 源归因 | 是（基础模型） | 否 |
| **Nasdaq Verafin** | 源引用叙述 + **唯一明确命名 CoT 的供应商** | 是（GenAI Copilot） | 否 |

#### 5.4.2 市场分层

市场正在形成三个阵营：

**阵营 A — LLM 用于解释生成（非决策）**：Lucinity、SymphonyAI、Nasdaq Verafin、NICE Actimize
- LLM 叙述和总结由底层规则/ML 引擎做出的决策
- **没有供应商用 LLM 作为主要决策者**

**阵营 B — 传统 ML + 事后解释**：Featurespace、ComplyAdvantage
- 行为分析 + reason codes 或自然语言覆盖层

**阵营 C — 明确反对 LLM 决策**：Napier AI
- 专用分类模型，内在可解释性

#### 5.4.3 市场空白

**没有任何供应商提供计算机科学意义上的形式化溯源**（formal provenance）：
- 没有证明树（proof trees）
- 没有证据图（evidence graphs）
- 没有推理链的形式化验证
- 没有运行时决策捕获（runtime decision capture）——大多数系统用事后解释替代

行业分析（Consilient, 2026）指出核心问题：大多数 AML 程序能解释治理设计如何工作，**但无法提供特定决策执行时刻实际发生了什么的保留证据**。

来源：
- [Lucinity: Explainability in GenAI Copilots](https://lucinity.com/blog/ensuring-explainability-and-auditability-in-generative-ai-copilots-for-fincrime-investigations)
- [Napier AI: Compliance-First AI](https://www.napier.ai/post/how-to-implement-compliance-first-ai-for-aml)
- [Consilient: Human in the Loop 2026](https://consilient.com/human-in-the-loop-2026-aml-governance)
- [Verafin: Agentic AI Workforce](https://ir.nasdaq.com/news-releases/news-release-details/nasdaq-verafin-announces-launch-its-agentic-ai-workforce)

#### 5.4.4 对我们的含义

FactPy 的证据树（typed evidence trees with formal provenance links）在当前竞品中**没有对标物**。这是一个真实的差异化点——前提是我们能把它包装成合规官和审查员能用的形态。

---

## 6. 能力矩阵：代码验证

### 6.1 ✅ 单决策证据链（Per-Decision Evidence Trail）

**市场对应**：F4（纸面 vs 实际差距）、Reddit 关于"show me how your system decided"

**代码验证**：

- **函数**：`build_candidate_evidence_tree()` — `src/factpy_kernel/core/store/_candidate_evidence_tree.py` L12-54
- **返回结构**：
  - `binding`：变量赋值（哪些值参与了这个决策）
  - `rule_refs`：规则引用（哪条规则触发了这个结论）
  - `pred_witnesses`：谓词见证（哪些断言支撑了这个推理，含 `asrt_id`）
  - `non_fact_steps`：约束检查步骤
  - `children`：层级子节点（递归证据）
- **交付路径**：
  - API：`/v1/.../explain-tree`（结构化 JSON）
  - API：`/v1/.../explain-narrative`（人类可读叙述）
  - API：`/v1/.../explain-nl`（自然语言问答）
  - 静态导出：`render_audit_static_site()` — `audit/static_ui.py` L40-123
    - 生成多文件 HTML 站点：runs / decisions / assertions / rule_traces / candidate_evidence / indexes

**评估**：这是当前最强的能力。每个候选推理结论都有完整的因果链路，从变量绑定到谓词见证到规则引用。这直接回应了 Reddit 上"per-decision evidence and replay"的需求（evidence 部分），也是面对审查员时"证明你确实按流程做了"的核心武器。

**局限**：
- 多引擎间证据树的结构和深度不完全一致（Native/Souffle 最完整，ProbLog/PyReason 有 provenance 但结构不同）
- 证据树是只读回溯，不是可重放的执行记录（见 6.8）

---

### 6.2 ✅ 规则追踪（Rule Trace with Provenance）

**市场对应**：Reddit 关于"阈值为什么设在这里"、"vendor due diligence on AI-driven tools"

**代码验证**：

- **数据结构**：`RuleTraceArtifact` — `core/store/_trace.py` L136-154
  - 包含 `invocations: tuple[RuleTraceInvocation, ...]`
- **每次调用记录**（`RuleTraceInvocation` L88-133）：
  - `original_where`：原始查询条件
  - `rewritten_where`：重写后的查询条件
  - `bindings`：每个输出行的变量绑定
  - `output_rows`：产生的结果
  - `pred_witnesses`：引用了哪些断言
  - `non_fact_steps`：约束检查
  - `ruleref_links`：递归规则调用

**评估**：规则追踪完整记录了"这条规则用了什么输入、匹配了什么条件、产生了什么输出"。对于回应"阈值为什么设在这里"——如果阈值在规则条件中是显式的，追踪能展示它被如何使用。

**局限**：
- **没有时间维度**：`RuleTraceInvocation` 没有 `timestamp`、`duration` 字段。无法回答"这次推理花了多久"
- 追踪是记录性质，不是可重放的（见 6.8）

---

### 6.3 ⚠️ 置信度带推理（Confidence with Reasoning）

**市场对应**：Reddit 关于"置信度 + 推理依据让分析师在 Tier-2 内做优先级判断"

**代码验证**：

- **数据结构**：`CertaintySummary` — `core/annotation/_certainty.py` L25-40
  - `conditions: tuple[ConditionImpact, ...]`
    - 每个 `ConditionImpact` 包含：`atom_key`（哪个条件）、`node_kind`、`weight`（规则编写时声明的权重）、`impact`（weight × confidence 的乘积）
  - `aggregate_certainty: float | None`（加权聚合置信度）
  - `aggregation: str`（聚合策略名）
- **聚合策略**（L99-160）：
  - `"bottleneck"`：取最弱环节（min(weight × confidence)）
  - `"additive"`：加权求和
- **前提条件**（L46-54）：
  - 规则必须声明 `condition_weights`
  - 候选项必须标记 `confidence_kind="certainty"`
  - 必须有证据树
  - **三个条件缺任何一个，返回 `None`**

**评估**：当条件满足时，置信度解释是完整的——你能看到每个条件的权重、影响力、聚合方式。这远超市场上"一个裸浮点数"的水平。

**局限**：
- **条件性太强**：如果规则作者没有声明 `condition_weights`，置信度就只是一个裸 `float`，没有任何解释。这意味着"置信度带推理"不是系统默认行为，而是需要规则作者配合的可选特性
- 这是一个重要区别：对外说"我们的置信度有推理链路"时，必须说清楚前提条件

---

### 6.4 ⚠️ 降级支撑检测（Degraded Support Detection）

**市场对应**：Reddit 关于"不完整数据是大多数误报的来源"

**代码验证**：

- **函数**：`build_degraded_candidate_evidence_tree()` — `core/store/_candidate_evidence_tree.py` L57-100
- **触发条件**（`query.py` L100-106）：当 `support_kind` 不在 `_WITNESS_BEARING_SUPPORT_KINDS` 但在 `_DEGRADED_SUPPORT_KINDS` 或 `_PROVENANCE_BEARING_SUPPORT_KINDS` 时
- **返回结构**（L88-95）：
  - `"node_kind": "degraded_support"`
  - `"witness_status": "degraded"`
  - `"children": []`（空）
  - 叙述层会说："Candidate {id} uses degraded support kind {kind} without witness artifacts"

**评估**：系统**能检测到**"这个候选项的支撑证据是降级的"——即证据不完整或不可用。

**局限**（关键）：
- **不能定位具体缺失字段**。系统知道"证据降级了"，但不知道**为什么**降级。不会告诉你"因为 entity.phone_number 字段缺失导致条件 b0.a2 无法匹配"
- 要做到 Reddit 说的"区分数据质量问题和真正的风险信号"，需要在降级检测之上增加一层：追踪哪个条件因为哪个字段缺失而降级
- 这是"有基础但离产品需求有距离"的典型案例

---

### 6.5 ⚠️ 候选项处置与元数据（Candidate Accept Metadata）

**市场对应**：关闭理由库、分析师工作流

**代码验证**：

- **接受机制**：`accept_many_candidate_sets()` — `core/derivation/accept.py` L249-264
- **处置状态**（accept 返回值，非候选项自身状态）：
  - `"ACCEPTED"` — 成功接受
  - `"DUPLICATE"` — 重复（幂等）
  - `"BLOCKED_DEPENDENCY"` — 依赖阻塞
  - `"FAILED_VALIDATION"` — 校验失败
  - `"FAILED_RUNTIME"` — 运行时异常
- **可附加元数据**（`AcceptOptions` L34-36）：
  - `approved_by: str | None` — 审批人
  - `note: str | None` — 自由文本备注
- 这些元数据通过 write metadata 持久化到账本

**评估**：`approved_by` + `note` 是关闭理由的最小可用形态。有"谁批准的"和"为什么"的记录点。

**局限**：
- **只有自由文本 `note`**，没有结构化的关闭理由代码、分类体系、模板匹配
- **没有拒绝路径**：accept.py 处理的是"接受候选项并写入账本"，但没有对应的"明确拒绝候选项并记录拒绝理由"的路径
- **没有关闭理由库**：Reddit 那位说的"前 20-30 条关闭理由从真实工作中长出来"——完全没有这个机制
- **候选项自身没有状态机**：候选项生成时状态为 `"generated"`，accept 操作写入账本但不改候选项状态。没有 pending → investigating → escalated → closed 的生命周期

---

### 6.6 ⚠️ 按置信度排序的分诊视图（Confidence-Based Triage）

**市场对应**：Reddit 关于"置信度让分析师在 Tier 内做优先级判断"

**代码验证**：

- **置信度聚合**：`aggregate_confidence()` — `core/view/confidence.py` L8-43
  - 策略：`"max"` / `"mean"` / `"median"` / `"prefer_source"`
  - 返回 `float | None`
- **视图投影**：`project_display_facts()` — `core/view/projector.py`
  - **排序逻辑**（L87）：按事实元组的字符串表示排序
    ```python
    output[pred_id] = sorted(facts, key=lambda fact: tuple(str(part) for part in fact))
    ```

**评估**：置信度聚合函数存在且可用，但视图层**按事实内容排序，不按置信度排序**。

**局限**：
- 不能查询"给我 Tier-2 内按置信度从高到低排列的前 20 个候选项"
- 置信度作为计算工具存在，但没有暴露为分诊排序的一等维度
- 需要在视图层增加按置信度排序的投影策略

---

### 6.7 ❌ 规则生命周期管理（Rule Lifecycle Tracking）

**市场对应**：F1（TM 规则多年未调优）

**代码验证**：

- **RuleSpec**（`core/rules/rule_ir.py` L28-33）：只有 `rule_id`、`version`、`select_vars`、`where`、`expose`
- **RuleSpec TypedDict**（`core/store/types.py` L27-33）：同上，加 `body_confidences`
- **FileAuthoringRegistry**（`authoring/registry_fs.py` L35）：
  - 清单（manifest）结构（L101-109）：`path`、`digest`、`rule_id`、`version`
  - **没有**：`registered_at`、`created_at`、`last_modified`、`last_executed`
- **SDKRegistry**（`sdk/registry.py`）：包装 FileAuthoringRegistry，同样无时间戳

**评估**：**完全没有规则的时间维度元数据。** 无法回答：
- "这条规则什么时候创建的？"
- "上次修改是什么时候？"
- "上次执行是什么时候？"
- "这条规则被执行了多少次？"
- "触发率是多少？"
- "误报率是多高？"

这正是 FCA 罚的核心问题之一——规则存在但没人维护。我们的系统目前甚至没有追踪这些信息的数据结构。

---

### 6.8 ❌ 决策重放（Decision Replay）

**市场对应**：Reddit 关于"per-decision evidence and replay"

**代码验证**：

- 代码中的"replay"（`apply_execute.py` 中的 `_build_apply_execute_replay_result()`）是**幂等性机制**：重复提交同一 `apply_request_id` 的请求时跳过重复执行
- **不是**"给定同一输入重新执行同一规则验证可复现性"的语义

**评估**：**没有决策重放能力。** 不能：
- 拿一条历史决策的输入重新跑一遍
- 验证"如果当时数据不同，结果会怎样"（what-if 分析）
- 对比两次执行的差异

证据树是"发生了什么"的记录，不是"可以重来一遍"的机制。

---

### 6.9 ❌ 关闭理由库（Closure Reason Library）

**市场对应**：Reddit 关于"网络效应"、分析师信任与采纳

**代码验证**：无对应代码。

**需要的完整闭环**：
```
分析师关闭警报 → 撰写/选择关闭理由
→ 理由作为版本化模板存入注册中心
→ 其他分析师看到按匹配度排序的建议关闭理由
→ 分析师可标记"这条理由不适用"并提交新理由
→ 库从真实工作中自然增长
```

**可复用的基础**：
- `FileAuthoringRegistry` 的版本化存储机制可以承载关闭理由模板
- `AcceptOptions.note` 是关闭理由的最小写入点
- 但缺少：关闭理由 schema、匹配推荐机制、反馈回路、分析师交互面

---

### 6.10 ❌ 警报/案件生命周期（Alert Lifecycle）

**市场对应**：F3（升级流程崩溃）、分析师工作流

**代码验证**：

- `CandidateSet` 状态目前只有 `"generated"`
- `accept` 操作写入账本但不改候选项状态
- 没有：打开 → 分配 → 调查 → 升级 → 关闭的状态机
- 没有：分配机制、SLA 追踪、队列路由、负载感知

**评估**：当前系统是推理引擎层面的，不是案件管理层面的。这不是缺陷——这是产品层级的区别。但如果要面向分析师卖产品，这一层是必须的。

---

## 7. 综合能力矩阵

```
                                          代码      产品化
市场痛点                                  基础      距离        优先级建议
─────────────────────────────────────────────────────────────────────────
"证明你的系统怎么决策的"                   ✅ 强     近          → 核心卖点
 (证据树 + 叙述 + HTML 导出)

"阈值/权重为什么设在这里"                  ⚠️ 有条件  中         → 需要强制声明或默认权重
 (需 condition_weights 声明)

"数据缺失导致误报"                        ⚠️ 有基础  远         → 需增加字段级归因
 (能检测降级，不能定位字段)

"按风险排序分诊"                          ⚠️ 有基础  中         → 视图层增加置信度排序
 (聚合有，排序没有)

"谁批准的、为什么"                        ⚠️ 最小    中         → 结构化关闭理由
 (approved_by + note)

"规则多久没调过了"                        ❌ 没有    远         → 规则元数据 + 监控
 (零时间维度元数据)

"触发率 / 误报率"                         ❌ 没有    远         → 执行统计管线
 (零统计指标)

"决策可重放 / what-if"                    ❌ 没有    远         → 需要新的执行模型
 (幂等性 ≠ 重放)

"关闭理由库 / 网络效应"                    ❌ 没有    远         → 新子系统
 (无对应代码)

"警报生命周期 / 案件管理"                  ❌ 没有    远         → 产品层而非引擎层
 (候选项无状态机)
```

---

## 8. 战略方向建议

### 8.1 短期：强化已有优势（0-3 个月方向）

**原则**：不要急着补短板，先把长板磨到极致。

当前最强的能力是"单决策证据链 + 规则追踪 + 审计导出"。这正好命中了市场最尖锐的痛点（FCA 罚款的核心、Reddit 讨论的焦点）。

方向：
- 确保 `condition_weights` 有合理的默认策略，降低"置信度带推理"的启用门槛
- 审计 HTML 导出针对 FCA / BaFin 审查员的实际需求做格式验证（Stefan Wieland 访谈验证）
- 证据树叙述层的语言质量（审查员和分析师能不能直接看懂）

### 8.2 中期：产品化桥接（3-6 个月方向）

**原则**：在引擎层和终端用户之间搭建薄产品层。

方向：
- 候选项状态机（至少：generated → assigned → reviewed → closed）
- 结构化关闭理由（`AcceptOptions` 扩展 + 关闭理由 schema）
- 视图层按置信度排序
- 规则注册中心增加时间戳元数据（`registered_at`、`last_executed`）

### 8.3 长期：生态壁垒（6-12 个月方向）

**原则**：构建网络效应和切换成本。

方向：
- 关闭理由库（从分析师真实工作中增长，带反馈回路）
- 规则调优仪表盘（触发率、误报率、上次审查时间）
- 多租户注册中心（跨机构共享规则集和关闭理由）
- 决策重放 / what-if 分析
- 本体论层（参见 `2026-03-31_ontology-feasibility-analysis.md`，联系人 A 可推动范畴论方向）

### 8.4 监管框架分析（2026-04-03 调研修正）

#### 8.4.1 前提问题：FactPy 算不算"AI"？

**⚠️ 这是最关键的问题——它决定了整个监管对齐叙事是否成立。**

**EU AI Act Article 3(1) 对"AI 系统"的定义**：一个机器系统，设计为以不同程度的自主性运行，可能在部署后表现出适应性，并从输入推断如何生成输出。EU 委员会 2025 年 2 月指南进一步澄清：

- "基于自然人定义的规则来自动执行操作的系统"**不是** AI 系统
- "经典启发式方法"使用"预定义规则或算法推导解决方案，不根据输入输出关系调整模型"——**排除在外**
- **但是**：EU AI Act 也明确将"logic- and knowledge-based approaches"列为 AI 技术，包括"知识表示、归纳逻辑编程、知识库、推理和演绎引擎、符号推理、专家系统"

**按后端分类**：

| 后端 | 分类 | 依据 |
|------|------|------|
| 纯规则引擎（Native） | **很可能不算 AI** | 人工编写规则，无自主性，无适应性，无学习 |
| Datalog (Souffle) | **灰色地带** | 演绎推理被 EU AI Act 列为 AI 技术，但 Article 3(1) 要求自主性+适应性+推理三者同时具备（conjunctive reading），Souffle 缺前两者 |
| ProbLog | **很可能算 AI** | 概率推理明确属于统计方法 + 逻辑编程的结合 |
| PyReason | **灰色地带到可能算** | 不确定性传播的时间推理 |

**关键法律问题**：Article 3(1) 的三个条件（自主性 + 适应性 + 推理）是 AND 关系还是 OR 关系？EU 委员会指南倾向于 AND（conjunctive），即三者必须同时满足。如果是 AND，则即使使用 Datalog 推理，因为缺少自主性和适应性，FactPy 可能不算 AI。

**BaFin 的立场**：BaFin Prinzipienpapier BDAI（2021）明确区分了规则方法（regelbasierte Verfahren）和机器学习，但也说其原则"通常适用于所有类型的算法支持的决策过程"。BaFin 承认这里有"fließender Übergang"（流动的过渡）而非硬边界。

来源：
- [EU Commission Guidelines on AI System Definition](https://digital-strategy.ec.europa.eu/en/library/commission-publishes-guidelines-ai-system-definition-facilitate-first-ai-acts-rules-application)
- [BaFin Prinzipienpapier BDAI (English)](https://www.bafin.de/SharedDocs/Downloads/EN/Aufsichtsrecht/dl_Prinzipienpapier_BDAI_en.pdf)
- [Orrick: EU Commission Clarifies Definition](https://www.orrick.com/en/Insights/2025/04/EU-Commission-Clarifies-Definition-of-AI-Systems)

#### 8.4.2 DORA：以 ICT 供应商身份适用（非 AI）

**DORA 几乎确定适用于 FactPy——但不是因为我们是 AI，而是因为我们是 ICT 服务。**

DORA Article 3(21) 将"ICT 服务"定义为通过 ICT 系统持续提供的数字和数据服务。Recital 79 明确列出"云计算服务、**软件解决方案**和数据相关服务"。

任何向金融实体提供持续服务的软件供应商都属于"ICT 第三方服务提供商"。金融实体客户必须将我们纳入其 ICT 第三方风险登记册（Article 28 的"信息登记册"）。

**但这意味着**：DORA 对我们的要求是运营韧性（安全、事件报告、退出策略），**不是 AI 治理**。

**"关键 ICT 第三方"认定**：需要满足严格的量化标准（系统性影响、至少 10% 客户缺乏替代方案等）。作为小众合规规则引擎供应商，被认定为"关键"的可能性极低。

来源：
- [EBA Q&A on ICT services definition](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2024_7290)
- [Noerr: Classification of IT service providers under DORA](https://www.noerr.com/en/insights/classification-of-it-service-providers-under-dora)

#### 8.4.3 正确的产品定位

**之前的叙事（已废弃）**：
> ~~"FactPy 满足 BaFin 对 AI 的可解释性要求"~~ — **过度主张**。如果我们的规则引擎不算 AI，就不能声称满足 AI 监管要求。

**修正后的定位**：

> **FactPy 不是被监管的 AI 系统——它是帮助客户满足 AI 合规要求的审计基础设施。**
>
> 客户使用 ML/AI 做决策时，需要满足 BaFin 的 Nachvollziehbarkeit（可追溯性）和 Erklärbarkeit（可解释性）要求。FactPy 提供的 formal provenance trace 是实现这些要求的技术手段。

**三种市场进入角度**：

1. **审计基础设施**：客户的 AI/ML 系统做出决策 → FactPy 记录决策过程的形式化证据 → 满足 BaFin/EU AI Act 的可追溯性要求
2. **ICT 合规**：作为 DORA 下的 ICT 服务提供商，FactPy 本身的审计追踪能力降低了客户的第三方风险管理负担
3. **规则引擎替代 ML**：对于某些用例，确定性规则引擎 + formal provenance 可能比 ML + 事后解释更适合监管要求——因为规则引擎天然满足可复现性和可验证性

#### 8.4.4 监管术语对齐

**⚠️ BaFin 从不使用"Chain-of-Thought"。** 搜索 "Chain of Thought" + BaFin/AML/KYC 返回零结果。

德语监管术语与 FactPy 能力的映射：

| 监管术语（德语） | 含义 | FactPy 对应 |
|-----------------|------|-------------|
| **Nachvollziehbarkeit** | 可追溯性：任何形式的有文档记录的逐步决策追踪 | ✅ 证据树 + 规则追踪 |
| **Erklärbarkeit** | 可解释性：能向非技术人员解释决策 | ✅ explain-narrative + explain-nl |
| **lückenlose Protokollierung** | 无间断记录：完整记录决策、版本、事件 | ⚠️ 决策记录有，版本时间戳没有 |
| **Lebenszyklusorientiert** | 生命周期导向：从创建到停用 | ❌ 只有执行时快照 |

#### 8.4.5 CoT 可靠性的实证证据

IT Finanzmagazin 文章将 LLM CoT 作为三种 XAI 路径之一。但 CoT 的忠实性在学术界已被广泛质疑：

| 研究 | 发现 |
|------|------|
| Anthropic (2025-05), "Reasoning Models Don't Always Say What They Think" | Claude 3.7 Sonnet 的 CoT 忠实度仅 **25%**；安全场景下仅 **41%** |
| Barez et al. (Oxford/Bengio, 2025), "Chain-of-Thought Is Not Explainability" | ~25% 的 CoT 论文错误地将其当作可解释性工具；CoT 输出经常不忠实于模型的实际内部计算 |
| Arcuschin et al. (ICLR 2025) | 模型对相反问题生成逻辑矛盾的论证 |

**审计标准结构性偏向确定性方法**：ISA 500 要求审计证据"充分且适当"（可靠性）；SOC 2 要求"一致的、可审查的过程"；EU AI Act 区分"ante-hoc"（内在可解释，如规则系统）和"post-hoc"（事后解释，如 SHAP/LIME），前者在合规上更有利。

**但注意**：没有找到审计师明确说"我们拒绝 CoT、偏好 provenance"的直接调查。证据是结构性的（审计标准要求的属性，provenance 天然满足，CoT 不能保证），不是直接比较研究。

来源：
- [Anthropic: Reasoning Models Don't Say What They Think](https://www.anthropic.com/research/reasoning-models-dont-say-think)
- [Oxford AIGI: Chain-of-Thought Is Not Explainability](https://aigi.ox.ac.uk/publications/chain-of-thought-is-not-explainability/)
- [arXiv:2503.08679 - CoT In The Wild Is Not Always Faithful](https://arxiv.org/abs/2503.08679)

---

## 9. 待验证清单

### 已通过调研回答的问题（2026-04-03）

| 编号 | 问题 | 结论 |
|------|------|------|
| V7 | 竞品中有谁能做到 per-decision evidence？ | **没有。** 7 家主要供应商均无 formal provenance。市场标准是审计日志 + 自然语言摘要 + reason codes（见 §5.4） |
| V8 | FactPy 是否算"AI"（EU AI Act / BaFin 定义）？ | **纯规则引擎很可能不算；Datalog 灰色地带；ProbLog 很可能算**（见 §8.4.1）|
| V9 | DORA 是否适用于合规软件供应商？ | **是，作为 ICT 服务提供商**，不是作为 AI（见 §8.4.2）|
| V10 | BaFin 是否使用"Chain-of-Thought"概念？ | **不使用。** BaFin 用 Nachvollziehbarkeit 和 Erklärbarkeit，不指定技术实现（见 §8.4.4）|

### 仍需通过访谈/调研回答的问题

| 编号 | 问题 | 验证渠道 | 关联能力 |
|------|------|----------|----------|
| V1 | 审查员实际要看的审计报告格式是什么？ | Stefan Wieland 访谈 | 6.1 审计导出 |
| V2 | TM 规则调优在实践中谁负责、周期多长？ | Stefan Wieland 访谈 | 6.7 规则生命周期 |
| V3 | 对 AI 供应商的决策逻辑审计目前怎么做？ | Stefan Wieland 访谈 | 6.1, 6.2 |
| V4 | DORA 下 ICT 供应商的具体合同和审计义务？ | Stefan Wieland 访谈 + 法规研究 | 8.4.2 DORA |
| V5 | 关闭理由库在实践中的采纳障碍是什么？ | Reddit 社区 + 分析师访谈 | 6.9 关闭理由库 |
| V6 | 分析师实际的 alert-to-close 工作流长什么样？ | 分析师访谈 | 6.10 警报生命周期 |
| V11 | Datalog 演绎引擎在 EU AI Act 下是否真的属于灰色地带？需要法律意见 | 法律顾问 | 8.4.1 AI 定义 |
| V12 | 客户是否愿意为 formal provenance 付费，还是 reason codes + 审计日志已经足够？ | Stefan Wieland + 市场验证 | 5.4 竞品 |

---

## 10. 对子蓝图的约束

本文档作为指导性文档，对后续子蓝图施加以下约束：

1. **诚实原则**：子蓝图引用本文档的能力评估时，必须区分"已有"和"有基础但需要扩展"，不能把 ⚠️ 写成 ✅
2. **代码验证原则**：任何声称的系统能力必须附带代码引用（文件 + 行号或函数名），不以蓝图设想替代代码现实
3. **优先级原则**：短期子蓝图应聚焦 ✅ 能力的打磨，而非 ❌ 能力的从零建设
4. **访谈驱动原则**：V1-V7 待验证问题的答案应回流到本文档，用于修正能力矩阵和优先级

---

## 11. Outcome

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
