# Architecture Decision Blueprint: factpy Architectural Pivot v2

- Status: scoped
- Type: architectural-decision (guides child blueprints, not directly actionable)
- Created: 2026-03-22
- Last Updated: 2026-03-22
- Supersedes:
  - `docs/blueprints/archive/2026-03-15_overall-system-blueprint.md`
  - `docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md`
  - `docs/blueprints/archive/2026-03-17_runtime-traceability-explainability-blueprint.md`
- Child Blueprints:
  - `docs/blueprints/active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md`
- Related Docs:
  - `docs/architecture_principles.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/core/annotation/docs/README.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `memory/current.md`
- Audit Log:
  - `docs/blueprints/active/2026-03-22_architectural-decisions-v2.audit.md`

## 1. Purpose

本蓝图是**架构决策记录**（ADR），不是实施计划。它记录经过调研和验证的架构决策，约束所有子蓝图的方向。子蓝图提供具体行动指导；本蓝图提供方向约束和设计参考。

**任何偏离本蓝图的决策必须先修改本蓝图，不能在子蓝图中默默绕过。**

## 2. Product Identity

**factpy 是 auditable reasoning framework，不是 reasoning engine。**

依据：
- 代码实际结构：schema, metadata, audit, render 是主体；推理引擎（Souffle/ProbLog）是插件
- ESA 反馈："especially the explainability and traceability aspects"
- 引擎可替换，审计层不可替换

含义：
- 框架的价值 = "不管你用什么推理引擎，我们让推理过程可审计"
- 引擎是可替换的计算后端，框架是产品层
- 不宣称"我们的推理引擎有概率推理能力"

## 3. Three-Layer Data Architecture

### 3.1 核心原则：Input / Output / View 分离

```
┌─────────────────┐     ┌──────────────────────┐
│  Fact Store      │     │  Provenance Store     │
│  (INPUT layer)   │     │  (OUTPUT layer)       │
│                  │     │                       │
│  assertion:      │     │  derivation:          │
│    value         │     │    rule_id            │
│    meta:         │     │    inputs: [asrt_ids] │
│      confidence  │     │    engine: souffle    │
│      source      │     │    timestamp          │
│      analyst     │     │    min_height         │
│      method      │     │                       │
│      date        │     │  (NO reference to     │
│                  │     │   evidence tree)      │
│  (NO reference   │     │                       │
│   to evidence    │     │                       │
│   tree or        │     │                       │
│   provenance)    │     │                       │
└────────┬─────────┘     └──────────┬────────────┘
         │                          │
         │    READ                  │    READ
         └──────────┐  ┌───────────┘
                    ▼  ▼
           ┌─────────────────┐
           │  Evidence Tree   │
           │  (READ-ONLY VIEW)│
           │                  │
           │  Combines:       │
           │  - fact values   │
           │  - fact metadata │
           │  - provenance    │
           │                  │
           │  NO write-back   │
           │  to either store │
           └──────────────────┘
```

### 3.2 边界规则

- Fact metadata 不知道 evidence tree 的存在
- Provenance 不知道 evidence tree 的存在
- Evidence tree 是**只读视图**，从两个 store 读取后融合展示
- **没有反向引用 → 没有循环**
- Evidence tree 不应该有自己的 ID 让别人引用——它是查询结果，不是持久实体

### 3.3 审计查询路径

```
"这个数据从哪来的？" → Fact Store metadata（不需要 evidence tree）
"这个结论怎么推出来的？" → Provenance Store derivation graph（不需要 fact metadata）
"给我看完整审计链" → Evidence Tree view（融合 fact meta + provenance）
```

### 3.4 持久化策略

```
短期（当前 + ESA demo）：
  Fact meta → ledger（已有）
  Provenance → audit package JSONL（support_artifacts + engine provenance）
  Evidence tree → 实时构建的视图

长期（产品化）：
  Fact meta → 数据库（PostgreSQL / Neo4j）
  Provenance → 独立 store（engine provenance + derivation graph）
  Evidence tree → 按需构建的视图，不是存储的实体
```

## 4. Carrier Layer Boundary

### 4.1 三层能力归属

以下归属决策约束所有子蓝图：

| 能力 | 归属 | 理由 |
|------|------|------|
| Source taxonomy（事实来源分类） | **Proof/Provenance carrier** | "从规则推导的 vs 直接注入的 vs 用户回答的"是结构性 provenance 信息 |
| Missing optional conditions | **Proof carrier（结构）+ Annotation（数值）** | carrier 记录"哪些条件缺失且被跳过"；annotation 记录"跳过后 certainty 的变化量" |
| Contribution/impact breakdown | **Annotation / value-semantics layer** | impact 是数值语义；但计算依赖 proof carrier 提供的条件权重和条件 certainty |

### 4.2 归属漂移防线

如果归属不明确，后续很容易出现：
- proof carrier 开始承担数值语义
- annotation 开始承担结构信息
- 两者边界随迭代漂移

**检验标准**：如果一个信息回答"怎么推出来的"→ proof carrier；如果回答"推得有多确定"→ annotation。

## 5. Multi-Engine Architecture

### 5.1 引擎定位

```
Souffle:  确定性 Datalog（递归、固定点、关系推导）
ProbLog:  概率逻辑（WMC、概率事实、annotated disjunctions）
PyReason: 图神经推理（区间传播、时序推理、annotated graphs）
```

三者的编程模型根本不同，不应强行统一规则语法。

### 5.2 统一什么、不统一什么（updated 2026-03-26）

核心理念：**各引擎独立运行，统一审计。** Schema 是统一边界，审计是统一出口。中间的写入/规则/执行是引擎适配层的事。

| 层 | 统一？ | 说明 |
|----|--------|------|
| Schema / 实体定义 | ✅ 是 | 所有引擎共享同一份 `schema_ir`（Entity, Field, Relationship）。任何引擎写入事实时都必须校验 schema。 |
| Meta（事实元数据）| ✅ 是 | `belief`（通用真值区间）+ `source` / `analyst` / `method` 等。所有引擎通用，不因新引擎膨胀。 |
| 事实写入 API | ⚠️ 部分 | **修正**：写入 API 不强行统一。每个引擎有自己的写入路径，但都校验同一份 schema、记录到审计层。Souffle 用 `write_runtime_fact`，PyReason 用引擎特定 session API，ProbLog 同理。 |
| 规则定义 | ❌ 否 | 编程模型不同，三层规则系统（见 §5.3） |
| 执行/查询 | ⚠️ 部分 | "跑一下，告诉我结果"可统一接口；引擎特定参数（timesteps、convergence 等）通过 engine_options 传递 |
| Provenance 消费 | ✅ 是 | Provenance envelope（见 §5.4）：per-candidate、engine-specific payload |
| **Audit / Delivery** | **✅ 是** | **框架核心价值。所有引擎的推理结果汇入同一条审计管道。** |

**设计原则**：新增引擎时，只需要：
1. 实现自己的 fact write session（校验 schema，记录 audit）
2. 实现自己的 rule builder（Layer 2/3）
3. 实现自己的 provenance extractor（adapter-local carrier）
4. 不改共享层（schema、meta、audit pipeline）

**不应发生的事**：
- 共享 `meta` schema 因新引擎增加字段
- `write_runtime_fact` 因新引擎增加 `engine_hints` 参数
- Audit pipeline 因新引擎改变 JSONL 格式

### 5.2.1 通用真值：`confidence` 值域扩展

所有引擎都需要表达"这条事实有多真"，但数学框架不同：

```
Souffle:  确定性（true/false），certainty 系统用 confidence 做加权
ProbLog:  概率（float in [0,1]）
PyReason: 模糊区间（[lower, upper] in [0,1]）
```

**决策：不引入新字段。扩展 `confidence` 值域为 `float | [float, float]`。**

```
confidence = 0.8         → [0.8, 0.8]   所有引擎都能消费
confidence = [0.6, 0.9]  → [0.6, 0.9]   PyReason 直接用，Souffle/ProbLog 取 lower
```

每个引擎按自己的语义消费 `confidence`：
- Souffle certainty 系统：读 `lower` 作为 `condition_confidence`
- ProbLog：读 `lower` 作为概率标注
- PyReason：直接用 `[lower, upper]` 作为 bound

**规范化**：`write_protocol` 内部统一存储为 `[lower, upper]`。旧 surface 读 confidence 时，如果是区间取 `lower`（向后兼容）。certainty v1 的 16 条冻结 contract 不受影响。

### 5.2.2 引擎特有参数不进共享层

引擎特有概念（PyReason 时间步、ProbLog annotated disjunctions 等）**留在引擎自己的写入路径和规则 builder 里**，不通过共享 meta 或共享 API 传递。

```
✅ 正确：pyreason_session.write_fact(..., active_from=0, active_to=5)
❌ 错误：write_runtime_fact(..., meta={"active_from": 0})
❌ 错误：write_runtime_fact(..., engine_hints={"pyreason": {...}})
```

这样共享层永远不膨胀。

### 5.3 三层规则系统

```
Layer 1: Core Rule IR（现有 where_ast.py）
  - 平坦合取：Pred + Cmp + Eq
  - 变量绑定
  - 基本聚合
  → 适用于：所有引擎的公共子集

Layer 2: Engine Extensions
  - Souffle: 分层否定、subsumption、ADT、lattice
  - ProbLog: 概率事实（0.3::fact）、annotated disjunctions
  - PyReason: 时间步（t, t+1）、区间标注、图结构操作
  → 以 extension block 挂载，不污染 Core IR

Layer 3: Raw Syntax Escape Hatch
  - 直接写引擎原生语法（.dl / .pl / PyReason DSL）
  → 最大灵活性，最少框架保证
  → 框架仍提供 fact 注入 + provenance 消费
```

### 5.4 Provenance Payload Strategy (ADR-13, updated 2026-03-26)

**Original design (2026-03-22):** Unified `ProofNode` tree with engine-specific annotations.

**Updated decision (2026-03-26):** **Per-candidate engine-specific provenance envelope.** The original `ProofNode` tree design is withdrawn based on two real engine samples:

- **Souffle** produces a **proof tree** (JSON, recursive nodes, per-conclusion)
- **PyReason** produces an **event log** (DataFrame rows, per-change, temporal)

These are fundamentally different shapes. Forcing PyReason's event log into a tree loses temporal ordering and interval semantics. Forcing Souffle's tree into an event log loses hierarchical proof structure.

**Frozen decision:** Use a **provenance envelope** that preserves engine-native shape:

```python
# NOT a unified tree — a typed envelope
@dataclass(frozen=True)
class ProvenanceEnvelope:
    candidate_id: str
    engine: str              # "souffle" | "pyreason" | "problog"
    payload_type: str        # "proof_tree" | "event_log" | "probability_decomposition"
    payload: dict[str, Any]  # engine-native shape, not forced into a common schema
```

**Consumer dispatch:** Static HTML, narrative, and query surfaces render by `payload_type`:
- `proof_tree` → nested tree visualization (existing Souffle renderer)
- `event_log` → temporal timeline visualization (future PyReason renderer)
- `probability_decomposition` → probability attribution (future ProbLog renderer)

**What this means for child blueprints:**
- Do NOT build a unified `ProofNode` tree
- Do NOT force engine output into a common node schema
- DO preserve engine-native provenance in adapter-local carriers
- DO use `engine` + `payload_type` for consumer dispatch
- The envelope schema itself is a core contract; the payload contents are adapter-local

### 5.5 跨引擎互通

**不追求自动互通。** 各引擎独立运行、统一审计。

如果确实需要跨引擎 pipeline，使用**显式语义桥**：

```
确定性 → 概率:  无损（p = 1.0）
概率 → 确定性:  有损（阈值化，用户显式决策）
确定性 → 区间:  无损（[1.0, 1.0]）
区间 → 确定性:  有损（阈值化）
```

桥接操作本身作为审计证据记录。

## 6. Engine Provenance Strategy

### 6.1 调研结论（2026-03-22 verified）

**Souffle provenance** (`-t explain`):
- 完整递归证明链 ✅
- 最小高度证明 ✅
- JSON 输出 ✅
- 负向推理（交互式 `explainnegation`）⚠️
- 性能：~1.3-1.5x overhead
- **接入成本：低**——factpy 已用 interpreter 模式，加 flag 即可

**ProbLog explanation**:
- 互斥证明枚举 ✅
- LogicFormula 地面公式图 ✅
- aProbLog provenance semiring（per-fact 概率归因）✅
- **接入成本：中**——需从 subprocess 改为 Python API

**PyReason explanation** (added 2026-03-26, spike verified):
- `pr.get_rule_trace()` event log ✅
- 时间步 + 区间值变化 ✅
- Clause grounding（哪些节点/边匹配了规则体）✅
- **形态：event log（DataFrame），不是 proof tree**
- **接入成本：低**——in-process Python API，无 subprocess
- **环境约束：`pyreason==3.0.0`，ARM64 macOS 首次 JIT ~85s**

### 6.2 接入优先级（updated 2026-03-26）

```
1. Souffle provenance（-t explain + JSON）→ 已完成，audit pipeline 已接入
2. PyReason provenance（get_rule_trace）→ spike 完成，adapter-local carrier 已验证
3. ProbLog explain mode → 未开始，中成本
4. aProbLog provenance semiring → 未开始，高成本
```

### 6.3 核心原则

**Provenance 应该从引擎里拿，不是在框架外部重建。**

当前 certainty v1 在 annotation 层重建 traceability，只能看到引擎给的 support artifact，信息不够。正确模型：引擎产出 provenance → 框架消费和呈现。

## 7. Certainty V1 Assessment

### 7.1 已冻结，16 条 contract

Certainty v1 已完成并冻结（234 tests）。详见 `src/factpy_kernel/core/annotation/docs/README.md`。

### 7.2 诚实评估

| 维度 | 评估 |
|------|------|
| 覆盖面 | 窄——只处理 flat single-rule cases |
| 递归 | 返回 null |
| 多路径 | 只看 1 条 proof |
| 在 ECSS 场景下 | **够用**——ECSS 规则大多是 flat 合取 + 阈值 |
| Delivery pipeline | **有价值**——summary/narrative/NL/audit/static 可复用 |
| 定位 | 引擎不给 provenance 时的 fallback 启发式 |

### 7.3 Evidence Tree 的真实能力

| 能力 | 状态 |
|------|------|
| 展示规则结构 + 具体事实实例 | ✅ |
| 展示递归推导链 | ❌ 只看最后一步 |
| 解释为什么不成立（负向推理）| ❌ |
| 展示替代证明路径 | ❌ |
| 反事实分析 | ❌ |
| 最小证明 | ❌ |

**定位**：evidence tree 是"审计留痕"，不是"推理解释"。对 ESA 合规审计有价值；但用户已知的规则结构不算新信息。

## 8. ECSS Domain Validation（2026-03-22 verified）

### 8.1 ESSB-ST-U-007 规则复杂度

| 类型 | 存在？ | 对 Datalog 的适配性 |
|------|--------|-------------------|
| 平坦合取 | ✅ 主要 | 完全适配 |
| 阈值比较 | ✅ 常见 | 完全适配 |
| 条件分支 | ✅ 中等 | 适配 |
| 浅层递归（组件 for-all）| ✅ 有限 | 分层否定可表达 |
| 深层递归 | ❌ | 不需要 |
| 复杂时序 | ❌ | 不需要 |

**结论**：Datalog (Souffle) 完全适配 ECSS 合规规则。当前 evidence tree 在 ECSS 场景下大概率满血可用。

### 8.2 已有领域代码

`src/factpy_kernel/domains/ecss/` 已包含：
- `vcd.py`: requirement, verification_method, compliance_status, requirement_rid, review_milestone
- `uncertainty.py`: collision_probability_ppm, disposal_success_probability_ppm + thresholds
- `temporal.py`: obligation_timestamp, window_start/end, interval_start/end

### 8.3 Demo 规则候选

优先编码（Tier 1）：
- 处置成功概率 ≥ 90%（或星座 ≥ 95%）
- 碰撞概率 < 1:1000
- 轨道清除 ≤ 5 年
- 无碎片释放

## ADR-14: Multi-Engine Integration Boundary (2026-03-26, revised)

基于 Souffle（完整集成）+ PyReason（spike 验证）+ ProbLog（调研完成）三个真实样本。

核心原则：**Schema 是统一边界，审计是统一出口。写入/规则/执行是引擎适配层的事。**

### ADR-14a: 事实写入——共享 schema，独立写入路径

**决策（修正）：不强行统一写入 API。每个引擎有自己的写入 session，但都校验同一份 schema、记录到审计层。**

```
Souffle:  write_runtime_fact(session_id, {...})     ← 已有，不改
PyReason: pyreason_session.write_fact(...)          ← 引擎特定 API
ProbLog:  problog_session.assert_fact(...)          ← 引擎特定 API

所有路径共同约束：
  1. 校验 schema_ir（pred_id 必须在 schema 里）
  2. 记录通用 meta（belief, source, analyst）
  3. 写入审计可追溯的存储
```

**原因**：强行统一写入 API 会导致共享接口因新引擎不断膨胀。引擎特有概念（PyReason 时间步/区间/图边、ProbLog 概率标注）留在引擎自己的写入路径里，不进共享 meta。

### ADR-14b: Relationship Schema

**决策（保持）：新增 `Relationship` 概念，与 `Entity` 平行。**

```python
class Friends(Relationship):
    from_entity: User
    to_entity: User
    strength: float = Field()
```

Relationship 在 `schema_ir` 里生成 predicate，形态 `(e_ref_from, e_ref_to, ...field_args)`。所有引擎的写入路径都校验 Relationship schema。

### ADR-14c: 通用 Meta（confidence 扩展 + 来源信息）

**决策：不引入 `belief`。扩展 `confidence` 值域为 `float | [float, float]`。**

```python
meta = {
    "confidence": 0.8,            # float → 内部存为 [0.8, 0.8]
    # 或
    "confidence": [0.6, 0.9],    # [float, float] → PyReason 直接用
    "source": "...",
    "analyst": "...",
}
```

旧 surface 读区间时取 `lower`。引擎特有参数不进 meta。

### ADR-14d: Layer 2 Rule Builder

**决策（保持）：引擎特定 Rule 子类。**

```python
Rule(where=[Pred(...)])                                    # Layer 1: all engines
PyReasonRule(where=[...], timestep_delay=1, bound=[...])  # Layer 2: PyReason
ProbLogRule(where=[...], probability=0.3)                  # Layer 2: ProbLog
```

### ADR-14e: Evaluate Engine Dispatch

**决策（保持）：`mode` 参数 dispatch + `engine_options`。**

### ADR-14 实施优先级（修正）

```
Phase 1: 共享 schema 扩展（Relationship + belief meta）
         + PyReason 引擎 session 写入路径
Phase 2: Layer 2 Rule builder（PyReasonRule + ProbLogRule）
Phase 3: Evaluate dispatch + result normalization
```

---

## 9. ESA Interaction Context

### 9.1 ESA 反馈摘要

联系人：Christophe Honvault, Head of AI and Data Science section, ESA Future Engineering Division

ESA 的评价：
- "especially the explainability and traceability aspects"
- "the tool can estimate the certainty and source of extracted facts is also a feature we enjoy"

ESA 的要求：
- 具体 use case + vs 竞品优势
- 用户交互形态（web app? library? agent?）
- 非技术人员可理解的表述

### 9.2 ESA 推荐的合作路径

- ESA Discovery element: ideas.esa.int → Open Discovery Ideas Channel
- 推荐 use case: ECSS 标准验证、ESSB-ST-U-007 碎片减缓
- 推荐展示场合: FLoC "Automated Reasoning for Future Space Logistics" workshop

### 9.3 产品叙事

> "上次你们看到我们用 LLM 生成规则，你们担心可靠性。我们听进去了。
> 现在规则仍然可以 LLM 辅助生成，但人工审核后进入形式化推理引擎，
> 每一步推导都有完整的、可验证的证明链。
> 这就是你们说的 traceability——不是 LLM 说的，是逻辑推理证明的。"

## 10. Annotation Extension Candidates

以下候选能力保留观察，不进入当前实施范围：

### 近期保留（和当前架构方向一致）

1. **Fact metadata 透传到 evidence tree**——让 tree node 展示 source, analyst, method, date
2. **Engine provenance 集成**——Souffle explain / ProbLog LogicFormula → ProofNode
3. **Source taxonomy**——proof carrier 层记录事实来源类型

### 中期观察

4. **Missing optional conditions**——proof carrier 记录结构，annotation 记录数值影响
5. **Why-not / counterfactual**——需要 Souffle `explainnegation` 或等价能力
6. **Certainty evaluator vs probabilistic evaluator 分离**——共享 proof carrier，不共享 confidence 语义
7. **Interval annotation**——PyReason 接入时需要

### 不作为当前方向

8. Generic annotation algebra
9. Annotation as the only traceability carrier
10. Full PyReason-style unified annotation semantics

## 11. Reference Scenarios

用于持续检验候选设计：

### Scenario A: ESA SDM Compliance

一个候选设计必须能回答：
- 某条 requirement 为什么当前是 compliant / partial / non-compliant
- 这一状态由哪次 run、哪类 analysis、哪些 supporting artifacts 得到
- 对应 evidence / justification / close-out reference 如何被消费

### Scenario B: AML/KYC Suspicious Account（中期参考）

一个候选设计必须能回答：
- 系统是否能把分布式事件聚合成 obligation / risk state
- 是否能解释"为什么在此刻触发"
- 是否能表达弱信号组合、缺失条件、主要/次要 proof 的关系

## 12. Frozen Decisions（变更需先修改本蓝图）

1. 产品定位：auditable reasoning framework
2. 三层数据架构：Fact Store / Provenance Store / Evidence Tree View
3. 引擎隔离：统一 fact + audit，不统一规则
4. ~~ProofNode 作为统一 provenance 中间层~~ → **Per-candidate engine-specific provenance envelope**（ADR-13, updated 2026-03-26; see §5.4）
5. 跨引擎不自动互通
6. Provenance 从引擎里拿，不在外部重建
7. Certainty v1 冻结（16 条 contract）
8. ECSS 作为第一领域验证目标
9. 领域先行，系统跟上（不再 system-first）

## 13. Acceptance

本蓝图的验收标准是**决策记录完整且被子蓝图引用**：

- [x] 产品定位已冻结
- [x] 三层数据架构已定义
- [x] 引擎 provenance 调研已完成
- [x] ECSS 适配性已验证
- [x] 子蓝图（ECSS validation PoC）已创建并引用本蓝图
- [ ] 至少一个子蓝图进入 implementing 状态（验证决策可执行）
