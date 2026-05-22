# Task Blueprint: AML Aggregation Materialization Walkthrough

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
  - [2026-03-18_aml-case-review-walkthrough.md](../archive/2026-03-18_aml-case-review-walkthrough.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_aml-event-aggregation-semantics.md](../archive/2026-03-18_aml-event-aggregation-semantics.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_aml-aggregation-materialization-walkthrough.audit.md](./2026-03-18_aml-aggregation-materialization-walkthrough.audit.md)

## 1. Problem

`aml-event-aggregation-semantics` 已给出 adopted conclusion：

- first-round AML aggregation 不应直接进入 `T2`
- 当前应先验证 `Route A`
  - pre-materialized aggregation helper / contract

这意味着下一步不该去实现 in-rule sequence semantics，而是验证一个更窄但更真实的问题：

- 当 raw transactions / timing anchors / risk anchors 作为 facts 存在，
- 同时 aggregation helper 也把自己的输出 summary facts 写入 ledger，
- 当前 explain delivery substrate 是否能清楚表达：
  - rule 实际消费了哪些 materialized facts
  - 与这些 materialized facts 同域的 raw inputs 也可被单独 drill-down
  - 但 narrative / NL 不会伪装成“rule 已经亲自完成了事件聚合”

如果这条 walkthrough 顺畅，就说明 first-round AML aggregation 可以继续停留在 materialization helper 路线；如果不顺畅，才需要更具体地判断缺口是在：

- helper traceability boundary
- delivery wording / presentation honesty
- 或真正的 `T2` capability

## 2. Goals

- 用一个 synthetic AML aggregation-materialization walkthrough 验证 `Route A` 是否站得住。
- walkthrough 必须同时包含：
  - raw event facts
  - materialized aggregation facts
  - single downstream trigger rule run
- walkthrough 必须验证现有五层 explain delivery：
  - runtime raw
  - runtime summary
  - runtime narrative
  - runtime NL
  - audit/static proof-entry
- walkthrough 必须明确回答：当前 substrate 是否能把“helper computed this”与“rule consumed this”边界表达清楚。

## 3. Non-goals

- 不实现真正的 aggregation helper runtime。
- 不实现 helper-internal trace contract。
- 不进入 `T2 sequence/state semantics`。
- 不新增 judgment contract。
- 不新增 uncertainty semantics。
- 不修改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- `AML trigger walkthrough` 已证明：当 `windowed_structuring_signal` 与 threshold facts 已存在时，当前 explain delivery 足以支撑 first-round trigger。
- `aml-event-aggregation-semantics` 已进一步收敛：
  - materialized aggregation facts 的 explain honesty 边界，与当前 `T1 temporal` anchors 一致
  - 下一步不该直接开 `T2`
- 当前仍未被 walkthrough 验证的是：
  - 当 raw inputs 和 materialized outputs 同时存在时，consumer 是否还能清楚分辨：
    - 哪些 facts 是 raw inputs
    - 哪些 facts 是 helper outputs
    - rule 到底消费了哪一层

authority note:

- 该 walkthrough 只验证 explain/delivery honesty，不构成 AML 规则引擎或监管解释承诺。
- “materialization helper” 在本切片中只作为 synthetic upstream producer 存在，不代表 durable runtime API 已冻结。

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 应使用一个单账户 synthetic scenario，并同时写入两层 facts：

- raw layer
  - `>=3` transaction facts
  - explicit transaction timestamps
  - beneficiary / jurisdiction risk anchor
- materialized layer
  - 一个窗口聚合 summary fact，例如：
    - `aml:windowed_structuring_signal`
  - 如有必要，可带：
    - window boundaries
    - near-threshold transaction count
    - linked risk anchor summary

关键约束：

- raw facts 必须足够让 reader 理解 helper 理应“看到了什么”
- downstream rule 仍只消费 materialized facts，而不是直接重新聚合 raw events
- walkthrough 必须避免让 raw layer 变成无关背景数据；raw facts 应与 materialized outputs 在语义上明显相关

### 5.2 Rule / Result Shape

结果继续保持最小 first-round 形状：

- single composite trigger rule
- single `rule_run_id`
- flag-style placeholder result
  - 例如 `aml:review_required`

这条 rule 应明确只消费：

- materialized aggregation fact(s)
- 必要的 risk/supporting signal facts
- 如仍需 threshold compare，可继续复用现有 `U1` placeholder path

它不应直接扫描原始 transactions 做计数/窗口聚合，否则就会偷渡回 `T2`

### 5.3 Delivery Path To Validate

walkthrough 必须完整验证当前已有的五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 materialization-specific 要求：

- trace 必须清楚显示 rule 消费的是 materialized aggregation fact
- raw transaction / risk facts 必须仍然可通过 assertion/detail 页面单独查看
- narrative / NL explain 必须避免把 helper 的计算过程表述成 rule 自己完成的推理

### 5.4 Success Criteria

这条 walkthrough 若要算成功，至少要同时满足：

1. `materialized-rule boundary remains readable`
   - reader 能看懂 rule 消费的是 helper outputs，不是 raw transaction scan
2. `raw-input context remains inspectable`
   - raw transactions / risk anchors 仍可被单独查看，帮助 consumer理解 helper output 的来源背景
3. `narrative honesty remains intact`
   - narrative / NL explain 不会把 materialized output 错写成 in-rule event aggregation

若任一条件失败，失败方式应被单一化映射为：

- helper traceability gap
- delivery wording gap
- 或 `T2` capability gap

### 5.5 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新 runtime feature。

当前 draft 倾向：

- 以 tests 为主
- 如有必要，补最小 synthetic schema helper
- 不新增 helper API
- 不改 runtime/audit/service contract
- 若 walkthrough 暴露问题，只在 outcome 中单一化命名 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 `Route A` walkthrough，不得滑回 `T2`
- helper 的“如何计算”不在本切片 contract 内
- 问题必须保持为 aggregation/materialization honesty，不与 judgment/uncertainty 混切
- 若 walkthrough 成功，不得借机扩 scope 去补 helper API

## 7. Acceptance

- [x] walkthrough 同时包含 raw facts 与 materialized aggregation facts
- [x] downstream trigger rule 明确只消费 materialized layer
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] 已明确判断 `Route A` 是否在 explain honesty 上站得住；若不足，gap 已被单一化分类

## 8. Plan

1. 定义 synthetic raw/materialized 双层 fact shape，避免退化成仅有 materialized facts 的 trigger replay。
2. 补 single-rule-run walkthrough regression，验证五层 explain delivery 与 wording honesty。
3. 在 outcome 中记录 `Route A` 是否成立；若不成立，给出单一 follow-on gap blueprint。

## 9. Docs To Update

- 无默认新增；若 walkthrough 实际迫使 contract 变化，再更新对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 synthetic AML aggregation-materialization walkthrough regression。
  - 该 walkthrough 同时写入了：
    - raw layer：
      - `>=3` transaction facts
      - explicit transaction timestamp facts
      - beneficiary risk anchor
    - materialized layer：
      - `aml:windowed_structuring_signal`
      - `aml:high_risk_outflow_signal`
      - trigger evaluation/threshold supporting facts
  - downstream rule run 明确只消费 materialized layer 与 supporting signal facts，不直接扫描 raw transactions。
  - walkthrough 完整验证了：
    - runtime raw explain
    - runtime summary
    - runtime narrative
    - runtime NL explain
    - audit export + static proof-entry page
  - 回归同时验证了两件事：
    - rule trace / summary / narrative 只声明 rule 实际消费的 materialized facts
    - raw transaction / timestamp / risk assertions 仍可通过 audit assertion detail / static assertion pages 单独 inspect
- Route A 是否站得住：
  - 结论是站得住。当前 substrate 已足够清楚地区分：
    - helper output facts
    - downstream rule consumption
    - raw input context
  - narrative / NL explain 也没有把 materialized aggregation 误表述成 in-rule event aggregation。
- 若失败，单一 follow-on gap：
  - 不适用；本次 walkthrough 未暴露 blocker。
- 归档说明：
  - 本切片完成后归档到 `docs/blueprints/archive/`；由于未改变 operator-facing contract，本轮未更新模块 docs。
