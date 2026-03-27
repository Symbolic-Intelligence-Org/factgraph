# Task Blueprint: Engine Options Implementation

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_engine-options-runtime-dispatch-decision.md](./2026-03-27_engine-options-runtime-dispatch-decision.md)
- Related Modules:
  - `src/factpy_kernel/core/store/types.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py`
- Audit Log:
  - [2026-03-27_engine-options-impl.audit.md](./2026-03-27_engine-options-impl.audit.md)

## 1. Problem

D-EO1-6 frozen. `engine_options: dict[str, Any] | None` needs to be threaded through the evaluate dispatch path and consumed by PyReason adapter.

## 2. Implementation Steps

### Step 1: Core signatures (`types.py` + `_evaluate.py` + `runtime.py`)

- Add `engine_options: dict[str, Any] | None = None` to:
  - `evaluate_store()` in `_evaluate.py`
  - `Store.evaluate()` in `runtime.py`
  - `Store.evaluate_engine()` in `runtime.py`
- Per D-EO3: `mode="native"` + non-empty `engine_options` → `ValueError`
- Forward `engine_options` to engine evaluator call

### Step 2: SDK passthrough (`sdk/store.py`)

- Thread `engine_options` through SDK evaluate helpers
- `SDKStore.evaluate(derivation, engine_options=None)` → extracts and forwards
- Does NOT enter `to_authoring_payload()` (D-EO2)

### Step 3: PyReason adapter consumption (`engine_eval.py`)

- Add `resolve_pyreason_run_config(engine_options)` helper
- Validates: `timesteps` must be positive int if present
- Unknown keys → `ValueError` with list of supported keys
- Replaces hardcoded `PyReasonRunConfig(timesteps=2, atom_trace=False)`

### Step 4: Tests

- Core: `engine_options` forwarded to adapter
- Core: `mode="native"` + `engine_options` → `ValueError`
- PyReason: `timesteps=5` respected
- PyReason: missing `timesteps` → default 2
- PyReason: unknown key → `ValueError`
- PyReason: bad `timesteps` type → `ValueError`
- Full regression green

## 3. Non-goals

- No `Derivation` changes
- No authoring payload changes
- No ProbLog adapter
- No trace return path
- No convergence params

## 4. Acceptance

- [x] `engine_options` kwarg on `Store.evaluate()`, `evaluate_store()`, `Store.evaluate_engine()`
- [x] SDK `evaluate()` accepts and forwards `engine_options`
- [x] `mode="native"` rejects non-empty `engine_options`
- [x] PyReason adapter: `timesteps` from `engine_options`
- [x] PyReason adapter: unknown keys → `ValueError`
- [x] Tests cover all paths
- [x] 487+ tests green

## 5. Outcome / Deviations

- Final outcome:
  - Shared evaluate dispatch now threads `engine_options` through `evaluate_store()`, `Store.evaluate()`, `Store.evaluate_engine()`, and SDK compiled-derivation helpers.
  - `SDKStore.evaluate(...)` keeps `engine_options` strictly call-time only; it is forwarded to runtime evaluation but never enters `Derivation` or `to_authoring_payload()`.
  - `mode="native"` now rejects non-empty `engine_options` early with a clear `ValueError`.
  - PyReason adapter now normalizes public `engine_options` through `resolve_pyreason_run_config(...)` and exposes only `timesteps`; unknown keys and invalid values fail fast.
  - Core, SDK, and PyReason module docs were updated to reflect the new runtime-config boundary.
  - Regression suite passed at `Ran 495 tests`, `OK`.
- Deviations from blueprint:
  - `runner.py` did not need a code change. `PyReasonRunConfig` remained unchanged and was reused as the adapter-internal normalized type from `engine_eval.py`.
  - Additional doc sync landed in SDK module docs because `SDKStore.evaluate(...)` is part of the public surface touched by this task.
- Why:
  - Reusing the existing `PyReasonRunConfig` kept the change narrow and aligned with D-EO5.
  - SDK doc updates were necessary because the new call-time kwarg is user-visible, not just an internal core change.
- Archive note:
  - Archived on 2026-03-27 after code, tests, and module docs were aligned.
