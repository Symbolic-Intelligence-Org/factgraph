# Task Blueprint: Free-Text Narrative Evidence Anchoring

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
  - [2026-03-18_document-evidence-extraction-anchoring.md](../archive/2026-03-18_document-evidence-extraction-anchoring.md)
  - [2026-03-18_form-document-extraction-walkthrough.md](../archive/2026-03-18_form-document-extraction-walkthrough.md)
  - [2026-03-18_clinical-deterioration-uncertainty-anchoring.md](../archive/2026-03-18_clinical-deterioration-uncertainty-anchoring.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
- Audit Log:
  - [2026-03-18_free-text-narrative-evidence-anchoring.audit.md](./2026-03-18_free-text-narrative-evidence-anchoring.audit.md)

## 1. Problem

`form-document-extraction-walkthrough` 已证明：

- structured document source
- extracted facts
- materialized helper outputs
- downstream rule run

可以在现有 substrate 下形成一条诚实的 `source -> normalize -> materialize -> rule -> explain` 链。

因此 document line 的下一个真正压力点，已经不是更复杂的 form，而是 **free-text narrative evidence**：

- source 本身不是字段化，而是自然语言叙述
- extraction 不再只是 field-level deterministic mapping
- provenance 粒度也不再天然等于 `document_id`

这意味着下一步最值得回答的问题是：

- free-text narrative 是否仍能在现有 substrate 下保持诚实边界
- 还是第一次真正逼出：
  - snippet/span provenance contract
  - extraction-boundary contract
  - extraction-step uncertainty semantics
  - 或时间序列/T2 压力

## 2. Goals

- 为 free-text narrative evidence 选出 first meaningful near-term cut，而不是泛化设计整条 extraction pipeline。
- 比较至少两条 narrative-evidence 路线，并判断哪条最适合作为 first-round pressure test。
- 明确 free-text 线最可能逼出的 primary blocker 是什么：
  - snippet/span provenance
  - extraction-boundary contract
  - extraction-step uncertainty
  - 或 T2 sequence/state semantics
- 产出 adopted next-slice recommendation，而不是直接进入实现。

## 3. Non-goals

- 不实现 OCR、LLM parsing、embedding retrieval 或 production extraction pipeline。
- 不在本蓝图中设计完整 provenance API。
- 不新增新的 runtime explain contract。
- 不重做 structured form/document 路线。
- 不提前实现 `weak-signal uncertainty contract`，除非 narrative-evidence 的分析已经明确把它逼成 immediate blocker。

## 4. Current Context

- 当前已验证的 source shapes：
  - synthetic facts
  - structured feed normalization
  - structured form-like document extraction
- 这些成功案例的共同点：
  - source 边界清楚
  - source-to-fact mapping 相对 deterministic
  - provenance 至少可以靠 field/record identity 保持诚实

free-text narrative 与前两条路不同的地方在于：

- source 里可能同时包含：
  - explicit facts
  - implied facts
  - time order hints
  - uncertainty or modality language
- 同一段文本可能被不同 extraction strategy 映射为不同 fact sets
- 若没有更细粒度 provenance，explain 很容易从 “系统抽取了这个意思” 滑到 “系统知道这是事实”

因此 narrative-evidence 的价值，不是再多一个 source shape，而是：

- 它最可能第一次真正逼出 source-provenance / extraction-boundary / uncertainty 的真实 blocker。

## 5. Proposed Shape

### 5.1 Comparison Frame

本蓝图比较两条近端路线：

- `Route A: single-note free-text extraction`
  - 单条短 narrative note，单次 extraction，单文档内完成
- `Route B: multi-note narrative synthesis`
  - 多条 notes / 多时点记录，跨 note 聚合或时间顺序解释

比较维度：

- first-round implementation fit
- provenance honesty 是否可在现有 substrate 下表达
- extraction ambiguity level
- 是否立即逼出 snippet/span、uncertainty、或 T2 sequence/state semantics

### 5.2 Route A: Single-Note Free-Text Extraction

这条路线把 source 收窄为：

- 单条短 narrative note
- 单文档内 extraction
- 不要求跨 note 汇总

例如：

- investigator note
- operator handoff note
- clinical short note
- incident summary paragraph

它的优点：

- 比 structured form 明显更接近自然语言
- 但仍把问题控制在：
  - 单个 source object
  - 单次 extraction
  - 单文档 provenance
- 更适合 first-round 验证：
  - excerpt/snippet-level provenance 是否已成 blocker
  - extraction helper 是否还能保持 boundary honesty
  - mild ambiguity 是否已经足以逼出 uncertainty semantics

它真正测试的新问题是：

- 没有 span/snippet 时，document_id 是否还够
- extraction 结果如果只是 “best-effort interpretation”，当前 explain 是否已经开始不诚实
- 轻度 narrative ambiguity 会不会把 `U2` 从 deferred 变成 blocker

### 5.3 Route B: Multi-Note Narrative Synthesis

这条路线直接把 source 设为多个 narrative notes，例如：

- multiple investigator notes
- sequential clinical notes
- operator logs across shifts

它的价值很高，但 first-round 风险更大：

- provenance 从 “哪个 document” 变成 “哪一段、哪一条 note、哪个时间点”
- extraction ambiguity 与 cross-note interpretation 会立刻混在一起
- 一旦 notes 之间含有时间顺序或 evolving state，问题还会快速拖进 `T2`

对于当前阶段，这条路线的主要风险是：

- 它很可能让首个 free-text slice 同时变成：
  - snippet/span provenance contract
  - extraction-boundary contract
  - uncertainty contract
  - T2 sequence/state contract

这会让 first-round narrative-evidence slice 失去聚焦。

### 5.4 Adopted Recommendation

adopted recommendation：

- 近端优先 `Route A`
  - single-note free-text extraction
- `Route B` 保持后置
  - 作为 narrative-synthesis / multi-note line

原因：

1. 它是从 form-like document 往真正 narrative evidence 过渡的最小增量，而不是一次打开所有难题。
2. 它最适合 first-round 判断：
   - `document_id` 是否还够
   - snippet/span provenance 是否已成 blocker
   - extraction-step ambiguity 是否已逼出 uncertainty contract
3. 它更容易把失败单一化归因到：
   - snippet/span provenance gap
   - extraction-boundary contract gap
   - extraction uncertainty gap

### 5.5 Adopted Gate Answers

在 opening first implementation blueprint 之前，本 anchoring 已收敛出三条 adopted gate answers：

1. `snippet/span provenance`
   - single-note free-text extraction first-round **不需要** snippet/span provenance contract。
   - 对于单条短 note，`note_id` / `document_id` 仍足以支撑 first-round provenance honesty。
   - test-scope helper 可以输出 best-effort excerpt/quote mapping 作为 side output，但不需要冻结成 runtime/audit contract。
   - snippet/span provenance 继续后置；只有当单条 note 已长到 `document_id` 无法让 consumer 手动定位信息来源时，它才更可能成为 blocker。
2. `uncertainty contract`
   - extraction ambiguity first-round **还不是** immediate uncertainty-contract blocker。
   - single-note walkthrough 仍可使用：
     - deterministic best-effort interpretation
     - 或 explicit skip/unsupported
   - 只要 explain / narrative / NL 不把 best-effort interpretation 误说成确定性事实，这仍属于诚实边界内的 placeholder。
   - 只有当 walkthrough 暴露出“mechanically correct but semantically misleading”的 explain wording 时，`weak-signal uncertainty` 才应被拉前为具体 follow-on gap。
3. `walkthrough vs durable extraction helper`
   - first-round 仍应保持为 **walkthrough/regression**。
   - extraction helper 与 optional materialization helper 可保持 test scope，不需要 durable extraction/provenance API。
   - 只有当 walkthrough 暴露出 extraction 必须被 replay、audit-versioned、或 source-boundary 无法仅靠 test-scope helper 诚实表达时，才应拆出 durable extraction contract blueprint。

因此，本 anchoring 的 adopted next-slice recommendation 直接是：

- `single-note-narrative-extraction-walkthrough`

而不是先开 snippet/span provenance、uncertainty、或 durable extraction gap blueprint。

## 6. Boundaries And Invariants

- 必须优先选择 free-text narrative 的最小增量路线，不得一上来就混入 multi-note synthesis。
- 不得把本蓝图扩成通用 OCR/LLM/provenance framework 设计。
- 若发现 gap，必须单一化命名，不得在一个蓝图里同时打开 snippet provenance、uncertainty、T2 三个问题。
- 不得回到 structured form 已验证过的问题。

## 7. Acceptance

- [x] 两条 free-text narrative 路线已被明确比较
- [x] first-round 推荐路线已 adopted，并说明为什么它比另一条更适合作为 near-term vertical slice
- [x] opening implementation 之前必须回答的 gate 已明确
- [x] 若已有 adopted conclusion，下一条 blueprint 的类型（walkthrough or gap）已被明确命名

## 8. Implementation Plan

1. 收敛 free-text narrative 的最小比较框架，避免问题膨胀成 OCR/LLM pipeline 设计。
2. 判断哪条路线最能补齐新的 provenance / extraction / uncertainty 压力，而不把 first-round 变成多问题混切。
3. 形成 adopted next-slice recommendation，并在 outcome 中记录 deferred route。

## 9. Docs To Update

- 默认无；若 adopted conclusion 直接冻结新的 durable boundary，再补对应模块 docs

## 10. Outcome / Deviations

- adopted first-route：
  - `Route A: single-note free-text extraction`
- opening gate answers：
  - snippet/span provenance：first-round 不需要 snippet/span contract；单条短 note 仍可由 `note_id` / `document_id` 提供 source-level honesty，best-effort excerpt/quote mapping 仅保留在 test-scope helper side output。
  - uncertainty contract：first-round 仍可用 deterministic best-effort interpretation 或 explicit skip/unsupported 做 walkthrough；只要 explain wording 不把 interpretation 误说成 certainty，就不构成立即 blocker。
  - implementation shape：first-round 仍是 walkthrough/regression，helper 保持 test scope；只有当 replay/audit/versioning 或 extraction-boundary honesty 无法满足时，才再拆 durable extraction contract。
- next blueprint：
  - `single-note-narrative-extraction-walkthrough`
- deferred route：
  - `Route B: multi-note narrative synthesis`
  - snippet/span provenance contract
  - extraction uncertainty contract
  - durable extraction/provenance helper API
- 归档说明：
  - 本切片是纯 analysis/anchoring 蓝图；gate 收敛后直接归档，不涉及代码、测试或模块 docs 改动。
