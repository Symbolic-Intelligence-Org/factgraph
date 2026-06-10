# Task Blueprint: Explain Conformance Batch C — NotAtom repr and negation flag

- Status: scoped
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework batch
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (`NotAtom` form/repr baking; primary edit target)
  - `src/factgraph/application/explain/evidence_tree.py` (`EvidenceAtom.negated`, read-only DTO context)
  - `src/factgraph/core/rules/where_eval.py` (`not` body normalization/evaluation semantics, read-only context)
  - `tests/application/explain/test_prober.py` (native prober NotAtom regressions)
  - `tests/test_souffle_evidence_graph.py` (existing adapter negation contract, read-only target shape)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-c-notatom-repr.audit.md](./2026-06-10_explain-conformance-batch-c-notatom-repr.audit.md)

---

## 1. Problem

Native prober `NotAtom` evidence currently falls through the generic builtin
path in `_atom_form(...)`.

The lowered `("not", body)` atom is represented as:

- `Builtin(kind="not", operands=(Const(<raw not-body list>),))`;
- `repr_text` from `_repr_builtin(...)`, which stringifies that raw body list;
- `EvidenceAtom.negated == False`.

That produces human text such as raw tuple/list dumps and leaves the structured
negation bit unset. This diverges from the existing Souffle evidence contract,
where negated leaves are rendered as friendly `!<inner atom>` text and carry
`negated=True`.

The verdict semantics are already correct. Batch C only fixes native evidence
shape/text for NotAtom.

## 2. Goals

1. Render native `NotAtom` evidence with friendly text, not raw lowered tuples.
2. Set `EvidenceAtom.negated=True` for native NotAtom evidence.
3. Reuse Batch B's unified value renderer for NotAtom inner atoms, so entity
   labels, float64 display, and `<unbound>` behavior stay consistent.
4. Preserve existing `not` verdict semantics and tree status behavior.
5. Keep adapter behavior unchanged; Souffle remains the target contract, not an
   edit target.

## 3. Non-goals

- Do not change `where_eval` / `_extend_env_with_atom` / `not` evaluation
  semantics.
- Do not change `EvidenceAtom` DTO shape; `negated` already exists.
- Do not change row seed construction, verdict cascade semantics, support
  capture, adapters, or certainty.
- Do not broaden this into general boolean-expression prose design beyond
  NotAtom inner body rendering.

## 4. Source Preflight

Confirmed source facts:

- `tests/test_souffle_evidence_graph.py` already locks the desired adapter
  shape:
  - a negated body atom has `atom.negated`;
  - `atom.repr_text == "!component_passivated(battery_2)"`;
  - verdict remains `Holds`.
- `EvidenceAtom.negated: bool = False` already exists and is serialized in
  `application/explain/evidence_tree.py`.
- `prober._atom_form(...)` has explicit branches for `pred`, comparison ops,
  and `in`; all other kinds, including `not`, fall into generic `Builtin(...)`.
- `prober._repr_builtin(...)` has a legacy `form.kind == "not"` text branch,
  but it only receives a stringified raw not-body list because `_atom_form(...)`
  has already lost the inner atom structure.
- `where_eval.py` owns actual `not` verdict semantics. Batch C should not
  duplicate or alter that logic.
- Batch B has already provided context-aware term rendering through
  `_bake_repr_text(...)` and downstream repr helpers.

## 5. Proposed Shape

### 5.1 Native NotAtom representation

When the lowered atom kind is `not`, native prober should produce an
`EvidenceAtom` with:

- `negated=True`;
- `repr_text` rendered from the inner body, not from the raw lowered list;
- the existing verdict from `_extend_env_with_atom(...)`.

The outer `form` may remain `Builtin(kind="not", ...)` as long as the repr text
and `negated` flag are correct. If implementation finds a cleaner internal form
without changing the public DTO, that is acceptable.

### 5.2 Inner body rendering

NotAtom body rendering should recursively render inner atoms through the same
repr machinery used by normal atoms:

- single inner atom: `!<inner repr>`;
- conjunction: `!(<a> && <b>)`;
- disjunction of conjunctions: `!((<a> && <b>) || (<c>))`.

Scope review accepted this code-like format family. Exact whitespace is not
important, but tests should lock one stable format. Implementation must verify
the actual lowered OR-of-AND shape before emitting `||`; if the structure is
not the expected two-level branch list, it should degrade to readable fallback
text rather than guess.

Required properties:

- no raw Python list/tuple repr;
- no raw lowered `$...` variable names for values that Batch B can render;
- entity-ref and float64 values use Batch B rendering;
- true-unbound values use Batch B's `<unbound>` behavior;
- unknown/unsupported inner form falls back gracefully to readable text, not an
  exception.

Defensive fallback text should still keep the negation surface obvious, using a
`!` prefix where possible.

### 5.3 Verdict boundary

Batch C must not decide whether a negated atom holds or fails. It only decorates
the result already returned by the current prober/evaluation path.

Tests should include both sides:

- negation succeeds (`not p(x)` when `p(x)` is absent) and `verdict` remains
  `Holds`;
- negation fails (`not p(x)` when `p(x)` is present) and `verdict` remains
  `Fails`.

## 6. Boundaries And Invariants

- **INV-verdict-stable**: Batch C changes repr/negated metadata only. The
  verdict classes for NotAtom do not change.
- **INV-souffle-contract**: native NotAtom display aligns with the existing
  Souffle shape: `negated=True` plus `!<inner repr>`.
- **INV-Batch-B-renderer**: inner NotAtom rendering reuses Batch B value
  rendering; it must not introduce a second idref/float display implementation.
- **INV-no-DTO-change**: `EvidenceAtom` shape remains unchanged.
- **INV-adapter-boundary**: Souffle/ProbLog/PyReason converters are not edited.

## 7. Acceptance

- [ ] Native NotAtom with a single inner atom renders as `!<friendly inner>`.
- [ ] Native NotAtom with multi-atom AND body renders a stable grouped form,
  e.g. `!(a && b)`, with friendly inner terms.
- [ ] Native NotAtom with OR-of-AND body renders a stable grouped form, e.g.
  `!((a && b) || c)`.
- [ ] Native NotAtom sets `EvidenceAtom.negated=True`.
- [ ] Native NotAtom verdicts remain unchanged for both holding and failing
  negation cases.
- [ ] Repr text has no raw Python tuple/list dumps and no avoidable internal
  `$...` variable names.
- [ ] Entity-ref and float64 values inside NotAtom body use Batch B rendering.
- [ ] Existing G1 monotonic, Batch A seed, Batch D verdict cascade, Batch E
  aggregate, Batch B repr, and adapter cohorts remain green.
- [ ] No implementation diff in DTOs, seed builder, support-capture, or adapter
  converters.

## 8. Implementation Plan

1. Add failing native prober tests for current NotAtom repr:
   - single inner atom;
   - multi-atom AND body;
   - OR-of-AND body;
   - both negation Holds and Fails cases;
   - entity-ref and/or float64 inner values.
2. Extend prober NotAtom handling so `_probe_atom(...)` can set
   `negated=True`.
3. Add a private helper for rendering not-body branches by recursively applying
   the existing atom repr path.
4. Ensure `_repr_builtin(...)` legacy `kind == "not"` fallback no longer
   stringifies raw lowered lists in the main path. It may remain as a defensive
   fallback if no production NotAtom reaches it.
5. Run focused prober/conformance tests and the broader explain cohort.

## 9. Docs To Update

No public docs expected in this batch. Final conformance cleanup should mention
that native and Souffle negation evidence now share the `negated=True` /
`!<inner>` convention.

## 10. Outcome / Deviations

To be filled after implementation and gate.
