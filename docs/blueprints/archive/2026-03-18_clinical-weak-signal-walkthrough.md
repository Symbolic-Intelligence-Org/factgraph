# Task Blueprint: Clinical Weak-Signal Walkthrough

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
  - [2026-03-18_clinical-deterioration-uncertainty-anchoring.md](../archive/2026-03-18_clinical-deterioration-uncertainty-anchoring.md)
  - [2026-03-18_scenario-a-uncertainty-and-confidence.md](../archive/2026-03-18_scenario-a-uncertainty-and-confidence.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_aml-aggregation-materialization-walkthrough.md](../archive/2026-03-18_aml-aggregation-materialization-walkthrough.md)
  - [2026-03-18_process-safety-shutdown-walkthrough.md](../archive/2026-03-18_process-safety-shutdown-walkthrough.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_clinical-weak-signal-walkthrough.audit.md](./2026-03-18_clinical-weak-signal-walkthrough.audit.md)

## 1. Problem

`clinical-deterioration-uncertainty-anchoring` 已经给出 adopted answer：

- weak-signal escalation 可以先用 placeholder 形状做 first-round walkthrough
- 但这条线第一次把 success criterion 推到了 explain **honesty / quality**
- 关键不再只是系统能否 mechanically 产出 trace，而是：
  - narrative / NL 是否能诚实表达 “多个 individually-weak indicators together matter”

因此下一步不应先开 `weak-signal-uncertainty-contract`，而是直接做一个具名 walkthrough，验证：

- 在 pre-materialized weak-signal facts + count/threshold placeholder 前提下，
- 一个 single composite escalation rule run
- 是否仍能被当前 explain delivery 栈诚实表达给 clinician/operator

如果这条 walkthrough 顺畅，就说明 uncertainty contract 还可以继续后置；如果不顺畅，而且失败方式是 technically correct but semantically misleading，那么 blocker 才真正收敛为 `weak-signal uncertainty semantics`。

## 2. Goals

- 用一个 synthetic clinical deterioration / sepsis-style walkthrough 验证当前 explain delivery substrate 的弱信号组合边界。
- walkthrough 必须严格建立在：
  - pre-materialized weak-signal facts
  - single composite rule run
  - flag-style result
  - count/threshold placeholder
- walkthrough 必须完整穿过：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须显式判断：现有 surface 是否已经足以诚实表达 “collective significance”，而不是只会复述 `count >= threshold`。

## 3. Non-goals

- 不实现真实临床规则、分诊建议或医疗建议。
- 不引入新的 uncertainty contract。
- 不引入 judgment/obligation contract。
- 不引入 T2 sequence/state semantics。
- 不新增专用 clinical renderer / DTO / page。
- 不修改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- `U1` 路线已经被证明是稳定的：
  - integer scalar + compare threshold
- `AML` 与 `process safety` 又证明：
  - placeholder 在 mechanical correctness 上仍可复用
- 但这些已成功场景都有一个共同点：
  - 每个 supporting signal 本身都已经具有独立可解释意义

当前这条 clinical weak-signal line 的新压力是：

- 单个 mild abnormality 本身不足以决定结论
- 但它们共同出现时，应推动 escalation

因此 walkthrough 真正要测的是：

- current narrative / NL 是否会把这种组合老老实实说成：
  - “多项轻度异常共同提示升级”
- 而不是误导性地说成：
  - “某个指标本身越界”
  - 或 “4 >= 4，所以触发”

authority note:

- 本切片只作为能力 walkthrough，不构成临床建议、分诊协议或医疗意见。

## 5. Proposed Shape

### 5.1 Scenario Shape

第一轮 walkthrough 使用一个 synthetic weak-signal escalation scenario，至少包含：

- `>=4` mild abnormality facts，来自不同指标类别
  - 例如：
    - mild fever
    - mildly elevated heart rate
    - mildly elevated respiratory rate
    - mildly low blood pressure
    - mild confusion / lactate / WBC abnormality
- `>=2` normal-range indicator facts
  - walkthrough 必须显式保留一部分“未异常”的指标，
    以确保场景表达的是 “4 out of 6 mild abnormalities together matter”，
    而不是 “所有相关指标都异常，因此自然触发”
- `0` single severe abnormality facts
  - walkthrough 必须避免被误读成“某一项已严重到足以单独触发”
- `>=1` materialized count fact
  - 例如 `clinical:abnormal_indicator_count = 4`
- `>=1` threshold fact
  - 例如 `clinical:deterioration_count_threshold = 4`

关键约束：

- 每个 weak-signal fact 必须单独可读，但又不应单独足以解释 escalation
- 正常范围指标 facts 也必须可读，以便 reader 能看出这是部分异常的组合显著性，而不是全局失控
- count/threshold placeholder 仍可作为 rule consumption layer
- walkthrough 必须防止退化成：
  - 单个 severe threshold alert
  - 或一个 opaque total score，而完全看不出组合来源

### 5.2 Rule / Result Shape

walkthrough 应以一条 single composite rule 为中心：

- single `rule_id`
- single `rule_run_id`
- single result row

结果保持最小 first-round 形状：

- `clinical:deterioration_review_required`
  - 或语义等价的 predicate result

关键约束：

- 仍然只是普通 predicate / rule result
- 不在本切片中偷渡新的 uncertainty or judgment carrier
- rule 至少组合：
  - multiple weak-signal facts
  - materialized count fact
  - count threshold compare

### 5.3 Delivery Path To Validate

walkthrough 必须完整验证当前已有的五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 uncertainty-specific 要求：

- trace 必须清楚显示：
  - multiple weak-signal facts were witnessed
  - count threshold compare was evaluated
- narrative / NL explain 必须尽量表达：
  - escalation 来源于多个 individually-weak signals 的组合
- 但文本不能假装系统已经拥有：
  - contribution weights
  - probability semantics
  - formal uncertainty algebra

### 5.4 Success Criteria

与前序 walkthrough 不同，这条切片的主判据不再只是 `mechanical correctness`，而是 explain
是否能诚实表达组合显著性。也就是说，单纯做到 “trace 正确存在、`count >= threshold` 可见”
并不算通过；输出必须让 reader 看懂 why-combination-matters，同时不伪装成系统已经具备更重的
uncertainty semantics。

这条 walkthrough 若要算成功，至少需要同时满足：

1. `weak-signal fan-out remains inspectable`
   - 多个 mild abnormality facts 能通过 witness/assertion/static page drill-down 查看
2. `combination significance remains honest`
   - narrative / NL 不只是复述 `count >= threshold`
   - 还必须让 reader 看懂这是“多个 individually-weak signals together matter”
3. `no fake uncertainty semantics`
   - narrative / NL explain 不会伪装成系统已经具备更重的 contribution/probability semantics

若任一条件不成立，失败方式应被单一化映射为：

- weak-signal uncertainty contract gap
- delivery wording gap
- 或其他单一 follow-on gap

### 5.5 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 runtime feature。

scope freeze:

- 以 tests 为主
- 如有必要，只补最小 synthetic schema helper
- 不改 runtime/audit/service contract
- walkthrough 失败时只在 outcome 中命名 follow-on blueprint，不在本切片扩 scope

## 6. Boundaries And Invariants

- 必须保持为 placeholder walkthrough，不得滑入新的 uncertainty contract
- 不得先行引入 judgment contract
- 不得引入时间序列/T2 语义
- 若 walkthrough 成功，不得顺手把 uncertainty contract 拉进 scope

## 7. Acceptance

- [x] synthetic clinical weak-signal walkthrough 已形成 single composite rule run
- [x] walkthrough 明确使用 multiple weak-signal facts + count/threshold placeholder
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 collective significance；若不足，gap 已被单一化分类

## 8. Plan

1. 定义 synthetic weak-signal facts 与 single composite rule，确保它不是单一 severe-threshold alert 的变体。
2. 补 runtime + audit + static walkthrough regression，验证五层 explain delivery 与 combinatorial-significance honesty。
3. 在 outcome 中记录：uncertainty contract 是否仍可继续后置。

## 9. Docs To Update

- 无默认新增；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 synthetic clinical weak-signal walkthrough regression。
  - 场景显式包含 `>=4` mild abnormality facts、`>=2` normal-range indicator facts、`clinical:abnormal_indicator_count` 与 `clinical:deterioration_count_threshold`，并以 single composite rule run 验证五层 explain delivery。
- 现有 surface 是否足够：
  - 足够。当前 raw / summary / narrative / NL / audit-static proof-entry 能诚实表达 “多个轻度异常共同推动 escalation”，同时不伪装成系统已具备 contribution weights、probability semantics 或正式 uncertainty algebra。
  - rule trace 只 witness weak-signal + count/threshold placeholder；normal-range indicators 保持为可审计但非 witnessed 的背景 assertions，这与本切片的 placeholder honesty 边界一致。
- 若不足，单一 follow-on gap：
  - 无。本次 walkthrough 未逼出 immediate `weak-signal-uncertainty-contract` blocker。
- 归档说明：
  - 该切片证明 current substrate 对 first-round weak-signal escalation 仍然站得住，因此 uncertainty contract 继续保持 deferred 状态。
