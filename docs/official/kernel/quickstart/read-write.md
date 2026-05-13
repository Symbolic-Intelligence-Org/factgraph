# Read and write facts

The first two pages showed the shape of a graph. This page focuses on what
happens when you write and read data.

A `FactGraph` is not a mutable table. A write appends an assertion to the
ledger. A read asks the graph to resolve the active assertions for an entity and
return a read-only snapshot. That distinction is why the API talks about
references, assertion ids, and snapshots instead of object mutation.

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
`u-1`". It is an opaque `idref_v1` token. Treat it as a handle returned by the
SDK, not as a string you parse or construct yourself.

Calling `fg.read.ref(...)` does not write a fact by itself. It only gives later
write calls a managed coordinate.

## Single and multi writes

Use `fg.write.set(...)` for `single` fields and `fg.write.add(...)` for
`multi` fields.

```python
name_v1 = fg.write.set(User.name, alice, "Alice")
name_v2 = fg.write.set(User.name, alice, "Alice Chen")

tag_engineer = fg.write.add(User.tags, alice, "engineer")
tag_reviewer = fg.write.add(User.tags, alice, "reviewer")
```

Each call returns an assertion id. The id identifies the exact ledger record
that was written. It is useful when you need to inspect history or retract that
particular assertion later.

`set` does not delete the earlier `name` assertion. It appends a newer
assertion, and the current read view chooses the latest active value for the
single field.

## Current snapshots

Use `fg.read.get(...)` when you know the full identity.

```python
snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice Chen"
assert set(snap.tags) == {"engineer", "reviewer"}
```

The snapshot is read-only. It is the graph's current answer for that entity,
not the ledger itself.

For ordinary application code, reading `snap.name` and `snap.tags` is usually
enough. When you need to understand why the snapshot has that value, inspect
the assertion records behind a field.

```python
name_history = snap.field("name").history

assert {record.value for record in name_history} == {"Alice", "Alice Chen"}
assert {record.asrt_id for record in name_history} == {name_v1, name_v2}
```

`history` includes active and revoked records. `active` is the current active
set for that field.

## Finding entities

Use `fg.read.find(...)` when you want all matching snapshots. Filters are exact
matches. For a `multi` field, the filter is a containment check.

```python
bob = fg.read.ref(User, user_id="u-2")
fg.write.set(User.name, bob, "Bob")
fg.write.add(User.tags, bob, "reviewer")

reviewers = fg.read.find(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice Chen", "Bob"}
```

`find` is still a read surface, not a rule engine or query language. It is for
snapshot filtering over entity identities and field values. Rules, inferences,
and saved query surfaces are separate topics.

## Retracting an assertion

Retraction is also append-only. It records that a specific assertion should no
longer be authoritative in the current view.

```python
retraction_id = fg.write.retract(tag_reviewer)

assert isinstance(retraction_id, str)

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

Notice the input: `fg.write.retract(...)` takes an assertion id, not an entity
reference. To retract the "reviewer" tag, pass the id returned by the earlier
`fg.write.add(...)` call.

The original assertion remains in history:

```python
tag_history = after.field("tags").history

assert tag_reviewer in {record.asrt_id for record in tag_history}
assert tag_reviewer not in {record.asrt_id for record in after.field("tags").active}
```

## Complete example

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")

name_v1 = fg.write.set(User.name, alice, "Alice")
name_v2 = fg.write.set(User.name, alice, "Alice Chen")
fg.write.add(User.tags, alice, "engineer")
tag_reviewer = fg.write.add(User.tags, alice, "reviewer")

snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice Chen"
assert set(snap.tags) == {"engineer", "reviewer"}
assert {record.value for record in snap.field("name").history} == {
    "Alice",
    "Alice Chen",
}
assert {record.asrt_id for record in snap.field("name").history} == {
    name_v1,
    name_v2,
}

bob = fg.read.ref(User, user_id="u-2")
fg.write.set(User.name, bob, "Bob")
fg.write.add(User.tags, bob, "reviewer")

reviewers = fg.read.find(User, tags="reviewer")
assert {row.name for row in reviewers} == {"Alice Chen", "Bob"}

fg.write.retract(tag_reviewer)

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
assert tag_reviewer in {record.asrt_id for record in after.field("tags").history}
assert tag_reviewer not in {record.asrt_id for record in after.field("tags").active}
```

## What to remember

- `fg.read.ref(...)` gives writes a managed entity coordinate.
- `fg.write.set(...)` appends a single-field assertion.
- `fg.write.add(...)` appends a multi-field assertion.
- Writes return assertion ids.
- `fg.read.get(...)` returns the current snapshot for a full identity.
- `fg.read.find(...)` returns matching snapshots.
- `fg.write.retract(...)` takes an assertion id and records a retraction.
- The ledger is append-only; snapshots are read-time views over assertions.
