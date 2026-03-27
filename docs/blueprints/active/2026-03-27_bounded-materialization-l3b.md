# Task Blueprint: Bounded Materialization L3b

- Status: draft
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md) (L3b)
  - [2026-03-27_value-carrying-semantics-v1-decision.md](./2026-03-27_value-carrying-semantics-v1-decision.md) (L3a decisions)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py` — graph builder + derived extraction
  - `src/factpy_kernel/adapters/pyreason/engine_eval.py` — EDB materialization
  - `src/factpy_kernel/adapters/pyreason/session.py` — fact write API
- Audit Log:
  - [2026-03-27_bounded-materialization-l3b.audit.md](./2026-03-27_bounded-materialization-l3b.audit.md)

## 1. Problem

L3a froze 5 decisions + closed D-VC4 as infeasible. The v0 existence model (`= 1`) discards numeric values. L3b implements the narrowed scope: bounded `[0,1]` values materialized into PyReason graph and extracted from results.

## 2. Scope (narrowed by D-VC4 closure)

**In scope**:
- D-VC2: Bounded graph materialization — `graph.nodes[ref][pred] = value` for bounded preds
- D-VC3: Bound summary extraction — derived value = `str(lower_bound)` for bounded preds
- D-VC5: Schema-driven routing — numeric type_domain + bounded annotation + `[0,1]` values

**Out of scope** (per D-VC4 closure):
- Value variables in rule syntax
- Rule-level numeric comparison (CompareExpr)
- WhereIR compiler changes (stays existence-based for all rule atoms)

## 3. Implementation Steps

### Step 1: Schema-driven routing in runner.py (node + edge)

`build_pyreason_graph()` currently hardcodes `= 1` for all node AND edge attributes. Change both paths:

**Node facts** (`runner.py:58`):
- Check `schema_ir` for predicate's bounded domain contract
- If bounded: `graph.nodes[ref][pred] = float(value)`
- Otherwise: `graph.nodes[ref][pred] = 1` (existence, unchanged)

**Edge facts** (`runner.py:65`):
- Same routing logic applied to edge attributes
- If bounded: `graph.edges[from_ref, to_ref][pred] = float(value)`
- Otherwise: `graph.edges[from_ref, to_ref][pred] = 1` (existence, unchanged)

**Bounded domain check** (per D-VC5, 3 hard AND conditions):
1. `type_domain` is numeric in `arg_specs` (`float64`, `float32`, or similar)
2. Predicate is explicitly annotated as bounded (`bounded=True` in schema predicate spec)
3. Actual value parses as float in `[0.0, 1.0]`

ALL three must hold. If any fails → fallback to existence model. No implicit inference.

### Step 2: Bound summary extraction in runner.py (node + edge)

`_extract_derived_facts()` currently outputs `"true"/"false"` for both node and edge derived facts. Change both paths:

**Node derived facts** (`runner.py:114`):
- For bounded predicates: `value = str(lower_bound)` (e.g., `"0.85"`)
- For non-bounded: `value = "true" if lower > 0 else "false"` (unchanged)

**Edge derived facts** (same logic):
- Same routing applied to edge interpretations

### Step 3: EDB materialization routing in engine_eval.py

`pyreason_engine_eval()` materializes EDB from Ledger via `project_view_facts()`. Currently all facts get `bound=(1.0, 1.0)` and `value` is used as-is in session. Change to:
- Pass `schema_ir` to the materialization step
- For bounded numeric preds: materialize with actual float value
- For non-bounded preds: materialize with existence (`"1"`) as before

### Step 4: Tests

- Extend `test_pyreason_runner.py`: graph builder with bounded vs non-bounded node AND edge predicates
- Extend `test_pyreason_engine_eval.py`: EDB materialization with mixed predicates (node + edge)
- New test: end-to-end bounded materialization → derived bound summary extraction
- Test: edge predicate bounded materialization and extraction

## 4. Non-goals

- No WhereIR compiler changes
- No CompareExpr support
- No value variable syntax
- No normalization registry
- No arbitrary numeric support (only `[0, 1]`)
- No core changes

## 5. Boundaries And Invariants

- `where_compile.py` is NOT touched — rule atoms stay existence-based
- Backward compatibility: non-bounded predicates behave exactly as v0
- If a "bounded" value is outside `[0.0, 1.0]`, silently fall back to existence model
- Annotation templates (`pyreason/semantic/bound_lower/upper`) already handle this correctly — no annotation changes needed

## 6. Acceptance

- [ ] Bounded node predicates materialized as float value in graph (not `= 1`)
- [ ] Bounded edge predicates materialized as float value in graph (not `= 1`)
- [ ] Non-bounded predicates (node + edge) still use `= 1` (backward compat)
- [ ] Derived extraction returns `str(lower_bound)` for bounded preds (node + edge)
- [ ] EDB materialization routes correctly for both node and edge
- [ ] Tests cover bounded vs non-bounded routing for both node and edge paths
- [ ] Full regression green

## 7. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md` — bounded materialization

## 8. Outcome / Deviations

(Fill after implementation)
