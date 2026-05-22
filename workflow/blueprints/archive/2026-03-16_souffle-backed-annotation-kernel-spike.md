# Task Blueprint: Souffle-backed Annotation Kernel Spike

- Status: implemented
- Created: 2026-03-16
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/sdk`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/adapters/docs/01_souffle_adapter.md](../../../src/factpy_kernel/adapters/docs/01_souffle_adapter.md)
  - [src/factpy_kernel/adapters/docs/02_problog_adapter.md](../../../src/factpy_kernel/adapters/docs/02_problog_adapter.md)
- Audit Log:
  - [2026-03-16_souffle-backed-annotation-kernel-spike.audit.md](./2026-03-16_souffle-backed-annotation-kernel-spike.audit.md)

## 1. Problem

当前仓库的推理后端以 `native | souffle | problog` 单模式切换为主：一次 `Store.evaluate(...)` 调用只会进入一个 evaluator，并返回统一的 `CandidateSet` 结果。这个边界清晰，但也导致两个现实问题：

- `Souffle` 的高性能关系推理能力与工业化成熟度无法直接承接概率/区间/时间这类 annotation 语义。
- `ProbLog` 与潜在的 `PyReason` 能力只能以并列后端存在，不能自然复用 `Souffle` 在 grounding、join、closure 上的优势。

本 spike 要回答的不是“是否完整复制 ProbLog 或 PyReason”，而是一个更窄的问题：

- 是否可以把 `Souffle` 作为结构推理底座；
- 再在 `core` 中叠加一层 annotation kernel；
- 只实现概率、区间、时间中的可靠子集；
- 从而形成一个比“继续并列挂引擎”更稳定的长期方向。

## 2. Goals

- 明确 `Souffle-backed annotation kernel` 的最小问题定义与术语边界。
- 识别哪些能力适合保留在 `Souffle`，哪些必须进入 `core` annotation kernel。
- 定义“可靠子集”范围，避免不加边界地承诺兼容 `ProbLog` / `PyReason`。
- 把 `PyReason` 直跑、`ProbLog` 单引擎直跑、`Souffle + 最小 annotation prototype` 三个 baseline 明确纳入同一评估框架。
- 为后续 spike 或 prototype 提供清晰的验收问题，而不是直接推动正式实现。

## 3. Non-goals

- 不在本蓝图中实现新的 hybrid evaluator、planner、adapter 或 kernel 代码。
- 不承诺完整兼容 `ProbLog` 的 possible-world / WMC 语义。
- 不承诺完整兼容 `PyReason` 的 annotation、open-world、temporal、conflict resolution 全语义。
- 不在本蓝图中替换现有 `native | souffle | problog` 单模式执行入口。
- 不在本蓝图中定义最终对外 API、service DTO 或 SDK 形态。

## 4. Current Context

- 当前实现入口：
  - `Store.evaluate(...)` 以单一 `mode` 分发 evaluator，`mode` 仅支持 `native | souffle | problog`。
  - `Souffle` adapter 当前承担“整条 derivation/query 的外部执行器”角色，而不是 staged execution 中的结构子执行器。
  - `ProbLog` adapter 当前承担“整条 derivation/query 的概率执行器”角色，并把概率回填到 `CandidateSet.confidence`。
- 当前已知约束：
  - 当前 contract 没有 execution plan / stage / merger 结构。
  - `core` 是 runtime semantic kernel；若 annotation 语义会影响 accept/audit/provenance，不应放在 adapter 私有逻辑中。
  - `sdk.evaluate(..., view=...)` 不支持，说明“事实切片”和“执行规划”当前仍是两件事。
- 当前相关母蓝图：
  - [docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
    - 本蓝图作为其子蓝图，专门收口 `Souffle` 底座 + annotation kernel 的可行性。
- 当前 baseline 假设：
  - `PyReason` 代表 annotation-first、现成可运行的参考基线。
  - `ProbLog` 代表当前仓库已接入的单引擎概率基线。
  - `Souffle + 最小 annotation prototype` 代表目标方向，而不是默认更优方案。
- 当前契约策略：
  - `PyReason` baseline 需要一层实验性 bridge contract，负责输入快照、结果归一化和 unsupported feature 报告。
  - baseline 阶段不直接扩张 `Store.evaluate(...)`、`EvaluateMode`、`CandidateSet`、service DTO 或 SDK 的正式 v1 契约。
  - baseline 比较结果应走独立的 normalized baseline result，而不是提前把 `PyReason` 语义塞进现有对外 contract。
- 当前实现切片：
  - 当前代码实现覆盖 `Workload C` smoke 闭环，并继续推进 `Workload A`。
  - `Workload A` 的口径固定为：
    - golden/reference 使用 `min-max` 语义；
    - `Souffle proto` 使用 `Souffle` 结构闭包 + Python 侧精确 DP，不做完整路径枚举；
    - `ProbLog` baseline 保留 possible-world 概率语义，并将与 `min-max` 的差异视为语义偏差而非实现错误。
  - `Workload A` 的附加实验：
    - `souffle_full_a` 作为 benchmark-only exploratory variant，引擎直接执行 R1-R4；
    - 该变体不替代原三 baseline，只用于回答 Python annotation kernel 在该场景下是否为纯开销。
  - `Workload B` 的当前实现口径：
    - 优先落 `souffle_proto` 路径；
    - 采用 `state_candidate + best_priority + state` 三层关系，由 `Souffle` 内部完成优先级裁决；
    - 为规避 `Souffle` 对聚合递归分层的限制，实际程序以显式 `t=0..Tmax` unroll 形式生成，不依赖单个递归聚合 relation；
    - `annotation kernel` 在该 workload 中不承担语义处理，应在结果中显式记录 `annotation_kernel_noop = true`。
  - 当前 benchmark 结果：
    - `Workload C` smoke 已闭环；
    - `Workload A` 已触发 Gate 1 失败信号，`souffle_proto` 成为主路径，`souffle_full_a` 为负结论；
    - `Workload B` 的 `souffle_proto` 1x smoke 已跑通：`annotation_kernel_noop = true`，1x (`100 entities x 20 steps`) 下 wall-clock 约 `0.295s`、peak memory 约 `9.892 MB`，结果与 golden 完全一致，provenance completeness 为 `1.0`。
  - 当前阶段仍不实现完整三 workload benchmark，也不把 `PyReason` bridge 提升为正式 adapter/runtime mode。

## 5. Proposed Shape

### 5.1 核心立场

建议探索的不是：

- `Souffle` 直接替代 `ProbLog` 或 `PyReason`

而是：

- `Souffle` 负责结构推理
- `core` annotation kernel 负责非布尔语义

也就是：

- `Souffle`: join / recursion / grounding / closure / candidate support skeleton
- `annotation kernel`: probability / interval / time 的受控合并语义

### 5.2 建议保留在 `Souffle` 的内容

- 纯确定性 Horn / Datalog 结构推理
- 类型约束后的 grounding 缩减
- 图上的递归闭包和多跳传播
- 与 annotation 无关的候选绑定枚举
- 可稳定导出的 support skeleton

### 5.3 建议进入 annotation kernel 的内容

- annotation value 形态
  - 标量置信度
  - 区间 `[l, u]`
  - 有界时间标签或时间步
- annotation merge / propagation algebra
- “未知”与“缺失”的口径
- 与 `CandidateSet` / provenance / audit 的对接形态
- 是否允许单次执行内进行 staged iteration

### 5.4 本 spike 只讨论的可靠子集

为避免过早承诺，本 spike 只讨论以下“可靠子集”：

1. `ProbLog` 方向：
   - 事实置信度或规则权重的受控传播
   - 查询结果的概率/置信度排序
   - 不要求完整 possible-world 精确语义

2. `PyReason` 方向：
   - 区间 annotation 的最小形态
   - 有界时间步或静态/动态谓词区分
   - 不要求完整 temporal logic 与冲突修复体系

3. `Souffle` 方向：
   - 仅作为结构推理底座
   - 不要求 `Souffle` 自身原生承担 annotation 语义

### 5.5 需要通过 spike 回答的问题

1. annotation kernel 的最小 IR 应该长什么样？
2. `Souffle` 输出的 relation tuples 如何稳定映射到 annotation-bearing intermediate form？
3. 哪些 annotation 运算是单调、可缓存、可审计的？
4. 哪些概率/区间/时间能力一旦实现，就会迫使 `Store.evaluate(...)` 从单模式进入 staged execution？
5. 如果最终需要 staged execution，最小新增 contract 是：
   - execution plan
   - stage result
   - merger
   中的哪几个？

### 5.6 Baseline-First Evaluation Order

在进入任何正式实现之前，本 spike 先按以下顺序比较三个 baseline：

1. `PyReason` 直跑
   - 目的：验证 annotation-first 语义在现成系统中的表达力、traceability 和性能基线。
   - 前置条件：先建立内部 bridge contract，再进行公平对照；不把 `PyReason` baseline 直接提升为正式 runtime mode。
2. `ProbLog` 单引擎直跑
   - 目的：验证当前仓库已接入概率引擎在代表性 workload 下的上限与边界。
3. `Souffle` 结构推理 + 最小 annotation prototype
   - 目的：验证目标方向是否在结构性能、审计链一致性或语义控制权上提供实质收益。

这三个 baseline 不是“功能并列展示”，而是 go / no-go 决策框架：

- 如果 `PyReason` 或 `ProbLog` 已满足目标用例且性能/审计链可接受，则 `Souffle-backed annotation kernel` 不应自动进入主线。
- 只有当第三个 baseline 在至少一个关键维度上显著优于前两个 baseline，才值得继续推进：
  - 结构推理性能
  - 统一 audit / provenance 契约
  - annotation 语义控制权
  - 对既有 `core` 架构的兼容性

### 5.7 Comparative Evaluation Questions

本 spike 至少需要在代表性 workload 上回答：

1. 哪些 workload 属于结构推理主导，适合 `Souffle` 发挥优势？
2. 哪些 workload 属于 annotation 语义主导，`PyReason` 或 `ProbLog` 反而更直接？
3. `Souffle + 最小 annotation prototype` 是否只是“能做”，还是在关键维度上优于两个基线？
4. 若第三个 baseline 仅在个别场景占优，这种优势是否足以抵消新增 kernel 复杂度？

### 5.8 Baseline Bridge Contract

本 spike 约定：

- `PyReason` baseline 通过内部 bridge contract 接入，而不是直接修改正式 runtime contract。
- bridge contract 至少需要覆盖：
  - baseline input snapshot
  - normalized baseline result
  - unsupported feature report
- bridge contract 的职责是“让三基线可以公平比较”，不是“提前定义未来正式 API”。
- 只有当 baseline 结果证明值得继续推进时，才讨论哪些 bridge 概念需要毕业进入 `core` 正式契约。

### 5.9 PyReason Bridge V0

`PyReason` baseline 在本阶段只要求一个最小 bridge `v0`，其目标是让 baseline 可执行、可比较、可报告，而不是让 `PyReason` 成为正式后端。

建议的最小组成：

1. `baseline input snapshot`
   - 受控事实快照
   - 受限 derivation/rule 子集
   - 必要的 meta（如 confidence/source/time horizon）

2. `normalized baseline result`
   - 统一候选结果形态
   - annotation 结果摘要（如 probability / interval / temporal tag）
   - support/trace summary

3. `unsupported feature report`
   - 明确列出当前 derivation 无法公平映射到 `PyReason` baseline 的原因
   - 阻止 silent degradation

`v0` 阶段明确不要求：

- 与 `CandidateSet` 一一同构
- 进入 `Store.evaluate(mode=...)` 正式路径
- 对 service / SDK 暴露正式 DTO
- 完整覆盖 open-world、interval propagation、temporal trace 全语义

`v0` 的成功标准是：

- 能支撑三基线公平比较
- 能解释“不支持”的原因
- 不破坏现有 public contract
- 能为后续是否值得把某些概念提升到 `core` 提供证据

### 5.10 Benchmark Evaluation Matrix

本 spike 先围绕三类代表性 workload 建立统一评估矩阵。以下规模为 `provisional spike gate`，后续若进入 scoped prototype 可再按机器资源微调，但不得在不同 baseline 之间使用不同规模。

| Workload | 描述 | 侧重瓶颈 | 初始规模假设 | 三 baseline 公平性 |
| --- | --- | --- | --- | --- |
| `A: multi-hop closure + confidence propagation` | 多跳传递闭包与路径置信度合并 | `Souffle` 的结构推理优势与概率传播开销的交叉点 | 500-2000 facts, 10-30 recursive rules | 三者均应可跑 |
| `B: bounded temporal state propagation` | 有界时间步状态传播，输出最终状态与 support 链 | `PyReason` 天然优势场景；`ProbLog/Souffle` 需要显式编码时间步 | 100 entities x 20 time steps x 15 transition rules | 三者均应可跑，但表达自然度允许不同 |
| `C: deterministic structure + probabilistic evidence ranking` | 确定性 Horn clause + 带置信度观测事实，输出候选排序与 provenance | audit / provenance 一致性与候选排序能力 | 1000 deterministic facts + 200 probabilistic evidence facts + 50-200 ranked candidates | 三者均应可跑 |

统一比较维度：

| 维度 | 度量方式 |
| --- | --- |
| `Correctness` | 与 golden output 逐候选比对；annotation 差异同时报告 absolute / relative error |
| `Performance` | 固定硬件、相同输入、5 次取中位数；记录 wall-clock、peak memory，以及 2x / 5x 规模趋势 |
| `Audit / Provenance` | 逐候选检查 support 链完整性，标记是否存在断点、engine-internal 不可解释节点或不可回填片段 |
| `Contract Invasiveness` | 统计需要新增/修改的接口数、类型数，以及是否破坏现有 public API 向后兼容 |

### 5.11 Provisional Go / No-Go Decision Criteria

以下标准是 `provisional spike gate`，用于决定该方向是否值得继续进入 scoped prototype，而不是最终产品 KPI。

#### Gate 1: `ProbLog` already sufficient

若以下条件全部满足，则默认终止第三条路线：

- Workload A: `ProbLog` wall-clock <= `Souffle` 纯结构时间的 5 倍，且绝对值 <= 10s
- Workload C: provenance 能完整映射回现有 `CandidateSet` + audit 模型，且无断点
- Workload B: correctness 通过，且 wall-clock <= 30s

#### Gate 2: `PyReason` already sufficient

若以下条件全部满足，则默认终止第三条路线：

- Workload B: correctness 与 provenance completeness 均通过
- Workload A: wall-clock <= `Souffle` 对应结构基线的 10 倍，且绝对值 <= 30s
- `PyReason` bridge contract 的 invasiveness <= `Souffle + prototype` 路线的 1.5 倍

#### Gate 3: `Souffle + minimal annotation prototype` is worth continuing

只有当以下条件中至少满足两项，第三条路线才值得进入 scoped prototype：

- Workload A: wall-clock <= `ProbLog` 的 50%，即至少 2x 加速，且 correctness 通过
- Workload C: provenance completeness 严格优于另两个 baseline
- 三类 workload 的 contract invasiveness <= `PyReason` baseline

#### Gate 4: bridge complexity too high, terminate early

出现任一项即直接终止第三条路线：

- 映射依赖非单调变换，且无法以局部、增量或静态有界方式表达
- 必须修改 `CandidateSet` 核心 identity / hash 语义才能完成 baseline 对照
- 3 个 workload 中至少 2 个需要多轮 `Souffle <-> kernel` 迭代，且迭代次数无法静态有界

### 5.12 Benchmark Spec Reference

三个 workload 的完整可执行规格已独立成文，存放于：

- [`docs/blueprints/archive/2026-03-16_souffle-annotation-benchmark-spec.md`](./2026-03-16_souffle-annotation-benchmark-spec.md)

本节仅记录各 workload 的一句话摘要，以及本轮讨论中确认的所有决策点。

#### Workload 摘要

| Workload | 一句话描述 |
| --- | --- |
| `A` | 在带置信度的有向图上计算多跳传递闭包，并按路径置信度 algebra 合并输出最优置信度。 |
| `B` | 在 100 个实体、20 个离散时间步、15 条转移规则下传播状态，输出 t=20 的最终状态及 provenance 链。 |
| `C` | 从 1000 条确定性结构事实和 200 条带置信度证据事实中推导候选集，由 harness 统一排序后输出 Top-50。 |

#### Confirmed Decision Points

以下决策点已确认，写入 benchmark spec 文档，并在本节存档：

| 编号 | 适用范围 | 决策内容 | 确认值 | 灵敏度分析 |
| --- | --- | --- | --- | --- |
| `D-1` | 全局 | 随机数种子 | `seed=42`，固定不变 | 无 |
| `A-1` | Workload A | 路径置信度合并代数 | **主实验**：min-max（路径取最小值，跨路径取最大值） | **灵敏度实验**：乘法-max（路径取乘积，跨路径取最大），在主实验完成后单独运行 |
| `B-1` | Workload B | 状态持续规则中是否使用 NAF（negation-as-failure） | 不使用 NAF；状态持续规则改为无条件持续，不依赖 `\+transition_fired` | 无。NAF 的引入会破坏 PyReason open-world 与 Souffle closed-world 之间的公平性，故不提供变体 |
| `B-2` | Workload B | PyReason 是否允许使用原生时间步语义 | 允许；PyReason 结果中须标注 `native_temporal_advantage: true`，说明此项语义优势来自 PyReason 原生能力而非三方共享编码方式 | 无 |
| `B-3` | Workload B | 状态数量 | 固定 3 种状态：`active`、`inactive`、`degraded` | 无 |
| `C-1` | Workload C | 候选置信度聚合方式 | **主实验**：max（同一候选多条证据取最高置信度） | **灵敏度实验**：Noisy-OR（`1 - prod(1 - C_i)`），在主实验完成后单独运行 |
| `C-2` | Workload C | Top-K 排名逻辑的执行层级 | **Harness 层统一处理原则**：Top-K 排名由 benchmark harness 统一执行，对所有三个 baseline 完全相同，不作为任何单一 baseline 的例外处理。这是公平性原则，避免对任何引擎出现特殊优待或特殊惩罚。 | 无 |

### 5.13 Smoke Test Execution Order

在进入完整 benchmark 执行之前，先按以下顺序跑一轮 smoke test。Smoke test 的目的是验证 harness 本身是否工作正常，而不是做 go/no-go 决策。

**执行顺序**

1. **Workload C 优先**
   与当前系统的 `CandidateSet / audit / provenance` 主线最接近，最容易在早期暴露 bridge contract 和结果归一化的问题。优先跑 C 可以在不涉及递归闭包或时序语义的情况下，先把 harness 管道打通。

2. **Workload A 第二**
   在 harness 已验证可用之后，验证 Souffle 的结构推理优势是否能在端到端流程中实际体现。此 workload 的结果将直接影响 Gate 1 和 Gate 3 的评估。

3. **Workload B 最后**
   时序语义最容易把讨论重新拉回"时间是否应该进入 kernel"这一更大的架构问题。在前两个 workload 稳定之后再运行 B，可以把时序语义问题控制在有据可查的实验结果范围内，而不是重新变成开放式讨论。

**Smoke test 的三个验证目标**

Smoke test 不执行完整的 go/no-go 检查，只验证以下三点：

1. runner contract 是否能稳定地为三个 baseline 产出统一的归一化 JSON 输出（结构完整、字段齐全、无异常终止）？
2. `unsupported_features` 报告是否足够清晰，能让人在不读引擎日志的情况下理解哪些语义被降级处理了？
3. provenance completeness 检查逻辑是否在三个 baseline 上表现一致、可复用，没有对特定引擎的隐式假设？

**注意**

Smoke test 不是 go/no-go 决策点。Go/no-go 决策依据第 5.11 节的 Gate 标准，仅在完整 benchmark 运行结束后作出。Smoke test 通过仅说明 harness 可用于完整运行，不对任何 baseline 的能力作出任何判断。

### 5.14 Current Observed Benchmark Outcomes

截至当前 scoped spike，三个 workload 都已经有可复核的 benchmark-only 结果，可用于约束后续讨论边界。

#### Observed Results Summary

| Baseline / Signal | Workload A | Workload B | Workload C |
| --- | --- | --- | --- |
| `ProbLog` | `Gate 1` 失败信号成立：`1x` 上在 `30s` timeout 内零产出 | 尚未实现，当前为占位结果 | 正常产出，smoke 级 wall-clock 约 `0.36s` |
| `souffle_proto` | 约 `6.29s`，`38,417` reachable pairs，matches golden，provenance completeness `1.0` | sub-second (`~0.30-0.43s`)；`100/100` entity results matches golden，`1288/1288` provenance completeness | 约 `0.07s`，`504` raw candidates，Top-50 matches golden，provenance completeness `1.0` |
| `souffle_full_a` | 明确负结论：约 `155.6s`，比 `souffle_proto` 慢约 `25x` | N/A | N/A |
| `annotation_kernel` role | `required = true`：R3/R4 的 `min-max` 置信度聚合由 Python DP 承担，且不是瓶颈 | `noop = true`：时间步传播与优先级裁决全部在 `Souffle` 内完成 | `required = true`：evidence aggregation / ranking 仍由 harness / kernel 层统一承担 |
| Gate status | `Gate 1` 对 `ProbLog` 的失败信号已足够强 | `Gate 2` 暂阻塞：`PyReason bridge v0` 仍未接通 | smoke / harness correctness 已验证 |

#### Working Conclusions

1. `annotation_kernel_noop = true` 已由 `Workload B` 实证支持。对 bounded temporal propagation 而言，只要时间步有界且优先级裁决可在 `Souffle` 内编码，annotation kernel 不需要承担运行时语义。
2. `annotation_kernel_required = true` 已由 `Workload A` 和 `Workload C` 实证支持。前者需要 kernel 层的 `min-max` 聚合，后者需要统一的证据聚合与 Top-K harness 逻辑。
3. `gate2_blocked_by_pyreason_bridge = true` 是当前真实状态。`PyReason` 还没有进入可比较状态，因此当前只能对 `Gate 1` 和部分 `Gate 3` 给出有力信号，不能宣称 `Gate 2` 已完成评估。

#### Implication For Next Step

当前文档状态已经足够支撑一个明确的分叉决策：

- 若优先追求 prototype momentum，应基于现有 `souffle_proto` 结果进入下一轮 prototype blueprint；
- 若优先追求 baseline completeness，应先解除 `PyReason bridge` 阻塞，再补完 `Gate 2`。

在 `PyReason bridge` 仍为阻塞项之前，不应把当前结果表述为“三基线最终结论”；更准确的说法是：“`Souffle-backed` 路线已经拿到强正信号，而 `PyReason` 路线尚未完成公平评估。”

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `Souffle` 仍然是结构执行器，不应被重新包装成“完整概率/时序语义引擎”。
  - annotation 语义若进入 runtime，必须进入 `core`，不能只停留在单个 adapter 私有实现。
  - `CandidateSet` / accept / audit / provenance 的统一出口不应被破坏。
- baseline 对照必须公平：
  - 同一组代表性 workload
  - 同一组 correctness / audit 检查点
  - 不允许只拿最有利于目标方案的 case 做结论
- bridge contract 必须保持内部/实验性：
  - 不得在 baseline 阶段直接修改 v1 public contract
  - 不得把 `pyreason` 直接加入当前正式 `EvaluateMode`
  - 不得为了 baseline 提前扩张 `CandidateSet` 稳定结构
- 明确不做的内容：
  - 不直接把 `ProbLog` 或 `PyReason` 作为“兼容目标”来设计 API。
  - 不在没有最小 annotation algebra 的前提下讨论 service/UI 侧产品表现。
  - 不把“高性能”当作先验结论；性能必须来自明确的 benchmark 或对照实验。
- 兼容性约束：
  - 任何未来 hybrid 方案都必须保留现有 `native | souffle | problog` 的最小可运行路径。
  - 任何新增 annotation contract 都必须能解释如何映射回现有 `CandidateSet` 和 audit 模型。

## 7. Acceptance

- [x] 已形成一份独立于母蓝图的 `Souffle-backed annotation kernel` 子蓝图
- [x] 蓝图已明确区分 `Souffle` 结构职责与 annotation kernel 语义职责
- [x] 蓝图已限定“可靠子集”，没有暗含完整兼容 `ProbLog` / `PyReason`
- [x] 已把 `PyReason` / `ProbLog` / `Souffle + 最小 annotation prototype` 三个 baseline 明确写入比较框架
- [x] 已明确 `PyReason` baseline 通过内部 bridge contract 接入，而不是直接扩张 v1 正式契约
- [x] 已给出 `PyReason bridge v0` 的最小职责和非目标
- [x] 已写入 workload matrix 与 `provisional spike gate`
- [x] 母蓝图已引用该子蓝图，避免主题继续堆叠到同一文档

## 8. Implementation Plan

1. 建立本子蓝图 draft，收口讨论目标、边界和关键问题。
2. 把 `PyReason` 直跑、`ProbLog` 单引擎直跑、`Souffle + 最小 annotation prototype` 写成明确 baseline，并约定评估顺序与 go / no-go 标准。
3. 在母蓝图中增加对子蓝图的引用，把该方向从 umbrella discussion 中拆出。
4. 后续若决定进入 prototype，再基于本蓝图单独创建 scoped implementation blueprint。

## 9. Docs To Update

- `docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md`
- `docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.audit.md`
- `docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 三个 workload 的 benchmark-only 工具链均已落地并形成可复核结果：输入生成、runner、golden/reference、compare harness、provenance completeness 检查全部可运行。
  - `souffle_proto` 在 `Workload A / B / C` 上都通过了正确性验证：
    - `A`: 约 `6.29s`，`38,417` reachable pairs，matches golden，provenance completeness `1.0`
    - `B`: 约 `0.30-0.43s`，`100/100` entity results matches golden，`1288/1288` provenance completeness
    - `C`: 约 `0.07s`，`504` raw candidates，Top-K / provenance 检查通过
  - `Gate 1` 的失败信号已成立：`ProbLog` 在 `Workload A` 的 `1x` fixture 上 `30s` timeout 内零产出。
  - annotation kernel 的角色已得到 workload 级别实证：
    - `Workload A + C`: `annotation_kernel_required = true`
    - `Workload B`: `annotation_kernel_noop = true`

- 与 blueprint 不同的地方：
  - 在原始三 baseline 之外引入了 `souffle_full_a` benchmark-only 附加变体，用于测试“让 `Souffle` 原生承接 R1-R4 是否更优”。
  - `PyReason bridge v0` 没有在本 spike 内接通，因此 `Gate 2` 未完成公平评估。
  - `Workload B` 的 `souffle_proto` 实现从最初的通用递归 relation 方案，调整为显式 bounded-time unrolling，以规避 `Souffle` 的 cyclic aggregation stratification 限制。

- 为什么会有这些调整：
  - `souffle_full_a` 是 `Workload A` 实验中自然增长出的关键对照项；它给出了明确负结论，显著降低了“让 `Souffle` 原生承接全部 annotation 语义”这条路线的不确定性。
  - `PyReason bridge` 的实现成本与契约映射复杂度已超出本次 benchmark-only spike 的合理边界；在没有更窄的 bridge blueprint 前，继续推进会稀释本 spike 的判断力。
  - `Workload B` 的显式 unrolling 不是语义退让，而是让“优先级裁决完全留在 `Souffle` 内部”这一实验目标可执行的工程化实现。

- 归档说明：
  - 本 spike 的核心问题已经得到足够清晰的实证回答：`Souffle + annotation kernel` 的分层方案在当前代表性 workload 上是靠谱的，但其价值具有 workload 依赖性，而不是普遍优于所有单引擎基线。
  - `Gate 2` 当前仍被 `PyReason bridge v0` 阻塞；该阻塞不影响本 spike 自身结论成立，但意味着“PyReason 是否已足够好从而提前终止第三路线”仍需后续独立工作回答。
  - 因此，本蓝图已达到“implemented / ready to archive”状态；后续若继续推进，应新开独立蓝图处理 `PyReason bridge` 或 prototype 化，而不是继续在本 spike 文档内扩写。
