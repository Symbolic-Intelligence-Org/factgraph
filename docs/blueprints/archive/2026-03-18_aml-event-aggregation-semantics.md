# Task Blueprint: AML Event Aggregation Semantics

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_aml-suspicious-account-anchoring.md](../archive/2026-03-18_aml-suspicious-account-anchoring.md)
  - [2026-03-18_aml-case-review-walkthrough.md](../archive/2026-03-18_aml-case-review-walkthrough.md)
  - [2026-03-18_aml-obligation-trigger-semantics.md](../archive/2026-03-18_aml-obligation-trigger-semantics.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_aml-event-aggregation-semantics.audit.md](./2026-03-18_aml-event-aggregation-semantics.audit.md)

## 1. Problem

`AML case-review walkthrough` 与 `AML trigger walkthrough` 都已经证明：

- 当前 explain delivery substrate 足以支撑 single-rule-run walkthrough
- 但前提是输入 facts 已经是上游 **pre-aggregated** 的结果

这意味着 AML 线当前最大的真实空白，不在 delivery，也不在 first-round judgment/uncertainty，而在更上游的问题：

- 若输入不再是预先聚合好的 `windowed_structuring_signal`，
- 而是原始 transaction / device / beneficiary / timing 事件，
- 当前 kernel 是否已经足以表达“窗口内多笔接近阈值交易 + 同期风险信号”的 aggregation semantics？

如果答案是否定，就需要明确：

- 真实缺口究竟是 `T2 state propagation / sequence semantics`
- 还是只要一个较窄的 aggregation helper / materialization contract

这条蓝图的任务不是立刻实现 aggregation，而是把这个缺口收敛成 adopted next-slice recommendation。

## 2. Goals

- 判断 current substrate 是否已经足够表达 first meaningful AML event aggregation。
- 区分两类候选路线：
  - `pre-materialized helper contract`
  - `true T2 sequence/state semantics`
- 明确 aggregation 问题是否会先于 judgment contract / weak-signal uncertainty 成为 blocker。
- 产出 adopted next blueprint recommendation，而不是直接进入实现。

## 3. Non-goals

- 不直接实现新的 aggregation runtime。
- 不新增 judgment / obligation result contract。
- 不实现 weak-signal certainty combination。
- 不重做 explain delivery surface。
- 不设计完整 AML ontology 或监管规则库。

## 4. Current Context

已归档蓝图已经给出三条稳定事实：

- `AML case-review walkthrough`：single-rule-run investigator walkthrough 已够用。
- `AML obligation trigger semantics`：first-round trigger 可以先依赖 `pre-aggregated facts + flag-style placeholder + U1 placeholder`。
- `AML trigger walkthrough`：`T1 temporal` 与 `U1 threshold` placeholders 在 explain delivery 上都站得住。

所以现在唯一还未被验证的高价值问题是：

- 一旦不再假定 `windowed_structuring_signal` 等聚合事实已经由外部写入，
- 当前 `T1` temporal contract 是否仍然够用，还是必须进入 `T2`。

## 5. Analysis Questions

### 5.1 Minimal Aggregation Pressure

本蓝图只考虑一个最小 yet meaningful 的 AML aggregation 问题：

- 对同一 account，
- 在具名时间窗口内，
- 出现 `N` 笔接近阈值的交易，
- 且与至少一个高风险信号发生时间上相关联，
- 从而形成一个 downstream trigger candidate。

这里真正需要判断的是：

- 这件事是否还能通过“先 materialize 再 compare”的窄 contract 表达
- 还是必须让 rule evaluation 自己具备事件序列/窗口聚合能力

### 5.2 Candidate Route A: Pre-materialized Aggregation Helper

候选路线 A：

- 保持现有 rule engine / explain substrate 不变
- 在上游或写侧引入一个更显式的 aggregation helper / materialization contract
- 例如把窗口统计结果、近阈值交易计数、关联风险信号摘要先写成 facts
- runtime rules 仍只消费这些聚合后 facts

这条路线的潜在优点：

- explain delivery 基本不变
- 仍能走 fact-backed witness path
- 不需要立即进入 `T2`

它的风险是：

- aggregation logic 可能被推到 explain 之外
- downstream trace 看到的是 materialized summary，而不是真正的 event-sequence derivation
- 需要判断这是否已经足够诚实/可接受

### 5.3 Candidate Route B: True In-rule Event Aggregation

候选路线 B：

- 让 rule/derivation evaluation 直接面对原始事件
- 在 rule 执行中表达窗口、计数、关联、顺序或状态传播
- 这基本等价于进入 `T2 state propagation / sequence semantics`

这条路线的潜在优点：

- aggregation 不再依赖上游 materialization
- explain path 理论上可更接近真实 sequence reasoning

它的成本与风险也更明显：

- 需要新的 execution semantics
- 很可能需要新的 trace/explain contract 约束
- scope 远超当前 first-round placeholder 体系

### 5.4 Adopted Answer

**adopted answer：Route A（pre-materialized aggregation helper）足以支撑 first-round AML aggregation。**

explain honesty 的判断也已经可以收敛：

- pre-materialized aggregation facts 一旦写入 ledger，就会像其他 fact-backed predicates 一样进入 `pred_witnesses`
- trace 会诚实地告诉 consumer：
  - rule 看到了哪些 aggregation facts
  - 这些 facts 的值是什么
  - 哪些 compare checks 被执行了
- trace **不会**直接告诉 consumer aggregation helper 是如何从原始事件算出这些 summary facts 的
  - 但这与当前 `T1 temporal` 的诚实性边界是一致的：rule trace 告诉你 rule 看到了 `time/window` anchors，却不追溯这些 anchors 最初如何形成

因此，对 first-round 而言，这个诚实性边界是可接受的，原因有三：

1. `AML trigger walkthrough` 已经证明 pre-aggregated temporal facts 可以形成 readable、drillable 的 explain output。
2. aggregation helper 自身如何计算其输出，可以在未来作为独立的 materialization contract / helper trace 问题处理；它不是当前 `rule_run` explain contract 的 blocker。
3. Route B 并不会自动带来“更诚实”的 explain。它只会把 aggregation 过程搬进 evaluation path，但要让这些 intermediate steps 可读，仍需要新的 execution semantics 和更重的 trace contract 设计。

### 5.5 Deferred Route B And Next Slice

Route B 并没有被否定，只是被明确后置：

- true in-rule event aggregation 基本等价于 `T2 state propagation / sequence semantics`
- 这是 kernel 级能力，不只是 AML 的一个局部 helper
- 它应该在某个 scenario **真正要求** sequence/state reasoning 时，以单独 capability blueprint 打开，而不是作为 AML first-round aggregation 的默认下一步

因此，这条蓝图的 adopted next-slice recommendation 是：

- `aml-aggregation-materialization-walkthrough`

它的目标不是直接进入 `T2`，而是验证：

- pre-materialized aggregation helper 是否已经足够
- 当 helper 的输入（raw transactions、window boundaries、risk anchors）也以 facts 形式存在时，
- 当前 explain stack 是否能清楚表达“rule 看到了什么”和“helper 事先算出了什么”之间的边界

judgment / uncertainty 继续后置，原因也已经明确：

- judgment contract：
  - aggregation 不会改变 first-round result shape；trigger 结果仍然只是 flag-style placeholder
  - 只有当消费者必须在 contract 层区分 `flagged` / `review_required` / `obligation_triggered` 时，judgment 才会成为单独蓝图
- uncertainty：
  - aggregation 不会自动引入 weak-signal combination
  - 只要每个 supporting signal 仍然以 boolean/threshold placeholder 表达，uncertainty 就不是 first-round blocker
  - 真正的 U2 只会在系统需要解释“多个 individually-weak signals 如何组合成判断”时才成为必要能力

## 6. Boundaries And Invariants

- 必须把问题保持为 **aggregation first**，不与 judgment/uncertainty 混切。
- 若 adopted answer 指向 gap，该 gap 必须是单一主问题。
- 不允许在本蓝图里偷做 implementation 或 contract freeze。
- 若引用外部资料，只能作为 pressure/rationale，当前 truth 仍以 module docs 与归档蓝图为准。

## 7. Acceptance

- [x] 已明确 first meaningful AML aggregation 的最小压力问题
- [x] 已比较 route A（pre-materialized helper）与 route B（true T2 semantics）
- [x] 已给出 adopted next-slice recommendation
- [x] 已明确 judgment / uncertainty 为什么继续后置
- [x] 若 adopted answer 指向 gap，该 gap 已被单一化命名

## 8. Plan

1. 明确最小 aggregation 压力问题，不让问题发散成完整 AML engine 设计。
2. 判断 route A 是否足够，以及 explain honesty 能否接受。
3. 若 route A 不够，明确是否直接进入 T2；若够，命名下一条实现切片。

## 9. Docs To Update

- 无；本切片是分析蓝图

## 10. Outcome / Deviations

- 最终 adopted answer：
  - Route A（pre-materialized aggregation helper）足以支撑 first-round AML aggregation。
  - `rule_run` explain honesty 的可接受边界是：“trace 诚实展示 rule 看到了哪些 aggregation facts 与 compare checks”，而不是“trace 必须内建展示 helper 如何从原始事件算出这些 facts”。
  - Route B 并未被否定，但它已明确收敛为 `T2 state propagation / sequence semantics` 类能力扩展，不应作为 AML first-round aggregation 的默认下一步。
- 后续推荐蓝图：
  - `aml-aggregation-materialization-walkthrough`
- 为什么 judgment / uncertainty 继续后置：
  - aggregation 先决定系统能处理什么输入 facts；
  - judgment 仍只影响结果 contract；
  - uncertainty 仍只影响多个弱信号如何组合；
  - 在 first-round aggregation 问题里，这两者都不是主 blocker。
- 归档说明：
  - 本切片是纯分析蓝图；结论收敛后直接归档到 `docs/blueprints/archive/`，不涉及代码、测试或模块 docs 改动。
