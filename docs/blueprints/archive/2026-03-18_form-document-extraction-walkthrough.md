# Task Blueprint: Form Document Extraction Walkthrough

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
  - [2026-03-18_document-evidence-extraction-anchoring.md](../archive/2026-03-18_document-evidence-extraction-anchoring.md)
  - [2026-03-18_aml-transaction-feed-materialization-walkthrough.md](../archive/2026-03-18_aml-transaction-feed-materialization-walkthrough.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_form-document-extraction-walkthrough.audit.md](./2026-03-18_form-document-extraction-walkthrough.audit.md)

## 1. Problem

`document-evidence-extraction-anchoring` 已经给出 adopted conclusion：

- first-round document evidence 应优先选择 structured form-like document
- 不需要先开 first-class source handle contract
- 不需要先开 snippet/span provenance contract
- 第一轮仍应保持 walkthrough/regression，而不是 durable extraction API

因此下一步不应先做通用 provenance framework，而是做一个具名 walkthrough，验证：

- 一个 structured form-like document fixture
- 一个 test-scope extraction/normalize helper
- 一个 test-scope materialization helper
- 一个 single downstream rule run

是否仍能在现有 substrate 下形成诚实的
`document -> extracted facts -> materialized facts -> rule -> explain` 链条。

## 2. Goals

- 用一个 synthetic form-like document walkthrough 验证 first-round document evidence vertical slice。
- walkthrough 必须显式包含：
  - stable document identifier
  - extraction/normalize step
  - 至少一个带 document identifier 的 extracted fact
  - 至少一个轻度歧义字段的 extraction handling
  - materialized helper outputs
  - single downstream trigger rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：当前 surface 是否足够诚实表达
  - 同一份 document 产出了哪些 extracted facts
  - helper 又输出了哪些 downstream facts
  - rule 实际消费了哪一层

## 3. Non-goals

- 不实现 durable extraction/provenance API。
- 不实现 OCR 或 LLM extraction。
- 不实现 snippet/span contract。
- 不引入 first-class source handle runtime surface。
- 不改现有 raw / summary / narrative / NL / static contracts。
- 不把本切片扩成 free-text narrative extraction。

## 4. Current Context

- transaction-feed walkthrough 已经证明：
  - structured source -> normalize -> materialize -> rule 的最小 vertical slice 在现有 contract 下是可行的
- document-evidence anchoring 已进一步指出：
  - document source 比 transaction feed 新增了 provenance/extraction pressure
  - 但 first-round 仍可保持 walkthrough 级验证
- 当前还未被 walkthrough 直接验证的是：
  - 多个 extracted facts 共同来自同一份 document 时，reader 能否看清这个同源关系
  - 轻度歧义字段是否会被 extraction helper 静默吞掉
  - current narrative / NL 是否会误说系统“知道”这些 facts，而不是“从 form 中抽出”

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用一个 single synthetic AML review/intake form，至少包含：

- stable `document_id` / `form_id`
- `account_id`
- `beneficiary_id`
- `device_id`
- review window or transaction count style fields
- one risk-bearing field
  - 例如 `jurisdiction = "high-risk-jurisdiction"`
- one threshold-bearing field
  - 例如 `score_ppm`, `score_threshold_ppm`
- one lightly ambiguous field
  - 例如枚举别名、日期格式、或弱规范化文本值

关键约束：

- document fixture 必须显式是“单个表单、多字段”
- walkthrough 不得退化成 transaction feed 的另一种手写 facts 形式
- 至少一个 extracted fact 必须把 `document_id` 写入 term structure 中，以便同源 facts 可在 audit/assertion drill-down 中手动关联

### 5.2 Extraction / Normalize Step

第一轮 walkthrough 必须显式包含一个 test-scope extraction/normalize helper：

- input:
  - structured form-like document（dict / JSON-like object）
- output:
  - extracted/normalized fact descriptors

例如可产出：

- form-derived beneficiary risk fact
- form-derived shared-device fact
- form-derived mismatch/risk flag
- form-derived score / threshold fact
- 或用于 helper materialization 的中间 extracted predicates

关键约束：

- helper 必须是 plain test-scope function，不是 durable API
- helper 必须至少保留一条 field-level round-trip check：
  - form field value -> extracted fact term value
- helper 对轻度歧义字段不能静默吞掉：
  - 要么 deterministic 映射为 extracted fact
  - 要么显式标记为 skipped/unsupported（test-scope side output 即可）

### 5.3 Materialization And Downstream Rule

如有必要，walkthrough 可通过 test-scope materialization step 将 extracted facts 变成 downstream helper outputs，例如：

- `aml:windowed_structuring_signal`
- `aml:trigger_evaluation_time`
- `aml:trigger_score_ppm`
- `aml:trigger_score_threshold_ppm`

然后以 single downstream trigger rule 为中心：

- single `rule_id`
- single `rule_run_id`
- single result row

结果保持最小 first-round 形状：

- `aml:review_required`
  - 或语义等价 predicate result

关键约束：

- downstream rule 不应直接消费 raw document object
- downstream rule 也不应假装自己完成了 extraction
- walkthrough 可以复用现有 AML trigger/materialization 路径，但必须保留 document-origin extracted layer

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 document-specific 要求：

- audit/assertion pages 必须仍能单独 inspect extracted facts
- document identifier 必须能通过 extracted fact detail 被看见
- current surfaces 不应假装存在 first-class document page 或 source object query

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `document-to-fact boundary remains inspectable`
   - extracted facts 能通过 assertion/audit/static page 单独 inspect
   - 至少一条 extracted fact 明确携带 document identifier
   - walkthrough 的 test 断言必须至少包含一条 field-level round-trip check：
     - form field value -> extracted fact term value
   - walkthrough 的 test 断言必须至少包含一条 same-document correlation check：
     - `>=2` 条来自同一 document 的 extracted facts
     - 在 term structure 中携带相同的 `document_id`
     - 以证明同源关系可以在 fact 层面被检查，而不是只靠 test 上下文推断
2. `ambiguous-field handling remains visible`
   - 轻度歧义字段不能被 helper 静默吞掉
   - walkthrough 必须显式证明该字段被 deterministic 映射，或被明确标记为 skipped/unsupported
3. `helper-vs-rule boundary remains honest`
   - narrative / NL / static proof-entry 不会误说 rule 自己完成了 document extraction
4. `current surface remains sufficient without new document contracts`
   - walkthrough 不需要 first-class source handle、snippet/span provenance 或 durable extraction API 就能完成 first-round validation

若任一条件不成立，失败方式应被单一化映射为：

- source handle gap
- snippet/span provenance gap
- extraction-boundary contract gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 extraction feature。

scope freeze:

- 以 tests 为主
- extraction/normalize helper 与 materialization helper 都保留在 test scope
- 不改 runtime/audit/service contract
- walkthrough 成功时不顺手冻结新的 document/provenance API
- walkthrough 失败时只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 structured form-like document walkthrough，不得滑入 free-text narrative extraction。
- 必须显式保留 document-origin extracted layer，不得直接从手写 downstream facts 起步。
- 不得把 document fixture 伪装成当前系统已有的 first-class source object surface。
- 不得把本切片扩成通用 provenance framework 设计。

## 7. Acceptance

- [x] synthetic form-document walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 stable document identifier + extraction/normalize helper + materialized helper outputs
- [x] walkthrough 已显式验证至少一个 field-level round-trip check
- [x] walkthrough 已显式验证至少一个轻度歧义字段未被静默吞掉
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 `document -> extracted facts -> materialized facts -> rule` 边界；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 single structured form fixture，并加入 stable document identifier 与一个轻度歧义字段。
2. 编写 test-scope extraction/normalize helper 与 materialization helper，确保至少一条 field-level round-trip check 与 ambiguous-field handling 可验证。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 document/provenance boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 structured form-document extraction walkthrough regression。
  - walkthrough 显式包含：
    - stable document fixture (`form_id`)
    - test-scope extraction/normalize helper
    - test-scope materialization helper
    - same-document correlation checks
    - single downstream AML trigger rule run
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 `document -> extracted facts -> materialized facts -> rule` 的边界：
    - document identifier 被写入 extracted fact term structure
    - 多条 extracted facts 可通过 shared `document_id` 手动关联
    - 轻度歧义字段被 deterministic alias mapping 显式处理，而未被静默吞掉
    - downstream rule witness surface 仍只覆盖 materialized/supporting AML predicates，不会误说 rule 自己完成了 document extraction
  - first-round 不需要 first-class source handle、snippet/span provenance 或 durable extraction API。
- 若不足，单一 follow-on gap：
  - 无。本次 walkthrough 未逼出 immediate source-handle / snippet-provenance / extraction-contract blocker。
- 归档说明：
  - 该切片证明 document evidence 的 first-round vertical slice 仍可保持在 walkthrough/regression 级别；更重的 provenance/extraction contracts 继续保持 deferred。
