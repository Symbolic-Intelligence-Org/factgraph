# Task Blueprint: Single-Note Narrative Extraction Walkthrough

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
  - [2026-03-18_free-text-narrative-evidence-anchoring.md](../archive/2026-03-18_free-text-narrative-evidence-anchoring.md)
  - [2026-03-18_form-document-extraction-walkthrough.md](../archive/2026-03-18_form-document-extraction-walkthrough.md)
  - [2026-03-18_clinical-weak-signal-walkthrough.md](../archive/2026-03-18_clinical-weak-signal-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_single-note-narrative-extraction-walkthrough.audit.md](./2026-03-18_single-note-narrative-extraction-walkthrough.audit.md)

## 1. Problem

`free-text-narrative-evidence-anchoring` 已经给出 adopted conclusion：

- first-round narrative evidence 应优先选择 single-note free-text extraction
- 不需要先开 snippet/span provenance contract
- 不需要先开 extraction uncertainty contract
- 第一轮仍应保持 walkthrough/regression，而不是 durable extraction API

因此下一步不应先做通用 provenance/uncertainty framework，而是做一个具名 walkthrough，验证：

- 一个 single short note fixture
- 一个 test-scope extraction helper
- optional test-scope materialization helper
- 一个 single downstream rule run

是否仍能在现有 substrate 下形成诚实的
`note -> extracted facts -> materialized facts -> rule -> explain` 链条。

## 2. Goals

- 用一个 synthetic single-note walkthrough 验证 first-round free-text narrative vertical slice。
- walkthrough 必须显式包含：
  - stable `note_id`
  - test-scope extraction helper
  - 至少一个 best-effort interpretation or explicit-skip path
  - visible note/document identity in extracted fact terms
  - single downstream trigger rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：当前 surface 是否足够诚实表达
  - 哪些 facts 是从 note 中 best-effort 抽出来的
  - helper 又输出了哪些 downstream facts
  - rule 实际消费了哪一层

## 3. Non-goals

- 不实现 durable extraction/provenance API。
- 不实现 snippet/span provenance contract。
- 不实现 multi-note synthesis。
- 不实现 OCR 或 LLM extraction pipeline。
- 不改现有 raw / summary / narrative / NL / static contracts。
- 不在本切片中引入新的 uncertainty result contract。

## 4. Current Context

- form-document walkthrough 已经证明：
  - structured document -> extracted facts -> materialized facts -> rule 在现有 contract 下是可行的
- free-text anchoring 已进一步指出：
  - single-note narrative 是 free-text 的最小增量路线
  - first-round 仍可维持 note-level provenance，而无需立刻引入 snippet/span contract
  - extraction ambiguity 可先以 deterministic best-effort interpretation 或 explicit skip 处理
- 当前还未被 walkthrough 直接验证的是：
  - natural-language note 是否会让 extraction boundary 变得不诚实
  - current narrative / NL 是否会把 best-effort interpretation 误说成确定性事实
  - note-level identity 是否已足够让 reader 手动关联同源 extracted facts

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用一个 single synthetic short narrative note，至少包含：

- stable `note_id`
- one account/entity reference
- one explicit risk-bearing statement
- one support signal statement
- one mild interpretation-bearing phrase
  - 例如非标准化措辞、近义表达、或需要 alias mapping 的描述
- optional one non-triggering background statement

关键约束：

- note fixture 必须显式是自由文本，不得退化成 key/value form
- walkthrough 不得从手写 extracted facts 直接起步
- 至少两条 extracted facts 必须把同一个 `note_id` / `document_id` 写入 term structure 中，以便同源关系可在 fact 层面被检查
- 至少一条 source statement 必须走 best-effort interpretation 或 explicit-skip 路径，不能全是零歧义直译

### 5.2 Extraction Step

第一轮 walkthrough 必须显式包含一个 test-scope extraction helper：

- input:
  - single short free-text note（string 或 dict 内文本字段）
- output:
  - extracted fact descriptors
  - extraction meta / side output

例如可产出：

- note-derived beneficiary risk fact
- note-derived device-sharing signal
- note-derived mismatch/risk flag
- note-derived trigger support fact

关键约束：

- helper 必须是 plain test-scope function，不是 durable API
- helper 至少保留一条 field/text-level round-trip check：
  - source phrase or token -> extracted fact term value
- helper 对轻度歧义表达不能静默吞掉：
  - 要么 deterministic best-effort 映射为 extracted fact，并在 meta 中留下可检查记录
  - 要么显式标记为 skipped/unsupported（test-scope side output 即可）
- helper 的 meta 可包含 excerpt/quote mapping，但不得把它冻结成 runtime/audit contract

### 5.3 Materialization And Downstream Rule

如有必要，walkthrough 可通过 test-scope materialization step 将 extracted facts 变成 downstream helper outputs，例如：

- `aml:windowed_structuring_signal`
- `aml:high_risk_outflow_signal`
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

- downstream rule 不应直接消费 raw note
- downstream rule 也不应假装自己完成了 extraction
- walkthrough 可以复用现有 AML trigger/materialization 路径，但必须保留 note-origin extracted layer

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 narrative-specific 要求：

- audit/assertion pages 必须仍能单独 inspect extracted facts
- note/document identifier 必须能通过 extracted fact detail 被看见
- current surfaces 不应假装存在 snippet/span page、source-note query、或 extraction confidence object

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `note-to-fact boundary remains inspectable`
   - extracted facts 能通过 assertion/audit/static page 单独 inspect
   - 至少两条 extracted facts 明确携带相同的 `note_id` / `document_id`
   - walkthrough 的 test 断言必须至少包含一条 phrase-level round-trip check：
     - source phrase -> extracted fact term value
2. `best-effort interpretation remains visible`
   - walkthrough 必须显式证明至少一条轻度歧义表达：
     - 被 deterministic best-effort 映射，并在 helper meta 中留痕
     - 或被明确标记为 skipped/unsupported
   - 轻度歧义表达不能被 helper 静默吞掉
3. `helper-vs-rule boundary remains honest`
   - narrative / NL / static proof-entry 不会误说 rule 自己完成了 narrative extraction
   - current wording 不会把 best-effort interpretation 误说成 certainty or confirmed fact
   - walkthrough 的 NL explain test 断言必须至少包含一条 negative wording check：
     - NL paragraphs 中不得出现暗示 extraction 结果是 `confirmed` / `certain` / `verified` 的措辞
4. `current surface remains sufficient without new narrative contracts`
   - walkthrough 不需要 snippet/span provenance、extraction uncertainty contract 或 durable extraction API 就能完成 first-round validation

若任一条件不成立，失败方式应被单一化映射为：

- snippet/span provenance gap
- extraction-boundary contract gap
- extraction uncertainty gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 extraction feature。

scope freeze:

- 以 tests 为主
- extraction helper 与 optional materialization helper 都保留在 test scope
- 不改 runtime/audit/service contract
- walkthrough 成功时不顺手冻结新的 note/provenance/uncertainty API
- walkthrough 失败时只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 single-note walkthrough，不得滑入 multi-note narrative synthesis。
- 必须显式保留 note-origin extracted layer，不得直接从手写 downstream facts 起步。
- 不得把 note fixture 伪装成当前系统已有的 first-class source object surface。
- 不得把本切片扩成通用 provenance 或 uncertainty framework 设计。

## 7. Acceptance

- [x] synthetic single-note walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 stable `note_id` + extraction helper + optional materialized helper outputs
- [x] walkthrough 已显式验证至少一个 phrase-level round-trip check
- [x] walkthrough 已显式验证至少一个轻度歧义表达未被静默吞掉
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 `note -> extracted facts -> materialized facts -> rule` 边界；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 single short note fixture，并加入 stable `note_id` 与一个轻度歧义表达。
2. 编写 test-scope extraction helper 与 optional materialization helper，确保至少一条 phrase-level round-trip check 与 ambiguity handling 可验证。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 narrative/provenance boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 single-note narrative extraction walkthrough regression。
  - walkthrough 显式包含：
    - stable note fixture (`note_id`)
    - test-scope extraction helper
    - test-scope materialization helper
    - same-note correlation checks
    - phrase-level round-trip check
    - visible best-effort interpretation metadata
    - explicit skipped background phrase
    - single downstream AML trigger rule run
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 `note -> extracted facts -> materialized facts -> rule` 的边界：
    - 至少两条 extracted facts 在 term structure 中携带相同 `note_id`
    - phrase-level round-trip check 可证明 source phrase 到 extracted term 的映射未丢失关键值
    - 轻度歧义表达通过 deterministic best-effort interpretation 被显式记录在 helper meta 中，而非被静默吞掉
    - downstream rule witness surface 仍只覆盖 materialized/supporting AML predicates，不会误说 rule 自己完成了 narrative extraction
    - NL explain 明确通过 negative wording checks 排除了 `confirmed` / `certain` / `verified` 这类把 best-effort interpretation误说成确定性事实的措辞
  - first-round 不需要 snippet/span provenance、extraction uncertainty contract 或 durable extraction API。
- 若不足，单一 follow-on gap：
  - 无 immediate blocker 被暴露；snippet/span provenance、extraction uncertainty、durable extraction/provenance API 继续保持 deferred。
