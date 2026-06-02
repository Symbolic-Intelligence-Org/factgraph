# Read and write facts

The first two pages showed the shape of a graph. This page focuses on the
everyday data path: create an entity coordinate, write fields, read snapshots,
filter entities, and retract by assertion id.

A `FactGraph` is not a mutable table. A write appends an assertion to the
ledger. A read resolves active assertions into a read-only snapshot. That
distinction is why the API is grouped by navigation key:

- `fg.entities.*` for entity lifecycle and entity reads;
- `fg.fields.*` for field writes and field-level reads;
- `fg.assertions.*` for assertion-id reads and assertion-id retraction.

## The entity coordinate

Writes need an entity reference. Create one from the full identity bundle:

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])

alice = fg.entities.create(User, user_id="u-1")
```

The reference is the graph coordinate for "the `User` whose `user_id` is
`u-1`". The token has a canonical `idref_v1:` prefix and an opaque payload;
treat it as a handle returned by the SDK and do not parse or construct it
yourself.

`fg.entities.create(...)` emits the entity identity (writes Identity Claims
plus a `<EntityType>:exists` Claim to the ledger). `fg.entities.ref(...)`
returns the deterministic reference for an identity coordinate and registers
the bundle in the SDK shadow store, without writing identity Claims to the
ledger. Use `create(...)` for explicit entity-lifecycle entries, and `ref(...)`
when you only need the reference for follow-up `fg.fields.*` writes.

## Single and multi writes

Use `fg.fields.set(...)` for single-value fields and `fg.fields.add(...)` for
multi-value fields.

```python
name_id = fg.fields.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
tag_engineer = fg.fields.add(
    User.tags,
    alice,
    "engineer",
    meta={"source": "profile", "trace_id": "profile-001"},
)
tag_reviewer = fg.fields.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)
```

Each call returns an `asrt_id`. The id identifies the exact ledger record that
was written. Keep it whenever you may want to audit or retract that assertion
later.

Calling `set` again appends a newer assertion. The snapshot's scalar view
chooses the latest active value for a single-value field.

## Current snapshots

Use `fg.entities.get(...)` when you know the full identity.

```python
snap = fg.entities.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert set(snap.tags) == {"engineer", "reviewer"}
```

The snapshot is read-only. It is the graph's current answer for that entity,
not the ledger itself.

When you need to know why a snapshot has a value, open an assertion view:

```python
name_records = snap.field("name").active
tag_records = snap.field("tags").all
```

The next page, [Assertion records and views](assertions.md), explains how to
filter those records by value and metadata.

## Field-level reads and deletes

`fg.fields.get(field, e_ref)` returns the **current** value for a single
coordinate (single-cardinality fields return the chosen value; multi-cardinality
fields return the tuple of active values):

```python
current_name = fg.fields.get(User.name, alice)
assert current_name == "Alice"

current_tags = fg.fields.get(User.tags, alice)
assert set(current_tags) == {"engineer", "reviewer"}
```

`fg.fields.delete(field_or_identity, e_ref, *, meta=None)` retracts the
entire field (all active assertions for that coordinate) in a single call.
It accepts either a `Field` descriptor or an `Identity` descriptor:

```python
fg.fields.delete(User.tags, alice)
assert fg.fields.get(User.tags, alice) == ()
```

`fg.fields.set(...)` chooses the latest active assertion under
single-cardinality semantics (tie-broken by `ingested_at` descending, then
`asrt_id` lexicographic); for multi-cardinality fields, `set(...)` replaces
the whole set while `add(...)` appends. Use `fg.assertions.retract(asrt_id,
*, meta=None)` for assertion-id-level retraction (next section).

## Existence and entity lifecycle

`fg.entities.exists(EntityCls, **identity)` returns a boolean without
materializing a snapshot. Useful for guard clauses:

```python
if not fg.entities.exists(User, user_id="u-3"):
    fg.entities.create(User, user_id="u-3")
```

`fg.entities.delete(e_ref_or_cls, *, meta=None, **identity)` retracts the
entity coordinate (its Identity Claims + `<EntityType>:exists` Claim). It
accepts either an existing entity ref or an `EntityCls + **identity`
descriptor:

```python
fg.entities.delete(User, user_id="u-2")
assert not fg.entities.exists(User, user_id="u-2")
```

For multi-field staged edits before commit, `fg.entities.edit(EntityCls,
**identity)` returns an `EntityEditor` that buffers writes until
`.commit()` (or `.rollback()`):

```python
with fg.entities.edit(User, user_id="u-1") as editor:
    editor.set(User.name, "Alicia")
    editor.add(User.tags, "lead")
    editor.commit()
```

The editor closes at the end of the `with` block; using it after closure
raises `EditorClosedError`.

## Finding entities

Use `fg.entities.where(...)` when you want all matching snapshots. Field filters
are exact matches. For a multi-value field, the filter is a containment check.

```python
bob = fg.entities.create(User, user_id="u-2")
fg.fields.set(User.name, bob, "Bob")
fg.fields.add(User.tags, bob, "reviewer")

reviewers = fg.entities.where(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice", "Bob"}
```

`where(...)` is for direct entity and field filters. When the read pattern needs
a `Rule` or an AND-only `RuleExpr`, use `fg.entities.match(...)`; see
[Rules and inferences](rules-and-inferences.md#reading-snapshots-with-match).

## Retracting an assertion

Retraction is append-only. It records that a specific assertion should no
longer be active in current reads.

`fg.assertions.retract(...)` takes an `asrt_id`, not an entity ref:

```python
revoker_id = fg.assertions.retract(
    tag_reviewer,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)

assert isinstance(revoker_id, str)

after = fg.entities.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

Here `tag_reviewer` is the `asrt_id` returned by the earlier
`fg.fields.add(...)` call. The original assertion is not deleted; it moves out
of the active set into history. The retract itself is a separate ledger record.

Identity Claims are protected. Attempting to retract an identity assertion by
id raises `SDKStoreError` with code `INV_7C_IDENTITY_PROTECTED`; use
`fg.entities.delete(...)` for whole
entity lifecycle changes.

## Complete example

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])

alice = fg.entities.create(User, user_id="u-1")
name_id = fg.fields.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "import", "trace_id": "seed-001"},
)
tag_engineer = fg.fields.add(
    User.tags,
    alice,
    "engineer",
    meta={"source": "profile", "trace_id": "profile-001"},
)
tag_reviewer = fg.fields.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "seed-002"},
)

snap = fg.entities.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert set(snap.tags) == {"engineer", "reviewer"}

bob = fg.entities.create(User, user_id="u-2")
fg.fields.set(User.name, bob, "Bob")
fg.fields.add(User.tags, bob, "reviewer")

reviewers = fg.entities.where(User, tags="reviewer")

assert {row.name for row in reviewers} == {"Alice", "Bob"}

fg.assertions.retract(tag_reviewer, meta={"source": "manual-fix"})

after = fg.entities.get(User, user_id="u-1")

assert after is not None
assert tuple(after.tags) == ("engineer",)
```

## Syntax checklist

- `fg.entities.create(...)` creates and materializes an entity coordinate.
- `fg.entities.ref(...)` returns a deterministic entity reference for an
  already-known coordinate.
- `fg.fields.set(...)` appends a single-value field assertion.
- `fg.fields.add(...)` appends a multi-value field assertion.
- `meta={"source": ..., "trace_id": ...}` attaches audit-friendly metadata.
- Field writes return `asrt_id` strings for exact ledger records.
- `fg.entities.get(...)` returns the current snapshot for a full identity.
- `fg.entities.where(...)` returns snapshots matching entity/field filters.
- `fg.entities.match(...)` returns snapshots selected by a `Rule` or
  `RuleExpr`.
- `fg.assertions.retract(asrt_id)` records a retraction by id and returns the
  revoker's `asrt_id`.
- The ledger is append-only; snapshots are read-time views over assertions.
- For deeper assertion mechanics, see [Assertion records and views](assertions.md).
