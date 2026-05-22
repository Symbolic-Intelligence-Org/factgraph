# Task Blueprint Audit: Souffle Annotation Kernel Prototype

- Blueprint: [2026-03-17_souffle-annotation-kernel-prototype.md](./2026-03-17_souffle-annotation-kernel-prototype.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Follow-up prototype blueprint opened after the archived spike established positive signals for `Workload A + C` and a `noop` boundary for `Workload B`. |
| 2026-03-17 | scoped | Scope freeze for first implementation round | Fixed the prototype landing zone to `src/factpy_kernel/core/annotation/` and chose explicit A/C capabilities over an upfront generic algebra. |
| 2026-03-17 | scoped | First capability implemented | Added `core/annotation/` with the `min-max` path-confidence capability, switched `Workload A / souffle_proto` to the new implementation, and kept benchmark reference code frozen as oracle. |
| 2026-03-17 | scoped | Workload C prototype capability implemented | Replaced the `_evidence.py` stub with an independent raw-candidate/provenance implementation and switched `Workload C / souffle_proto` to consume the prototype instead of oracle helpers. |
| 2026-03-17 | implemented | Step 4 close-out completed | Documented provenance summary schemas, checked acceptance, and marked the prototype blueprint implemented without adding a separate prototype entrypoint module. |

## Decision Notes

- 2026-03-17: 本蓝图不再把 `PyReason bridge` 作为 prototype 前置条件。`Gate 2` 仍是未完成问题，但不阻止当前 prototype 路线推进。
- 2026-03-17: 第一轮 prototype 只覆盖 `Workload A + C`；`Workload B` 已给出 `annotation_kernel_noop` 结论，不纳入当前实现边界。
- 2026-03-17: benchmark harness 保留为回归标准，而不是在 prototype 阶段被一次性替换掉。
- 2026-03-17: 第一轮 prototype 的具体模块落点固定为 `src/factpy_kernel/core/annotation/`，避免实现开始后再次讨论“放在哪里”。
- 2026-03-17: Step 1 的默认设计倾向固定为“先做两个显式 capability，再视重复结构决定是否抽象共享 algebra”，不以通用 annotation 框架作为起手式。
- 2026-03-17: `Workload A` 的 oracle 与 prototype 已明确分层：
  - `tools/benchmarks/workload_a_reference.py` 保持为冻结 oracle；
  - `src/factpy_kernel/core/annotation/_min_max.py` 作为新的 prototype 实现；
  - `tools/benchmarks/bench_runner.py` 的 `souffle_proto` 路径已切换为调用 prototype，而不是继续直接依赖 oracle 代码。
- 2026-03-17: `Workload C` 采用同样的 oracle / prototype 分层：
  - `tools/benchmarks/workload_c_reference.py` 继续作为 oracle；
  - `src/factpy_kernel/core/annotation/_evidence.py` 承担 prototype 实现；
  - `Workload C / souffle_proto` 仅切换到 prototype 的直接证据展开与 provenance 重建，不改变 Top-K 仍由 harness 统一处理的公平性原则。
- 2026-03-17: Step 4 的收口判断是“不新增单独 entrypoint 模块”。当前 `bench_runner.py + core.annotation` 的组合已经足够充当 prototype execution slice，因此继续增加一层入口不会提升验证质量，只会增加抽象表面积。
