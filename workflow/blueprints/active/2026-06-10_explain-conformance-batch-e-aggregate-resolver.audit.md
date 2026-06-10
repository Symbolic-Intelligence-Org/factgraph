# Audit Log: Explain Conformance Batch E — support-capture aggregate resolver

Paired with [2026-06-10_explain-conformance-batch-e-aggregate-resolver.md](./2026-06-10_explain-conformance-batch-e-aggregate-resolver.md).

---

## A. Source Preflight (2026-06-10)

Codex read these shipped anchors before drafting:

- `src/factgraph/core/store/_support_capture.py`
  - `find_winning_case_index(...)`
  - `_branch_satisfies(...)`
  - `_atom_satisfies(...)`
  - `_eq_atom_satisfies(...)`
  - `_ne_atom_satisfies(...)`
  - `_cmp_atom_satisfies(...)`
  - `_arith_atom_satisfies(...)`
  - `_in_atom_satisfies(...)`
- `src/factgraph/core/rules/where_eval.py`
  - `evaluate_where(...)`
  - `_resolve(...)`
  - `_resolve_eval_term(...)`
  - `_resolve_aggregate_term_for_env(...)`
  - arithmetic/comparison resolver use sites.
- Callers:
  - `src/factgraph/core/store/_evaluate.py`
  - `src/factgraph/application/diagnose_runtime.py`
  - `src/factgraph/application/derivation_check_runtime.py`
  - `src/factgraph/core/rules/ruleref_substrate.py`
  - `src/factgraph/adapters/souffle/engine_eval.py`
- Existing aggregate tests:
  - `tests/core/rules/test_aggregate_eval.py`
  - `tests/sdk/dsl/test_aggregate_ergonomic.py`
  - `tests/sdk/test_rule_expr_evaluate.py`

## B. Preflight Findings

1. `find_winning_case_index(...)` already constructs `view_facts` from
   `witness_facts`, so support-capture has the substrate required to evaluate
   aggregate terms.
2. Support-capture currently drops that substrate before eq/ne/cmp/arith atom
   rechecks. Those helpers use bare `_resolve(...)`.
3. `where_eval` already has the correct aggregate-aware resolver:
   `_resolve_eval_term(env, term, view_facts, ast_gate_on=...)`.
4. `evaluate_where(...)` obtains `ast_gate_on` from `_where_ast_gate_enabled()`
   and passes it into all resolver paths. Support-capture should mirror this
   for branch rechecks.
5. The bug is in support reconstruction after evaluation, not in aggregate
   evaluation itself. Existing `where_eval` aggregate tests demonstrate correct
   row semantics.
6. The fix touches core support-capture and therefore must be treated as an
   evaluate-path correctness change, not explain-only rendering work.

## C. Scope Questions For Review

1. **`_in_atom_satisfies(...)` inclusion**:
   The obvious failing aggregate cases use `eq`, comparison, or arithmetic.
   The blueprint includes `_in_atom_satisfies(...)` as a source-review point
   because aggregate-valued operands could theoretically pass through it. Scope
   review should decide whether to update it now or explicitly leave it out.

2. **Public API stability**:
   The preferred shape keeps `find_winning_case_index(...)`,
   `build_support_artifact_for_binding(...)`, and
   `derive_rule_ref_edges_for_binding(...)` signatures stable. The only new
   state is threaded internally after `find_winning_case_index(...)` builds
   `view_facts`.

3. **`ast_gate_on` source**:
   The blueprint assumes support-capture should call `_where_ast_gate_enabled()`
   in `find_winning_case_index(...)`, matching `evaluate_where(...)`. If scope
   review finds a caller-specific gate state is required, that should be locked
   before implementation.

## D. Required Tests

Batch E implementation must include tests that fail on the current support
capture path:

1. SDK/native end-to-end aggregate `count` with `evaluate(...)` and
   `row.explain()`.
2. SDK/native end-to-end aggregate `sum`.
3. SDK/native end-to-end aggregate `min`.
4. SDK/native end-to-end aggregate `max`.
5. SDK/native end-to-end aggregate `mean`.
6. A non-aggregate native evaluate→explain regression.
7. Existing support-capture, diagnose, ruleref, Souffle, and conformance tests
   stay green.

## E. Implementation Outcome

Pending.
