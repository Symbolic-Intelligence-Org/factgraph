# Task Blueprint: Explain v2 Bugfix — per-row native prober anchoring

- Status: draft
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Type: bugfix slice
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/application/explain/prober.py`
  - `src/factgraph/application/protocol/rule_expr_lowering.py`
- Audit Log:
  - [2026-06-09_explain-layer-bugfix-row-anchoring.audit.md](./2026-06-09_explain-layer-bugfix-row-anchoring.audit.md)

---

## 1. Problem

Native `EvaluateRow.explain()` currently does not anchor the prober to the row
being explained. In a multi-entity result, explanations for different passed
rows can become identical and can mix facts from different entities. The
evaluation result remains correct, but the evidence no longer proves the row.

The defect sits in `_initial_probe_bindings_for_row(...)`:

1. It seeds `probe_native(...)` with `plan.head.ports` variable names such as
   `$user`, `$region`, and `$age`.
2. The lowered body atoms actually use execution-local variables such as
   `$adult__user`, `$adult__region`, and `$adult__age`.
3. Because the seed keys do not match the body atom variables,
   `where_eval._eval_pred_atom(...)` does not see the bound variables and freely
   enumerates every fact.
4. The seeded values are also typed public row-binding dictionaries, while the
   prober compares against bare values.

The result is unanchored free enumeration, hidden by single-entity cases and
exposed by multi-entity demos.

## 2. Goals

1. Seed `probe_native(...)` with lowered execution-local variable names from
   `RuleExprLoweringPlan.occurrence_map[*].port_bindings[*].alias_local_execution_var`.
2. Use `RuleExprPortBinding.source_var` to map logical head variables to each
   occurrence-local execution variable.
3. Decode row binding values through `_public_term_value(...)` before seeding.
4. Preserve support for multiple occurrence-local variables per logical source
   variable, so join cases seed every relevant body occurrence.
5. Add focused regressions for multi-row anchoring, join/multi-occurrence
   anchoring, OR branch anchoring, typed-value unwrapping, and
   `closed_head_false` non-regression.

## 3. Non-goals

- Do not change prober witness semantics; S3 G1 remains unchanged.
- Do not change paths-model DTOs, adapter dispatch, or audit facade.
- Do not alter Souffle / ProbLog / PyReason row anchoring; they already use
  row-id keyed support artifacts or provenance envelopes.
- Do not fix `%ENT` label rendering for bound entity refs in this slice. That is
  a separate presentational bugfix.
- Do not change `closed_head_false` to focus on a requested subject. It has no
  result row and remains an all-view failure explanation.

## 4. Current Context

- `src/factgraph/sdk/store.py:_initial_probe_bindings_for_row(...)` currently
  builds a seed from `plan.head.ports` and raw `row.bindings`.
- `RuleExprLoweringPlan.occurrence_map` already carries the required metadata:
  `RuleExprOccurrenceBinding.port_bindings`, where each
  `RuleExprPortBinding` has `source_var` and `alias_local_execution_var`.
- `src/factgraph/application/protocol/evaluate_result.py:_public_term_value(...)`
  is the existing public-term unwrapping helper used by closed-head logic.
- Native passed and `closed_head_false` graph builders share the prober path.
  Passed rows provide a row; `closed_head_false` intentionally passes `row=None`.

## 5. Proposed Shape

Update `_initial_probe_bindings_for_row(row, plan)` to:

1. Return `{}` if `row.bindings` is unavailable or not a mapping.
2. Build `exec_by_source: dict[str, list[str]]` by iterating
   `plan.occurrence_map[*].port_bindings`.
3. For each `port_name, var` in `plan.head.ports`, look up the row binding by
   `port_name`.
4. Resolve `source_name = var.name`.
5. For every execution-local variable in `exec_by_source[source_name]`, seed
   that execution-local variable with `_public_term_value(row.bindings[port_name])`.

Sketch:

```python
def _initial_probe_bindings_for_row(row: Any, plan: RuleExprLoweringPlan) -> dict[str, Any]:
    row_bindings = getattr(row, "bindings", None)
    if not isinstance(row_bindings, Mapping):
        return {}

    exec_by_source: dict[str, list[str]] = {}
    for occurrence in plan.occurrence_map:
        for binding in occurrence.port_bindings:
            exec_by_source.setdefault(binding.source_var.name, []).append(
                binding.alias_local_execution_var.name
            )

    out: dict[str, Any] = {}
    for port_name, var in plan.head.ports.items():
        if port_name not in row_bindings:
            continue
        source_name = getattr(var, "name", None)
        if not isinstance(source_name, str) or not source_name:
            continue
        value = _public_term_value(row_bindings[port_name])
        for exec_name in exec_by_source.get(source_name, ()):
            out[exec_name] = value
    return out
```

Reuse of `_public_term_value(...)` is preferred over hand-rolled unwrapping.
`store.py` already imports from `factgraph.application.protocol.evaluate_result`,
so adding one private helper import is acceptable for this targeted fix.

## 6. Boundaries And Invariants

- The prober must remain row-specific for passed native explanations.
- A logical source variable may map to multiple execution-local variables across
  body occurrences; seed all of them.
- A typed row binding must be unwrapped before comparison with view facts.
- `closed_head_false` remains unanchored unless a row is supplied.
- Adapter engines keep row-id based anchoring.
- INV-single-stack remains in force: this bugfix lands on top of the v2 linear
  stack after S6d.

## 7. Acceptance

- [ ] Multi-row native result: `row[0].explain()` and `row[1].explain()` anchor
  to their respective row bindings and do not mix entity facts.
- [ ] The v1-style monotonic case still passes: adding an extra non-winning
  witness must not flip a holds explanation to fails.
- [ ] Multi-occurrence / join rule: every occurrence-local variable that maps to
  the same source variable is seeded; join evidence remains structurally present.
- [ ] OR branch rule: each row explanation remains anchored to that row.
- [ ] Typed values unwrap correctly for entity refs, strings, and ints.
- [ ] `closed_head_false` still produces evidence and does not regress.
- [ ] Souffle / ProbLog / PyReason dispatch tests remain green.
- [ ] Explain cohort remains green.

## 8. Implementation Plan

1. Import `_public_term_value` into `sdk/store.py` or promote a shared helper if
   the implementation finds a cleaner local boundary.
2. Replace `_initial_probe_bindings_for_row(...)` with the occurrence-map based
   seeding algorithm.
3. Add regression tests for multi-row anchoring, join/multi-occurrence seeding,
   OR branch anchoring, and typed-value unwrapping.
4. Run focused native explain/prober tests plus adapter dispatch regression
   tests.
5. Report any `%ENT` label issue separately; do not expand this bugfix.

## 9. Docs To Update

None expected. This is an evidence correctness bugfix, not a user-facing API
change.

## 10. Outcome / Deviations

To be filled after implementation.
