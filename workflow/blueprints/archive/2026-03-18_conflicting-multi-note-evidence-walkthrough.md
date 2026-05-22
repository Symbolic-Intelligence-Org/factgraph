# Task Blueprint: Conflicting Multi-Note Evidence Walkthrough

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
  - [2026-03-18_conflicting-narrative-evidence-anchoring.md](../archive/2026-03-18_conflicting-narrative-evidence-anchoring.md)
  - [2026-03-18_correlated-multi-note-review-walkthrough.md](../archive/2026-03-18_correlated-multi-note-review-walkthrough.md)
  - [2026-03-18_single-note-narrative-extraction-walkthrough.md](../archive/2026-03-18_single-note-narrative-extraction-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_conflicting-multi-note-evidence-walkthrough.audit.md](./2026-03-18_conflicting-multi-note-evidence-walkthrough.audit.md)

## 1. Problem

`conflicting-narrative-evidence-anchoring` 已经给出 adopted conclusion：

- first-round conflicting evidence 应优先选择 explicit conflict retention
- 不需要先开 source-linkage contract
- 不需要先开 extraction uncertainty contract
- 不需要先开 judgment contract
- 第一轮仍应保持 walkthrough/regression，而不是 durable conflict API

因此下一步不应先做通用 conflict-resolution/judgment framework，而是做一个具名 walkthrough，验证：

- `>=2` notes with explicit conflicting statements
- test-scope extraction helper
- optional test-scope conflict meta
- downstream rule run 只消费匹配的一侧

是否仍能在现有 substrate 下形成诚实的
`notes -> conflicting extracted facts -> rule -> explain` 链条。

## 2. Goals

- 用一个 synthetic conflicting multi-note walkthrough 验证 first-round conflict-retention vertical slice。
- walkthrough 必须显式包含：
  - `>=2` notes with stable `note_id`
  - 至少一对互相冲突的 extracted facts
  - test-scope extraction helper
  - visible per-note identity in conflicting extracted fact terms
  - optional test-scope conflict meta
  - single downstream rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：当前 surface 是否足够诚实表达
  - conflicting facts 都存在
  - 哪条 fact 被 rule 消费
  - 哪条 conflicting fact 仍然保留但未被 witness

## 3. Non-goals

- 不实现 helper-side conflict resolution。
- 不实现 durable conflict/provenance API。
- 不实现 snippet/span provenance contract。
- 不实现 judgment contract。
- 不改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- correlated multi-note walkthrough 已经证明：
  - 多条 notes 可在 non-conflicting 前提下被 deterministic 聚合
- conflicting-evidence anchoring 已进一步指出：
  - first-round 不需要先解决冲突
  - 冲突可以先被保留在 extracted fact 层
  - current surface 的关键问题是 conflict 是否仍然可被诚实看见
- 当前还未被 walkthrough 直接验证的是：
  - conflicting extracted facts 同时存在时，reader 能否在不新增 contract 的前提下看见它们
  - current narrative / NL 是否会误导 reader 以为只有一条说法存在
  - downstream rule witness 某一侧时，未被 witness 的 conflicting fact 是否仍然可 audit

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用 `>=2` 条 short narrative notes，至少满足：

- each note has stable `note_id`
- all notes share one account/case target
- 至少一对 extracted facts 明确冲突
  - 例如 NOTE-A -> `low-risk-jurisdiction`
  - NOTE-B -> `high-risk-jurisdiction`
- 至少一条 supporting non-conflicting signal 仍存在
- first-round fixture 不做 automated conflict resolution

关键约束：

- notes 必须显式是自由文本，不得退化成 key/value form
- walkthrough 不得从手写 conflicting facts 直接起步
- conflicting extracted facts 必须在 term structure 中携带各自不同的 `note_id`
- downstream rule 只允许自然匹配其 where 所要求的一侧，不允许 helper 预先 resolve 冲突

### 5.2 Extraction Step

第一轮 walkthrough 必须显式包含一个 test-scope extraction helper：

- input:
  - list of short free-text notes
- output:
  - extracted fact descriptors
  - extraction meta / side output

例如可产出：

- NOTE-A derived low-risk fact
- NOTE-B derived high-risk fact
- other non-conflicting support signal facts

关键约束：

- helper 必须是 plain test-scope function，不是 durable API
- helper 必须至少保留一条 per-note phrase-level round-trip check
- helper 不得静默吞掉 conflicting statement
- helper 的 meta 可显式记录 `conflict_detected`, 但不得冻结成 runtime/audit contract

### 5.3 Downstream Rule

第一轮 walkthrough 不要求 helper-side resolution。

downstream rule 仅以现有 matching semantics 工作：

- 若 rule 需要 `high-risk-jurisdiction`
- 它自然绑定到 high-risk 那条 extracted/materialized fact
- conflicting low-risk fact 仍保留在 ledger 中，但不会成为 witness

结果保持最小 first-round 形状：

- `aml:review_required`
  - 或语义等价 predicate result

关键约束：

- downstream rule 不应直接消费 raw notes
- downstream rule 不应假装自己“解决了”冲突
- walkthrough 不得把 ordinary rule matching 误写成 judgment/resolution semantics

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 conflict-specific 要求：

- audit/assertion pages 必须仍能单独 inspect both sides of the conflict
- note identifiers 必须能通过 conflicting extracted fact detail 被看见
- current surfaces 不应假装存在 conflict-resolution object、source-linkage graph、或 judgment record

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `conflicting facts remain inspectable`
   - 至少两条 conflicting extracted facts 能通过 assertion/audit/static page 单独 inspect
   - conflicting facts 明确携带不同的 `note_id`
   - walkthrough 的 test 断言必须至少包含一条 per-note phrase-level round-trip check
2. `retained conflict remains visible`
   - walkthrough 必须显式证明 conflicting extracted facts 都存在于 ledger
   - downstream rule witness 其中一侧时，另一侧仍可通过 audit/assertion detail 被找到
   - walkthrough 的 test 断言必须显式验证：
     - 未被 rule witness 的 conflicting extracted fact 仍然能通过 `assertion_index.get_assertion_detail()` 被独立取回
     - 且其 `claim_args` 中仍携带对应的 `note_id` 与 conflicting term value
3. `helper-vs-rule boundary remains honest`
   - narrative / NL / static proof-entry 不会误说系统已经解决了 conflicting evidence
   - current wording 不会把 ordinary rule matching 误说成 conflict resolution, certainty, or judgment
4. `current surface remains sufficient without new conflict contracts`
   - walkthrough 不需要 source-linkage contract、extraction uncertainty contract、judgment contract、或 durable conflict API 就能完成 first-round validation

若任一条件不成立，失败方式应被单一化映射为：

- source-linkage gap
- conflict-visibility / extraction-boundary gap
- judgment/resolution gap
- extraction uncertainty gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 conflict feature。

scope freeze:

- 以 tests 为主
- extraction helper 与 optional conflict meta 都保留在 test scope
- 不改 runtime/audit/service contract
- walkthrough 成功时不顺手冻结新的 conflict/linkage/judgment API
- walkthrough 失败时只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 explicit conflict retention walkthrough，不得滑入 helper-side resolution。
- 必须显式保留 conflicting extracted layer，不得直接从手写 resolved facts 起步。
- 不得把 notes fixture 伪装成当前系统已有的 first-class conflict object surface。
- 不得把本切片扩成通用 contradiction、judgment、或 provenance framework 设计。

## 7. Acceptance

- [x] synthetic conflicting multi-note walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 `>=2` stable `note_id` + extraction helper + retained conflicting facts
- [x] walkthrough 已显式验证至少一个 per-note phrase-level round-trip check
- [x] walkthrough 已显式验证 conflicting facts 两侧都能被 inspect，而不仅是 witnessed side
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 `notes -> conflicting facts -> rule` 边界；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 `>=2` 条 short conflicting notes fixture，并加入 stable `note_id`。
2. 编写 test-scope extraction helper，确保 conflicting facts 被保留、per-note round-trip checks 可验证、optional conflict meta 可检查。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 conflicting-evidence boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 conflicting multi-note evidence walkthrough regression。
  - walkthrough 显式包含：
    - `>=2` short conflicting notes with stable `note_id`
    - test-scope extraction helper
    - test-scope conflict meta
    - per-note phrase-level round-trip checks
    - retained low-risk / high-risk extracted fact pair
    - non-conflicting support signals and materialized AML helper outputs
    - single downstream AML trigger rule run
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 `notes -> conflicting extracted facts -> rule` 的边界：
    - high-risk side 通过现有 helper output 被 rule 自然消费
    - low-risk side 虽未被 witness，但仍保留在 ledger 中
    - low-risk side 可通过 `assertion_index.get_assertion_detail()` 被独立取回，并保留 `note_id` 与 conflicting jurisdiction value
    - runtime raw / summary / narrative / NL explain 与 audit/static proof-entry 都未把 ordinary matching 误说成 conflict resolution、certainty、或 judgment
- 若不足，单一 follow-on gap：
  - 无。此次 walkthrough 没有暴露 immediate source-linkage、extraction-uncertainty、judgment、或 durable conflict-API blocker。
