# Identity, Primary Key, and Coordinate Semantics

Status: working / non-authoritative
Authority: Research note. Current implementation truth remains in `src/kernel/sdk/`, `src/kernel/application/`, and their module docs. User-facing conclusions must be migrated before they become release documentation.

## Question

What is the actual role of `Identity(primary_key=True)`?

The key confusion is that `primary_key=True` sounds like a database primary key, where only that field determines row identity. FactPy's current implementation does not work that way.

## Current Behavior

For an SDK entity such as:

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="en")
    name: str = Field(cardinality="single")
```

all `Identity` fields participate in the entity reference coordinate. In current code, both `user_id` and `locale` contribute to the encoded `idref_v1` value. Therefore:

```python
fg.ref(User, user_id="u1", locale="en")
fg.ref(User, user_id="u1", locale="zh")
```

refer to different entity coordinates.

The `primary_key=True` marker does not exclude secondary `Identity()` fields from identity encoding. It marks which identity fields act as primary logical join anchors in authoring and rule-lowering contexts.

## Practical Distinction

`Identity` and `Field` are different along two axes:

| Construct | Participates in entity ref? | Mutable as ordinary fact content? | Rule/authoring role |
|---|---:|---:|---|
| `Identity(primary_key=True)` | Yes | No | Main logical join anchor |
| `Identity()` | Yes | No | Coordinate dimension; not the main cross-coordinate anchor |
| `Field(...)` | No | Yes | Fact content under an entity coordinate |

So the current mental model is:

```text
(all Identity fields) -> idref_v1 entity coordinate
primary Identity fields -> rule-level logical anchors
Field values -> mutable facts attached to that coordinate
```

## Source-Grounded Notes

- `EntityMeta` splits class attributes into `identity_fields` and `fields`, and requires at least one `Identity(primary_key=True)`.
- `SDKStore.ref(...)` accepts only identity field names, fills identity defaults, and encodes all identity fields into `idref_v1`.
- Application schema runtime materializes all identity fields and rejects unsupported identity domains such as `entity_ref`.
- Authoring rule lowering treats primary and non-primary identity fields differently: primary identity fields are implicit from entity bindings, while non-primary identity fields must be explicit where needed.
- Cross-coordinate attribute comparisons are constrained to primary-key identity fields.

## Historical Context

Historical design notes described Identity as n-ary coordinate semantics, not a single-column database key. The intended shape was closer to:

```text
(user_id, work_id, lang) -> address
```

Current storage uses a surrogate entity ref:

```text
(user_id, work_id, lang) -> idref_v1
idref_v1 -> field facts
```

This preserves n-ary identity semantics while giving the runtime a stable entity reference token. The `primary_key=True` marker was later hardened into a class-definition requirement so every entity has at least one logical anchor.

## User-Facing Explanation

Recommended documentation framing:

> `Identity` fields define the coordinate of an entity. All identity fields participate in the generated entity reference. Mark one or more identity fields as `primary_key=True` to identify the logical anchor used by rules and cross-coordinate joins. Ordinary `Field(...)` values do not participate in entity identity; they are facts attached to an entity coordinate.

Avoid saying:

> The primary key is the only field that defines the entity.

That is false for current code.

## Documentation Actions

- Update SDK docs to state that all `Identity` fields participate in entity refs.
- Explain `primary_key=True` as a logical anchor, not a database-style sole identity determinant.
- Add a small example showing same primary / different secondary identity values produce distinct refs.
- Keep the lower-level rule-authoring implications out of beginner quickstarts unless the guide introduces derivations.

## Open Follow-Ups

- Decide whether the public term `primary_key` should remain documented as-is or be explained with an alias such as "logical anchor".
- Add or verify tests for rule lowering with primary vs non-primary identity fields so the authoring semantics are locked as strongly as the SDK ref semantics.
- Review current `EntitySnapshot.identity` hydration behavior when identity defaults are applied, because snapshot identity can reflect only the selector-provided values rather than the fully recovered coordinate.
