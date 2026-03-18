# Task Blueprint: Multi-Note Narrative Synthesis Anchoring

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
  - [2026-03-18_free-text-narrative-evidence-anchoring.md](../archive/2026-03-18_free-text-narrative-evidence-anchoring.md)
  - [2026-03-18_single-note-narrative-extraction-walkthrough.md](../archive/2026-03-18_single-note-narrative-extraction-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_multi-note-narrative-synthesis-anchoring.audit.md](./2026-03-18_multi-note-narrative-synthesis-anchoring.audit.md)

## 1. Problem

`single-note-narrative-extraction-walkthrough` 已证明：

- free-text source
- extracted facts
- materialized helper outputs
- downstream rule run

可以在现有 substrate 下形成一条诚实的
`note -> extracted facts -> materialized facts -> rule -> explain` 链。

因此 free-text line 的下一个真正压力点，已经不是更复杂的单 note，而是 **multi-note narrative synthesis**：

- source 从单个 note 变成多个 notes
- extracted facts 不再只是 “来自这条 note”，而会出现跨 note 的关系
- 同一结论可能依赖：
  - cross-note correlation
  - time ordering
  - interpretation aggregation

这意味着下一步最值得回答的问题是：

- multi-note synthesis 是否仍能在现有 substrate 下保持诚实边界
- 还是第一次真正逼出：
  - snippet/span provenance contract
  - extraction uncertainty contract
  - T2 sequence/state semantics
  - 或更强的 source identity / lineage requirement

## 2. Goals

- 为 multi-note narrative evidence 选出 first meaningful near-term cut，而不是泛化设计 narrative ingestion/synthesis pipeline。
- 比较至少两条 multi-note 路线，并判断哪条最适合作为 first-round pressure test。
- 明确 multi-note 线最可能逼出的 primary blocker 是什么：
  - cross-note provenance granularity
  - extraction uncertainty aggregation
  - T2 sequence/state semantics
  - 或 first-class source/linkage contract
- 产出 adopted next-slice recommendation，而不是直接进入实现。

## 3. Non-goals

- 不实现 OCR、LLM parsing、embedding retrieval 或 production synthesis pipeline。
- 不在本蓝图中设计完整 snippet/span API。
- 不新增新的 runtime explain contract。
- 不重做 single-note narrative 路线。
- 不提前实现 `T2`、`judgment contract`、或 `weak-signal uncertainty contract`，除非 multi-note 分析已经明确把它们逼成 immediate blocker。

## 4. Current Context

- 当前已验证的 source shapes：
  - structured feed normalization
  - structured form-like document extraction
  - single-note free-text extraction
- 这些成功案例的共同点：
  - source object 边界明确
  - extraction 仍能被保持在 single-source, single-step 的诚实范围内
  - provenance 至少还能依赖 record/document/note identity

multi-note narrative 与 single-note 不同的地方在于：

- source 里可能出现来自不同 note 的 overlapping / conflicting evidence
- 同一结论可能需要组合多个 notes 的片段或 interpretation
- notes 之间可能存在时间顺序或 evolving state

因此 multi-note line 的价值，不是“再加一个 source 数量”，而是：

- 它最可能第一次真正逼出 cross-note provenance、interpretation aggregation、或 sequence/state 的真实 blocker。

## 5. Proposed Shape

### 5.1 Comparison Frame

本蓝图比较两条近端路线：

- `Route A: correlated multi-note review`
  - 多条 notes 指向同一 account/case，但只要求 correlation，不要求时间顺序语义
- `Route B: temporal note progression`
  - 多条 notes 存在明确先后关系，结论依赖 note 的 time ordering 或 evolving state

比较维度：

- first-round implementation fit
- provenance honesty 是否可在现有 substrate 下表达
- cross-note ambiguity / interpretation aggregation level
- 是否立即逼出 snippet/span、uncertainty、或 T2 sequence/state semantics

### 5.2 Route A: Correlated Multi-Note Review

这条路线把 source 收窄为：

- 多条短 notes
- notes 之间共享一个 account/case target
- 允许跨 note 相关联，但不要求时间顺序本身成为规则语义

例如：

- multiple investigator notes about one account
- multiple operator handoff notes about one incident
- multiple clinical comments about one patient, but only as correlated evidence set

它的优点：

- 比 single-note 明显更接近 narrative synthesis
- 但仍把问题控制在：
  - 多 source objects
  - cross-note correlation
  - 无强制 time-order semantics
- 更适合 first-round 验证：
  - note identity 是否还够
  - excerpt/snippet-level provenance 是否已成 blocker
  - cross-note interpretation aggregation 是否已经足以逼出 uncertainty contract

它真正测试的新问题是：

- 没有 snippet/span 时，multiple note_ids 是否还够
- helper 若把多个 note 的弱 signals 合成一条 support fact，当前 explain 是否已经开始不诚实
- cross-note aggregation 会不会把 `U2` 从 deferred 变成 blocker

### 5.3 Route B: Temporal Note Progression

这条路线直接把 source 设为带顺序的多条 notes，例如：

- shift-by-shift operator notes
- sequential clinical progress notes
- investigator notes with evolving escalation state

它的价值更高，但 first-round 风险也更大：

- provenance 从 “哪个 note” 快速变成 “哪个 note 的哪段、在什么时点”
- interpretation aggregation 与时间顺序语义会立刻混在一起
- 一旦结论依赖 progression / deterioration / escalation across time，问题会快速拖进 `T2`

对于当前阶段，这条路线的主要风险是：

- 它很可能让首个 multi-note slice 同时变成：
  - cross-note provenance contract
  - extraction uncertainty contract
  - T2 sequence/state contract
  - source/linkage contract

这会让 first-round multi-note slice 失去聚焦。

### 5.4 Adopted Recommendation

adopted recommendation：

- 近端优先 `Route A`
  - correlated multi-note review
- `Route B` 保持后置
  - 作为 temporal note progression / sequence line

原因：

1. 它是从 single-note narrative 往真正 synthesis 过渡的最小增量，而不是一次打开所有时序难题。
2. 它最适合 first-round 判断：
   - multiple note identifiers 是否还够
   - cross-note provenance granularity 是否已成 blocker
   - interpretation aggregation 是否已逼出 uncertainty contract
3. 它更容易把失败单一化归因到：
   - snippet/span provenance gap
   - extraction uncertainty gap
   - source/linkage gap

### 5.5 Adopted Gate Answers

在 opening first implementation blueprint 之前，本 anchoring 已收敛出四条 adopted gate answers：

1. `snippet/span provenance`
   - correlated multi-note first-round **不需要** snippet/span provenance contract。
   - multiple notes 与 single-note 的差异，在 first-round 是 note identity 的数量，而不是 note 内部定位的精度。
   - 只要每条 extracted fact 仍携带它来自的 `note_id`，reader 就能追溯到具体 source object。
   - test-scope helper 可输出 per-note excerpt mapping 作为 side output，但不需要冻结成 runtime/audit contract。
2. `uncertainty contract`
   - cross-note interpretation aggregation first-round **还不是** immediate uncertainty-contract blocker。
   - 在 correlated review 场景下，aggregation 可以先收敛为：
     - 每条 note 独立 extraction
     - 然后由 helper 做 deterministic aggregation / union / dedup
   - 真正的 uncertainty pressure来自 conflicting evidence across notes；first-round walkthrough 可通过 fixture 设计回避冲突，或以 explicit skip/conflict meta 处理。
   - 只有当 walkthrough 暴露出 explain 无法诚实表达这种 best-effort aggregation 时，`weak-signal uncertainty` 才应被拉前为具体 follow-on gap。
3. `walkthrough vs durable synthesis helper`
   - first-round 仍应保持为 **walkthrough/regression**。
   - extraction helper 的 interface 只是从 single note 扩展成 multi-note list，materialization helper 也只是消费 multi-note extracted facts；这仍属于 test-scope helper 的自然扩展，而不是 durable API 的刚需。
   - stronger source/linkage 或 durable synthesis helper 继续后置；只有当 walkthrough 证明 test-scope helper 已无法诚实表达 note 之间的关系时，才再拆出 contract blueprint。
4. `temporal ordering / T2`
   - first-round multi-note **可以继续后置 temporal ordering**，不必直接进入 `T2`。
   - correlated review 路线允许 note 自带 timestamp metadata，但规则结论不依赖 notes 的先后顺序。
   - 只有当场景要求 progression / deterioration / escalation across notes 才应进入 `Route B` 和 `T2`。

因此，本 anchoring 的 adopted next-slice recommendation 直接是：

- `correlated-multi-note-review-walkthrough`

而不是先开 snippet/span provenance、extraction uncertainty、source/linkage、或 `T2` gap blueprint。

## 6. Boundaries And Invariants

- 必须优先选择 multi-note narrative 的最小增量路线，不得一上来就混入 temporal progression。
- 不得把本蓝图扩成通用 OCR/LLM/provenance/synthesis framework 设计。
- 若发现 gap，必须单一化命名，不得在一个蓝图里同时打开 snippet provenance、uncertainty、T2、source-linkage 四个问题。
- 不得回到 single-note 已验证过的问题。

## 7. Acceptance

- [x] 两条 multi-note narrative 路线已被明确比较
- [x] first-round 推荐路线已 adopted，并说明为什么它比另一条更适合作为 near-term vertical slice
- [x] opening implementation 之前必须回答的 gate 已明确
- [x] 若已有 adopted conclusion，下一条 blueprint 的类型（walkthrough or gap）已被明确命名

## 8. Implementation Plan

1. 收敛 multi-note narrative 的最小比较框架，避免问题膨胀成 synthesis platform 设计。
2. 判断哪条路线最能补齐新的 provenance / extraction aggregation / sequence 压力，而不把 first-round 变成多问题混切。
3. 形成 adopted next-slice recommendation，并在 outcome 中记录 deferred route。

## 9. Docs To Update

- 默认无；若 adopted conclusion 直接冻结新的 durable boundary，再补对应模块 docs

## 10. Outcome / Deviations

- adopted first-route：
  - `Route A: correlated multi-note review`
- opening gate answers：
  - snippet/span provenance：first-round 不需要 snippet/span contract；multiple notes 只增加 source object 数量，不增加 note 内部定位的刚性需求，per-note excerpt mapping 仍可保留在 test-scope side output。
  - uncertainty contract：first-round 仍可用 deterministic extraction + best-effort aggregation/union/dedup 做 walkthrough；conflicting-evidence semantics 和更强 uncertainty 继续后置。
  - implementation shape：first-round 仍是 walkthrough/regression，multi-note extraction/materialization helper 保持 test scope；只有当 note 关系无法被诚实表达时，才再拆 stronger source/linkage or durable synthesis contract。
  - temporal ordering：first-round 可继续后置，不进入 `T2`；notes 可带 timestamp metadata，但规则结论不依赖 ordering semantics。
- next blueprint：
  - `correlated-multi-note-review-walkthrough`
- deferred route：
  - `Route B: temporal note progression`
  - snippet/span provenance contract
  - extraction uncertainty contract
  - stronger source/linkage contract
  - durable synthesis helper API
- 归档说明：
  - 本切片是纯 analysis/anchoring 蓝图；gate 收敛后直接归档，不涉及代码、测试或模块 docs 改动。
