# Task Blueprint: Explain Conformance Batch F — aggregate explain verdict and repr

- Status: draft
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework post-D2 correction
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Design Authority: [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md) §5.7 / §308
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (primary edit target)
  - `tests/sdk/test_explain_conformance_native.py` (aggregate evaluate→explain conformance)
  - `tests/application/explain/test_prober.py` (targeted prober regression if useful)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-f-aggregate-explain.audit.md](./2026-06-10_explain-conformance-batch-f-aggregate-explain.audit.md)

---

## 1. Problem

Aggregate evaluate paths now work after Batch E, but native explain still
misrepresents aggregate compare atoms.

Observed shape for a passed row such as `total == sum(amount over orders)`:

```text
NotReached  60 equals ('sum', '$agg__amt', [('pred', 'order:amount', ['$agg__o', '$agg__amt'])])
```

Two defects:

1. Correctness: the row passed and `60 == 60`, so the aggregate compare atom
   should be `Holds`, not `NotReached`.
2. Repr: aggregate operand rendering leaks raw tuple structure and internal
   `$agg__...` variables.

## 2. Goals

1. Let prober aggregate compare atoms reach the aggregate-aware evaluation path
   (`_extend_env_with_atom → where_eval._eval_eq_atom/_eval_cmp_atom`).
2. Treat aggregate terms as self-contained during missing-variable preflight;
   do not count aggregate-internal variables as outer atom dependencies.
3. Render aggregate operands with friendly text such as `sum of amount`, not
   raw tuple text.
4. Add tests proving all five aggregate kinds explain with `Holds` and friendly
   repr for passed rows.
5. Preserve non-aggregate missing-variable and D2 no-free-enumeration behavior.

## 3. Non-goals

- Do not change `where_eval`, `diagnose_runtime`, or support-capture.
- Do not change aggregate evaluation semantics.
- Do not change seed mapping, DTOs, adapters, or EvidenceGraph schema.
- Do not rewrite aggregate DSL or add new aggregate kinds.
- Do not change quickstart docs in this batch unless a tiny targeted note is
  required.

## 4. Source Preflight

Confirmed source facts:

- `prober.py:_probe_atom(...)` calls `_missing_variables(...)` before
  `_extend_env_with_atom(...)` for non-binding atoms.
- `_missing_variables(...)` delegates to `_vars_in_atom_tuple(...)`.
- `_vars_in_atom_tuple(...)` recursively descends into every list/tuple, so an
  aggregate term like `("sum", "$agg__amt", [("pred", ..., ["$agg__o",
  "$agg__amt"])])` contributes `$agg__amt` and `$agg__o` as missing outer
  variables.
- `_extend_env_with_atom(...)` ultimately uses `where_eval`, whose compare/equal
  evaluation path is already aggregate-aware through `_resolve_eval_term(...)`.
- Therefore current prober blocks aggregate compare atoms before they reach the
  correct aggregate-aware evaluator.
- `tests/sdk/test_explain_conformance_native.py` already has 5 aggregate
  evaluate+explain tests, but they only assert row value and evidence presence;
  they do not assert atom verdict or aggregate repr text.
- `_render_term_value(...)` currently has no aggregate branch, so aggregate
  constants fall through to `str(value)`.

## 5. Proposed Shape

### 5.1 Missing-variable preflight

Update the prober variable scan used by `_missing_variables(...)` and
`_missing_verdict_dependencies(...)` so aggregate terms are treated as
self-contained values.

Expected behavior:

- outer compare atom vars are still checked;
- aggregate-internal target/filter vars are not considered missing outer
  dependencies;
- the atom then reaches `_extend_env_with_atom(...)`, which computes aggregate
  values through the existing `where_eval` aggregate-aware resolver.

Implementation options:

- teach `_vars_in_atom_tuple(...)` to stop descending when it sees an aggregate
  term; or
- add a dedicated `_vars_in_eval_atom(...)` used by missing checks.

The code should not reimplement aggregate evaluation.

### 5.2 Aggregate repr

Add friendly aggregate display for aggregate terms in the prober rendering path.

Recommended shape:

- detect aggregate term tuple `(kind, target, filter_atoms)`;
- render as `<kind> of <target label>`;
- for `count`, render `count`;
- for field-target aggregates, derive a stable target label from the target var
  and/or the aggregate filter predicate; e.g. `sum of amount`;
- never emit raw tuple/list text or `$agg__...` internal vars.

Exact wording is implementation-owned but must be stable and tested.

### 5.3 Scope boundaries

This fix is deliberately local to the explain prober. Batch E already aligned
support-capture with aggregate-aware evaluation, and `where_eval` already knows
how to compute aggregate terms.

## 6. Boundaries And Invariants

- **INV-eval-source-of-truth**: aggregate values must be computed only by the
  existing `where_eval` aggregate-aware path, not reimplemented in the prober.
- **INV-missing-nonaggregate**: non-aggregate missing-variable behavior remains
  unchanged.
- **INV-D2-no-leak**: verdict-mode key-unbound predicates still return
  `NotReached` rather than free-enumerating.
- **INV-render-no-internal-vars**: aggregate repr must not contain raw tuple
  text or `$agg__` internal variables.
- **INV-no-scope-creep**: no support-capture / seed / DTO / adapter diff.

## 7. Acceptance

- [ ] `count`, `sum`, `min`, `max`, and `mean` aggregate explain atoms on passed
  rows are `Holds`, not `NotReached`.
- [ ] Aggregate repr text is friendly and contains no raw tuple/list text and no
  `$agg__` variables.
- [ ] Existing aggregate row values remain correct.
- [ ] Non-aggregate compare missing-variable tests remain green.
- [ ] D2 senior / order-independence / no-leak regressions remain green.
- [ ] Batch A/B/C/E and adapter cohorts remain green.
- [ ] No `where_eval`, `diagnose_runtime`, support-capture, seed, DTO, or
  adapter implementation diff.

## 8. Implementation Plan

1. Add failing aggregate explain assertions to
   `tests/sdk/test_explain_conformance_native.py`.
2. Add any targeted prober-level regression if the SDK test is not precise
   enough for repr shape.
3. Update prober missing-variable scanning to treat aggregate terms as
   self-contained.
4. Add aggregate display support to the prober rendering path.
5. Run aggregate conformance, prober, native conformance, Batch D2, and broader
   explain cohort.

## 9. Docs To Update

None expected unless implementation changes the public aggregate repr wording in
a way that should be documented in `application/explain/docs/README.md`.

## 10. Outcome / Deviations

Pending.
