# Application Walker Module

`kernel.application.walker` is a Tier 2 advanced-importable traversal
surface over application/core DTOs. It is not an SDK facade and does not
create an outward compatibility promise.

Current implementation status:

- **B Phase 0:** `WalkerError(Exception)` hierarchy is implemented and
  exported from `kernel.application.walker`.
- **B Phase 1:** `IRBodyWalker` and `IRAtomView` are implemented for
  `RuleSpec.where` / `CompiledDerivationPlan.body_ir` style IR bodies.
- **B Phase 2:** `FrozenTupleView` and `frozen_collection(...)` are
  implemented for already-frozen tuple collections.
- **B Phase 3:** `AtomKeyView`, `parse_atom_key(...)`,
  `SupportArtifactView`, and `AssertionView` are implemented for
  `SupportArtifact` / ledger-claim cross-referencing.
- **B Phase 4+ not implemented yet:** `ProofFrameView` and
  `ProofFrameDiffView` remain blueprint-scoped future phases.
- **B3 not implemented:** audit/store stream walkers remain future-only.

## IRBodyWalker

`IRBodyWalker(source, source_id=None)` accepts a flat AND body or an
OR-of-AND body represented as `list` / `tuple` IR:

```python
from kernel.application.walker import IRBodyWalker

walker = IRBodyWalker([
    ("pred", "Person:age", ["$p", "$age"]),
    ("eq", "$age", 40),
])

for atom in walker:
    print(atom.key, atom.kind, atom.args)
```

The walker snapshots the source at construction time, recursively freezing
mutable list/tuple/dict containers into immutable tuples. Mutating the
original source after construction does not change traversal results.

Each yielded `IRAtomView` exposes:

- `kind`
- `pred_id` (`str | None`; set only for `pred` atoms)
- `args`
- `branch_index`
- `atom_index`
- `key`
- `underlying`

`underlying` is the frozen snapshot atom, not the original mutable object.
It is an escape hatch for inspection and is excluded from equality / hash.
There are no `.source`, `.carrier`, or `.raw` aliases.

## Lookup

`find(...)` returns `IRAtomView | None`:

```python
atom = walker.find(kind="pred", pred_id="Person:age")
missing = walker.find(key="b0.a9:eq")  # None
```

Exact accessors raise `WalkerLookupError` on miss:

```python
atom = walker.require_key("b0.a0:Person:age")
atom = walker.require_position(branch_index=0, atom_index=1)
```

## FrozenTupleView

`FrozenTupleView` wraps an existing tuple without modifying the tuple or its
items:

```python
from kernel.application.walker import frozen_collection

rows = frozen_collection(result.atom_verdicts)
invalidated = rows.filter(verdict="invalidated")
first = invalidated.first()  # item | None
```

`filter(...)` eagerly returns a new `FrozenTupleView`; stream semantics remain
reserved for future B3. It accepts an optional predicate plus attribute
equality filters:

```python
view.filter(lambda row: row.kind == "pred", status="active")
```

`find(predicate)` returns the first matching item or `None`.
`first()` returns the first item or `None` on empty.
`require_position(index)` raises `WalkerLookupError` on miss.
`require_key(value, key=...)` raises `WalkerLookupError` on miss; without a
custom extractor it checks common key-like attributes: `key`, `pred_atom_key`,
`step_key`, `atom_key`, `asrt_id`, and `id`.

## Atom Keys

`parse_atom_key(key)` parses canonical `b{branch}.a{atom}:{payload}` strings:

```python
from kernel.application.walker import parse_atom_key

atom_key = parse_atom_key("b0.a1:Person:age")
assert atom_key.branch_index == 0
assert atom_key.atom_index == 1
assert atom_key.payload == "Person:age"
```

The parser is syntactic. It returns an `AtomKeyView` with `kind="unknown"`.
Context-specific callers can promote the same parsed key without mutation:

```python
pred_key = atom_key.as_pred()
step_key = parse_atom_key("b0.a2:eq").as_step()
```

Malformed input raises `WalkerParseError`.

## SupportArtifactView and AssertionView

`SupportArtifactView` wraps a frozen `SupportArtifact` plus caller-provided
frozen assertion indexes:

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

`SupportArtifactView` performs no live store reads. Missing assertion ids raise
`WalkerReferenceError`.

`AssertionView` can also be constructed directly from an assertion id and
frozen claim / metadata indexes. Its surfaced fields are:

- `asrt_id`
- `pred_id`
- `e_ref`
- `rest_terms` as a snapshot tuple
- `meta_rows` as a snapshot tuple
- `underlying`, the original `Claim` escape hatch

`Claim.rest_terms` is a mutable list in the underlying DTO. `AssertionView`
snapshots it for surfaced reads, but callers who access
`assertion.underlying.rest_terms` are using the escape hatch and accept the
underlying object's mutability.

## Errors

The module currently exports:

- `FrozenTupleView`
- `AssertionView`
- `AtomKeyView`
- `IRAtomView`
- `IRBodyWalker`
- `SupportArtifactView`
- `WalkerError`
- `WalkerLookupError`
- `WalkerParseError`
- `WalkerReferenceError`
- `WalkerSnapshotError`
- `WalkerFrozenError`
- `UnboundedStreamError`
- `frozen_collection`
- `parse_atom_key`

`UnboundedStreamError` is a dormant placeholder for future B3 StreamWalker
work. B1/B2 code has no raise site for it.
