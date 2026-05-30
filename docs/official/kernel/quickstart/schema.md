# Define a schema

The schema is the vocabulary and coordinate system of a `FactGraph`. It tells
the graph which entity types exist, how each entity is located, and which facts
can be asserted at that location.

The main distinction is:

- `Identity()` fields form the immutable entity coordinate.
- `Field()` descriptors hold facts attached to that coordinate.

There is no primary/non-primary identity split in Form I. Every `Identity()`
participates in the entity reference.

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

`User.user_id` and `User.locale` are both identity fields, so both participate
in the entity reference.

```python
user_en = fg.entities.create(User, user_id="u-1", locale="en")
user_zh = fg.entities.create(User, user_id="u-1", locale="zh")

assert user_en != user_zh
```

Every identity value must be supplied explicitly. `Identity(default=...)` and
`Identity(default_factory=...)` are not part of Form I.

## Identity vs Field

Use `Identity()` when a value decides where facts live. Use `Field()` when a
value is itself a fact stored at that coordinate.

| Need | Use | Example |
|---|---|---|
| Locate the coordinate | `Identity()` | `tenant_id`, `user_id`, `locale` |
| Store current mutable content | `Field()` with scalar annotation | `display_name`, `status` |
| Store multiple active facts | `Field()` with collection annotation | `tags`, `roles` |
| Store another entity reference | `Field()` with an `Entity` annotation | `team: Team = Field()` |

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
a `Field()`.

## Writing values from schema descriptors

Cardinality is inferred from type annotations. A scalar annotation is a
single-value field. Collection annotations such as `list[T]` are multi-value
fields.

`Literal[...]` adds an enum constraint, and `pattern=` adds a regex constraint
for string-valued `Identity()` or `Field()` descriptors.

```python
team_ref = fg.entities.create(Team, team_id="t-1")

fg.fields.set(Team.name, team_ref, "Research")
fg.fields.set(User.display_name, user_en, "Alice")
fg.fields.set(User.status, user_en, "active")
fg.fields.add(User.tags, user_en, "engineer")
fg.fields.set(User.team, user_en, team_ref)

user = fg.entities.get(User, user_id="u-1", locale="en")

assert user is not None
assert user.display_name == "Alice"
assert user.status == "active"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
```

Use `fg.entities.where(...)` when you want matching snapshots under a partial
filter:

```python
fg.fields.set(User.display_name, user_zh, "Alice ZH")

rows = fg.entities.where(User, user_id="u-1")

assert {row.identity["locale"] for row in rows} == {"en", "zh"}
assert {row.display_name for row in rows} == {"Alice", "Alice ZH"}
```

## Registering a new entity type

`fg.schema.register(EntityCls)` registers a new entity type after the graph was
created.

```python
class Project(Entity):
    project_id: str = Identity()
    title: str = Field()


register_result = fg.schema.register(Project)

assert register_result.added_entities == ["Project"]
```

After registration, use the registered class normally:

```python
project_ref = fg.entities.create(Project, project_id="p-1")
fg.fields.set(Project.title, project_ref, "Apollo")

project = fg.entities.get(Project, project_id="p-1")

assert project is not None
assert project.title == "Apollo"
```

Registering an already-known entity type raises `SchemaConflictError`.

## Extending an existing entity type

`fg.schema.extend(EntityCls)` adds non-identity fields to an existing entity
type. Use a replacement class with the same Python class name and the new
fields included.

```python
class User(Entity):
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    locale: str = Identity()
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[str] = Field()
    team: Team = Field()
    nickname: str = Field()
    skills: list[str] = Field()


extend_result = fg.schema.extend(User)

assert extend_result.added_entities == []
assert extend_result.added_fields == ["User.nickname", "User.skills"]
```

Existing facts remain readable. New single fields read as `None` until written.
New multi fields read as `()`.

```python
updated = fg.entities.get(User, user_id="u-1", locale="en")

assert updated is not None
assert updated.nickname is None
assert tuple(updated.skills) == ()
```

After a successful extension, use the replacement class object for reads and
writes. Superseded descriptors belong to the older schema declaration.

## Applying a safe schema diff

`fg.schema.apply(EntityCls)` routes to `register(...)` for a new entity type and
to `extend(...)` for an existing entity type.

```python
class Team(Entity):
    team_id: str = Identity()
    name: str = Field()
    region: str = Field()


apply_result = fg.schema.apply(Team)

assert apply_result.added_fields == ["Team.region"]
```

Use `apply(...)` when the caller is intentionally accepting either safe path.
Use `register(...)` or `extend(...)` when the operation kind itself matters.

## What schema extension will not do

Schema extension is additive-only. It rejects:

- adding, removing, or changing Identity fields;
- changing a Field into an Identity or an Identity into a Field;
- removing fields;
- changing field type or cardinality;
- changing the generated `<EntityType>:exists` predicate.

These rejections happen before schema state is mutated. Destructive schema
migration is a separate future design problem.

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

team_ref = fg.entities.create(Team, team_id="t-1")
user_en = fg.entities.create(User, user_id="u-1", locale="en")
user_zh = fg.entities.create(User, user_id="u-1", locale="zh")

assert user_en != user_zh

fg.fields.set(Team.name, team_ref, "Research")
fg.fields.set(User.display_name, user_en, "Alice")
fg.fields.set(User.status, user_en, "active")
fg.fields.add(User.tags, user_en, "engineer")
fg.fields.set(User.team, user_en, team_ref)
fg.fields.set(User.display_name, user_zh, "Alice ZH")

user = fg.entities.get(User, user_id="u-1", locale="en")
rows = fg.entities.where(User, user_id="u-1")

assert user is not None
assert user.display_name == "Alice"
assert user.status == "active"
assert tuple(user.tags) == ("engineer",)
assert user.team == team_ref
assert {row.identity["locale"] for row in rows} == {"en", "zh"}


class Project(Entity):
    project_id: str = Identity()
    title: str = Field()


register_result = fg.schema.register(Project)

assert register_result.added_entities == ["Project"]

project_ref = fg.entities.create(Project, project_id="p-1")
fg.fields.set(Project.title, project_ref, "Apollo")


class User(Entity):
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    locale: str = Identity()
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[str] = Field()
    team: Team = Field()
    nickname: str = Field()
    skills: list[str] = Field()


extend_result = fg.schema.extend(User)
updated = fg.entities.get(User, user_id="u-1", locale="en")

assert extend_result.added_fields == ["User.nickname", "User.skills"]
assert updated is not None
assert updated.nickname is None
assert tuple(updated.skills) == ()
```

## Syntax checklist

- Define graph vocabulary with `class User(Entity): ...`.
- Use `Identity()` for immutable coordinate values.
- Every `Identity()` field participates in the complete entity reference.
- Supply every identity value explicitly.
- Use `Field()` with scalar annotations for single-value fields.
- Use `Field()` with collection annotations for multi-value fields.
- Use `Literal[...]` and `pattern=` for validation constraints.
- Use `fg.entities.create(...)` to create entity coordinates.
- Use `fg.entities.ref(...)` for a deterministic ref to an already-known
  coordinate.
- Use `fg.entities.get(Entity, **full_identity)` for one full coordinate.
- Use `fg.entities.where(Entity, **partial_filters)` for matching snapshots.
- Use `fg.schema.register(EntityCls)` for a new entity type.
- Use `fg.schema.extend(EntityCls)` for additive field extension.
- Use `fg.schema.apply(EntityCls)` when either safe path is acceptable.
- Schema extension does not delete, rename, backfill, change identity, change
  type, or change cardinality.
