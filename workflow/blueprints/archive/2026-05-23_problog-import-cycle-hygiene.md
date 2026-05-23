# ProbLog import cycle hygiene

- Status: implemented
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - T2.1 closure follow-up: [2026-05-22_t2-1-ne-adapter-dispatch.md](../archive/2026-05-22_t2-1-ne-adapter-dispatch.md)
  - Reproduced import failure from `PYTHONPATH=src python -m unittest tests.test_problog_export`
- Outputs / Downstream:
  - ProbLog test gate restored for T2.2 ArithExpr and later ProbLog-facing slices
  - Cleaner baseline for `tests.test_problog_export` and `tests.test_problog_engine_eval`
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [2026-05-22_t2-1-ne-adapter-dispatch.audit.md](../archive/2026-05-22_t2-1-ne-adapter-dispatch.audit.md)
- Related Modules:
  - `src/factgraph/adapters/problog/__init__.py` — eager package import registers the ProbLog evaluator and re-exports adapter API.
  - `src/factgraph/adapters/problog/engine_eval.py` — imports provenance support.
  - `src/factgraph/adapters/problog/provenance.py` — imports `factgraph.audit.evidence_graph`.
  - `src/factgraph/audit/__init__.py` — eagerly imports audit submodules, including `round_events`.
  - `src/factgraph/audit/round_events.py` — imports `factgraph.application.protocol.common`.
  - `src/factgraph/application/__init__.py` — eagerly imports `capability_helpers`.
  - `src/factgraph/application/capability_helpers/round_events.py` — imports projector functions from `factgraph.audit.round_events`.
- Audit Log:
  - [2026-05-23_problog-import-cycle-hygiene.audit.md](./2026-05-23_problog-import-cycle-hygiene.audit.md)
- Branch: `v0.2.0-blueprint-problog-import-cycle-hygiene-2026-05-23`

## 1. Problem

T2.1 shipped raw tuple `ne` support for Souffle and ProbLog adapters, but its normal ProbLog test gate could not run because importing `tests.test_problog_export` fails before test execution.

The failure is unrelated to T2.1's adapter changes. It is a pre-existing import cycle triggered by package eager imports:

1. `tests/test_problog_export.py:9` imports `factgraph.adapters.problog.problog_export`.
2. Python initializes `factgraph.adapters.problog.__init__`, which eagerly imports `engine_eval` at `src/factgraph/adapters/problog/__init__.py:4`.
3. `src/factgraph/adapters/problog/engine_eval.py:14` imports `factgraph.adapters.problog.provenance`.
4. `src/factgraph/adapters/problog/provenance.py` imports `factgraph.audit.evidence_graph`, which first initializes the `factgraph.audit` package.
5. `src/factgraph/audit/__init__.py` eagerly imports `round_events`.
6. `src/factgraph/audit/round_events.py:11` imports `factgraph.application.protocol.common`, which first initializes the `factgraph.application` package.
7. `src/factgraph/application/__init__.py:3-18` eagerly imports `capability_helpers`, including `build_round_event_payload`.
8. `src/factgraph/application/capability_helpers/round_events.py:21-27` imports projector functions from `factgraph.audit.round_events` while that module is still partially initialized.

The observed failure:

```text
ImportError: cannot import name 'project_check_event_payload' from partially initialized module 'factgraph.audit.round_events'
```

This blocks all future ProbLog-facing slices from running the full `tests.test_problog_export` gate. It should be fixed before T2.2 ArithExpr so future closure reports do not need the same isolated-module workaround.

## 2. Goals

### 2.1 Break the import cycle at the smallest safe boundary

- Make direct ProbLog submodule imports work without pulling the full evaluator/provenance/audit/application capability-helper chain unless needed.
- Prefer reducing or lazifying package eager imports over moving domain logic.
- Keep the patch surgical enough that behavior changes are limited to import timing.

### 2.2 Preserve ProbLog package registration behavior

- `import factgraph.adapters.problog` must still register the `"problog"` engine evaluator.
- Existing identity expectation must remain true:
  - `tests/test_problog_engine_eval.py:79-81` expects `get_engine_evaluator("problog") is evaluate_problog`.
- Do not replace `evaluate_problog` registration with a wrapper unless identity can be preserved.

### 2.3 Preserve public package facades

- Public imports from `factgraph.adapters.problog` remain available.
- Public imports from `factgraph.audit` remain available if `audit/__init__.py` is changed.
- Public imports from `factgraph.application` remain available if `application/__init__.py` is changed.
- Capability helper exports, especially `build_round_event_payload`, must continue to work:
  - `tests/test_capability_helpers_round_events.py:312-313` asserts `application.build_round_event_payload` and `capability_helpers.build_round_event_payload` identity.

### 2.4 Restore ProbLog test gate for downstream work

- `tests.test_problog_export` should import and run through its normal unittest entrypoint.
- `tests.test_problog_engine_eval` should still import and run through its normal unittest entrypoint.
- T2.2 and later ProbLog slices should no longer need isolated module loading to verify export behavior.

## 3. Non-goals

- No changes to ProbLog export semantics.
- No changes to ProbLog import parsing.
- No changes to `evaluate_problog(...)`, provenance parsing, or engine execution behavior.
- No changes to T2.1 `ne` behavior.
- No ArithExpr, AggregateExpr, or atom-language expansion.
- No broad audit package refactor beyond the import boundary needed to break the cycle.
- No broad application package refactor beyond the import boundary needed to break the cycle.
- No rewrite of round-event projector logic.
- No cleanup of unrelated test failures outside the import cycle.

## 4. Current Context

### 4.1 ProbLog package eager import

`src/factgraph/adapters/problog/__init__.py:3-11` eagerly imports all package exports, including `engine_eval`, then registers the evaluator:

```python
from factgraph.adapters.problog.engine_eval import evaluate_problog
from factgraph.core.store.runtime import register_engine_evaluator

register_engine_evaluator(evaluate_problog, "problog")
```

This is intentional enough to preserve because `tests/test_problog_engine_eval.py:79-81` validates the registered evaluator identity.

### 4.2 Export-only tests still pay evaluator/provenance import cost

`tests/test_problog_export.py:9` imports:

```python
from factgraph.adapters.problog.problog_export import ProbLogExportError, export_problog
```

Even though this test needs only exporter code, Python initializes the parent package first, so `adapters/problog/__init__.py` eagerly imports evaluator/provenance code.

### 4.3 Provenance pulls audit package initialization

`src/factgraph/adapters/problog/engine_eval.py:14` imports provenance support. Provenance imports `factgraph.audit.evidence_graph`, and Python initializes `factgraph.audit.__init__` before loading the submodule.

`src/factgraph/audit/__init__.py` currently imports multiple audit submodules eagerly, including:

- `.assertions`
- `.evidence_graph`
- `.dto`
- `.reader`
- `.round_events`

The cycle does not require `round_events` for the original provenance import; `round_events` is pulled because the package initializer imports it eagerly.

### 4.4 Round events pull application package initialization

`src/factgraph/audit/round_events.py:11` imports:

```python
from factgraph.application.protocol.common import JSONValue, WarningDTO
```

Importing a submodule under `factgraph.application` still initializes `src/factgraph/application/__init__.py`.

### 4.5 Application package eager imports capability helpers

`src/factgraph/application/__init__.py:3-18` imports `.capability_helpers`, including `build_round_event_payload`.

That reaches `src/factgraph/application/capability_helpers/round_events.py:21-27`, which imports projector functions from `factgraph.audit.round_events` while that module is still partially initialized.

### 4.6 Existing public identity constraints

`tests/test_capability_helpers_round_events.py:312-313` checks:

```python
self.assertIs(application.build_round_event_payload, build_round_event_payload)
self.assertIs(capability_helpers.build_round_event_payload, build_round_event_payload)
```

Any lazy export strategy must preserve these identity expectations.

## 5. Proposed Shape

### 5.1 Preferred fix after precondition: decouple `audit.round_events` from application package import

Implementation-time precondition checking showed that normal `import factgraph.audit.evidence_graph` still fails before any code edit because `audit/__init__.py` imports `assertions`, `assertions` imports `reader`, and `reader` imports `round_events`. That means lazying only the direct `round_events` import from `audit/__init__.py` is insufficient.

The revised preferred implementation is to make `src/factgraph/audit/round_events.py` stop importing `factgraph.application.protocol.common` at module import time.

Rationale:

- The actual cycle is enabled when `round_events` imports `factgraph.application.protocol.common` while `audit.round_events` is still partially initialized.
- `JSONValue` is used as a type alias and can be defined locally in `round_events` without changing runtime payload validation.
- `WarningDTO` is needed at runtime only when `make_warning(...)` constructs a warning DTO; import it lazily inside that function.
- This boundary keeps the existing `audit/__init__.py` eager public facade intact and avoids an eight-submodule lazy facade refactor.
- This boundary avoids changing ProbLog evaluator registration and avoids touching `application.__init__`.

Acceptable tactics:

- Remove the top-level `from factgraph.application.protocol.common import JSONValue, WarningDTO` import from `audit/round_events.py`.
- Add a local `JSONValue` type alias equivalent to `application.protocol.common.JSONValue`.
- Import `WarningDTO` inside `make_warning(...)` only.
- Keep `warning_to_row(...)` duck-typed: it only reads `code`, `message`, `path`, and `details`.
- Keep every `audit/__init__.py` public export intact.

### 5.2 Fallback fix: defer capability-helper export from `factgraph.application`

If the `round_events` import-time decoupling does not break the cycle safely, the fallback is to defer `capability_helpers` imports from `src/factgraph/application/__init__.py` while preserving public attribute access and identity.

Rationale:

- `audit.round_events` only needs `application.protocol.common`.
- It should not need to import `application.capability_helpers.round_events` while initializing.

This fallback is acceptable only if tests covering `application.build_round_event_payload` and `capability_helpers.build_round_event_payload` still pass.

### 5.3 Avoid a ProbLog registration workaround unless necessary

Changing `src/factgraph/adapters/problog/__init__.py` to avoid importing `engine_eval` may appear simpler, but it risks breaking the evaluator registration identity tested by `tests/test_problog_engine_eval.py:79-81`.

Allowed only if:

- `import factgraph.adapters.problog` still registers `"problog"`.
- The registered evaluator object remains `evaluate_problog`, not a wrapper.
- Existing package-level exports continue to work.

### 5.4 Test-first verification target

The implementation should be judged by normal import and unittest behavior, not by an isolated module loader workaround. T2.1 used isolated loading only to prove the `ne` patch itself was correct despite the unrelated baseline cycle; this slice removes the need for that workaround.

## 6. Boundaries And Invariants

- The fix is an import hygiene change, not a behavior rewrite.
- Direct submodule import should not pay unrelated package-initializer costs when those costs create cycles.
- Public package facades remain compatible.
- ProbLog engine registration remains eager enough that `import factgraph.adapters.problog` registers the `"problog"` evaluator.
- Registered evaluator identity remains exactly `evaluate_problog`.
- Round-event projector functions keep their existing names and behavior.
- If a public export is intentionally no longer available from a package root, that is a scope expansion and requires blueprint amendment before implementation continues.
- `make_warning(...)` must still return the canonical `factgraph.application.protocol.common.WarningDTO` object.
- `warning_to_row(...)` must still accept the canonical `WarningDTO` object and preserve row shape.

## 7. Acceptance

- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_export` runs through the normal unittest entrypoint without the import-cycle failure.
- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_engine_eval` runs through the normal unittest entrypoint.
- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_export tests.test_problog_engine_eval` passes; if a new baseline failure unrelated to this import-cycle fix appears, closure §10 documents the failure mode and evidence that it is unrelated.
- [ ] `PYTHONPATH=src python -c "from factgraph.adapters.problog.problog_export import export_problog; print(export_problog.__name__)"` succeeds.
- [ ] `PYTHONPATH=src python -c "import factgraph.adapters.problog; from factgraph.adapters.problog.engine_eval import evaluate_problog; from factgraph.core.store.runtime import get_engine_evaluator; assert get_engine_evaluator('problog') is evaluate_problog"` succeeds.
- [ ] If `factgraph.audit.round_events` changes: `make_warning(...)` still returns a canonical `WarningDTO`, and `warning_to_row(make_warning(...))` preserves current row shape.
- [ ] If `factgraph.audit.__init__` changes: targeted imports from `factgraph.audit` still expose the names used by the existing tests.
- [ ] If `factgraph.application.__init__` changes: `tests.test_capability_helpers_round_events` still validates application/capability-helper identity for `build_round_event_payload`.
- [ ] Scope diff does not change ProbLog export semantics, provenance parsing, round-event projection behavior, or atom-language behavior.
- [ ] Ruff passes on every touched source/test file.
- [ ] Sacred `master` remains unchanged and unrelated dirty files remain untouched.

## 8. Implementation Plan

1. Reproduce `tests.test_problog_export` import failure on the implementation branch and save the exact trace for the closure note.
2. Verify the primary-boundary precondition before editing: run `PYTHONPATH=src python -c "import factgraph.audit.evidence_graph"` and confirm direct evidence-graph import does not itself trigger `application.__init__` / `capability_helpers` initialization. This failed before implementation and is recorded as the reason for the §5.1 boundary amendment.
3. Apply the smallest import-boundary change: decouple `factgraph.audit.round_events` from top-level `factgraph.application` imports by localizing `JSONValue` and lazily importing `WarningDTO` inside `make_warning(...)`.
4. Preserve facade compatibility with focused import smoke tests or existing unittest coverage.
5. Run the ProbLog gates:
   - `PYTHONPATH=src python -m unittest tests.test_problog_export`
   - `PYTHONPATH=src python -m unittest tests.test_problog_engine_eval`
   - `PYTHONPATH=src python -m unittest tests.test_problog_export tests.test_problog_engine_eval`
6. Run any package-facade regression tests relevant to the chosen boundary:
   - audit facade tests if `factgraph.audit.__init__` changes
   - capability-helper tests if `factgraph.application.__init__` changes
7. Run ruff on touched files.
8. Fill §10 with the chosen boundary, test results, and any baseline failures that remain.

## 9. Docs To Update

- No module behavior docs are expected for a pure import hygiene fix.
- If implementation changes a package root's public import policy in a way users should know, update the relevant module docs in the same implementation commit.
- This blueprint and audit log are the durable task record.

## 10. Outcome / Deviations

### 10.1 Final Landed Boundary

Implemented in `d0fec968` by changing `src/factgraph/audit/round_events.py`:

- Removed the top-level `from factgraph.application.protocol.common import JSONValue, WarningDTO` import.
- Added a local `JSONValue` type alias equivalent to the application protocol type alias.
- Lazily imports canonical `WarningDTO` inside `make_warning(...)`.
- Left `audit/__init__.py`, `application/__init__.py`, and `adapters/problog/__init__.py` unchanged.

This is a deliberate boundary deviation from the scoped draft's original preferred `audit/__init__.py` lazy export plan. The implementation-time precondition failed, and amendment commit `57b838e0` recorded the reason: `audit/__init__.py -> assertions -> reader -> round_events` still reached the same cycle before the direct `round_events` export mattered. Fixing the submodule's top-level application import is smaller and more robust.

### 10.2 Test Gates Run

Passing:

- `PYTHONPATH=src python -m unittest tests.test_problog_import_cycle_hygiene`
- `PYTHONPATH=src python -m unittest tests.test_capability_helpers_round_events`
- `PYTHONPATH=src python -c "from factgraph.adapters.problog.problog_export import export_problog; print(export_problog.__name__)"`
- `PYTHONPATH=src python -c "import factgraph.adapters.problog; from factgraph.adapters.problog.engine_eval import evaluate_problog; from factgraph.core.store.runtime import get_engine_evaluator; assert get_engine_evaluator('problog') is evaluate_problog; print('identity ok')"`
- `PYTHONPATH=src python -c "from factgraph.audit.round_events import make_warning, warning_to_row; from factgraph.application.protocol.common import WarningDTO; w = make_warning(code='TEST_WARNING', message='ok'); assert isinstance(w, WarningDTO); assert warning_to_row(w)['code'] == 'TEST_WARNING'; print('warning ok')"`
- `python -m ruff check src/factgraph/audit/round_events.py tests/test_problog_import_cycle_hygiene.py`

ProbLog gates now import and execute test bodies, but still fail on a separate baseline fixture drift:

- `PYTHONPATH=src python -m unittest tests.test_problog_export`
- `PYTHONPATH=src python -m unittest tests.test_problog_engine_eval`
- `PYTHONPATH=src python -m unittest tests.test_problog_export tests.test_problog_engine_eval`

Failure mode:

```text
factgraph.core.evidence.write_protocol.WriteProtocolError:
meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.
```

This is unrelated to the import-cycle fix:

- Error class changed from `ImportError` during module import to `WriteProtocolError` during test fixture setup.
- Error path is `src/factgraph/core/evidence/write_protocol.py:263` / `:272`, not package import initialization.
- The affected tests construct fixture data using removed `meta[confidence]` input.
- Direct `problog_export` import and evaluator identity smoke tests now pass.

### 10.3 Public Facade Compatibility

- `factgraph.adapters.problog` still registers the canonical `"problog"` evaluator object.
- `make_warning(...)` still returns canonical `factgraph.application.protocol.common.WarningDTO`.
- `warning_to_row(make_warning(...))` preserves row shape.
- `tests.test_capability_helpers_round_events` passes, including application/capability-helper identity assertions.

### 10.4 Follow-Up

Open a separate hygiene slice, or fold into T2.2 if appropriate, to migrate ProbLog test fixtures away from removed `meta[confidence]` and toward `raw_kind` / `bound` uncertainty inputs.

### 10.5 Archive Note

Ready to archive after reviewer verification. The slice achieved its primary objective: the ProbLog import cycle is gone, and the remaining ProbLog test failures are now visible baseline fixture drift rather than import-time failure.
