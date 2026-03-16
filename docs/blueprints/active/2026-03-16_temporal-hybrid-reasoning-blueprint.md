# Task Blueprint: Temporal Hybrid Reasoning Blueprint

- Status: draft
- Created: 2026-03-16
- Last Updated: 2026-03-16
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
  - [docs/blueprints/active/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
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

本蓝图建议项目优先探索：

- `统一语义内核 + 复合执行器`

而不是：

- `寻找一个覆盖所有能力的单一万能引擎`

原因是：

- 时间、递归、概率、外部谓词、数值约束通常来自不同技术传统，强行塞进单引擎往往会牺牲可解释性、可维护性或性能。
- 当前仓库已经天然更接近“统一 IR + 多引擎”形状，继续沿这个方向演化成本更低。
- 复合执行更适合将“数值/轨道处理”和“符号/规则推理”分层，而不是让逻辑引擎承担全部时序计算。

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

5. `PyReason` 若接入，扮演什么角色？
   - drop-in runtime adapter
   - 专门 temporal engine
   - authoring-time or batch-time propagation service
   - 仅作为实验参考实现

### 5.4 建议的子蓝图拆分

- `temporal-semantics-blueprint`
  - 定义时间语义最小闭环，尤其是 observation/event/interval/state 与 runtime 的关系。
- `engine-capability-matrix-blueprint`
  - 形成 `native / souffle / problog / pyreason` 的能力矩阵与选择规则。
- `temporal-runtime-contract-blueprint`
  - 若决定恢复 runtime 时态能力，定义 rule/derivation/service/sdk 的 contract。
- `uncertainty-and-confidence-blueprint`
  - 统一 `confidence`、probabilistic evidence、LLM extraction confidence 的口径。
- `authoring-llm-governance-blueprint`
  - 限定 LLM 在规则提取、修订建议、发布审核中的角色。
- `pyreason-integration-spike-blueprint`
  - 如果后续决定探索 PyReason，单独做限边界的 spike，而不是直接把其语义写进主蓝图。

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
3. 基于代表性用例，形成引擎能力矩阵，比较 `native / Souffle / ProbLog / PyReason` 的适配位置和不可替代能力。
4. 明确“时间是否进入 kernel 语义”这一决策点；如果答案是是，再拆出 `temporal-semantics` 与 `temporal-runtime-contract` 子蓝图。
5. 在时序语义边界清晰后，再讨论 LLM 规则提取、规则管理、置信度来源与治理模型。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md`
- `docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.audit.md`
- `docs/README.md`（当前 draft 阶段暂不更新；若后续产出持久入口或归档，再讨论）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
