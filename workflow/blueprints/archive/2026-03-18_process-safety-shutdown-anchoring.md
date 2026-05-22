# Task Blueprint: Process Safety Shutdown Anchoring

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
  - [2026-03-18_aml-suspicious-account-anchoring.md](../archive/2026-03-18_aml-suspicious-account-anchoring.md)
  - [2026-03-18_aml-event-aggregation-semantics.md](../archive/2026-03-18_aml-event-aggregation-semantics.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_process-safety-shutdown-anchoring.audit.md](./2026-03-18_process-safety-shutdown-anchoring.audit.md)

## 1. Problem

`ECSS` 与 `AML` 两条场景线已经分别证明：

- explain / audit delivery substrate 可以跨域复用
- `T1 temporal`、`U1 threshold`、materialized aggregation helper 都能支撑 first-round walkthrough
- 但三类更重的 capability gap 仍未被真实触发为 blocker：
  - `T2 sequence/state semantics`
  - `judgment / obligation contract`
  - `weak-signal uncertainty combination`

如果下一条场景线继续停留在“reviewable flag / case walkthrough”这一类形状，增量信息会很低。第三域更应该刻意选择一个能更直接压到 **judgment contract** 的场景，同时避免一上来就掉进完整 `T2` 或概率组合。

## 2. Goals

- 选择一个第三域场景，优先测试当前 substrate 在 `judgment / obligation` 边界上的真实能力。
- 比较至少两个切片，避免直接跳到实现。
- 产出 adopted next-slice recommendation，而不是直接开始编码。

## 3. Non-goals

- 不实现工业控制 / 安全系统逻辑。
- 不提供真实工艺安全建议或监管解释。
- 不在本蓝图里直接冻结新的 runtime/audit contract。
- 不把 `T2` / uncertainty / judgment 三个 gap 一次性混切。

## 4. Current Context

- `ECSS` 更偏 requirement/compliance 与 temporal/uncertainty placeholders。
- `AML` 更偏 case-review、trigger、aggregation materialization honesty。
- 这两条线都没有真正逼出：
  - “系统是否必须在 contract 层表达 `must act now` 的 judgment object”

因此，第三域应尽量满足：

- 结果不是单纯 `flagged`
- 结果更接近 `shutdown required` / `trip required` / `isolate immediately`
- explain 仍然要能被 operator 读懂

authority note:

- 本蓝图中的 process safety 场景只是能力锚点，不代表真实 SIS / PLC / interlock 设计。

## 5. Comparison Memo

### 5.1 Why Process Safety

过程安全场景和现有两条线有一个关键差异：

- `ECSS` 与 `AML` 都允许 first-round 用 `flag-style placeholder` 过渡
- process safety 更自然的问题是：
  - `high temperature and pressure alarm` 只是一个 flag
  - 还是已经到了 `shutdown required` / `trip required`

这能更直接回答：当前系统是不是已经需要正式的 judgment contract，而不只是再做一个更复杂的 walkthrough。

### 5.2 Cut A: Alarm Review

候选切片 A：

- 多个传感器 threshold / state facts
- 单个 composite rule run
- 结果是 `alarm_review_required`
- operator 通过现有 explain stack 回看为什么系统要求人工 review

优点：

- 与现有 substrate 高度兼容
- 很容易复用 AML/ECSS 的 placeholder 路线

缺点：

- 过于接近 `AML review` / `trigger`
- 很可能再次证明“当前系统还能站住”，而不是逼出新 blocker

### 5.3 Cut B: Shutdown Command

候选切片 B：

- 多个传感器 threshold / state / interlock facts
- 单个 composite rule run
- 结果不是 review flag，而是更接近：
  - `shutdown_required`
  - `trip_required`
  - `isolation_required`

这条切片会自然压到三个问题中的第一个：

- 当前系统是否还能继续用普通 predicate / rule result 承载“必须动作”的输出
- 还是已经需要正式 judgment / obligation contract

它的优点：

- 对现有场景线形成真正新的压力
- 如果当前 substrate 还够用，就说明 judgment contract 还能继续后置
- 如果不够，就能第一次把 `judgment / obligation` 明确逼成 blocker

它的风险：

- 如果 scope 太大，容易顺手把 interlock state propagation 也拉进来，滑向 `T2`

### 5.4 Near-term Recommendation

当前 draft 的推荐是：

- **近端优先：`Shutdown Command`**
- **后置参考：`Alarm Review`**

理由：

1. `Alarm Review` 太像 AML 的 operator-facing case review，增量信息不足。
2. `Shutdown Command` 更直接测试当前系统是否还能把“must-act”结果继续塞在 flag-style surface 里。
3. 只要把输入保持为 pre-materialized / explicit state facts，它可以优先压力测试 `judgment contract`，而不必立刻滑进 `T2`。

### 5.5 Gate Resolution

这两个 gate 问题现在都可以直接关闭。

**Gate Q1 adopted answer：现有 predicate/result surface 足以支撑 first-round `Shutdown Command` walkthrough。**

原因很直接：

- 在 rule engine 层，`shutdown_required` 与 `aml:review_required` 没有结构性区别
- 两者本质上都只是：
  - 某条 rule 是否产出结果行
  - explain trace 是否能展示 supporting facts 与 compare checks
- “这是 flag 还是 command”的差别，目前主要发生在 consumer 对结果语义的解释，而不是 rule execution contract 本身

因此，judgment / obligation contract 还不是 immediate blocker。它只有在下列需求出现时才会变成真实 blocker：

- contract 层必须区分：
  - `shutdown_required`
  - `shutdown_recommended`
  - `shutdown_under_review`
- downstream consumers 需要 first-class 查询：
  - “当前所有 active obligations”
  - 而不只是“哪些 rule runs 产出了某个 predicate”
- 结果本身必须携带更重的 lifecycle / deadline semantics

这些都不属于 first-round walkthrough 的目标。

如果 walkthrough 暴露问题，更可能首先暴露的是：

- delivery wording gap
  - 例如 narrative / NL 把 operator 需要看到的 “required” 说成了过于中性的 “flagged”

而不是 contract-level gap。

**Gate Q2 adopted answer：是，inputs 必须保持为 pre-materialized facts。**

- 传感器读数
- alarm states
- interlock states / inhibit facts

都应先以 facts 形式写入，再由 downstream rule 做 conjunction + threshold 判断。

这与 AML aggregation 的结论一致：

- first-round 不应让 rule 自己承担轮询、状态机推进或 sequence/state evaluation
- 否则就会直接滑入 `T2`

**因此 adopted next blueprint 是：**

- `process-safety-shutdown-walkthrough`

不是先开 `judgment-obligation-contract`。

这个 walkthrough 的价值就在于：它会真实检验 “must-act result” 是否仍能在现有 surface 上被 operator 清楚理解；只有当它失败时，judgment contract 才会从 deferred gap 变成 immediate next slice。

## 6. Boundaries And Invariants

- 本蓝图首先服务于识别 `judgment contract` 是否成为真实 blocker。
- 若发现真正 blocker 是 `T2`，也必须明确写出为什么 judgment 反而还可后置。
- 外部/工作参考只能作为压力来源，不是当前 truth。

## 7. Acceptance

- [x] 已明确第三域为何选 process safety，而不是另一个 review-style domain
- [x] 已比较 `Alarm Review` 与 `Shutdown Command`
- [x] 已给出 adopted near-term recommendation
- [x] 已写清 next-blueprint gate：walkthrough 还是先开 judgment contract

## 8. Plan

1. 比较两个切片，判断哪个更有可能逼出真正的新 blocker。
2. 明确 `Shutdown Command` 是否已经足以把 judgment contract 逼成 immediate blocker。
3. 产出 adopted next-slice recommendation。

## 9. Docs To Update

- 无；本切片是分析蓝图

## 10. Outcome / Deviations

- adopted recommendation：
  - 近端优先切片采用 `Shutdown Command`
  - 下一条蓝图直接开 `process-safety-shutdown-walkthrough`
- gate answer：
  - 现有 predicate/result surface 足以支撑 first-round walkthrough
  - inputs 必须保持为 pre-materialized alarm / interlock / sensor state facts
- 若 judgment contract 仍可后置，为什么：
  - `shutdown_required` 在 first-round walkthrough 中仍可被视为普通 predicate result
  - immediate pressure 更可能落在 operator-facing wording/readability，而不是 result carrier contract
  - judgment / obligation contract 只有在 lifecycle-differentiated results 或 first-class obligation query 成为必需时，才会变成真正 blocker
- 归档说明：
  - 本切片是纯分析蓝图；gate 收敛后直接归档到 `docs/blueprints/archive/`，不涉及代码、测试或模块 docs 变更。
