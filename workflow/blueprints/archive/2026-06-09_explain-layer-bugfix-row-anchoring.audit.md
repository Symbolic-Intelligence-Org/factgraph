# Audit Log: Explain v2 bugfix — per-row native prober anchoring

Paired with [2026-06-09_explain-layer-bugfix-row-anchoring.md](./2026-06-09_explain-layer-bugfix-row-anchoring.md).

---

## A. Root Cause Review (2026-06-09)

Claude's demo audit found a critical native explain correctness bug:

- multi-entity passed rows can all explain to the same mixed-entity evidence;
- single-entity cases pass only because there is one possible environment;
- unwrapping typed row values alone does not fix the bug;
- seeding with lowered execution-local variable names plus unwrapped values fixes
  the demo end to end.

Codex source-read confirmation:

- `src/factgraph/sdk/store.py:_initial_probe_bindings_for_row(...)` seeds with
  `plan.head.ports` variable names and raw row-binding values.
- `RuleExprLoweringPlan.occurrence_map[*].port_bindings[*]` has the authoritative
  `source_var → alias_local_execution_var` mapping.
- `src/factgraph/application/protocol/evaluate_result.py:_public_term_value(...)`
  is the existing typed-term unwrapping helper.

Verdict: root cause accepted.

## B. Locked Fix

- Use occurrence-map port bindings to seed execution-local variables.
- Seed all execution-local variables mapped from the same logical source var.
- Decode row binding values with `_public_term_value(...)`.
- Keep adapter anchoring unchanged.
- Keep `closed_head_false` behavior unchanged.
- `application/explain/prober.py` and `application/protocol/rule_expr_lowering.py`
  are read-only context for this slice; the code edit target is `sdk/store.py`
  unless helper placement requires a small `evaluate_result.py` adjustment.
- If no lowered execution variable maps to a head port source variable, leave
  that port unseeded. This safe under-seed fallback is preferable to guessing.

## C. Split-Out Findings

- `%ENT` rendering for already-bound entity refs can show raw `idref_v1:...`
  instead of a friendly entity label. This is presentation quality, not row
  anchoring correctness. It is explicitly deferred to a separate slice.
- `closed_head_false` has no row and remains an all-view failure explanation.
  Subject-focused failed explanation is out of scope.

## D. Required Regression Tests

1. Multi-row native passed explanations anchor to each row independently.
2. Join / multi-occurrence seeding writes every lowered variable for the source
   variable.
3. OR branches remain row-anchored.
4. Entity-ref, string, and integer row bindings are unwrapped to bare values.
5. `closed_head_false` still yields evidence.
6. Existing prober monotonic and adapter dispatch tests remain green.

## E. Scope Review (2026-06-09)

Claude review approved `draft → scoped` with three clarifications:

1. `sdk/store.py` is the primary edit target; prober/lowering files are
   read-only context.
2. Missing source-var mappings degrade by under-seeding, not by guessing.
3. The original demo command must be rerun as an integration gate:
   `PYTHONPATH=src python examples/explain_layer_demo.py`.

## F. Implementation Outcome

Implemented by Codex in `e78d5a99`.

Implementation facts:

- Only shipped code file changed: `src/factgraph/sdk/store.py`.
- Test file changed: `tests/sdk/test_rule_expr_evaluate.py`.
- `_initial_probe_bindings_for_row(...)` now maps logical source vars to all
  lowered execution-local vars through `plan.occurrence_map`.
- `_public_term_value(...)` unwraps public row-binding values before seed use.
- `application/explain/prober.py` and `application/protocol/rule_expr_lowering.py`
  have zero diff.
- `evaluate_result.py` was not edited; the private helper was imported directly.

Codex verification:

- Focused native/prober suite: 48 tests OK.
- Explain cohort: 125 tests OK.
- Demo command: `PYTHONPATH=src python examples/explain_layer_demo.py` produced
  a coherent single-row explanation with one user, one region, one age, and a
  matching comparison.

Claude independent gate:

- Re-read implementation and confirmed it matches the approved occurrence-map
  multi-value seed shape.
- Confirmed multi-row test has explicit negative assertions against cross-row
  mixing.
- Confirmed join/multi-occurrence, OR branch seed, typed-value unwrap,
  `closed_head_false`, monotonic, and adapter dispatch coverage.
- Re-ran focused 48 and explain cohort 125; both passed.
- Re-ran demo and confirmed row-coherent output.

Verdict: PASS. `%ENT` raw idref rendering remains deferred to a separate slice.
