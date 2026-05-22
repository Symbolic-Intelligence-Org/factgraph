# Task Blueprint: Souffle Annotation Kernel Prototype

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/adapters`
  - `tools/benchmarks`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
  - [docs/blueprints/archive/2026-03-16_souffle-annotation-benchmark-spec.md](../archive/2026-03-16_souffle-annotation-benchmark-spec.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/adapters/docs/01_souffle_adapter.md](../../../src/factpy_kernel/adapters/docs/01_souffle_adapter.md)
- Audit Log:
  - [2026-03-17_souffle-annotation-kernel-prototype.audit.md](./2026-03-17_souffle-annotation-kernel-prototype.audit.md)

## 1. Problem

上一轮 spike 已经给出足够清晰的 benchmark 结论：

- `Souffle + Python annotation kernel` 的分层方案在 `Workload A` 和 `Workload C` 上有实际价值；
- `ProbLog` 在递归闭包主导场景下不足以成为默认主路线；
- `Workload B` 中 annotation kernel 是 `noop`，说明 prototype 不应一开始把时序语义纳入实现范围。

现在的缺口不再是“方向是否成立”，而是：

- 如何把 benchmark-only 的验证代码收敛成一个最小 prototype；
- 如何把已证明有价值的 annotation 语义沉淀成内部实现结构；
- 如何在不破坏现有 `Store.evaluate(...)` / `CandidateSet` / SDK/service 契约的前提下，把这条路线推进到可持续迭代的原型状态。

## 2. Goals

- 实现一个 **最小的内部 prototype**，覆盖 spike 已证实有价值的两个场景：
  - `Workload A`: `min-max` 路径置信度传播
  - `Workload C`: 结构候选 + 证据聚合 / Top-K 前的 annotation 合并
- 将现有 benchmark helper 中的核心 annotation 逻辑整理成可复用的 prototype 模块，而不是继续只停留在 `tools/benchmarks`。
- 保持 `Souffle` 只承担结构推理职责；annotation 语义由 prototype kernel 承担。
- 为后续是否进入正式 runtime 集成建立更清晰的内部 API 和模块边界。
- 让 benchmark 结果可以作为 prototype 回归标准，而不只是一次性实验。

## 3. Non-goals

- 不实现 `PyReason bridge`。
- 不在本蓝图中覆盖 `Workload B` 的时序传播 productization；该场景已被证实为 `annotation_kernel_noop`。
- 不修改正式 `Store.evaluate(...)`、`EvaluateMode`、`CandidateSet`、SDK 或 service 对外契约。
- 不实现通用 planner / staged execution 框架。
- 不追求完整兼容 `ProbLog` 或 `PyReason` 的语义系统。

## 4. Current Context

- 当前实现入口：
  - benchmark-only runner 已经存在于 `tools/benchmarks/bench_runner.py`。
  - `Workload A/B/C` 的 reference、compare、fixture、golden 都已齐备。
- 当前已知约束：
  - benchmark 代码能证明方向，但不是可维护的系统内 prototype 形态。
  - 现有 `core` 仍是单 mode runtime；本轮 prototype 不应直接把 benchmark 逻辑硬塞进正式执行入口。
  - `Workload B` 已给出负边界：annotation kernel 不应在 prototype 第一轮里承担时序语义。
- 当前相关历史蓝图：
  - [docs/blueprints/archive/2026-03-16_souffle-backed-annotation-kernel-spike.md](../archive/2026-03-16_souffle-backed-annotation-kernel-spike.md)
    - 已提供 go/no-go、workload 结果和边界。
  - [docs/blueprints/archive/2026-03-16_souffle-annotation-benchmark-spec.md](../archive/2026-03-16_souffle-annotation-benchmark-spec.md)
    - 已提供 prototype 回归所需的 benchmark 规格。

## 5. Proposed Shape

### 5.1 Prototype Positioning

本轮要实现的不是正式产品功能，而是一个 **内部 prototype execution slice**：

- `Souffle` 负责结构推理子问题
- prototype annotation kernel 负责 `Workload A + C` 已验证过的 annotation 合并语义
- benchmark harness 继续作为回归和对照工具，而不是被删除

### 5.2 Prototype Scope

第一轮 prototype 只实现两个 annotation capability：

1. `min_max_path_confidence`
   - 输入：结构闭包 / 图边权
   - 输出：带置信度的路径结论
   - 来源：`Workload A` 的 Python DP 参考实现

2. `max_evidence_aggregation`
   - 输入：结构候选 + 直接证据
   - 输出：归一化 annotation 值与 support/provenance 摘要
   - 来源：`Workload C` 的 evidence aggregation / ranking 前逻辑

### 5.3 Expected Module Shape

预期至少引入一个内部 prototype 落点，用于承载 annotation 语义，而不是继续让 benchmark helper 同时承担“参考实现”和“唯一实现”两种职责。

建议形状：

- `src/factpy_kernel/core/annotation/`
  - 新增 internal / prototype annotation kernel 落点，先承接 `Workload A + C` 的最小 capability，不承诺直接进入稳定 public surface
- `src/factpy_kernel/adapters/...`
  - 保持 `Souffle` 仍然只作为结构执行后端
- `tools/benchmarks/...`
  - 保留 generator / compare / fixture / golden
  - benchmark helper 尽量退回“参考实现 / 验证器”角色

### 5.4 Execution Boundary

本 prototype 默认不进入正式 `Store.evaluate(...)` 路径。更合理的第一步是：

- 提供一个内部 prototype entrypoint
- 能消费 benchmark 级输入或受控内部 DTO
- 产出可与 benchmark compare harness 对齐的结果形态

也就是说，先证明“prototype 代码可替代 benchmark helper 的核心语义”，再讨论它是否值得进入正式 runtime。

### 5.5 Key Design Questions

本蓝图要回答的实现问题是：

1. `Workload A` 与 `Workload C` 的 annotation 逻辑，最小公共抽象应该是什么？
   - 当前倾向：先做两个显式 capability（`min_max_path_confidence` 与 `max_evidence_aggregation`），只抽出最小共享 carrier / helper，不先设计通用 annotation algebra。
2. prototype kernel 应该以“通用 annotation algebra”组织，还是先做两个显式 capability？
   - 当前默认答案：先做两个显式 capability；只有当 Step 2/3 出现明确重复结构，再反向提炼共享抽象。
3. support / provenance 摘要在 prototype 层如何表达，才能既满足 benchmark compare，又不提前污染正式 audit contract？
4. benchmark 参考实现与 prototype 实现之间，如何保持清晰分工，避免一份代码既当 oracle 又当 production candidate？

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `Workload B` 不进入本轮 prototype 主实现范围。
  - `Souffle` 仍然只负责结构推理，不承担完整 annotation 语义。
  - benchmark harness 保留，作为 prototype 回归基线。
  - prototype 不得直接修改正式 public contract。
- 明确不做的内容：
  - 不把 `PyReason bridge` 夹带进本蓝图。
  - 不把 `souffle_full_a` 负结论路径重新包装进 prototype。
  - 不先做通用 planner，再回头找用例。
- 兼容性约束：
  - 任何 prototype 模块都必须说明如何与现有 benchmark fixtures / golden 对齐。
  - 任何新增内部 DTO 都不得假定已经进入 `CandidateSet` 稳定结构。

## 7. Acceptance

- [x] 已有一个清晰的内部 prototype 落点，承接 `Workload A + C` 的 annotation 语义
- [x] `Workload A` 的 prototype 路径能复现实验中已验证的 `min-max` 结果
- [x] `Workload C` 的 prototype 路径能复现实验中已验证的 evidence aggregation 结果
- [x] benchmark harness 仍可作为 prototype 的回归标准
- [x] 没有越过 blueprint 明示的边界，尤其没有把 `Workload B` / `PyReason bridge` 混入实现
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 明确 prototype 落点与最小内部 contract，决定哪些 benchmark helper 应上移到系统内模块。
2. 先把 `Workload A` 的 `min-max` annotation 逻辑迁入 prototype 实现，并用现有 golden / compare 验证等价性。
3. 再把 `Workload C` 的 evidence aggregation 逻辑迁入 prototype 实现，并保持 Top-K 仍在 harness 层统一处理。
4. 收口 prototype 的 support / provenance 摘要形态，并更新对应模块 docs。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
- 新 prototype 模块的 `docs/README.md`（若新增模块目录）

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增了 `src/factpy_kernel/core/annotation/` internal prototype 模块，作为 `Workload A + C` annotation 能力的系统内落点。
  - `Workload A` 的 `min-max` 路径置信度传播已从 benchmark helper 迁入 `core/annotation/_min_max.py`，并接管 `Workload A / souffle_proto` 的 prototype 路径。
  - `Workload C` 的直接证据展开、结构候选 provenance 重建与 `max` 聚合 helper 已从 benchmark helper 迁入 `core/annotation/_evidence.py`，并接管 `Workload C / souffle_proto` 的 prototype 路径。
  - benchmark harness 继续保留为 oracle / compare / regression 基线；A/C 的真实 fixture 都已重新跑通并保持与 golden 完全一致。

- 与 blueprint 不同的地方：
  - §5.4 中原本预留了“单独的内部 prototype entrypoint”这一可能性，但最终没有新增专门 entrypoint 模块。
  - 相反，本轮直接采用了“`bench_runner.py` 作为 prototype execution slice，`core.annotation` 作为 prototype capability provider”的组合。

- 为什么会有这些调整：
  - 当前阶段的核心目标是把 benchmark-only 逻辑迁出 oracle helper，形成可维护的系统内 prototype；为此再新增一层 entrypoint 模块只会增加中间抽象，而不会带来额外验证价值。
  - `bench_runner.py` 已经能够消费 benchmark payload、调用 prototype capability、并产出与 compare harness 对齐的结果，因此它已经满足当前“prototype entrypoint”的实际职责。
  - 在还没有决定是否进入正式 runtime 集成前，保持 prototype execution slice 最薄更符合本轮边界。

- 归档说明：
  - 本蓝图的 prototype 目标已完成，可以进入 `implemented / ready to archive` 状态。
  - 若后续继续推进，应单独开新蓝图处理以下任一主题：
    - 是否把 prototype 进一步接入正式 `Store.evaluate(...)`
    - 是否实现 `PyReason bridge`
    - 是否把当前两个显式 capability 提炼成更稳定的共享 annotation contract
