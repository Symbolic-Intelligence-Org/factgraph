# Rainbird 证据链比较笔记

- Status: maintained
- Type: external comparison
- Authority: external comparative rationale; not current implementation truth
- Usage:
  - 可用于 blueprint 中的证据链、delivery shape、explainability 对照讨论
  - 不应单独作为本项目 contract 或实现承诺

## 评估：证据链设计的完整性 vs. Rainbird 的实现

> **Last reviewed against codebase: 2026-03-20**
> 本节的"当前状态"列反映截至该日期的代码真相（含 evidence tree 六轮实现、Souffle partial witness、live permalink、NL explain）。

### 一、Rainbird 证据链设计的核心结构（先建立比较基线）

Rainbird 的证据链由四个层次构成，形成一个完整闭环：

```
Result (factID + certainty)
  └─ Evidence Tree (recursive rule-chain traversal)
       ├─ Rule Node: 哪条规则触发 + max certainty cap
       │    ├─ Condition 1 → factID (可递归展开)
       │    ├─ Condition 2 → factID (可递归展开，可选条件)
       │    └─ Condition N → leaf (inject / answer / KM global)
       └─ Salience Chart: 每个条件对最终 certainty 的 impact breakdown
  └─ NL Explain (BETA): 把树结构转为自然语言"为什么"
  └─ Interaction Log: 完整 session 事件流（queries/answers/injects/datasources）
```

交付形态三种并存：
1. **Visual evidence URL**（可嵌入 iFrame，适合 case management 系统）
2. **REST API 递归遍历**（开发者自定义 UI）
3. **NL Explain endpoint**（生成自然语言解释，BETA）

---

### 二、蓝图当前证据链定义的完整性评估

对照 Rainbird，逐层检查蓝图当前的定义：

#### 层 1：Result 载体（`CandidateSet` + `support_digest/support_kind`）

| 维度 | Rainbird | 当前状态 | 差距 |
|---|---|---|---|
| 结论对象 | `subject + relationship + object + certainty + factID` | `CandidateSet` 携带 `candidate_id` + `support_digest` + `support_kind`；`candidate_id` 即为 proof entry handle，可串联 `ProofReceipt` readback | ✅ `factID` 等价物已存在 |
| 置信度语义 | 明确是 certainty-weighted（非概率），1-100 整数，有 rule-level cap | `confidence` 语义未分离（certainty vs probability 混用风险，母蓝图 §5.4 已点出） | ⚠️ 语义分离问题已识别但未解决 |
| 多结果 | 每个 result 有独立 evidence tree | 每个 candidate 有独立 `support_digest` + `support_kind`，可各自展开为独立 `candidate_evidence_tree` | ✅ 已明确 |

#### 层 2：Evidence Tree（proof/provenance carrier）

| 维度 | Rainbird | 当前状态 | 差距 |
|---|---|---|---|
| 树的入口 | `factID` → `GET /analysis/evidence/{factID}/{sessionID}` | `candidate_id` → `Store.get_candidate_support_digest()` → `ProofReceipt` → recursive `candidate_evidence_tree`；runtime 提供 `GET /v1/runtime/sessions/{sid}/evidence/candidate/{cid}` HTML permalink | ✅ per-result proof entry point 已存在 |
| 递归结构 | 每个 condition 有 `factID`，可无限递归到 leaf | `candidate_evidence_tree` 已实现递归展开：`rule_ref_edges` → child `ProofReceipt` → 递归子树；`_MAX_RECURSION_DEPTH=8`；cycle detection via `ancestry: set[str]`；4 种 terminal reason（`child_support_unavailable` / `artifact_missing` / `cycle` / `depth_limit`） | ✅ 递归结构与终止条件已定义 |
| 条件来源类型 | 6 种明确的 source（Rule/Inject/Answer/Datasource/KM/Synthesised），颜色编码 | `node_kind` 已提升为 carrier-level provenance-role taxonomy（6 类：structural / witness / constraint / rule_chain / terminal / degraded）；但更深的 assertion-origin taxonomy（direct write / derivation accept / import）仍 deferred | ⚠️ provenance-role 层已关闭；assertion-origin 层仍开放（依赖 assertion metadata schema） |
| 可选条件处理 | optional condition 缺失时生成 synthesised fact at 0%，在树中显示为 strikethrough | `unresolved_support` + `unresolved_reason` 机制可表达"子证明不可用"；但 **optional condition 语义**（rule IR 级别的"条件缺失但允许跳过"）仍未实现 | ⚠️ 结构性 unresolved 机制存在，但 authoring-level optional 语义仍为 deferred |

#### 层 3：Salience / Impact Breakdown（certainty 分解）

| 维度 | Rainbird | 当前状态 | 差距 |
|---|---|---|---|
| 条件权重 | 每个条件有 explicit weight，impact = f(weight, condition certainty) | salience/impact 归属已冻结为 annotation/value-semantics 层，compute-time = query-time；**blocked on certainty/weight vocabulary**（当前不存在） | ⚠️ 归属问题已关闭，但实现 blocked on 前置基础设施 |
| Salience Chart | 独立视图，显示每条件的 actual impact vs max possible impact | 无对应概念；当前 tree summary 仅有结构性统计（node counts / assertion counts / recursive depth），不含数值权重 | ❌ **gap**：impact breakdown 的数据结构需要 certainty/weight 基础设施才能定义 |
| Rule-level certainty cap | 规则本身有 max certainty 上限，独立于条件 certainty | 未实现 | ⚠️ 规则级 certainty 上限是 authoring contract 问题，属于 certainty/weight 基础设施的一部分 |

#### 层 4：Audit / Session Trace（interaction log）

| 维度 | Rainbird | 当前状态 | 差距 |
|---|---|---|---|
| Session 级别的事件流 | `GET /analysis/interactions/{sessionID}` 返回完整事件序列（query/inject/question/answer/result/error），可导出 CSV | audit package 对应 run/candidate/decision/apply event，结构类似；audit query 已支持 `get_candidate_evidence_tree()` | ✅ 概念覆盖；Rainbird 侧是 session 级聚合，本项目是 package 导出 + candidate-level tree |
| Live vs offline audit | Rainbird 的 evidence 和 interaction log 是 live API，保留 7-30 天 | audit 仍为离线 package 消费；但 runtime 现已提供 session-bound live evidence permalink（HTML GET routes，session 生命周期内可用） | ⚠️ live evidence 已存在但仅限 session scope；durable（跨 session）live URL 仍未实现 |

#### 层 5：对外交付形态（最终成品方式）

Rainbird 的三种交付形态现已在本项目中各有对应落点：

| 维度 | Rainbird | 当前状态 | 差距 |
|---|---|---|---|
| Visual evidence URL | Rainbird Agent（iFrame/URL），visual evidence tree URL | `GET /v1/runtime/sessions/{sid}/evidence/candidate/{cid}` → HTML；audit static site 也渲染 candidate evidence page | ✅ session-bound live permalink + offline static page 均存在 |
| Structured API | REST API 递归遍历，明确 schema | 7 个 explain POST 端点（explain-tree / summary / narrative / support / nl / rule-trace / explain-fact），返回 structured JSON | ✅ 已存在 |
| NL Explain | NL Explain endpoint（BETA） | `POST .../queries/explain-nl` 支持 `kind="candidate"` 和 `kind="rule_run"`；当前为 **deterministic template-based** rendering，不依赖 LLM | ✅ deterministic NL 已存在；LLM-powered NL explain 仍为候选方向（若需更高质量的自然语言输出） |
| 竞争差异化 | visual evidence tree + salience chart + NL explain 的组合 | evidence tree + NL explain 已具备；**salience chart 仍为空白**（blocked on certainty/weight）；temporal logic + deontic reasoning 是本项目独有的差异化来源（Rainbird 不具备） | ⚠️ salience chart 是与 Rainbird 对比中仍缺失的主要可视化能力 |

---

### 三、Rainbird 与你们系统的根本性架构差异（不能直接套用的地方）

这三点决定了不能简单照搬 Rainbird 的设计：

**1. Rainbird 是 certainty-weighted backward-chaining，你们的系统要支持更丰富的推理语义**

Rainbird 明确声明：它不是 Bayesian 概率推理，而是"人工标注的 certainty 权重 + 规则链传播"。这在 AML 用例中是不够的——多笔转账的组合风险不能简单用 certainty weight 解释，需要时间窗口内的事件聚合 + 概率语义。蓝图 §5.4 对 certainty-style 和 probabilistic 的分离讨论，正是在 Rainbird 没有解决的区域。

**2. Rainbird 没有 temporal logic，只有 date expression**

Rainbird 能做 `今天 - 开户日 > 36小时`，但不能做 `在36小时窗口内，事件序列的累积状态是否触发义务`。这个 gap 是你们系统的差异化来源。

**3. Rainbird 没有 obligation / deontic 语义**

它能推理出"应该是什么"，但不能区分"被允许"、"被禁止"、"有义务"。ECSS 合规场景的核心恰好是义务推理。

---

### 四、证据链完整性的总结评分

| 层次 | 完整度 | 主要剩余缺口 |
|---|---|---|
| Result 载体 | 85% | certainty vs probability 语义分离仍未解决 |
| Evidence Tree 结构 | 80% | assertion-origin taxonomy deferred；optional condition 语义依赖 rule IR 扩展 |
| Impact / Salience | 30% | 归属已冻结（annotation/value-semantics 层），但 **blocked on certainty/weight vocabulary** |
| Audit / Session Trace | 75% | offline audit + session-bound live permalink 均存在；durable（跨 session）live URL 未实现 |
| 对外交付形态 | 70% | evidence tree URL + structured API + deterministic NL 三种形态均已存在；salience chart 缺失；LLM-powered NL 仍为候选 |

> 与本文早期版本相比，Result 载体、Evidence Tree 结构和对外交付形态三层的完整度在 evidence tree 六轮实现后有大幅提升。当前与 Rainbird 对比中最大的结构性缺口集中在 **Impact / Salience** 层（certainty/weight 基础设施缺失），以及 **certainty 语义分离** 这一贯穿多层的设计问题。

---

### 五、剩余差距与下一步建议

以下建议基于当前已落地能力，聚焦于与 Rainbird 对比中仍然开放的设计问题。

#### 5.1 已关闭的早期建议（仅作历史记录）

- ~~把交付形态纳入讨论~~：三种形态（evidence URL / structured API / NL explain）均已实现
- ~~把 `factID` 等价物加入设计~~：`candidate_id → support_digest → ProofReceipt → candidate_evidence_tree` 链路已完整

#### 5.2 当前最大的结构性 gap：certainty/weight 基础设施

Rainbird 的 salience chart 依赖两个前提：(1) 每个条件有 explicit weight；(2) certainty 语义明确（1-100 整数，非概率）。本项目当前 **两者均不具备**：

- `confidence` 字段语义未分离（certainty vs probability 混用风险）
- rule authoring 不支持 per-condition weight
- 因此 salience / impact breakdown 在当前基础设施上无法实现

这不是单独一个 feature 的缺失，而是 **贯穿 Result 载体 → Evidence Tree → Salience 三层的共同前置依赖**。建议：

1. 先在 certainty vs probability 语义分离上形成 contract-level decision
2. 再决定 per-condition weight 是否进入 rule authoring contract
3. salience / impact 作为最后一环，在前两者就绪后自然展开

#### 5.3 assertion-origin taxonomy

Rainbird 的 6 种 source 类型（Rule / Inject / Answer / Datasource / KM / Synthesised）在本项目中对应的问题是 assertion-origin taxonomy：一个 `assertion_fact` 树节点的事实来源是 ledger write（≈ Inject）、derivation accept（≈ Rule）、还是 import？

当前 `node_kind` provenance-role taxonomy 已关闭，但它只回答"节点在树中的角色"，不回答"事实的来源"。assertion-origin taxonomy 仍 deferred，blocked on assertion metadata schema 设计。

#### 5.4 optional condition 语义

Rainbird 用 synthesised fact at 0% 表达"条件缺失但允许跳过"。本项目当前有 `unresolved_support` 机制表达"子证明不可用"，但这是 tree traversal 层面的事实，不是 rule authoring 层面的"可选条件"语义。

实现 optional condition 需要 rule IR 扩展（标记某个 predicate atom 为 optional），这属于 authoring contract 变更，scope 超出 traceability-explainability 母蓝图。

#### 5.5 本项目超越 Rainbird 的方向

以下能力是 Rainbird 不具备的，是本项目的差异化来源（详见第三节）：

- temporal logic（时间窗口内事件序列的累积状态推理）
- obligation / deontic 语义（被允许 / 被禁止 / 有义务）
- multi-engine architecture（native / Souffle / ProbLog，各有独立 witness 通道）
- Souffle partial witness via adapter-level Datalog rewriting（Rainbird 无对应能力）

这些方向的 traceability / explainability 需求可能需要超出 Rainbird 比较框架来单独设计。
