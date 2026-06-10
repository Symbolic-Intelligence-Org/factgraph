# Task Blueprint: Explain Conformance Batch E — support-capture aggregate resolver

- Status: draft
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework batch
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `src/factgraph/core/store/_support_capture.py` (support-capture atom recheck; primary edit target)
  - `src/factgraph/core/rules/where_eval.py` (aggregate-aware resolver source; read-only unless preflight finds a helper exposure need)
  - `tests/sdk/test_rule_expr_evaluate.py` or `tests/sdk/test_explain_conformance_native.py` (native aggregate evaluate→explain regressions)
  - `tests/core/rules/test_aggregate_eval.py` (evaluate aggregate semantics reference)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-e-aggregate-resolver.audit.md](./2026-06-10_explain-conformance-batch-e-aggregate-resolver.audit.md)

---

## 1. Problem

Native aggregate rules can evaluate successfully in `where_eval`, then fail or
crash when support-capture tries to reconstruct the winning branch for the same
final binding.

Root cause: support-capture rechecks selected branches with helpers that resolve
terms via bare `_resolve(...)`. Aggregate terms remain raw tuples such as
`("sum", "$amount", [...])`, so the recheck compares the final binding value
against an unevaluated aggregate tuple.

The evaluate path already has the correct semantics:
`where_eval._resolve_eval_term(...)` detects aggregate terms and computes them
against `view_facts` and the current environment. Support-capture already builds
`view_facts` from witness facts, but it does not use the aggregate-aware
resolver.

This is a core evaluate/support bug, not only an explain rendering issue.

## 2. Goals

1. Make support-capture branch rechecks aggregate-aware for native rules.
2. Preserve evaluate result semantics: support-capture must validate the same
   binding that evaluate already produced, not change row selection.
3. Cover all five aggregate kinds: `count`, `sum`, `min`, `max`, and `mean`.
4. Keep non-aggregate support-capture behavior unchanged.
5. Keep explain-layer DTO/prober/adapter paths untouched.

## 3. Non-goals

- Do not change public aggregate DSL syntax or lowering.
- Do not change `evaluate_where(...)` aggregate semantics.
- Do not change explain prober verdict semantics; Batch D owns that.
- Do not change repr/value rendering; Batch B/C own that.
- Do not add adapter aggregate support. PyReason aggregate rejection remains out
  of this batch.

## 4. Source Preflight

Confirmed source facts:

- `where_eval.evaluate_where(...)` computes `ast_gate_on =
  _where_ast_gate_enabled()` and routes eq/ne/cmp/arith operands through
  `_resolve_eval_term(...)`.
- `_resolve_eval_term(...)` delegates aggregate tuples to
  `_resolve_aggregate_term_for_env(...)`, which evaluates aggregate filter
  atoms over `view_facts`.
- `core/store/_support_capture.py` builds `view_facts` from
  `witness_facts` in `find_winning_case_index(...)`, then passes those facts
  through `_branch_satisfies(...)` into `_atom_satisfies(...)`.
- `_atom_satisfies(...)` currently calls `_eq_atom_satisfies`,
  `_ne_atom_satisfies`, `_cmp_atom_satisfies`, `_arith_atom_satisfies`, and
  `_in_atom_satisfies` without giving them `view_facts`.
- `_eq_atom_satisfies(...)` and peers call bare `_resolve(...)`, so aggregate
  tuples are treated as literal values.
- Support-capture callers include native evaluate, diagnose, derivation check,
  ruleref substrate, and Souffle's native-like support receipt builder.

## 5. Proposed Shape

Keep the support-capture public entry points stable. Internally, thread
`view_facts` and `ast_gate_on` into atom recheck helpers and resolve terms with
the same aggregate-aware resolver as evaluate.

Expected implementation outline:

```python
from factgraph.core.rules.where_eval import _resolve_eval_term, _where_ast_gate_enabled

def find_winning_case_index(...):
    ast_gate_on = _where_ast_gate_enabled()
    ...
    if _branch_satisfies(..., ast_gate_on=ast_gate_on):
        ...

def _eq_atom_satisfies(*, atom, binding, view_facts, ast_gate_on):
    _, lhs, rhs = atom
    lhs_known, lhs_value = _resolve_eval_term(binding, lhs, view_facts, ast_gate_on=ast_gate_on)
    rhs_known, rhs_value = _resolve_eval_term(binding, rhs, view_facts, ast_gate_on=ast_gate_on)
    return lhs_known and rhs_known and lhs_value == rhs_value
```

Apply the same resolver to:

- `eq`;
- `ne`;
- `gt` / `ge` / `lt` / `le`;
- arithmetic atoms (`add`, `sub`, `neg`, `addc`, `mulc`);
- `in` if aggregate or resolved terms appear in its operands.

This keeps support-capture's recheck aligned with evaluation without changing
row generation.

## 6. Boundaries And Invariants

- **INV-evaluate-result-stable**: aggregate-aware support-capture must not
  change which rows evaluate returns. It only prevents support reconstruction
  from rejecting an already-produced final binding.
- **INV-support-recheck-same-resolver**: when support-capture compares a term
  that can be aggregate-valued, it must use the same resolver family as
  `where_eval`.
- **INV-non-aggregate-regression**: existing non-aggregate support-capture tests
  and explain conformance tests remain green.
- `build_support_artifact_for_binding(...)` can continue using selected branch
  index; this batch only changes how the winning branch is found/rechecked.
- If an aggregate resolves to `AggregateNoValue`, support-capture should treat
  the atom the same way evaluate did: the selected binding should not satisfy
  that branch. In normal flow, such a branch should not be selected by evaluate.

## 7. Acceptance

- [ ] Native aggregate rules using `count`, `sum`, `min`, `max`, and `mean`
  evaluate without `WhereValidationError`.
- [ ] Each aggregate kind has an end-to-end SDK/native test that calls
  `evaluate(...)` and `row.explain()` successfully.
- [ ] Aggregate rows contain the same row bindings expected from existing
  `where_eval` aggregate semantics.
- [ ] Non-aggregate native evaluate→explain conformance remains green.
- [ ] Existing support-capture, diagnose, ruleref, and Souffle support tests
  remain green.
- [ ] No implementation diff in `application/explain/prober.py`, DTOs, or
  adapter provenance converters.

## 8. Implementation Plan

1. Add failing end-to-end native aggregate tests for all five aggregate kinds.
2. Thread `ast_gate_on` from `find_winning_case_index(...)` into
   `_branch_satisfies(...)`, `_atom_satisfies(...)`, and the affected atom
   helpers.
3. Thread `view_facts` into affected atom helpers.
4. Replace bare `_resolve(...)` calls in eq/ne/cmp/arith support-capture
   helpers with `_resolve_eval_term(...)`.
5. Decide whether `_in_atom_satisfies(...)` needs aggregate-aware value
   resolution based on the shipped IR validator and add coverage if yes.
6. Run focused aggregate tests, support-capture tests, native explain
   conformance, and the broader explain/conformance cohort.
7. Report any behavior change in evaluated rows back to the blueprint before
   widening scope.

## 9. Docs To Update

No public docs expected in this batch. This is an internal support-capture
correctness fix. Final conformance docs may summarize aggregate coverage.

## 10. Outcome / Deviations

To be filled after implementation.
