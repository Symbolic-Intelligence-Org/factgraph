# Task Blueprint: Mixed-Source Case Pack Walkthrough

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
  - [2026-03-18_mixed-source-case-pack-anchoring.md](../archive/2026-03-18_mixed-source-case-pack-anchoring.md)
  - [2026-03-18_aml-transaction-feed-materialization-walkthrough.md](../archive/2026-03-18_aml-transaction-feed-materialization-walkthrough.md)
  - [2026-03-18_form-document-extraction-walkthrough.md](../archive/2026-03-18_form-document-extraction-walkthrough.md)
  - [2026-03-18_single-note-narrative-extraction-walkthrough.md](../archive/2026-03-18_single-note-narrative-extraction-walkthrough.md)
  - [2026-03-18_correlated-multi-note-review-walkthrough.md](../archive/2026-03-18_correlated-multi-note-review-walkthrough.md)
  - [2026-03-18_conflicting-multi-note-evidence-walkthrough.md](../archive/2026-03-18_conflicting-multi-note-evidence-walkthrough.md)
- Audit Log:
  - [2026-03-18_mixed-source-case-pack-walkthrough.audit.md](./2026-03-18_mixed-source-case-pack-walkthrough.audit.md)

## 1. Problem

单 source family walkthrough 已经压过：

- structured feed
- structured form
- single-note free-text
- multi-note non-conflicting
- multi-note conflicting

但当前还没有一条 walkthrough 直接验证：

- 同一 account/case 下，多种 source family 的 facts 同时进入一条 downstream rule / explain 链时
- 当前 surface 是否仍然足够让 reader 区分它们的来源、查看它们的 drill-down、并理解 helper 与 rule 的边界

## 2. Goals

- 用一个 synthetic mixed-source same-case package 验证 first-round mixed-source vertical slice。
- walkthrough 必须显式包含：
  - structured transaction feed rows
  - one structured form-like document
  - one or more short notes
  - shared account/case target
  - test-scope normalize/extract helpers for each source family
  - test-scope materialization helper
  - single downstream rule run
- walkthrough 必须完整穿过现有五层 explain delivery：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须明确判断：
  - 当前 assertion detail surfaces 是否足以区分 feed-derived、form-derived、note-derived facts

## 3. Non-goals

- 不实现 first-class case/package contract。
- 不实现 durable ingest/materialization API。
- 不实现 snippet/span provenance contract。
- 不实现新的 source-linkage graph / package object。
- 不改现有 raw / summary / narrative / NL / static contracts。

## 4. Current Context

- 单-source walkthrough 已经证明每一类 source family 自身都能在现有 substrate 下保持诚实边界。
- mixed-source anchoring 的 adopted conclusion 是：
  - first-round 还不需要 first-class case/package object
  - source-linkage 还不是 immediate blocker
  - 但 mixed-source distinguishability 是新的 load-bearing observation point

## 5. Proposed Shape

### 5.1 Scenario Shape

walkthrough 使用同一 account/case 下的最小 mixed-source pack，至少满足：

- `>=3` structured transaction feed rows
- `>=1` structured form-like document
- `>=1` short free-text note
- all source fixtures share one account/case target
- 至少一条 downstream materialized/helper fact 来自 feed-derived information
- 至少一条 downstream materialized/helper fact 来自 form-derived information
- 至少一条 downstream materialized/helper fact 来自 note-derived information

关键约束：

- 不得从手写 normalized/extracted facts 直接起步
- 各 source family 必须保留自己的 source identity：
  - feed refs
  - form/document ref
  - note ref
- first-round fixture 不要求冲突或 ordering semantics

### 5.2 Source-Family Helpers

walkthrough 必须显式包含 test-scope helpers：

- feed normalize/materialize helper
- form extract/materialize helper
- note extract/materialize helper

可以复用现有 single-source walkthrough 中已验证的 helper shape，但必须在 mixed-source fixture 下共同工作。

关键约束：

- helpers 必须保持 test scope，不是 durable API
- helpers 必须至少各保留一条 source-specific round-trip check
- helpers 不得在 mixed-source walkthrough 中偷偷抹平 source identity

### 5.3 Downstream Rule

使用一个 single downstream AML-style rule run：

- single `rule_id`
- single `rule_run_id`
- single result row

downstream rule 只消费 materialized facts，不直接消费 raw source fixtures。

关键约束：

- walkthrough 不应把 source-family merge 误说成 first-class case reasoning object
- ordinary matching / helper materialization 不得被写成 package-level synthesis semantics

### 5.4 Delivery Path To Validate

walkthrough 必须完整验证现有五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

额外的 mixed-source specific 要求：

- assertion/audit detail 必须仍能单独 inspect each source family
- current surfaces 不应假装存在 first-class case/package object
- current surfaces 不应假装存在 source-linkage graph

### 5.5 Success Criteria

这条 walkthrough 若要算成功，至少需要同时满足：

1. `each source family remains independently inspectable`
   - feed-derived、form-derived、note-derived facts 都能通过 assertion/audit/static page 单独 inspect
   - walkthrough 的 test 断言必须至少包含每个 source family 各一条 round-trip check
2. `cross-source distinguishability remains visible`
   - walkthrough 必须显式证明 reader 能仅通过现有 assertion detail surfaces 区分：
     - feed-derived facts
     - form-derived facts
     - note-derived facts
   - 这种区分不能依赖测试代码变量名或 fixture 上下文推断
   - walkthrough 的 test 断言必须至少包含一个 cross-source distinguishability check：
     - 从同一 rule run 的 assertion pages / assertion detail 中，选取分别来自 feed、form、note 三个 source family 的 assertion
     - 通过 `assertion_index.get_assertion_detail()` 取回其 `claim_args`
     - 并断言它们携带的 source ref 落在不同的 source-family namespace / ref shape 中
     - 从而证明仅靠 assertion detail surface 即可区分 source family
3. `helper-vs-rule boundary remains honest`
   - narrative / NL / static proof-entry 不会误说系统已经拥有 first-class case/package synthesis object
   - current wording 不会把 helper materialization 误说成 deeper case-level reasoning
4. `current surface remains sufficient without new mixed-source contracts`
   - walkthrough 不需要 first-class case/package object、source-linkage graph、durable ingest API、或 snippet/span provenance contract 就能完成 first-round validation

若任一条件不成立，失败方式应被单一化映射为：

- source-linkage gap
- case/package object gap
- extraction-boundary gap
- durable ingest/helper gap
- 或其他单一 follow-on gap

### 5.6 Expected Implementation Boundary

第一轮仍应是 walkthrough / regression slice，而不是新的 ingest/product feature。

scope freeze:

- 以 tests 为主
- all helpers remain in test scope
- 不改 runtime/audit/service contract
- walkthrough 成功时不顺手冻结新的 case/package/linkage API
- walkthrough 失败时只在 outcome 中命名单一 follow-on blueprint

## 6. Boundaries And Invariants

- 必须保持为 mixed-source same-case walkthrough，不得扩成真实 ingest system。
- 必须优先验证 source-family distinguishability，而不是顺手扩大为 provenance graph 设计。
- 不得把本切片扩成通用 package schema、OCR、或 durable import framework。

## 7. Acceptance

- [x] synthetic mixed-source walkthrough 已形成 single composite rule run
- [x] walkthrough 已显式包含 feed + form + note 三种 source family
- [x] walkthrough 已显式验证每个 source family 至少一条 round-trip check
- [x] walkthrough 已显式验证仅靠现有 assertion detail surfaces 就能区分不同 source family
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确判断现有 surface 是否足够支撑 mixed-source same-case package；若不足，gap 已被单一化分类

## 8. Implementation Plan

1. 设计 mixed-source same-case fixture bundle。
2. 复用并组合 single-source helpers，补每个 source family 的 round-trip checks 与 cross-source distinguishability checks。
3. 补 five-layer explain walkthrough regression，并在 outcome 中记录当前 mixed-source boundary 是否仍足够。

## 9. Docs To Update

- 默认无；若 walkthrough 实际迫使 contract 变化，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `src/factpy_kernel/tests/test_phase3_contracts_v1.py` 中新增了一条 mixed-source case-pack walkthrough regression。
  - walkthrough 显式包含：
    - structured transaction feed rows
    - one structured form-like document
    - one free-text note
    - per-source test-scope helpers
    - single downstream AML-style rule run
    - assertion-detail-based cross-source distinguishability checks
- 现有 surface 是否足够：
  - 足够。当前 substrate 已能诚实表达 mixed-source same-case package：
    - feed-derived、form-derived、note-derived facts 都可独立 inspect
    - reader 可仅通过 `assertion_index.get_assertion_detail()` 返回的 `claim_args` 与 source-ref shape 区分三类 source family
    - runtime raw / summary / narrative / NL explain 与 audit/static proof-entry 没有把 helper materialization 误说成 first-class case/package synthesis object
- 若不足，单一 follow-on gap：
  - 无。此次 walkthrough 没有暴露 immediate source-linkage、case/package、durable ingest、或 snippet/span blocker。
