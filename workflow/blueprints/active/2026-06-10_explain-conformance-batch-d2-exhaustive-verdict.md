# Task Blueprint: Explain Conformance Batch D2 — exhaustive verdict track after upstream failure

- Status: implemented
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework post-closure correction
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Design Authority: [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md) §307-308
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (primary behavior change)
  - `src/factgraph/application/explain/docs/README.md` (verdict semantics docs)
  - `tests/application/explain/test_prober.py` (unit regressions)
  - `tests/sdk/test_explain_conformance_native.py` (native evaluate-to-explain regressions)
  - `examples/explain_layer_demo.py` (demo expectation, if still exposing senior/failed branch)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-d2-exhaustive-verdict.audit.md](./2026-06-10_explain-conformance-batch-d2-exhaustive-verdict.audit.md)

---

## 1. Problem

Batch D fixed the worst verdict cascade bug, but it still freezes the
explanation verdict environment after an upstream failure. That leaves a
residual deviation from the governing design.

Design §307-308 says:

- the prober is exhaustive and does not voluntarily skip later atoms;
- `NotReached` is caused only by unbound variables;
- an earlier atom returning `Fails` does not make later atoms `NotReached`;
- if a later atom's dependencies are bound, the prober continues evaluating it.

Current Batch D behavior:

- candidate envs become empty after an atom fails, which is correct for branch
  execution and tree status;
- verdict-only evaluation uses the last non-empty prefix env, but does not
  advance that explanation env with later bind-producing atoms;
- therefore an atom sequence such as
  `[age, age >= 65 Fails, region_pred, region == us]` reports the region atoms
  as `NotReached`, while `[age, region_pred, age >= 65 Fails, region == us]`
  can report `region == us` as `Holds`.

That order dependency is not the intended exhaustive semantics.

## 2. Goals

1. Keep the **candidate track** unchanged: after a failed atom, candidate envs
   stay empty and the tree remains `status="fails"`.
2. Add an exhaustive **explanation track**: after a failed atom, keep evaluating
   later atoms with row-anchored verdict envs.
3. Let a downstream atom that can be evaluated from row-anchored envs return
   its own `Holds` or `Fails`.
4. Advance explanation envs when a downstream bind-producing atom succeeds, so
   later atoms can consume its outputs.
5. Preserve `NotReached` only for true direct unbound dependencies.
6. Preserve no-leakage: a key-unbound predicate after failure must not
   free-enumerate all facts.
7. Update module docs to describe exhaustive verdict advancement.

## 3. Non-goals

- Do not resurrect failed branch candidate envs.
- Do not change row seed construction. Batch A owns seed mapping.
- Do not change DTOs, adapters, support-capture, schema rendering, or NotAtom
  rendering.
- Do not change value rendering. Batch B owns `_term_display` behavior.
- Do not rewrite quickstart docs in this correction slice.

## 4. Source Preflight

Confirmed source facts:

- `prober.py:_probe_branch(...)` tracks:
  - `envs`: current candidate envs;
  - `last_non_empty_envs`: the Batch D verdict-only anchor;
  - `failed_upstream`: whether a previous atom failed.
- `prober.py:_probe_atom(...)` sets
  `verdict_only = failed_upstream and not envs`.
- In verdict-only mode it runs `_extend_env_with_atom(...)` against
  `verdict_envs` if direct variables are present, but returns the original empty
  `candidate_envs`.
- `_probe_branch(...)` updates `last_non_empty_envs` only when returned
  candidate envs are non-empty. Because verdict-only mode returns empty
  candidate envs by design, explanation envs freeze after the first failure.
- `explain/docs/README.md` currently documents Batch D's frozen-prefix wording:
  "compute downstream verdicts from the last row-anchored prefix environment".
  That is now stale relative to design §308.

## 5. Proposed Shape

Preserve the dual-track model, but make the explanation track advance
exhaustively.

### 5.1 Candidate track

Candidate envs represent branch execution state:

- before failure, they follow the normal G1 backtracking path;
- after failure, they remain empty;
- they are the only envs that can make a branch continue as a successful
  candidate chain;
- D2 must never return explanation envs as candidate envs after upstream
  failure.

### 5.2 Explanation track

Explanation envs represent row-anchored verdict evaluation:

- before failure, they track the same successful prefix envs as today;
- after failure, `_probe_atom(...)` evaluates later atoms using explanation envs
  if the atom's direct dependencies are present;
- if `_extend_env_with_atom(...)` yields next envs, the atom verdict is `Holds`
  and the explanation track advances to those envs;
- if dependencies are bound but `_extend_env_with_atom(...)` yields no envs,
  the atom verdict is `Fails` and the explanation track remains at the previous
  envs for later independent atoms;
- if dependencies are genuinely missing, the atom verdict is
  `NotReached(blocked_by=...)` and the explanation track remains unchanged.

Implementation may make `_probe_atom(...)` return a third value such as
`next_verdict_envs`, or may use a small internal result object. The semantic
split must remain explicit.

### 5.3 No free enumeration guard

The explanation track is allowed to probe only row-anchored facts. In
failed-upstream verdict mode, a predicate atom with an unbound key/input must
return `NotReached`, not enumerate every fact in the relation.

Recommended implementation shape:

- keep using `_missing_variables(...)` for normal non-binding checks;
- add a verdict-mode dependency helper for bind-producing predicate atoms;
- require at least the predicate key/input variable to be bound before running
  `_extend_env_with_atom(...)`;
- if the key/input variable is missing, return `NotReached(blocked_by=...)`.

The exact key heuristic is implementation-owned but must be justified in the
audit. The expected common case is field predicates where the first argument is
the entity key already seeded by Batch A.

Scope-review lock: this is not a second notion of "missing". The no-free-
enumeration guard and design §305 `NotReached` are the same dependency check.
If the atom's input dependency is bound, run a pinned `_extend_env_with_atom`.
If the dependency is not bound, return `NotReached(blocked_by=...)`.

For predicate atoms, the operational key is the entity subject position
(`term0`) for field/identity/exists-style predicates. If that subject variable
is unbound in failed-upstream explanation mode, return `NotReached` instead of
free-enumerating. Unknown predicate shapes should fail closed to `NotReached`.

### 5.4 Order independence

For a row-anchored rule, downstream verdicts should not depend on whether a
bind-producing predicate appears before or after a failing filter, as long as
its key dependencies are bound by the row anchor.

Example target:

- `[age, age >= 65 Fails, region_pred, region == us]`
- `[age, region_pred, age >= 65 Fails, region == us]`

Both should report the same verdicts for `region_pred` and `region == us`.

## 6. Boundaries And Invariants

- **INV-exhaustive-308**: upstream `Fails` does not by itself produce later
  `NotReached`.
- **INV-no-resurrection**: branches with any failed atom remain `status="fails"`.
- **INV-no-free-enumeration**: key-unbound predicate atoms after failure must
  not enumerate all rows.
- **INV-row-anchored**: explanation env advancement must stay within row seed
  bindings and facts compatible with those bindings.
- **INV-G1**: normal candidate backtracking before failure remains unchanged.
- **INV-Batch-A/B/C/E**: seed mapping, value rendering, NotAtom rendering, and
  aggregate support-capture remain green.

## 7. Acceptance

- [x] Upstream failed filter followed by dependency-bound downstream predicate
  yields `Holds` or `Fails`, not `NotReached`.
- [x] Senior demo shape: `age >= 65` returns `Fails`, then
  `User u-1 is in region us` returns `Holds`, then `us equals us` returns
  `Holds`.
- [x] Equivalent rule orders produce the same downstream verdicts.
- [x] A truly unbound downstream dependency still returns
  `NotReached(blocked_by=...)`.
- [x] A failed branch remains `status="fails"` after downstream `Holds`.
- [x] Multi-entity tests show no cross-entity leakage after upstream failure.
- [x] G1 monotonic witness regression remains green.
- [x] Batch A seed conformance, Batch B rendering, Batch C NotAtom, and Batch E
  aggregate tests remain green.
- [x] `src/factgraph/application/explain/docs/README.md` describes exhaustive
  explanation-track advancement.
- [x] No seed, DTO, adapter, or support-capture implementation diff.

## 8. Implementation Plan

1. Add failing tests for the design §308 senior-order case.
2. Add an order-independence test for the same logical row facts with atoms
   before/after the failed filter.
3. Add a true-unbound dependency test that must stay `NotReached`.
4. Refactor `_probe_branch(...)` / `_probe_atom(...)` to carry both candidate
   envs and explanation envs.
5. Add the verdict-mode no-free-enumeration guard for bind-producing predicate
   atoms.
6. Update explain module docs.
7. Run prober, native conformance, demo, and broader explain cohort.

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`
- `examples/explain_layer_demo.py` if the demo's expected text still describes
  senior-branch `NotReached`

## 10. Outcome / Deviations

Implemented in `d4747a88`.

Outcome:

- `_probe_branch(...)` now carries an explicit explanation verdict track in
  addition to the candidate track.
- `_probe_atom(...)` returns candidate envs and explanation envs separately.
  After upstream failure, candidate envs remain empty while explanation envs can
  keep advancing through row-anchored atoms.
- The no-free-enumeration guard is unified with the `NotReached` dependency
  check: bind-producing predicate atoms require the subject/key position
  (`term0`) to be bound before they may call `_extend_env_with_atom(...)`.
- The module docs now describe exhaustive explanation-track advancement after
  upstream failure.

Reviewer gate passed:

- §308 senior path now reports `30 >= 65` as `Fails`, then
  `User u-1 is in region us` as `Holds`, then `us equals us` as `Holds`.
- Equivalent atom orders produce the same downstream verdicts.
- Key-unbound predicate atoms after failure remain `NotReached` and do not leak
  other entities.
- Failed branches stay `status="fails"`.
- G1 monotonic and Batch A/B/C/E regressions remained green.

Deviation:

- `examples/explain_layer_demo.py` already had pre-existing local changes. The
  implementation commit intentionally did not stage that file; the demo was
  still run and showed the expected exhaustive senior-path output.
