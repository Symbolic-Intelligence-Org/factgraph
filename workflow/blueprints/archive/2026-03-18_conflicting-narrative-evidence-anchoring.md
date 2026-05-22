# Task Blueprint: Conflicting Narrative Evidence Anchoring

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
  - [2026-03-18_free-text-narrative-evidence-anchoring.md](../archive/2026-03-18_free-text-narrative-evidence-anchoring.md)
  - [2026-03-18_multi-note-narrative-synthesis-anchoring.md](../archive/2026-03-18_multi-note-narrative-synthesis-anchoring.md)
  - [2026-03-18_correlated-multi-note-review-walkthrough.md](../archive/2026-03-18_correlated-multi-note-review-walkthrough.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_conflicting-narrative-evidence-anchoring.audit.md](./2026-03-18_conflicting-narrative-evidence-anchoring.audit.md)

## 1. Problem

`correlated-multi-note-review-walkthrough` 已证明：

- 多条 notes
- extracted facts
- aggregated/materialized helper outputs
- downstream rule run

仍能在现有 substrate 下形成一条诚实的
`notes -> extracted facts -> aggregated facts -> rule -> explain` 链。

但这条成功有一个关键前提：

- notes 之间 **不冲突**
- helper aggregation 仍可以 deterministic union/dedup 完成

因此 narrative line 的下一个真正压力点，已经不是更多相关 notes，而是 **conflicting narrative evidence**：

- note A 和 note B 可能给出相互张力很大的描述
- helper 不能再只做 union/dedup
- 系统必须决定：
  - 保留冲突
  - 跳过冲突
  - 还是综合成单一判断

这意味着下一步最值得回答的问题是：

- conflicting evidence 是否仍能在现有 substrate 下保持诚实边界
- 还是第一次真正逼出：
  - source-linkage contract
  - extraction uncertainty contract
  - judgment contract
  - 或更细的 provenance boundary

## 2. Goals

- 为 conflicting narrative evidence 选出 first meaningful near-term cut，而不是泛化设计 conflict-resolution framework。
- 比较至少两条 conflict-handling 路线，并判断哪条最适合作为 first-round pressure test。
- 明确 conflicting-evidence 线最可能逼出的 primary blocker 是什么：
  - source-linkage / conflict visibility
  - extraction uncertainty / conflict handling
  - judgment / resolution contract
- 产出 adopted next-slice recommendation，而不是直接进入实现。

## 3. Non-goals

- 不实现通用 contradiction-resolution engine。
- 不在本蓝图中设计完整 source-linkage API。
- 不新增新的 runtime explain contract。
- 不回头重做 non-conflicting multi-note 路线。
- 不提前实现 `T2`，除非 conflicting-evidence 分析已经明确把它逼成 immediate blocker。

## 4. Current Context

- 当前已验证的 narrative source shapes：
  - single-note free-text extraction
  - correlated multi-note review
- 这些成功案例的共同点：
  - evidence 可被保持为 non-conflicting
  - helper aggregation 仍可 deterministic union/dedup
  - explanation honesty 主要依赖 source identity + negative wording constraints

conflicting narrative evidence 与上述路线不同的地方在于：

- extracted facts 可能彼此矛盾
- helper 不再能只做 mechanical merge
- 结果如果仍要落成单一 support fact，就需要解释：
  - 为什么保留 A 而不是 B
  - 为什么两者都被跳过
  - 或为什么需要一个更高层 judgment object

因此 conflicting-evidence line 的价值，不是“再加一种 note 关系”，而是：

- 它最可能第一次真正逼出 deferred gaps 之间的优先级关系。

## 5. Proposed Shape

### 5.1 Comparison Frame

本蓝图比较两条近端路线：

- `Route A: explicit conflict retention`
  - 保留冲突 extracted facts，并要求 delivery 层诚实显示 conflicting evidence
- `Route B: helper-side conflict resolution`
  - helper 在 test scope 内先决定保留/跳过/合并冲突，再把结果喂给 downstream rule

比较维度：

- first-round implementation fit
- provenance honesty 是否可在现有 substrate 下表达
- conflict visibility / traceability
- 是否立即逼出 source-linkage、uncertainty、或 judgment contract

### 5.2 Route A: Explicit Conflict Retention

这条路线把 source 收窄为：

- `>=2` notes
- 至少一对 extracted facts 明确冲突
- walkthrough 不要求系统解决冲突，只要求系统保留冲突并让 reader 看见它

例如：

- NOTE-A: beneficiary jurisdiction is low-risk
- NOTE-B: beneficiary jurisdiction is high-risk

它的优点：

- 最小化 first-round scope
- 不要求 helper 先完成冲突解决
- 更适合 first-round 验证：
  - note-level provenance 是否仍足够
  - conflicting facts 能否在当前 explain/audit surface 中被诚实保留
  - source-linkage 是否已成 blocker

它真正测试的新问题是：

- 只靠 assertion detail 和 rule trace，reader 是否已经能理解 “这里有冲突”
- 如果 rule 不能消费 conflicting facts，是否必须先出现新的 conflict-carrier 或 linkage surface

### 5.3 Route B: Helper-Side Conflict Resolution

这条路线直接让 helper 在 extraction/materialization 时处理冲突，例如：

- choose one side
- skip conflicting pair
- emit a single resolved downstream support fact

它的价值更高，但 first-round 风险也更大：

- 一旦 helper 先解决冲突，就很容易立即引出：
  - 为什么选这一边
  - 为什么丢弃另一边
  - 这是不是 uncertainty semantics
  - 这是不是 judgment contract

对于当前阶段，这条路线的主要风险是：

- 它很可能让首个 conflict slice 同时变成：
  - source-linkage contract
  - extraction uncertainty contract
  - judgment contract

这会让 first-round conflicting-evidence slice 失去聚焦。

### 5.4 Adopted Recommendation

adopted recommendation：

- 近端优先 `Route A`
  - explicit conflict retention
- `Route B` 保持后置
  - 作为 conflict-resolution / resolution-policy line

原因：

1. 它是从 correlated multi-note 往真正 conflicting evidence 过渡的最小增量，而不是一上来就设计 resolution semantics。
2. 它最适合 first-round 判断：
   - conflicting facts 是否还能在现有 surface 中被诚实保留
   - source-linkage 是否已成 blocker
   - 当前 explain stack 是否已经需要 conflict-specific contract
3. 它更容易把失败单一化归因到：
   - source-linkage gap
   - conflict-visibility / extraction-boundary gap
   - judgment/resolution gap

### 5.5 Adopted Gate Answers

在 opening first implementation blueprint 之前，本 anchoring 已收敛出四条 adopted gate answers：

1. `conflict retention vs resolution`
   - first-round **可以只做 explicit conflict retention**，不需要先做 helper-side resolution。
   - helper 只负责 extraction，并将冲突的 extracted facts 全部写入 ledger。
   - downstream rule 若只消费满足 where 条件的一侧，这属于现有 matching semantics 的自然结果，而不是 helper/judgment resolution。
2. `source-linkage immediate blocker`
   - 保留冲突的情况下，现有 surface **仍然足够**让 reader 看清 conflicting facts 的 provenance。
   - 只要 conflicting extracted facts 各自带有 `note_id` / `note_ref`，reader 就能通过 assertion detail 看见：
     - 相同 predicate family
     - 相同 account/case target
     - 不同值
     - 不同 note provenance
   - source-linkage 继续后置；只有当 walkthrough 证明这种“被动可发现”已经不够诚实时，它才变成 concrete blocker。
3. `walkthrough vs durable conflict helper`
   - first-round 仍应保持为 **walkthrough/regression**。
   - extraction helper 的 interface 不变，只是 fixture 中出现 conflicting note content。
   - materialization helper 可以在 test-scope meta 中显式记录 conflict detected / retained both，但不需要 durable conflict API。
4. `judgment contract`
   - `judgment contract` 继续后置，只要 first-round 不做 automated resolution。
   - 在 `Route A` 下，系统没有做 “choose A over B” 的 judgment；rule 只是自然绑定到满足条件的 fact。
   - 只有 `Route B` 才更可能把 judgment contract 逼成 immediate blocker。

因此，本 anchoring 的 adopted next-slice recommendation 直接是：

- `conflicting-multi-note-evidence-walkthrough`

而不是先开 source-linkage、uncertainty、或 judgment gap blueprint。

## 6. Boundaries And Invariants

- 必须优先选择 conflicting narrative 的最小增量路线，不得一上来就混入 automated resolution。
- 不得把本蓝图扩成通用 contradiction/provenance/judgment framework 设计。
- 若发现 gap，必须单一化命名，不得在一个蓝图里同时打开 source-linkage、uncertainty、judgment 三个问题。
- 不得回到 non-conflicting multi-note 已验证过的问题。

## 7. Acceptance

- [x] 两条 conflicting-evidence 路线已被明确比较
- [x] first-round 推荐路线已 adopted，并说明为什么它比另一条更适合作为 near-term vertical slice
- [x] opening implementation 之前必须回答的 gate 已明确
- [x] 若已有 adopted conclusion，下一条 blueprint 的类型（walkthrough or gap）已被明确命名

## 8. Implementation Plan

1. 收敛 conflicting narrative 的最小比较框架，避免问题膨胀成 general resolution system design。
2. 判断哪条路线最能补齐新的 conflict visibility / source-linkage / resolution pressure，而不把 first-round 变成多问题混切。
3. 形成 adopted next-slice recommendation，并在 outcome 中记录 deferred route。

## 9. Docs To Update

- 默认无；若 adopted conclusion 直接冻结新的 durable boundary，再补对应模块 docs

## 10. Outcome / Deviations

- adopted first-route：
  - `Route A: explicit conflict retention`
- opening gate answers：
  - retention vs resolution：first-round 可以只做 conflict retention，不需要 helper-side resolution。
  - source-linkage：现有 surface 仍足够；conflicting facts 只要带有各自 `note_id`，reader 就能通过 assertion detail 识别冲突，source-linkage 继续后置。
  - implementation shape：first-round 仍是 walkthrough/regression，helper 保持 test scope；durable conflict helper 继续后置。
  - judgment contract：继续后置，只要 first-round 不做 automated resolution。
- next blueprint：
  - `conflicting-multi-note-evidence-walkthrough`
- deferred route：
  - `Route B: helper-side conflict resolution`
  - source-linkage contract
  - extraction uncertainty contract
  - judgment contract
- 归档说明：
  - 本切片是纯 analysis/anchoring 蓝图；gate 收敛后直接归档，不涉及代码、测试或模块 docs 改动。
