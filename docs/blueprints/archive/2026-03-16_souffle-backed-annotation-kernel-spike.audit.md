# Task Blueprint Audit: Souffle-backed Annotation Kernel Spike

- Blueprint: [2026-03-16_souffle-backed-annotation-kernel-spike.md](./2026-03-16_souffle-backed-annotation-kernel-spike.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-16 | draft | Blueprint created | Split the Souffle-backed annotation kernel discussion out of the temporal hybrid mother blueprint to keep scope bounded. |
| 2026-03-16 | scoped | Workload C smoke implementation started | Scope tightened to a benchmark-only runner slice: unified JSON contract, unsupported feature reporting, and provenance completeness entrypoint for Workload C. |
| 2026-03-16 | scoped | Workload B souffle_proto implementation completed | Added bounded-time Souffle runner, reference/golden harness, compare script, and tests; verified `annotation_kernel_noop = true` on the 1x smoke fixture. |
| 2026-03-16 | scoped | Cross-workload outcome summary recorded | Consolidated A/B/C benchmark-only results into blueprint conclusions, including `annotation_kernel_required` vs `annotation_kernel_noop` split and explicit `Gate 2` blockage by the unfinished PyReason bridge. |
| 2026-03-17 | implemented | Blueprint close-out completed | Filled Section 10, checked acceptance items, and marked the spike implemented/ready-to-archive; no new runtime scope added. |

## Decision Notes

- 2026-03-16: 该主题不再继续堆叠到 `2026-03-16_temporal-hybrid-reasoning-blueprint.md` 主文中；主文保留 umbrella 角色，子蓝图专门收口 `Souffle` 底座 + annotation kernel 的可行性。
- 2026-03-16: 明确采用 baseline-first 策略。`Souffle-backed annotation kernel` 不是默认优选方案，必须先与 `PyReason` 直跑和 `ProbLog` 单引擎直跑进行对照，才能决定是否值得进入正式实现。
- 2026-03-16: `PyReason` baseline 不直接推动正式 contract 扩张。先通过内部 bridge contract 做输入快照、结果归一化和 unsupported feature 报告；只有 baseline 结果通过后，才讨论哪些概念需要进入 `core` 正式语义。
- 2026-03-16: 为避免 baseline 阶段继续漂移，补充 `PyReason bridge v0` 最小职责：`baseline input snapshot`、`normalized baseline result`、`unsupported feature report`。该 bridge 仅服务对照实验，不作为正式 API 承诺。
- 2026-03-16: 补充三类 workload matrix 和 `provisional spike gate`。当前默认规模采用：A=`500-2000 facts / 10-30 recursive rules`，B=`100 entities x 20 time steps x 15 transition rules`，C=`1000 deterministic facts + 200 probabilistic evidence facts + 50-200 ranked candidates`。这些数值用于早期 go / no-go，而不是长期性能承诺。

- 2026-03-16 (讨论轮次：benchmark spec 终稿与决策点确认)
  - 本轮讨论将三个 workload 的描述从"矩阵占位"推进为"最小可执行规格"，并确认了全部 7 个决策点。
  - 已创建独立操作性规格文档：[`2026-03-16_souffle-annotation-benchmark-spec.md`](./2026-03-16_souffle-annotation-benchmark-spec.md)
  - 已在蓝图中新增 `5.12 Benchmark Spec Reference` 节，存档所有确认决策点并引用规格文档。

  **已确认的 7 个决策点**

  | 编号 | 决策内容 | 确认值 |
  | --- | --- | --- |
  | `D-1` | 全局随机种子 | `seed=42`，固定不变 |
  | `A-1` | Workload A 路径置信度代数 | 主实验：min-max；灵敏度分析：乘法-max（主实验完成后单独运行） |
  | `B-1` | Workload B 是否使用 NAF | 不使用；状态持续规则改为无条件持续，以保证 Souffle/PyReason/ProbLog 三方语义可比性 |
  | `B-2` | PyReason 是否允许使用原生时间步语义 | 允许；结果中须标注 `native_temporal_advantage: true` |
  | `B-3` | Workload B 状态数量 | 固定 3 种：`active`、`inactive`、`degraded` |
  | `C-1` | Workload C 置信度聚合方式 | 主实验：max；灵敏度分析：Noisy-OR（主实验完成后单独运行） |
  | `C-2` | Top-K 排名执行层级 | Harness 层统一执行，对所有三个 baseline 完全相同（见下方关键澄清） |

  **关键澄清：C-2 的修订**

  C-2 在讨论过程中经过一次重要修订。初始提案为"允许 ProbLog 将 Top-K 排名放到 Python post-processing 层，并在 `unsupported_features` 中记录"，即把排名处理作为 ProbLog 的一项例外处理。

  用户明确反对这种表述，理由是：将 Top-K 排名作为某一特定 baseline 的例外处理，会在视觉上制造"ProbLog 需要额外帮助才能完成排名"的印象，即使其他 baseline 实际上也需要在 harness 层处理排名。

  **修订结论**：Top-K 排名统一升格为 harness 层的公平性原则，适用于所有三个 baseline，不作为任何单一 baseline 的例外记录。这一修订已在蓝图 5.12 节的 C-2 决策点说明中体现，并写入 benchmark spec 的 Section 3.2 规则说明。

- 2026-03-16 (讨论轮次：smoke test 执行顺序确认)
  - 确定在完整 benchmark 执行前先运行一轮 smoke test，入口为 Workload C + baseline runner。
  - 已在蓝图中新增 `5.13 Smoke Test Execution Order` 节。

  **执行顺序及理由**

  | 顺序 | Workload | 理由 |
  | --- | --- | --- |
  | 1 | C | 与当前系统 `CandidateSet / audit / provenance` 主线最接近；优先跑可在不引入递归或时序语义的情况下验证 harness 管道 |
  | 2 | A | harness 已验证后，测试 Souffle 结构推理优势能否在端到端流程中实际体现；直接关联 Gate 1 和 Gate 3 |
  | 3 | B | 时序语义最容易引发更大范围的架构讨论；放到最后可将其限制在有实验结果支撑的范围内 |

  **Smoke test 的三个验证目标**（均为 harness 自身验证，不涉及 go/no-go 判定）

  1. Runner contract 能否为三个 baseline 稳定产出结构完整的归一化 JSON 输出
  2. `unsupported_features` 报告是否清晰到不需要读引擎日志即可理解降级原因
  3. Provenance completeness 检查逻辑是否在三个 baseline 上表现一致、无隐式引擎假设

  Smoke test 通过仅说明 harness 可用于完整运行，不对任何 baseline 的能力作出判断。Go/no-go 决策依据 5.11 节 Gate 标准，仅在完整 benchmark 运行后作出。

- 2026-03-16 (讨论轮次：Workload C smoke 实现启动)
  - 蓝图状态从 `draft` 切换为 `scoped`，因为接下来将进入多文件实现。
  - 本轮实现目标刻意压缩为 benchmark-only 代码路径：
    - 独立 runner contract
    - Workload C 输入生成 / 归一化输出
    - `problog` / `souffle_proto` 的最小执行路径
    - `pyreason` bridge stub 与清晰的 `unsupported_features`
  - 明确本轮不修改正式 `Store.evaluate(...)`、`EvaluateMode`、`CandidateSet` 或 service / SDK v1 contract。

- 2026-03-16 (讨论轮次：Workload C smoke harness 闭环)
  - 在 runner 基础上继续补齐 benchmark-only 闭环：
    - `generate_workload_c.py` 生成固定 seed 输入
    - Python 参考实现生成 golden output
    - `compare_workload_c.py` 执行 max 聚合、Top-K、provenance completeness 和 golden diff
  - 该扩展仍限定在 `tools/benchmarks`，不回流 `core` 或正式 adapter contract。

- 2026-03-16 (讨论轮次：Workload A 语义口径确认)
  - `Workload A` 的 golden/reference 固定采用 `min-max` 语义，作为 benchmark 的正确性锚点。
  - `Souffle proto` 不走完整路径枚举；实现口径固定为 `Souffle` 执行 R1/R2 结构闭包，Python 侧以精确 DP / widest-path 方式实现 `min-max` 语义。
  - `ProbLog` baseline 不强行拟合 `min-max`；其输出保留 possible-world 概率语义。与 golden 的 `confidence delta` 视为语义差异信号，而不是实现 bug。
  - 若后续探索 `Souffle` 原生执行 R3/R4，应作为独立附加实验（例如 `souffle_full_a`），不改变当前 `souffle_proto` 基线含义。

- 2026-03-16 (讨论轮次：Workload A Gate 1 初步结论)
  - `ProbLog` 在 `Workload A` 的 `1x` fixture 上已在 30s timeout 内未产出结果，而 `souffle_proto` 在同规模上完成并匹配 golden。
  - 该结果已构成足够强的 Gate 1 失败信号；当前阶段不再优先推进 `2x/5x` 扩规模。
  - 下一步转向 `souffle_full_a` 附加实验，专门评估若 `Souffle` 原生执行 R3/R4，则 Python annotation kernel 在该场景下是否成为纯开销。

- 2026-03-16 (讨论轮次：Workload A `souffle_full_a` 附加实验结果)
  - 在与 `souffle_proto` 相同的 `Workload A 1x` fixture 上，`souffle_full_a` 最终完成，但 wall-clock 约为 `155.57s`，峰值内存约 `90.16 MB`。
  - 同一 fixture 下，`souffle_proto` 已在约 `6.29s` 内完成并匹配 golden，峰值内存约 `81.23 MB`。
  - 当前信号表明：在该场景中，`Souffle` 原生承接 R3/R4 的递归浮点 + 聚合代价显著高于“`Souffle` 结构闭包 + Python 精确 DP”分层实现；Python annotation kernel 不是瓶颈，反而可能是更实用的工程切分点。

- 2026-03-16 (讨论轮次：Workload B 实现口径确认)
  - `Workload B` 先只要求 `souffle_proto` 路径可跑，用于验证“时间步传播是否已可完全由 Souffle 原生 Datalog 承担”。
  - 语义口径采用三层关系：
    - `state_candidate(E,T,S,P,RuleId,Helper)`
    - `best_priority(E,T,P)`
    - `state(E,T,S)`
  - 优先级在 `Souffle` 内部归约完成，Python compare/harness 不承担最终状态裁决语义。
  - `T1` 固定最低优先级；`T2/T3` 规则实例使用全局唯一 `rule_id`，并以此作为优先级，避免同一 `(entity,timestep)` 上的同优先级歧义。
  - `T3` 同一规则实例因多个 `E2` 绑定产生的重复候选被视为集合语义下的重复 tuple；若 provenance 输出存在多条 helper 见证，compare 只要求事件键存在且 trigger entities 合法。

- 2026-03-16 (讨论轮次：Workload B `souffle_proto` 实装与 smoke 结果)
  - 初始实现若直接使用通用 `state_candidate/best_priority/state` 递归 relation，会触发 `Souffle` 的 cyclic aggregation stratification error。
  - 最终实现改为显式 bounded-time unrolling：为每个 `t=1..Tmax` 生成独立的 `state_candidate_t / best_priority_t / state_t` relation，再汇总到统一的 `state(entity,timestep,status)` 和 `provenance(...)` 输出。
  - 该实现仍保持 Workload B 的核心判断不变：
    - 优先级裁决完全在 `Souffle` 内部完成；
    - compare/harness 只验证，不承担状态裁决语义；
    - `annotation kernel` 在此 workload 中为 `noop`。
  - `1x` smoke 结果：
    - fixture: `100 entities x 20 time steps`, `seed=42`
    - baseline: `souffle_proto`
    - wall-clock: `~0.295s`
    - peak memory: `~9.892 MB`
    - final result rows: `100`
    - provenance rows emitted: `9080`
    - golden diff: 完全一致
    - provenance completeness: `1288 / 1288 = 1.0`

- 2026-03-16 (讨论轮次：三 workload 收口结论)
  - `Workload A`
    - `ProbLog` 在 `1x` 上已构成足够强的 `Gate 1` 失败信号：`30s` timeout 内零产出。
    - `souffle_proto` 为当前主路径：约 `6.29s`，`38,417` reachable pairs，matches golden。
    - `souffle_full_a` 为负结论：约 `155.6s`，较 `souffle_proto` 慢约 `25x`，说明 Python DP 不是该场景瓶颈。
  - `Workload B`
    - `souffle_proto` 的 `1x` smoke 已实证支持 `annotation_kernel_noop = true`：bounded temporal propagation 与优先级裁决均可在 `Souffle` 内完成。
  - `Workload C`
    - smoke harness 已验证 unified runner / normalized result / provenance completeness 检查可稳定复用。
  - 跨 workload 收口判断：
    - `annotation_kernel_required = true`：由 `Workload A + C` 支持；
    - `annotation_kernel_noop = true`：由 `Workload B` 支持；
    - `gate2_blocked_by_pyreason_bridge = true`：`PyReason bridge v0` 未接通前，`Gate 2` 只能保持“暂阻塞”状态，而不能被宣称为通过或失败。

- 2026-03-17 (讨论轮次：蓝图结项维护)
  - 根据当前实证范围，`Gate 2` 的阻塞并不削弱本 spike 自身的结论价值；它只说明 `PyReason` 路线仍需独立 bridge 工作。
  - 因此本蓝图选择标记为 `implemented`，而不是继续维持 `scoped`：
    - benchmark-only spike 目标已经完成；
    - 后续工作若继续，应拆成新的实现蓝图，而不是继续在本蓝图中扩 scope。
