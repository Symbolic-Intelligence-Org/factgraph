# Task Blueprint: Explain Conformance Batch F — aggregate explain verdict and repr

- Status: implemented
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
2. Treat aggregate-local variables as self-contained during missing-variable
   preflight while preserving correlated outer variables as real dependencies.
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
- aggregate-local target/filter vars are not considered missing outer
  dependencies;
- correlated outer vars referenced by the aggregate filter remain dependencies;
- the atom then reaches `_extend_env_with_atom(...)`, which computes aggregate
  values through the existing `where_eval` aggregate-aware resolver.

Implementation options:

- add a dedicated missing-check variable scanner used by `_missing_variables`
  and `_missing_verdict_dependencies`;
- detect lowered aggregate terms `(kind, target, filter_atoms)`;
- exclude aggregate-local variables from the missing set, but keep correlated
  outer variables.

The runtime lowered form uses aggregate-local variables in the `$agg...`
namespace. That namespace is the implementation-level carrier for the
source-level distinction described by `where_ast_validate`:

- local target/filter variables such as `$agg__amt` / `$_agg1` are internal to
  aggregate computation and must not block the outer atom;
- non-aggregate-prefixed variables referenced by the aggregate filter are
  correlated outer dependencies and must still be present in the row-anchored
  environment;
- if such correlated vars are missing, the atom is `NotReached` rather than
  free-computing the aggregate over all facts.

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
- **INV-correlated-aggregate-no-leak**: correlated aggregate filter variables
  that are not bound by the row/prefix environment remain missing dependencies;
  the prober must not free-compute a correlated aggregate.
- **INV-render-no-internal-vars**: aggregate repr must not contain raw tuple
  text or `$agg__` internal variables.
- **INV-no-scope-creep**: no support-capture / seed / DTO / adapter diff.

## 7. Acceptance

- [x] `count`, `sum`, `min`, `max`, and `mean` aggregate explain atoms on passed
  rows are `Holds`, not `NotReached`.
- [x] Aggregate repr text is friendly and contains no raw tuple/list text and no
  `$agg__` variables.
- [x] Correlated aggregate with its correlation variable bound evaluates to
  `Holds` when the aggregate value matches.
- [x] Correlated aggregate with its correlation variable unbound is
  `NotReached`, does not free-compute, and does not leak unrelated facts.
- [x] Existing aggregate row values remain correct.
- [x] Non-aggregate compare missing-variable tests remain green.
- [x] D2 senior / order-independence / no-leak regressions remain green.
- [x] Batch A/B/C/E and adapter cohorts remain green.
- [x] No `where_eval`, `diagnose_runtime`, support-capture, seed, DTO, or
  adapter implementation diff.

## 8. Implementation Plan

1. Add failing aggregate explain assertions to
   `tests/sdk/test_explain_conformance_native.py`.
2. Add any targeted prober-level regression if the SDK test is not precise
   enough for repr shape.
3. Update prober missing-variable scanning to treat aggregate terms as
   local-self-contained while preserving correlated outer dependencies.
4. Add aggregate display support to the prober rendering path.
5. Run aggregate conformance, prober, native conformance, Batch D2, and broader
   explain cohort.

## 9. Docs To Update

None expected unless implementation changes the public aggregate repr wording in
a way that should be documented in `application/explain/docs/README.md`.

## 10. Outcome / Deviations

Implemented in `86437ccc`; reviewer-gate remediation in `f2df0e89`.

Outcome:

- Native aggregate compare atoms now pass missing-variable preflight and reach
  the existing aggregate-aware `where_eval` resolver.
- Aggregate operands render as friendly text (`count`, `sum of amount`,
  `min of amount`, `max of amount`, `mean of amount`) instead of raw tuples.
- Correlated aggregate filters preserve outer dependencies: bound correlation
  vars evaluate normally; missing correlation vars produce `NotReached` and do
  not free-compute over unrelated facts.
- Reviewer gate found `count(None, [amount($order, $amount)])` still blocked on
  the value-position filter variable. The follow-up `f2df0e89` switched the
  local-var calculation to use canonical aggregate filter binding data and
  hardened the count test to use a field-predicate filter.

Tests:

- `NativeAggregateExplainConformanceTests`: `8 OK`.
- `tests.application.explain.test_prober` + native conformance: `33 OK`.
- Broader explain/schema/adapter cohort: `143 OK`.
- Aggregate DSL/eval/adapter cohort: `50 OK`.
- `examples/explain_layer_demo.py` runs coherently.

Post-remediation tests:

- Native aggregate explain: `8 OK`.
- Prober + native conformance: `33 OK`.
- Broader explain/schema/adapter cohort: `143 OK`.
- Aggregate DSL/eval/adapter cohort: `50 OK`.
- `examples/explain_layer_demo.py` runs coherently.

Deviation:

- The runtime lowered form does not preserve source `AggregateAtom` nodes, so
  the implementation combines lowered aggregate conventions with canonical
  aggregate filter binding data. Predicate subject terms and aggregate target
  vars are aggregate-local; value-position vars are aggregate-local only when
  canonical filter data says the filter binds them and the var has lowered-local
  shape. Plain correlation vars remain outer dependencies. This keeps the scope
  local to `prober.py` without changing `where_eval` or lowering metadata.
