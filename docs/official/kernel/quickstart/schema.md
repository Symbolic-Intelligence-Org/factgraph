# Define a schema

The schema is the vocabulary and coordinate system of a `FactGraph`. It tells
the graph which kinds of entities exist, how each entity is located, and which
facts can be asserted at that location.

The most important distinction is between `Identity` and `Field`:

- `Identity` fields define the entity coordinate.
- `Field` descriptors define fact content attached to that coordinate.

This is not a database table model where a primary key is the only identifier
and every other column is mutable content. In FactGraph, all `Identity` fields
participate in the generated entity reference. `primary_key=True` marks the
logical anchor used by authoring and cross-coordinate joins; it does not exclude
non-primary identities from the coordinate.

This page stays with ordinary entity classes. Relationship classes are covered
later because they are a more advanced schema declaration.

## Entity classes

Every entity class subclasses `Entity`. Each entity must declare at least one
`Identity(primary_key=True)`.

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
```

`FactGraph.create(...)` compiles these classes into the active graph schema:

```python
fg = FactGraph.create(schema_classes=[Team, User])
```

`User.user_id` is the logical anchor. `User.locale` is a coordinate dimension.
Both are identity fields, so both participate in the entity reference.

```python
user_en = fg.read.ref(User, user_id="u-1", locale="en")
user_zh = fg.read.ref(User, user_id="u-1", locale="zh")

assert user_en != user_zh
```

Those two references point to different complete coordinates. They share the
same primary anchor (`user_id="u-1"`), but they are not the same entity
coordinate.

## Identity vs Field

Use `Identity` when a value decides where facts live. Use `Field` when a value
is itself a fact stored at that coordinate.

| Need | Use | Example |
| --- | --- | --- |
| Locate the logical thing | `Identity(primary_key=True)` | `user_id` |
| Separate domains under the same anchor | `Identity()` | `locale`, `work_id`, `tenant_id` |
| Store current mutable content | `Field(cardinality="single")` | `display_name`, `status` |
| Store multiple active facts | `Field(cardinality="multi")` | `tags`, `roles` |

So this model:

```text
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
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

## Single, multi, and entity references

Use `cardinality="single"` when the field should read as one current value.
Use `cardinality="multi"` when the field should read as a collection.

```python
team_ref = fg.read.ref(Team, team_id="t-1")
user_ref = fg.read.ref(User, user_id="u-1", locale="en")

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_ref, "Alice")
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
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
```

`fg.read.get(...)` reads one complete coordinate. When you want all coordinates
under a primary anchor, use `fg.read.find(...)`.

```python
zh_ref = fg.read.ref(User, user_id="u-1", locale="zh")
fg.write.set(User.display_name, zh_ref, "Alice ZH")

rows = fg.read.find(User, user_id="u-1")

assert {row.identity["locale"] for row in rows} == {"en", "zh"}
assert {row.display_name for row in rows} == {"Alice", "Alice ZH"}
```

Each row returned by `find` is still a full-coordinate snapshot. There is no
separate primary-only entity reference.

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
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
    nickname: str = Field(cardinality="single")
    skills: str = Field(cardinality="multi")


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

The current schema mutation surface is intentionally narrow. It does not delete
fields, rename fields, change field types, change cardinality, or change
identity fields. Those operations need an explicit migration design because
they affect existing facts, saved rules, saved inferences, and workspace schema
digests.

## Complete example

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")


fg = FactGraph.create(schema_classes=[Team, User])

team_ref = fg.read.ref(Team, team_id="t-1")
user_en = fg.read.ref(User, user_id="u-1", locale="en")
user_zh = fg.read.ref(User, user_id="u-1", locale="zh")

assert user_en != user_zh

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_en, "Alice")
fg.write.add(User.tags, user_en, "engineer")
fg.write.set(User.team, user_en, team_ref)
fg.write.set(User.display_name, user_zh, "Alice ZH")

user = fg.read.get(User, user_id="u-1", locale="en")
rows = fg.read.find(User, user_id="u-1")

assert user is not None
assert user.display_name == "Alice"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
assert {row.identity["locale"] for row in rows} == {"en", "zh"}


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
    nickname: str = Field(cardinality="single")
    skills: str = Field(cardinality="multi")


result = fg.schema.add(User)
updated = fg.read.get(User, user_id="u-1", locale="en")

assert result.added_fields == ["User.nickname", "User.skills"]
assert updated is not None
assert updated.nickname is None
assert tuple(updated.skills) == ()
```

## What to remember

- `Identity` fields define the entity coordinate.
- All `Identity` fields participate in the generated `idref_v1` reference.
- `primary_key=True` marks the logical anchor; it is not the only identity
  field used by the ref.
- `Field(...)` values are mutable facts attached to a complete coordinate.
- Use `fg.read.get(...)` for one full coordinate.
- Use `fg.read.find(...)` for partial identity filters such as a primary
  anchor.
- Entity-reference fields store managed refs returned by `fg.read.ref(...)`.
- `fg.schema.add(...)` can add entity types and non-identity fields.
- Field deletes, rewrites, renames, type changes, and identity changes are not
  part of the current additive schema surface.
