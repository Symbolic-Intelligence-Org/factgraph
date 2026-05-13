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
name_v1 = fg.write.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
name_v2 = fg.write.set(
    User.name,
    alice,
    "Alice Chen",
    meta={"source": "correction", "trace_id": "fix-001"},
)

tag_engineer = fg.write.add(
    User.tags,
    alice,
    "engineer",
    meta={
        "source": "profile",
        "trace_id": "seed-003",
        "version": "tag-v1",
        "valid_from": "2026-01-01T00:00:00Z",
    },
)
tag_reviewer = fg.write.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)
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

seed_name = name_history.where(source="import", trace_id="seed-001").one()
assert seed_name.asrt_id == name_v1
```

`history` includes active and revoked records. `active` is the current active
set for that field.

## Snapshot assertion paths

An `EntitySnapshot` has two layers:

```text
snap.name                 -> current scalar or tuple value
snap.field("name")        -> assertion records for that field
snap.assertions.name      -> same assertion records, static attribute form
```

Use the scalar field view for ordinary reads. Use assertion records when you
need provenance, history, selection before retraction, or review workflows.

```python
name_assertions = snap.field("name")
same_name_assertions = snap.assertions.name

assert name_assertions.history.where(value="Alice").one().asrt_id == name_v1
assert same_name_assertions.history.where(value="Alice Chen").one().asrt_id == name_v2
```

`snap.field("name")` is convenient when the field name is dynamic.
`snap.assertions.name` is convenient when the field is known in code. Both
return a field assertion view with the same shape:

```text
FieldAssertions
  .active   -> AssertionRecordSet
  .history  -> AssertionRecordSet
  .at(t)    -> active assertions valid at business time t
  .version(v) -> active assertions with raw metadata version v
```

`AssertionRecordSet` behaves like a tuple and adds selection helpers:

```python
tag_records = snap.field("tags").active

assert len(tag_records) == 2
assert tag_records.where(value="engineer").one().asrt_id == tag_engineer
assert tag_records.version("tag-v1").one().asrt_id == tag_engineer
assert (
    tag_records.at("2026-02-01T00:00:00Z")
    .where(value="engineer")
    .one()
    .asrt_id
    == tag_engineer
)
assert tag_records.where(value="missing").first() is None
assert tag_records.where(value="missing").all() == ()
```

`.where(...)` can filter by `value`, `source`, `trace_id`, `version`, or
arbitrary raw metadata with `meta={...}`. Multiple filters are ANDed together.

`.one()` is for destructive or review steps that need exactly one assertion.
It raises if the set has zero or multiple records. `.first()` is for browsing.
`.all()` returns a plain tuple.

`.at(t)` is a business-valid-time filter over `valid_from` / `valid_to`
metadata. It is not a filter over ingestion time.

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
target = snap.field("tags").active.where(value="reviewer").one()
retraction_id = fg.write.retract(target.asrt_id)

assert isinstance(retraction_id, str)

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

Notice the input: `fg.write.retract(...)` takes an assertion id, not an entity
reference. Use `where(...).one()` when you need to select the exact active
assertion before retracting it.

The original assertion remains in history:

```python
tag_history = after.field("tags").history

assert tag_reviewer in {record.asrt_id for record in tag_history}
assert tag_reviewer not in {record.asrt_id for record in after.field("tags").active}
```

## Frozen assertion views

`fg.views` stores named frozen selections of assertion ids. A frozen view is not
a read policy and it is not a dynamic query. It is a named list of exact ledger
records.

```python
review_view = fg.views.create("review_set", asrt_ids=[name_v1, tag_engineer])

assert set(fg.views.get("review_set").asrt_ids) == {name_v1, tag_engineer}
assert "review_set" in fg.views.list()

records = fg.assertions.by_ids(review_view.asrt_ids)

assert {record.asrt_id for record in records} == {name_v1, tag_engineer}
```

Use `fg.assertions.by_id(...)` or `fg.assertions.by_ids(...)` to read the
records captured by a view. Frozen views are id-set containers, not read-policy
objects.

## Evidence starts with assertion anchors

The lowest-level evidence object users meet in the kernel is an assertion
record. It answers: which exact ledger row supports this current snapshot
value?

```python
name_record = fg.assertions.by_id(name_v1)

assert name_record is not None
assert name_record.value == "Alice"
assert name_record.meta.source == "import"
assert name_record.meta.trace_id == "seed-001"
```

This is intentionally smaller than a full proof tree. It gives you the durable
anchor for a fact: assertion id, value, active/revoked status, and metadata.
Higher-level explanation APIs can build from those anchors.

For direct fact-level inspection, `fg.audit.explain_fact(...)` and
`fg.audit.conflicts(...)` operate on a predicate id plus an entity reference:

```python
explanation = fg.audit.explain_fact("user:name", alice)
conflicting = fg.audit.conflicts("user:name", alice)

assert explanation["pred_id"] == "user:name"
assert conflicting["pred_id"] == "user:name"
```

Think of this as the quickstart evidence boundary:

```text
assertion id -> assertion record -> fact explanation / conflict inspection
```

Engine proof traces and cross-engine `EvidenceGraph` objects exist in the audit
layer, but they are advanced explainability surfaces. You do not need them to
understand ordinary write/read/assertion workflows.

## Complete example

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")

name_v1 = fg.write.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
name_v2 = fg.write.set(
    User.name,
    alice,
    "Alice Chen",
    meta={"source": "correction", "trace_id": "fix-001"},
)
tag_engineer = fg.write.add(
    User.tags,
    alice,
    "engineer",
    meta={
        "source": "profile",
        "trace_id": "seed-003",
        "version": "tag-v1",
        "valid_from": "2026-01-01T00:00:00Z",
    },
)
tag_reviewer = fg.write.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)

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
assert (
    snap.field("name")
    .history.where(source="import", trace_id="seed-001")
    .one()
    .asrt_id
    == name_v1
)

assert snap.assertions.name.history.where(value="Alice Chen").one().asrt_id == name_v2

tag_records = snap.field("tags").active
assert tag_records.where(value="engineer").one().asrt_id == tag_engineer
assert tag_records.version("tag-v1").one().asrt_id == tag_engineer
assert (
    tag_records.at("2026-02-01T00:00:00Z")
    .where(value="engineer")
    .one()
    .asrt_id
    == tag_engineer
)
assert tag_records.where(value="missing").first() is None
assert tag_records.where(value="missing").all() == ()

bob = fg.read.ref(User, user_id="u-2")
fg.write.set(User.name, bob, "Bob")
fg.write.add(User.tags, bob, "reviewer")

reviewers = fg.read.find(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice Chen", "Bob"}

target = snap.field("tags").active.where(value="reviewer").one()
fg.write.retract(target.asrt_id)

after = fg.read.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
assert tag_reviewer in {record.asrt_id for record in after.field("tags").history}
assert tag_reviewer not in {record.asrt_id for record in after.field("tags").active}

view = fg.views.create("review_set", asrt_ids=[name_v1, tag_engineer])
records = fg.assertions.by_ids(view.asrt_ids)

assert {record.asrt_id for record in records} == {name_v1, tag_engineer}

name_record = fg.assertions.by_id(name_v1)
assert name_record is not None
assert name_record.meta.source == "import"
assert name_record.meta.trace_id == "seed-001"

explanation = fg.audit.explain_fact("user:name", alice)
conflicting = fg.audit.conflicts("user:name", alice)

assert explanation["pred_id"] == "user:name"
assert conflicting["pred_id"] == "user:name"
```

## Syntax checklist

- `fg.read.ref(...)` gives writes a managed entity coordinate.
- `fg.write.set(...)` appends a single-field assertion.
- `fg.write.add(...)` appends a multi-field assertion.
- `meta={"source": ..., "trace_id": ...}` attaches audit-friendly metadata.
- Writes return assertion ids for exact ledger records.
- `fg.read.get(...)` returns the current snapshot for a full identity.
- `fg.read.find(...)` returns matching snapshots.
- `snap.name` and `snap.tags` are current snapshot values.
- `snap.field("name")` dynamically opens the assertion records for one field.
- `snap.assertions.name` opens the same field records through static attribute
  syntax.
- `snap.field(name).active` shows active assertion records for one field.
- `snap.field(name).history` shows active and revoked assertion records.
- `FieldAssertions.at(t)` and `.version(v)` are shortcuts over active
  assertion records.
- `AssertionRecordSet.where(...)`, `.at(t)`, `.version(v)`, and
  `.by_id(asrt_id)` filter record sets.
- `AssertionRecordSet.one()` selects exactly one assertion; `.first()` previews;
  `.all()` returns a tuple.
- `fg.write.retract(...)` takes an assertion id and records a retraction.
- `fg.views.create/get/list/update/delete` stores frozen assertion-id sets.
- `fg.assertions.by_id(...)` and `fg.assertions.by_ids(...)` read exact
  assertion records.
- `fg.assertions` is by-id readback only; it is not a graph-wide assertion
  query namespace.
- `fg.audit.explain_fact(pred_id, e_ref, *value_atoms)` inspects active claims
  supporting a fact coordinate.
- `fg.audit.conflicts(pred_id, e_ref)` inspects active conflicts for that fact
  coordinate.
- Evidence starts from assertion ids and metadata; full engine evidence graphs
  are an advanced audit-layer surface.
- The ledger is append-only; snapshots are read-time views over assertions.
