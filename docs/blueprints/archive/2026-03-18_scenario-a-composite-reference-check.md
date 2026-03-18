# Task Blueprint: Scenario A Composite Reference Check

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/audit`
  - `src/factpy_kernel/ecss`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-uncertainty-and-confidence.md](../archive/2026-03-18_scenario-a-uncertainty-and-confidence.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [src/factpy_kernel/ecss/docs/01_overview.md](../../../src/factpy_kernel/ecss/docs/01_overview.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-18_scenario-a-composite-reference-check.audit.md](./2026-03-18_scenario-a-composite-reference-check.audit.md)

## 1. Problem

`Scenario A` 的两个基础子切片已经分别落地：

- `T1 temporal semantics`
- `U1 uncertainty-and-confidence`

但它们目前还只在各自的单维回归里被验证，没有经过一次真正的组合检查。

对于 `ESSB-ST-U-007` 风格的 reference scenario，真实判断更接近以下 conjunction：

- 事件/义务发生在具名时间窗口内
- collision probability 满足阈值约束
- disposal success probability 满足阈值约束

如果这三类条件在同一条 rule / trace / audit 路径里能顺畅组合，说明当前 `Scenario A` 的第一阶段基线已经足够支撑一个最小 reference check；如果不能，则暴露出的缺口将比抽象讨论更具体，例如：

- 是否需要 `T2 state propagation`
- 是否需要新的 delivery shape
- 是否出现 trace / audit 交付上的真实短板

因此，这个切片的目标不是再发明新语义，而是验证现有 temporal + uncertainty substrate 组合后是否已经形成一个稳定、可交付的 Scenario A reference check。

## 2. Goals

- 构造一个具名的 `Scenario A` composite rule，组合：
  - temporal window / deadline
  - collision probability threshold
  - disposal success threshold
- 用真实 trace / audit readback 验证：
  - `pred_witnesses` 同时覆盖时间 anchor 与概率 anchor
  - `details.binding` 同时带出时间值与 `ppm` 值
- 评估当前 substrate 是否已经足够支撑 first-round Scenario A 演示
- 判断下一步更自然的后续是：
  - delivery/demo 形态
  - 还是 `T2 state propagation / temporal materialization`

## 3. Non-goals

- 不在本蓝图中新增 temporal 或 uncertainty 新语义
- 不在本蓝图中实现 `T2 state propagation`
- 不在本蓝图中扩展 `RuleTraceArtifact` schema
- 不在本蓝图中新增 live endpoint 或 graph UI
- 不在本蓝图中把 working note 的 ESSB 数值写成标准原文解释
- 不把 Rainbird 的 certainty 机制作为实现目标

## 4. Current Context

- 当前已实现基线：
  - `factpy_kernel.ecss.temporal`
  - `factpy_kernel.ecss.uncertainty`
  - temporal / uncertainty checks 都能通过 fact-backed predicates + 既有比较语法运行
  - explain / audit 都复用既有 `pred_witnesses + non_fact_steps.details.binding`
- 当前仍未知的点：
  - 三类条件组合后，trace / audit 交付是否仍然足够清晰
  - 是否已经足够接近一个具名 Scenario A reference check
  - 是否暴露出需要 `T2` 才能表达的真实场景缺口
- 当前参考：
  - `Rainbird` 在本切片里只作为 evidence-chain / proof-entry 形状参考
  - 当前系统不追求复制其 certainty model，只比较“用户能否看到一条完整的条件链”

## 5. Proposed Shape

### 5.1 First-Round Composite Rule

第一轮 composite check 应只组合现有已经稳定的 contract：

- `ecss:obligation_timestamp`
- `ecss:window_start`
- `ecss:window_end`
- `ecss:collision_probability_ppm`
- `ecss:collision_probability_threshold_ppm`
- `ecss:disposal_success_probability_ppm`
- `ecss:disposal_success_threshold_ppm`

组合后的 where 仍只使用既有比较语法：

- `window_start <= event_ts`
- `event_ts <= window_end`
- `pc_ppm <= pc_threshold_ppm`
- `success_ppm >= success_threshold_ppm`

> **composite rule 中 temporal 与 uncertainty predicates 通过共享的 `assessment_ref` 关联。** 第一轮 composite scenario 假设同一个 `assessment_ref` 同时拥有时间窗口 facts 和概率阈值 facts。如果验证时发现 temporal 的 `anchor_ref` 和 uncertainty 的 `assessment_ref` 天然不同（例如时间窗口挂在 obligation 上，概率挂在 conjunction assessment 上），则需要在 rule 里加一条显式 join predicate 来桥接。

### 5.2 Delivery Check

这条 composite rule 的交付验证至少应检查：

- 是否成功返回结果行
- `pred_witnesses` 是否同时包含 temporal anchors 与 uncertainty anchors
- `details.binding` 是否同时带出时间标量和 `ppm` 标量
- 当前 explain/readback 形态是否已经足够让用户理解“为什么成立”
- export `package_kind="audit"` 后，`rule_trace_artifacts.jsonl` 是否能完整回读 composite trace
- 离线 consumer 拿到 package 后，是否能从 composite trace -> `pred_witnesses` -> assertion detail 形成完整下钻

### 5.3 Decision Gate For Next Step

本切片结束时必须明确回答：

1. 当前 `T1 + U1` 组合是否已经足够支撑 first-round Scenario A reference check？
2. 如果不够，缺口到底属于：
   - `T2 state propagation`
   - delivery shape
   - more scenario-specific data modeling
3. Rainbird 参考在这一轮里是否指出了明确的 proof-entry / evidence-chain 交付缺口？

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 只组合现有稳定 contract，不新增语义
  - trace / explain 继续沿用现有 carrier
  - Scenario A 仍以 rule/audit/readback 为主，不新开 live runtime surface
- 明确不做的内容：
  - 不在本切片中引入新的 adapter-specific 逻辑
  - 不在本切片中实现 state propagation 或 event accumulation
  - 不在本切片中产出正式产品化 UI
- 兼容性约束：
  - `ecss.temporal` / `ecss.uncertainty` 的现有 contract 保持不变
  - `RuleTraceArtifact` / `SupportArtifact` schema 保持不变

## 7. Acceptance

- [ ] 具名 composite rule 已形成，并覆盖 temporal + uncertainty conjunction
- [ ] trace / explain readback 已验证同时承载 temporal anchors 与 uncertainty anchors
- [ ] 已形成明确的 substrate 充分性判断，并至少从以下三个维度给出结论：
  - conjunction 表达：现有 where 比较链是否足够支撑三条件 conjunction
  - trace 交付：composite trace 是否能让 consumer 追溯每一个条件的 anchor + binding
  - audit 交付：离线 package 中的 trace 是否与 live readback 一致
- [ ] 已明确是否需要进入 `T2 state propagation`
- [ ] 若后续需要实现型工作，再从本蓝图拆出下一条子切片

## 8. Implementation Plan

1. 固定一个 first-round composite scenario 和最小数据样例
2. 组装 composite rule 并验证 trace / explain readback
3. 对照已归档蓝图与 Rainbird 参考，形成“当前够不够”的判断结论

## 9. Docs To Update

- 视结论而定；如果只形成结论 memo，可能不需要更新模块 docs
- 若落到新的 durable operator-facing 结论，则同步到：
  - `src/factpy_kernel/ecss/docs/01_overview.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增一条 composite integration regression，验证 `T1 temporal + U1 uncertainty` 可在单条 rule 中组合为 first-round Scenario A reference check
  - live readback 已确认：
    - `pred_witnesses` 同时覆盖 temporal anchors 与 uncertainty anchors
    - `non_fact_steps.details.binding` 同时带出时间值与 `ppm` 值
  - audit package parity 已确认：
    - `audit/rule_trace_artifacts.jsonl` 可完整回读 composite trace
    - static audit site 能为所有 witness assertions 生成 assertion detail 页面
  - 结论：当前 substrate 已足够支撑 first-round Scenario A reference check；现阶段没有证据表明必须立即进入 `T2 state propagation`
- 与 blueprint 不同的地方：
  - 未新增模块 docs 更新
- 为什么会有这些调整：
  - 本切片只验证既有 contract 的组合充分性，没有引入新的 public behavior 或 operator-facing contract，因此无需同步模块 docs
- 归档说明：
  - 本蓝图已完成 composite reference check 验证并归档；后续若继续，应基于这里的结论再决定是转向 delivery/demo 还是打开 `T2`
