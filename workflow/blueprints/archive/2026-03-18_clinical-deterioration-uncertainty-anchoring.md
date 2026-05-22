# Task Blueprint: Clinical Deterioration Uncertainty Anchoring

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_scenario-a-uncertainty-and-confidence.md](../archive/2026-03-18_scenario-a-uncertainty-and-confidence.md)
  - [2026-03-18_aml-obligation-trigger-semantics.md](../archive/2026-03-18_aml-obligation-trigger-semantics.md)
  - [2026-03-18_process-safety-shutdown-anchoring.md](../archive/2026-03-18_process-safety-shutdown-anchoring.md)
  - [2026-03-18_process-safety-shutdown-walkthrough.md](../archive/2026-03-18_process-safety-shutdown-walkthrough.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_clinical-deterioration-uncertainty-anchoring.audit.md](./2026-03-18_clinical-deterioration-uncertainty-anchoring.audit.md)

## 1. Problem

`ECSS`、`AML`、`process safety` 三条场景线已经把另外两个 deferred gaps 都往后推了：

- `T2 sequence/state semantics`
  - 还没有被真实场景逼成 immediate blocker
- `judgment / obligation contract`
  - 也还没有被 first-round walkthrough 逼成 immediate blocker

剩下还没有被正面压力测试的，就是第三个 gap：

- `weak-signal uncertainty combination`

也就是：

- 没有任何单一条件足以触发结果
- 但多个 individually-weak signals 一起出现时，系统应该升级结论

如果下一条场景线仍然选择单阈值或单条件即可成立的判断，现有 `boolean/threshold placeholder` 很可能还能继续过关，不会给出新信息。因此第三域应该刻意选择一个“多项轻度异常共同推高风险”的形状。

## 2. Goals

- 选择一个第三域场景，优先测试当前 substrate 在 `weak-signal uncertainty` 边界上的真实能力。
- 比较至少两个切片，避免直接跳到实现。
- 产出 adopted next-slice recommendation，而不是直接开始编码。

## 3. Non-goals

- 不实现临床规则、分诊协议或医疗建议。
- 不在本蓝图里直接冻结新的 uncertainty contract。
- 不把 uncertainty、judgment、T2 一次性混切。
- 不设计完整 clinical ontology 或 scoring engine。

## 4. Current Context

- `Scenario A uncertainty` 已经证明：
  - `U1` 路径，也就是 fact-backed integer threshold + compare chain，是稳定可用的
- `AML` 线又进一步证明：
  - 只要问题仍可表述为 pre-materialized signal/threshold placeholders，当前 explain delivery 就还能站住
- `process safety` 则证明：
  - 即便结果看起来更接近 must-act，judgment contract 也还没被逼成 blocker

因此，当前最有价值的新问题是：

- 当系统必须解释“多个 individually-weak indicators 为什么会组合成 escalation”时，
- 现有 `U1` placeholder 到底还能不能继续撑住？

## 5. Comparison Memo

### 5.1 Why Clinical Deterioration

clinical deterioration / sepsis-style triage 的价值在于，它天然不是“一个指标过线就触发”的形状。

更典型的压力是：

- mild fever
- mildly elevated heart rate
- mildly elevated respiratory rate
- mildly low blood pressure
- mild confusion / lactate / white-cell abnormality

任何一个单项都可能不足以单独触发 escalation，但若 4/6 同时出现，系统应升级结论。

这比 vendor risk 更适合作为下一条 uncertainty pressure line，因为：

- vendor risk 很容易再次退化成 pre-scored checklist threshold
- clinical deterioration 更自然要求系统解释“组合为什么重要”

### 5.2 Cut A: Single-Threshold Clinical Alert

候选切片 A：

- 仍然围绕单阈值或单项严重异常
- 例如：
  - temperature above critical threshold
  - oxygen saturation below critical threshold
- 输出是 `review_required` 或 `rapid_response_required`

优点：

- 非常容易复用现有 `U1` path
- 几乎不需要新 contract

缺点：

- 这基本不会提供新信息
- 它再次测试的只是 threshold placeholder，而不是 weak-signal combination

### 5.3 Cut B: Weak-Signal Escalation

候选切片 B：

- 多个 mild abnormalities individually are insufficient
- 但它们共同组成一个 escalation candidate
- 输出可先保持为普通 predicate result，例如：
  - `clinical:deterioration_review_required`
  - `clinical:sepsis_escalation_candidate`

这条切片真正会压到的问题是：

- 当前系统是否还能把这种组合继续伪装成：
  - 多个 boolean facts + 一个 count threshold
  - 或一个上游 materialized risk score + compare
- 还是必须引入更显式的 uncertainty semantics，来表达：
  - why these weak signals combine
  - how much each contributes
  - why no single one was enough

它的优点：

- 很可能第一次真正触发 `weak-signal uncertainty` gap
- 就算当前 substrate 还能过，也会更清楚地暴露它的 honesty boundary

它的风险：

- 如果 scope 没收紧，容易顺手把时间序列与 judgment 一起拉进来

### 5.4 Near-term Recommendation

当前 draft 的推荐是：

- **近端优先：`Weak-Signal Escalation`**
- **后置参考：`Single-Threshold Clinical Alert`**

理由：

1. `Single-Threshold Clinical Alert` 太接近现有 `U1` 成功路径，增量信息极低。
2. `Weak-Signal Escalation` 才真正对应当前唯一还没被逼出的 deferred gap。
3. 只要把输入暂时保持为 pre-materialized indicator facts，并且暂不引入更重 judgment，就可以先纯粹测试 uncertainty boundary。

### 5.5 Gate Resolution

这两个 gate 问题现在都可以直接关闭。

**Gate Q1 adopted answer：placeholder 在技术上仍足以支撑 first-round walkthrough，但这会第一次把 success criterion 推到 explain quality / honesty，而不只是 explain correctness。**

原因是：

- 从 mechanical shape 看，当前系统完全可以把 weak-signal escalation 表达成：
  - 多个 boolean weak-signal facts
  - 一个 materialized count fact，例如 `clinical:abnormal_indicator_count = 4`
  - 一个 compare threshold，例如 `count >= 4`
- 这条链在 current substrate 上是能工作的：
  - raw rule trace
  - summary
  - narrative
  - NL
  - static proof-entry

但这次的 honesty boundary 与此前不同：

- 在 `AML`、`process safety` 等场景里，每个 supporting signal 本身都已经有独立意义
- 在 weak-signal escalation 里，单个 mild abnormality **恰恰没有独立决定性**
- 因此，如果系统只输出：
  - “4 signals >= threshold”
  - 却没有把 “这些 signals individually weak, collectively significant” 的语义表达出来，
  - 那 explain 虽然 technically correct，却可能在语义上误导

所以，placeholder 不是立即失效；但 walkthrough 必须把一条此前没有的成功标准写死：

- narrative / NL 必须诚实表达“组合 significance”
  - 而不只是复述 count/threshold 机械关系

**Gate Q2 adopted answer：如果 walkthrough 失败，而且失败表现为 explain technically correct but semantically misleading，那么 blocker 就是 `weak-signal uncertainty semantics`。**

这时 blocker 不是：

- judgment contract
  - 因为结果仍可保持为普通 flag / review-required predicate
- `T2`
  - 因为这里需要的是组合 significance，不是时间序列/状态传播

因此 adopted next blueprint 是：

- `clinical-weak-signal-walkthrough`

并且它必须显式携带一个新的成功标准：

- explain output 必须能诚实表达：
  - escalation 来自多个 individually-weak signals 的组合
  - 而不是暗示某个单一指标本身就足够决定结论

如果这个标准失败，后续单一 follow-on gap 就是：

- `weak-signal-uncertainty-contract`

judgment 与 T2 继续后置，原因也已经明确：

- judgment：
  - first-round 结果仍只是 `deterioration_review_required` 风格 flag
  - 不需要 lifecycle-differentiated result kind
- T2：
  - 这里的压力来自 concurrent weak-signal combination
  - 不是 sequence/state evolution

## 6. Boundaries And Invariants

- 本蓝图首先服务于识别 `weak-signal uncertainty` 是否成为真实 blocker。
- 若发现真正 blocker 是 judgment 或 T2，也必须明确写出为什么 uncertainty 反而还可后置。
- 外部/工作参考只能作为压力来源，不是当前 truth。
- 不允许在本蓝图里偷做实现或 contract freeze。

## 7. Acceptance

- [x] 已明确第三域为何选 clinical deterioration，而不是另一个容易退化为 checklist threshold 的 domain
- [x] 已比较 `Single-Threshold Clinical Alert` 与 `Weak-Signal Escalation`
- [x] 已给出 adopted near-term recommendation
- [x] 已写清 next-blueprint gate：walkthrough 还是先开 uncertainty contract

## 8. Plan

1. 比较两个切片，判断哪个更可能逼出真正的新 blocker。
2. 明确 `Weak-Signal Escalation` 是否已经足以把 uncertainty contract 逼成 immediate blocker。
3. 产出 adopted next-slice recommendation。

## 9. Docs To Update

- 无；本切片是分析蓝图

## 10. Outcome / Deviations

- adopted recommendation：
  - 近端优先切片采用 `Weak-Signal Escalation`
  - 下一条蓝图直接开 `clinical-weak-signal-walkthrough`
- gate answer：
  - placeholder 在技术上仍可工作
  - 但 walkthrough 必须显式验证 explain quality / honesty：是否真正表达了组合 significance
- 若 uncertainty 仍可后置，为什么：
  - first-round 仍可先用 placeholder 形状验证 mechanical reuse
  - 只有当 walkthrough 暴露“technically correct but semantically misleading”时，uncertainty contract 才会从 deferred gap 变成 immediate blocker
- 归档说明：
  - 本切片是纯分析蓝图；gate 收敛后直接归档到 `docs/blueprints/archive/`，不涉及代码、测试或模块 docs 改动。
