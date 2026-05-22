# Task Blueprint: AML Transaction Feed Normalization Anchoring

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_aml-case-review-walkthrough.md](../archive/2026-03-18_aml-case-review-walkthrough.md)
  - [2026-03-18_aml-trigger-walkthrough.md](../archive/2026-03-18_aml-trigger-walkthrough.md)
  - [2026-03-18_aml-aggregation-materialization-walkthrough.md](../archive/2026-03-18_aml-aggregation-materialization-walkthrough.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
- Audit Log:
  - [2026-03-18_aml-transaction-feed-normalization-anchoring.audit.md](./2026-03-18_aml-transaction-feed-normalization-anchoring.audit.md)

## 1. Problem

四条场景线已经把当前 `runtime + explain + audit` 中游主轴压到了稳定停点，但
`overall-system-blueprint` 上游的 `Source / Ingestion / Normalize / Semantic Integration`
仍然基本空白。

继续新增 walkthrough 或 explain surface 的边际价值已经明显下降；下一步更值得回答的问题是：

- 第一条 upstream vertical slice 应该长什么样
- 它应优先验证哪个 source shape
- 它如何把 raw source evidence、normalized facts、materialized helper outputs 与现有 explain stack 连起来

这个蓝图不是立即做 ingestion 工程，而是为第一条 upstream 实现切片收敛方向。

## 2. Goals

- 为第一条 upstream slice 选出一个近端场景与边界，而不是泛化设计整个平台。
- 比较至少两条候选路线，并明确哪条最适合 first-round：
  - structured transaction feed normalization
  - document/narrative evidence extraction
- 明确第一轮要验证的最小链路：
  - raw source record
  - normalized ledger facts
  - materialized helper outputs
  - existing rule_run explain delivery
- 判断第一轮是否可以继续复用现有 runtime/audit contracts，还是先要开新的上游 contract blueprint。

## 3. Non-goals

- 不实现完整 ingestion framework。
- 不引入新的 unstructured extraction / OCR / LLM pipeline。
- 不新增新的 runtime explain contract。
- 不在本蓝图中实现 durable source-storage API。
- 不重开 `T2` / judgment / weak-signal uncertainty 语义问题，除非它们被 upstream 问题直接逼成 blocker。

## 4. Current Context

- 当前系统在 synthetic facts 上已经有稳定的五层 explain delivery：
  - raw
  - summary
  - narrative
  - NL
  - audit/static proof-entry
- `AML` 线已经证明：
  - case review 可行
  - trigger 可行
  - aggregation materialization 路线可行
- 但这些都建立在 fact 已经写进 ledger 的前提下；系统还没有回答：
  - source record 进来之后如何 normalize
  - helper output 与 source evidence 的最小可追溯边界该如何形成

当前最现实的两个 upstream 候选是：

1. `Structured Transaction Feed`
   - 例如 raw AML transaction events / timestamps / counterparties / device linkage
   - 优点：结构稳定、无需抽取、最适合 first-round vertical slice
2. `Document / Narrative Evidence Extract`
   - 例如 requirement text / case note / operator log 抽取成 facts
   - 优点：更接近真实 evidence ingestion
   - 缺点：会立刻把问题拖进 extraction correctness、text ambiguity、LLM/OCR 边界

## 5. Proposed Shape

### 5.1 Comparison Frame

本蓝图比较两条近端路线：

- `Route A: structured transaction feed normalization`
- `Route B: document/narrative evidence extraction`

比较维度：

- first-round implementation fit
- 对现有 runtime/audit contracts 的复用程度
- source-to-fact honesty 是否可验证
- 是否会过早把问题拖进新的 extraction or semantics blocker

### 5.2 Route A: Structured Transaction Feed Normalization

第一轮以结构化 transaction feed 作为 source，最小链路是：

- raw feed record
- normalized transaction facts
- materialized helper outputs
  - 例如 windowed signal / threshold score
- downstream trigger rule run
- existing explain delivery

这条路线的优点：

- 与已验证的 AML trigger / aggregation walkthrough 自然衔接
- source shape 明确，不需要先解决文本抽取
- 最容易回答：
  - source evidence 到 normalized facts 的边界是否清晰
  - helper output 与 downstream rule consumption 是否仍然 explain-honest

它真正测试的新问题不是 rule semantics，而是：

- raw source record 是否需要 first-class durable identity
- normalized fact 与 materialized helper output 是否需要显式 lineage hook
- audit/static 是否足以让 reader 从 helper result 回看 source record

### 5.3 Route B: Document / Narrative Evidence Extract

这条路线会把 source 直接设为半结构化或非结构化文档，例如：

- requirement text
- case note
- operator log

它的价值在于更接近真实 evidence ingestion，但 first-round 代价更高：

- 需要先定义 extraction boundary
- 需要处理 text ambiguity
- 很容易把“source ingestion”与“semantic interpretation correctness”混成一个问题

对于当前阶段，这条路线的问题不是不重要，而是它会过早地把首个上游切片变成：

- extraction contract
- uncertainty of extraction
- potentially LLM/OCR provenance

这会遮蔽我们真正还没验证的更基础问题：

- structured source 到 normalized facts 的最小诚实链条

### 5.4 Adopted Recommendation

adopted recommendation：

- 近端优先 `Route A`
  - structured transaction feed normalization
- `Route B` 保持后置
  - 作为将来 document-evidence ingestion 的单独线

原因：

1. 它最适合补齐 `overall-system-blueprint` 当前最薄的上游层，而不会立刻把问题扩成 extraction platform
2. 它能直接复用已完成的 AML materialization / trigger walkthrough，形成最小 vertical slice
3. 它更容易把失败单一化归因到：
   - source identity / lineage gap
   - normalization contract gap
   - helper materialization boundary gap

### 5.5 Adopted Gate Answers

在 opening first implementation blueprint 之前，本 anchoring 已经收敛出三条 adopted gate answers：

1. `source-record identity`
   - first-round **不需要** first-class source-record identity。
   - assertion-level drill-down 已足以覆盖 structured transaction feed 的近端场景，因为 transaction source record 到 normalized fact 的映射大概率是 `1:1` 或 `1:few`。
   - source-record identity 继续后置；只有当系统进入多源归并、batch-import dedup、或 “同一条 source record 产出大量 normalized facts 且 consumer 需要回看原始 source object” 时，它才更可能变成 blocker。
2. `lineage contract between normalized facts and helper outputs`
   - first-round **不需要**新增显式 lineage contract。
   - 现有 assertion graph + audit package 对当前阶段已经足够：normalized facts 仍是 ordinary facts，helper outputs 也是 ordinary facts，downstream rule consumption 的 honesty 边界已由 AML aggregation materialization walkthrough 证明可接受。
   - 显式 lineage hook 继续后置；只有当 helper-chain 变长、多级 materialization 出现、或 consumer 需要从 helper output 一键回溯到其消费过的 normalized fact set 时，它才更可能成为单独 capability gap。
3. `walkthrough vs durable ingest/helper`
   - first-round 仍应是 **walkthrough/regression**，而不是 durable ingest API。
   - 但这条 walkthrough 必须显式包含一个 synthetic normalize step：
     - 输入 raw structured transaction record（例如 test-scope dict/JSON）
     - 产出 normalized facts 并写入 ledger
   - 这样做的目的不是冻结 ingest API，而是验证 normalize output shape 是否已经稳定到足以被 downstream materialization / trigger walkthrough 直接消费。
   - 只有当 synthetic normalize step 暴露出 output shape 不稳定、identity 语义不足或 lineage 边界不诚实，才应再拆出 normalize contract gap blueprint。

因此，本 anchoring 的 adopted next-slice recommendation 直接是：

- `aml-transaction-feed-materialization-walkthrough`

而不是先开 source-identity / lineage / durable-helper gap blueprint。

## 6. Boundaries And Invariants

- 必须优先回答上游 source/normalize 问题，而不是继续厚 runtime explain layer。
- 必须保持 first-round 为 structured source；不得在本轮把文档抽取混入同一切片。
- 若发现 gap，必须单一化命名，不得在 anchoring 中同时打开 source identity、lineage、helper API 三个问题。
- 不得把这个蓝图写成泛 ingestion platform 设计。

## 7. Acceptance

- [x] 两条 upstream 候选路线已被明确比较
- [x] first-round 推荐路线已 adopted，并说明为什么它比另一条更适合作为近端 vertical slice
- [x] opening implementation 之前必须回答的 gate 已明确
- [x] 若已有 adopted conclusion，下一条 blueprint 的类型（walkthrough or gap）已被明确命名

## 8. Implementation Plan

1. 收敛上游的最小比较框架，避免把问题写成“泛 ingestion 架构”。
2. 判断哪条路线最能补齐当前最薄的系统层，同时不把 scope 扩到 extraction correctness。
3. 形成 adopted next-slice recommendation，并在 outcome 中记录 deferred route。

## 9. Docs To Update

- 默认无；如果 adopted conclusion 直接冻结了新的 durable boundary，再补对应模块 docs

## 10. Outcome / Deviations

- adopted first-route：
  - `Route A: structured transaction feed normalization`
- opening gate answers：
  - source-record identity：first-round assertion-level drill-down 已足够，first-class source identity 继续后置。
  - lineage contract：first-round 复用现有 assertion graph + audit package 即可，显式 lineage hook 继续后置。
  - implementation shape：first-round 应是 walkthrough/regression，但 walkthrough 内必须显式包含 synthetic normalize step，而不是直接从手写 facts 开始。
- next blueprint：
  - `aml-transaction-feed-materialization-walkthrough`
- deferred route：
  - `Route B: document / narrative evidence extraction`
  - source-record identity enhancement
  - explicit normalized-to-helper lineage contract
  - durable ingest/materialization helper API
- 归档说明：
  - 本切片是纯 analysis/anchoring 蓝图；gate 收敛后直接归档，不涉及代码、测试或模块 docs 改动。
