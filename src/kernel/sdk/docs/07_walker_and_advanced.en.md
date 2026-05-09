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
  derivations or overlays from string templates, the raw application
  protocol DTOs (`EvaluationOverlay`, `RuleLiteralPath`,
  `RuleAddedAtom`) are usually easier to construct than going through
  the typed SDK builders.
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

diff = fg.audit.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)
view = ProofFrameDiffView(diff)

for changed in view.changed_frames():
    print(changed.frame_identity, changed.head_predicate)
    for delta in changed.atom_deltas:
        print("  ", delta.kind, delta.atom_locator)
```

The view is a frozen wrapper around the DTO; constructing it is cheap
(no copies). Methods provide indexed access by predicate, by status
change, and by frame identity.

The SDK does not auto-wrap because not every caller wants the indexing
cost. If you only need a flat list, use `diff.added_frames`,
`diff.removed_frames`, `diff.changed_frames` directly.

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
recorder = start_round(round_id="round-2026-05-09T10:00:00Z")

# During evaluation, hooks call into record_round_event
record_round_event(recorder, event=...)
record_round_event(recorder, event=...)

# Persist the round
events = finalize_round(recorder)         # → tuple[RoundEvent, ...]
```

The recorder is **stateful** — it accumulates events as your
evaluation progresses. Call `finalize_round` exactly once per round.

Why this isn't in the SDK: the recorder is mutable, raises on
double-finalize, is persistence-adjacent (most callers immediately
write the events to disk), and existing UX already imports it directly.
Wrapping it as `fg.audit.recorder()` would add a layer without value.

### Loading recorded rounds

```python
from kernel.audit import load_audit_package

bundle = load_audit_package("/path/to/round_a/")
events = bundle["events"]                    # tuple[RoundEvent, ...]
metadata = bundle["metadata"]
```

Use `load_audit_package` to read events back from disk.

---

## 3. Raw cross-boundary DTOs

The SDK accepts these as input arguments to `fact_overlay.check`,
`rule.literal_replace`, `rule.add_condition`, etc. Construct them
directly:

```python
from kernel.application.protocol import (
    EvaluationOverlay,
    FactOverlayAction,
    RuleLiteralPath,
    RuleAddedAtom,
    RuleOverlayAction,
)

overlay = EvaluationOverlay(
    fact_actions=(
        FactOverlayAction(
            entity="Country",
            identity={"code": "FR"},
            field="official_language",
            value="Spanish",
        ),
    ),
)

literal_path = RuleLiteralPath(field="official_language")

added_atom = RuleAddedAtom(
    predicate="Person",
    positional=(person_var,),
    keyword={"name": "Alice"},
)
```

These are frozen dataclasses; they validate inputs in `__post_init__`
and raise `ProtocolShapeError` on bad shapes.

`RoundEvent` and related audit DTOs:

```python
from kernel.audit.round_events import RoundEvent
# (Most users obtain RoundEvents from the recorder, not by construction)
```

---

## 4. Compiled-plan pass-through

The SDK accepts a high-level `Derivation` and lowers it for you. If
you've already lowered (e.g. cached compiled plans across requests),
use the `_compiled` variants:

```python
from kernel.sdk import compile_schema_from_classes

# Cache the compiled plans somewhere
compiled = fg._compile_derivation_input(my_derivation)

# Reuse without re-lowering
result = fg.eval.evaluate_compiled(compiled, mode="native")
accepted = fg.eval.accept_compiled(compiled, ...)
```

`evaluate_compiled` and `accept_compiled` are passthrough wrappers
around the application's compiled-plan execution path. They skip SDK
lowering but otherwise behave identically.

These are advanced — most callers should use `evaluate(...)` and
`accept(...)` and trust the compile cache.

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

## 6. Optional-domain bundles

Some domain packages (e.g. ECSS compliance) ship as optional extras.
Use `ensure_domain` to import them with a single point of failure:

```python
from kernel.sdk import ensure_domain

ecss = ensure_domain("ecss")     # raises SDKStoreError if not installed

ecss.compliance.evaluate_baseline(...)
```

Rather than scattering `try: import kernel.domains.ecss except
ImportError: ...` across your codebase, `ensure_domain` gives a single,
informative error message ("install factpy-kernel[ecss]") and a single
audit point for which domains your application uses.

---

## 7. Frontier (advanced evaluator hook)

The native evaluator's frontier trace is an introspection hook used
by what-if and audit internals. It is not currently part of the SDK
surface but is reachable via:

```python
from kernel.core.rules.frontier import collect_frontier_trace
```

Use case: building a custom audit tool that needs to see the
evaluator's working set. Most users do not need this.

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
