# Define a schema

The schema is the vocabulary and coordinate system of a `FactGraph`. It tells
the graph which kinds of entities exist, how each entity is located, and which
facts can be asserted at that location.

The most important distinction is between `Identity` and `Field`:

- `Identity` fields define the entity coordinate.
- `Field` descriptors define fact content attached to that coordinate.

This is not a database table model where a primary key is the only identifier
and every other column is mutable content. In FactGraph, all `Identity` fields
participate in the generated entity reference. There is no primary/non-primary
split in the public schema surface: the complete Identity bundle is the
immutable coordinate.

This page stays with ordinary entity classes. Relationship classes are covered
later because they are a more advanced schema declaration.

## Entity classes

Every entity class subclasses `Entity`. Each entity must declare at least one
`Identity()`.

```python
from typing import Literal
from factgraph.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    locale: str = Identity()
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[str] = Field()
    team: Team = Field()
```

`FactGraph.create(...)` compiles these classes into the active graph schema:

```python
fg = FactGraph.create(schema_classes=[Team, User])
```

Internally, `FactGraph.create(...)` calls `compile_schema_from_classes(...)`
to turn the classes into the compiled schema IR. The high-level SDK
constructors (`create` / `load` / `attach`) hide that call so you only pass
classes. When you work directly with the lower-level `Database` boundary
(see [Database and durable views](database.md)), you compile once with
`compile_schema_from_classes(...)` and pass the IR as `schema_ir=` instead.

`User.user_id` and `User.locale` are both identity fields, so both participate
in the entity reference.

```python
user_en = fg.read.ref(User, user_id="u-1", locale="en")
user_zh = fg.read.ref(User, user_id="u-1", locale="zh")

assert user_en != user_zh
```

Those two references point to different complete coordinates. Every identity
value must be supplied explicitly; `Identity(default=...)` and
`Identity(default_factory=...)` are not part of Form I.

## Identity vs Field

Use `Identity` when a value decides where facts live. Use `Field` when a value
is itself a fact stored at that coordinate.

| Need | Use | Example |
| --- | --- | --- |
| Locate the coordinate | `Identity()` | `tenant_id`, `user_id`, `locale` |
| Store current mutable content | `Field()` with scalar annotation | `display_name`, `status` |
| Store multiple active facts | `Field()` with collection annotation | `tags`, `roles` |

So this model:

```text
class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    display_name: str = Field()
```

means:

```text
(User, user_id, locale) -> idref_v1
idref_v1 -> display_name
```

If `locale` decides which facts are being described, make it an `Identity()`.
If `locale` is only a changeable preference about one user coordinate, make it
a `Field(...)`.

Historically, this is the reason dimensions such as `dims` or `fact_key` do not
belong on `Field(...)`. Coordinate dimensions should be modeled as n-ary
identity fields. Field values are the facts attached to the resulting
coordinate.

## How schema becomes graph facts

The SDK stores facts in a normalized graph form. You declare Python classes, but
the graph works with predicate ids, entity references, assertion rows, and
values.

You normally do not write that lower-level form yourself. The schema compiler
does the splitting:

```text
User.display_name -> predicate id "user:display_name"
User.tags         -> predicate id "user:tags"
(User, user_id, locale) -> idref_v1 entity coordinate
fg.write.set(User.display_name, user_ref, "Alice")
  -> one assertion row for predicate "user:display_name"
```

This normalized fact shape is useful because schema, reads, writes, rules,
inferences, and audit all agree on the same predicate and assertion model. The
quickstart calls it the graph fact model; internal design notes may call this
GNF. The user-facing rule is simpler: declare `Entity`, `Identity`, and
`Field`, then let the SDK split them into graph predicates and assertion rows.

## Single, multi, and entity references

Cardinality is inferred from type annotations. A scalar annotation such as
`str`, `int`, `bool`, `UUID`, `datetime`, or another `Entity` subclass is a
single field. Collection annotations `list[T]`, `tuple[T, ...]`, `set[T]`,
and `frozenset[T]` are multi fields.

`Literal[...]` adds an enum constraint, and `pattern=` adds a regex constraint
for string-valued `Identity` or `Field` descriptors. These constraints are
stored in schema truth and enforced by the application write path before ledger
append.

```python
team_ref = fg.read.ref(Team, team_id="t-1")
user_ref = fg.read.ref(User, user_id="u-1", locale="en")

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_ref, "Alice")
fg.write.set(User.status, user_ref, "active")
fg.write.add(User.tags, user_ref, "engineer")
fg.write.set(User.team, user_ref, team_ref)
```

`User.team` is a normal field whose value is another entity reference. Use the
reference returned by `fg.read.ref(...)` from the same graph; do not parse,
construct, or copy an `idref_v1` string by hand.

```python
user = fg.read.get(User, user_id="u-1", locale="en")

assert user is not None
assert user.display_name == "Alice"
assert user.status == "active"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
```

`fg.read.get(...)` reads one complete coordinate. When you want matching
coordinates under a partial filter, use `fg.read.find(...)`.

```python
zh_ref = fg.read.ref(User, user_id="u-1", locale="zh")
fg.write.set(User.display_name, zh_ref, "Alice ZH")

rows = fg.read.find(User, user_id="u-1")

assert {row.identity["locale"] for row in rows} == {"en", "zh"}
assert {row.display_name for row in rows} == {"Alice", "Alice ZH"}
```

Each row returned by `find` is still a full-coordinate snapshot. There is no
separate primary-only entity reference, and batch writes also require the full
Identity bundle when constructing a handle.

## Adding fields later

`fg.schema.add(...)` is additive. It can add a new entity type or add
non-identity fields to an existing entity type. To add a field to an existing
entity, declare a replacement class with the same Python class name and the new
field included.

This is a graph schema transition, not ordinary Python monkey-patching. The new
class object is the post-add declaration. After the graph accepts it, use that
replacement class for reads and writes. The old class and its descriptors
represent an earlier schema declaration.

```python
class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    display_name: str = Field()
    tags: list[str] = Field()
    team: Team = Field()
    nickname: str = Field()
    skills: list[str] = Field()


result = fg.schema.add(User)

assert result.added_entities == []
assert result.added_fields == ["User.nickname", "User.skills"]
```

Existing facts remain readable. New single fields read as `None` until written.
New multi fields read as `()`.

```python
updated = fg.read.get(User, user_id="u-1", locale="en")

assert updated is not None
assert updated.nickname is None
assert tuple(updated.skills) == ()
```

## What schema add will not do

The current schema mutation surface is **intentionally narrow and
additive-only by design**. It does not delete fields, rename fields, change
field types, change cardinality, or change identity fields. Each of those
operations would change the workspace `schema_digest`, which is recorded
on every assertion's transaction and is the anchor for `FactGraph.load(...)`,
`FactGraph.attach(...)`, and the durable Database boundary
(see [Database and durable views](database.md#schema-strong-correspondence)).
Schema migration semantics that re-anchor existing facts to a new digest
are an explicit design decision deferred to a future migration cycle, not
an accident of incomplete coverage.

## Complete example

```python
from typing import Literal
from factgraph.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity()
    name: str = Field()


class User(Entity):
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    locale: str = Identity()
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[str] = Field()
    team: Team = Field()


fg = FactGraph.create(schema_classes=[Team, User])

team_ref = fg.read.ref(Team, team_id="t-1")
user_en = fg.read.ref(User, user_id="u-1", locale="en")
user_zh = fg.read.ref(User, user_id="u-1", locale="zh")

assert user_en != user_zh

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_en, "Alice")
fg.write.set(User.status, user_en, "active")
fg.write.add(User.tags, user_en, "engineer")
fg.write.set(User.team, user_en, team_ref)
fg.write.set(User.display_name, user_zh, "Alice ZH")

user = fg.read.get(User, user_id="u-1", locale="en")
rows = fg.read.find(User, user_id="u-1")

assert user is not None
assert user.display_name == "Alice"
assert user.status == "active"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
assert {row.identity["locale"] for row in rows} == {"en", "zh"}


class User(Entity):
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    locale: str = Identity()
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[str] = Field()
    team: Team = Field()
    nickname: str = Field()
    skills: list[str] = Field()


result = fg.schema.add(User)
updated = fg.read.get(User, user_id="u-1", locale="en")

assert result.added_fields == ["User.nickname", "User.skills"]
assert updated is not None
assert updated.nickname is None
assert tuple(updated.skills) == ()
```

## Syntax checklist

- Define graph vocabulary with `class User(Entity): ...`.
- Use `Identity()` for immutable coordinate values.
- Every `Identity` field participates in the complete `idref_v1` coordinate.
- Supply every identity value explicitly; Identity defaults are not part of Form I.
- Use `Field()` with a scalar annotation for one active value at a coordinate.
- Use `Field()` with a collection annotation for multiple active values at a coordinate.
- Use `Literal[...]` for enum-constrained fields and `pattern=` for string regex validation.
- Use managed refs from `fg.read.ref(...)`; do not hand-build `idref_v1`.
- Use `fg.read.get(Entity, **full_identity)` for one full coordinate.
- Use `fg.read.find(Entity, **partial_filters)` for matching snapshots.
- In batches, construct handles with the complete Identity bundle.
- Add schema with `fg.schema.add(NewEntity)` or same-name replacement classes.
- Field-add can only add non-identity fields; old class descriptors are
  superseded by the replacement class.
- New `single` fields read as `None`; new `multi` fields read as `()`.
- Deletes, renames, type changes, cardinality changes, identity changes,
  defaults, and backfill are not part of the current additive schema surface.
