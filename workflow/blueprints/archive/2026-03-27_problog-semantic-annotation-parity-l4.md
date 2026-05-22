# Task Blueprint: ProbLog Semantic Annotation Parity L4

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](../active/2026-03-27_multi-engine-semantic-delivery.md) (L4)
- Related Decisions:
  - [2026-03-26_assertion-annotation-store-decision.md](../active/2026-03-26_assertion-annotation-store-decision.md) (Decision 5-6)
  - [2026-03-27_multi-engine-execution-surface-decision.md](../active/2026-03-27_multi-engine-execution-surface-decision.md)
- Related Modules:
  - `src/factpy_kernel/adapters/problog/__init__.py`
  - `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/derivation/accept.py`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/assertions.py`
  - `src/factpy_kernel/audit/static_ui.py`
- Audit Log:
  - [2026-03-27_problog-semantic-annotation-parity-l4.audit.md](./2026-03-27_problog-semantic-annotation-parity-l4.audit.md)

## 1. Problem

ProbLog already has a working evaluate path:

- `Store.evaluate(mode="problog")`
- adapter registration on import
- CLI execution
- `CandidateSet.confidence = probability`
- `CandidateSet.confidence_kind = "probability"`

But this probability currently stops at the candidate / accept meta layer. It does **not** enter the framework's semantic-delivery surface as `problog/semantic/*` annotations.

That means:

- accepted ProbLog facts do not write `problog/semantic/probability`
- audit export cannot include ProbLog semantic annotations for those assertions
- static HTML's namespace-grouped annotation panel has nothing ProbLog-specific to render

L4 is therefore not "make ProbLog run". It already runs. L4 is "make ProbLog semantic truth enter the unified consumption/delivery surface".

## 2. Goals

- Persist accepted ProbLog probabilities into Annotation Store as `problog/semantic/probability`
- Reuse the existing audit export / reader / assertion detail / static UI paths from L2 without inventing ProbLog-specific UI
- Keep ProbLog probability available in both places:
  - shared compatibility path: `meta.confidence`
  - engine-native semantic path: `annotation_rows(namespace="problog", category="semantic")`
- Add focused tests for evaluate → accept → annotation persist → audit/static consumption

## 3. Non-goals

- No ProbLog session API
- No adapter-local accept flow analogous to `accept_pyreason_session(...)`
- No `engine_ext` / `ProbLogRuleExt` implementation in this blueprint
- No `engine_options` for ProbLog
- No cleanup of `body_confidences` shared-core debt
- No fake proof tree or fake provenance payload
- No new static UI section specific to ProbLog; reuse existing namespace-grouped annotation panel

## 4. Current Context

- `parse_problog_output(...)` already writes probability into `CandidateSet` via:
  - `replace(candidate, confidence=float(prob), confidence_kind="probability")`
- core accept already persists:
  - `meta.confidence = candidate_set.confidence`
  - `meta.confidence_kind = candidate_set.confidence_kind`
- L2 already made annotation consumption generic:
  - audit package exports `assertion_annotations.jsonl`
  - reader loads it as optional artifact
  - assertion detail indexes by namespace
  - static UI groups annotations by namespace and already knows display label `"ProbLog"`

So the missing piece is not consumer infrastructure. The missing piece is **writing ProbLog semantic annotations after accept**.

## 5. Proposed Shape

### 5.1 Minimal write path

Mirror the PyReason shared-surface pattern, but keep it narrower:

1. `evaluate_problog(...)` produces `CandidateSet`s as today
2. it also records pending annotation templates keyed by `run_id`
3. core `accept()` writes the fact and shared meta as today
4. caller runs `persist_problog_annotations(...)`
5. helper binds `candidate_id -> asrt_id` and appends:
   - `problog / semantic / probability`

This is a post-accept binder, not a new accept pipeline.

### 5.2 Annotation content

For each accepted ProbLog fact candidate with non-`None` probability:

- `namespace="problog"`
- `category="semantic"`
- `key="probability"`
- `kind="float"`
- `value=<candidate probability>`
- `origin="derived"`
- `derivation=<derivation_id or adapter-defined derivation label>`

Shared compatibility remains unchanged:

- `meta.confidence`
- `meta.confidence_kind="probability"`

### 5.3 Consumer reuse

No new audit reader or UI feature branch is required. Existing generic L2 paths should consume the new annotation automatically once it is written.

This blueprint may still add tests that prove:

- `assertion_annotations.jsonl` includes `problog/semantic/probability`
- assertion detail exposes it under the `problog` namespace
- static HTML renders a ProbLog annotation table

## 6. Boundaries And Invariants

- `CandidateSet.confidence` remains the shared compatibility lane; L4 adds engine-native annotation, not a replacement
- No serialization of ProbLog runtime/definition parameters into `to_authoring_payload()`
- No change to `EngineEvaluatorFn` return shape
- No reuse of annotation mechanism for rule-level semantics
- No provenance artifact is emitted unless there is a real, truthful ProbLog carrier
- If a ProbLog candidate has `confidence is None`, no `problog/semantic/probability` annotation is written

## 7. Acceptance

- [x] Accepted ProbLog fact candidates can be materialized into `problog/semantic/probability` annotations
- [x] Existing shared accept path still writes `meta.confidence` / `confidence_kind="probability"`
- [x] Audit package includes the ProbLog annotation in `assertion_annotations.jsonl`
- [x] Assertion detail / static HTML render ProbLog annotations without ProbLog-specific UI branching
- [x] Focused tests cover evaluate → accept → persist → audit/static consumption
- [x] Full regression green

## 8. Implementation Plan

1. Add a minimal ProbLog pending-annotation + post-accept binder path in `adapters/problog`
2. Add focused unit/e2e coverage for ProbLog annotation persistence and consumer reuse
3. Update adapter/module docs to describe the new semantic-delivery path
4. If docs and code align, mark implemented and archive

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/02_problog_adapter.md`
- `src/factpy_kernel/audit/docs/01_overview.md` if audit-facing behavior needs explicit mention

## 10. Outcome / Deviations

- 最终落地结果：
  - `evaluate_problog(...)` 现在会为有概率的 fact candidates 缓存 pending `problog/semantic/probability` 模板。
  - 新增 `persist_problog_annotations(...)`，在 shared `accept` 之后把 `candidate_id` 绑定到真实 `asrt_id`，并将 `problog/semantic/probability` 写入 `Ledger.annotation_rows`。
  - 既有 L2 audit export / reader / assertion detail / static annotation panel 无需代码改动即可消费 ProbLog annotation。
  - 新增 L4 专项测试，覆盖 evaluate → accept → persist → audit/static；全量回归为 `499 tests` 全绿。
- 与 blueprint 不同的地方：
  - 实现使用了专用 side channel `store._problog_pending_annotations`，没有复用 PyReason 的 `_engine_pending_annotations`。
- 为什么会有这些调整：
  - ProbLog 的 post-accept binder 需要 `run_id -> candidate_id -> templates` 的映射，直接复用 PyReason 的 `run_id -> list[template]` 形状会引入类型冲突和行为歧义。
- 归档说明：
  - 本蓝图已实现并归档到 `docs/blueprints/archive/`；母蓝图 L4 描述也已同步收窄到 semantic annotation parity。
