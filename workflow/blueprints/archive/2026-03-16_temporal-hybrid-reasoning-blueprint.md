# Task Blueprint: Temporal Hybrid Reasoning Blueprint

- Status: superseded
- Created: 2026-03-16
- Last Updated: 2026-03-22
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/application`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/audit`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
  - [src/factpy_kernel/adapters/docs/01_souffle_adapter.md](../../../src/factpy_kernel/adapters/docs/01_souffle_adapter.md)
  - [src/factpy_kernel/adapters/docs/02_problog_adapter.md](../../../src/factpy_kernel/adapters/docs/02_problog_adapter.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - [docs/blueprint_history/概率推理适配层设计文档.md](../../blueprint_history/概率推理适配层设计文档.md)
  - [docs/blueprint_history/规则.md](../../blueprint_history/规则.md)
- Audit Log:
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.audit.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.audit.md)

## 1. Problem

项目当前已经具备较清楚的 `rule IR -> adapter -> engine` 基本结构，但在“时间推理 + 复合推理”这个方向上存在明显的架构空档。

这在潜在的 ESA / space 场景下会变得突出：

- 卫星、轨道、姿态、观测窗口、相对位置等问题天然包含时间序列、区间、顺序和状态传播。
- 当前系统虽然保留了 `valid_from / valid_to / version` 等业务时态元数据，并支持读侧的 `.at(t)` / `.version(v)` 过滤，但 runtime rule / derivation / service 链路明确不接受 `temporal_view`，说明“时间”目前还不是 runtime 推理的一等语义。
- 现有多后端能力更接近“共享同一运行时语义的不同执行器”：
  - `Souffle / datalog` 适合大规模递归、闭包和关系推导；
  - `ProbLog` 适合概率化证据与不确定性传播；
  - `PyReason` 与类似时间推理工具更接近显式时序/状态传播引擎。
- 如果直接把某个引擎作为新的 adapter 接入，而不先统一时间、概率、外部谓词、provenance 的核心语义，很容易出现 adapter 各自偷偷扩语义、authoring contract 分叉、audit 难以统一的问题。
- 后续还计划引入 LLM 交互、规则提取、规则管理等模块。如果这些能力直接产出 engine-specific 规则或绕过 authoring/control plane，会进一步放大漂移。

因此，本蓝图需要先回答一个更底层的问题：项目要追求的是“单一万能引擎”，还是“统一语义内核之上的复合执行器”。当前倾向是后者，但需要正式收口边界和讨论入口。

## 2. Goals

- 为“时间推理 + 复合引擎”方向建立一个跨模块讨论入口，明确问题拆分与设计语言。
- 说明当前代码基线中哪些能力已经存在，哪些只是历史讨论，哪些尚未进入 runtime 语义。
- 给出一个候选架构形状，帮助后续比较 `PyReason`、`datalog/Souffle`、`ProbLog` 以及可能的 native temporal evaluator 各自角色。
- 定义后续讨论必须覆盖的核心维度：
  - 时间语义模型
  - 不确定性语义模型
  - 引擎能力矩阵与执行规划
  - LLM / rule extraction / rule management 与 runtime 的边界
- 为后续拆分子蓝图提供母结构，避免在单个讨论中同时混合语义、引擎、产品方向和实现细节。

## 3. Non-goals

- 不在本蓝图中直接决定必须采用 `PyReason`、`Souffle`、`ProbLog` 或其他单一引擎。
- 不在本蓝图中立即恢复 `temporal_view` 或定义完整的 temporal materialization 写入协议。
- 不在本蓝图中设计 ESA 领域本体、卫星 schema、坐标系统或轨道算法细节。
- 不在本蓝图中冻结新的 DSL 语法或 service DTO。
- 不在本蓝图中直接实现 adapter、kernel 改动或 LLM 工作流。
- 不把历史蓝图中的时间/规则设想直接视为当前实现真相。

## 4. Current Context

- 当前实现入口：
  - `core` 已提供统一的 rule AST / IR、native evaluator、RuleRef、append-only ledger、accept/audit 主线。
  - `adapters` 当前已落地 `souffle` 与 `problog`，都通过 engine registration 接入 `Store.evaluate(...)`。
  - `authoring` 已明确是 control plane，负责 rule/derivation compile、registry 和 publish/apply 工作流。
  - `service` 和 `sdk` 已明确拒绝 runtime rule/derivation 的 `temporal_view` 参数。
- 当前已知约束：
  - 现有 adapter 机制假定不同引擎共享大体一致的 runtime 输入输出语义，而不是各自引入独占语义。
  - `valid_from / valid_to / version` 目前主要位于 meta 和读侧过滤语义中，还没有进入统一 runtime rule semantics。
  - append-only ledger、显式 accept、统一 audit/provenance 仍是核心不变量，不能因为新引擎而弱化。
  - `core` 不静态依赖 adapters；多引擎并存是既有方向。
  - 当前 backend profile 只在较轻量级的 validator/能力约束上使用，还没有发展成真正的 execution planning contract。
- 当前相关历史蓝图：
  - [docs/blueprint_history/概率推理适配层设计文档.md](../../blueprint_history/概率推理适配层设计文档.md)
  - [docs/blueprint_history/规则.md](../../blueprint_history/规则.md)
  - [docs/blueprint_history/从Rule到Query的迭代设计.md](../../blueprint_history/从Rule到Query的迭代设计.md)
  - [docs/blueprint_history/视图层.md](../../blueprint_history/视图层.md)
  - [docs/blueprint_history/规范.md](../../blueprint_history/规范.md)

### 4.1 当前冲突点

1. `时间作为数据` 与 `时间作为推理语义` 仍未分清。
   - 目前系统保存时间相关 meta，但 runtime 并不以时间为一等推理输入。

2. `adapter 扩展` 与 `kernel 扩展` 仍未分清。
   - 若某能力会被多个引擎共享，或会影响 authoring contract / audit / accept 语义，它更像 kernel 问题，而非 adapter 问题。

3. `单引擎替代` 与 `复合执行` 仍未分清。
   - `datalog`、`ProbLog`、`PyReason` 各有优势，但优势并不在同一维度上。

4. `runtime 推理` 与 `authoring/control plane` 仍需进一步隔离。
   - 未来 LLM 参与规则提取、规则修订和规则管理是合理方向，但不应直接绕开 authoring validation / registry / audit。

## 5. Proposed Shape

### 5.1 顶层设计立场

**核心原则: 单引擎优先，复合执行是逃生通道而非默认路径。**

> 2026-03-16 讨论澄清：对于任意一次推理任务，默认假设是由单一引擎从头执行到底。只有当单一引擎在性能或语义能力上确实无法覆盖整个任务时，才引入 staged pipeline。构建跨引擎 pipeline 的代价是真实的（引擎间语义映射、跨引擎 provenance 链维护、调试复杂度），不应为了"架构优雅"而提前支付。

在此原则下，本蓝图建议项目的架构**容许能力**（而非默认路径）是：

- `统一语义内核 + 复合执行器`（当需要时可以组合多引擎）

而不是：

- `寻找一个覆盖所有能力的单一万能引擎`（不要求某个引擎解决所有问题）

**为什么不排除复合执行的可能性**：

- 时间、递归、概率、外部谓词、数值约束通常来自不同技术传统，强行塞进单引擎往往会牺牲可解释性、可维护性或性能。
- 当前仓库已经天然更接近"统一 IR + 多引擎"形状，继续沿这个方向演化成本更低。
- 复合执行更适合将"数值/轨道处理"和"符号/规则推理"分层，而不是让逻辑引擎承担全部时序计算。

**但复合执行只在以下条件满足时才值得引入**：

- **(a)** 确定性阶段涉及大规模递归闭包，概率引擎（如 ProbLog）在 certainty=1.0 的情况下仍存在不可接受的性能开销；或者
- **(b)** 推理任务需要某种单一引擎根本不支持的语义（如显式时间区间状态传播），构成能力缺口而非仅仅性能问题。

**在真正遇到上述瓶颈之前，更简单的替代方案是**：让单一引擎（如 ProbLog）从头跑到底，确定性部分标注 certainty=1.0。这在逻辑上完全正确，只是在大规模递归闭包场景下可能产生不必要的性能开销。对于中小规模规则集，这个开销可能完全不重要。

### 5.2 建议的讨论层次

1. `Temporal Evidence Layer`
   - 明确哪些信息属于 observation / event / interval / state。
   - 区分 transaction time 与 business valid time。
   - 明确轨道坐标序列、姿态序列、接触窗口、告警事件等进入系统时的 canonical shape。

2. `Reasoning Semantic Layer`
   - 定义 runtime 真正需要的一等语义，而不是直接讨论具体引擎。
   - 最少需要讨论：
     - 时间点 vs 时间区间
     - 顺序/前后关系
     - 窗口与持续条件
     - 递归闭包
     - 概率/置信度
     - provenance / support
     - 外部谓词或外部数值过程

3. `Unified Rule IR Layer`
   - 在现有 rule/where AST 基础上，明确哪些能力属于可扩展 IR：
     - temporal atoms 或 temporal predicates
     - confidence annotations
     - external predicate contract
     - capability requirements / execution hints
   - 目标不是一口气支持所有语法，而是先确定 IR 的扩展位点和不可跨越边界。

4. `Execution Planning Layer`
   - 在 `BackendProfile` 的轻量能力矩阵之上，逐步引入真正的 execution planning：
     - 哪类规则可由 `native` 执行
     - 哪类规则适合 `Souffle/datalog`
     - 哪类规则适合 `ProbLog`
     - 哪类时间传播规则需要 `PyReason` 或独立 temporal engine
     - 哪些查询需要 staged execution，而不是单引擎直跑

5. `Adapter / Engine Role Layer`
   - 建议把引擎角色理解为：
     - `Souffle / datalog`: 关系递归、闭包、静态依赖分析、批量实例化
     - `ProbLog`: 不确定性传播、证据融合、概率回填
     - `PyReason` 或类似引擎: 时间传播、显式状态更新、时序 rule firing
     - `native`: 最小可用语义、测试基线、无外部依赖 fallback
   - 这不是最终定稿，只是当前讨论起点。

6. `Control Plane Layer`
   - LLM、规则提取、规则管理、规则评审都应进入 authoring/control plane。
   - 这些模块产出的应是结构化 authoring assets 或 change proposals，而不是未经验证的 engine-specific 程序。

7. `Audit / Provenance Layer`
   - 无论 future engine 如何组合，最终都需要回到统一的：
     - candidate identity
     - support/provenance
     - accepted evidence
     - run/session/package audit
   - 时间推理和概率推理都不能绕开 audit 模型。

### 5.3 建议先回答的核心问题

本蓝图建议后续讨论按以下问题推进：

1. 我们真正需要的时间能力是什么？
   - point-time
   - interval
   - sequence / ordering
   - sliding window
   - state transition

2. 时间语义应该落在哪里？
   - 只停留在读侧过滤
   - 进入 rule IR
   - 进入 accept/materialization contract
   - 进入 view/projector contract

3. 不确定性来自哪里？
   - 观测/传感器证据
   - 规则本身
   - LLM 抽取结果
   - 外部模型输出

4. 复合执行是否允许 staged pipeline？
   - 例如：轨道/几何预处理 -> temporal/event facts -> datalog closure -> probabilistic ranking
   - **讨论进展 (2026-03-16)**: 架构上允许，但不作为默认路径。单引擎从头执行到底是默认选择。Staged pipeline 只在单引擎遇到性能瓶颈（大规模递归 + 概率引擎开销）或语义能力缺口（如时间区间传播）时才值得引入。更简单的替代方案（ProbLog + certainty=1.0 跑全程）应先被排除后再考虑 staged 方案。

5. `PyReason` 若接入，扮演什么角色？
   - drop-in runtime adapter
   - 专门 temporal engine
   - authoring-time or batch-time propagation service
   - 仅作为实验参考实现
   - **讨论进展 (2026-03-16)**: 已有初步实验但未覆盖完整 annotation 功能。此问题在 `pyreason-integration-spike-blueprint` 完成之前无法可靠回答，当前状态为"待定"。

6. 可解释性/可视化应如何分层和排序？
   - audit-log 风格（追溯链、合规证据）
   - proof-tree 风格（推理链、置信度来源）
   - graph-based 依赖可视化（拓扑展示、workshop 演示）
   - **讨论进展 (2026-03-16)**: 长期目标为三者兼备。面向 ESA 近期接触，建议按 audit-log -> proof-tree -> graph-based 顺序推进，理由见 5.4 风险 3。

### 5.4 开放风险与未解决前置依赖

> 以下风险来自 2026-03-16 讨论，三个关键问题的回答暴露了当前规划中的具体缺口。

1. **近期 ESA demo 目标尚无具体 ECSS 场景锚点**
   - 先前讨论将"ECSS 合规性演示"列为近期优先方向（无需 PyReason，可利用现有 Datalog 递归 + audit/provenance + confidence 能力）。
   - 但截至目前，尚未确定具体 ECSS 条款或验证场景（如 ESSB-ST-U-007 中的哪项碎片缓解要求，或 ECSS-M-ST-10 中的哪项评审检查点）。
   - **风险等级**: 高。如果近期优先方向无法落地为可演示的具体场景，Implementation Plan step 2 实际处于阻塞状态，而非仅仅 pending。整个近期 vs. 中期优先级排序的基础尚未被验证。
   - **建议下一步**: 针对 ECSS-M-ST-10（设计评审合规）和 ESSB-ST-U-007（碎片缓解）进行条款级别的初步调研，筛选出一到两个适合用"规则推理 + 追溯链"演示的候选条款。如果调研后仍无法找到合适的条款，需要重新评估近期方向是否应从 ECSS 合规转向其他 ESA 关注点。

2. **PyReason 实验状态为"半生不熟"，annotation 语义尚未覆盖**
   - 已有初步实验经验，但未涉及完整的 annotation 功能。
   - 先前分析已识别 Souffle 输出（关系元组）与 PyReason 输入（标注图）之间的语义映射为 staged pipeline 的核心技术风险。annotation 语义恰好是该风险的关键部分。
   - **硬性前置条件**: 在做出任何涉及 PyReason 架构角色的决策之前，必须完成一次聚焦的 spike，至少覆盖以下内容：
     - PyReason 的 annotation 模型（节点/边标注的完整语义）
     - annotation 与时间传播的交互方式
     - 从 Souffle 关系元组到 PyReason 标注图的映射可行性评估
   - 此 spike 对应子蓝图 `pyreason-integration-spike-blueprint`，应在该 spike 完成前将 PyReason 相关的架构决策标记为"待定"。

3. **可解释性/可视化方向尚未排定优先级**
   - 长期目标是三种方式（proof-tree、audit-log、graph-based）都实现，这作为愿景合理。
   - 但面向 ESA 的近期交付需要排定先后顺序：
     - **audit-log 风格** (建议优先): 与 ESA 关注的 traceability 和合规证据最对齐，且现有 audit 基础设施可复用，实现成本最低。
     - **proof-tree 风格** (建议次优先): 与 ESA 关注的 explainability 和 certainty estimation 最对齐，直接展示推理链和置信度来源。
     - **graph-based 依赖可视化** (建议第三): 对演示和 workshop 展示（如 FLoC 2026）视觉冲击力最强，但对合规验证的紧迫性较低。
   - **风险**: 若三者同时推进而无优先级，容易分散有限资源，且可能在 ESA 首次接触时缺乏聚焦的演示故事。

### 5.5 建议的子蓝图拆分

- `temporal-semantics-blueprint`
  - 定义时间语义最小闭环，尤其是 observation/event/interval/state 与 runtime 的关系。
- `engine-capability-matrix-blueprint`
  - 形成 `native / souffle / problog / pyreason` 的能力矩阵与选择规则。
- `temporal-runtime-contract-blueprint`
  - 若决定恢复 runtime 时态能力，定义 rule/derivation/service/sdk 的 contract。
- `uncertainty-and-confidence-blueprint`
  - 统一 `confidence`、probabilistic evidence、LLM extraction confidence 的口径。
- `runtime-traceability-explainability-blueprint`
  - 单独比较 `audit-log`、`proof-tree`、`graph-based` 以及 annotation/provenance 承载方式的边界。
  - 该子蓝图当前只用于收口讨论，不预设“support graph first”或“annotation first”为既定路线。
- `souffle-backed-annotation-kernel-spike`
  - 评估是否以 `Souffle` 作为结构推理底座，并在 `core` 叠加 annotation kernel，只实现概率/区间/时间的可靠子集。
  - 该子蓝图默认采用三基线对照：`PyReason` 直跑、`ProbLog` 单引擎直跑、`Souffle + 最小 annotation prototype`。
- `authoring-llm-governance-blueprint`
  - 限定 LLM 在规则提取、修订建议、发布审核中的角色。
- `pyreason-integration-spike-blueprint`
  - 如果后续决定探索 PyReason，单独做限边界的 spike，而不是直接把其语义写进主蓝图。

在这些候选子蓝图之前，当前更基础的前置动作是先把“ESA / ECSS 方向”锚定到具名场景，而不是继续停留在抽象引擎与语义讨论中。为此，新的活动子蓝图已打开为 [2026-03-18_ecss-scenario-anchoring.md](./2026-03-18_ecss-scenario-anchoring.md)，先比较 design-review/compliance 与 debris-mitigation 两类 reference scenarios，再决定后续的 temporal / uncertainty / engine 优先级。

当前该子蓝图的第一轮结论已明确倾向：

- 近期优先锚点：`ECSS-M-ST-10` 风格的 VCD / compliance-matrix scenario
- 中期驱动场景：`ESSB-ST-U-007` 风格的 debris-mitigation scenario

这意味着在 temporal-hybrid 主线上，下一条更自然的实现型子蓝图并不是 `pyreason-integration-spike` 或 `temporal-semantics`，而更接近：

- `ecss-vcd-compliance-delivery`

该子蓝图现已实现并归档为 [2026-03-18_ecss-vcd-compliance-delivery.md](../archive/2026-03-18_ecss-vcd-compliance-delivery.md)，说明近期 ECSS-M-ST-10 锚点已经从“优先级判断”推进为一个真实的 offline delivery 能力切片。

后两者仍然保留，但更适合作为被 ESSB-ST-U-007 场景反向驱动的中期切口。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `core` 仍然是 runtime semantic kernel，不得把关键时间语义偷偷塞进单个 adapter。
  - `authoring` 仍然是 control plane；未来 LLM / extraction / management 必须经过 authoring validation 和 registry。
  - `audit` 仍然是跨引擎统一追溯入口；新引擎不能绕过 candidate/support/provenance。
  - append-only ledger、显式 accept、结构化 IR 优先的原则不能被削弱。
- 明确不做的内容：
  - 不在本蓝图中把任何单一引擎升级为默认唯一内核。
  - 不在没有定义 temporal write semantics 之前仓促恢复 runtime `temporal_view`。
  - 不把轨道传播、几何计算、数值积分等全部挤进逻辑 rule engine。
- 兼容性约束：
  - 若时间语义需要进入 runtime，必须通过可验证的 IR / DTO / audit contract 进入，而不是 adapter 私有 side-channel。
  - 若引入 capability matrix 或 execution planner，必须保留现有 `native|souffle|problog` 的最小可运行路径。
  - 若后续引入 `PyReason`，其角色必须先在 blueprint 中定性，再进入 adapter 或独立服务设计。

## 7. Acceptance

- [ ] 已形成一份专门面向“时间推理 + 复合执行器”的讨论蓝图
- [ ] 蓝图已明确区分当前实现真相、历史讨论与未来探索方向
- [ ] 蓝图已提出统一语义内核优先于单一万能引擎的候选立场
- [ ] 蓝图已拆出后续需要分别推进的子蓝图方向

## 8. Implementation Plan

1. 建立本蓝图 draft，记录当前冲突点、目标和候选架构形状，不直接启动实现。
2. 在后续讨论中补齐面向 satellite / ESA 场景的代表性推理用例，尤其是轨道、坐标、窗口、事件与状态传播。
   - **当前状态 (2026-03-16)**: 此步骤处于阻塞状态。尚未确定具体 ECSS 条款作为近期演示锚点。下一步需对 ECSS-M-ST-10 和 ESSB-ST-U-007 进行条款级初步调研。
3. 基于代表性用例，形成引擎能力矩阵，比较 `native / Souffle / ProbLog / PyReason` 的适配位置和不可替代能力。
   - **前置依赖**: step 2 的 ECSS 场景确定 + `pyreason-integration-spike-blueprint` 的 spike 结果。在此之前，PyReason 在矩阵中的定位标记为"待定"。
4. 明确“时间是否进入 kernel 语义”这一决策点；如果答案是是，再拆出 `temporal-semantics` 与 `temporal-runtime-contract` 子蓝图。
5. 在时序语义边界清晰后，再讨论 LLM 规则提取、规则管理、置信度来源与治理模型。

## 9. Docs To Update

- `docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md`
- `docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.audit.md`
- `docs/README.md`（当前 draft 阶段暂不更新；若后续产出持久入口或归档，再讨论）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - 该母蓝图完成了对“单引擎优先 vs 复合执行 escape hatch”的早期收口，并为 ECSS 场景锚定、engine capability 讨论和后续 certainty/provenance 线路提供了上游 framing。
- 与 blueprint 不同的地方：
  - 当前阶段并未继续沿 temporal runtime contract 或 PyReason integration 开实现线，而是先收敛到 ECSS 规则 fit 与 Souffle provenance feasibility。
- 为什么会有这些调整：
  - 2026-03-22 的阶段判断表明，真实 ECSS 规则复杂度与 engine-native provenance 才是当前最关键的未知数，优先级高于抽象 temporal/hybrid 讨论。
- 归档说明：
  - 本蓝图已由 `2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md` 接替当前阶段母图角色，并按 `superseded` 路径归档。
