# Decision Blueprint: Multi-Engine Execution Surface v0

- Status: scoped
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Supersedes: [2026-03-27_pyreason-execution-surface-v0-decision.md](../archive/2026-03-27_pyreason-execution-surface-v0-decision.md) (D1-D4)
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
- Design Rationale:
  - [2026-03-27_multi-engine-execution-surface-design-rationale.md](./2026-03-27_multi-engine-execution-surface-design-rationale.md)
- Related Modules:
  - `src/factpy_kernel/core/store/types.py` — `EvaluateMode` literal
  - `src/factpy_kernel/core/store/_evaluate.py` — mode dispatch gate
  - `src/factpy_kernel/core/store/runtime.py` — `register_engine_evaluator` + `Store.evaluate()`
  - `src/factpy_kernel/sdk/dsl/rule.py` — Rule + Derivation frozen dataclasses
  - `src/factpy_kernel/sdk/store.py` — SDK evaluate path + `to_authoring_payload()`
  - `src/factpy_kernel/adapters/pyreason/` — session, runner, accept, rule_ext
- Audit Log:
  - [2026-03-27_multi-engine-execution-surface-decision.audit.md](./2026-03-27_multi-engine-execution-surface-decision.audit.md)

## 1. Problem

PyReason originally landed with a complete adapter-local vertical slice (schema → session → runner → accept → ledger) that **bypasses core**. It introduced parallel containers (`PyReasonRuleDef`, adapter-local AcceptResult), a parallel compilation path, and a parallel accept flow. The `Derivation.engine_ext` branch has since been implemented on the shared evaluate surface, and `Rule.engine_ext` is now available as the preferred rule-level carrier; `PyReasonRuleDef` survives only as a compatibility shim.

The result is a **shadow pipeline**: users must learn different APIs depending on which engine they use. This contradicts the framework narrative: "users write rules and get results through one interface; engine-specific capabilities are handled by adapters behind that interface."

### 1.1 Architectural Principle

**Unified interface, not unified implementation.** Adapters can do wildly different things internally. The constraint is: inputs and outputs conform to shared types. Users see one pipeline (`Rule → evaluate → CandidateSet → accept`), regardless of engine.

## 2. Decisions (9 frozen contracts)

### D1: EvaluateMode gate — add `"pyreason"` to closed Literal

Add `"pyreason"` to `EvaluateMode = Literal["native", "souffle", "problog", "pyreason"]`. Update mode gate in `_evaluate.py`. Register `pyreason_engine_eval()` via `adapters/pyreason/__init__.py`.

**Rationale**: Only 3 engines exist; open string brings marginal benefit. Consistent with ProbLog's addition pattern.

### D2: v0 does not open engine_options

`pyreason_engine_eval()` uses default `PyReasonRunConfig(timesteps=2)` internally. No `engine_options` parameter in core signatures.

**Rationale**: `engine_options` would require changing 4 layers (`types.py` → `_evaluate.py` → `runtime.py` → `sdk/store.py`). No real v0 use case. If v1 needs it, core signatures must be explicitly extended — no existing kwargs passthrough exists.

### D3: WhereIR → PyReason compiler (new, v0 scope)

v0 implements a new `WhereIR → PyReason rule syntax` compiler, independent of existing `compile_pyreason_rule()` (which operates on PredAtom SDK objects).

**v0 scope**:
- Only lowered WhereIR `("pred", pred_id, terms)` atoms
- `terms`: `$var` tokens and string/number literals only
- `cmp` / `not` / `ruleref` / `branch-list` → raise `PyReasonCompileError` (capability gate)
- Head compilation: from `head_vars` + `target_pred_id`

**Two compilers coexist**: WhereIR compiler (for execution surface) and PredAtom compiler (for adapter-local runner). They serve different layers.

**File location**: `adapters/pyreason/where_compile.py`

### D4: Provenance — reuse `engine_no_witness_v1`

`CandidateSet.support_kind` uses existing `engine_no_witness_v1`. No new support kind. No explain path. No witness capture. v0 focuses on evaluate → candidate → accept flow.

### D5: engine_ext crosses compile boundary as independent kwarg

`engine_ext` does NOT enter `to_authoring_payload()` or any compiled/persisted artifact. `sdk.evaluate()` extracts `derivation.engine_ext` separately and passes it as an independent kwarg:

```python
# sdk/store.py evaluate path
compiled = derivation.to_authoring_payload()  # unchanged, no engine_ext
engine_ext = derivation.engine_ext             # extracted separately
evaluate_store(..., engine_ext=engine_ext)     # new kwarg
```

`evaluate_store()` gains `engine_ext: EngineExtBase | None = None`, forwarded to `engine_evaluate(**engine_kwargs)`.

### D6: Annotation side-channel via Store pending state

`EngineEvaluatorFn` return type stays `list[CandidateSet]`. Annotations travel via Store instance pending state:

```python
# Inside pyreason_engine_eval():
store._engine_pending_annotations[run_id] = annotation_templates

# After accept, caller calls:
pyreason_persist_annotations(store, run_id, accept_result)
# reads pending → maps candidate_id → asrt_id → writes AnnotationRows → clears pending
```

Lifecycle: `evaluate → accept → persist → clear`. Single-threaded; no concurrent `run_id` collision in v0.

### D7: PyReason v0 fact semantics = attribute existence model

Consistent with current tested code:
- Node fact: `graph.nodes[node_ref][pred_short_name] = 1` (bound still applies)
- Derived extraction: outputs `"true"` / `"false"` (not arbitrary values)
- WhereIR compiler generates: `popular(X) <-2 strength(Y, X), popular(Y)` (no value variables)
- Value-carrying predicates deferred to v1

### D8: v0 closed on Derivation.engine_ext first; Rule.engine_ext later aligned to the same carrier

The first closed loop landed through `Derivation.engine_ext`:
- `Derivation(where=[...], mode="pyreason", engine_ext=PyReasonRuleExt(...))`
- `sdk.evaluate(derivation)` → engine_ext extracted → `pyreason_engine_eval()`

That deferral is now closed in implementation: shared `Rule.engine_ext` is also available as the preferred definition-time carrier for adapter-local PyReason rule compilation, and `PyReasonRuleDef` remains only as a backward-compatibility shim.

### D9: EDB materialization — default bounds for non-PyReason facts

When Ledger facts from non-PyReason sources enter PyReason:
- Default bound: `[1.0, 1.0]` (definitely true)
- No temporal: `active_from=0, active_to=None`
- Rationale: accepted Ledger facts are ground truth for PyReason EDB. Engine-native annotations can refine in v1.

## 3. Key Design Details

### 3.1 EngineExtBase contract

```python
class EngineExtBase:
    """Base class for engine-specific rule/derivation extensions.
    Subclasses must be frozen dataclasses. Framework never inspects
    fields; only the target engine's adapter reads them."""
    pass

@dataclass(frozen=True)
class PyReasonRuleExt(EngineExtBase):
    timestep_delay: int = 0
```

Marker type for isinstance checks. Module location TBD (`core/store/types.py` or `core/engine_ext.py`).

### 3.2 Error cases

| Scenario | Behavior |
|----------|----------|
| `engine_ext=PyReasonRuleExt(...)` + `evaluate(mode="souffle")` | **Error.** `ValueError("engine_ext type PyReasonRuleExt is not compatible with engine 'souffle'")`. Presence of engine_ext pins to specific engine. |
| No `engine_ext` + `evaluate(mode="pyreason")` | Valid — defaults apply (timestep_delay=0). |
| `engine_ext=SouffleRuleExt(...)` + `evaluate(mode="pyreason")` | **Error.** PyReason adapter checks isinstance. |

### 3.3 Migration: Derivation.engine_ext

Adding `engine_ext: EngineExtBase | None = None` to frozen Derivation:
- Default `None` — all existing constructions valid
- In-memory only — not serialized, not persisted
- `Derivation.mode` determines engine; `engine_ext` adds parameterization

## 4. Non-goals

- engine_options core signature extension
- Complete WhereIR compiler (beyond pred atoms + literals)
- Explain path / witness capture for PyReason
- Query.engine_ext
- Rule.engine_ext (deferred to v1 — D8)
- UI / audit consumer switch to pyreason/* annotations
- Multi-engine execution abstraction generalization
- Rule registry integration for PyReason rules
- Value-carrying predicate semantics (deferred to v1 — D7)

## 5. Core Changes Required

| File | Change | Est. Lines |
|------|--------|------------|
| `core/store/types.py` | Add `"pyreason"` to `EvaluateMode`; add `EngineExtBase` | ~5 |
| `core/store/_evaluate.py` | Add `"pyreason"` to mode gate; add `engine_ext` kwarg passthrough; pyreason dispatch branch | ~10 |
| `core/store/runtime.py` | `evaluate()` + `evaluate_engine()` gain `engine_ext` kwarg | ~5 |
| `sdk/store.py` | Extract `derivation.engine_ext` before compile, pass separately | ~5 |

Total: **~25 lines** of core changes.

## 6. New Adapter Files

| File | Role |
|------|------|
| `adapters/pyreason/engine_eval.py` | `pyreason_engine_eval()` — registered via `__init__.py` |
| `adapters/pyreason/where_compile.py` | WhereIR → PyReason rule syntax compiler |
| `adapters/pyreason/__init__.py` | `register_engine_evaluator(pyreason_engine_eval, "pyreason")` (guarded import) |

## 7. Open Items (to resolve in implementation blueprint)

1. `EngineExtBase` module location — `core/store/types.py` vs `core/engine_ext.py`
2. `get_facts_for_pred()` does not exist on Ledger — EDB materialization requires new API or composition from existing methods
3. WhereIR compiler vs PredAtom compiler coexistence — both may survive serving different layers
4. PyReason adapter import guard — registration guarded so missing `pyreason` library doesn't break import
5. `engine_ext` also on Query? — decision blueprint says no for v0

## 8. Acceptance Criteria

- [ ] 9 decisions explicitly reviewed and approved
- [ ] Core change scope confirmed (~25 lines)
- [ ] WhereIR compiler scope confirmed (lowered pred atoms only, attribute existence model)
- [ ] `engine_no_witness_v1` reuse accepted
- [ ] Store pending state annotation mechanism accepted
- [ ] engine_ext compile-boundary crossing confirmed (independent kwarg, not in payload)
- [ ] v0 closure path confirmed: Derivation.engine_ext first; Rule.engine_ext later aligned without entering payload serialization
