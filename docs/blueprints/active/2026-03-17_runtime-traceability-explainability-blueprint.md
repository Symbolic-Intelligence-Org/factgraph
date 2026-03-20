# Task Blueprint: Runtime Traceability And Explainability Blueprint

- Status: draft
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/audit`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/service`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/README.md](../../references/README.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
  - [docs/blueprints/active/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
  - [docs/blueprints/archive/2026-03-17_souffle-annotation-kernel-prototype.md](../archive/2026-03-17_souffle-annotation-kernel-prototype.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/docs/04_public_contract_v1.md](../../../src/factpy_kernel/core/docs/04_public_contract_v1.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-17_runtime-traceability-explainability-blueprint.audit.md](./2026-03-17_runtime-traceability-explainability-blueprint.audit.md)

## 1. Problem

当前仓库已经分别讨论和实现了几块相关能力，但还没有一份专门蓝图来回答一个更聚焦的问题：

- `audit-log`、`proof-tree`、`graph-based` 这三类可解释性/追溯性形态，项目近期到底应如何分层和比较？
- `annotation` 在这件事里是“主要载体”“附属语义值”还是“局部 helper”？
- `CandidateSet`、`support/provenance`、`audit package`、以及可能的 proof/support graph 之间，未来是否需要一个更清晰的运行时承载模型？

当前已有材料给出了方向，但没有给出单独的讨论入口：

- 母蓝图已经提出 `audit-log -> proof-tree -> graph-based` 的优先级建议；
- annotation spike / prototype 已经证明 annotation 对某些 workload 有价值；
- 但仓库里仍缺少一份蓝图，专门比较不同 traceability / explainability 承载方式的优缺点、边界和后续实验入口。

因此，本蓝图的目标不是立即决定一种方案，而是把“运行时追溯与可解释性应该如何承载”这件事单独收口为一个可讨论、可拆解的主题。

## 2. Goals

- 建立一个专门讨论 runtime traceability / explainability 承载模型的子蓝图入口。
- 明确区分当前已存在的几种事实：
  - 现有 `audit` 与 `CandidateSet` 契约
  - 已实现的 prototype 级 annotation 摘要
  - 尚未形成独立 contract 的 proof/support graph 设想
- 比较若干可能的承载形态，而不是预先假定某一种为正确路线。
- 为后续是否要开实现型子蓝图提供判断问题，例如：
  - 是否需要 runtime-governance 级 contract 扩展
  - 是否值得引入 support/proof graph
  - annotation 是否应进入正式 runtime / audit 口径

## 3. Non-goals

- 不在本蓝图中决定“必须采用 support/proof graph first + annotation second”。
- 不在本蓝图中把 annotation 提升为唯一的解释/追溯载体。
- 不在本蓝图中修改正式 `Store.evaluate(...)`、`CandidateSet`、`audit` package、SDK 或 service 契约。
- 不在本蓝图中直接实现新的 runtime capability。
- 不把 `PyReason`、`Souffle`、`ProbLog` 任一引擎的语义假设直接写成系统真相。

## 4. Current Context

- 当前实现入口：
  - `core` 已提供 `CandidateSet`、accept、query、view projector audit 等主线能力。
  - `audit` 已作为离线审计消费层存在，读取导出的 package 做查询与静态展示。
  - `core/annotation` 当前是 internal / prototype，只覆盖 `Workload A + C` 的最小 annotation 能力。
- 当前已知约束：
  - `CandidateSet.confidence` 仍是窄字段，不等价于完整解释对象。
  - `ProjectorAudit` 目前只提供轻量统计，不是 proof/provenance contract。
  - `audit` 当前主要消费离线 package，不直接暴露 live runtime trace。
  - prototype 级 provenance 摘要已经存在，但它们仍按 workload 区分，不是统一 carrier。
  - 当前 annotation prototype 看起来更接近 workload-scoped 的 confidence/certainty propagation helper；它是否应被进一步理解为 probabilistic reasoning 的入口，仍值得单独比较，而不宜提前视为既定事实。
- 当前相关历史蓝图：
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
    - 已证明 annotation 在部分 workload 上有价值，但价值具有 workload 依赖性。
  - [docs/blueprints/archive/2026-03-17_souffle-annotation-kernel-prototype.md](../archive/2026-03-17_souffle-annotation-kernel-prototype.md)
    - 已将 A/C 的 annotation 能力沉淀为 internal prototype。
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
    - 已提出 `audit-log -> proof-tree -> graph-based` 的长期排序，但尚未展开承载模型本身。

### 4.1 Current Position After Delivery Closure

自本母蓝图打开以来，仓库已经落地了一批当时仍处于讨论阶段的 child slices。按当前代码真相，以下事项已不再属于“未来可能”：

- native `SupportArtifact` capture / readback 已存在
- `candidate_id -> support_digest/support_kind` 已存在
- `rule_run_id -> RuleTraceArtifact` explain readback 已存在
- runtime `rule_run` delivery spine 已闭环：
  - raw
  - summary
  - narrative
  - NL explain
- audit/static proof-entry 也已闭环：
  - `rule_traces/{rule_run_id}.html`
  - 离线 `rule_run_summary`
  - 离线 `rule_run_narrative`

这意味着本母蓝图里较早期的某些担忧，今天已经需要按“已完成第一阶段”来重读，尤其是：

- delivery shape 不再是空白；
- proof entry handle 不再是完全空白；
- `audit-log-first` 已不只是倾向，而是已经被一系列 child slices 与 walkthrough 验证压实的当前阶段基线。

因此，若这条母蓝图下一步继续推进，最自然的剩余方向已经不再是 proof-tree 本体，而是 tree surface 的 richer delivery / semantics：

- salience / impact
- stronger engine witness parity
- optional / missing-condition style semantics

也就是说，`result-centric / recursive evidence tree` 已从“下一子阶段”转入“当前已完成基线”。

### 4.2 Current Position After Evidence Tree Implementation (2026-03-20)

§4.1 指出的"下一子阶段"——result-centric recursive evidence tree——现已完成六轮实现并全部归档。按当前代码真相：

**已落地能力（5 个冻结合约）：**

1. **RuleRef execution substrate** (`a8e1b5d`) — 统一的 `evaluate_native_where()`，SDK/service 共享
2. **Recursive proof edges** (`f4756d9`) — `RuleRefEdge` + `SupportArtifact.rule_ref_edges`，递归子 support 展开，cycle detection + depth limit=8
3. **Winning-branch narrowing** (`13b7827`) — 每个 binding 只采纳一个 OR 分支，source-order wins，capture 侧选择
4. **Richer unresolved taxonomy** (`f649c5d`) — 4 terminal reasons × 2 node kinds × 3 owner layers
5. **Engine degraded tree shape** (`cf7f56d`) — `degraded_support` 节点，`none` ≡ `engine_no_witness_v1`
6. **Provenance-role taxonomy** (doc-and-contract promotion) — `node_kind` 正式提升为 carrier-level provenance-role taxonomy，零新字段，映射写入 core/service/audit docs；[archived blueprint](../archive/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md)
7. **Candidate evidence tree NL explain** (`9560fd2`) — tree → summary → narrative → NL，runtime/audit/static delivery matrix 已冻结
8. **Souffle partial witness delivery surface** — adapter-level witness sidecar via Datalog rewriting，`support_kind="souffle_witness_v1"`，runtime + audit + static 现已接受 witness-bearing engine support

**已落地 tree node taxonomy（完整）：**

- Native path: `candidate_result → support_section / rule_ref_section → predicate_witness_group / non_fact_check / assertion_fact / rule_ref / referenced_support / unresolved_support / recursion_boundary`
- Engine degraded path: `candidate_result → support_section → degraded_support`

**三通道交付已闭环：** runtime `explain_tree(kind="candidate")` + audit `get_candidate_evidence_tree()` + static site rendering

这意味着本母蓝图 §4.1 中预设的两阶段路线——`audit-log-first → proof-tree / support-graph-oriented`——的前两阶段现在都已完成。

**对照 Rainbird 的剩余 gap 重评估：**

以 [rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md) 为参照基线，Rainbird 比较文档中标识的主要 gap 在 evidence tree 实现后的状态如下：

| Rainbird gap | 当前状态 | 说明 |
|---|---|---|
| Result carrier / proof entry | ⚠️ native path 基本关闭；全局仍部分开放 | native path: `candidate_id → support_digest → SupportArtifact` 是真实 artifact。但 engine candidate 仍走 degraded 路径（无真实 witness artifact），且 `candidate_id → support_digest/support_kind` 的第一跳仍是 Store 实例内索引，不是 Rainbird 那种稳定 proof entry |
| Evidence tree recursive | ✅ 已关闭 | 完整递归证明、4 terminal reasons、cycle/depth 保护 |
| Structured API | ✅ 已关闭 | runtime + audit + static 三通道 |
| Audit/session trace | ✅ 已关闭 | audit package + static site |
| Visual evidence URL | ⚠️ 部分完成 | 当前 runtime 已为 `candidate_id` / `rule_run_id` 提供 session-bound live HTML permalink；audit/static 仍是 durable shareable surface，但尚无 session-less live URL |
| **Source taxonomy** | ⚠️ provenance-role 已冻结；assertion-origin 仍开放 | `node_kind → provenance role category` 映射已冻结为 carrier contract（[provenance blueprint](../archive/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md)）；更深的 assertion-origin taxonomy（direct write / derivation accept / import）deferred |
| **Salience / Impact** | ⚠️ 仍开放 | 仍在 §5.9 候选清单，依赖 certainty/weight 基础设施 |
| **Missing optional conditions** | ⚠️ 仍开放 | 依赖 rule authoring optional 语义，当前不具备 |
| **NL explain for tree** | ✅ 已关闭 | candidate evidence tree 现已具备 runtime summary / narrative / NL explain，以及 audit summary / narrative 和 static narrative block |

**下一阶段方向判断：**

本母蓝图的下一阶段不再是"补 proof-tree surface"（已完成），而是进入 tree surface 的丰富化：

1. ~~**Provenance / source taxonomy**~~ ✅ 已完成并归档 — `node_kind` 提升为 provenance-role carrier，零新字段
2. ~~**NL explain for evidence tree**~~ ✅ 已完成并归档 — candidate tree 现已具备 summary / narrative / NL 分层
3. ~~**Salience / impact breakdown**~~ ⏸️ 归属与计算时机已冻结（annotation/value-semantics 层，query-time derivation），但 implementation blocked on certainty / weight vocabulary — [decision-only archive](../archive/2026-03-20_candidate-evidence-tree-salience-impact.md)
4. **Stronger engine witness parity** — 当前已完成 Souffle partial witness 的 runtime + audit + static delivery；ProbLog、以及更强 proof-bearing engine explain 仍开放

salience / impact 的 4 条冻结结论：owner = annotation/value-semantics; compute-time = query-time; blocked on certainty/weight; no implementation slice until prerequisites exist。

剩余方向仍应以 child blueprint 逐条推进，本母蓝图保持 framing 角色。

## 5. Proposed Shape

### 5.1 Positioning

本蓝图更适合作为一个 **runtime-governance 侧的探索子蓝图**：

- 关注 runtime 结果如何被解释、追溯、导出和消费；
- 不默认把问题缩减为“增加一个 annotation 字段”；
- 也不默认把问题放大成“必须先做完整 graph engine”。

### 5.2 Candidate Design Directions To Compare

本蓝图建议至少比较以下几种方向，而不是先选定其一：

1. `CandidateSet-first`
   - 保持当前 candidate identity 为主轴；
   - 逐步丰富 support/provenance 摘要与 confidence/annotation 载体。

2. `audit-log-first`
   - 继续把 run / candidate / decision / apply event 作为主追溯链；
   - proof-tree 或 graph-based 解释作为 audit 的派生视图。

3. `proof-tree / support-graph-oriented`
   - 探索是否需要一个更显式的 proof/support object；
   - 由 candidate、annotation、audit 引用或投影到该对象。

4. `hybrid`
   - candidate identity 仍留在 runtime；
   - annotation 负责语义值；
   - audit 负责 run/session/decision 可追溯性；
   - proof/support graph 仅在需要更强 explainability 时作为补充层。

### 5.3 Questions This Blueprint Should Clarify

1. explainability 与 traceability 的最小公共需求是什么？
   - “为什么成立”
   - “依赖了什么”
   - “由哪次 run / 规则 / decision 产生”
   - “为什么强度是这个值”

2. annotation 在这条链上更像什么？
   - 候选结果的附加语义值
   - proof/support object 上的属性
   - audit package 的派生摘要
   - 或仅在特定 workload 中成立的局部 helper

3. 当前 contract 缺的究竟是哪一段？
   - `CandidateSet -> richer support summary`
   - `runtime -> audit package`
   - `audit-log -> proof-tree`
   - `proof/support graph -> UI / service delivery`

4. 哪类承载方式最适合近期对外演示，哪类适合中期内核建设？

围绕第 4 个问题，一个目前看来值得继续测试的工作性判断是：

- 在当前仓库状态下，`audit-log-first` 也许仍是近期最容易对外演示、也是最容易与现有 `audit` 基础设施对接的路径；
- `proof-tree / support-graph` 可能更像中期的 explainability differentiator；
- 但这仍更接近"当前倾向"，而不是已经冻结的路线，后续仍应以具名 reference scenario 和外部可验证材料来反复检验。

在"近期对外演示"这一问题上，一个目前尚未被蓝图收口、但影响承载模型讨论的约束是：**delivery shape**，即用户或消费方最终能摸到的是什么形态。

以 [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md) 中整理的 Rainbird evidence tree 作为对照参考（不是模板），它把同一条推理链同时以三种形态并存交付：

- `visual evidence URL`：可嵌入 case management 系统的可分享链接，从任意结论 ID 进入，展开完整推理树；
- `structured API`：开发者递归遍历 `GET /analysis/evidence/{factID}/{sessionID}`，自定义渲染；
- `NL explain`：自然语言叙述"为什么得到这个结论"，面向无形式逻辑背景的消费方（当前 Beta）。

这对本蓝图的启示不是照搬三种形态，而是：**在讨论承载模型时，如果还没有回答"哪种形态的消费方能拿到什么"，那么 carrier 和 annotation 的边界设计可能仍然是悬空的**。

因此，围绕第 4 个问题，一个值得显式加入讨论的追问是：

- 近期对外演示的 delivery shape 是否已经确定？至少需要确定"是 API-only，还是附带某种可消费的 audit/evidence 视图"；
- 如果是 audit artifact（如 requirement-scoped compliance status matrix），用户拿到的是一个结构化文档，还是一个可交互的链接或页面？
- 如果是 API 形态，`service` 层是否需要一个 `/explain/{candidate_id}` 风格的端点，返回可递归消费的 proof chain？
- NL explain 类形态（自然语言解释）是否属于近期目标，还是交由 LLM 层在 service 外部组装？

这些追问当前不要求给出答案，但如果不明确，§5.4 中关于 proof carrier 的 framing 选择（snapshot vs reference、candidate-level vs proof-level）将很难在后续讨论中收口。

基于 2026-03-18 之前已经落地的 child slices，delivery shape 的 first-round 问题现在也有了更明确的当前答案：

- structured JSON surface：已存在
- deterministic NL explain：已存在
- shareable audit/static proof-entry：已存在

因此，本母蓝图若继续向前推进，delivery shape 的下一问题不再是”有没有 consumer-facing surface”，而是：

- 是否需要一个 **tree-oriented / result-centric** surface，而不是继续停留在 `rule_run`-centric proof-entry。

**2026-03-20 更新：tree-oriented surface 现已存在。** evidence tree 六轮实现后，`candidate_evidence_tree` 是一个完整的 result-centric recursive tree surface，通过 runtime / audit / static 三通道交付。delivery shape 的下一问题现在是：

- 当前 tree node 的来源/承载语义是否需要从隐式推断（`node_kind + support_kind`）提升为正式 `source_kind` / `provenance_kind` contract？（→ provenance/source taxonomy blueprint）
- salience / impact breakdown 的数据结构是否应进入 tree carrier，还是作为 annotation layer 的派生视图？（→ §5.8 #3 归属问题）
- evidence tree 是否需要自己的 NL explain 端点，还是继续依赖 rule_run 级别的 NL explain？

### 5.4 Carrying Objects, Value Semantics, And Mapping Boundaries

本蓝图也许需要把“值语义”本身从 provenance / proof carrier 中拆开讨论，而不是默认把它们揉成一个 `confidence` 字段。

一个值得继续测试的 framing 可能是：

1. `shared proof / provenance carrier`
   - 负责表达 candidate 是如何被支持、由哪些 facts / rules / support path 得到、是否存在多条候选证明链；
   - 这一层首先回答“为什么成立 / 依赖了什么”，不急于决定数值一定代表什么。

2. `certainty-weighted reasoning`
   - 更接近 confidence / certainty propagation；
   - 可能允许“可选条件缺失但结论仍成立”“不同条件贡献不同 impact”“同一条 proof 链给出一个解释友好的 certainty breakdown”。

3. `probabilistic reasoning`
   - 若未来考虑该方向，可能需要更强的语义约束；
   - 例如多条 proof 是否独立、共享 support 如何处理、冲突证据是否抵消、Top-K 截断后的尾部如何解释。

基于这一 framing，一个仍待讨论的问题是：

- 项目近期是否更适合把 certainty-style reasoning 与 probabilistic reasoning 视为两类可并行 evaluator，它们共享 proof/provenance carrier，但不强行复用同一个未标注语义的 `confidence` 值。
- 若两者并行存在，annotation 应更像：
  - proof/provenance carrier 的一部分；
  - certainty evaluator 的输出层；
  - probabilistic evaluator 的辅助摘要；
  - 或仅在特定 workload 中作为局部解释层。

这并不预设系统一定要同时支持两种 evaluator；它只是提示，本蓝图后续也许需要把“承载对象”和“数值语义”分开比较。

若继续沿 hybrid 方向讨论，一个也许更棘手、但值得尽早澄清的问题是：proof carrier、annotation、audit trace 三者的映射边界应该如何拆分。

当前可以先保留几种待比较的 framing，而不急于冻结其中一种：

1. `run-scoped proof instance`
   - 一种可能的看法是，具体 proof 更适合作为单次 run 下的对象；
   - 因为一旦绑定 facts、rules、time context、evaluator 结果，它是否还适合跨 run 复用，可能就不再显然。

2. `proof shape / proof signature`
   - 另一种可能是，把“跨 run 相似的证明结构”与“某次 run 中的具体 proof”分开；
   - 前者更像可选的复用或去重辅助对象，后者才是 runtime traceability 真正需要引用的 carrier。

3. `audit snapshot vs audit reference`
   - audit package 也许不适合只保留 proof reference；
   - 但若直接固化完整 proof tree snapshot，又可能过早冻结 proof schema，并带来体积和演化成本；
   - 因此，一个值得比较的中间形态是：audit 中保留最小可独立消费的 proof summary snapshot，同时附带可选的 proof reference / hash / artifact pointer。

4. `candidate-level vs proof-level annotation`
   - 若 annotation 只挂在 candidate 顶层，可能会丢失局部 explainability；
   - 若 annotation 全部挂在 proof node 上，又可能让 query / service 端难以消费最终摘要；
   - 因此也许需要继续比较两层并存的形态：
     - proof-level annotation 更偏局部条件贡献、缺失但允许跳过的条件、bottleneck/support 解释；
     - candidate-level annotation 更偏聚合后的 evaluator summary、主 proof、Top-K 摘要。

这些 framing 暂时更像"设计空间中的候选拆法"，它们要回答的核心问题包括：

- 一个 proof object 是否应天然对应单次 run，而不是多个 run？
- audit 更适合消费 proof snapshot、proof ref，还是二者的组合？
- annotation 若继续保留，主挂点更应落在 candidate summary，还是 proof node / support object？
- 若未来同时存在 certainty evaluator 与 probabilistic evaluator，它们各自更自然地附着在哪一层？

5. `proof entry point identifier` 与 `support` 字段的关系

   **5a. 现有代码里已经有 proof witness 的预留槽位**

   `CandidateSet` 里有两个字段：`support_digest` 和 `support_kind`。从代码看，目前所有 `make_candidate` 的调用点（`evaluate_store`、`_builders.py`、`evaluate_dummy`）都把这两个字段填成哑值：`support_kind="none"`、`support_digest=sha256:000...`。

   这不是偶然——这两个字段是系统设计者为"proof witness 是什么"预留的槽位，只是目前还没有填充真实内容。这是整个 proof entry 设计最重要的既有基础，比新增字段更关键。

   **5b. `candidate_id` 可以作为 proof entry handle，但前提是 `support` 不再是哑值**

   `candidate_id`（`cand_v2:` 前缀）天然是 run-scoped 的 handle，已随 evaluate 结果返回，且在 accept 后继续写入 ledger meta。在合规追溯场景中，run-scoped 是正确的语义——ESA SDMR 和 AML SAR 都需要"这次 run 的具体 proof"，而非跨 run 复用的抽象结构。

   但 `candidate_id` 作为 proof entry handle 的意义，取决于 `support_digest` 是否指向真实的 proof witness：若 `support_digest` 仍是哑值，`candidate_id` 只能作为"找到这个 candidate 的 audit meta"的入口，而不能作为"展开这个 candidate 的 proof chain"的入口。两者是配套关系，不是独立选择。

   **5c. 长期正确的方向：proof witness 必须在 evaluate 时捕获，且需要 witness-capable projection**

   一个可以在此收口的方向性判断是：**proof witness 必须在 `evaluate` 时同步捕获，不能推迟到 accept 或 query 时重建**。

   理由：accept 时 ledger 状态可能已与 evaluate 时不同（新 facts 已写入）；在 accept 时重新执行 `evaluate_where` 并捕获 bindings，重建的 proof 不一定与原始 proof 一致。在合规场景中，这是不可接受的——监管方需要的是"当时为何作出这个决策"，而不是"如果现在重跑会得到什么"。

   但这里有一个关键的代码现实约束：**`evaluate_where` 目前只返回变量绑定值（`list[dict[str, Any]]`），不返回 `asrt_id`**。原因是 `project_view_facts`（`projector.py`）在把 ledger 中的 claim 投影成 `dict[pred_id, list[tuple]]` 时，已经把 `asrt_id` 剥除——where evaluator 拿到的只是纯 value 元组，完全不知道这些值来自哪条 claim。

   因此，"在 evaluate 时捕获 proof witness"不能依赖现有的 `evaluate_where` 接口；需要的是一个 **witness-capable projection 层**：在投影时，不仅输出 value 元组，还保留每个 value 元组对应的 `asrt_id`（或 claim digest）；where evaluator 或其 witness 并行通道在匹配时，能同时记录"哪条 claim 满足了哪个 `pred` 原子"。

   这个 witness 信息应被汇总成一个 `SupportArtifact` 对象，建议最小 schema：

   ```
   SupportArtifact:
     kind: "native_binding_v1" | "souffle_v1" | "problog_v1" | ...
     root_result_kind: "fact" | "entity"
     bindings: [variable binding summary per matched row]
     pred_witnesses: {pred_atom_key -> [asrt_id, ...]}   # 每个 pred 原子匹配到的 claim 身份
     non_fact_steps: [satisfaction evidence for not/cmp/in/arithmetic atoms]
     rule_refs: [RuleRef expansion chain, if any]
   ```

   `SupportArtifact` 的 digest 写入 `support_digest`，`support_kind` 写成 `"native_binding_v1"` 而非 `"none"`。实现入口在 `store/_evaluate.py`（native 模式的 `evaluate_store`）。

   对 engine 路径（souffle、problog），evaluator 接口需要扩展以支持可选的 witness output；其 `support_kind` 可以分别标注为 `"souffle_v1"`、`"problog_v1"`，以便消费方区分 proof 来源。

   **实现优先级排序**：
   1. 先在 `store/_evaluate.py` 定义 `SupportArtifact` minimum schema，确认 `pred_witnesses` 捕获机制；
   2. 在 `_builders.py` 填充真实 `support_digest`/`support_kind`，替换哑值；
   3. `run_rule` 的 rule-run trace 机制（见 5e）作为独立子蓝图，不阻塞 derivation 路径；
   4. service 层 `explain_ref` 统一协议最后收口。

   **5d. `explain_ref` 统一协议应在 service 层定义**

   不同类型的执行结果有不同的 identity 体系，长期看不适合让 core 中每类对象各自长出同名字段。更稳的方式是 service 层统一定义 `explain_ref` 协议：

   ```
   explain_ref:
     kind: "candidate" | "assertion" | "rule_run" | "judgment"
     id: ...
     run_id: ...
     stable_key: ...   # 可选，content-addressed，用于跨 run 去重
   ```

   各类结果的映射：
   - `derivation candidate`：`kind="candidate"`，`id=candidate_id`，`stable_key=candidate_key`
   - `accepted assertion`：`kind="assertion"`，`id=asrt_id`，related `candidate_id` 放 explain payload
   - `rule run`：`kind="rule_run"`，`id=rule_run_id`（见 5e）
   - `deontic judgment`：`kind="judgment"`，待后续单独定义

   这样 `CandidateSet` 不需要新增 `proof_entry_id` 字段；它已有的 `candidate_id` 即为 `explain_ref(kind="candidate")` 的底层 handle。proof entry 的统一问题更多地落在 service contract，而不是 core candidate schema。

   **5e. rule run 路径现在已有 execution trace，剩余问题转向 schema / contract**

   这里的代码现实已经不同于更早期讨论阶段：`run_rule_with_trace(...)`、`RuleTraceArtifact`、memo-hit replay、`pred_witnesses`/`non_fact_steps` capture，以及 `rule_run_id` explain readback 都已经落地。

   这意味着当前 `rule_run` 的主要问题不再是“有没有 trace”，而是：
   - trace schema 的哪些部分已经进入稳定 contract；
   - `ruleref` call-site atom 与 child invocation 之间如何显式映射；
   - `non_fact_steps.status` 的枚举语义是否已冻结；
   - service 层 `rule_run` explain payload 的 typed subset 与 opaque boundary 如何文档化。

   因此，`rule_run` 的下一切口不应再用“从零补 execution trace”来 framing，而应以当前代码现实为准，继续收口 schema / contract gap。这个工作现已拆到并归档为子蓝图 [2026-03-17_rule-run-trace-schema-contract.md](../archive/2026-03-17_rule-run-trace-schema-contract.md)。

   **5f. 当前代码对 explain 的最主要阻塞点**

   综合来看，当前阻塞 proof entry 落地的代码问题按优先级排列：

   1. **`support_digest` / `support_kind` 全是哑值 + projection 层剥除了 `asrt_id`**
      - `project_view_facts` 在投影时剥除 `asrt_id`，where evaluator 只看到 value 元组；
      - 因此 `evaluate_store` 在执行完 `evaluate_where` 后，根本不知道哪些 claims 被匹配；
      - 需要 witness-capable projection 层（保留 `asrt_id`）+ `SupportArtifact` schema（`pred_witnesses` 等）；
      - 这是最根本的 gap：不解决，`candidate_id` 作为 proof entry 永远是空壳。

   2. **`rule_run` trace 的 schema / contract 仍未完全冻结**
      - capture/readback 已存在，但 `ruleref` atom linkage、`non_fact_steps.status` 语义、以及 service payload contract 仍需单独子蓝图收口；
      - 这也是为什么 `rule_run` 仍然值得保留独立后续切片。

   3. **`explain_fact` 入口是 `(pred_id, e_ref)` 而非 `asrt_id`**
      - `explain_fact(store, pred_id, e_ref)` 返回该 predicate 下该实体的所有 active claims；
      - 功能上可以工作，但 service 层的 `explain_ref(kind="assertion", id=asrt_id)` 需要以 `asrt_id` 为直接入口；
      - 当前路径需要在 service 层做一次包装，把 `asrt_id` 解析为 `(pred_id, e_ref)` 后再调用。

   一句话总结：**长期正确方向不是"给每个结果挂一个新 ID"，而是"让现有结果 ID 能解引用到 evaluate 当时捕获的真实 artifact"；derivation 先走 `candidate_id + support_digest`，assertion 继续走 `asrt_id`，rule run 则在已存在 trace 的基础上继续收口 schema / contract。**

   与此相关的第一份实现型切口，现已拆到子蓝图 [2026-03-17_support-artifact-native-capture.md](../archive/2026-03-17_support-artifact-native-capture.md)。service 层的统一 explain contract 也已作为独立子蓝图落地并归档到 [2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)。针对 `rule_run`，schema / contract 收口工作也已作为独立子蓝图落地并归档到 [2026-03-17_rule-run-trace-schema-contract.md](../archive/2026-03-17_rule-run-trace-schema-contract.md)，用于按当前代码现实而不是更早期假设来冻结 trace payload 边界。针对 engine witness output，第一轮“显式 degraded explain 优先于真 witness parity”的子蓝图现已实现并归档到 [2026-03-18_engine-witness-parity.md](../archive/2026-03-18_engine-witness-parity.md)。本母蓝图保留总问题 framing，不在此处继续展开 native `SupportArtifact` 的实现细节；后续若进入更强的 engine witness output，也更适合继续拆成后续子蓝图。

   在当前代码现实下，若本母蓝图继续推进实现型 child slice，最自然的下一项已经不是再补同层 explain delivery，而是把现有：

   - `candidate_id + support_digest/support_kind`
   - `rule_run_id + RuleTraceArtifact`
   - assertion drill-down
   - runtime/audit/static delivery spine

   提升成 **result-centric recursive evidence tree / proof-tree surface**。这条线应被视为本母蓝图里 `proof-tree / support-graph-oriented` 方向的第一实现阶段，而不是新的独立母计划。

### 5.5 Cross-domain Discussion Prompts

仓库中的 [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md) 目前只是一份 **无来源的内部参考报告**。它不应被当作外部事实依据、标准条款来源或决策性证据；但其中有些 framing 也许可以作为继续收口问题时的讨论提示。

若仅把它当作“启发式类比材料”来看，其中较值得保留的不是具体行业事实，而是以下几类抽象能力：

1. `time-window + threshold reasoning`
   - 不论是在高监管金融场景，还是在航天/工程合规场景，系统也许都需要表达：
     - 某个阈值是否在某个时间窗口内被触发；
     - 该触发为何在这一时刻成立，而不是更早或更晚。

2. `distributed events -> obligation / risk state`
   - 一种值得继续比较的 framing 是：
     - 系统的核心价值未必只是识别单个事件；
     - 而是把分布式、异构、时间相关的事件，聚合成“义务状态 / 风险状态 / 合规状态”。

3. `weak-signal combination`
   - 若未来要支持 richer explainability，annotation 或其他 value-semantics layer 也许需要回答：
     - 哪些弱信号被组合；
     - 哪些信号贡献较大；
     - 哪些缺失信号被允许跳过；
     - 最终为什么形成某个 certainty / probability / ranking outcome。

4. `audit-log -> proof-tree`
   - 该参考材料强化了一种值得继续验证的猜想：
     - 近期更容易落地、也更贴近现有系统能力的，也许仍是 `audit-log-first`；
     - 更强的 explainability 则可能逐步延伸到 `proof-tree` 或 support-graph 视图。

5. `hybrid layering as a candidate framing`
   - 该参考材料还提示，一个也许更稳的长期形态，不一定是 `annotation-only`，而可能是分层的 hybrid：
     - `proof / provenance carrier`
       - 中性承载“怎么推出的 / 依赖了什么”；
     - `annotation / evaluator layer`
       - 承载 certainty、probability、impact breakdown、missing optional conditions 等值语义；
     - `audit / trace layer`
       - 承载 run、decision、apply、version、export、replay 等系统追溯信息。
   - 当前这更像一个值得比较的设计提示，而不是既定路线：
     - 它与本蓝图前文的 `hybrid` 候选方向相关；
     - 但是否真的需要三层显式拆分、以及它们如何映射到现有 `CandidateSet / audit / annotation`，仍需后续讨论。

6. `cross-domain obligation reasoning`
   - 该材料还提示，本蓝图或许不必把讨论限制在单一行业名词上；
   - 更可迁移的表述也许是：
     - 规则、阈值、时间窗口、证据链、义务状态、例外/豁免说明；
     - 然后再分别映射到 ESA、金融合规或其他 regulation-heavy 场景。

如果后续要把这些启发纳入正式蓝图结论，仍需要：

- 用已验证的外部材料或仓库内部已确认文档重新支撑；
- 把“跨领域类比”与“项目当前实现真相”继续分开；
- 避免把某个示例用例的说服力误写成系统已经决定的产品路线。

### 5.6 Verified External Anchors Worth Comparing Against

在继续保持讨论开放的前提下，官方 ESA Space Debris Mitigation 文档似乎已经能够为本蓝图中的部分问题提供更强的外部锚点。这里仍不把它们写成“系统必然应如何实现”，而是把它们作为可验证的比较基线。

1. `threshold-driven obligation / compliance state`
   - 在 [ESSB-ST-U-007 Issue 1 Rev. 1](https://sdup.esoc.esa.int/documents/download/ESSB-ST-U-007_Issue_1_Revision_1_23_October_2025.pdf) 中，若干 requirement 已明确采用“阈值 + 状态”形态，例如：
     - 正常运行期间近地轨道航天器的可接受碰撞概率阈值应低于 `10^-4 per conjunction`；
     - LEO protected region clearance 要求 orbit lifetime 小于 `5 years`；
     - re-entry 的 expected number of casualties per re-entry 应小于 `10^-4`，并要求进行 probabilistic assessment。
   - 这些 requirement 似乎支持这样一种看法：系统近期至少需要能表达“某个 requirement / obligation / compliance state 是否在某一条件下成立”，而不是只产出无主语的分数。

2. `time-window + threshold reasoning`
   - 同一标准中，对 `5 years` lifetime、`10^-4` 碰撞概率上限、以及 re-entry casualty threshold 的表达，也提示本蓝图中的 `time-window + threshold reasoning` 可能不只是演示友好特性，而是至少在一个官方监管场景中确实存在的核心需求。

3. `probability / certainty boundary`
   - ESA 标准与 handbook 一方面定义了 requirement threshold，另一方面又要求某些分析以 probabilistic 方式进行，并在 [ESSB-HB-U-002 Issue 3 Rev. 0](https://sdup.esoc.esa.int/documents/download/ESA_Space_Debris_Mitigation_Compliance_Verification_Guidelines.pdf) 中讨论了 Monte Carlo、confidence level 以及 90%-95% 置信水平常见用法。
   - 这似乎进一步支持本蓝图前文的一个判断：阈值驱动的 compliance state、certainty-style explanation、以及 probabilistic assessment，可能需要在 carrier 和 semantics 上保持可区分，而不宜提前压缩成单一 `confidence` 语义。

4. `audit / compliance trace artifact`
   - [ESSB-ST-U-007 Issue 1 Rev. 1](https://sdup.esoc.esa.int/documents/download/ESSB-ST-U-007_Issue_1_Revision_1_23_October_2025.pdf) 的 Annex A / B 定义了 `SDMP` 与 `SDMR`，并给出了 compliance and verification matrix 示例字段：
     - `Req. Id.`
     - `Compliance Status`
     - `Verification Method(s)`
     - `Justification`
     - `Close-out Reference`
     - `Close-out Status`
   - [ESSB-HB-U-002 Issue 3 Rev. 0](https://sdup.esoc.esa.int/documents/download/ESA_Space_Debris_Mitigation_Compliance_Verification_Guidelines.pdf) 还把 `SDMR` 的更新连接到 PDR / CDR / FRR、在轨异常、任务变更、任务结束等节点。
   - 这些外部材料至少表明：在一个现实合规场景中，`audit-like trace artifact + requirement-scoped status + evidence/reference fields` 的组合确实是被需要的。

5. `near-term demonstration inclination`
   - 基于上述官方文档，以及当前仓库已有的 `audit` 基础设施，一个仍需继续验证、但似乎已经比之前更有支撑的判断是：
     - 近期对外演示也许更适合先围绕 `audit-log-first` 或 requirement-scoped audit artifact 展开；
     - proof-tree / support-graph 则作为后续增强 explainability 的层，而不是一开始就要求完整落地。

### 5.7 Reference Scenarios To Pressure-test Candidate Designs

为了避免讨论停留在抽象层，本蓝图也许可以用两个具名 scenario 来持续检验候选承载模型。它们不自动意味着产品路线，只是作为“如果一个设计连这些问题都解释不清，就说明仍缺关键维度”的压力测试。

1. `ESA SDM compliance scenario`
   - 该 scenario 可用官方 ESA SDM 文档中的 requirement / documentation structure 作为支撑，例如：
     - requirement-scoped compliance status；
     - threshold-triggered state；
     - time-window / orbit-lifetime constraints；
     - compliance and verification matrix；
     - close-out reference 与更新节点。
   - 一个候选设计若要通过这一 scenario，也许至少需要回答：
     - 某条 requirement 为什么当前是 compliant / partial / non-compliant；
     - 这一状态由哪次 run、哪类 analysis、哪些 supporting artifacts 得到；
     - 对应 evidence / justification / close-out reference 该如何被消费。

2. `AML/KYC suspicious-account scenario`
   - 该 scenario 当前只作为设计型 reference，不是本蓝图中的正式监管依据。
   - 其核心形状是：
     - 在一个有限时间窗口内出现多笔接近阈值但未越阈的转账；
     - 之后资金被汇总并流向高风险受益方；
     - 同时存在可组合但单独较弱的 supporting signals，例如共享设备、共享受益人、不一致的受益所有人信息。
   - 一个候选设计若要通过这一 scenario，也许至少需要回答：
     - 系统是否能把分布式事件聚合成 obligation / risk state；
     - 是否能解释“为什么在此刻触发”而不是只给出结果分数；
     - 是否能表达弱信号组合、缺失条件、以及主要 / 次要 proof 的关系。

这两个 scenario 目前主要对应本蓝图前文的第 1、3、4 个问题，尤其是：

- explainability 与 traceability 的最小公共需求是什么；
- 当前 contract 缺的究竟是哪一段；
- 哪类承载方式更适合近期演示，哪类更适合中期建设。

### 5.8 Carrier Layer Boundary: What Belongs Where

在推进 §5.4 的 framing 比较时，有三类能力的归属问题会反复出现：它们究竟属于 **proof/provenance carrier**（结构性的"怎么推出的"），还是属于 **annotation / value-semantics layer**（数值性的"成立程度 / 条件贡献"），还是属于 **audit / trace layer**（系统级的"何时决策 / 由谁执行"）？

这些能力目前在蓝图 §5.9 中作为 annotation extension candidates 列出，但它们的归属问题比是否采用更优先需要讨论。以下是三条当前最容易引发混淆的候选能力及其归属分析：

1. `source taxonomy`（事实来源分类）
   - 对应 Rainbird 中的六种 source 颜色标注：Rule / Inject / Answer / Datasource / KM-global / Synthesised。
   - **更可能属于 proof/provenance carrier**：因为"这个事实是从规则推导的、还是直接注入的、还是用户回答的"是结构性 provenance 信息，不是数值性语义值。
   - 对本项目的映射：facts 来自 ledger write（相当于 Inject）、derivation evaluate（相当于 Rule）、还是 accept 后物化（相当于 KM-global）。如果 proof carrier 未来需要表达这一区分，它需要一个 source type 枚举，而不是一个 annotation 字段。
   - **开放问题**：当前 `CandidateSet` 和 `audit event` 是否已经隐含了 source type 信息？如果已有，proof carrier 可以直接引用；如果没有，这是 carrier 层的 schema gap，而不是 annotation 层的扩展点。

2. `missing optional conditions`（缺失但允许跳过的条件）
   - 对应 Rainbird 中的 synthesised fact：optional condition 不满足时，引擎生成一个 0% certainty 的合成事实，允许规则继续执行，并在 evidence tree 中以 strikethrough 标注。
   - **归属存在张力**：
     - 作为 proof carrier 的一部分：如果 proof tree 记录了"条件 C 本该存在但缺失，rule 以 optional 语义继续执行"，这是结构性 provenance 信息，属于 carrier。
     - 作为 annotation / value-semantics 的一部分：如果关注的是"C 的缺失对最终 certainty 贡献了多少（0%）"，这是数值性语义，属于 annotation layer。
   - **建议**：proof carrier 记录"哪些条件缺失且被允许跳过"（结构），annotation layer 记录"跳过这些条件后 certainty 的变化量"（数值）。两者不应混在同一字段里。

3. `contribution / impact breakdown`（条件贡献分解）
   - 对应 Rainbird 的 Salience Chart：每个条件的 actual impact vs max possible impact，颜色标注，可视化显示。
   - **更可能属于 annotation / value-semantics layer**：因为 impact 是数值语义，不是结构性的 proof 路径。但它的计算依赖 proof carrier 提供的条件权重和条件 certainty，不能脱离 carrier 单独存在。
   - **开放问题**：impact breakdown 的计算时机是什么？
     - 如果在 evaluate 时计算并写入 carrier，那么它会影响 carrier 的 schema；
     - 如果在 query / service 消费时按需计算，它就是 annotation layer 或 service layer 的派生视图，不需要进入 carrier schema。
     - 两种选择的成本和稳定性不同，需要在后续子蓝图中明确。

这三条能力的归属问题，比它们本身是否值得实现更优先需要收口。如果归属不明确，后续很容易出现：proof carrier 开始承担数值语义、annotation 开始承担结构信息、两者边界随迭代漂移的情况。

### 5.9 Annotation Extension Candidates Worth Keeping In View

基于当前 annotation prototype、已归档 workload 结论，以及本蓝图对 carrying model 的重新拆分，先前关于"annotation 还可以扩展什么"的讨论，仍有一部分保留价值；但这些内容更适合作为 **value-semantics layer 候选能力清单**，而不是默认要全部实现的路线图。

#### 近期保留

1. `contribution / impact breakdown`
   - 用来解释某个条件、证据或 support path 对最终 certainty / ranking 结果贡献了多少。

2. `missing optional conditions`
   - 用来表达“哪些条件缺失了，但 evaluator 仍允许结论成立”。

3. `source-aware aggregation`
   - 用来比较不同来源、不同证据类型、不同规则来源对最终结果的影响。

4. `candidate-level + proof-level annotation`
   - candidate 层保留最终 evaluator summary；
   - proof 层保留更局部的贡献、bottleneck、缺失条件等解释。

#### 中期观察

1. `certainty evaluator` 与 `probabilistic evaluator` 分离
   - 可能共享同一个 proof/provenance carrier；
   - 但不强行复用同一个未标注语义的 `confidence` 值。

2. `interval annotation`
   - 适合作为未来表达上下界或不确定范围的候选方向；
   - 但当前优先级低于 certainty-style breakdown。

3. `conflict / contradiction marking`
   - 有继续讨论价值；
   - 但更依赖 proof carrier 与 evaluator 的共同设计，而不是 annotation 单层自足。

4. `why-not / counterfactual annotation`
   - 若未来需要解释“为什么未触发 / 为什么未进入 Top-K”，这会是自然延伸；
   - 但需要更成熟的 proof/provenance contract。

#### 当前不建议作为主方向

1. `generic annotation algebra`
   - 当前证据不足，容易过度设计。

2. `annotation as the only traceability carrier`
   - 当前更合适的讨论方向是 hybrid，而不是 annotation-only。

3. `temporal annotation as first-priority expansion`
   - 既有 spike 已显示 `Workload B` 中 annotation 可能是 `noop`，不应默认放在最前面。

4. `full PyReason-style unified annotation semantics`
   - 当前没有足够证据说明这是近期项目的最优路线。

上述分类并不意味着后续一定采纳或放弃某项能力；它们只是帮助后续讨论时把“值得继续保留的问题”和“当前不宜继续扩大的方向”先分开。

### 5.10 Likely Documentation And Implementation Touchpoints

若后续从讨论进入实现，最可能触及的区域是：

- `src/factpy_kernel/core/store/_evaluate.py`（**首要入口**：`SupportArtifact` schema 定义 + witness-capable projection 集成；native 模式 `evaluate_store` 的 proof witness 捕获逻辑在此）
- `src/factpy_kernel/core/view/projector.py`（witness-capable projection 层：保留 `asrt_id` 与 value 元组的对应关系）
- `src/factpy_kernel/core/store/_builders.py`（`make_candidate` 调用点：用真实 `support_digest`/`support_kind` 替换哑值）
- `src/factpy_kernel/core/derivation`（`candidates.py`、`CANDIDATE_PROTOCOL_V2.md` 更新）
- `src/factpy_kernel/core/rules/rule_ir.py`（rule-run trace：`_evaluate_rule` + `memo_rows` 扩展；需单独子蓝图）
- `src/factpy_kernel/core/store/_queries.py`（`explain_fact` 包装：service 层 `explain_ref(kind="assertion")` 需要 `asrt_id` 直接入口）
- `src/factpy_kernel/core/store`（整体 `Store` public contract）
- `src/factpy_kernel/core/annotation`
- `src/factpy_kernel/audit`
- `src/factpy_kernel/service`（`explain_ref` 统一协议；`runtime_v1.py` 返回结构扩展）

但本蓝图当前阶段不要求这些模块立刻修改，只要求把“哪些点未来可能需要 contract 级变更”讲清楚。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 当前模块 docs 仍然是实现真相。
  - `audit` 仍然是当前的离线审计消费层，不因本蓝图被重写为 live runtime layer。
  - `core/annotation` 仍然是 internal / prototype；其存在不自动意味着正式 contract 已决定。
  - 本蓝图只讨论承载模型，不把任何单个方向提前写成默认路线。
- 明确不做的内容：
  - 不在当前阶段起草新的 stable DTO。
  - 不在当前阶段定义完整 proof/support graph schema。
  - 不直接把此蓝图等同于 `PyReason` 集成、temporal engine 或 graph visualization 项目。
- 兼容性约束：
  - 若后续进入实现，必须复用现有 `candidate / support / provenance / audit` 词汇与边界，而不是重新发明平行语义。
  - 若未来需要新增承载层，必须明确它与 `CandidateSet` 和 `audit package` 的映射，而不是以 side-channel 存在。

## 7. Acceptance

- [ ] 已形成一份专门讨论 runtime traceability / explainability 承载模型的子蓝图
- [ ] 蓝图已明确列出若干候选方向，而不是把某一种写成既定路线
- [ ] 蓝图已明确指出 annotation prototype、当前 audit、以及潜在 proof/support graph 之间的边界
- [ ] 已为后续实现型子蓝图或 contract 讨论留出清晰入口

## 8. Implementation Plan

1. 先建立本讨论型蓝图，明确问题、候选方向和边界，不直接冻结实现方案。
2. 在后续讨论中，把“现有 contract 真相”和“仍需探索的问题”分开记录，避免把设想误写成现状。
3. 在比较承载模型时，也把 proof/provenance carrier 与 value semantics 分开记录，避免把 certainty-style propagation 与 probabilistic reasoning 提前混成同一条路线。
4. 持续用具名 reference scenario 和外部已验证锚点回压候选设计，避免蓝图讨论只停留在抽象术语。
5. 若后续对某个方向形成足够强的共识，再拆分为实现型子蓝图，例如 runtime integration、audit contract、proof/support carrier、reasoning evaluator semantics 等。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.audit.md`
- `docs/blueprints/active/2026-03-15_overall-system-blueprint.md`
- `docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
