# Task Blueprint: Explain Conformance Batch D — prober verdict cascade semantics

- Status: implemented
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework batch
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (verdict/env propagation; primary edit target)
  - `src/factgraph/application/explain/docs/README.md` (verdict semantics authority; read-only unless docs drift is found)
  - `tests/application/explain/test_prober.py` (prober unit regressions)
  - `tests/sdk/test_explain_conformance_native.py` (native conformance battery)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-d-verdict-cascade.audit.md](./2026-06-10_explain-conformance-batch-d-verdict-cascade.audit.md)

---

## 1. Problem

The native prober currently conflates "upstream emptied the candidate env
chain" with "this atom failed".

In `_probe_branch(...)`, once an earlier atom returns `Fails`, `failed_upstream`
is set and subsequent atoms receive the empty env tuple produced by that
failure. `_probe_atom(...)` then has no runnable envs and returns `Fails()` for
downstream atoms even when the downstream atom would hold against the row's
anchored bindings.

That violates the documented verdict semantics:

- `NotReached` is reserved for direct unbound-variable dependencies.
- It is not a generic "previous atom failed" marker.
- An atom holds if at least one next environment survives.

So the downstream atom verdict must describe the downstream atom itself, not the
side effect of an earlier atom clearing the candidate env chain.

## 2. Goals

1. Preserve G1 witness backtracking and normal candidate-env semantics for
   successful prefixes.
2. When upstream has failed and the current candidate env tuple is empty,
   evaluate the current atom's own verdict against the row's anchored initial
   bindings.
3. Emit `Holds` or `Fails` when the current atom's variables are directly bound
   by the row anchor and the atom can be checked.
4. Emit `NotReached(blocked_by=...)` only when the current atom has a direct
   unbound-variable dependency under the row anchor.
5. Do not resurrect the branch candidate env chain after upstream failure; the
   overall branch/tree must remain failed if an earlier atom failed.

## 3. Non-goals

- Do not change row seed construction. Batch A owns that.
- Do not change repr rendering or internal `$` display. Batch B owns Bug 5.
- Do not change NotAtom rendering. Batch C owns Bug 6.
- Do not change adapter dispatch, DTOs, or support-capture.
- Do not weaken G1 monotonic witness backtracking.

## 4. Source Preflight

Confirmed source facts:

- `prober.py:_probe_branch(...)` starts with
  `envs = (ProbeEnv.from_bindings(initial_bindings),)`.
- Normal atom evaluation threads `envs` forward through `_probe_atom(...)`.
- If an atom returns `Fails`, `_probe_atom(...)` returns an empty env tuple and
  `_probe_branch(...)` sets `failed_upstream = True`.
- Subsequent atoms currently see `failed_upstream=True` and `envs=()`, so they
  return `Fails()` because there are no runnable envs.
- `_probe_branch(...)` still has `initial_bindings`, the row-anchored seed that
  should be used for verdict-only downstream checks.
- `_tree_status(...)` already keeps a tree failed if any body rule has a failed
  atom. Therefore downstream `Holds` after an earlier `Fails` does not make the
  whole tree hold.
- `explain/docs/README.md` says `NotReached` is only for direct unbound-variable
  dependencies, not generic previous failure.

## 5. Proposed Shape

Add a verdict-only anchored fallback path for atoms after upstream failure.

Expected implementation outline:

```python
anchor_envs = (ProbeEnv.from_bindings(initial_bindings),)
envs = anchor_envs

...

evidence_atom, envs = _probe_atom(
    atom,
    before_envs,
    anchor_envs=anchor_envs,
    failed_upstream=failed_upstream,
    ...
)
```

Inside `_probe_atom(...)`:

1. If `envs` is non-empty, keep the existing G1 path.
2. If `envs` is empty and `failed_upstream` is true, use the last non-empty
   prefix env tuple as verdict-only anchors. If the first atom failed and no
   prefix survived, fall back to the row's initial anchor env.
3. In that verdict-only mode, do **not** free-enumerate bind-producing atoms
   from an empty anchor. The atom should be runnable only if its direct
   variables are bound in the anchor env. If variables are missing, return
   `NotReached(blocked_by=...)`.
4. If the atom is runnable from the anchor and `_extend_env_with_atom(...)`
   yields at least one env, return `Holds`.
5. If it is runnable but yields no env, return `Fails`.
6. Return the original empty `envs` to the caller when in verdict-only upstream
   failure mode, so downstream atoms are also checked against the row anchor but
   the branch candidate chain is not resurrected.

The chosen Batch D semantics are **last-non-empty prefix anchors** rather than
row-seed-only anchors. This is more faithful for downstream check atoms whose
variables were bound by a previously holding body atom. It still cannot
resurrect the branch, because verdict-only evaluation never returns the anchor
envs as candidate envs.

The exact helper names are open to implementation, but the semantic split must
be explicit: **verdict envs** can use row anchors after upstream failure;
**candidate envs** remain the true branch execution state.

## 6. Boundaries And Invariants

- **INV-G1**: normal non-failed prefixes keep existing backtracking semantics;
  adding a non-winning witness must not flip a later successful env from Holds
  to Fails.
- **INV-no-resurrection**: a branch with an earlier failed atom remains failed,
  even if a downstream atom is independently true under row anchors.
- **INV-notreached-direct-only**: `NotReached` is emitted only when the current
  atom has a direct missing variable under the row anchor.
- **INV-passed-regression**: passed rows that currently produce all-Holds paths
  remain all-Holds.
- **INV-Batch-A**: projection/external/OR/join row anchoring remains intact.

## 7. Acceptance

- [x] Repro: upstream atom fails, downstream atom is independently true under
  row anchors, downstream verdict is `Holds`, not `Fails`.
- [x] Repro: upstream atom fails, downstream atom has a direct missing variable,
  downstream verdict is `NotReached(blocked_by=...)`.
- [x] A branch with an earlier failed atom remains `status="fails"` even when
  a downstream atom holds independently.
- [x] Existing `test_monotonic_witness_backtracking_keeps_later_successful_env`
  remains green.
- [x] Passed-row native conformance remains green.
- [x] Batch A projection/external/OR/join row anchoring tests remain green.
- [x] No DTO, adapter, support-capture, or seed-builder implementation diff.

## 8. Implementation Plan

1. Add failing prober unit tests for the upstream-fail/downstream-holds case.
2. Add failing prober unit tests for upstream-fail/downstream-direct-unbound
   `NotReached`.
3. Thread anchor envs through `_probe_branch(...)` into `_probe_atom(...)`.
4. Add a verdict-only path in `_probe_atom(...)` for
   `failed_upstream and not envs`.
5. Keep returned candidate envs empty in verdict-only mode.
6. Run prober tests, native conformance tests, Batch A tests, and explain
   cohort.

## 9. Docs To Update

No docs expected unless implementation discovers drift from
`application/explain/docs/README.md`. The docs already state the intended
`NotReached` semantics.

## 10. Outcome / Deviations

Implemented in `9b3c912f`.

Batch D chose the more faithful **last-non-empty prefix anchor** semantics from
scope review. `_probe_branch(...)` tracks the last non-empty candidate env
tuple and passes it as verdict-only context after upstream failure. `_probe_atom`
uses those verdict envs only to decide the current atom's own verdict, and
returns the original empty candidate env tuple in verdict-only mode. This keeps
the branch failed and prevents resurrection while allowing downstream atoms
whose variables are fully bound by the prefix anchor to report `Holds`.

Implementation scope was intentionally narrow:

- `src/factgraph/application/explain/prober.py`
- `tests/application/explain/test_prober.py`

No DTO, adapter, support-capture, seed-builder, or lowering implementation was
changed.

Reviewer gate passed:

- Independent probe confirmed an upstream failure followed by
  `region(u-1, us)` / `us equals us` now reports downstream `Holds`, while the
  tree remains `fails`.
- The same probe confirmed no cross-entity leakage after Batch A; `u-2` data did
  not appear in the row-anchored failed explanation.
- Directly unbound downstream atoms return `NotReached(blocked_by=...)`.
- G1 monotonic witness regression remained green.
- Broader explain/conformance cohort remained green.

Carry-forward: Batch D reduced the surface of Bug 5 by giving many failed-path
atoms anchored values, but true unbound `NotReached` repr text can still expose
internal `$...` variable names. That remains assigned to Batch B's unified value
rendering work.
