# Task Blueprint: ProbLog RuleExt Branch Probabilities

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/adapters/problog/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/problog_export.py`
  - `src/factpy_kernel/core/store/types.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/authoring/derivation_compile.py`
  - `src/factpy_kernel/authoring/rule_dsl_parse.py`
  - `src/factpy_kernel/sdk/dsl/rule.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/adapters/docs/02_problog_adapter.md](../../../src/factpy_kernel/adapters/docs/02_problog_adapter.md)
  - [src/factpy_kernel/sdk/docs/00_user_guide.md](../../../src/factpy_kernel/sdk/docs/00_user_guide.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-29_problog-rule-ext-branch-probabilities.audit.md](./2026-03-29_problog-rule-ext-branch-probabilities.audit.md)

## 1. Problem

ProbLog currently has one remaining pre-architecture debt lane: `body_confidences`.

The current behavior is not a generic confidence surface. It is a ProbLog-specific definition/compile sidecar that is threaded through shared evaluate signatures and finally consumed by ProbLog export as per-branch weights for `where` OR branches.

This creates three problems:

- the semantics are real, but they are not represented as typed `engine_ext`
- shared core signatures still carry a ProbLog-only parameter
- the existing name (`body_confidences`) obscures the actual meaning and invites the wrong replacement shape (`probability: float`)

The closeout blueprint on 2026-03-28 explicitly deferred this debt. This blueprint reopens it as a new task with a narrower goal: freeze the typed replacement and migrate without changing the meaning.

## 2. Goals

- Freeze the replacement shape for ProbLog branch weighting as typed `engine_ext`.
- Preserve current `body_confidences` semantics exactly: one probability per `where` OR branch.
- Migrate ProbLog evaluation/export to consume typed `engine_ext` instead of the shared `body_confidences` sidecar.
- Remove `body_confidences` from shared core evaluate signatures after the new path is in place.
- Keep existing fact-level probability, candidate probability, and annotation-store probability lanes unchanged.

## 3. Non-goals

- Do not change EDB fact probability sourcing from `meta.confidence`.
- Do not change accepted-result semantic persistence (`problog/semantic/probability`).
- Do not introduce ProbLog summary / narrative / NL work.
- Do not widen the numeric domain beyond the current `(0, 1]` contract.
- Do not add new shared top-level evaluate kwargs such as `branch_probabilities=...`.

## 4. Current Context

- 当前实现入口：
  - `authoring/derivation_compile.py` compiles and validates `body_confidences`, including branch-count alignment and `(0, 1]` value checks.
  - `authoring/rule_dsl_parse.py` lowers `Body(confidence=...)` wrappers into `body_confidences`.
  - `sdk/store.py`, `core/store/runtime.py`, and `core/store/_evaluate.py` pass `body_confidences` through the shared evaluate path.
  - `adapters/problog/engine_eval.py` currently rejects any non-`None` `engine_ext` with a blanket error.
  - `adapters/problog/problog_export.py` consumes `body_confidences` as branch weights and emits one weighted helper clause per normalized branch.
- 当前已知约束：
  - `body_confidences` is semantically per-branch, not per-rule and not per-fact.
  - Current accepted values are strict floats in `(0, 1]`; `1.0` means deterministic branch.
  - `engine_ext` is the architecture-approved definition-time lane; `engine_options` remains call-time only.
  - `Rule.engine_ext` and `Derivation.engine_ext` already share the same `EngineExtBase` slot.
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-27_problog-semantic-annotation-parity-l4.md`
  - `docs/blueprints/archive/2026-03-28_problog-timeout-eval-surface.md`
  - `docs/blueprints/archive/2026-03-28_rule-engine-ext-alignment.md`
  - `docs/blueprints/archive/2026-03-28_design-branch-closeout.md`

## 5. Proposed Shape

### 5.1 Typed carrier

Adopt one adapter-local typed extension:

```python
@dataclass(frozen=True)
class ProbLogRuleExt(EngineExtBase):
    """ProbLog-specific branch weighting for OR-branch derivations/rules."""

    branch_probabilities: tuple[float, ...] | None = None
```

Semantics:

- `branch_probabilities[i]` is the probability for normalized `where` branch `i`
- length must equal the normalized branch count
- `None` means every branch is `1.0`
- values remain in `(0, 1]`

### 5.2 Meaning boundaries

`ProbLogRuleExt.branch_probabilities` is only the definition-time carrier for branch weighting.

It is not:

- fact-level probability from `meta.confidence`
- runtime output probability in `CandidateSet.confidence`
- accepted semantic annotation `problog/semantic/probability`

Those three lanes remain separate and keep their current responsibilities.

### 5.3 Ownership

The first real consumer is the shared evaluate path for ProbLog derivations, so v1 must work on `Derivation.engine_ext`.

`Rule.engine_ext` may also accept `ProbLogRuleExt` for surface consistency, but this blueprint does not require a broader Rule-only execution semantics beyond cases that lower losslessly to the same normalized branch structure.

### 5.4 Migration contract

Migration order is:

1. remove the blanket `engine_ext` rejection in `problog/engine_eval.py` and replace it with adapter-local type validation
2. add `ProbLogRuleExt` and adapter validation
3. bridge existing compatibility inputs into typed branch probabilities
4. make ProbLog evaluation/export consume `engine_ext`
5. remove `body_confidences` from shared core signatures and payload threading

Compatibility inputs may still be accepted at authoring/DSL boundaries during migration, but the shared evaluate core must stop routing a ProbLog-only sidecar once the typed path is live.

### 5.5 Migration-time conflict policy

During migration, a ProbLog derivation may surface both:

- explicit `engine_ext=ProbLogRuleExt(...)`
- legacy compiled `body_confidences`

The conflict policy is:

- if only `engine_ext.branch_probabilities` exists, use it
- if only legacy `body_confidences` exists, bridge it into `ProbLogRuleExt` before adapter execution
- if both exist and normalize to the same branch tuple, keep `engine_ext` as the source of truth
- if both exist and differ, fail fast with a clear conflict error

The system must never silently merge, average, or independently consume both lanes.

### 5.6 Bridge location

The compatibility bridge happens in the SDK evaluate path, not in authoring payload serialization.

Reason:

- `Body(confidence=...)` is currently lowered during authoring compile into `body_confidences`
- `engine_ext` is intentionally not serialized into authoring payloads
- therefore the safe migration shape is:
  - authoring compile may continue to emit legacy `body_confidences` temporarily
  - SDK evaluate reconstructs `ProbLogRuleExt` from compiled `body_confidences` when no explicit `engine_ext` is present
  - once all ProbLog execution paths consume typed `engine_ext`, the legacy sidecar can be removed from compile payloads and shared evaluate signatures

## 6. Boundaries And Invariants

- 必须保持的边界：
  - branch weighting keeps exact current meaning: one probability per normalized OR branch
  - missing branch weights remain equivalent to deterministic `1.0`
  - core shared APIs expose `engine_ext`, not new ProbLog-only kwargs
  - fact-level probability and accepted semantic annotations keep their current contracts
  - `engine_ext` does not become part of authoring payload serialization during the bridge period
- 明确不做的内容：
  - no probability-summary or NL layer
  - no reinterpretation of `meta.confidence`
  - no expansion to a more expressive ProbLog rule-language feature set beyond current branch weighting
- 兼容性约束：
  - existing authoring forms (`body_confidences`, `Body(confidence=...)`) may be bridged during migration but must converge to the typed `engine_ext` shape
  - if branch structure cannot be mapped losslessly, the system must fail fast rather than silently changing semantics

## 7. Acceptance

- [x] `ProbLogRuleExt` exists as the typed adapter-local definition surface
- [x] `branch_probabilities` semantics are validated against normalized branch count and `(0, 1]`
- [x] `problog/engine_eval.py` accepts `ProbLogRuleExt` and rejects only unsupported `engine_ext` types
- [x] ProbLog evaluate/export consumes typed `engine_ext` instead of shared `body_confidences`
- [x] migration-time conflict behavior is explicit: `engine_ext` wins when equivalent, mismatch raises
- [x] shared core evaluate signatures no longer carry `body_confidences`
- [x] compatibility authoring inputs are either lowered to `ProbLogRuleExt` or rejected clearly
- [x] affected module docs are updated to describe the new contract

## 8. Implementation Plan

1. Replace the blanket `engine_ext` rejection in `adapters/problog/engine_eval.py` with `ProbLogRuleExt`-aware validation and normalization.
2. Add `ProbLogRuleExt` and implement SDK-evaluate bridge logic from compiled `body_confidences` to typed `engine_ext`, including mismatch detection when both lanes are present.
3. Move ProbLog evaluation/export to read branch probabilities from `engine_ext`, then remove shared `body_confidences` threading from core/store/runtime surfaces.
4. Refresh tests and module docs for ProbLog, SDK, authoring, and core architecture boundaries.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/authoring/docs/01_overview.md`
- `src/factpy_kernel/authoring/docs/README.md`

## 10. Outcome / Deviations

- 最终落地结果：
- 新增 `adapters/problog/rule_ext.py`，正式引入 `ProbLogRuleExt(branch_probabilities=...)`，并提供 branch-count/materialization/legacy-bridge helper。
- `adapters/problog/engine_eval.py` 不再 blanket 拒绝 `engine_ext`；现在接受 `ProbLogRuleExt`，并在执行前完成 typed normalization。
- `adapters/problog/problog_export.py` 现只从 typed `engine_ext` 读取分支概率；legacy `body_confidences` 不再进入 adapter/export surface。
- `sdk/store.py` 在 evaluate path 中把 compiled `body_confidences` bridge 成 `ProbLogRuleExt`；显式 `engine_ext` 与 legacy lane 同时存在时，等价则保留 `engine_ext`，不等价则 fail fast。
- `core/store/_evaluate.py`、`core/store/runtime.py` 与 `service/runtime_v1.py` 已移除 shared `body_confidences` evaluate routing，ProbLog branch weighting 重新回到 `engine_ext` / `engine_options` 双槽位边界。
- 针对性回归已覆盖 rule ext、adapter eval、semantic annotation、provenance、EvidenceGraph 和 runtime surface，共 `33 tests` 通过。
- 与 blueprint 不同的地方：
- 除 SDK evaluate bridge 外，`service/runtime_v1.py` 也增加了同一条 bridge；否则 runtime derivation 仍会绕过 SDK 并继续依赖已删除的 shared `body_confidences` 参数。
- 为什么会有这些调整：
- blueprint 冻结时只显式写了 SDK evaluate bridge，但实际仓库里还存在一条直接走 `Store.evaluate(...)` 的 runtime derivation 路径；两处必须同时收口，shared core 才能真正移除 ProbLog-only 参数。
- 归档说明：
- 本蓝图已于 2026-03-29 实现完成并归档到 `docs/blueprints/archive/`。
