# Audit Log: Explain Conformance Batch D — prober verdict cascade semantics

Paired with [2026-06-10_explain-conformance-batch-d-verdict-cascade.md](./2026-06-10_explain-conformance-batch-d-verdict-cascade.md).

---

## A. Source Preflight (2026-06-10)

Codex read these shipped anchors before drafting:

- `src/factgraph/application/explain/prober.py`
  - `probe_native(...)`
  - `_probe_branch(...)`
  - `_probe_atom(...)`
  - `_tree_status(...)`
  - `_atom_status(...)`
  - `_verdict_status(...)`
- `src/factgraph/application/explain/evidence_tree.py`
  - `Holds`, `Fails`, `NotReached`, `EvidenceAtom`, `EvidenceTree`.
- `src/factgraph/application/explain/docs/README.md`
  - Verdict semantics section.
- Existing tests:
  - `tests/application/explain/test_prober.py`
  - `tests/sdk/test_explain_conformance_native.py`

## B. Preflight Findings

1. `_probe_branch(...)` has access to `initial_bindings`, the row anchor
   produced by Batch A.
2. `_probe_atom(...)` currently receives only the current candidate env tuple.
3. A failed atom returns an empty env tuple and sets `failed_upstream=True`.
4. Downstream atoms therefore see `envs=()` and return `Fails()` even if their
   own terms are fully bound by the row anchor and would hold.
5. `_tree_status(...)` already makes the tree fail if any body rule contains a
   failed atom, so downstream Holds after an earlier Fails cannot falsely make
   the tree hold.
6. `NotReached` docs explicitly reject using NotReached as a generic
   previous-failure marker.

## C. Scope Questions For Review

1. **Free enumeration in verdict-only mode**:
   The draft recommends not allowing bind-producing atoms to freely enumerate
   from an empty anchor after upstream failure. They should either check against
   directly bound row-anchor variables or return `NotReached`. Scope review
   should confirm this strict interpretation.

2. **Candidate chain resurrection**:
   The draft recommends returning the original empty candidate env tuple after
   verdict-only checks, even if the current atom independently holds. Scope
   review should confirm this, because otherwise later atoms might accidentally
   continue from a resurrected branch.

3. **Tree/head ports after upstream failure**:
   `_head_rule_for_plan(...)` falls back to `initial_bindings` when
   `terminal_envs` is empty. This is already the right shape for row-anchored
   failed explanations. Scope review should confirm no change is needed.

Scope-review decisions:

- Use **last non-empty prefix envs** as verdict-only anchors after upstream
  failure, falling back to the initial row seed when no prefix survived. This is
  more faithful than row-seed-only anchors for downstream check atoms whose
  variables were bound by an earlier holding atom.
- Preserve no-resurrection: verdict-only anchors must never be returned as the
  branch candidate env tuple.
- Keep `NotReached` direct-only: bind-producing atoms or check atoms with
  missing direct variables under the selected verdict anchors return
  `NotReached`, not free enumeration.
- Edit target remains `prober.py` plus tests; seed builder, DTOs, adapters, and
  support-capture stay out of scope.

## D. Required Tests

Batch D implementation must include tests that fail on the current cascade:

1. Upstream atom fails; downstream atom is fully row-anchored and true;
   downstream verdict is `Holds`, not `Fails`.
2. Upstream atom fails; downstream atom has a direct unbound dependency;
   downstream verdict is `NotReached(blocked_by=...)`.
3. Tree status remains `fails` when any earlier atom failed.
4. Existing monotonic witness backtracking remains green.
5. Existing Batch A native conformance tests remain green.

## E. Implementation Outcome

Implemented in `9b3c912f`.

Implementation notes:

- `_probe_branch(...)` now tracks `last_non_empty_envs` alongside the true
  candidate env chain.
- `_probe_atom(...)` receives `verdict_envs` and enters verdict-only mode when
  `failed_upstream and not envs`.
- Verdict-only mode checks direct variable availability with
  `_missing_variables(...)`; missing variables produce `NotReached`, while
  runnable atoms are evaluated against the prefix anchor.
- Verdict-only `Holds` never returns the verdict anchors as candidate envs, so
  the branch cannot resurrect after an earlier failed atom.

Added tests:

- `test_downstream_check_after_failed_upstream_can_hold_from_prefix_anchor`
- `test_downstream_bind_atom_after_failed_upstream_is_not_reached_when_unbound`

Reviewer gate:

- PASS.
- Reviewer independently confirmed the more faithful prefix-anchor semantics:
  after `30 >= 65` failed, downstream `region(u-1, us)` and `us equals us`
  reported `Holds`, while the tree status remained `fails`.
- Reviewer confirmed the same probe had zero `u-2` leakage, preserving Batch A
  row anchoring.
- Reviewer confirmed direct missing variables still produce `NotReached`.
- Reviewer reran the G1 monotonic regression and broader explain/conformance
  cohort successfully.

Boundary:

- Only `prober.py` and `test_prober.py` changed in the implementation commit.
- DTO, adapter, support-capture, seed-builder, and lowering implementation
  paths were untouched.
