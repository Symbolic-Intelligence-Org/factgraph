# Task Blueprint: PyReason Execution Surface Closeout

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Related Modules:
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py`
  - `src/factpy_kernel/adapters/pyreason/accept.py`
  - `src/factpy_kernel/tests/test_pyreason_engine_eval.py`
  - `src/factpy_kernel/tests/test_pyreason_e2e.py`
  - `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-27_multi-engine-execution-surface-decision.md](./2026-03-27_multi-engine-execution-surface-decision.md)
  - [2026-03-27_multi-engine-execution-surface-impl.md](../archive/2026-03-27_multi-engine-execution-surface-impl.md)
- Audit Log:
  - [2026-03-27_pyreason-execution-surface-closeout.audit.md](./2026-03-27_pyreason-execution-surface-closeout.audit.md)

## 1. Problem

PyReason execution surface v0 is implemented, but one explicit gap remains: wrong `engine_ext` types are not rejected. The current end-to-end test also carries hand-written post-accept annotation materialization logic that should exist as a reusable adapter helper instead of living only in tests.

## 2. Goals

- Reject non-`EngineExtBase` values at the shared `evaluate_store(...)` boundary.
- Reject non-`PyReasonRuleExt` engine extensions inside `pyreason_engine_eval(...)`.
- Formalize post-accept pending annotation persistence as a reusable PyReason adapter helper.
- Replace test-local post-accept annotation glue with helper-backed coverage.

## 3. Non-goals

- No new engine option surface.
- No rule compile capability expansion (`CompareExpr`, value semantics, etc.).
- No real PyReason runtime/environment validation work.
- No new mother blueprint in this task.

## 4. Current Context

- Current execution surface is archived in [2026-03-27_multi-engine-execution-surface-impl.md](../archive/2026-03-27_multi-engine-execution-surface-impl.md).
- `engine_ext` currently flows through SDK/core/adapter, but only the happy path is tested.
- Pending PyReason annotations are cached on `store._engine_pending_annotations[run_id]`.
- The existing e2e test proves the lifecycle, but uses a test-local helper to bind templates to accepted assertion ids.

## 5. Proposed Shape

- Add a framework-level marker-type guard in `core/store/_evaluate.py`.
- Add an adapter-specific ext-type guard in `adapters/pyreason/engine_eval.py`.
- Add `persist_pyreason_annotations(...)` to `adapters/pyreason/accept.py` as the v0 post-accept helper.
- Cover both guards and the helper with focused tests, and update adapter docs so the execution surface narrative matches code.

## 6. Boundaries And Invariants

- Must keep `engine_ext` out of persisted authoring payloads.
- Must not change the `EngineEvaluatorFn -> list[CandidateSet]` contract.
- Must preserve the explicit v0 pending-annotation lifecycle: `evaluate -> accept -> persist`.
- Must not generalize the helper beyond PyReason in this task.

## 7. Acceptance

- [ ] Wrong non-`EngineExtBase` values fail fast at core evaluate boundary.
- [ ] Wrong non-`PyReasonRuleExt` values fail fast in PyReason adapter.
- [ ] Pending PyReason annotations can be persisted via a reusable helper after accept.
- [ ] Tests cover the new guards/helper and the full suite remains green.
- [ ] Affected adapter docs are synchronized.

## 8. Implementation Plan

1. Add shared and adapter-local `engine_ext` type guards with focused tests.
2. Add a reusable PyReason post-accept annotation persistence helper and switch e2e coverage to it.
3. Update adapter docs, record outcome/deviations, and archive the closeout blueprint.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- closeout blueprint audit log

## 10. Outcome / Deviations

- Final outcome:
  - Added a framework-level `EngineExtBase` guard in `core/store/_evaluate.py`.
  - Added a PyReason-specific `PyReasonRuleExt` guard in `adapters/pyreason/engine_eval.py`.
  - Added `persist_pyreason_annotations(...)` in `adapters/pyreason/accept.py` and switched end-to-end coverage to the helper.
  - Added focused guard/helper coverage and kept the full suite green.
- Deviations from initial expectation:
  - The helper stays PyReason-specific; this task did not attempt to generalize post-accept persistence for other engines.
- Validation:
  - `PYTHONPATH=src python -m unittest factpy_kernel.tests.test_pyreason_engine_eval factpy_kernel.tests.test_pyreason_e2e`
  - `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'`
  - Result: `Ran 467 tests`, `OK`
- Archive note:
  - Adapter docs were updated and the closeout blueprint was archived after code/tests/docs alignment.
