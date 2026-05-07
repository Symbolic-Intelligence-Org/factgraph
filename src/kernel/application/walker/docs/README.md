# Application Walker Module

`kernel.application.walker` is a Tier 2 advanced-importable traversal
surface over application/core DTOs. It is not an SDK facade and does not
create an outward compatibility promise.

Current implementation status:

- **B Phase 0:** `WalkerError(Exception)` hierarchy is implemented and
  exported from `kernel.application.walker`.
- **B Phase 1:** `IRBodyWalker` and `IRAtomView` are implemented for
  `RuleSpec.where` / `CompiledDerivationPlan.body_ir` style IR bodies.
- **B Phase 2+ not implemented yet:** `FrozenTupleView`,
  `SupportArtifactView`, `ProofFrameView`, `ProofFrameDiffView`,
  `parse_atom_key`, and `AssertionView` remain blueprint-scoped future
  phases.
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

## Errors

The module currently exports:

- `WalkerError`
- `WalkerLookupError`
- `WalkerParseError`
- `WalkerReferenceError`
- `WalkerSnapshotError`
- `WalkerFrozenError`
- `UnboundedStreamError`

`UnboundedStreamError` is a dormant placeholder for future B3 StreamWalker
work. B1/B2 code has no raise site for it.
