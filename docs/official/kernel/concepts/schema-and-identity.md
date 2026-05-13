# Schema and identity

The quickstart showed how to declare `Entity`, `Identity`, and `Field`. This
page explains the model behind those names.

The short version:

```text
Identity fields -> entity coordinate -> idref_v1
Field values    -> facts attached to that coordinate
```

`primary_key=True` does not mean "this is the only field that identifies the
entity." It means "this identity field is the logical anchor." All identity
fields still participate in the full coordinate.

## The schema is a coordinate model

An entity class defines two kinds of information:

- where facts live;
- what facts can be written there.

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
```

`User.user_id` and `User.locale` are both identity fields. Together they define
the coordinate. `display_name` and `tags` are facts that can be asserted at one
coordinate.

```text
(User, user_id, locale) -> idref_v1
idref_v1 -> display_name
idref_v1 -> tags
```

This is the main difference from a table row model. `locale` is not just
another mutable column if it is declared as `Identity()`. It decides which
coordinate receives the facts.

## Primary identity is a logical anchor

The primary identity is the first handle you usually think with. It answers:
"which logical thing are we talking about?"

The non-primary identity answers: "which coordinate or domain under that
anchor are we talking about?"

```python
user_en = fg.read.ref(User, user_id="u-1", locale="en")
user_zh = fg.read.ref(User, user_id="u-1", locale="zh")

assert user_en != user_zh
```

Both refs share the same primary anchor, `user_id="u-1"`. They are still
different full coordinates because `locale` differs.

The complete mental model is:

| Declaration | Role | Enters `idref_v1`? | Mutable fact content? |
| --- | --- | --- | --- |
| `Identity(primary_key=True)` | logical anchor | yes | no |
| `Identity()` | coordinate/domain dimension | yes | no |
| `Field(cardinality="single")` | one current fact value | no | yes |
| `Field(cardinality="multi")` | multiple active fact values | no | yes |

## Field facts attach to one complete coordinate

When you write a field, you choose one full coordinate first.

```python
fg.write.set(User.display_name, user_en, "Alice")
fg.write.set(User.display_name, user_zh, "艾丽丝")
fg.write.add(User.tags, user_en, "engineer")

en = fg.read.get(User, user_id="u-1", locale="en")
zh = fg.read.get(User, user_id="u-1", locale="zh")

assert en is not None
assert zh is not None
assert en.display_name == "Alice"
assert zh.display_name == "艾丽丝"
assert tuple(en.tags) == ("engineer",)
assert tuple(zh.tags) == ()
```

The `tags` write went to the English coordinate only. It did not fan out to all
coordinates sharing `user_id="u-1"`.

That is deliberate. Write-side operations target a full coordinate. There is no
primary-anchor fan-out write API.

## `get` reads one coordinate; `find` can collect coordinates

Use `fg.read.get(...)` when you know the full identity coordinate.

```python
one = fg.read.get(User, user_id="u-1", locale="en")

assert one is not None
assert one.identity["user_id"] == "u-1"
assert one.identity["locale"] == "en"
```

Use `fg.read.find(...)` when you want all coordinates matching a partial
identity or field filter.

```python
rows = fg.read.find(User, user_id="u-1")

assert {row.identity["locale"] for row in rows} == {"en", "zh"}
assert {row.display_name for row in rows} == {"Alice", "艾丽丝"}
```

`find(...)` returns a list of full-coordinate snapshots. It does not return a
separate primary-only entity object. If you want one locale, filter the returned
snapshots with ordinary Python.

## Primary-first binding in batch writes

The special role of `primary_key=True` is most visible in batch writes.

Batch handles are primary-first. You start from the primary anchor, then bind
non-primary identity fields before writing.

```python
with fg.batch() as tx:
    user = tx.entity(User, user_id="u-2")
    user.bind(locale="en")
    user.display_name.set("Bob")
    tx.commit(objects=[user])

bob = fg.read.get(User, user_id="u-2", locale="en")

assert bob is not None
assert bob.display_name == "Bob"
```

`tx.entity(User, user_id="u-2")` is not a runtime `idref_v1` by itself. It is an
SDK handle anchored by the primary identity. `bind(locale="en")` completes the
coordinate before the write.

`bind(...)` may complete non-primary identity fields. It is not where you add
or change primary identity fields.

## Why dimensions became identity fields

Earlier designs considered attaching dimensions such as language, channel, or
work id to a `Field`. That made a field carry its own mini-key, which confused
two different jobs:

- locating the fact;
- storing the fact value.

The current model keeps those jobs separate. If a value decides where facts
live, make it an `Identity`. If a value is the content being asserted, make it a
`Field`.

| Question | Schema choice |
| --- | --- |
| Does this value choose a coordinate? | `Identity(...)` |
| Is this the main logical anchor? | `Identity(primary_key=True)` |
| Does this value vary under a coordinate? | `Field(...)` |
| Is this a mutable preference, status, or label? | `Field(...)` |

For example, `locale` should be an identity if `display_name` differs by
locale. It should be a field if it is only the user's current language
preference.

## Schema add follows the same boundary

`fg.schema.add(...)` can extend a graph schema, but it keeps the identity
boundary strict.

Adding a new non-identity field is additive:

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    display_name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
    nickname: str = Field(cardinality="single")
    skills: str = Field(cardinality="multi")


result = fg.schema.add(User)

assert result.added_entities == []
assert result.added_fields == ["User.nickname", "User.skills"]
```

Existing assertions are not backfilled. Missing added fields read as the normal
empty value for their cardinality.

```python
after_add = fg.read.get(User, user_id="u-1", locale="en")

assert after_add is not None
assert after_add.nickname is None
assert tuple(after_add.skills) == ()
```

Changing identity fields is not additive. Adding, removing, or rewriting
identity fields changes the coordinate model, so it belongs to a future
migration design rather than `fg.schema.add(...)`.

## What to remember

- All `Identity` fields define the complete coordinate.
- `primary_key=True` marks the logical anchor; it is not the only identity.
- `Field(...)` values are mutable facts attached to one coordinate.
- `fg.read.get(...)` reads one full coordinate.
- `fg.read.find(...)` can collect full-coordinate snapshots under a partial
  identity filter.
- Batch writes start from primary identity, then bind non-primary identity
  dimensions.
- Schema field-add is additive only for non-identity fields.
