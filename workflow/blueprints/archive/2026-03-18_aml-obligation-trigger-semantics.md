# Task Blueprint: AML Obligation Trigger Semantics

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_aml-suspicious-account-anchoring.md](../archive/2026-03-18_aml-suspicious-account-anchoring.md)
  - [2026-03-18_aml-case-review-walkthrough.md](../archive/2026-03-18_aml-case-review-walkthrough.md)
  - [2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
  - [2026-03-18_scenario-a-uncertainty-and-confidence.md](../archive/2026-03-18_scenario-a-uncertainty-and-confidence.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_aml-obligation-trigger-semantics.audit.md](./2026-03-18_aml-obligation-trigger-semantics.audit.md)

## 1. Problem

`AML-Review` 已经证明：对于 single composite rule run，当前 explain delivery substrate 足以支撑 investigator-facing case review。

剩下真正还没被验证的，是 `AML suspicious-account` 场景里更难的那一层：

- 系统能否表达“在此刻触发 SAR / review obligation”；
- 这个 trigger 是否能仅用现有 `T1 temporal + fact-backed threshold/signal predicates` 表达；
- 还是说它已经越过当前 substrate，必须先引入：
  - event aggregation / sequence semantics
  - deontic judgment contract
  - weak-signal uncertainty combination

这条蓝图的目标不是直接实现 AML trigger，而是先把这些 kernel-boundary 问题收敛清楚。否则下一轮实现很容易在同一个切片里同时偷扩：

- temporal aggregation
- judgment result shape
- uncertainty semantics

最终无法判断到底是哪一层真正成为 blocker。

## 2. Goals

- 用 `AML suspicious-account obligation trigger` 作为压力场景，评估当前 kernel/substrate 的边界。
- 明确回答三个按顺序收敛的问题：
  1. 现有 `T1 temporal` 是否足够表达 first-round trigger？
  2. 是否必须新增 `judgment` / deontic result contract？
  3. uncertainty 在此场景里是 hard blocker，还是可先用 fact-backed threshold/flag 占位？
- 给出 adopted next slice recommendation：
  - 直接开实现型 trigger walkthrough
  - 或先开某个 gap blueprint（aggregation / judgment / uncertainty）

## 3. Non-goals

- 不在本蓝图中实现 AML trigger 规则。
- 不在本蓝图中引入真实 AML 监管条款或法律解释。
- 不在本蓝图中设计完整 AML ontology。
- 不在本蓝图中直接实现新的 engine capability。
- 不在本蓝图中把 LLM / NL investigator workflow 拉进来。

## 4. Current Context

- `AML suspicious-account anchoring` 已把 `AML-Trigger` 定义为中期驱动场景。
- `AML case-review walkthrough` 已证明：
  - 单个 `rule_run_id` proof-entry 对 case review 足够
  - 当前五层 explain delivery 栈对 walkthrough 足够
- 但 walkthrough 故意避开了三类 harder semantics：
  - 事件时间聚合（如 36 小时窗口内多笔交易）
  - judgment / obligation result object
  - 多个弱信号组合的 uncertainty semantics
- 现有可复用的近似基座是：
  - `Scenario A T1 temporal semantics`
  - `Scenario A uncertainty threshold lane`
  - 既有 explain / audit / NL delivery substrate

authority note:

- working note 与 Rainbird comparison 只用于 design pressure，不构成 AML 监管事实。
- 本蓝图讨论的是 kernel 边界，不是 AML 业务正确性的最终定义。

## 5. Proposed Shape

### 5.1 Question Order

这条蓝图必须按严格顺序回答三个问题，不能并行发散：

1. `T1 temporal sufficiency`
2. `judgment contract necessity`
3. `uncertainty blocker vs placeholder`

原因：

- 如果第 1 问的答案已经是“必须有事件聚合 / sequence semantics”，那就没必要先讨论 judgment DTO。
- 如果第 1 问还能用现有 contract 占位，第 2 问才值得单独回答。
- uncertainty 必须最后判断，否则会掩盖真正的 temporal/deontic blocker。

### 5.2 Q1: Is Existing T1 Temporal Enough?

第一问不是“系统能否做完整 AML temporal reasoning”，而是更窄的：

- first-round trigger 是否可以通过 **上游先物化聚合结果 facts**，再在当前 rule runtime 中用已有 `T1` temporal checks 表达？

需要至少比较两种形状：

1. `pre-aggregated trigger facts`
   - 例如：
     - `windowed_structuring_signal(account_ref, window_ref, tx_count, total_amount)`
     - `high_risk_outflow_signal(account_ref, beneficiary_ref)`
   - runtime 只负责做 conjunction + threshold + explain

2. `in-rule event aggregation`
   - 直接在 runtime rule 中表达“36 小时窗口内 >=N 笔交易 + 后续汇总流向高风险受益方”
   - 这更接近 sequence / state / aggregation semantics

> **Q1（adopted answer）：对于 first-round AML trigger，现有 `T1 temporal` 只有在允许 `pre-aggregated facts` 的前提下才足够。**
>
> 原因不是偏好判断，而是 `T1` 已归档范围的直接推论：
>
> - `T1` 已明确支持：fact-backed temporal anchors + 现有比较语法
> - `T1` 已明确延后：state propagation、multi-step event sequence semantics、temporal materialization
>
> 因此：
>
> - `pre-aggregated trigger facts` 正是 `T1` 被设计来支撑的形状
> - `in-rule event aggregation` 则已经越过 `T1`，属于 `T2` / aggregation gap 问题

### 5.3 Q2: Does AML Trigger Need A New Judgment Contract?

第二问要收敛的是：

- first-round trigger 的输出是否还能暂时停留在普通 `rule_run` result row / suspicious flag
- 还是必须先引入具名 `judgment` / `obligation` result contract，才能让 explain/audit/consumer 有正确的主语

需要比较的两种形状：

1. `flag-style placeholder`
   - 输出仍是普通 predicate / candidate，例如：
     - `aml:suspicious_account_triggered`
     - `aml:review_required`
   - explain 仍走现有 `rule_run` / assertion drill-down

2. `judgment-style object`
   - 输出是新的具名 result kind，例如：
     - obligation triggered / not triggered
     - review required / not required
   - 这会影响 runtime/service/audit contract

> **Q2（adopted answer）：对于 first-round AML trigger，`flag-style placeholder` 足够，不必先开新的 judgment/deontic result contract。**
>
> 原因：
>
> - `AML-Review walkthrough` 已证明：`rule_run` result row + 既有 explain delivery 栈，已经能形成 investigator-facing 可读输出
> - first-round trigger 的目标是验证“何时触发”是否能被 explain，而不是立刻定义正式的 obligation object model
>
> 因此：
>
> - 第一轮可先输出普通 predicate / candidate，例如 `aml:suspicious_account_triggered` 或 `aml:review_required`
> - 只有当消费方面明确需要“obligation triggered vs suspicious candidate flagged”的 contract-level 区分时，judgment contract 才会成为下一条独立 gap

### 5.4 Q3: Is Uncertainty A Hard Blocker?

第三问要判断：

- 多个单独较弱的 signals（shared device / shared beneficiary / BO mismatch）是否必须在 first-round 就进入 certainty/probability semantics
- 还是可以先用 fact-backed threshold/flag 占位，把 uncertainty 留到下一轮

至少比较三种占位策略：

1. `boolean signal conjunction`
   - 各个 signal 已由上游判定为 present/absent
   - runtime 只做 conjunction

2. `fact-backed threshold lane`
   - 复用 `Scenario A uncertainty` 的思路，把某种 risk score / threshold 写成事实
   - runtime 只做 integer threshold compare

3. `true weak-signal combination`
   - 需要更明确的 certainty / probability / contribution semantics

> **Q3（adopted answer）：uncertainty 不是 first-round AML trigger 的 hard blocker。**
>
> 第一轮可接受的占位方式是：
>
> - `boolean signal conjunction`
> - 或 `fact-backed threshold lane`
>   - 复用 `Scenario A uncertainty` 的 `U1` 模式：integer scalar + existing compare
>
> 只有当 first-round 就要求回答“多个 individually-weak signals 如何组合成可解释 certainty/probability”时，uncertainty 才会升级为独立 gap。

### 5.5 Expected Outcome

> **Adopted conclusion：outcome 1 — existing substrate is enough for a first-round AML trigger walkthrough。**
>
> 条件已经由 Q1/Q2/Q3 收敛为：
>
> - temporal：使用 `pre-aggregated facts`（`T1` pattern）
> - output：使用 `flag-style placeholder`（既有 `rule_run` result pattern）
> - uncertainty：使用 `boolean/threshold placeholder`（`U1` pattern）
>
> 因此，下一条切片不应先开 gap blueprint，而应直接开：
>
> - `aml-trigger-walkthrough`
>
> 该 walkthrough 才是验证这些 placeholder 是否真的站得住的第一轮实现测试。
>
> **Deferred gaps**（若 walkthrough 暴露它们成为真实 blocker，再各自单独开 blueprint）：
>
> - `T2 / aggregation gap`
>   - runtime 原生 event aggregation / sequence semantics
> - `judgment contract gap`
>   - 正式 obligation / review-required result kind
> - `U2 / weak-signal combination gap`
>   - 多个弱信号组合的 certainty/probability semantics

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 先判断 sufficiency，再决定是否进入实现
  - 不能因为场景压力直接绕过已经冻结的 explain delivery contracts
- 明确不做的内容：
  - 不实现 walkthrough
  - 不定义真实监管逻辑
  - 不把所有 gap 一次性都纳入下条蓝图
- 兼容性约束：
  - 若 adopted conclusion 是“先开 gap blueprint”，该 gap 必须是单一主问题，不得重新混成时间+判断+不确定性大杂烩

## 7. Acceptance

- [x] 已明确回答 `T1 temporal` 对 first-round AML trigger 是否足够
- [x] 已明确回答是否必须新增 judgment/deontic result contract
- [x] 已明确回答 uncertainty 是 hard blocker 还是可占位
- [x] 已形成 adopted next-slice recommendation
- [x] authority boundary 已保持清晰，不把 working note 写成事实承诺

## 8. Implementation Plan

1. 用 `AML-Trigger` 场景把 temporal sufficiency 问题先收窄成“pre-aggregated facts vs in-rule event aggregation”。
2. 在 temporal 前提明确后，再判断 output 是否必须升级为 `judgment` contract。
3. 最后判断 uncertainty 是不是 first-round blocker，并给出 adopted next-slice recommendation。

## 9. Docs To Update

- 无；本切片第一轮为纯分析型蓝图，不改模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 本切片已将 `AML-Trigger` 的三个问题直接收口为 adopted answers：
    - `Q1`: `T1 temporal` 仅在允许 `pre-aggregated facts` 时足够；`in-rule event aggregation` 仍属 `T2`
    - `Q2`: first-round 使用 `flag-style placeholder` 足够，不必先开 judgment/deontic contract
    - `Q3`: uncertainty 不是 first-round blocker，可先用 boolean/threshold placeholder 占位
  - adopted next slice recommendation 已冻结为：
    - 直接进入 `aml-trigger-walkthrough`
    - 不先开 gap blueprint
  - 只有当 walkthrough 真正暴露 blocker 时，才分别拆成：
    - aggregation gap
    - judgment contract gap
    - weak-signal uncertainty gap
- 与 blueprint 不同的地方：
  - 无实质偏离；这条分析蓝图不再保留开放判断，直接依据已归档的 `T1/U1` scope 收口为 adopted conclusion。
- 为什么会有这些调整：
  - 三个问题的答案已经被既有蓝图边界决定，不需要再保留为开放分析项。
- 归档说明：
  - 该分析蓝图在形成 adopted next-slice recommendation 后归档到 `docs/blueprints/archive/`。
