# Rainbird 证据链比较笔记

- Status: maintained
- Type: external comparison
- Authority: external comparative rationale; not current implementation truth
- Usage:
  - 可用于 blueprint 中的证据链、delivery shape、explainability 对照讨论
  - 不应单独作为本项目 contract 或实现承诺

## 评估：蓝图证据链设计的完整性 vs. Rainbird 的实现

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

#### 层 1：Result 载体（`CandidateSet` + `confidence`）

| 维度 | Rainbird | 当前蓝图 | 差距 |
|---|---|---|---|
| 结论对象 | `subject + relationship + object + certainty + factID` | `CandidateSet` + 窄 `confidence` 字段 | ⚠️ `factID` 等价物缺失：没有一个能直接指向证据树的唯一入口标识 |
| 置信度语义 | 明确是 certainty-weighted（非概率），1-100 整数，有 rule-level cap | `confidence` 语义未分离（certainty vs probability 混用风险，蓝图 §5.4 已点出） | ⚠️ 语义分离问题已识别但未解决 |
| 多结果 | 每个 result 有独立 evidence tree | `CandidateSet` 支持多候选，但各候选是否各有独立 proof 入口未明确 | ⚠️ 需要明确 |

#### 层 2：Evidence Tree（proof/provenance carrier）

| 维度 | Rainbird | 当前蓝图 | 差距 |
|---|---|---|---|
| 树的入口 | `factID` → `GET /analysis/evidence/{factID}/{sessionID}` | 无对应的 stable per-result proof entry point | ❌ **关键缺口**：蓝图讨论了 proof/provenance carrier 的形态，但没有定义"如何从一个 candidate 结论找到它的证明树入口" |
| 递归结构 | 每个 condition 有 `factID`，可无限递归到 leaf | 蓝图 §5.4.1 讨论了 run-scoped proof instance vs proof signature，但没有定义递归边界 | ⚠️ 递归终止条件未定义（何时到达 leaf：inject / KM global / user answer） |
| 条件来源类型 | 6 种明确的 source（Rule/Inject/Answer/Datasource/KM/Synthesised），颜色编码 | 蓝图提到 `support/provenance`，但没有枚举来源类型 | ⚠️ fact source taxonomy 缺失 |
| 可选条件处理 | optional condition 缺失时生成 synthesised fact at 0%，在树中显示为 strikethrough | 蓝图 §5.8 提到 `missing optional conditions`，但没有定义运行时表达方式 | ⚠️ 缺失条件的运行时表达方式未定义 |

#### 层 3：Salience / Impact Breakdown（certainty 分解）

| 维度 | Rainbird | 当前蓝图 | 差距 |
|---|---|---|---|
| 条件权重 | 每个条件有 explicit weight，impact = f(weight, condition certainty) | 蓝图 §5.8 提到 `contribution/impact breakdown`，但作为 annotation extension candidate，未进入核心 contract | ⚠️ impact breakdown 目前只是候选能力，没有明确是否进入 proof carrier 还是 annotation layer |
| Salience Chart | 独立视图，显示每条件的 actual impact vs max possible impact | 无对应概念 | ❌ **gap**：即使不做完整可视化，impact breakdown 的数据结构需要在 carrier 层定义 |
| Rule-level certainty cap | 规则本身有 max certainty 上限，独立于条件 certainty | 蓝图未讨论 rule-level certainty cap 的存在 | ⚠️ 规则级 certainty 上限是个重要的 authoring contract 问题 |

#### 层 4：Audit / Session Trace（interaction log）

| 维度 | Rainbird | 当前蓝图 | 差距 |
|---|---|---|---|
| Session 级别的事件流 | `GET /analysis/interactions/{sessionID}` 返回完整事件序列（query/inject/question/answer/result/error），可导出 CSV | 蓝图的 `audit-log` 对应 run/candidate/decision/apply event，结构类似 | ✅ 概念覆盖，但 Rainbird 明确支持 session 级别聚合，蓝图的 audit 是 package 导出模式 |
| Live vs offline audit | Rainbird 的 evidence 和 interaction log 是 live API，保留 7-30 天 | 蓝图明确：`audit` 是离线 package 消费，不直接暴露 live runtime trace | ⚠️ live trace 的需求在 reference scenario 中（AML/ESA 场景都需要"当时为何决策"）已经浮现，但蓝图尚未决策是否扩展 audit 到 live 模式 |

#### 层 5：对外交付形态（最终成品方式）

这是 Rainbird 文档**与当前蓝图差距最大的维度**：

| 维度 | Rainbird | 当前蓝图 |
|---|---|---|
| 最终用户界面 | Rainbird Agent（iFrame/URL），React SDK，visual evidence tree URL | **完全未定义** |
| "为什么"的消费形态 | 三种并存：visual tree URL（可嵌入）/ API 递归遍历 / NL Explain endpoint | 蓝图 §5.6 只提到 `proof/support graph -> UI / service delivery`，无具体形态 |
| 开发者集成 | REST API + JS/Go SDK，明确的 QuestionResponse / ResultResponse schema | `service` 层存在，但 traceability/explainability 的 service delivery contract 未定义 |
| 竞争差异化 | visual evidence tree + salience chart + NL explain 的组合 | 蓝图有四个候选方向但没有哪种被明确对应到"用户能摸得到的东西" |

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

| 层次 | 完整度 | 主要缺口 |
|---|---|---|
| Result 载体 | 60% | 缺少 proof entry point 标识（`factID` 等价物），certainty 语义未分离 |
| Evidence Tree 结构 | 40% | 递归结构、来源类型枚举、可选条件运行时表达，三者均未定义 |
| Impact / Salience | 30% | impact breakdown 只在 annotation extension candidates 中，未进入核心 carrier contract |
| Audit / Session Trace | 70% | offline package 模式存在，live trace 需求已浮现但未决策 |
| **对外交付形态** | **10%** | **最大缺口：没有一种"用户能看到的东西"被明确定义** |

---

### 五、给蓝图的具体建议

**最需要补充的是：把交付形态纳入 §5.3 的第 4 个问题**

当前 §5.3 的第 4 个问题是"哪类承载方式最适合近期对外演示"，但回答时缺少对**交付形态**的约束。借鉴 Rainbird，可以考虑三种近期可行的形态：

| 形态 | 对应 Rainbird | 实现成本 | ESA/AML 适用性 |
|---|---|---|---|
| **Shareable audit URL**（给定 candidate ID，打开完整 audit trace 页面）| Evidence Tree URL | 低，复用现有 audit 基础设施 | ✅ ESA SDMR close-out reference 直接映射 |
| **Structured JSON API**（`GET /explain/{candidate_id}`，返回 proof chain JSON）| Evidence API | 中，需要定义 schema | ✅ 开发者可自定义渲染 |
| **NL explain**（自然语言解释一个 candidate 为何成立）| `/nl/explain` BETA | 中高，需要 LLM 集成 | ✅ ESA 要求"对非形式逻辑背景的人可理解" |

**以及：把 `factID` 等价物（proof entry point）加入 §5.4 的讨论**

Rainbird 架构中最优雅的设计是：`result` 里携带 `factID`，作为连接 decision 层和 evidence 层的桥梁。这在蓝图 §5.4.1 的 `run-scoped proof instance` 讨论中已经隐含了，但没有明确提出"每个 candidate 结论需要一个 proof entry point identifier"这个设计决策。这是证据链完整性最关键的缺失环节。

需要我帮你把这些内容具体起草为蓝图 §5.3 和 §5.4 的修订建议，还是你希望先在这里讨论某个具体的设计选择？
