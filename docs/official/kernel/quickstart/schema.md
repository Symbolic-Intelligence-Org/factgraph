# Define a schema

The schema is the set of Python declarations that tells a `FactGraph` what
entities exist and which facts can be written about them. A good first schema
usually answers three questions:

- What identifies each entity?
- Which values are current single values?
- Which values can have many active entries?

This page stays with ordinary entity classes. Relationship classes are covered
later because they are a more advanced schema declaration.

You can think of the schema as the graph's vocabulary. Entity classes name the
kinds of things the graph can talk about. Identity fields say how one thing is
located. Field descriptors say which facts can be asserted about that thing.
Without the schema, the graph would have facts but no stable language for
reading or validating them.

## Entity classes

Every entity class subclasses `Entity`. Identity fields locate the entity.
Regular fields hold facts about it.

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
```

`FactGraph.create(...)` compiles these classes into the active graph schema:

```python
fg = FactGraph.create(schema_classes=[Team, User])
```

Each entity must have at least one `Identity(primary_key=True)` field. A primary
identity should be stable, compact, and known before you write facts for the
entity.

Do not use a display label or a mutable business attribute as the primary
identity if it can change later. The identity is the coordinate system the graph
uses to attach assertions to the same entity over time.

## Single and multi fields

Use `cardinality="single"` when the field should read as one current value.
Use `cardinality="multi"` when the field should read as a collection.

```python
team_ref = fg.read.ref(Team, team_id="t-1")
user_ref = fg.read.ref(User, user_id="u-1")

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_ref, "Alice")
fg.write.add(User.tags, user_ref, "engineer")
fg.write.set(User.team, user_ref, team_ref)
```

`User.team` is a normal field whose value is another entity reference. Store the
reference returned by `fg.read.ref(...)`; do not parse or build the reference
string yourself.

```python
user = fg.read.get(User, user_id="u-1")

assert user is not None
assert user.display_name == "Alice"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
```

## Adding fields later

`fg.schema.add(...)` is additive. It can add a new entity type or add
non-identity fields to an existing entity type. To add a field to an existing
entity, declare a replacement class with the same Python class name and the new
field included.

This is a graph schema transition, not ordinary Python monkey-patching. After
the graph accepts the replacement declaration, use the replacement class object
for reads and writes. The old class and its descriptors represent an earlier
schema declaration.

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
    nickname: str = Field(cardinality="single")


result = fg.schema.add(User)

assert result.added_entities == []
assert result.added_fields == ["User.nickname"]
```

After a field add, use the replacement class object. The old class declaration
is treated as superseded.

```python
updated = fg.read.get(User, user_id="u-1")

assert updated is not None
assert updated.nickname is None
```

Existing facts remain readable. New single fields read as `None` until written.
New multi fields read as `()`.

## What schema add will not do

The first schema mutation surface is intentionally narrow. It does not delete
fields, rename fields, change field types, change cardinality, or change identity
fields. Those operations need an explicit migration design because they affect
existing facts and saved authoring assets.

## Complete example

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class Team(Entity):
    team_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")


fg = FactGraph.create(schema_classes=[Team, User])

team_ref = fg.read.ref(Team, team_id="t-1")
user_ref = fg.read.ref(User, user_id="u-1")

fg.write.set(Team.name, team_ref, "Research")
fg.write.set(User.display_name, user_ref, "Alice")
fg.write.add(User.tags, user_ref, "engineer")
fg.write.set(User.team, user_ref, team_ref)

user = fg.read.get(User, user_id="u-1")

assert user is not None
assert user.display_name == "Alice"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref


class User(Entity):
    user_id: str = Identity(primary_key=True)
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    team: Team = Field(cardinality="single")
    nickname: str = Field(cardinality="single")


result = fg.schema.add(User)
updated = fg.read.get(User, user_id="u-1")

assert result.added_fields == ["User.nickname"]
assert updated is not None
assert updated.nickname is None
```

## What to remember

- Identity fields are how the graph finds entities.
- `single` fields read as one current value.
- `multi` fields read as a tuple-like collection.
- Entity-reference fields store `fg.read.ref(...)` values.
- `fg.schema.add(...)` can add entity types and non-identity fields.
- Field deletes, rewrites, renames, type changes, and identity changes are not
  part of the current additive schema surface.
