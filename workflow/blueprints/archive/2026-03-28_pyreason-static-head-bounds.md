# Task Blueprint: PyReason Static Head Bounds

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/rule_ext.py`
  - `src/factpy_kernel/adapters/pyreason/where_compile.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
  - `src/factpy_kernel/tests/test_pyreason_rule_ext.py`
  - `src/factpy_kernel/tests/test_pyreason_where_compile.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-27_multi-engine-execution-surface-decision.md](../active/2026-03-27_multi-engine-execution-surface-decision.md)
  - [2026-03-27_value-carrying-semantics-v1-decision.md](../active/2026-03-27_value-carrying-semantics-v1-decision.md)
- Audit Log:
  - [2026-03-28_pyreason-static-head-bounds.audit.md](./2026-03-28_pyreason-static-head-bounds.audit.md)

## 1. Problem

Real-engine follow-up established a narrower PyReason behavior boundary than the current adapter exposes:

- default derived heads materialize as `[1.0, 1.0]`
- explicit head annotations such as `popular(x) : [0.8, 0.9] <-1 ...` produce derived heads with that same non-`[1.0, 1.0]` interval
- the derived bound is static head syntax, not a dynamic function of body intervals

The adapter currently supports body-clause interval hints through `PyReasonRuleExt.body_predicate_bounds`, but it has no definition-time surface for this static head-bound behavior. That leaves both adapter-local rule compilation and shared WhereIR compilation unable to express a real engine capability that has now been validated.

## 2. Goals

- Add a definition-time `head_bound` carrier to `PyReasonRuleExt`
- Compile explicit head interval syntax in both PyReason rule compilers
- Keep the behavior available through both `Rule.engine_ext` and `Derivation.engine_ext`
- Document the exact semantics as static head annotation, not dynamic interval propagation
- Add focused regression coverage for compile shape and validation

## 3. Non-goals

- Do not implement dynamic body-to-head interval propagation
- Do not add value-variable semantics to PyReason rules
- Do not widen shared DSL or authoring payload shape
- Do not remove deprecated compatibility wrapper paths in this slice

## 4. Current Context

- 当前实现入口：
  - `rule_ext.py` 已支持 `timestep_delay` 与 `body_predicate_bounds`
  - `where_compile.py` 已支持 execution-surface `engine_ext` delay/body threshold lowering
- 当前已知约束：
  - `engine_ext` 仍是 definition-time only carrier，不进入 authoring payload
  - PyReason 的非 `[1.0, 1.0]` derived head 目前只在显式 head annotation 下得到验证
- 当前相关历史蓝图：
  - `2026-03-28_pyreason-threshold-aware-clause-bounds`
  - `2026-03-28_rule-engine-ext-alignment`

## 5. Proposed Shape

`PyReasonRuleExt` 增加 `head_bound: tuple[float, float] | list[float] | None`。当该字段存在时：

- adapter-local `compile_pyreason_rule(...)` 在 head 上附加 `: [lo, hi]`
- execution-surface `compile_where_ir_to_pyreason(...)` 在目标 head 上附加同样的 interval

该字段只是 PyReason-specific compile hint，语义是“生成静态 head annotation”。文档必须明确：

- 未声明 `head_bound` 时，derived head 默认仍是 `[1.0, 1.0]`
- 声明 `head_bound` 后，derived bound 取该静态值
- 这不代表 adapter 支持从 body bound 动态计算 derived bound

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `head_bound` 只存在于 `PyReasonRuleExt`
  - `Rule.engine_ext` / `Derivation.engine_ext` 继续作为 shared definition-time carrier
  - 兼容 wrapper `PyReasonRuleDef` 仍然可用
- 明确不做的内容：
  - 不在 shared `Rule` / `Derivation` 上新增专用字段
  - 不在 `engine_options` 中暴露 `head_bound`
  - 不把静态 head annotation 描述成 uncertainty propagation
- 兼容性约束：
  - 未设置 `head_bound` 的既有规则编译结果保持不变
  - 非法 bound 继续在 adapter/compiler 边界 fail fast

## 7. Acceptance

- [x] 代码行为满足任务目标
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步
- [x] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. 在 `rule_ext.py` 中增加 `head_bound` 字段与统一 bound 校验，并把 adapter-local rule compilation 扩展到 head interval syntax。
2. 在 `where_compile.py` 中把 `Derivation.engine_ext.head_bound` lower 到 execution-surface rule head。
3. 为两个编译入口补充 validation / compile-shape 回归测试，并更新 adapter docs 对静态 head-bound 语义的表述。
4. 跑 targeted + full regression，完成 outcome，归档 blueprint。

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `PyReasonRuleExt` 现在支持 `head_bound`
  - adapter-local `compile_pyreason_rule(...)` 与 execution-surface `compile_where_ir_to_pyreason(...)` 都会把该字段 lower 成 head interval annotation
  - focused regression tests 覆盖了 rule_ext / where_compile / engine_eval / SDK evaluate path
  - adapter module docs 已明确这是静态 head annotation，不是动态 interval propagation
- 与 blueprint 不同的地方：
  - 没有改 demos / notebooks
- 为什么会有这些调整：
  - 当前 demos 仍承担“默认 body threshold + bounded propagation 边界”说明职责；本轮新能力更适合先在 adapter docs 与 tests 中精确落地，而不是让 demo 口径扩散成新的主叙述
- 归档说明：
  - 2026-03-28 实现完成后归档；验证包括 targeted unittest、全量 unittest，以及基于 `/tmp/pyreason` 的 real-engine smoke
