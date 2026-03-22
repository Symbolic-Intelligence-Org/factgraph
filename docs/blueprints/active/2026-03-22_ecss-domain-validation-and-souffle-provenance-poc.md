# Task Blueprint: ECSS Domain Validation And Souffle Provenance PoC

- Status: scoped
- Created: 2026-03-22
- Last Updated: 2026-03-22
- Related Modules:
  - `docs`
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/audit`
  - `src/factpy_kernel/sdk`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/core/annotation/docs/README.md](../../../src/factpy_kernel/core/annotation/docs/README.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
  - [memory/current.md](../../../memory/current.md)
- Audit Log:
  - [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.audit.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.audit.md)

## 1. Problem

当前仓库已经具备一条完整的 delivery pipeline：

- candidate evidence tree
- explain summary / narrative / NL
- audit package export / query / static site
- certainty v1 routing / materialization / rendering

但 2026-03-22 的架构复盘已经明确指出：这条 pipeline 的底层信息仍然偏薄，尤其在真实 Datalog reasoning 场景中，evidence tree 更接近 audit trail，而不是 engine-native reasoning explanation。

同时，项目仍未完成最关键的现实验证：

- 没有读并编码真实的 ECSS 规则；
- 没有验证这些规则是 flat 还是 recursive；
- 没有用 Souffle provenance 去验证当前 delivery pipeline 能否消费 engine-native proof data。

因此，当前阶段的核心任务不再是继续打磨 certainty、narrative 或 static delivery，而是：

1. 用真实 ECSS 条款验证当前 Rule DSL / Datalog 适配度；
2. 用 Souffle provenance PoC 验证 engine-native proof 是否能接入现有 framework；
3. 基于这两条证据，决定下一轮实现是否必须进入 ProofNode / provenance adapter 路线。

## 2. Goals

- 建立一个新的阶段母蓝图，承接 2026-03-22 之后的唯一 active 母方向。
- 明确当前阶段只围绕两条主验证线推进：
  - ECSS domain validation
  - Souffle provenance PoC
- 冻结本阶段的非目标，避免继续扩张 certainty v1 或 delivery polish。
- 给下一轮收窄子蓝图提供拆分框架与完成顺序。

## 3. Non-goals

- 不在本母蓝图中直接实现 ProofNode。
- 不在本母蓝图中继续扩 certainty v1、probability lane 或更多 narrative/NL 功能。
- 不在本母蓝图中重开 evidence tree 的 carrier contract。
- 不在本母蓝图中承诺 PyReason 集成或多引擎 execution planner 实现。
- 不把战略思考写成 module current truth。

## 4. Current Context

- 当前实现入口：
  - `certainty v1` 已冻结，相关 contract 只接受 bug fix / performance / docs clarification。
  - `candidate_evidence_tree`、runtime explain、audit/static delivery 已形成稳定基线。
  - Souffle 当前通过 [runner.py](../../../src/factpy_kernel/adapters/souffle/runner.py) 在 interpreter mode 下执行，具备 provenance PoC 的低成本插入点。
- 当前已知约束：
  - 项目定位应描述为“auditable reasoning framework”，而不是“自研 reasoning engine”。
  - traceability/explainability 应优先消费 engine-native capability，而不是在 annotation layer 中重建。
  - evidence tree 当前能回答“为什么成立”，但不能回答负向 reasoning、完整递归链、alternative proofs 或 minimal proof。
  - 真正决定下一阶段路线的关键输入不是更多系统内打磨，而是真实 ECSS 规则复杂度。
- 当前相关历史蓝图：
  - `2026-03-15_overall-system-blueprint`
  - `2026-03-16_temporal-hybrid-reasoning-blueprint`
  - `2026-03-17_runtime-traceability-explainability-blueprint`
  - 上述三个母蓝图已完成其探索角色，将由本母蓝图接替当前阶段 framing。

## 5. Proposed Shape

### 5.1 当前阶段定位

本蓝图是 2026-03-22 之后的阶段母图，不直接承载单条 capability line 的实现。

它的职责是：

- 提供当前阶段的唯一 active framing；
- 明确哪些方向继续推进，哪些方向暂停；
- 定义子蓝图拆分顺序；
- 给后续 agent 一个不会误导的阶段边界。

### 5.2 关键架构判断

1. **产品定位**
   - 项目应被描述为 auditable reasoning framework。
   - engine 负责 reasoning；framework 负责 audit、traceability、delivery 和 engine capability consumption。

2. **对 evidence tree 的诚实判断**
   - 当前 evidence tree 是 audit trail / positive proof logging。
   - 它不是完整 reasoning explanation。

3. **对 certainty v1 的诚实判断**
   - certainty v1 仅适用于 flat、single-rule、non-recursive 子集。
   - 它已冻结，不是当前阶段的主线。

4. **下一阶段的正确瓶颈**
   - 不是 delivery pipeline feature gap。
   - 而是 domain content gap + engine provenance gap。

### 5.3 当前阶段两条主验证线

#### A. ECSS Domain Validation

目标不是立即做完整 ESA demo，而是先回答三个问题：

1. 真实 ECSS 条款能否被当前 Rule DSL / Datalog 子集表达？
2. 条款是 flat 为主，还是会迅速进入 recursive / multi-path complexity？
3. 当前 evidence tree 对最小可演示规则是否已经足够？

最低交付应包含：

- 选出 3-5 条最简单的 ECSS 合规规则；
- 至少 1 条被编码为现有 SDK Rule DSL / Datalog；
- 对规则复杂度与当前 delivery sufficiency 给出书面判断。

#### B. Souffle Provenance PoC

目标不是直接重构 explain stack，而是验证 feasibility：

1. `runner.py` 能否以低侵入方式进入 provenance mode；
2. provenance output 是否能表达当前 evidence tree 缺失的递归 proof 信息；
3. 现有 framework 是否适合消费 provenance-adapted proof carrier。

最低交付应包含：

- provenance mode 的运行 PoC；
- 对 proof structure、限制与 integration cost 的记录；
- 对“是否进入下一阶段 provenance adapter / ProofNode”给出判断。

### 5.4 决策门

本阶段至少要回答以下决策门：

1. **ECSS fit gate**
   - 若最简单 ECSS 规则都难以落入当前 Rule DSL / Datalog 子集，则应先收口 authoring/rule-layer 问题。

2. **Evidence sufficiency gate**
   - 若选定规则多为 flat 且 positive proof 足够，则当前 evidence tree 可继续承担近期 demo carrier。

3. **Provenance necessity gate**
   - 若规则迅速进入 recursive proof、negative reasoning 或多路径 explain，则 Souffle provenance 应升为下一阶段前置能力。

### 5.5 明确暂停的方向

在以上决策门关闭前，以下方向不应继续作为当前主线推进：

- certainty v1 新功能
- probability lane
- ProofNode implementation
- 更多 narrative / NL / ranking polish
- generalized multi-engine abstraction expansion

### 5.6 子蓝图拆分建议

本母蓝图下的首批子蓝图建议为：

1. `ecss-rule-selection-and-fit-assessment`
   - 读标准，挑规则，判断 flat/recursive/negative reasoning 复杂度。

2. `first-ecss-rule-encoding-spike`
   - 用当前 SDK / Datalog 子集编码第一条规则。

3. `souffle-provenance-runner-poc`
   - 在最小切口下验证 provenance mode 与输出形态。

4. `domain-validation-decision-handoff`
   - decision-only child blueprint，用于收口下一阶段是否必须进入 provenance-first 路线。

### 5.7 尚未实现但可保留在视野中的中期结构

- `ProofNode`
  - 应被理解为 engine-native proof consumption 的统一 carrier，而不是当前阶段立即实现项。
- `three-layer rule system`
  - Layer 1: current shared core IR
  - Layer 2: engine-specific extension
  - Layer 3: raw engine syntax escape hatch

这两者保留为中期设计方向，但不在本阶段直接落地。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 模块 docs 仍然是当前实现真相。
  - `certainty v1` 的 frozen contract 不重开。
  - `candidate_evidence_tree` 的当前 contract 不在无子蓝图的情况下改写。
  - 所有实现型工作继续通过收窄子蓝图推进。
- 明确不做的内容：
  - 不把本母蓝图变成新的根目录 design memo。
  - 不让本母蓝图直接承载多条实现线的代码改动。
  - 不把 research notes 直接写成 module truth。
- 兼容性约束：
  - 后续 child blueprint 若改变 engine/native proof carrier，必须显式说明与当前 evidence tree 的共存或替换策略。
  - 若真实 ECSS 规则与当前假设冲突，应以真实规则复杂度为准，而不是保卫当前架构假设。

## 7. Acceptance

- [ ] 当前阶段已有唯一 active 母蓝图
- [ ] 两条主验证线与暂停方向已明确
- [ ] 子蓝图拆分顺序已写清
- [ ] 本母蓝图未越权改写 module current truth

## 8. Implementation Plan

1. 建立本母蓝图，接替 03-15 / 03-16 / 03-17 三个旧母蓝图的 framing 角色。
2. 基于本母蓝图打开第一批收窄子蓝图，而不是直接在母蓝图上实施多条 capability line。
3. 待 ECSS fit 与 provenance feasibility 有结论后，再决定是否进入 ProofNode / provenance adapter 下一阶段。

## 9. Docs To Update

- `docs/README.md`
- `docs/blueprints/README.md`
- `memory/current.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
