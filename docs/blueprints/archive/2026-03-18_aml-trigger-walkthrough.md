# Task Blueprint: AML Trigger Walkthrough

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
  - [2026-03-18_aml-suspicious-account-anchoring.md](../archive/2026-03-18_aml-suspicious-account-anchoring.md)
  - [2026-03-18_aml-case-review-walkthrough.md](../archive/2026-03-18_aml-case-review-walkthrough.md)
  - [2026-03-18_aml-obligation-trigger-semantics.md](../archive/2026-03-18_aml-obligation-trigger-semantics.md)
  - [2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
  - [2026-03-18_scenario-a-uncertainty-and-confidence.md](../archive/2026-03-18_scenario-a-uncertainty-and-confidence.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_aml-trigger-walkthrough.audit.md](./2026-03-18_aml-trigger-walkthrough.audit.md)

## 1. Problem

`AML-Review` 已证明当前 explain delivery 栈可以跨域复用到 investigator-facing case review。`AML obligation trigger semantics` 也已经给出 adopted conclusion：

- temporal: first-round 允许 `pre-aggregated facts`
- output: 使用 `flag-style placeholder`
- uncertainty: 使用 `boolean/threshold placeholder`

这意味着下一步不应先开 aggregation / judgment / uncertainty gap blueprint，而是直接验证：

- 在这些明确受限的条件下，
- 一个 AML trigger-style scenario 是否也能复用现有 runtime/audit explain delivery substrate。

当前缺的不是新的 contract，而是一条具体的 trigger walkthrough：

- synthetic AML trigger facts
- pre-aggregated window/risk/signal facts
- single composite rule run
- flag-style trigger result
- runtime + audit + static proof-entry readback

如果这条 walkthrough 顺畅，就说明：

- 现有 `T1 + U1 + explain delivery` 组合确实足以支撑 first-round AML trigger

如果不顺畅，暴露出来的缺口就会更精确地指向：

- aggregation gap
- judgment contract gap
- weak-signal uncertainty gap

而不是再回到抽象讨论。

## 2. Goals

- 用一个 synthetic AML trigger walkthrough 验证 adopted conclusion `outcome 1` 是否成立。
- walkthrough 必须显式遵守三条前提：
  - `pre-aggregated facts`
  - `flag-style placeholder`
  - `boolean/threshold placeholder`
- walkthrough 必须完整穿过既有 explain delivery 栈：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：这些 placeholder 是否已经足够支撑 first-round trigger explainability。

## 3. Non-goals

- 不实现 in-rule event aggregation / sequence semantics。
- 不新增 `judgment` / `obligation` result kind。
- 不实现 true weak-signal certainty/probability combination。
- 不新增 case-level aggregation 或 case-management surface。
- 不修改现有 raw / summary / narrative / NL / static delivery contract。

## 4. Current Context

- `AML case-review walkthrough` 已证明单个 `rule_run_id` 对 case review 足够。
- `AML obligation trigger semantics` 已给出 adopted answer：
  - `T1` only if `pre-aggregated facts`
  - `flag-style placeholder` is enough
  - `U1`-style placeholder is enough
- 当前还没被验证的是：
  - pre-aggregated temporal trigger facts 进入 rule trace 后是否仍然可读
  - trigger-style predicate result 是否足以承载“此刻触发 review/suspicious flag”的解释
  - boolean/threshold placeholder 是否在 explain/narrative/NL 输出里足够清楚，不会误导成“已经具备正式 certainty semantics”

authority note:

- walkthrough 仍然只是 design scenario，不是 AML 监管逻辑实现。
- pre-aggregated facts 的存在是本切片的前提，不是现实系统数据流的终局设计承诺。

## 5. Proposed Shape

### 5.1 Scenario Shape

第一轮 walkthrough 使用 synthetic pre-aggregated AML trigger facts，而不是原始事件流聚合。

至少应包含：

- `windowed_structuring_signal`
  - 表示某账户在具名窗口内已经满足“多笔接近阈值交易”的上游聚合判断
- `high_risk_outflow_signal`
  - 表示资金已流向高风险受益方 / 司法辖区
- 至少两类 supporting signals
  - 可用 boolean predicates，或 integer threshold predicates
  - 例如：
    - `shared_device_signal`
    - `shared_beneficiary_signal`
    - `bo_mismatch_signal`

这条 walkthrough 还必须满足一组区别于 `AML case-review walkthrough` 的最小事实多样性约束：

- `>=1` pre-aggregated temporal fact with explicit window boundaries
  - 例如 `window_start_ns` / `window_end_ns` 这类 `int` epoch nanoseconds
  - 目的不是再做 flat boolean conjunction，而是强制 explain trace 真正经过 `T1` temporal anchor + compare path
- `>=1` integer threshold fact using `U1`-style scalar comparison
  - 不能只用 boolean present/absent
  - 目的是真正压到 `non_fact_steps.details.binding` 中的 threshold comparison binding，并验证 narrative / NL 不会把 placeholder 误表述成 formal certainty claim
- 其余 supporting signals 可以保持 boolean
  - 但 temporal path 和 threshold path 至少各有一个 non-boolean fact，否则这条 walkthrough 就会退化成 case-review 已经验证过的 boolean-only conjunction

若使用 threshold placeholder，数值语义应继续沿 `U1`：

- fact-backed integer scalar
- existing compare atoms (`>=` / `<=`)

### 5.2 Result Shape

结果必须保持为 `flag-style placeholder`，不引入新的 judgment object。

第一轮建议形状：

- `aml:suspicious_account_triggered`
  - 或
- `aml:review_required`

关键约束：

- 它仍然只是普通 predicate / rule result
- explain 仍走既有 `rule_run` path
- 不能在本切片里偷渡新的 `judgment` carrier

### 5.3 Delivery Path To Validate

walkthrough 必须完整验证当前已有的五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 trigger-specific 要求：

- trace 中要能看出 temporal/threshold anchors 是 fact-backed，而不是隐藏逻辑
- narrative / NL explain 中要能读出：
  - windowed trigger 已满足
  - high-risk outflow 已满足
  - supporting signals 已满足
- 但文本不能假装系统已经拥有 formal obligation semantics 或 probabilistic combination semantics

### 5.4 Success Criteria For The Walkthrough

这条 walkthrough 若要算成功，至少需要同时满足：

1. `pre-aggregated trigger facts remain explainable`
   - temporal/threshold anchors 进入 `pred_witnesses` 与 explain drill-down，未退化成 opaque hidden state
2. `flag-style placeholder remains readable`
   - investigator 能理解这是“triggered/review-required”风格的 first-round placeholder，而不是完整 judgment ontology
3. `placeholder uncertainty remains honest`
   - 现有 narrative / NL explain 不会把 boolean/threshold placeholder 误表述成已经做了真正的 weak-signal certainty combination

若任一条件不成立，这条 walkthrough 的失败方式就应直接对应到一个单一 gap：

- aggregation
- judgment contract
- weak-signal uncertainty

### 5.5 Expected Implementation Boundary

这条切片仍应是一个 walkthrough / regression slice，而不是新的 runtime feature slice。

当前 draft 倾向：

- 以 tests 为主
- 如有必要，只补最小 synthetic schema helper / fixture
- 不修改 runtime/audit contracts
- 不新增新的 docs truth，除非 walkthrough 实际迫使 contract 发生变化

## 6. Boundaries And Invariants

- 必须保持的边界：
  - pre-aggregated facts 是前提，不在本切片内实现 aggregation
  - flag-style placeholder 是前提，不在本切片内实现 judgment contract
  - boolean/threshold placeholder 是前提，不在本切片内实现 U2 semantics
- 明确不做的内容：
  - 不实现 36-hour sequence reasoning
  - 不实现 obligation object model
  - 不实现 weak-signal contribution / salience breakdown
- 兼容性约束：
  - 若 walkthrough 暴露真实 gap，必须在 outcome 中指向单一 follow-on blueprint，而不是在本切片里扩 scope

## 7. Acceptance

- [x] synthetic AML trigger walkthrough 已形成 single composite rule run
- [x] walkthrough 明确使用 `pre-aggregated facts + flag-style placeholder + boolean/threshold placeholder`
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 placeholder 组合是否足够；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 定义 synthetic trigger facts 与 single composite rule，确保它们严格符合 adopted placeholder 边界。
2. 补 runtime + audit + static 的 walkthrough regression，验证五层 explain delivery 链。
3. 在 outcome 中记录：当前 placeholder 组合是否站得住；若不行，下一条单一 gap blueprint 是什么。

## 9. Docs To Update

- 无默认新增；若 walkthrough 实际改变了 operator-facing truth，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 synthetic AML trigger walkthrough regression。
  - 该 walkthrough 保持为 single composite rule run，并显式使用：
    - `pre-aggregated temporal facts`
    - `flag-style placeholder`
    - `boolean/threshold placeholder`
  - synthetic facts 同时压到了两条非 boolean 路径：
    - `aml:windowed_structuring_signal` + `aml:trigger_evaluation_time` + `<=` 比较，验证 `T1` temporal anchor/readback
    - `aml:trigger_score_ppm` + `aml:trigger_score_threshold_ppm` + `>=` 比较，验证 `U1` threshold anchor/readback
  - walkthrough 完整验证了：
    - runtime raw explain
    - runtime summary
    - runtime narrative
    - runtime NL explain
    - audit export + static proof-entry page
  - 结论是：在 pre-aggregated temporal facts、flag-style result、boolean/threshold placeholder 的受限前提下，当前 substrate 足以支撑 first-round AML trigger walkthrough；不需要先开 aggregation / judgment / uncertainty gap blueprint。
- 与 blueprint 不同的地方：
  - 无实质偏离；实现保持为 regression/test slice，没有新增 runtime 或 audit contract，也没有新增页面类型。
- 为什么会有这些调整：
  - 不适用。
- 归档说明：
  - 本切片完成后归档到 `docs/blueprints/archive/`；由于没有改变 operator-facing truth，本轮未更新模块 docs。
