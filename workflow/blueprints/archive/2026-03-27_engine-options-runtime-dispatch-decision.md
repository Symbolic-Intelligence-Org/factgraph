# Decision Blueprint: Engine Options Runtime Dispatch v1

- Status: scoped
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md) (future design branch; not a numbered direction line)
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) (ADR-14e)
- Related Decisions:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md) (Decision 5-6)
  - [2026-03-27_multi-engine-execution-surface-decision.md](./2026-03-27_multi-engine-execution-surface-decision.md) (D2 current behavior freeze)
- Related Modules:
  - `src/factpy_kernel/core/store/types.py` — shared evaluate type surface
  - `src/factpy_kernel/core/store/_evaluate.py` — mode gate + engine passthrough
  - `src/factpy_kernel/core/store/runtime.py` — `Store.evaluate()` / `Store.evaluate_engine()`
  - `src/factpy_kernel/sdk/store.py` — SDK evaluate path and compiled derivation helpers
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py` — current hardcoded PyReason config
  - `src/factpy_kernel/adapters/pyreason/runner.py` — `PyReasonRunConfig` + actual engine invocation
- Audit Log:
  - [2026-03-27_engine-options-runtime-dispatch-decision.audit.md](./2026-03-27_engine-options-runtime-dispatch-decision.audit.md)

## 1. Problem

The architecture docs already distinguish:

- definition-time engine semantics → `engine_ext`
- run-time engine config → `engine_options`

But current code does not expose `engine_options` anywhere in the shared evaluate path. PyReason therefore hardcodes:

```python
PyReasonRunConfig(timesteps=2, atom_trace=False)
```

inside `pyreason_engine_eval()`.

That was correct for execution-surface v0 (D2), but it leaves three unresolved questions for v1:

1. Should `Store.evaluate(...)` open a shared `engine_options` contract at all?
2. If yes, what part of `PyReasonRunConfig` should become user-facing?
3. How do we keep run-time config separate from `engine_ext` and other persisted artifacts?

### Naming clarification

The mother blueprint's numbered mainline remains:

- L1 real-engine validation
- L2 annotation consumer
- L3a decision
- L3b bounded materialization
- L4 ProbLog semantic-delivery parity

`engine_options` is a **future design branch**, not the mother blueprint's L4. This blueprint exists to remove that naming drift before implementation starts.

## 2. Current Verified State

### 2.1 Shared evaluate surface

- `Store.evaluate(...)`, `evaluate_store(...)`, `Store.evaluate_engine(...)`, and `SDKStore.evaluate(...)` accept `engine_ext`
- none of them accept `engine_options`
- `Derivation` has `engine_ext`, but no runtime options carrier

### 2.2 PyReason config surface

`runner.py` defines:

```python
class PyReasonRunConfig:
    timesteps: int = 1
    atom_trace: bool = True
    convergence_threshold: float | None = None
    convergence_bound_threshold: float | None = None
```

But current shared execution only uses:

- `timesteps`
- `atom_trace`

and only `timesteps` has user-visible effect in the shared evaluate path. `atom_trace` produces trace data that `Store.evaluate(mode="pyreason")` does not currently return, and both `convergence_*` fields are present in the dataclass but not wired into `pr.reason(...)`.

## 3. Decisions To Freeze

### D-EO1: Open one shared `engine_options` kwarg on the evaluate dispatch path

`engine_options` is the shared carrier for run-time engine configuration.

The public shape is:

```python
engine_options: dict[str, Any] | None = None
```

It is added only to the evaluate dispatch path:

- `Store.evaluate(...)`
- `evaluate_store(...)`
- `Store.evaluate_engine(...)`
- `SDKStore.evaluate(...)`
- SDK compiled-derivation helpers

No engine-specific top-level kwargs such as `timesteps=` or `convergence=` are added to core APIs.

**Rationale**: this preserves ADR-14e's single dispatch slot and avoids a growing list of engine-specific parameters in shared signatures.

### D-EO2: `engine_options` is call-time only and never becomes authored or persisted state

`engine_options` is strictly run-time configuration.

It does **not** live in:

- `Derivation`
- `Query`
- `engine_ext`
- `to_authoring_payload()`
- Ledger rows
- audit artifacts

`engine_ext` remains definition-time. `engine_options` remains call-time.

### D-EO3: Shared core treats `engine_options` as opaque and adapters own validation

The shared layer only enforces:

- `engine_options` is `None` or `dict[str, Any]`
- `mode="native"` does not accept non-empty `engine_options`

Everything else is adapter-local:

- supported keys
- value type validation
- default filling
- error messages for unsupported options

This mirrors the existing `engine_ext` principle: shared surface routes, adapters interpret.

### D-EO4: PyReason v1 shared-surface options expose only `timesteps`

The only PyReason run-time option that becomes user-facing on the shared evaluate surface in v1 is:

- `timesteps: int`

Behavior:

- missing `timesteps` preserves the current default of `2`
- non-positive or non-int values fail fast

The following remain internal for now:

- `atom_trace`
  - shared evaluate does not return trace payloads, so exposing this would add cost without user-visible output
- `convergence_threshold`
- `convergence_bound_threshold`
  - present in `PyReasonRunConfig` today, but not wired into the actual engine call path

### D-EO5: `PyReasonRunConfig` stays adapter-internal as the normalized execution struct

`PyReasonRunConfig` remains the adapter's internal execution type.

The adapter may add a normalization helper such as:

```python
def resolve_pyreason_run_config(engine_options: dict[str, Any] | None) -> PyReasonRunConfig
```

but core code never imports, type-checks, or persists `PyReasonRunConfig`.

**Rationale**: the shared contract is the dispatch slot (`engine_options`), not the concrete run-config class of any one engine.

### D-EO6: Initial implementation scope is deliberately narrow

Opening `engine_options` v1 does **not** imply:

- Query-level runtime options
- authoring-schema changes
- `Derivation` schema changes
- `engine_ext` redesign
- trace return-path changes
- cleanup of historical `body_confidences` debt

The first implementation scope is only:

1. shared evaluate signatures
2. PyReason adapter validation + normalization
3. tests for defaulting and bad-option failures
4. module docs sync for core/adapters

## 4. Impact Assessment

### 4.1 Files that will change in the first implementation blueprint

| File | Change |
|------|--------|
| `core/store/types.py` | add `engine_options` type alias if needed |
| `core/store/_evaluate.py` | validate + forward `engine_options` |
| `core/store/runtime.py` | extend `evaluate()` and `evaluate_engine()` |
| `sdk/store.py` | thread `engine_options` through SDK evaluate helpers |
| `adapters/pyreason/engine_eval.py` | parse/normalize runtime options |
| `adapters/pyreason/runner.py` | reuse `PyReasonRunConfig` as adapter-internal normalized type |

### 4.2 Files that do not change in the first implementation

| File / Area | Why |
|-------------|-----|
| `sdk/dsl/rule.py` | runtime config is not part of authored derivation/rule state |
| `authoring/*` compile payloads | `engine_options` is not serialized |
| audit package / static UI | run config does not change semantic-delivery format |
| ProbLog adapter | future consumer, not part of the first implementation slice |

## 5. Non-goals

- Do not rename mainline L4 away from ProbLog semantic-delivery parity
- Do not expose adapter-local trace toggles on shared evaluate before a trace consumer exists
- Do not pretend unused `convergence_*` fields are supported just because they exist in `PyReasonRunConfig`
- Do not move `engine_options` into `engine_ext`
- Do not add arbitrary passthrough `**kwargs` to evaluate paths

## 6. Acceptance Criteria

- [x] The relationship to ADR-14e and Annotation Store Decision 5-6 is explicit
- [x] Current D2 behavior is acknowledged as the v0 baseline that this blueprint advances beyond
- [x] PyReason's first user-facing runtime subset is explicit: `timesteps` only
- [x] `PyReasonRunConfig` is kept adapter-internal
- [x] The mother blueprint numbering is clarified: `engine_options` is a future design branch, not mainline L4
- [x] A follow-up implementation blueprint opens before code changes land
