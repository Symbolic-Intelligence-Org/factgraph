# FactGraph, ledger, and snapshots

A `FactGraph` is not a mutable object table. It is a schema-bound facade over
an append-only ledger of assertions.

That one sentence matters because most user-facing API choices follow from it:
writes append assertion records, reads assemble current snapshots from those
records, and retractions point at a specific assertion id.

```text
entity coordinate
  -> field assertion
    -> assertion id
      -> value + metadata + revocation state
```

The entity coordinate comes from the schema. The assertion id comes from a
write. A snapshot is the read-side view that resolves the active assertions for
one coordinate.

## Start with a coordinate

The schema gives the graph a vocabulary and a coordinate model. Once the graph
knows that model, `fg.read.ref(...)` builds an opaque entity reference. Treat
that ref as a handle, not a string format to parse.

```python
from kernel.sdk import Entity, FactGraph, Field, Identity, ReadPolicy


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
alice = fg.read.ref(User, user_id="u-1")
```

`alice` is the write target for facts about the coordinate
`User(user_id="u-1")`.

## Writes append assertions

`set(...)` and `add(...)` both append assertions and return assertion ids.
`set(...)` is for single-cardinality fields; `add(...)` is for
multi-cardinality fields.

```python
name_v1 = fg.write.set(User.name, alice, "Alice", meta={"source": "import"})
name_v2 = fg.write.set(User.name, alice, "Alice Chen", meta={"source": "hr"})

tag_engineer = fg.write.add(User.tags, alice, "engineer")
tag_reviewer = fg.write.add(User.tags, alice, "reviewer")

snap = fg.read.get(User, user_id="u-1")

assert snap.name == "Alice Chen"
assert set(snap.tags) == {"engineer", "reviewer"}

name_history = snap.field("name").history
assert {record.value for record in name_history} == {"Alice", "Alice Chen"}
assert {record.asrt_id for record in name_history} == {name_v1, name_v2}
```

The second `set(...)` does not erase the first assertion. It changes what the
current snapshot shows for the single field, while the earlier assertion remains
available in history.

This is the first important FactGraph habit: when you need auditability, keep
the assertion id.

## Snapshots are read models

`fg.read.get(...)` returns one `EntitySnapshot` for a complete coordinate. The
direct attributes are convenient current values:

```python
assert snap.name == "Alice Chen"
assert tuple(snap.tags) == ("engineer", "reviewer")
```

The assertion collections give you the underlying records:

```python
active_tags = snap.field("tags").active
tag_values = {record.value for record in active_tags}

assert tag_values == {"engineer", "reviewer"}
assert active_tags.where(value="engineer").one().asrt_id == tag_engineer
```

Use direct attributes when you want the current value. Use
`snapshot.field(...).active` or `.history` when you need assertion ids,
metadata, or historical records.

## Retraction is also append-only

Retraction targets an assertion id. It does not take an entity ref, a field
descriptor, or a value.

```python
revoker = fg.write.retract(tag_reviewer)
assert isinstance(revoker, str)

after_retract = fg.read.get(User, user_id="u-1")

assert tuple(after_retract.tags) == ("engineer",)
assert tag_reviewer not in {
    record.asrt_id for record in after_retract.field("tags").active
}
assert tag_reviewer in {
    record.asrt_id for record in after_retract.field("tags").history
}
```

The original assertion is still in history. The current snapshot ignores it
because it has an active retraction.

This is different from deleting a row in a table. It preserves the fact that
someone asserted `"reviewer"` and later revoked that assertion.

## Views name assertion sets

`fg.views` is for named frozen assertion-id selections. A view records
membership: these assertion ids belong to this named set.

```python
review_view = fg.views.create(
    "review_set",
    asrt_ids=[name_v1, tag_engineer],
)

assert review_view.asrt_ids == frozenset({name_v1, tag_engineer})
assert fg.views.get("review_set").asrt_ids == review_view.asrt_ids
assert "review_set" in fg.views.list()

records = fg.assertions.by_ids(review_view.asrt_ids)
assert {record.asrt_id for record in records} == {name_v1, tag_engineer}
```

A frozen assertion view is not a read policy and it is not dynamic. Future
writes do not enter the view automatically. If you want a different assertion
set, create or update a view with the assertion ids you want.

## ReadPolicy is a call-site policy

`ReadPolicy` controls read-time display and confidence aggregation for calls
that accept `policy=...`. It is not stored in `fg.views`, and it does not
change the ledger.

```python
policy = ReadPolicy(respect_revocations=True, confidence_strategy="max")
rows = fg.read.find(User, tags="engineer", policy=policy)

assert {row.name for row in rows} == {"Alice Chen"}
```

Use a policy when a read needs a particular display rule. Use a frozen view when
you need to name a specific set of assertion ids.

## What to remember

- A `FactGraph` is an append-only assertion ledger with a schema-bound facade.
- Entity refs identify coordinates; assertion ids identify individual writes.
- `fg.write.set(...)` and `fg.write.add(...)` append assertions and return ids.
- A single field's direct snapshot value is a read-side projection, not proof
  that older assertions disappeared.
- `fg.write.retract(...)` takes an assertion id and appends a revocation.
- `fg.views` stores frozen assertion-id membership, not read policies.
- `ReadPolicy` is a call-site option for reads, not a saved view.
