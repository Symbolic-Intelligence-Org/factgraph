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

## E. Implementation Outcome

Pending.
