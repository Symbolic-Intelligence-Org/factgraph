# Task Blueprint: PyReason Node-Edge Channel Split

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/tests/test_pyreason_runner.py`
  - `src/factpy_kernel/tests/test_pyreason_rule_ext.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-28_pyreason-graph-fact-materialization-fix.md](../archive/2026-03-28_pyreason-graph-fact-materialization-fix.md)
- Audit Log:
  - [2026-03-28_pyreason-node-edge-channel-split.audit.md](./2026-03-28_pyreason-node-edge-channel-split.audit.md)

## 1. Problem

The previous PyReason runner fix moved all session facts from graph attributes to `add_fact(...)`. Real-engine follow-up indicates that this was only half-correct:

- node labels should go through explicit facts
- edge labels should remain graph attributes

This means the adapter must split node and edge facts across two PyReason input channels instead of treating them uniformly.

## 2. Goals

- encode edge facts back into graph edge attributes
- keep node facts on the explicit `add_fact(...)` path
- update tests and docs to reflect the split

## 3. Non-goals

- do not add new compiler constraints such as head-in-body validation without upstream proof
- do not redesign `engine_eval` or schema contracts
- do not modify annotation or accept behavior

## 4. Current Context

- `runner.build_pyreason_graph(...)` currently builds structure only
- `_session_fact_records(...)` currently lowers both node and edge facts to explicit facts
- real-engine smoke now shows rule iteration returning, but remaining demo behavior suggests edge labels still need graph attribute transport

## 5. Proposed Shape

- `build_pyreason_graph(...)` keeps nodes plus edges, and writes edge labels as graph attributes
- `_session_fact_records(...)` lowers only node facts to explicit facts
- bounded edge values keep using the lower-bound summary when encoded as graph attributes, matching the already-frozen bounded-materialization compromise

## 6. Boundaries And Invariants

- graph remains the only structure carrier
- node labels remain explicit initial facts
- no new compiler restriction is added in this task

## 7. Acceptance

- [x] edge labels restored as graph attributes
- [x] node facts only are sent through `_session_fact_records(...)`
- [x] runner tests/docs updated

## 8. Implementation Plan

1. update `runner.py` node/edge routing
2. update runner/rule_ext tests
3. update adapter docs and archive the blueprint

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：`runner.build_pyreason_graph(...)` 现在保留 graph 结构并写入 edge-label attributes；`_session_fact_records(...)` 只 lower session node facts 到 `pr.add_fact(...)`。相关测试和 adapter 文档已同步。
- 与 blueprint 不同的地方：无实现范围扩张；仍未添加 head-in-body compiler validation。
- 为什么会有这些调整：本任务只收敛已被真实 PyReason 对照实验验证的 node/edge channel split。head-in-body 约束仍缺少足够的 upstream 证据，保持在 task 外。
- 归档说明：实现完成后归档到 `docs/blueprints/archive/2026-03-28_pyreason-node-edge-channel-split.md`，验证使用 `py_compile` 以及 73 个 runner/e2e 定向测试和 101 个 annotation/session 相关回归测试。
