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
- **B Phase 3+ not implemented yet:** `SupportArtifactView`,
  `ProofFrameView`, `ProofFrameDiffView`, `parse_atom_key`, and
  `AssertionView` remain blueprint-scoped future phases.
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

## Errors

The module currently exports:

- `FrozenTupleView`
- `IRAtomView`
- `IRBodyWalker`
- `WalkerError`
- `WalkerLookupError`
- `WalkerParseError`
- `WalkerReferenceError`
- `WalkerSnapshotError`
- `WalkerFrozenError`
- `UnboundedStreamError`
- `frozen_collection`

`UnboundedStreamError` is a dormant placeholder for future B3 StreamWalker
work. B1/B2 code has no raise site for it.
