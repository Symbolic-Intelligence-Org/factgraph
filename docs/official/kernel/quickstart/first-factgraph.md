# Your first FactGraph

This page builds the smallest useful graph: a schema, two writes, and one read.
It uses only the in-memory SDK path so you can see the core model before adding
rules, inferences, workspaces, or persistence.

A `FactGraph` is a place where typed facts live. The schema says what kinds of
things the graph can talk about. Writes append assertions to the graph ledger.
Reads resolve those assertions into the current snapshot of an entity.

That is why the first example has three parts: declare the shape of a `User`,
write a few facts about one user identity, then read back the current view of
that user. You are not mutating a Python `User` object; you are adding facts to
the graph.

## Define a schema

A FactGraph starts from Python classes. Each class represents an entity type.
`Identity` fields identify an entity, and `Field` descriptors hold values about
that entity.

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
```

`single` fields keep the current value. `multi` fields collect values. A field
is not a Python storage slot by itself; it is a schema descriptor that tells the
graph how to write and read assertions.

`Identity(primary_key=True)` marks `user_id` as the **primary anchor** of
the entity. An entity can have multiple `Identity` fields — every `Identity`
participates in the entity reference and changes which coordinate is being
described. The simple one-field case shown here uses only the primary anchor.
See [Define a schema](schema.md#why-the-primary-anchor-matters) for the
multi-field identity pattern.

## Create a graph

Use `FactGraph.create(...)` as the normal constructor.

```python
fg = FactGraph.create(schema_classes=[User])
```

This compiles the schema and creates an empty in-memory graph. Later tutorials
add `path=...` for a workspace that can be saved and loaded.

`FactGraph.create(schema_classes=[...])` is the **high-level constructor**
— it calls `compile_schema_from_classes(schema_classes)` for you and stores
the resulting compiled IR inside the runtime. When you work at the lower
`Database` boundary directly, you compile once with
`compile_schema_from_classes(...)` and pass the IR as `schema_ir=` instead
(see [Database and durable views](database.md#define-a-schema-ir) for the
surface comparison).

## Write facts

Writes use an entity reference. Build one with `fg.read.ref(...)`, then write
field values through `fg.write`.

```python
alice = fg.read.ref(User, user_id="u-1")

fg.write.set(User.name, alice, "Alice")
fg.write.add(User.tags, alice, "engineer")
```

The reference is an opaque handle for "the user whose `user_id` is `u-1`".
`set` is for `single` fields. `add` is for `multi` fields. Both calls append
assertions to the graph ledger; they do not mutate a Python `User` object.

## Read a snapshot

Use `fg.read.get(...)` with the same identity values to read the current
snapshot.

```python
snap = fg.read.get(User, user_id="u-1")

print(snap.name)        # Alice
print(tuple(snap.tags)) # ('engineer',)
```

The returned snapshot is read-only. If the entity is not visible in the current
view, `fg.read.get(...)` returns `None`.

Think of the snapshot as the graph's answer to "what is currently known about
this identity?" It is not the source of truth itself; the append-only assertions
in the graph ledger are.

## Complete example

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.name, alice, "Alice")
fg.write.add(User.tags, alice, "engineer")

snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert tuple(snap.tags) == ("engineer",)
```

## Syntax checklist

- A schema is made from `Entity` classes.
- `Identity` fields locate entities.
- `Field` descriptors define values you can write.
- `FactGraph.create(...)` builds the graph.
- `fg.read.ref(...)` creates an entity handle for writes.
- `fg.write.set(...)` writes `single` fields.
- `fg.write.add(...)` writes `multi` fields.
- `fg.read.get(...)` reads the current snapshot.
