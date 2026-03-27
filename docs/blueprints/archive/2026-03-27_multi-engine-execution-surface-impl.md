# Task Blueprint: Multi-Engine Execution Surface v0 Implementation

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-execution-surface-decision.md](../active/2026-03-27_multi-engine-execution-surface-decision.md) (9 frozen decisions)
- Related Modules:
  - `src/factpy_kernel/core/store/types.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/sdk/dsl/rule.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/adapters/pyreason/`
- Audit Log:
  - [2026-03-27_multi-engine-execution-surface-impl.audit.md](./2026-03-27_multi-engine-execution-surface-impl.audit.md)

## 1. Problem

9 frozen decisions (D1-D9) describe how to unify the PyReason shadow pipeline with core dispatch. This blueprint implements them.

## 2. Goals

- `Derivation.engine_ext: EngineExtBase | None` field on frozen dataclass
- `EngineExtBase` base class in core
- `"pyreason"` in EvaluateMode + dispatch gate
- `engine_ext` kwarg passthrough in evaluate_store → engine evaluator
- WhereIR → PyReason compiler (attribute existence model, pred atoms only)
- `pyreason_engine_eval()` registered as engine evaluator
- EDB materialization (Store → PyReasonSession)
- Store pending state for annotation side-channel
- End-to-end integration test

## 3. Non-goals

Per parent decision blueprint §4.

## 4. Implementation Steps

### Step 1: EngineExtBase + Derivation.engine_ext

- Define `EngineExtBase` in `core/store/types.py`
- Add `engine_ext: EngineExtBase | None = None` to `Derivation` in `sdk/dsl/rule.py`
- `PyReasonRuleExt` inherits `EngineExtBase`
- Run full test regression (435 tests must pass unchanged)

### Step 2: Core dispatch — EvaluateMode + engine_ext kwarg

- Add `"pyreason"` to `EvaluateMode` literal in `types.py`
- Add `engine_ext` kwarg to `evaluate_store()` in `_evaluate.py`
- Add `engine_ext` kwarg to `Store.evaluate()` and `Store.evaluate_engine()` in `runtime.py`
- Forward `engine_ext` in `engine_kwargs` to engine evaluator
- Extract `derivation.engine_ext` in `sdk/store.py` evaluate path, pass as separate kwarg
- Add engine_ext type mismatch validation (wrong ext type for engine → ValueError)

### Step 3: WhereIR → PyReason compiler

- New file: `adapters/pyreason/where_compile.py`
- Compile lowered `("pred", pred_id, terms)` atoms → PyReason rule syntax
- Attribute existence model: no value variables
- `cmp`/`not`/`ruleref`/`branch-list` → raise `PyReasonCompileError`
- Head compilation from `head_vars` + `target_pred_id`
- Tests

### Step 4: EDB materialization + pyreason_engine_eval

- Implement `_materialize_edb_from_store(store, schema_ir) → PyReasonSession`
- Default bound `[1.0, 1.0]` for non-PyReason facts (D9)
- Implement `pyreason_engine_eval(store, *, derivation_id, version, target_pred_id, head_vars, where, head, engine_ext)` → `list[CandidateSet]`
- Register via `adapters/pyreason/__init__.py` (guarded import)
- Store pending state for annotations (D6)
- Tests

### Step 5: Integration test + cleanup

- End-to-end: `Derivation(mode="pyreason", engine_ext=...) → store.evaluate() → CandidateSet → store.accept() → annotations`
- Update adapter docs
- Update integration demo if applicable

## 5. Acceptance

- [x] `Derivation(engine_ext=PyReasonRuleExt(...))` constructs without error
- [x] `store.evaluate(mode="pyreason", ...)` returns `list[CandidateSet]`
- [x] `store.accept(candidate)` returns core `AcceptResult`
- [x] `pyreason/semantic/*` annotations persisted after accept
- [x] 435+ existing tests green
- [x] New integration tests pass
- [ ] Error case: wrong engine_ext type → ValueError

## 6. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`
- Implementation blueprint audit log

## 7. Outcome / Deviations

- Final outcome:
  - Step 1 (`833075c`): added `EngineExtBase`, `Derivation.engine_ext`, and `EvaluateMode="pyreason"` support.
  - Step 2 (`0a8a449`): threaded `engine_ext` through `sdk/store.py` → `core/store/_evaluate.py` → `runtime.py`.
  - Step 3 (`62e5783`): added `adapters/pyreason/where_compile.py` plus focused compiler coverage.
  - Step 4 (`5e7e7e8`): added `pyreason_engine_eval()`, EDB materialization, adapter registration, and pending annotation caching.
  - Step 5 (`fa35c54`): added SDK end-to-end execution-surface coverage and patched authoring compile/preflight mode gates so `Derivation(mode="pyreason")` can actually reach execution.
- Deviations from the original step text:
  - OR branch groups are compiled into one PyReason rule per branch instead of being rejected as unsupported `branch-list`.
  - Pending annotations are cached on `store._engine_pending_annotations`; `Store.accept()` does not auto-persist or auto-clear them. The current v0 close loop is `evaluate -> accept -> explicit bind/persist`.
  - `wrong engine_ext type -> ValueError` remains deferred; the implementation does not yet reject cross-engine ext mismatches.
- Validation:
  - `PYTHONPATH=src python -m unittest factpy_kernel.tests.test_pyreason_e2e`
  - `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'`
  - Result: `Ran 464 tests`, `OK`
- Archive note:
  - Adapter module docs were updated and the implementation blueprint was archived after code/tests/docs alignment.
