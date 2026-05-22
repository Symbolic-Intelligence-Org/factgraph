# Task Blueprint: Rule Engine Ext Alignment

- Status: implemented
- Created: 2026-03-28
- Last Updated: 2026-03-28
- Related Modules:
  - `src/factpy_kernel/sdk/dsl/rule.py`
  - `src/factpy_kernel/adapters/pyreason/rule_ext.py`
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
  - `src/factpy_kernel/sdk/docs/00_user_guide.md`
  - `src/factpy_kernel/sdk/docs/00_user_guide.en.md`
  - `src/factpy_kernel/sdk/docs/04_api_surface.md`
  - `src/factpy_kernel/sdk/docs/04_api_surface.en.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/active/2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
  - [docs/blueprints/active/2026-03-27_multi-engine-execution-surface-decision.md](./2026-03-27_multi-engine-execution-surface-decision.md)
- Audit Log:
  - [2026-03-28_rule-engine-ext-alignment.audit.md](./2026-03-28_rule-engine-ext-alignment.audit.md)

## 1. Problem

The repository's current PyReason adapter still relies on `PyReasonRuleDef` as an adapter-local wrapper to attach definition-time engine semantics to shared `Rule` objects. That wrapper exists because `Rule` never received the `engine_ext` field that the mother blueprint and ADR direction already identified as the intended shared carrier.

This leaves the implementation split across two shapes:

- shared evaluate surface: `Derivation.engine_ext`
- adapter-local PyReason runner path: `PyReasonRuleDef(rule, ext)`

That split is now architectural drift, not an intentional long-term boundary.

## 2. Goals

- Add `engine_ext: EngineExtBase | None` to shared `Rule`.
- Let PyReason rule compilation read engine semantics directly from `Rule.engine_ext`.
- Keep `PyReasonRuleDef` as a deprecated compatibility wrapper instead of breaking existing adapter-local call sites immediately.
- Update tests, examples, and module docs so repo truth points at `Rule.engine_ext` as the preferred definition-time path.

## 3. Non-goals

- Do not add `Query.engine_ext`.
- Do not change `to_authoring_payload()` or any persisted payload shape to include `engine_ext`.
- Do not remove `PyReasonRuleDef` in this slice.
- Do not redesign shared runtime `engine_options`.

## 4. Current Context

- 当前实现入口：
  - `Rule` has no `engine_ext`; `Derivation` already has it.
  - `compile_pyreason_rule(...)` only accepts `PyReasonRuleDef`.
  - `run_pyreason(...)` only types `rule_defs` as `list[PyReasonRuleDef]`.
- 当前已知约束：
  - Mother blueprint direction already says definition-time engine semantics belong on `Rule.engine_ext`.
  - `engine_ext` remains in-memory only and must not enter authoring payload serialization.
  - PyReason demos and tests still exercise the adapter-local wrapper heavily.
- 当前相关历史蓝图：
  - `2026-03-22_architectural-decisions-v2.md` ADR-14d
  - `2026-03-27_multi-engine-execution-surface-decision.md` D8
  - `docs/blueprints/archive/2026-03-28_pyreason-threshold-aware-clause-bounds.md`

## 5. Proposed Shape

Move the preferred definition-time carrier to shared `Rule.engine_ext`, matching `Derivation.engine_ext`.

PyReason compilation should accept either:

- preferred: `Rule(..., engine_ext=PyReasonRuleExt(...))`
- compatibility: `PyReasonRuleDef(rule=Rule(...), ext=PyReasonRuleExt(...))`

The adapter should treat `PyReasonRuleDef` as a compatibility shim around the shared `Rule` model, not as the primary API shape. Repo examples and docs should point to the shared carrier first.

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `engine_ext` stays definition-time only and in-memory only
  - `Derivation.engine_ext` remains unchanged
  - PyReason threshold-aware clause support remains intact
- 明确不做的内容：
  - no Query surface change
  - no registry / authoring serialization change
  - no removal of compatibility wrapper in this task
- 兼容性约束：
  - existing `PyReasonRuleDef` call sites must keep working
  - rules without `engine_ext` must preserve current default PyReason behavior

## 7. Acceptance

- [x] 代码行为满足任务目标
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步
- [x] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. Add `Rule.engine_ext` without changing serialized payload behavior.
2. Update PyReason compilation and runner typing to prefer `Rule.engine_ext` while preserving `PyReasonRuleDef`.
3. Migrate tests, examples, and module docs to the shared carrier and verify regressions.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.en.md`
- `src/factpy_kernel/sdk/docs/04_api_surface.md`
- `src/factpy_kernel/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 共享 `Rule` 已新增 `engine_ext: EngineExtBase | None = None`，且保持不进入 `to_authoring_payload()`。
  - `compile_pyreason_rule(...)` 与 `run_pyreason(...)` 现在优先消费 `Rule(..., engine_ext=PyReasonRuleExt(...))`，同时继续兼容 `PyReasonRuleDef`。
  - PyReason examples 与主要回归测试已迁移到 shared carrier；兼容 wrapper 只在兼容测试和兼容文档中保留。
  - SDK / adapter 模块文档与 active 决策参考文档已同步到新的 `Rule.engine_ext` 状态。
- 与 blueprint 不同的地方：
  - 文档同步范围比原计划更大，除了模块 docs 外，还补了 active 决策与 rationale 文档中的过期 D8 表述。
- 为什么会有这些调整：
  - 若不同时修正 active 决策页里的 “Rule.engine_ext deferred” 文案，仓库会重新出现代码真相与决策文档冲突。
- 归档说明：
  - 2026-03-28 实现完成后归档到 `docs/blueprints/archive/`。
