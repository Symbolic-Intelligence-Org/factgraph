# Audit Log: Explain Conformance Batch C — NotAtom repr and negation flag

Paired with [2026-06-10_explain-conformance-batch-c-notatom-repr.md](./2026-06-10_explain-conformance-batch-c-notatom-repr.md).

---

## A. Source Preflight (2026-06-10)

Codex read these shipped anchors before drafting:

- `src/factgraph/application/explain/prober.py`
  - `_atom_form(...)`
  - `_bake_repr_text(...)`
  - `_repr_builtin(...)`
  - `_render_term_value(...)`
- `src/factgraph/application/explain/evidence_tree.py`
  - `EvidenceAtom.negated`
  - Evidence serialization/deserialization of `negated`
- `src/factgraph/core/rules/where_eval.py`
  - `_eval_not_atom(...)`
  - `_normalize_not_body(...)`
  - `not` validation paths
- `tests/test_souffle_evidence_graph.py`
  - existing `negated=True` / `!component_passivated(...)` contract
- `tests/application/explain/test_prober.py`
  - current native prober coverage and Batch B/D regressions

## B. Preflight Findings

1. `EvidenceAtom.negated` already exists and is serialized, so no DTO change is
   required.
2. Souffle already establishes the desired visible shape:
   `negated=True`, friendly `!<inner>` repr text, and unchanged verdict.
3. Native prober does not special-case `kind == "not"` in `_atom_form(...)`.
   It packages the entire not-body list as a `Const(list)`.
4. `_repr_builtin(...)` has a legacy `form.kind == "not"` branch, but because
   the operand is the raw not-body list, it still prints lowered Python data
   rather than an inner atom repr.
5. Batch B's renderer is already available through `_bake_repr_text(...)` and
   downstream helpers. Batch C should reuse it instead of adding a new
   idref/float display path.
6. `where_eval.py` owns `not` truth semantics. Batch C should not change it.

## C. Scope Questions For Review

1. **Not-body prose style**:
   Draft proposes `!<inner>` for one atom, `!(a && b)` for conjunction, and
   `!((a && b) || c)` for OR-of-AND. Scope review should approve or adjust the
   exact grouping syntax before implementation.

2. **Internal form strategy**:
   Draft permits the outer form to remain `Builtin(kind="not", ...)` if
   `repr_text` and `negated=True` are correct. Scope review may require a more
   structured internal form, but no public DTO change should happen in Batch C.

3. **Fallback policy**:
   Draft requires graceful readable fallback for unsupported inner structures,
   not an exception. Scope review should decide whether defensive fallback text
   should still use the `!` prefix.

Scope-review decisions:

- Not-body prose style approved: `!a` for one atom, `!(a && b)` for
  conjunction, and `!((a && b) || c)` for OR-of-AND. Tests should lock one
  stable syntax. `and` / `or` wording is not required.
- OR-of-AND rendering must be source-verified before implementation. The
  single-AND case is confirmed as a flat list of inner atoms. If OR lowered
  structure differs from the expected two-level branch list, implementation
  should degrade to readable non-throwing fallback instead of inventing
  semantics.
- The outer form may remain `Builtin(kind="not", ...)`; public DTO shape must
  not change. The acceptance criteria are the `negated=True` flag, friendly
  repr, and verdict stability.
- Defensive fallback should preserve a visible negation marker (`!`) where
  possible.

## D. Required Tests

Batch C implementation must include tests that fail on current native prober
behavior:

1. Single-atom NotAtom repr is friendly, prefixed with `!`, and has
   `negated=True`.
2. Negation that holds keeps a `Holds` verdict.
3. Negation that fails keeps a `Fails` verdict.
4. Multi-atom AND not-body renders a grouped form without raw tuples/lists.
5. OR-of-AND not-body renders a grouped form without raw tuples/lists.
6. Inner entity-ref and float64 values reuse Batch B rendering.
7. Existing Batch A/B/D/E and adapter cohorts remain green.

## E. Implementation Outcome

To be filled after implementation and gate.
