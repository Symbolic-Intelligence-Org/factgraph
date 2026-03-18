# Task Blueprint: Document Evidence Extraction Anchoring

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_aml-transaction-feed-normalization-anchoring.md](../archive/2026-03-18_aml-transaction-feed-normalization-anchoring.md)
  - [2026-03-18_aml-transaction-feed-materialization-walkthrough.md](../archive/2026-03-18_aml-transaction-feed-materialization-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
- Audit Log:
  - [2026-03-18_document-evidence-extraction-anchoring.audit.md](./2026-03-18_document-evidence-extraction-anchoring.audit.md)

## 1. Problem

`structured source -> normalize -> materialize -> rule -> explain` 的最小 vertical slice 已经通过 AML transaction-feed walkthrough 验证。

因此当前最值得继续压力测试的上游边界，已经不再是结构化 source ingestion，而是：

- source 本身带有语义歧义或 extraction uncertainty 时，
- 当前 substrate 是否还能保持 source-to-fact 的诚实边界
- 以及 provenance chain 是否仍然足够让 consumer 理解：
  - 原文是什么
  - 系统抽取成了什么
  - 哪一步是 deterministic parsing
  - 哪一步已经进入 interpretation / uncertainty

这条蓝图不是立刻做 extraction pipeline，而是收敛 document-evidence 的第一条近端切片。

## 2. Goals

- 比较两条 document-evidence 路线，并选出 first-round 更合适的近端切片：
  - structured form-like document extraction
  - free-text narrative evidence extraction
- 明确 document source 的第一条 vertical slice 应主要验证：
  - extraction boundary
  - provenance honesty
  - uncertainty pressure
- 判断第一轮是否仍然可以保持为 walkthrough/regression，还是 document evidence 一上来就会逼出新的 source/provenance/uncertainty contract。

## 3. Non-goals

- 不实现 OCR、LLM parsing 或 production extraction pipeline。
- 不在本蓝图中设计完整 document schema / provenance API。
- 不新增新的 runtime explain contract。
- 不重开 structured feed ingestion 路线。
- 不直接实现 `weak-signal uncertainty contract`，除非 document extraction 本身把它逼成 immediate blocker。

## 4. Current Context

- 现有系统已经证明：
  - synthetic facts 可行
  - materialized helper outputs 可行
  - structured source normalization 可行
- 但这些成功案例都有一个共同点：
  - source shape 本身几乎没有语义歧义
- document evidence 则会第一次显式引入：
  - extraction correctness boundary
  - provenance from source text to normalized fact
  - source-level ambiguity that may itself become uncertainty pressure

因此 document-evidence 线的价值，不只是“再加一个 source shape”，而是：

- 它最可能第一次真正逼出：
  - source identity/provenance contract
  - extraction-boundary contract
  - 或弱不确定性语义

## 5. Proposed Shape

### 5.1 Comparison Frame

本蓝图比较两条近端路线：

- `Route A: structured form-like document extraction`
  - 例如半结构化 case form、inspection checklist、incident form
- `Route B: free-text narrative evidence extraction`
  - 例如 operator note、clinical note、investigator narrative

比较维度：

- first-round implementation fit
- extraction ambiguity level
- provenance honesty 是否可在现有 substrate 下表达
- 是否会立刻逼出新的 uncertainty / source-identity / lineage contract

### 5.2 Route A: Structured Form-like Document Extraction

这条路线把 document source 限定为：

- 字段化或半字段化文档
- 人类可读，但 extraction 仍接近 deterministic mapping

例如：

- checklist
- incident form
- intake form
- tabular report converted to key/value records

它的优点：

- 比 transaction feed 更接近真实 document evidence
- 但仍能把 ambiguity 控制在较低水平
- 更适合 first-round 验证：
  - source text/field 到 normalized fact 的最小 provenance 边界
  - extraction helper 是否会被误说成 semantic reasoning

它真正测试的新问题是：

- 文档片段是否需要 first-class source handle
- extracted fact 是否需要带 snippet/span style provenance
- current explain/audit 是否足以让 consumer 看懂 “这是从表单字段抽出来的”，而不是系统直接“知道”这个事实

### 5.3 Route B: Free-text Narrative Evidence Extraction

这条路线直接把 source 设为 narrative text，例如：

- operator note
- clinical note
- investigator memo
- requirement paragraph

它的价值更高，但 first-round 风险也更大：

- extraction correctness 与 semantic interpretation 会迅速缠在一起
- source ambiguity 本身可能就等于 uncertainty semantics 问题
- provenance 也更难被简单表达成 field-level mapping

对当前阶段而言，这条路线的主要风险是：

- 它很可能让首个 document slice 同时变成：
  - extraction contract
  - provenance contract
  - uncertainty contract
  - potentially LLM/OCR contract

这会让 first-round vertical slice 失去聚焦。

### 5.4 Adopted Recommendation

adopted recommendation：

- 近端优先 `Route A`
  - structured form-like document extraction
- `Route B` 保持后置
  - 作为 narrative-extraction 专门线

原因：

1. 它是从 structured feed 往 document evidence 过渡的最小增量，而不是跳进最大歧义源
2. 它最适合 first-round 测试：
   - provenance honesty
   - extraction boundary
   - source snippet / field mapping 是否需要 first-class support
3. 它更容易把失败单一化归因到：
   - source handle gap
   - snippet/span provenance gap
   - extraction-boundary contract gap

### 5.5 Adopted Gate Answers

在 opening first implementation blueprint 之前，本 anchoring 已收敛出三条 adopted gate answers：

1. `source handle`
   - first-round **不需要** first-class source-handle contract。
   - 但这次比 structured feed 更进一步：test-scope document fixture 必须带稳定 document identifier（例如 `form_id` / `document_id`），而 normalize/extraction step 必须把这个 identifier 写进至少一个 extracted fact 的 term structure 中。
   - 这样同源 facts 才能通过 assertion drill-down 被关联回同一份文档，而不需要先引入新的 runtime/audit source-object surface。
   - first-class source handle 继续后置；只有当 consumer 必须直接查询或聚合同一 document 产出的全部 facts 时，它才更可能成为 blocker。
2. `snippet/span provenance`
   - first-round **不需要** snippet/span provenance contract。
   - 对于 form-like document，field-to-fact 命名约定与 document identifier 已足以支撑 first-round provenance honesty。
   - 但 walkthrough 必须包含至少一个轻度歧义字段的 extraction 验证：
     - extraction helper 不能默默吞掉模糊输入
     - 它必须要么保留为 normalized fact，要么在 test-scope 输出中被显式标记为 skipped/unsupported
   - 真正的 snippet/span provenance 继续后置，更适合 free-text narrative route。
3. `walkthrough vs durable extraction helper`
   - first-round 仍应保持为 **walkthrough/regression**。
   - extraction/normalize step 可保持 test-scope helper function，不需要 durable extraction or provenance API。
   - 只有当 walkthrough 暴露出 extraction 必须被 replay、audit versioned、或 source-boundary 无法仅靠 test-scope helper 诚实表达时，才应拆出 durable extraction contract blueprint。

因此，本 anchoring 的 adopted next-slice recommendation 直接是：

- `form-document-extraction-walkthrough`

而不是先开 source-handle / snippet-provenance / durable-extraction gap blueprint。

## 6. Boundaries And Invariants

- 必须优先选择 document-evidence 的最小增量路线，不得一上来就混入 free-text / OCR / LLM。
- 不得把本蓝图扩成通用 provenance framework 设计。
- 若发现 gap，必须单一化命名，不得在一个蓝图里同时打开 source handle、snippet provenance、uncertainty 三个问题。
- 不得在本轮里偷偷回到结构化 feed 已验证过的问题。

## 7. Acceptance

- [x] 两条 document-evidence 路线已被明确比较
- [x] first-round 推荐路线已 adopted，并说明为什么它比另一条更适合作为近端 vertical slice
- [x] opening implementation 之前必须回答的 gate 已明确
- [x] 若已有 adopted conclusion，下一条 blueprint 的类型（walkthrough or gap）已被明确命名

## 8. Implementation Plan

1. 收敛 document evidence 的最小比较框架，避免问题膨胀成 OCR/LLM pipeline 设计。
2. 判断哪条路线最能补齐新的 provenance/extraction 压力，而不把 first-round 变成多问题混切。
3. 形成 adopted next-slice recommendation，并在 outcome 中记录 deferred route。

## 9. Docs To Update

- 默认无；若 adopted conclusion 直接冻结新的 durable boundary，再补对应模块 docs

## 10. Outcome / Deviations

- adopted first-route：
  - `Route A: structured form-like document extraction`
- opening gate answers：
  - source handle：first-round 不需要 first-class source handle contract，但 document identifier 必须被写进至少一个 extracted fact 的 term structure 中，以支持同源 facts 的 drill-down 关联。
  - provenance detail：first-round 不需要 snippet/span provenance contract；field-to-fact mapping 已足够，但 walkthrough 必须包含一个轻度歧义字段的 extraction 验证，且该字段不能被静默吞掉。
  - implementation shape：first-round 仍是 walkthrough/regression，extraction/normalize helper 保持 test scope；只有当 replay/audit/versioning 成为刚性需求时，才再拆 durable extraction contract。
- next blueprint：
  - `form-document-extraction-walkthrough`
- deferred route：
  - `Route B: free-text narrative evidence extraction`
  - first-class source handle contract
  - snippet/span provenance contract
  - durable extraction/provenance helper API
- 归档说明：
  - 本切片是纯 analysis/anchoring 蓝图；gate 收敛后直接归档，不涉及代码、测试或模块 docs 改动。
