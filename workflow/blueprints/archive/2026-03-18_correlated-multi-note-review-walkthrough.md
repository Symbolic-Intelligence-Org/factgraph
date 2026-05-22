# Task Blueprint: Correlated Multi-Note Review Walkthrough

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
  - [2026-03-18_multi-note-narrative-synthesis-anchoring.md](../archive/2026-03-18_multi-note-narrative-synthesis-anchoring.md)
  - [2026-03-18_single-note-narrative-extraction-walkthrough.md](../archive/2026-03-18_single-note-narrative-extraction-walkthrough.md)
  - [2026-03-18_aml-aggregation-materialization-walkthrough.md](../archive/2026-03-18_aml-aggregation-materialization-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_correlated-multi-note-review-walkthrough.audit.md](./2026-03-18_correlated-multi-note-review-walkthrough.audit.md)

## 1. Problem

`multi-note-narrative-synthesis-anchoring` 已经给出 adopted conclusion：

- first-round multi-note narrative evidence 应优先选择 correlated multi-note review
- 不需要先开 snippet/span provenance contract
- 不需要先开 extraction uncertainty contract
- 第一轮仍应保持 walkthrough/regression，而不是 durable synthesis API
- temporal ordering 继续后置，不进入 `T2`

因此下一步不应先做通用 synthesis/provenance/uncertainty framework，而是做一个具名 walkthrough，验证：

- multiple short notes sharing one account/case
- test-scope extraction helper
- optional test-scope aggregation/materialization helper
- 一个 single downstream rule run

是否仍能在现有 substrate 下形成诚实的
`notes -> extracted facts -> aggregated/materialized facts -> rule -> explain` 链条。

## 2. Goals

- 用一个 synthetic correlated multi-note walkthrough 验证 first-round multi-note vertical slice。
- walkthrough 必须显式包含：
  - `>=2` notes with stable `note_id`
  - shared account/case target
  - test-scope extraction helper
  - visible per-note identity in extracted fact terms
  - deterministic cross-note aggregation/materialization helper
  - single downstream trigger rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：当前 surface 是否足够诚实表达
  - 哪些 facts 来自哪条 note
  - helper 聚合了哪些 note-derived signals
  - rule 实际消费了哪一层

## 3. Non-goals

- 不实现 durable synthesis/provenance API。
- 不实现 snippet/span provenance contract。
- 不实现 temporal note progression。
- 不引入 T2 ordering semantics。
- 不改现有 raw / summary / narrative / NL / static contracts。
- 不在本切片中引入新的 uncertainty result contract。

## 4. Current Context

- single-note narrative walkthrough 已经证明：
  - free-text note -> extracted facts -> materialized facts -> rule 在现有 contract 下是可行的
- multi-note anchoring 已进一步指出：
  - correlated multi-note review 是最小增量路线
  - first-round 仍可维持 note-level provenance，而无需立刻引入 snippet/span contract
  - cross-note aggregation 可先以 deterministic union/dedup 或 best-effort helper 处理
  - temporal ordering 继续后置
- 当前还未被 walkthrough 直接验证的是：
  - multiple notes 共同支持一个结论时，reader 能否看清每条 note 的贡献边界
  - current narrative / NL 是否会把 helper aggregation 误说成 deeper synthesis semantics
  - note-level identity 是否已足够让 reader 手动关联同源 extracted facts across notes

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用 `>=2` 条 short narrative notes，至少满足：

- each note has stable `note_id`
- all notes share one account/case target
- notes contain overlapping but non-conflicting support statements
- 至少一条 note 含 risk-bearing phrase
- 至少一条 note 含 support signal phrase
- 至少一条 note 含 mild interpretation-bearing phrase
- optional one background/non-triggering phrase remains explicit skip

关键约束：

- notes 必须显式是自由文本，不得退化成 key/value form
- walkthrough 不得从手写 extracted facts 直接起步
- 至少两条来自不同 notes 的 extracted facts 必须在 term structure 中携带各自不同的 `note_id`
- 至少一条 aggregated/materialized fact 必须能够被 test 证明来自多个 notes 的联合贡献，而不是单 note 重演
- first-round fixture 不允许 contradictory notes；若存在冲突，必须显式跳过并留给后续 gap

### 5.2 Extraction Step

第一轮 walkthrough 必须显式包含一个 test-scope extraction helper：

- input:
  - list of short free-text notes
- output:
  - extracted fact descriptors
  - extraction meta / side output

例如可产出：

- note-derived beneficiary risk fact
- note-derived device-sharing signal
- note-derived mismatch/risk flag
- note-derived count/support fact

关键约束：

- helper 必须是 plain test-scope function，不是 durable API
- helper 必须至少保留一条 per-note phrase-level round-trip check：
  - source phrase -> extracted fact term value
- helper 的 meta 可包含 per-note excerpt mapping，但不得把它冻结成 runtime/audit contract
- helper 对轻度歧义表达不能静默吞掉：
  - 要么 deterministic best-effort 映射为 extracted fact，并在 meta 中留下可检查记录
  - 要么显式标记为 skipped/unsupported

### 5.3 Aggregation / Materialization And Downstream Rule

第一轮 walkthrough 可通过 test-scope aggregation/materialization helper 将 multi-note extracted facts 变成 downstream helper outputs，例如：

- union/dedup 后的 shared-device support
- aggregated high-risk outflow signal
- aggregated trigger score or threshold support
- aggregated window/count support

然后以 single downstream trigger rule 为中心：

- single `rule_id`
- single `rule_run_id`
- single result row

结果保持最小 first-round 形状：

- `aml:review_required`
  - 或语义等价 predicate result

关键约束：

- downstream rule 不应直接消费 raw notes
- downstream rule 也不应假装自己完成了 cross-note synthesis
- aggregation/materialization helper 必须保持 deterministic，且不引入 ordering semantics

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 multi-note specific 要求：

- audit/assertion pages 必须仍能单独 inspect extracted facts from each note
- note identifiers 必须能通过 extracted fact detail 被看见
- current surfaces 不应假装存在 snippet/span page、note-link graph、或 synthesis confidence object

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `cross-note fact boundary remains inspectable`
   - extracted facts 能通过 assertion/audit/static page 单独 inspect
   - 至少两条来自不同 notes 的 extracted facts 明确携带不同的 `note_id`
   - walkthrough 的 test 断言必须至少包含一条 per-note phrase-level round-trip check
2. `cross-note aggregation remains visible`
   - walkthrough 必须显式证明至少一条 aggregated/materialized fact 由多个 notes 的 extracted facts 共同支持
   - helper aggregation 不得静默吞掉 note-level distinctions
3. `helper-vs-rule boundary remains honest`
   - narrative / NL / static proof-entry 不会误说 rule 自己完成了 multi-note synthesis
   - current wording 不会把 deterministic aggregation 误说成 deeper interpretation certainty
   - walkthrough 的 NL explain test 断言必须至少包含一条 negative wording check：
     - NL paragraphs 中不得出现暗示 extraction 结果是 `confirmed` / `certain` / `verified` 的措辞
     - 也不得出现暗示系统完成了 `synthesis` / `comprehensive analysis` 的措辞
4. `current surface remains sufficient without new multi-note contracts`
   - walkthrough 不需要 snippet/span provenance、extraction uncertainty contract、stronger source/linkage contract、或 durable synthesis API 就能完成 first-round validation

若任一条件不成立，失败方式应被单一化映射为：

- snippet/span provenance gap
- extraction uncertainty gap
- source/linkage gap
- T2/ordering gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 synthesis feature。

scope freeze:

- 以 tests 为主
- extraction helper 与 aggregation/materialization helper 都保留在 test scope
- 不改 runtime/audit/service contract
- walkthrough 成功时不顺手冻结新的 multi-note provenance/uncertainty API
- walkthrough 失败时只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 correlated multi-note walkthrough，不得滑入 temporal progression。
- 必须显式保留 note-origin extracted layer，不得直接从手写 aggregated facts 起步。
- 不得把 notes fixture 伪装成当前系统已有的 first-class source graph surface。
- 不得把本切片扩成通用 provenance、uncertainty、或 synthesis framework 设计。

## 7. Acceptance

- [x] synthetic correlated multi-note walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 `>=2` stable `note_id` + extraction helper + aggregation/materialization helper
- [x] walkthrough 已显式验证至少一个 per-note phrase-level round-trip check
- [x] walkthrough 已显式验证至少一个 aggregated fact 的 multi-note contribution
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够诚实表达 `notes -> extracted facts -> aggregated facts -> rule` 边界；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 `>=2` 条 short notes fixture，并加入 stable `note_id` 与一个轻度歧义表达。
2. 编写 test-scope extraction helper 与 aggregation/materialization helper，确保至少一条 per-note phrase-level round-trip check 与一条 aggregated multi-note contribution check 可验证。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 multi-note/provenance boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 correlated multi-note review walkthrough regression。
  - walkthrough 显式包含：
    - `>=2` short note fixtures with stable `note_id`
    - test-scope extraction helper
    - test-scope aggregation/materialization helper
    - per-note round-trip checks
    - cross-note contribution checks
    - visible best-effort interpretation metadata
    - explicit skipped background phrase
    - single downstream AML trigger rule run
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 `notes -> extracted facts -> aggregated facts -> rule` 的边界：
    - 至少两条 extracted facts 在 term structure 中携带不同 `note_id`
    - per-note round-trip checks 可证明 source phrase 到 extracted term 的映射未丢失关键值
    - aggregated/materialized facts 可通过 helper meta 明确证明来自多个 notes 的联合贡献，而不是单 note 重演
    - downstream rule witness surface 仍只覆盖 materialized/supporting AML predicates，不会误说 rule 自己完成了 multi-note synthesis
    - NL explain 明确通过 negative wording checks 排除了 `confirmed` / `certain` / `verified` / `synthesis` / `comprehensive analysis` 这类 over-claim 措辞
  - first-round 不需要 snippet/span provenance、extraction uncertainty contract、stronger source/linkage contract、或 durable synthesis API。
- 若不足，单一 follow-on gap：
  - 无 immediate blocker 被暴露；snippet/span provenance、extraction uncertainty、stronger source/linkage、以及 temporal progression/T2 继续保持 deferred。
