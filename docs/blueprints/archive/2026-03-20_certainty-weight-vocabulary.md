# Task Blueprint: Certainty / Weight Vocabulary

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/core/store/_support.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree.py`
  - `src/factpy_kernel/core/store/_candidate_evidence_tree_summary.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
  - `src/factpy_kernel/core/derivation/candidates.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/audit/query.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [docs/blueprints/archive/2026-03-20_candidate-evidence-tree-salience-impact.md](../archive/2026-03-20_candidate-evidence-tree-salience-impact.md)
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](../active/2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-20_certainty-weight-vocabulary.audit.md](./2026-03-20_certainty-weight-vocabulary.audit.md)

## 1. Problem

当前仓库在 traceability-explainability 主线上已完成 8 个能力线，但 **salience / impact breakdown** 被冻结为 blocked（`69d45d9`），原因是缺少 certainty/weight 基础设施。Rainbird 对比文档（2026-03-20 reviewed）确认这是与 Rainbird 对比中最大的结构性缺口。

具体缺失：

1. **`confidence` 语义未分离**：当前 `CandidateSet.confidence` 是一个窄字段，但没有明确它是 certainty-weighted（Rainbird 风格：人工标注 1-100 整数，非概率）还是 probabilistic（ProbLog 风格：概率值）还是其他语义。母蓝图 §5.4 已识别这一风险但未解决。

2. **Per-condition weight 不存在**：Rainbird 的 salience chart 依赖"每个条件有 explicit weight"。当前 rule IR（`where_ast`）和 rule authoring 均不支持 per-condition weight 标注。

3. **Rule-level certainty cap 不存在**：Rainbird 中每条规则有独立的 max certainty 上限（独立于条件 certainty）。当前 rule authoring 无此概念。

这三项缺失不是独立 feature gap，而是 **贯穿 Result 载体 → Evidence Tree → Salience 三层的共同前置依赖**。不解决它们，以下能力线无法启动：

- salience / impact breakdown（母蓝图 §5.8 #3）
- certainty-style explanation（母蓝图 §5.4 #2）
- Rainbird 对比中 Impact / Salience 层完整度从 30% 提升

## 2. Goals

- 形成 certainty vs probability 语义分离的 **contract-level decision**，明确 `confidence` 字段的语义口径。
- 评估 per-condition weight 是否应进入 rule authoring contract，以及进入方式（rule IR 扩展 vs annotation layer vs 独立 metadata）。
- 评估 rule-level certainty cap 是否属于近期目标。
- 明确 certainty/weight vocabulary 与以下已存在概念的关系：
  - `SupportArtifact`（proof carrier）
  - `candidate_evidence_tree_summary`（当前只有结构性统计，无数值权重）
  - `annotation` prototype（`core/annotation`，当前 internal）
  - engine-specific semantics（Souffle certainty=1.0、ProbLog 概率值）
- 为后续实现型子蓝图提供可收口的方向。

## 3. Non-goals

- 不在本蓝图中实现 salience / impact breakdown（那是 downstream consumer）。
- 不在本蓝图中定义完整的 probabilistic reasoning framework。
- 不在本蓝图中修改 `CandidateSet` 的稳定接口。
- 不在本蓝图中把 `core/annotation` prototype 提升为正式 contract。
- 不在本蓝图中实现 engine-specific certainty propagation。
- 不把 Rainbird 的 certainty-weighted backward-chaining 直接作为设计模板。

## 4. Current Context

### 4.1 已存在的相关概念

| 概念 | 位置 | 当前语义 |
|---|---|---|
| `CandidateSet.confidence` | `core/derivation/candidates.py` | 窄字段，语义未标注（certainty? probability? score?） |
| `SupportArtifact.pred_witnesses` | `core/store/_support.py` | 结构性 witness（哪些 assertions 满足了哪个 pred atom），无数值权重 |
| `candidate_evidence_tree_summary` | `core/store/_candidate_evidence_tree_summary.py` | 12 字段 core set，全部是结构性统计（node counts / assertion counts / recursive depth），无数值权重 |
| `core/annotation` prototype | `core/annotation/` | internal min-max path confidence propagation（Workload A+C），不在 public contract |
| Souffle adapter | `adapters/souffle/engine_eval.py` | 产出 `souffle_witness_v1` support，但 certainty 隐含为 1.0（deterministic Datalog） |
| ProbLog adapter | `adapters/problog/` | 产出概率值，但 support_kind 仍为 `engine_no_witness_v1`（degraded path） |

### 4.2 已冻结的相关决策

- salience / impact 归属：annotation / value-semantics 层，compute-time = query-time（`69d45d9`）
- provenance-role taxonomy：`node_kind` 是 carrier-level taxonomy，不新增 `source_kind` 字段（`729362f`）
- 母蓝图 §5.4：certainty-weighted reasoning 与 probabilistic reasoning 应保持可区分，不强行复用同一个未标注语义的 `confidence` 值

### 4.3 Rainbird 对比基线

Rainbird 的 certainty 模型（来自比较文档）：
- 明确声明不是 Bayesian 概率
- 1-100 整数，人工标注
- 每个条件有 explicit weight
- 每条规则有 max certainty cap
- Salience chart = f(condition weight, condition certainty)
- 传播语义：certainty 通过规则链向上传播，受 cap 和 weight 约束

本项目的差异化方向（不能照搬 Rainbird）：
- 需要同时支持 certainty-style 和 probabilistic reasoning
- temporal logic 和 deontic semantics 是 Rainbird 不具备的
- multi-engine architecture 意味着 certainty/weight vocabulary 必须跨引擎可用

## 5. Resolved Decisions

### 5.1 Confidence 语义分离

**Decision: 方案 1 — `confidence` + `confidence_kind`，详细语义留在 value layer。**

- `CandidateSet.confidence: float | None` 保持不变（candidate-level scalar）
- 新增 additive 字段 `CandidateSet.confidence_kind: str`
- 枚举收窄为 **`"none" | "probability" | "certainty"`**
  - 不保留泛化的 `"score"`：否则"语义分离"会被新的模糊桶重新破坏
  - `"none"` = 没有 uncertainty model（不等于"certainty = 1.0"，见 §5.4）
- 更细的 breakdown（per-condition certainty、per-condition impact）不进入 `CandidateSet` 或 `SupportArtifact`，继续留在 annotation / value-semantics 派生层
- 向后兼容：现有 `confidence=None` 的 candidate 默认 `confidence_kind="none"`

**Why**: `CandidateSet.confidence` 已是 stable carrier 字段。直接拆双字段扩宽过早；加 `confidence_kind` 是 additive 最小侵入。收窄枚举确保语义分离的目标不被泛化桶破坏。

### 5.2 Per-condition Weight

**Decision: Rule metadata 作为 weight source of truth，不进 `where_ast`，annotation layer 不拥有权重。**

- Weight 属于 **version-scoped rule metadata**，按 condition key 关联到具体条件
- 不扩张 `where_ast` / rule IR：把 weight 塞进 `where` 会把逻辑 IR 和 value semantics 耦合，还会把所有引擎一起拖进来
- annotation layer 可以在 query-time **消费** weight（用于 salience 计算），但不 **拥有** weight
- `RuleSpec` 现有字段只包含逻辑执行所需的最小字段；weight 不进入执行路径，只进入 value-semantics 派生路径

**Why**: rule IR 是逻辑执行的 contract，weight 是 value semantics。两者耦合会把所有引擎（native / Souffle / ProbLog）都拖进 weight 理解义务。metadata 层已有 `version / description / tags` 先例，weight 落在此层最自然。

### 5.3 Rule-level Certainty Cap

**Decision: deferred，不进第一实现轮。**

- Rule-level certainty cap 是 certainty-only 概念，不是 probability 的公共语义
- 在 `confidence_kind` 和 per-condition weight 都没冻结前，引入 cap 只会把 authoring contract 再扩大一层
- 等第一轮 vocabulary 落稳后，再开单独 child blueprint
- 届时也应优先落在 rule metadata，而不是 `where_ir`

**Why**: cap 的前置依赖是 certainty 语义本身。先稳定 confidence_kind + weight，再叠 cap，避免三层同时推进。

### 5.4 跨引擎最小公共语义

**Decision: deterministic 不等于 certainty=1.0。Deterministic engine 标注为 `confidence_kind="none"`。**

| 引擎 | confidence | confidence_kind | 语义 |
|---|---|---|---|
| native | `None` | `"none"` | 没有 uncertainty model |
| Souffle | `None` | `"none"` | 没有 uncertainty model |
| ProbLog | `float` | `"probability"` | 概率值 |
| 未来 certainty engine | `float` | `"certainty"` | certainty-weighted |

- 不把 deterministic 语义映射为 "certainty = 1.0"
- 对 deterministic engine，更准确的语义是"没有 uncertainty model"，不是"显式最大 certainty"
- 如果未来 native / Souffle 叠加了显式 certainty layer（例如通过 annotation），再 additive 地进入 `"certainty"`，不从 deterministic 语义直接推导

**Why**: certainty = 1.0 隐含"存在一个 certainty model，且当前值恰好为 1.0"。deterministic engine 根本没有这个 model。混淆两者会污染下游 salience 计算（0-weight-contribution vs 1.0-contribution 在语义上完全不同）。

### 5.5 与 Annotation Prototype 的关系

**Decision: annotation prototype 是 first consumer，不是 contract owner。**

- certainty/weight vocabulary 作为 **core-level、engine-neutral contract** 定义
- `core/annotation` prototype 后续去 **消费** 和 **验证** 该 vocabulary，但不反过来定义它
- annotation prototype 继续保持 internal / prototype 状态，不因 vocabulary 落地而自动提升为正式 contract

**Why**: `core/annotation` 文档已明确它是 internal/prototype，不应直接改稳定 `CandidateSet` 面。让 prototype 定义 contract 会把验证性质的代码变成 contract owner，违反当前架构边界。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `CandidateSet` 的现有接口不被破坏；任何扩展必须是 additive
  - `SupportArtifact` 作为 proof carrier 的角色不变；certainty/weight 是 value-semantics 层，不是 proof structure
  - 已冻结的 8 个 contract（handoff §7）不被重新打开
  - `core` 不静态依赖 `adapters`；certainty/weight vocabulary 必须是 engine-neutral
- 明确不做的内容：
  - 不在本蓝图中直接实现 certainty propagation engine
  - 不在本蓝图中修改 where evaluator 的执行语义
- 兼容性约束：
  - 若引入 `confidence_kind`，现有 `confidence` 字段的默认值语义必须是向后兼容的
  - 若引入 per-condition weight，现有无 weight 标注的规则必须继续正常工作（default weight = 1.0 或 unweighted）

## 7. Acceptance

- [x] certainty vs probability 语义分离方向已形成 contract-level decision — §5.1: `confidence` + `confidence_kind`，枚举 `none | probability | certainty`
- [x] per-condition weight 的归属已明确 — §5.2: rule metadata（version-scoped），不进 where_ast，annotation layer 只消费不拥有
- [x] rule-level certainty cap 是否近期目标已判定 — §5.3: deferred，不进第一轮
- [x] 跨引擎 certainty/weight 映射的最小公共语义已描述 — §5.4: deterministic = `"none"`（非 1.0），ProbLog = `"probability"`
- [x] 为后续实现型子蓝图提供了可收口的切口 — §8

## 8. Implementation Plan

1. ~~建立本蓝图 draft~~ ✅
2. ~~§5.1-§5.5 讨论收口~~ ✅ — 5 条 decision 已冻结

下一步拆分为 3 个实现型 child blueprints：

### Child 1: `candidate-confidence-kind` ✅ implemented

- `CandidateSet.confidence_kind: str = "none"` 已落地，枚举 `CONFIDENCE_KINDS = frozenset({"none", "probability", "certainty"})`
- native / Souffle 路径显式写 `confidence_kind="none"`
- ProbLog 路径在回填 confidence 时同时写 `confidence_kind="probability"`
- service DTO round-trip 支持该字段，旧客户端缺字段时默认回落 `"none"`
- accept 写入 ledger meta
- 175 tests pass
- 已归档：[2026-03-20_candidate-confidence-kind.md](../archive/2026-03-20_candidate-confidence-kind.md)

### Child 2: `rule-condition-weight-metadata` ✅ implemented

- `Rule(...)` / authoring rule payload 现已支持 version-scoped `condition_weights`
- condition key 已冻结并落地为 atom-position key：`b{branch}.a{atom}`
- `compile_authoring_rule_v1(...)` 会校验 key ownership 和 positive finite number value
- service `compile-preview` 现已保留 `description / tags / condition_weights`
- registry canonicalization 不再压缩掉 rule metadata；`description / tags / condition_weights` 可经 register/read 稳定 round-trip
- `RuleSpec` 和 where evaluator 仍保持纯逻辑执行 contract，不消费 metadata
- 180 tests pass
- 已归档：[2026-03-20_rule-condition-weight-metadata.md](../archive/2026-03-20_rule-condition-weight-metadata.md)

### Child 3: `certainty-propagation-prototype` ✅ implemented

- `core/annotation/_certainty.py` 现已落地，导出 `derive_certainty_summary`、`ConditionImpact`、`CertaintySummary`
- annotation prototype 现在成为 certainty/weight vocabulary 的 first consumer
- certainty lane 只在 `confidence_kind="certainty"` 时产出 candidate-level certainty summary
- per-condition impact 通过 tree carrier key 前缀与 `condition_weights` 关联；当前 deterministic 条件的 impact = weight
- `aggregate_certainty` 采用 bottleneck（最小 weighted impact）
- 这条线保持 internal / prototype，不扩张 runtime / audit 的稳定 summary DTO
- 194 tests pass
- 已归档：[2026-03-20_certainty-propagation-prototype.md](./2026-03-20_certainty-propagation-prototype.md)

三条 child slices 已全部完成；certainty/weight vocabulary 的结构性前置依赖现已就绪。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-20_certainty-weight-vocabulary.md`
- `docs/blueprints/active/2026-03-20_certainty-weight-vocabulary.audit.md`
- 若收口后产出 contract 变更：`src/factpy_kernel/core/docs/01_architecture.md`

## 10. Outcome / Deviations

- 最终落地结果：certainty/weight vocabulary 已完成三条 child slices。`confidence_kind` 已进入 candidate contract；`condition_weights` 已进入 rule metadata contract 并可经 SDK/authoring/service/registry round-trip；annotation prototype 已新增 certainty lane first-consumer `derive_certainty_summary(...)`，可从 evidence tree + condition weights 派生 per-condition weighted impact 与 candidate-level bottleneck certainty summary。
- 与 blueprint 不同的地方：Child 3 最终把 certainty summary 保留在 annotation internal surface，没有把它继续塞进 runtime / audit 的稳定 `candidate_evidence_tree_summary` DTO。
- 为什么会有这些调整：这能在验证 vocabulary end-to-end 可用性的同时，保持 “annotation prototype 只是 first consumer，不是 stable contract owner” 的架构边界，避免在同一轮把新的 value-semantics 直接扩到 public summary surface。
- 归档说明：2026-03-20 三条 child blueprints 全部完成，parent blueprint 标记 implemented 并归档到 `docs/blueprints/archive/`。
