# Task Blueprint: Scenario A Uncertainty And Confidence

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/ecss`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/sdk/docs/00_user_guide.md](../../../src/factpy_kernel/sdk/docs/00_user_guide.md)
  - [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-18_scenario-a-uncertainty-and-confidence.audit.md](./2026-03-18_scenario-a-uncertainty-and-confidence.audit.md)

## 1. Problem

`Scenario A` 的时间语义第一轮已经落地，但 uncertainty 侧仍然缺一个可执行 contract。

当前代码基线里，“confidence” 实际上混着三条不同语义通道：

- `meta.confidence`
  - 写入层/视图层使用的 source confidence
- `Body.confidence`
  - `ProbLog` 分支权重
- `CandidateSet.confidence`
  - `ProbLog` 结果概率；`native/souffle` 为 `None`

与此同时，`Scenario A` 需要的是另一类能力：

- `Pc` 之类的风险概率是否低于阈值
- 处置成功概率是否高于阈值
- 这些比较要能进入 trace / audit，而不是只停留在 UI 展示的 `confidence`

如果不先把这条 lane 收敛出来，后续实现会出现两个问题：

1. 把 `meta.confidence` 误当成 threshold-bearing probability 使用
2. 为了比较浮点概率而去改全局 `where` 比较器或 `CandidateSet` 稳定接口

本切片的目标就是先给 `Scenario A` 建立一个最小 uncertainty contract，并且不把问题扩成全局 runtime 重构。

## 2. Goals

- 为 `Scenario A` 定义第一条可实现的 uncertainty 子切片。
- 明确分离以下三条语义 lane：
  - source/display `confidence`
  - probabilistic engine probability
  - scenario threshold probability
- 为 `Pc` / 成功率这类 threshold-bearing value 定义一个可写、可比较、可 explain 的 shared contract。
- 继续复用现有 `where` 比较链，不新增浮点比较器、不修改 `CandidateSet` 稳定结构。
- 让 uncertainty threshold check 仍然走 fact-backed explain / audit 路径。

## 3. Non-goals

- 不在本蓝图中重命名或移除现有 `meta.confidence`。
- 不在本蓝图中修改 `CandidateSet.confidence` 结构。
- 不在本蓝图中新增 float comparison where atom 或全局浮点比较语义。
- 不在本蓝图中决定 `ProbLog` 的长期架构角色。
- 不在本蓝图中覆盖完整的 LLM extraction confidence / certainty taxonomy。
- 不把 unsourced ESSB 数值阈值写成标准事实。

## 4. Current Context

- 当前实现入口：
  - `meta.confidence` 是 write protocol / view display 的稳定字段，值域 `(0, 1]`
  - `confidence_strategy` 只影响 `find/run` 的结果呈现，不影响 reasoning
  - `Body.confidence` 只在 `mode="problog"` 路径中消费
  - `CandidateSet.confidence` 目前表示 `ProbLog` 概率值；`native/souffle` 为 `None`
- 当前已知约束：
  - 原生比较链当前只接受 `int/time`，不接受 float threshold compare
  - `RuleTraceArtifact` 已有 `pred_witnesses` 与 `non_fact_steps.details.binding`，无需新增 uncertainty 专用 carrier
  - `Scenario A` 的 uncertainty 必须和现有 temporal `T1` 一样，优先走 fact-backed + existing compare contract
- 当前相关蓝图与参考：
  - 母蓝图已经把 `uncertainty-and-confidence` 标记为 `Scenario A` 的中期必要切片
  - `Scenario A Temporal Semantics` 已证明：如果收敛成 shared preset + existing compare，能避免 runtime 表面失控
  - `cross-domain-compliance-framing.md` 中的概率/成功率数字只用于 scenario pressure，不作为标准核实结果

## 5. Proposed Shape

### 5.1 Adopted Narrowing

第一轮 uncertainty 切片不先改全局 `confidence`，也不直接扩 `ProbLog`。

当前 adopted narrowing 是：

- 先为 `Scenario A` 建立 **threshold-bearing probability lane**
- 这条 lane 与 `meta.confidence` / `Body.confidence` / `CandidateSet.confidence` 分离

### 5.2 Semantic Lane Separation

本蓝图明确区分三条 lane：

1. `source/display confidence`
   - `meta.confidence`
   - `view.confidence_strategy`
   - 作用：来源质量、读侧呈现聚合

2. `probabilistic reasoning probability`
   - `Body.confidence`
   - `CandidateSet.confidence`
   - 作用：`ProbLog` 分支权重与结果概率

3. `scenario threshold probability`
   - `Scenario A` 风险/成功率事实与阈值比较
   - 作用：判断 requirement / obligation 是否满足阈值条件

第一轮只实现第 3 条 lane，不重做前两条。

### 5.3 Scalar Probability Convention

> **U1（adopted）：Scenario A threshold probability 不使用 float compare，也不复用 `meta.confidence`。它采用 fact-backed integer scalar convention。**
>
> 第一轮统一使用：
>
> - canonical scalar：`ppm`（parts per million）
> - schema type：`int`
> - 规则比较：已有 `<=` / `>=`
>
> 例子：
>
> - `Pc = 1e-4` -> `100 ppm`
> - `success = 90%` -> `900000 ppm`
>
> 这样可以继续复用现有比较链，不引入 float comparison runtime contract。

### 5.4 Shared Preset Owner

> **U2（adopted）：第一轮 Scenario A uncertainty preset 归属 `factpy_kernel.ecss.uncertainty`，不提升为顶层通用模块。**
>
> 它只拥有 Scenario A 驱动的 domain preset，例如：
>
> - `ecss:collision_probability_ppm`
> - `ecss:collision_probability_threshold_ppm`
> - `ecss:disposal_success_probability_ppm`
> - `ecss:disposal_success_threshold_ppm`
>
> 以及：
>
> - `ecss_uncertainty_predicates()`
> - `extend_schema_ir_with_ecss_uncertainty_predicates()`

### 5.5 Explain / Audit Contract

> **U3（adopted）：uncertainty threshold check 继续走既有 explain contract，不新增专用 trace schema。**
>
> - 测量值与阈值都应优先 fact-backed，作为 predicates 写入 ledger
> - 它们的 `asrt_id` 进入 `pred_witnesses`
> - 比较结果绑定值继续走 `non_fact_steps.details.binding`
>
> 这样：
>
> - threshold check 仍可通过 `explain_ref(kind="assertion")` 下钻到原始概率/阈值断言
> - `RuleTraceArtifact` schema 不需要新增 uncertainty 字段

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不把 `meta.confidence` 重新解释成 Scenario A threshold probability
  - 不新增 float comparison atom
  - uncertainty lane 先定义为 shared preset，再谈 adapter-specific 语义
- 明确不做的内容：
  - 不在本蓝图中实现完整 certainty taxonomy
  - 不在本蓝图中扩展 `ProbLog` 输出 carrier
  - 不在本蓝图中实现 richer uncertainty aggregation UI
- 兼容性约束：
  - `meta.confidence`、`Body.confidence`、`CandidateSet.confidence` 当前 contract 保持兼容
  - `RuleTraceArtifact` / `SupportArtifact` schema 保持不变
  - explain / audit 继续沿用 `pred_witnesses` + `details.binding`

## 7. Acceptance

- [ ] Scenario A threshold-bearing probability lane 已与现有 confidence/probability lane 分离
- [ ] `factpy_kernel.ecss.uncertainty` 已定义并成为 shared preset owner
- [ ] uncertainty predicates 使用 `int` scalar（`ppm`），不使用 float compare
- [ ] threshold rule 可通过 predicates + 现有 `<=` / `>=` 表达，不需要新 where atom
- [ ] measurement/threshold assertions 均可进入 `pred_witnesses`
- [ ] `RuleTraceArtifact` schema 不因该切片新增字段
- [ ] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 新建 `ecss.uncertainty` preset owner，定义 first-round probability/threshold predicates 与 schema helper。
2. 用 targeted regression 验证：schema helper 幂等、threshold compare 可运行、trace anchor 进入 `pred_witnesses` 与 `details.binding`。
3. 更新 `ecss` / `sdk` / `core` / `service` 文档，写清 lane separation 与 `ppm` convention。

## 9. Docs To Update

- `src/factpy_kernel/ecss/docs/README.md`
- `src/factpy_kernel/ecss/docs/01_overview.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.en.md`
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `factpy_kernel.ecss.uncertainty` shared preset owner，定义 collision/disposal probability 与 threshold 的 `ppm` predicates，以及 `extend_schema_ir_with_ecss_uncertainty_predicates(...)`
  - 第一轮 uncertainty lane 通过 fact-backed integer scalar + 既有 `<=` / `>=` 比较语法落地，不新增 float compare 或新的 where atom
  - explain / audit 继续沿用既有 contract：测量值/阈值 assertions 进入 `pred_witnesses`，数值比较绑定值进入 `non_fact_steps.details.binding`
  - `ecss`、`authoring`、`sdk`、`core`、`service` 文档已同步写清三条 lane 分离：source/display confidence、probabilistic engine probability、Scenario A threshold probability
- 与 blueprint 不同的地方：
  - 没有新增 `sdk` 层 uncertainty convenience wrapper
- 为什么会有这些调整：
  - 当前切片的目标是 shared contract 和 lane separation；新增 facade helper 会扩大 API 面，但对 acceptance 不构成必需条件
- 归档说明：
  - 本蓝图已完成第一轮 `Scenario A / uncertainty-and-confidence` 最小落地，归档到 `docs/blueprints/archive/`
