# Audit Log: Explain Conformance Batch F — aggregate explain verdict and repr

Paired with [2026-06-10_explain-conformance-batch-f-aggregate-explain.md](./2026-06-10_explain-conformance-batch-f-aggregate-explain.md).

---

## A. Trigger (2026-06-10)

Post-D2 design-conformance review found a real aggregate explain bug missed by
Batch E and the earlier conformance audit.

Repro shape:

```text
total == sum(amount over orders)
evaluate row: passed, total=60
explain atom: NotReached, repr contains raw aggregate tuple
```

## B. Source Preflight

Read targets:

- `src/factgraph/application/explain/prober.py`
- `src/factgraph/core/rules/where_eval.py`
- `tests/sdk/test_explain_conformance_native.py`

Confirmed:

- Prober compare/equality atoms are blocked by `_missing_variables(...)` before
  they can reach `_extend_env_with_atom(...)`.
- `_missing_variables(...)` uses `_vars_in_atom_tuple(...)`, which descends into
  aggregate tuple internals.
- Aggregate-internal vars such as `$agg__amt` / `$agg__o` are therefore treated
  as missing outer dependencies.
- `where_eval` is already aggregate-aware through `_resolve_eval_term(...)`;
  prober does not need to implement aggregate computation.
- Existing aggregate conformance tests verify row values and evidence
  existence but not atom verdicts or repr text.
- `_render_term_value(...)` lacks aggregate rendering and falls back to
  `str(tuple)`.

## C. Locked Scope

- Edit target: `src/factgraph/application/explain/prober.py`.
- Tests: `tests/sdk/test_explain_conformance_native.py`; optional focused
  prober test if useful.

Non-targets:

- `where_eval.py`;
- `diagnose_runtime.py`;
- `core/store/_support_capture.py`;
- seed builder / lowering;
- DTOs / adapters.

## D. Open Implementation Questions for Scope Review

1. Exact aggregate repr wording:
   - `sum of amount`;
   - `sum(amount)`;
   - or another stable friendly form.
2. Target-label derivation:
   - from aggregate target var name;
   - from the filter predicate/field id;
   - fallback for non-field aggregate filters.
3. Missing-variable helper shape:
   - alter `_vars_in_atom_tuple(...)` directly; or
   - add a more specific helper used only by missing checks.

## E. Scope Review (2026-06-10)

Status: approved; blueprint moved to `scoped`.

Planner review accepted the root cause and local `prober.py` repair, with one
critical refinement:

- Do not treat aggregate terms as fully opaque for missing-variable checks.
- Exclude only aggregate-local lowered variables from the outer missing set.
- Preserve correlated outer variables referenced by aggregate filters as real
  dependencies.

Runtime lowered aggregate terms carry aggregate-local vars in the `$agg...`
namespace. The implementation may use that namespace as the lowered-IR marker
for the source-level distinction handled by `where_ast_validate`:

- `$agg__...` / `$_agg...` target and filter-bound vars are local to aggregate
  computation and must not block the outer compare atom;
- non-`$agg` vars referenced by the aggregate filter are correlated outer
  dependencies and must be present in the row/prefix environment;
- if a correlated outer var is missing, the atom must be `NotReached` and must
  not free-compute the aggregate over all facts.

This preserves the D2 no-leak invariant: missing dependency and no-free-enumerate
are the same check.

## F. Required Gate Evidence

- 5 aggregate kinds show `Holds` on passed explain rows.
- Aggregate repr has no raw tuple/list text and no `$agg__`.
- Correlated aggregate with bound correlation var shows `Holds`.
- Correlated aggregate with missing correlation var shows `NotReached` and does
  not leak unrelated facts.
- Non-aggregate missing-variable behavior remains green.
- D2 no-free-enumeration and order-independence remain green.
- Batch A/B/C/E regressions remain green.
- No non-prober runtime implementation diff.

## G. Implementation Outcome

Pending.
