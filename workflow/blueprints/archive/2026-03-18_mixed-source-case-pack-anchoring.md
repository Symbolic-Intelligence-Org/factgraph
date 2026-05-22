# Task Blueprint: Mixed-Source Case Pack Anchoring

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
  - [docs/session_handoff_2026-03-18.md](../../session_handoff_2026-03-18.md)
- Audit Log:
  - [2026-03-18_mixed-source-case-pack-anchoring.audit.md](./2026-03-18_mixed-source-case-pack-anchoring.audit.md)

## 1. Problem

当前 synthetic walkthrough 已经覆盖：

- structured feed
- structured form-like document
- single-note free-text
- correlated multi-note
- conflicting multi-note

而且都没有把任何 deferred gap 逼成 immediate blocker。

如果还想获得新信息，下一步不能再是“同一 source 形状里的更复杂 fixture”，而应该是：

- 同一 case 下，多个不同 source 形状共同进入一条推理/解释链

也就是一个最小 mixed-source case pack：

- transaction feed
- form-like document
- investigator notes

共同支撑同一 account/case 的 downstream walkthrough。

## 2. Goals

- 判断“mixed-source same-case package”是否是当前最有价值的上游压力点。
- 比较：
  - 一个可控的 semi-real mixed-source pack
  - 一个更真实但更脏的 uncontrolled bundle
- 明确下一条 implementation-facing blueprint 应该是 walkthrough 还是先开新的 capability gap。

## 3. Non-goals

- 不直接做 OCR / PDF parsing / LLM extraction。
- 不直接做 durable ingest API。
- 不直接做 first-class case/package contract。
- 不直接做新的 provenance graph / linkage API。
- 不直接打开 `T2`、judgment、`U2` capability blueprint。

## 4. Current Context

- 当前 substrate 已验证：
  - source-shape coverage 足够宽
  - conflicting evidence retention 也仍然诚实
- 但这些 walkthrough 仍有一个共同前提：
  - 单次 vertical slice 只从一种 source family 起步
- 当前还没被直接验证的是：
  - 同一 case 下，不同 source family 的 facts 是否仍然能在现有 surface 下保持可追溯、可区分、可 drill-down
  - reader 是否还能在没有 first-class case/source-linkage object 的情况下手动恢复“哪些事实来自 feed、哪些来自 form、哪些来自 notes”

## 5. Proposed Shape

### 5.1 Candidate Routes

#### Route A: Semi-Real Mixed-Source Single-Case Pack

一个受控但异构的 case package，同一 case/account 下同时包含：

- structured transaction feed rows
- structured form-like document
- one or more narrative notes

每类 source 都走各自的 test-scope normalize/extract helper，再共同进入一个 downstream rule run。

#### Route B: Uncontrolled Realistic Bundle

更接近真实世界的 source bundle，例如：

- 脏格式
- 更长文档
- 互相不一致的 naming
- 更弱的 source metadata

同时可能引入：

- OCR-like ambiguity
- snippet/span pressure
- extraction uncertainty
- package-level replay requirements

### 5.2 Comparison

#### Route A

- 新信息密度：高
  - 第一次把多种 source family 放进同一 case
- 变量控制：高
  - 仍然可以把失败单一化归因
- 与当前 substrate 的距离：近
  - 不需要立刻引入 OCR/LLM 或 durable ingest
- 最可能暴露的问题：
  - source-linkage / case correlation boundary 是否还够

#### Route B

- 新信息密度：也高
- 但变量控制：低
  - 一开始就会把 extraction ambiguity、provenance granularity、package durability 混在一起
- 与当前 substrate 的距离：远
  - 很难在 first-round 把失败归因到单一主问题

### 5.3 Route A Analysis

Route A 是当前最合理的 next pressure source，因为它第一次验证：

- 同一 case 下的 mixed-source provenance
- 同一 downstream rule run 的跨 source contribution
- 当前 assertion-level drill-down 是否足以替代 first-class case/source graph

它测试的新问题不是“又一种 source shape 能不能抽取”，而是：

- 多种 source shape 一起出现时，现有 surface 还能不能保持边界清晰

### 5.4 Adopted Recommendation

近端优先 `Route A: semi-real mixed-source single-case pack`。

它是当前最小、最可控、最可能产出新信息的一步：

- 比现有任何单-source walkthrough 更接近真实 package
- 但还没有复杂到把 OCR / snippet / uncertainty / durable ingest 全部同时拖进来

### 5.5 Adopted Gate Answers

1. `first-class case/package object`
   - first-round 不需要 first-class case/package object
   - shared target refs + per-source refs 仍足够支撑 walkthrough
2. `source-linkage blocker`
   - source-linkage 还不是 immediate blocker
   - 但 mixed-source walkthrough 必须把它当作主观察点：
     - 必须显式验证 reader 能否仅通过现有 assertion detail surfaces 区分 feed-derived、form-derived、note-derived facts
3. `walkthrough vs durable API`
   - 第一轮仍应保持 walkthrough/regression
   - 以 fixture bundle manifest + test-scope helpers 验证 mixed-source honesty

因此 adopted next blueprint 是：

- `mixed-source-case-pack-walkthrough`

而不是直接打开：

- first-class case/package contract
- source-linkage contract
- durable ingest/materialization API
- snippet/span provenance

## 6. Boundaries And Invariants

- first-round 必须保持为 mixed-source same-case pressure，不得扩成真实 OCR / parsing / LLM extraction 项目。
- 必须优先观察 source-linkage / package correlation 边界，而不是顺手重开 `T2`、judgment、或 `U2`。
- 若 walkthrough 暴露 blocker，必须尽量单一化归因，不得把 package、provenance、uncertainty 一起打包成泛化能力蓝图。

## 7. Acceptance

- [x] Route A / Route B 的比较已足够说明为什么 mixed-source pack 是当前最有价值的下一跳
- [x] 已明确 mixed-source pack 相比现有 single-source walkthrough 的新增压力点
- [x] 已明确是否需要 first-class case/package object
- [x] 已明确 source-linkage 是否已成 immediate blocker
- [x] 已明确 first implementation 应为 walkthrough 还是更重的 ingest/helper slice
- [x] 已给出下一条 blueprint 的 adopted 方向

## 8. Implementation Plan

1. 固定 Route A / Route B 的边界和比较维度。
2. 回答 mixed-source case/package、source-linkage、walkthrough-vs-durable 三个 gate。
3. 若答案收敛，直接归档并打开下一条 implementation-facing blueprint。

## 9. Docs To Update

- 默认无；这是 analysis-only anchoring

## 10. Outcome / Deviations

- adopted route：
  - `Route A: semi-real mixed-source single-case pack`
- gate answers：
  - first-round 不需要 first-class case/package object
  - source-linkage 不是 immediate blocker，但 mixed-source distinguishability 是 walkthrough 的 load-bearing observation point
  - first implementation 仍应保持 walkthrough/regression
- next blueprint：
  - `mixed-source-case-pack-walkthrough`
- deferred gaps：
  - first-class case/package contract
  - source-linkage contract
  - durable ingest/materialization API
  - snippet/span provenance
  - extraction uncertainty
