# Task Blueprint: Process Safety Shutdown Walkthrough

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_process-safety-shutdown-anchoring.md](../archive/2026-03-18_process-safety-shutdown-anchoring.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_aml-aggregation-materialization-walkthrough.md](../archive/2026-03-18_aml-aggregation-materialization-walkthrough.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_process-safety-shutdown-walkthrough.audit.md](./2026-03-18_process-safety-shutdown-walkthrough.audit.md)

## 1. Problem

`process-safety-shutdown-anchoring` 已经给出 adopted answer：

- `shutdown_required` 在 first-round 仍可先作为普通 predicate/result surface 承载
- inputs 必须保持 pre-materialized facts
- judgment / obligation contract 仍然不是 immediate blocker

因此下一步不该先开 `judgment-obligation-contract`，而是直接做一个具名 walkthrough，验证：

- 在 pre-materialized sensor/alarm/interlock facts 前提下，
- 一个 single composite `shutdown_required` rule run
- 是否仍然能被当前 explain delivery 栈清楚表达给 operator

如果这条 walkthrough 顺畅，说明 judgment contract 还可以继续后置；如果不顺畅，才说明真正的问题已经不再是抽象讨论，而是：

- operator wording gap
- 或 judgment/obligation contract gap

## 2. Goals

- 用一个 synthetic process-safety shutdown scenario 验证现有 explain delivery substrate 的跨域复用能力。
- walkthrough 必须严格建立在：
  - pre-materialized facts
  - single composite rule run
  - `shutdown_required`-style predicate result
- walkthrough 必须完整穿过：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须显式判断：现有 surface 是否已足以让 operator 区分 “required action” 与普通 review/flag 输出。

## 3. Non-goals

- 不实现真实工艺安全或 interlock 逻辑。
- 不引入新的 judgment / obligation contract。
- 不引入 in-rule state propagation / sequence semantics。
- 不新增专用 process-safety renderer / DTO / page。
- 不修改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- `AML` 线已经证明：
  - flag-style result
  - temporal/threshold placeholders
  - materialized aggregation
  都能在现有 explain stack 上站得住
- process safety 第一次真正不同的压力在于：
  - operator 看到的结果更接近 “must act now”
  - 而不是 “please review” / “flagged”

当前最需要验证的新点是：

- narrative / NL explain 在不改 contract 的前提下，是否仍能把 `shutdown_required` 传达为足够明确的 operator-facing output

authority note:

- 本切片只作为能力 walkthrough，不构成真实安全系统设计或控制建议。

## 5. Proposed Shape

### 5.1 Scenario Shape

第一轮 walkthrough 使用一个 synthetic process safety scenario，至少包含：

- pre-materialized sensor state facts
  - 例如温度、压力、流量等阈值已越界的状态
- pre-materialized alarm / interlock facts
  - 例如高高报警、联锁就绪、旁路未启用
- 至少一个 explicit inhibit/override fact
  - 例如 `shutdown_inhibit_absent` 或等价正向事实

关键约束：

- facts 应同时覆盖：
  - threshold/state 类输入
  - interlock / permissive 类输入
  - inhibit / override 类输入
- 但全部都必须以 facts 形式预先存在，rule 不做轮询或状态机推进

为了让这条 walkthrough 真正压到 “must-act vs review” 的可读性差异，而不是退化成普通 boolean conjunction，还必须满足以下最小事实多样性约束：

- `>=2` independent sensor threshold facts
  - 例如高温 + 高压
  - 目的是真正形成多条件 safety argument，而不是单阈值告警
- `>=1` interlock/permissive fact that is explicitly satisfied
  - 例如 `interlock_armed = true`
  - 目的是真正让 trace 展示“允许 shutdown 的 gate 已被满足”，而不只是 alarm firing
- `>=1` inhibit/override fact that is explicitly cleared or absent-via-positive-fact
  - 例如 `manual_override_active = false`，或等价的正向 “override cleared” facts
  - 目的是真正让 narrative/NL 需要表达“没有 override 在阻止动作”

这三个层次同时存在时，walkthrough 才真正具备：

- conditions met
- gate passed
- no override blocking

也只有这样，`shutdown_required` 的 explain 输出才有机会被 operator 读成 “must act now”，而不只是另一种 review-style flag。

### 5.2 Rule / Result Shape

walkthrough 应以一条 single composite rule 为中心：

- single `rule_id`
- single `rule_run_id`
- single result row

结果保持最小 first-round 形状：

- `process:shutdown_required`
  - 或语义等价的 predicate result

关键约束：

- 仍然只是普通 predicate / rule result
- 不在本切片中偷渡新的 `judgment` carrier
- rule 至少组合：
  - threshold/state facts
  - interlock/permissive fact
  - inhibit/override fact

### 5.3 Delivery Path To Validate

walkthrough 必须完整验证当前已有的五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 process-safety-specific 要求：

- narrative / NL explain 必须让 reader 看出这不是普通 review flag，而是 required action 风格结果
- 但文本不能伪装出当前并不存在的 lifecycle/judgment ontology
- proof-entry 必须仍能 drill-down 到 supporting sensor/alarm/interlock assertions

### 5.4 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `must-act result remains readable`
   - operator 能从现有 explain surface 读出 “shutdown required” 的语气和含义，而不是把它误读为普通 review flag
2. `supporting conditions remain inspectable`
   - supporting sensor/alarm/interlock facts 仍能通过 witness/assertion/static page drill-down 查看
3. `no fake judgment ontology`
   - narrative / NL explain 不会假装系统已经拥有更重的 obligation lifecycle contract

若任一条件不成立，失败方式应被单一化映射为：

- delivery wording gap
- judgment / obligation contract gap
- 或其他单一 follow-on gap

### 5.5 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 runtime feature。

当前 draft 倾向：

- 以 tests 为主
- 如有必要，只补最小 synthetic schema helper
- 不改 runtime/audit/service contract
- walkthrough 失败时只在 outcome 中命名 follow-on blueprint，不在本切片扩 scope

## 6. Boundaries And Invariants

- 必须保持为 pre-materialized facts walkthrough，不得滑入 `T2`
- 不得先行引入 judgment contract
- 问题必须保持在 operator readability / delivery honesty，不与 uncertainty 混切
- 若 walkthrough 成功，不得顺手把 judgment contract 拉进 scope

## 7. Acceptance

- [x] synthetic process-safety walkthrough 已形成 single composite rule run
- [x] walkthrough 明确使用 pre-materialized sensor/alarm/interlock facts
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够承载 `shutdown_required`；若不足，gap 已被单一化分类

## 8. Plan

1. 定义 synthetic process-safety facts 与 single composite rule，确保只使用 pre-materialized inputs。
2. 补 runtime + audit + static walkthrough regression，验证五层 explain delivery。
3. 在 outcome 中记录：judgment contract 是否仍可继续后置。

## 9. Docs To Update

- 无默认新增；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 synthetic process-safety shutdown walkthrough regression。
  - 该 walkthrough 维持为：
    - single composite rule run
    - pre-materialized sensor/alarm/interlock inputs
    - ordinary predicate/result surface
  - synthetic facts 形成了三层 safety argument：
    - `>=2` independent threshold facts
    - `>=1` satisfied interlock/permissive fact
    - `>=1` cleared override fact
  - walkthrough 完整验证了：
    - runtime raw explain
    - runtime summary
    - runtime narrative
    - runtime NL explain
    - audit export + static proof-entry
- 现有 surface 是否足够：
  - 结论是足够。当前 explain delivery surface 已经能够让 operator 把这条结果读成 `shutdown_required` 风格的 must-act output，而不是简单 review flag：
    - rule id / NL headline 保持 required-action 语气
    - witness groups 清楚展示了 threshold、interlock、override-cleared 三层条件
    - proof-entry 仍可下钻到 supporting assertions
  - 同时 narrative / NL 并未假装系统已经拥有更重的 judgment lifecycle ontology。
- 若不足，单一 follow-on gap：
  - 不适用；本次 walkthrough 未暴露 blocker。
- 归档说明：
  - 本切片完成后归档到 `docs/blueprints/archive/`；由于未改变 operator-facing contract，本轮未更新模块 docs。
