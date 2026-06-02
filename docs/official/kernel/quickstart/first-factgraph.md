# Your first FactGraph

This page builds the smallest useful graph: a schema, one entity coordinate,
two field writes, and one read. It uses only the in-memory SDK path so you can
see the core model before adding rules, workspaces, or persistence.

A `FactGraph` stores typed facts. The schema says what kinds of entities and
fields exist. Writes append assertions to the ledger. Reads resolve active
assertions into a read-only snapshot.

## Define a schema

A FactGraph starts from Python classes. Each class represents an entity type.
`Identity()` descriptors form the immutable identity bundle for an entity, and
`Field()` descriptors hold non-identity values about that entity.

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()
```

Every `Identity()` participates in the entity reference. Identity fields are not
ordinary editable fields; changing identity means deleting the old entity
coordinate and creating a new one. `Field()` descriptors are the values you
write through `fg.fields.*`.

## Create a graph

Use `FactGraph.create(...)` as the normal constructor.

```python
fg = FactGraph.create(schema_classes=[User])
```

This compiles the schema and creates an empty in-memory graph. Later tutorials
add `path=...` for a workspace that can be saved and loaded.

## Create an entity coordinate

Create the entity identity before writing fields:

```python
alice = fg.entities.create(User, user_id="u-1")
```

The returned value is an opaque `idref_v1` token for "the `User` whose
`user_id` is `u-1`". Treat it as a handle returned by the SDK; do not parse or
construct it yourself.

`fg.entities.ref(...)` returns the deterministic reference for an identity
coordinate and registers the bundle in the SDK shadow store, without writing
identity Claims to the ledger; it works for both already-seen and new
coordinates. For new application code, `fg.entities.create(...)` is the
explicit entity-lifecycle entry point (it writes Identity Claims and a
`<EntityType>:exists` Claim atomically).

## Write facts

Write field values through `fg.fields.*`:

```python
fg.fields.set(User.name, alice, "Alice")
fg.fields.add(User.tags, alice, "engineer")
```

`set` is for single-value fields. `add` appends a value to a multi-value field.
Both calls append assertions to the graph ledger; they do not mutate a Python
`User` object.

## Read a snapshot

Use `fg.entities.get(...)` with the same identity values to read the current
snapshot.

```python
snap = fg.entities.get(User, user_id="u-1")

print(snap.name)        # Alice
print(tuple(snap.tags)) # ('engineer',)
```

The returned snapshot is read-only. If the entity is not visible in the current
view, `fg.entities.get(...)` returns `None`.

## Complete example

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()


fg = FactGraph.create(schema_classes=[User])

alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.name, alice, "Alice")
fg.fields.add(User.tags, alice, "engineer")

snap = fg.entities.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert tuple(snap.tags) == ("engineer",)
```

## Syntax checklist

- A schema is made from `Entity` classes.
- `Identity()` fields locate entities.
- `Field()` descriptors define values you can write.
- `FactGraph.create(...)` builds the graph.
- `fg.entities.create(...)` creates an entity coordinate.
- `fg.entities.ref(...)` returns a deterministic reference for an identity
  coordinate and registers the bundle in the SDK shadow store (no ledger
  writes).
- `fg.fields.set(...)` writes a single-value field.
- `fg.fields.add(...)` writes a multi-value field.
- `fg.entities.get(...)` reads the current snapshot.
- For schema-level metadata, see [Define a schema](schema.md#entity-metadata-class-meta) (`class Meta:` with version/description/tags).
- For relationship (edge) declarations, see [Relationship descriptors](schema.md#relationship-descriptors).
- For the supported engine list, see [Configure inference semantics](semantics.md#supported-engines) (native / souffle / problog / pyreason).
