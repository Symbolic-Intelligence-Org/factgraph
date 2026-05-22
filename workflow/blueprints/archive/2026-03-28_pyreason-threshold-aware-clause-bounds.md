# Task Blueprint: PyReason Threshold-Aware Clause Bounds

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/rule_ext.py`
  - `src/factpy_kernel/adapters/pyreason/where_compile.py`
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
  - `examples/ecss_pyreason_demo.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-03-28_pyreason-threshold-aware-clause-bounds.audit.md](./2026-03-28_pyreason-threshold-aware-clause-bounds.audit.md)

## 1. Problem

PyReason real-engine validation has now exposed a narrower root cause for the current bounded-seed behavior than the repo documents today. Non-`[1.0, 1.0]` node seeds do not match PyReason rule bodies under the adapter's current generated syntax because body clauses inherit PyReason's default interval threshold semantics, which effectively require `[1.0, 1.0]` unless a clause interval is written explicitly.

The current repo surface cannot express explicit body-clause intervals, so both adapter-local rule compilation and shared WhereIR compilation force users onto the stricter default. The docs and warning text therefore overstate the engine boundary: the current adapter surface is missing clause-threshold control, but the engine can accept bounded seeds as rule preconditions when explicit clause intervals are emitted.

## 2. Goals

- Add an adapter-supported way to emit explicit body-clause interval thresholds for PyReason rules.
- Keep the change usable from both adapter-local rule defs and the shared evaluate surface.
- Revise warning text and module docs to describe the real boundary precisely.
- Preserve the already-verified materialization split: node labels via `add_fact()`, edge labels via graph attributes.

## 3. Non-goals

- Do not claim or encode that PyReason transports bounded node intervals unchanged into derived head facts.
- Do not change shared DSL semantics outside the PyReason engine-specific extension surface.
- Do not reopen unrelated frozen contracts or redesign value-carrying semantics broadly.

## 4. Current Context

- 当前实现入口：`compile_pyreason_rule(...)` and `compile_where_ir_to_pyreason(...)` emit body atoms without explicit interval suffixes.
- 当前已知约束：`run_pyreason(...)` warns on any non-`[1.0, 1.0]` node seed when rules are present because current generated rules cannot relax body matching.
- 当前相关历史蓝图：
  - `docs/blueprints/active/2026-03-27_multi-engine-execution-surface-decision.md`
  - `docs/blueprints/active/2026-03-27_value-carrying-semantics-v1-decision.md`

## 5. Proposed Shape

Extend `PyReasonRuleExt` with an engine-specific body-clause interval control that can be keyed by `pred_id`, so PyReason compilation can emit syntax like `popular(y) : [0.5, 1.0]` for selected body atoms. Use the same extension field in both adapter-local rule compilation and shared WhereIR compilation.

Revise runner warnings so they describe default-threshold behavior instead of claiming bounded seeds are inherently non-propagating. Update adapter docs and demos to distinguish:

- bounded seeds can satisfy rule bodies when explicit clause intervals allow them
- current derived head semantics still need to be described from observed behavior, not assumption

## 6. Boundaries And Invariants

- 必须保持的边界：
  - node fact materialization remains `pr.add_fact(...)`
  - edge fact materialization remains graph-edge attributes
  - no new shared `engine_options` keys are introduced for this feature
- 明确不做的内容：
  - no broad schema or DSL redesign
  - no claim that `[0.85, 0.95]` seeds automatically derive `[0.85, 0.95]` outputs
- 兼容性约束：
  - rules without explicit clause-bound configuration must preserve current output strings
  - shared evaluate callers not using the new extension must see existing behavior

## 7. Acceptance

- [x] 代码行为满足任务目标
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步
- [x] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. Add a scoped PyReason engine extension field for body-clause interval bounds and validate its shape.
2. Teach adapter-local rule compilation and shared WhereIR compilation to emit explicit body intervals from that extension.
3. Update warning logic, tests, adapter docs, and the PyReason demo language to match the validated engine behavior.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- `examples/README.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `PyReasonRuleExt` 新增 `body_predicate_bounds`，adapter-local rule compilation 与 shared WhereIR compilation 都可生成显式 body clause interval。
  - `run_pyreason(...)` warning 改成描述默认 `[1.0, 1.0]` body threshold 语义；显式 clause interval 存在时不再误报。
  - 回归测试新增 threshold-aware compile / flow / warning coverage；全量测试更新为 `513` 通过。
  - adapter docs 与 PyReason demo 文案同步到新边界：bounded seed 可参与 body matching，但当前不把 derived head 描述成 interval transport。
- 与 blueprint 不同的地方：
  - 没有改动 demo 的执行逻辑，只更新了说明文字。
- 为什么会有这些调整：
  - real-engine smoke 证据表明这次已确认的是 “body matching 可放宽”，不是 “demo 应恢复为 fuzzy payload propagation”。
- 归档说明：
  - 2026-03-28 实现完成后归档到 `docs/blueprints/archive/`。
