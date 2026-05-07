# Application Walker Module

## Scope

`kernel.application.walker` is a Tier 2 advanced-importable traversal surface
over application/core DTOs. It is not an SDK facade and does not create an
outward compatibility promise.

Current implementation status:

- **Implementation Phase 0:** `WalkerError(Exception)` hierarchy is implemented
  and exported from `kernel.application.walker`.
- **Implementation Phase 1:** `IRBodyWalker` and `IRAtomView` are implemented
  for `RuleSpec.where` / `CompiledDerivationPlan.body_ir` style IR bodies.
- **Implementation Phase 2:** `FrozenTupleView` and `frozen_collection(...)`
  are implemented for already-frozen tuple collections.
- **Implementation Phase 3:** `AtomKeyView`, `parse_atom_key(...)`,
  `SupportArtifactView`, and `AssertionView` are implemented for
  `SupportArtifact` / ledger-claim cross-referencing.
- **Implementation Phase 4+ not implemented yet:** `ProofFrameView` and
  `ProofFrameDiffView` remain blueprint-scoped future phases.
- **Scope item B3 audit/store stream walker not implemented:** stream walkers
  remain future-only.

## Responsibilities

`IRBodyWalker(source, source_id=None)` accepts a flat AND body or an OR-of-AND
body represented as `list` / `tuple` IR:

```python
from kernel.application.walker import IRBodyWalker

walker = IRBodyWalker([
    ("pred", "Person:age", ["$p", "$age"]),
    ("eq", "$age", 40),
])
```

The walker snapshots the source at construction time, recursively freezing
mutable list/tuple/dict/set containers into immutable tuples. Mutating the
original source after construction does not change traversal results. Atom view
objects are created lazily during traversal or lookup; construction stores the
frozen source snapshot, not a prebuilt view list.

`FrozenTupleView` wraps an existing tuple without modifying the tuple or its
items. `.filter(predicate=None, **attrs)` and `.find(predicate=None, **attrs)`
support predicate filtering plus exact attribute equality:

```python
from kernel.application.walker import frozen_collection

rows = frozen_collection(result.atom_verdicts)
invalidated = rows.filter(verdict="invalidated")
first = invalidated.first()  # item | None
```

`parse_atom_key(key)` parses canonical `b{branch}.a{atom}:{payload}` strings.
The parser is syntactic and returns `AtomKeyView(kind="unknown")`; contextual
callers promote with `.as_pred()` or `.as_step()`.

`SupportArtifactView` wraps a frozen `SupportArtifact` plus caller-provided
claim / metadata indexes:

```python
from kernel.application.walker import SupportArtifactView

view = SupportArtifactView(
    support,
    frozen_claim_index={"a1": claim},
    frozen_meta_index={"a1": (meta_row,)},
)

pred = view.pred_witnesses.first()
assertion = view.lookup_assertion("a1")
```

The view exposes:

- `pred_witnesses` as `FrozenTupleView[PredWitness]`
- `non_fact_steps` as `FrozenTupleView[NonFactStep]`
- `parse_pred_atom_key(...)` / `parse_step_key(...)`
- `lookup_assertion(asrt_id) -> AssertionView`
- `underlying`, the original `SupportArtifact` escape hatch

`AssertionView` exposes `asrt_id`, `pred_id`, `e_ref`, `rest_terms`,
`meta_rows`, and `underlying`. `rest_terms` and `meta_rows[*].value` are
recursively frozen for surfaced reads and hashing.

## Non-responsibilities

- No SDK shell or `kernel.sdk` import.
- No live `Store` / `Ledger` lookup during walker traversal or assertion lookup.
- No DTO mutation and no method attachment to tuple fields.
- No B3 stream walker, audit package walker, or bounded-stream machinery.
- No `.source`, `.carrier`, or `.raw` alias; `.underlying` is the only escape
  hatch.

## Limitations & Compatibility

`underlying` is an escape hatch and not a stable walker API. For
`AssertionView`, surfaced fields are frozen snapshots, but
`assertion.underlying` is the original `Claim`; callers who mutate
`underlying.rest_terms` accept the DTO escape-hatch risk.

`find(...)` returns `View | None`. Exact accessors such as `require_key(...)`,
`require_position(...)`, and `lookup_assertion(...)` raise walker-layer errors
on miss or reference inconsistency.

`UnboundedStreamError` is exported as a dormant placeholder for the future B3
stream walker contract. B1/B2 code has no raise site for it.

`FrozenTupleView` is a shallow content wrapper. Equality and hash are defined
over the underlying tuple content; `hash(view)` is only valid when the wrapped
tuple and its items are hashable. This is a deliberate content-wrapper carve-out
from surfaced DTO views such as `IRAtomView` / `AssertionView`, where
`.underlying` is excluded from equality and hash.

## Test Entry Points

Focused walker tests:

- `test_walker_errors.py`
- `test_walker_ir.py`
- `test_walker_views_frozen_tuple.py`
- `test_walker_keys.py`
- `test_walker_views_support.py`

Run:

```bash
PYTHONPATH=src python -m unittest \
  src.kernel.tests.test_walker_keys \
  src.kernel.tests.test_walker_views_support \
  src.kernel.tests.test_walker_views_frozen_tuple \
  src.kernel.tests.test_walker_ir \
  src.kernel.tests.test_walker_errors -v
```

## Related Historical Blueprints

- `docs/blueprints/active/2026-05-07_walker-mechanism.md`
- `docs/blueprints/active/2026-05-07_walker-mechanism.audit.md`
- `docs/references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md`
