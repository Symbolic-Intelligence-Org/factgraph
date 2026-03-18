# Task Blueprint: AML Transaction Feed Materialization Walkthrough

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
  - [2026-03-18_aml-transaction-feed-normalization-anchoring.md](../archive/2026-03-18_aml-transaction-feed-normalization-anchoring.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_aml-aggregation-materialization-walkthrough.md](../archive/2026-03-18_aml-aggregation-materialization-walkthrough.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
- Audit Log:
  - [2026-03-18_aml-transaction-feed-materialization-walkthrough.audit.md](./2026-03-18_aml-transaction-feed-materialization-walkthrough.audit.md)

## 1. Problem

`aml-transaction-feed-normalization-anchoring` 已经给出 adopted conclusion：

- first-round upstream vertical slice 应选 `structured transaction feed normalization`
- source-record identity 还不需要 first-class
- explicit normalized-to-helper lineage contract 还不需要先引入
- 第一轮实现应保持为 walkthrough/regression，而不是 durable ingest API

这意味着下一步不应先做 ingestion framework，而应先做一个具名 walkthrough，验证：

- raw structured transaction records
- synthetic normalize step
- materialized helper outputs
- downstream trigger rule run

是否能够在不改现有 runtime/audit contracts 的前提下，形成一条诚实的 upstream-to-explain vertical slice。

## 2. Goals

- 用一个 synthetic AML transaction feed walkthrough 验证 first-round upstream vertical slice 是否站得住。
- walkthrough 必须显式包含：
  - raw structured source records
  - synthetic normalize step
  - materialized helper outputs
  - single downstream trigger rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：当前 substrate 是否足以诚实表达
  - source record 被 normalize 成了哪些 facts
  - helper 输出了哪些 materialized facts
  - rule 实际消费了哪一层

## 3. Non-goals

- 不实现 durable ingest API。
- 不实现 first-class source-record identity。
- 不引入新的 lineage contract。
- 不实现 document / narrative extraction。
- 不引入新的 uncertainty / judgment / T2 semantics。
- 不修改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- `AML trigger walkthrough` 已经证明：
  - 当 trigger-supporting facts 已存在时，当前 explain delivery 栈是稳定的。
- `AML aggregation materialization walkthrough` 已经证明：
  - helper outputs 与 downstream rule consumption 的 honesty boundary 是可接受的。
- 当前还没有被 directly walkthrough 验证的是：
  - raw source record 经 normalize 后进入 ledger，再被 helper 消费并 materialize，最后进入 rule_run explain 的整条链

因此这条切片的真正新问题不是 rule semantics，而是：

- source-to-fact 边界是否足够清晰
- synthetic normalize output shape 是否稳定到足以支撑 downstream walkthrough
- current explain/audit surfaces 是否会误导 reader 以为 rule 直接看到了 raw source records

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用一个单账户 synthetic transaction feed，至少包含：

- `>=3` raw transaction records
  - each record 至少包含：
    - transaction id
    - timestamp
    - amount
    - beneficiary / counterparty
    - device or channel marker
- `>=1` linked risk anchor in the raw feed context
  - 例如 beneficiary jurisdiction 或 high-risk outflow marker
- `>=1` materialized aggregation/helper output
  - 例如 `aml:windowed_structuring_signal`
- `>=1` threshold-bearing helper output
  - 例如 `aml:trigger_score_ppm` + `aml:trigger_score_threshold_ppm`

关键约束：

- raw source records 不能只是注释性背景；它们必须被 normalize step 实际消费
- normalize step 不能直接手写最终 helper outputs；必须先产出 normalized ledger facts
- downstream rule run 不应直接扫描 raw source record；它只消费 normalized/materialized layer

### 5.2 Synthetic Normalize Step

第一轮 walkthrough 必须显式包含一个 test-scope synthetic normalize step：

- input:
  - raw structured transaction records（dict / JSON-like objects）
- output:
  - normalized ledger facts
  - 例如：
    - `aml:transaction_event`
    - `aml:transaction_timestamp`
    - `aml:beneficiary_risk`
    - `aml:shared_device_signal`

关键约束：

- normalize step 是 walkthrough 内的 plain helper function，不是 durable runtime API
- walkthrough 必须让 normalize output shape 可见、可检验
- 若 walkthrough 成功，结论只能是“当前 output shape 足够 first-round reuse”，不能反向声称 normalize contract 已冻结

### 5.3 Materialization And Downstream Rule

normalize 之后，walkthrough 再通过 test-scope materialization step 生成 helper outputs，例如：

- `aml:windowed_structuring_signal`
- `aml:trigger_evaluation_time`
- `aml:trigger_score_ppm`
- `aml:trigger_score_threshold_ppm`

然后以一条 single composite trigger rule 为中心：

- single `rule_id`
- single `rule_run_id`
- single result row

结果保持最小 first-round 形状：

- `aml:review_required`
  - 或语义等价的 predicate result

关键约束：

- downstream rule 只消费 materialized layer 与必要的 normalized supporting signals
- walkthrough 不得偷偷让 rule 重新聚合 raw transactions
- current explain surfaces 必须能看清：
  - rule witness 了什么
  - helper outputs 是什么
  - raw source record 并不是 rule witness surface 的一部分

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 upstream-specific 要求：

- trace 必须清楚显示：
  - materialized helper outputs were witnessed by the rule
  - threshold compares were evaluated
- audit / assertion pages 必须仍能单独 inspect normalized facts
- walkthrough 不应要求当前 system 直接展示 raw source-record object 作为 first-class runtime/audit surface

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `normalize-to-fact boundary remains inspectable`
   - synthetic normalize step 的输入输出在 test 中明确可核对
   - walkthrough 的 test 断言必须至少包含一条 field-level round-trip check：
     - 从 raw source record 的某个关键 field value
     - 到对应 normalized fact 的 `rest_term` value
     - 以确认 normalize step 没有把 source field 变成 opaque black box
   - normalized facts 在 assertion/audit/static page 中可单独 inspect
2. `helper-vs-rule boundary remains honest`
   - trace / narrative / NL 不会误说 rule 自己完成了 source normalization 或 aggregation
3. `current explain surface remains sufficient without new upstream contracts`
   - walkthrough 不需要 first-class source identity、显式 lineage contract 或 durable ingest API 就能完成 first-round vertical validation

若任一条件不成立，失败方式应被单一化映射为：

- source identity gap
- normalization contract gap
- explicit lineage gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 ingestion feature。

scope freeze:

- 以 tests 为主
- synthetic normalize step 与 materialization step 都保留在 test scope
- 不改 runtime/audit/service contract
- 若 walkthrough 成功，不顺手冻结新的 durable upstream API
- 若 walkthrough 失败，只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 structured-source walkthrough，不得混入 document extraction。
- 必须显式包含 normalize step，而不是直接从手写 facts 起步。
- 不得把 raw source record 伪装成当前系统已经拥有的 first-class explain surface。
- 不得把本切片扩成 ingest framework 或 source-storage API 设计。

## 7. Acceptance

- [x] synthetic AML transaction feed walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 raw source records + synthetic normalize step + materialized helper outputs
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 source->normalize->materialize->rule 的边界；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 raw structured transaction feed fixture，并用 synthetic normalize step 产出 normalized facts。
2. 用 test-scope materialization step 生成 helper outputs，再跑 downstream trigger rule run。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 upstream boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 synthetic AML transaction feed materialization walkthrough regression。
  - walkthrough 显式包含：
    - raw structured transaction feed records
    - test-scope synthetic normalize step
    - test-scope materialization step
    - single downstream trigger rule run
  - regression 复用了现有 AML predicates、现有 runtime/audit explain surfaces 与 static proof-entry。
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 `source -> normalize -> materialize -> rule` 的边界：
    - raw source record 由 test-scope helper normalize 成 ledger facts
    - helper outputs 进入 witness surface
    - downstream rule 只消费 materialized layer 与必要 supporting signals
    - narrative / NL 不会误说 rule 自己完成了 source normalization 或 raw feed ingestion
  - first-round 不需要 first-class source-record identity、显式 lineage contract 或 durable ingest API。
- 若不足，单一 follow-on gap：
  - 无。本次 walkthrough 未逼出 immediate source identity / normalization contract / explicit lineage blocker。
- 归档说明：
  - 该切片证明 first-round upstream vertical slice 可以继续停留在 walkthrough/regression 级别，source/normalize boundary 仍可在现有 contract 下诚实表达。
