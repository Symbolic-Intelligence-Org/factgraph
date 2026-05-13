# Read and write facts

The first two pages showed the shape of a graph. This page focuses on what
happens when you write and read data.

A `FactGraph` is not a mutable table. A write appends an assertion to the
ledger. A read asks the graph to resolve the active assertions for an entity
and return a read-only snapshot. That distinction is why the API talks about
references, assertion ids, and snapshots instead of object mutation.

This page covers the everyday read and write path. The next page,
[Assertion records and views](assertions.md), goes deeper into assertion
selection, frozen views, and the professional retract pattern. If you only
need to write a few facts and read them back, this page is enough.

## The write coordinate

Writes need an entity reference. Build it from the entity identity with
`fg.read.ref(...)`.

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
```

The reference is the graph coordinate for "the `User` whose `user_id` is
`u-1`". It is an opaque `idref_v1` token. Treat it as a handle returned by
the SDK, not as a string you parse or construct yourself.

Calling `fg.read.ref(...)` does not write a fact by itself. It only gives
later write calls a managed coordinate.

## Single and multi writes

Use `fg.write.set(...)` for `single` fields and `fg.write.add(...)` for
`multi` fields.

```python
name_id = fg.write.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
tag_engineer = fg.write.add(
    User.tags,
    alice,
    "engineer",
    meta={"source": "profile", "trace_id": "profile-001"},
)
tag_reviewer = fg.write.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)
```

Each call returns an `asrt_id`. The id identifies the exact ledger record
that was written. Keep it whenever you may want to retract or audit that
write later. The next page goes into the full assertion record model; this
page treats `asrt_id` as an opaque handle.

`set` does not delete the earlier `name` assertion if you call it again
later. It appends a newer assertion, and the snapshot's scalar view chooses
the latest active value for the single field.

## Current snapshots

Use `fg.read.get(...)` when you know the full identity.

```python
snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert set(snap.tags) == {"engineer", "reviewer"}
```

The snapshot is read-only. It is the graph's current answer for that entity,
not the ledger itself.

For ordinary application code, `snap.name` and `snap.tags` are usually
enough. When you need to know why the snapshot has that value -- which
assertion supports it, who added it, when -- open the field assertion view
described on [Assertion records and views](assertions.md).

## Finding entities

Use `fg.read.find(...)` when you want all matching snapshots. Filters are
exact matches. For a `multi` field, the filter is a containment check.

```python
bob = fg.read.ref(User, user_id="u-2")
fg.write.set(User.name, bob, "Bob")
fg.write.add(User.tags, bob, "reviewer")

reviewers = fg.read.find(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice", "Bob"}
```

`find(...)` is a read surface, not a rule engine or query language. It is
for snapshot filtering over entity identities and field values. Rules,
inferences, and saved query surfaces are separate topics.

## Retracting an assertion

Retraction is also append-only. It records that a specific assertion should
no longer be authoritative in the current view.

`fg.write.retract(...)` takes an `asrt_id`, not an entity ref:

```python
revoker_id = fg.write.retract(
    tag_reviewer,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)

assert isinstance(revoker_id, str)

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

Here `tag_reviewer` is the `asrt_id` we kept from the original
`fg.write.add(...)` call. That is the simplest retract pattern: save the id
at write time, retract by id later.

When you do not have the id handy and have to find the assertion through a
snapshot, use the selection-based retract pattern on
[Assertion records and views](assertions.md). It walks through
`snap.field(...).where(...).one().asrt_id` and explains why that step exists.

The original assertion is not deleted. It moves out of the active set into
history. The retract itself is a separate ledger record whose id is the
return value.

## Complete example

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
name_id = fg.write.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
tag_engineer = fg.write.add(
    User.tags,
    alice,
    "engineer",
    meta={"source": "profile", "trace_id": "profile-001"},
)
tag_reviewer = fg.write.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)

snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert set(snap.tags) == {"engineer", "reviewer"}

bob = fg.read.ref(User, user_id="u-2")
fg.write.set(User.name, bob, "Bob")
fg.write.add(User.tags, bob, "reviewer")

reviewers = fg.read.find(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice", "Bob"}

fg.write.retract(tag_reviewer, meta={"source": "manual-fix"})

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

## Syntax checklist

- `fg.read.ref(...)` gives writes a managed entity coordinate.
- `fg.write.set(...)` appends a single-field assertion.
- `fg.write.add(...)` appends a multi-field assertion.
- `meta={"source": ..., "trace_id": ...}` attaches audit-friendly metadata.
- Writes return `asrt_id` strings for exact ledger records; keep them for
  later inspection or retract.
- `fg.read.get(...)` returns the current snapshot for a full identity.
- `fg.read.find(...)` returns matching snapshots.
- `fg.write.retract(asrt_id)` records a retraction by id and returns the
  revoker's `asrt_id`.
- The ledger is append-only; snapshots are read-time views over assertions.
- For deeper assertion mechanics, see
  [Assertion records and views](assertions.md).
