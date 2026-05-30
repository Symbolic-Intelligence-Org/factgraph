# Assertion records and views

Read and write worked at the snapshot level. This page goes one layer deeper:
every field fact is an assertion with a durable `asrt_id`, value, metadata, and
active/revoked state.

The read-side type is `AssertionView`. It is pure read-only:

- `snap.assertions` is entity-scoped;
- `snap.field("name")` is field-scoped;
- `snap.assertions.field("name")` is the same field-scoped view;
- `fg.assertions.*` is the graph-level assertion namespace.

The mutation entry point is separate: `fg.assertions.retract(asrt_id)`.

## Writes return assertion ids

`fg.fields.set(...)` and `fg.fields.add(...)` return the `asrt_id` of the
assertion they append.

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")

name_seed = fg.fields.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001", "version": "name-v1"},
)
name_hr = fg.fields.set(
    User.name,
    alice,
    "Alice Liddell",
    meta={"source": "hr", "trace_id": "hr-2026-05", "version": "name-v2"},
)
engineer = fg.fields.add(
    User.tags,
    alice,
    "engineer",
    meta={
        "source": "profile",
        "trace_id": "profile-001",
        "valid_from": "2026-01-01T00:00:00Z",
        "version": "tag-v1",
    },
)
reviewer = fg.fields.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "import-002"},
)
```

Calling `set(...)` twice does not overwrite the first assertion. The snapshot
scalar view chooses the latest active value, while assertion views keep both
records in history.

```python
snap = fg.entities.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice Liddell"
assert set(snap.tags) == {"engineer", "reviewer"}
```

## AssertionRecord shape

An `AssertionRecord` carries:

```text
record.asrt_id     -> str, durable assertion id
record.value       -> raw value
record.value_tag   -> value storage tag
record.is_active   -> bool
record.entity_type -> SDK entity type name
record.field_name  -> SDK field name
record.pred_id     -> kernel predicate id
record.e_ref       -> encoded entity ref
record.meta        -> AssertionMeta
```

`AssertionMeta` exposes first-class slots such as `source`, `trace_id`,
`ingested_at`, `approved_by`, and `note`. The original metadata dictionary is
available as `record.meta.raw`.

## Field and entity assertion views

Open field-scoped views through either spelling:

```python
name_view = snap.field("name")
same_name_view = snap.assertions.field(User.name)

assert name_view is same_name_view
```

Use `.active` for non-revoked records and `.all` for active plus revoked
records. `.history` is a deprecated alias of `.all`; it does not warn by
default and only emits a `DeprecationWarning` when
`FACTGRAPH_WARN_DEPRECATED=1`.

```python
assert {r.value for r in name_view.all} == {"Alice", "Alice Liddell"}
assert {r.value for r in name_view.active} == {"Alice", "Alice Liddell"}
```

Entity-scoped views aggregate all field-scoped records:

```python
assert {r.field_name for r in snap.assertions.active} == {"name", "tags"}
```

## Canonical filtering

`AssertionRecordSet.where(...)` and `AssertionView.where(...)` use the canonical
filter shape:

```text
where(value=..., value_tag=..., _meta={...})
```

Metadata filters go under `_meta`; flat `source=`, `trace_id=`, `version=`,
and `meta=` kwargs are not part of the current API.

```python
target = (
    snap.field("name")
    .all
    .where(value="Alice", _meta={"source": "seed", "version": "name-v1"})
    .one()
)

assert target.asrt_id == name_seed
assert target.meta.source == "seed"
assert target.meta.raw["version"] == "name-v1"
```

Use `_meta={"version": ...}` for version labels:

```python
tag_v1 = snap.field("tags").all.where(_meta={"version": "tag-v1"})

assert {r.value for r in tag_v1} == {"engineer"}
```

Business-time selection uses `.at(t)` and reads `valid_from` / `valid_to` from
metadata:

```python
visible = snap.field("tags").all.at("2026-02-01T00:00:00Z")

assert {r.value for r in visible} == {"engineer"}
```

By-id selection returns a record set so you can still call `.one()`:

```python
same = snap.field("name").all.by_id(name_seed).one()

assert same.asrt_id == name_seed
```

## Graph-level assertion lookup

Use `fg.assertions.by_id(...)` and `fg.assertions.by_ids(...)` when you already
have assertion ids and do not need a snapshot.

```python
seed_record = fg.assertions.by_id(name_seed)

assert seed_record is not None
assert seed_record.value == "Alice"

records = fg.assertions.by_ids([name_seed, name_hr])

assert {r.value for r in records} == {"Alice", "Alice Liddell"}
```

`fg.assertions.where(...)` is the graph-level active assertion filter. It uses
the same `_meta` convention:

```python
seed_active = fg.assertions.where(field=User.name, e_ref=alice, _meta={"source": "seed"})

assert {r.asrt_id for r in seed_active} == {name_seed}
```

## Retracting one assertion

Retraction is append-only. It records that a specific assertion is no longer
active.

```python
reviewer_target = snap.field("tags").active.where(value="reviewer").one()

revoker = fg.assertions.retract(
    reviewer_target.asrt_id,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)

assert isinstance(revoker, str)

after = fg.entities.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
assert reviewer_target.asrt_id in {r.asrt_id for r in after.field("tags").all}
assert reviewer_target.asrt_id not in {r.asrt_id for r in after.field("tags").active}
```

Identity Claims are protected. If an `asrt_id` targets an Identity Claim,
`fg.assertions.retract(...)` raises `INV_7C_IDENTITY_PROTECTED`. Use
`fg.entities.delete(...)` for whole-entity lifecycle deletion.

## Complete example

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")

name_seed = fg.fields.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001", "version": "name-v1"},
)
name_hr = fg.fields.set(
    User.name,
    alice,
    "Alice Liddell",
    meta={"source": "hr", "trace_id": "hr-2026-05", "version": "name-v2"},
)
engineer = fg.fields.add(
    User.tags,
    alice,
    "engineer",
    meta={
        "source": "profile",
        "trace_id": "profile-001",
        "valid_from": "2026-01-01T00:00:00Z",
        "version": "tag-v1",
    },
)
reviewer = fg.fields.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "import-002"},
)

snap = fg.entities.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice Liddell"
assert set(snap.tags) == {"engineer", "reviewer"}

target = (
    snap.field("name")
    .all
    .where(value="Alice", _meta={"source": "seed", "version": "name-v1"})
    .one()
)

assert target.asrt_id == name_seed

visible = snap.field("tags").all.at("2026-02-01T00:00:00Z")
tag_v1 = snap.field("tags").all.where(_meta={"version": "tag-v1"})

assert {r.value for r in visible} == {"engineer"}
assert {r.value for r in tag_v1} == {"engineer"}

seed_record = fg.assertions.by_id(name_seed)

assert seed_record is not None
assert seed_record.value == "Alice"

reviewer_target = snap.field("tags").active.where(value="reviewer").one()
fg.assertions.retract(reviewer_target.asrt_id, meta={"source": "manual-fix"})

after = fg.entities.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
assert reviewer_target.asrt_id in {r.asrt_id for r in after.field("tags").all}
```

## Syntax checklist

- Field writes return `asrt_id` strings.
- `snap.assertions` is an entity-scoped `AssertionView`.
- `snap.field("name")` and `snap.assertions.field(User.name)` are field-scoped
  `AssertionView` objects.
- `AssertionView.active` returns non-revoked records.
- `AssertionView.all` returns active plus revoked records.
- `AssertionView.history` is a deprecated alias of `.all`.
- `AssertionRecordSet.where(value=..., value_tag=..., _meta={...})` is the
  canonical record filter.
- Version labels are metadata: use `.where(_meta={"version": v})`.
- `.at(t)` filters by business-time metadata.
- `.by_id(asrt_id).one()` selects one record by id.
- `fg.assertions.by_id(...)` and `fg.assertions.by_ids(...)` read records by id.
- `fg.assertions.where(field=..., e_ref=..., value=..., value_tag=..., _meta=...)`
  filters active graph-level assertion records.
- `fg.assertions.retract(asrt_id)` revokes exactly one assertion id.
- Do not retract by entity ref, value, or record object.
