# Walker and Advanced Importables

`kernel.sdk` is the ergonomic product surface, but the kernel exposes
a wider set of capabilities through direct imports. This page covers
when and why to drop down.

For the SDK API see [`04_api_surface.en.md`](04_api_surface.en.md).
For everyday what-if usage see
[`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

---

## When the SDK isn't the right tool

The SDK is designed for the common case: typed Python in-process.
Reach for the layers below when you need:

- **Wire bridges** — JSON in, JSON out across processes or languages.
  The SDK accepts and returns Python objects; serializing them back
  out is your responsibility.
- **LLM-generated payloads** — when the calling code is producing
  derivations or overlays from string templates, raw application
  protocol DTOs (`EvaluationOverlay`, `RuleLiteralPath`,
  `RuleAddedAtom`, etc.) are the only path for some advanced
  constructs that don't yet have an SDK builder. Construct them
  directly — the constructors are precise about their fields, so
  read `kernel.application.protocol` before composing.
- **Walker-driven analysis** — proof-frame diffs and large
  `SupportArtifact` trees are easier to navigate via walker views
  than via direct attribute access.
- **Round event recording** — the recorder lifecycle
  (`start_round`, `record_round_event`, `finalize_round`) is mutable
  and stateful; the SDK keeps it out of the namespace surface on
  purpose.
- **Engine adapter registration** — the SDK does not auto-discover
  adapters; you register the ones you need.

Each of these is reachable via direct import from the relevant kernel
package. The SDK never auto-wraps these surfaces, so cost is paid only
when you actually need them.

---

## 1. Walker views

The walker module provides traversal-friendly views over runtime
artifacts. The most common one is `ProofFrameDiffView` for navigating
the result of `fg.audit.diff_proof_frames(...)`.

```python
from kernel.application.walker import ProofFrameDiffView

diff = fg.audit.diff_proof_frames(
    round_a_id, round_b_id, round_a_events, round_b_events,
)
view = ProofFrameDiffView(diff)

# Frames whose proof status flipped between rounds (still_valid / invalidated / unknown)
for frame in view.frames_with_status_change():
    print(frame.frame_identity.support_digest, frame.frame_status_change)
    for delta in frame.atom_deltas:
        # delta.kind ∈ {"atom_added", "atom_removed", "atom_verdict_changed"}
        print("  ", delta.kind, delta.atom_key)

# Or filter at the atom level across all frames
for delta in view.iter_atom_deltas(kind="atom_verdict_changed"):
    print(delta.atom_key, delta.before_verdict, "→", delta.after_verdict)

# Or look up only frames whose atom verdicts changed
for frame in view.frames_with_atom_verdict_changes():
    ...
```

The view is a frozen wrapper around the DTO; constructing it is cheap
(no copies). Real method surface:
- `frames_with_status_change()` — frames where `frame_status_change is not None`
- `frames_with_atom_verdict_changes()` — frames containing any
  `atom_verdict_changed` delta
- `iter_atom_deltas(*, kind=None)` — iterate atom deltas across all
  frames, optionally filtered by kind

For raw data without indexing, walk `diff.frame_deltas` directly —
each `FrameDelta` carries `frame_identity` (a `FrameIdentity` with
`support_digest` and `binding_items`), `source_a` / `source_b`
(`EventReference | None`), `frame_status_change`, `atom_deltas`, and
`markers`. There is no `added_frames` / `removed_frames` /
`changed_frames` partition — frame add/remove/change semantics are
encoded per-delta via `source_a`/`source_b` presence and
`frame_status_change`.

---

## 2. Round events recorder

The recorder produces the event tuples that
`fg.audit.diff_proof_frames(...)` consumes. Lifecycle:

```python
from kernel.audit.round_events import (
    start_round,
    record_round_event,
    finalize_round,
)

# Start a recording session
recorder = start_round("round-2026-05-09T10:00:00Z")

# During evaluation, hooks call record_round_event with kind+payload
record_round_event(recorder, kind="check_completed", payload={"derivation_id": "drv.x"})
record_round_event(recorder, kind="diagnose_completed", payload={"derivation_id": "drv.x"})

# Persist the round to a directory; returns the bundle Path
bundle_path = finalize_round(recorder, "/var/factpy/rounds/round-2026-05-09T10:00:00Z")

# After finalize, the events are still readable in-memory
events = recorder.events                  # → tuple[RoundEvent, ...]
```

Real signatures:
- `start_round(round_id: str, *, event_ts: int | None = None) -> RoundRecorder`
- `record_round_event(recorder, *, kind: str, payload: Mapping[str, JSONValue], event_ts: int | None = None) -> RoundEvent`
- `finalize_round(recorder, package_dir: str | Path, *, event_ts: int | None = None) -> Path`
- `recorder.events` — frozen tuple property; the recorder still carries
  the events post-finalize for in-process consumers.

The recorder is **stateful** — it accumulates events as your
evaluation progresses. Call `finalize_round` exactly once per round
(double-finalize raises `RoundEventError`).

Why this isn't in the SDK: the recorder is mutable, raises on
double-finalize, is persistence-adjacent (most callers immediately
write the events to disk), and existing UX already imports it directly.
Wrapping it as `fg.audit.recorder()` would add a layer without value.

### Loading recorded rounds

```python
from kernel.audit import load_audit_package

bundle = load_audit_package("/var/factpy/rounds/round-2026-05-09T10:00:00Z")
events = bundle.round_events              # tuple[RoundEvent, ...]
warnings = bundle.round_event_warnings    # tuple[WarningDTO, ...]
manifest = bundle.manifest                # dict from manifest.json
```

`load_audit_package` returns an `AuditPackageData` frozen dataclass
(NOT a dict — subscript access raises). It carries many other
attributes too (`run_ledger`, `candidate_ledger`,
`accept_write_ledger`, `support_artifacts`, `evidence_graphs`, etc.);
read `kernel.audit.reader` for the full field list.

---

## 3. Raw cross-boundary DTOs

The SDK accepts these as input arguments to `fact_overlay.check`,
`rule.literal_replace`, `rule.add_condition`, etc. Construct them
directly:

```python
from kernel.application.protocol import (
    EvaluationOverlay,
    FactValueOverride,         # FactOverlayAction = FactValueOverride | FactRemoveAction
    FactRemoveAction,
    RuleLiteralPath,
    RuleAddedAtom,
    RuleDisableAction,         # RuleOverlayAction = RuleDisableAction | RuleLiteralReplaceAction | RuleAddConditionAction
    RuleLiteralReplaceAction,
    RuleAddConditionAction,
)

# Fact-overlay: replace one fact's value with another
overlay = EvaluationOverlay(
    fact_actions=(
        FactValueOverride(
            asrt_id="asrt-abc-123",
            pred_id="country:official_language",
            e_ref="idref_v1:Country:<digest>",
            old_fact_tuple=("idref_v1:Country:<digest>", "French"),
            new_fact_tuple=("idref_v1:Country:<digest>", "Spanish"),
            note="counterfactual",
        ),
    ),
    rule_actions=(),
)

# RuleLiteralPath: targets a literal slot inside an atom
literal_path = RuleLiteralPath(kind="pred_term", index=2)
# kind ∈ {"pred_term", "in_value", "lhs", "rhs", "const_operand"}
# index is required for "pred_term" / "in_value" only

# RuleAddedAtom: a tuple-encoded atom; the SDK predicate IR shape
added_atom = RuleAddedAtom(atom=("pred", "user:tag", "$u", "vip"))
# atom[0] is the kind tag (e.g. "pred"); the rest are atom-specific terms
```

These are frozen dataclasses; they validate inputs in `__post_init__`
and raise `ProtocolShapeError` on bad shapes. The constructors are
precise about field types — `tuple` not `list`, exact literal sets,
non-empty strings — so read the dataclass at
`kernel/application/protocol/derivation_fact_overlay.py` before
composing one in production code.

`RoundEvent` and related audit DTOs:

```python
from kernel.audit.round_events import RoundEvent
# (Most users obtain RoundEvents from the recorder, not by construction.)
```

---

## 4. Compiled-plan pass-through

`fg.eval.evaluate_compiled(...)` and `fg.eval.accept_compiled(...)`
are thin passthrough wrappers around the lower-level
`Store.evaluate(...)` / `Store.accept(...)` methods. They **skip SDK
DSL lowering** — i.e. they expect Store-level keyword arguments
(`derivation_id`, `version`, `target_pred_id`, `head_vars`, `where`,
`mode`, etc.), not an SDK `Derivation` object.

```python
# Pseudo-shape; consult kernel.core.store.runtime.Store.evaluate for
# the exact keyword set you need to provide.
result = fg.eval.evaluate_compiled(
    derivation_id="drv.copy_name",
    version="1.0.0",
    target_pred_id="user:name",
    head_vars=[...],
    where=[...],
    mode="native",
)
```

This path is **internal escape hatch territory** — it is not part of
the stable SDK contract:
- `_compile_derivation_input(...)` (private, leading underscore) is
  what the SDK uses internally to lower a `Derivation` for the Store.
  Calling it directly bypasses the SDK boundary and may break across
  versions.
- The right tool for almost all callers is the high-level
  `fg.eval.evaluate(deriv, mode=...)` (or `fg.eval.accept(...)`),
  which lowers + caches + delegates in one call.

If you genuinely need to reuse a lowered plan across calls, prefer
constructing a `kernel.application.protocol.CompiledDerivationPlan`
directly (frozen DTO) and feeding it through the application-level
`evaluate_derivation_plans(...)` runner — that path has a stable
public protocol contract; `evaluate_compiled` does not.

---

## 5. Engine adapter registration

The SDK does not auto-import engine adapters. To use Souffle, ProbLog,
or PyReason, import the adapter package — registration happens at
import time:

```python
import kernel.adapters.souffle    # registers "souffle" mode
import kernel.adapters.problog    # registers "problog" mode
import kernel.adapters.pyreason   # registers "pyreason" mode
```

After import, `fg.eval.evaluate(deriv, mode="souffle")` works. Without
the import, the call raises `SDKStoreError` with a "no such mode"
diagnostic.

Each adapter has its own dependency footprint (Souffle binary,
ProbLog Python package, PyReason). The SDK does not declare them as
hard dependencies; install the ones you need.

---

## 6. Frontier (advanced evaluator hook)

The native evaluator's frontier trace is an introspection hook used
by what-if and audit internals. It is not part of the SDK surface
but is reachable via:

```python
from kernel.core.rules.frontier import (
    evaluate_native_where_frontier,
    NativeWhereFrontierEvaluation,
    NativeWhereFrontierRow,
)

result = evaluate_native_where_frontier(...)   # → NativeWhereFrontierEvaluation
for row in result.rows:                         # → tuple[NativeWhereFrontierRow, ...]
    ...
```

Use case: building a custom audit tool that needs to see the
evaluator's working set during a `where`-clause evaluation. Most
users do not need this — the frontier trace is what powers Why-not
internally, and `fg.what_if.why_not(...)` is almost always the
right entry point. Read the module source for argument shape; the
public surface is small but precise.

---

## When to file a feature request

If you find yourself reaching into the same advanced surface
repeatedly, that's signal that the SDK is missing a namespace method.
File an issue; the SDK is open to adding ergonomic wrappers when
there's evidence of repeat use.

The boundary is intentional: not everything that's reachable should
be ergonomically wrapped. Wrappers commit the SDK to a stable contract,
and the kernel team prefers to add them after seeing real-world usage
patterns.
