# Task Blueprint: PyReason Seed Warning And Demo Reframe

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/tests/test_pyreason_rule_ext.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
  - `examples/ecss_pyreason_demo.py`
  - `examples/ecss_pyreason_demo.ipynb`
  - `examples/dora_pyreason_demo.py`
  - `examples/dora_pyreason_demo.ipynb`
  - `examples/README.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-28_pyreason-node-edge-channel-split.md](../archive/2026-03-28_pyreason-node-edge-channel-split.md)
- Audit Log:
  - [2026-03-28_pyreason-seed-warning-and-demo-reframe.audit.md](./2026-03-28_pyreason-seed-warning-and-demo-reframe.audit.md)

## 1. Problem

Real-engine validation now shows a PyReason capability boundary that was not reflected in factpy:

- node facts with explicit non-`[1.0, 1.0]` bounds are accepted as inputs
- but those bounded node seeds do not behave as rule-propagation sources

The adapter should not silently change this behavior, but callers need an explicit warning. The example demos also need to stop presenting PyReason as a fuzzy interval propagation engine and instead demonstrate the boolean/topology propagation pattern the engine actually supports.

## 2. Goals

- warn at runner time when rules are combined with non-default node seed bounds
- keep adapter semantics intact; do not silently coerce bounded seeds to boolean truth
- rewrite ECSS/DORA PyReason demos to boolean propagation narratives
- keep uncertainty information only as side-channel display context in demos
- sync module docs and example index to the new framing

## 3. Non-goals

- do not redesign `PyReasonSession` or shared schema contracts
- do not remove bounded fact support from the adapter
- do not freeze new compiler constraints from this finding
- do not change core annotation / accept behavior

## 4. Current Context

- `runner.run_pyreason(...)` currently lowers node seeds with explicit intervals and gives no warning
- `examples/ecss_pyreason_demo.py` and `examples/dora_pyreason_demo.py` still describe PyReason as fuzzy interval propagation
- recent real-engine experiments show propagation works for boolean seeds but not for non-default bounded node seeds

## 5. Proposed Shape

- add a runner-local warning that fires once per run when:
  - at least one rule is present, and
  - at least one node seed entering `add_fact(...)` has a non-default bound
- document the limitation as an engine boundary in the PyReason adapter docs
- reframe the PyReason demos around boolean label propagation and temporal/topological spread
- retain uncertainty bands in demos only as printed side-channel observations, not as propagation inputs
- update notebook mirrors to match the `.py` examples

## 6. Boundaries And Invariants

- must preserve current bounded fact encoding behavior in the adapter
- must not add silent fallback from bounded seed to boolean seed
- demo changes may change story, labels, and printed summaries, but should remain clearly domain-shaped
- notebooks must stay aligned with the corresponding `.py` files

## 7. Acceptance

- [x] runner emits a clear warning for bounded node seeds + rules
- [x] warning behavior is covered by tests
- [x] ECSS/DORA PyReason demos no longer claim fuzzy bound propagation
- [x] module docs and examples index are updated

## 8. Implementation Plan

1. add warning helpers and tests in the runner layer
2. update adapter docs to make the bounded-seed limitation explicit
3. rewrite ECSS and DORA PyReason demos plus notebook mirrors to boolean propagation
4. validate with targeted unit tests and demo script runs

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- `examples/README.md`

## 10. Outcome / Deviations

- 最终落地结果：`runner.run_pyreason(...)` 现在会在“有规则 + 非 `[1.0, 1.0]` node seed”组合下发出明确 warning；`03_pyreason_adapter.md` 和 `examples/README.md` 已把 bounded seed limitation 固定为显式能力边界；ECSS/DORA PyReason demos 与 notebook 镜像都已改为 boolean/topology propagation 叙事，并把 uncertainty 改成 side-channel 展示。
- 与 blueprint 不同的地方：无范围扩张；adapter 仍保留原始 bounded fact 编码，没有引入任何 silent fallback。
- 为什么会有这些调整：真实引擎验证支持的是“observability + honest demo reframe”，而不是修改 bounded seed 语义本身。
- 归档说明：验证包括 `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_pyreason_rule_ext src.factpy_kernel.tests.test_pyreason_runner`（50 tests 通过）、`py_compile` 校验，以及两个 demo 脚本的 fallback 路径运行。notebook 已做 JSON 结构校验。
