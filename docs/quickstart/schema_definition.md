# Schema definition: declaring and evolving entity types

A schema declares the entity types your FactGraph holds. A Database head is
anchored to one `schema_digest` (the canonical hash of the compiled schema) at
any point in history. Successful additive transitions advance the head to a new
digest; older schema objects remain content-addressed history. The runtime
supports adding new entity types and non-identity fields through the
`fg.schema.*` namespace; destructive changes are not supported.

## 1. Declaring an entity class

A schema entry is a Python class that subclasses `Entity` and declares fields with the `Identity()` and `Field()` descriptors. Cardinality is inferred from the field's type annotation, not from a keyword argument.

### 1.1 Minimal example

```python
from factgraph.sdk import Entity, Identity, Field

class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()
```

`User` has a compound identity (`user_id`, `locale`), one single-cardinality field (`name`), and one multi-cardinality field (`tag`).

### 1.2 Identity vs Field

| | `Identity()` | `Field()` |
|---|---|---|
| Purpose | builds the entity's stable coordinate (`idref_v1` reference) | carries mutable values |
| Mutability | immutable once set | can be set, added, retracted |
| Retractable individually | no (must use `fg.entities.delete` for the whole entity) | yes via `fg.fields.retract` / `fg.assertions.retract` |
| Multiple per entity | yes — together they form a compound identity | yes |

Every `Entity` subclass must declare at least one `Identity()` field. Identity immutability is also enforced at runtime: writing to an `Identity()` descriptor via `fg.fields.set` / `fg.fields.add` raises `SDKStoreError(code="INV_7C_IDENTITY_PROTECTED")`. To replace an identity bundle, delete the entity with `fg.entities.delete(...)` and create a new one.

### 1.3 Cardinality

Cardinality is taken from the type annotation. There is no `cardinality=` kwarg; `Field(cardinality="multi")` raises `SDKSchemaError`.

| Annotation shape | Cardinality |
|---|---|
| any scalar (see §1.4) | single |
| `list[T]`, `set[T]`, `frozenset[T]`, `tuple[T, ...]` | multi |

A missing single-cardinality field reads back as `None`; a missing multi-cardinality field reads back as `()`.

`fg.fields.get` and entity snapshots use the same canonical order for multi-cardinality values.

The four multi-cardinality shapes are **interchangeable cardinality signals** — they do **not** impose their container's semantics. A multi-cardinality cell holds a *set of distinct values*: each `(field, value)` is one content-addressed claim, so adding the same value twice is idempotent (no duplicates are stored). Reads always return a `tuple` of the distinct values regardless of which shape you annotated (`fg.fields.get` returns a `tuple`; see [`three_layer_api.md`](three_layer_api.md) §3). Choosing `set[T]` vs `list[T]` vs `frozenset[T]` vs `tuple[T, ...]` is a typing-ergonomics choice with no runtime difference — the declared container type is not reconstructed on read.

### 1.4 Scalar types

Each scalar annotation maps to a storage domain that the compiled schema IR records on the predicate. For multi-cardinality fields, the inner `T` in `list[T]` / `set[T]` / `frozenset[T]` / `tuple[T, ...]` follows the same table.

| Annotation | Storage domain | Notes |
|---|---|---|
| `str` | `string` | Required when using `pattern=r"..."`. |
| `int` | `int` | |
| `bool` | `bool` | |
| `bytes` | `bytes` | |
| `float` | `float64` | Float values cannot appear in `Literal[...]` enums. |
| `uuid.UUID` | `uuid` | |
| `datetime.datetime` | `time` | |
| Another `Entity` subclass (e.g., `team: Team = Field()`) | `entity_ref` | Forward-string annotations like `"Team"` resolve the same way. |

### 1.5 Value constraints

`Identity()` and `Field()` accept only two keyword arguments: `pattern=` (regex constraint, valid only for string-typed fields) and `repr=` (explain-layer representation template, validated at class definition time and stored in Schema IR as presentation metadata; syntax in §1.8). Passing other kwargs (`description=`, `primary_key=`, `default=`, `cardinality=`, etc.) raises `SDKSchemaError` at class definition time.

Enum-style constraints use `Literal[...]` in the annotation:

```python
class User(Entity):
    user_id: str = Identity()
    role: Literal["admin", "member", "viewer"] = Field()
    handle: str = Field(pattern=r"^[a-z][a-z0-9_]{2,31}$")
```

This descriptor-based declaration style is referred to as **Form I** in the source.

### 1.6 Not supported in Form I

These annotation shapes raise `SDKSchemaError` at class definition time:

| Annotation | Why |
|---|---|
| `Optional[T]`, `Union[T, U]`, `T \| None` | Form I has no optional/union shape. Unset reads already return `None` (single) or `()` (multi); no explicit nullable wrapper is needed. |
| `dict[K, V]` | Dictionaries are not a Form I storage shape. |
| Nested collections (`list[list[T]]`, `set[list[T]]`, etc.) | Multi-cardinality fields must hold scalar element types. |

### 1.7 Entity metadata

Each `Entity` subclass may declare an optional inner `class Meta:` block to attach schema-level metadata. It is preserved in the compiled schema and read by `fg.schema.*` and `fg.audit.*` consumers.

```python
class EmploymentEvent(Entity):
    class Meta:
        version = "v1"
        tags = ["employment", "event"]

    event_id: str = Identity()
    company: str = Field()
```

Only three keys are accepted: `version`, `tags`, `repr`. Unsupported keys raise `SDKSchemaError` at class definition time. `Meta.repr` is the entity-label template — its syntax is covered in §1.8 below.

### 1.8 `repr` templates — explain-layer rendering

`repr=` on `Field()` / `Identity()` and `repr` inside `class Meta` are **presentation templates** for the explain layer. They are validated at class-definition time, stored in Schema IR as metadata, and **excluded from `schema_digest`** (presentation only — adding or editing a template keeps schema identity stable, §5.6). They feed `row.explain()`: the atom and conclusion text in [`evaluate_and_evidence.md`](evaluate_and_evidence.md) §4 is rendered from these templates.

```python
class User(Entity):
    user_id: str = Identity(repr="%ENT has id %FLD")
    region: str = Field(repr="%ENT is in region %FLD")
    age: int = Field(repr="%ENT is %FLD years old")

    class Meta:
        repr = "%CLS %user_id"           # entity label, e.g. "User u-1"
```

**Placeholders** are validated per context; unknown placeholders are rejected at class-definition time:

| Placeholder | Meaning | `Field.repr` / `Identity.repr` | `Meta.repr` |
|---|---|---|---|
| `%CLS` | entity class name (e.g. `User`) | ✓ | ✓ |
| `%ENT` | the entity, rendered via its `Meta.repr` label | ✓ | ✗ |
| `%FLD` | the current field's value | ✓ (this field only) | ✗ |
| `%<identity_field>` | a named identity field's value (e.g. `%user_id`) | ✗ | ✓ (identity fields only) |

- A `Field` / `Identity` template describes one fact atom: `%ENT` resolves to the subject's entity label (its `Meta.repr`), `%FLD` to that field's value. Example render: `User u-1 is in region us`.
- A `Meta.repr` template is the entity **label** and may reference only `%CLS` + identity-field placeholders (the identity-only constraint).
- A field whose name collides with a reserved token (`CLS` / `ENT` / `FLD`) is rejected when a `repr` template is in use.

## 2. Compiling a schema and using it with FactGraph

A schema lives as Python classes during declaration and as a compiled JSON-like IR (the "schema IR") at runtime. `FactGraph.create(...)` and `FactGraph.load_workspace(...)` accept `schema_classes=[...]` and handle compilation internally.

```python
fg = FactGraph.create(path="path/to/workspace", schema_classes=[User])
```

If you need the compiled IR directly (for export, hashing, or preflight inspection), call:

```python
from factgraph.sdk import (
    MetaKeyPolicy,
    compile_schema_from_classes,
    schema_preflight_from_classes,
)

schema_ir = compile_schema_from_classes([User])     # compile and return the IR
schema_preflight_from_classes([User])               # validate and return a preflight report

# Advanced Database authoring: declare schema-global metadata policy.
audit_schema_ir = compile_schema_from_classes(
    [User],
    meta_keys={
        "trace_id": MetaKeyPolicy(
            reader_class="audit",
            load_policy="lazy",
            storage_scope="tx_liftable",
        )
    },
)
```

`meta_keys=` is a schema-global compile input, not a per-entity `class Meta`
setting. Its five independent properties are `reader_class`,
`premise_eligible`, `load_policy`, `storage_scope`, and `query_indexed`.
Properties equal to their defaults are omitted from canonical IR; declaring a
non-default policy changes schema identity. The current `FactGraph.create` and
`FactGraph.attach` convenience constructors compile their class list without a
`meta_keys=` argument, so use the explicit compile + `Database` surface when
authoring these policies.

The `schema_digest` is the SHA-256 of the canonicalized schema identity
(sorted-key JSON, UTF-8). It excludes volatile top-level `generated_at`
metadata, so recompiling the same `Entity` classes at a later time keeps the
same digest. Schema `repr` templates are presentation metadata and do not
participate in the identity digest. Structural schema fields, including
versions, remain identity-bearing in this release. Reopening validates the
supplied classes against the current digest in `db/assertions.db` and the
matching content-addressed schema object. A mismatch fails closed (see
[load_and_save.md](load_and_save.md)).

## 3. Runtime schema mutation

After a FactGraph is created, the `fg.schema.*` namespace supports adding new entity types and non-identity fields to existing entities. Three methods cover all flows.

### 3.1 register / extend / apply

| Method | Adds | If entity_type is already registered | If entity_type is not registered |
|---|---|---|---|
| `fg.schema.register(EntityCls)` | a new entity type | `SchemaConflictError` (`code="SCHEMA_CONFLICT"`) | OK |
| `fg.schema.extend(EntityCls)` | non-identity fields to an existing entity | OK (additive only; see §4) | `SchemaNotFoundError` (`code="SCHEMA_NOT_FOUND"`) |
| `fg.schema.apply(EntityCls)` | safe-diff helper | routes to `extend` | routes to `register` |

Use `apply` when you don't want to track which is which; use `register` or `extend` when you want the wrong-direction error to surface.

For `extend`, the `EntityCls` you pass is a **new version of the same-named class** with additional `Field()` declarations added; identity fields and existing fields must stay unchanged. See §3.4 for the concrete pattern.

### 3.2 SchemaAddResult

All three methods return a `SchemaAddResult`:

```python
@dataclass(frozen=True)
class SchemaAddResult:
    old_digest: str
    new_digest: str
    added_entities: list[str]
    added_fields: list[str]
```

`added_entities` lists new entity type names; `added_fields` lists newly added `(entity_type, field_name)` pairs.

### 3.3 Idempotency

Re-applying an equivalent class is a no-op: `old_digest == new_digest`, `added_entities == []`, `added_fields == []`. No ledger state changes.

### 3.4 Extended fields have no backfill

When `extend` adds a new `Field()` to an existing entity, pre-existing entities are **not** rewritten. Reading the new field on an entity that existed before the extend returns `None` (single-cardinality) or `()` (multi-cardinality), the same as any unset field. Previously written facts on other fields remain readable unchanged.

### 3.5 Superseded class objects

`extend` takes a **new version of the same-named entity class** that adds non-identity `Field()` declarations. The class object you pass in becomes the active class for the entity type on the runtime; any **previously-registered** class object for that entity type is now superseded.

```python
class User(Entity):
    user_id: str = Identity()
    name: str = Field()

fg = FactGraph.create(path=workspace_path, schema_classes=[User])
old_ref = User  # capture a reference to the pre-extend class

class User(Entity):              # redeclare with the same name + new fields
    user_id: str = Identity()
    name: str = Field()
    email: str = Field()         # new
    tags: list[str] = Field()    # new

result = fg.schema.extend(User)
# result.added_fields lists the two new field identifiers;
# User (the post-extend class) is now active;
# old_ref is superseded.
```

Reads or writes that go through the superseded class raise:

```text
SDKStoreError: schema declaration was superseded; use the post-add class object
```

In normal use the `User` name is rebound to the new class by Python's import or local re-declaration, so the old class object is only reachable through code that explicitly captured a reference before `extend`. Re-import the module or rebind the name to clear the reference.

### 3.6 Database history timing

`fg.schema.register / extend / apply` first apply the SDK's additive-only
policy. A successful change writes the canonical new schema object and commits
one isolated `schema_change` transaction containing the old and new digests.
The current digest and transaction head advance together; failed and no-op
changes do not advance either one. `fg.save_workspace()` is unrelated: it only
touches lifecycle metadata, and the v0.3 workspace manifest contains no schema
digest.

## 4. Schema mutation is additive-only (current scope)

Destructive operations (`delete`, `update`, `migrate`, `deprecate`) are not part of the current `fg.schema.*` surface. If you need a non-additive change today — removing a field, changing identity, retyping, or anything that retracts schema state — create a new workspace with the new schema and re-ingest. The core Database has a policy-free schema-transition mechanism for internal orchestration, but its raw transition DTO is intentionally not exported from the public SDK.

This is the **current mode**. Broader schema evolution semantics (destructive operations, in-place migration, digest evolution) are an open design question. The full rejection taxonomy and the design space sit in [`workflow/design/design-points/active/schema-mutation-additive-only.zh.md`](../../workflow/design/design-points/active/schema-mutation-additive-only.zh.md).

## 5. Reference

### 5.1 Descriptors

```python
class Entity(metaclass=EntityMeta):
    """Subclass to declare an entity type. Must have at least one Identity() field."""

class Identity(_DataMember):
    def __init__(self, *, pattern: str | None = None, repr: str | None = None): ...

class Field(_DataMember):
    def __init__(self, *, pattern: str | None = None, repr: str | None = None): ...
```

`pattern=` is valid only for string-typed fields; passing it to a non-string field raises `SDKSchemaError` at class definition time.

### 5.2 fg.schema.* methods

```python
fg.schema.register(entity_cls: type[Entity]) -> SchemaAddResult
fg.schema.extend(entity_cls: type[Entity]) -> SchemaAddResult
fg.schema.apply(entity_cls: type[Entity]) -> SchemaAddResult
```

### 5.3 Compile helpers

```python
compile_schema_from_classes(
    classes: list[type[Entity]],
    *,
    meta_keys: Mapping[str, MetaKeyPolicy] | None = None,
) -> dict
schema_preflight_from_classes(
    classes: list[type[Entity]],
    *,
    meta_keys: Mapping[str, MetaKeyPolicy] | None = None,
) -> dict
```

### 5.4 SchemaAddResult

```python
@dataclass(frozen=True)
class SchemaAddResult:
    old_digest: str                  # schema_digest before the mutation
    new_digest: str                  # schema_digest after; equal to old_digest if no-op
    added_entities: list[str]
    added_fields: list[str]
```

### 5.5 Errors

| Raised by | Type | Code | Message template |
|---|---|---|---|
| `Identity(...)` / `Field(...)` with unknown kwarg | `SDKSchemaError` | — | `Identity() only accepts pattern= and repr= in Form I; ...` |
| `Field(pattern="...")` on non-string field | `SDKSchemaError` | — | `pattern= is only supported for string-typed Identity/Field members` |
| `Field(pattern="...")` with invalid regex | `SDKSchemaError` | — | `pattern must be a valid regular expression: ...` |
| `Entity` subclass with no `Identity()` | `SDKSchemaError` | — | (raised by `EntityMeta`) |
| `fg.schema.register(EntityCls)` when registered | `SchemaConflictError` | `SCHEMA_CONFLICT` | `entity_type already registered: {entity_type}` |
| `fg.schema.extend(EntityCls)` when not registered | `SchemaNotFoundError` | `SCHEMA_NOT_FOUND` | `entity_type not registered: {entity_type}` |
| any non-additive change | `SchemaNonAdditiveError` | `SCHEMA_NON_ADDITIVE` | varies by violation category; see the design-point linked from §4 for the full taxonomy |
| using superseded class object after `extend` | `SDKStoreError` | — | `schema declaration was superseded; use the post-add class object` |

All schema errors inherit from `SDKStoreError`.

### 5.6 schema_digest

`schema_digest(schema_ir)` returns `"sha256:<hex>"`. The identity canonicalization sorts dict keys, emits compact UTF-8 JSON (`json.dumps(..., sort_keys=True, separators=(",", ":"))`), excludes only top-level `generated_at`, then hashes the bytes with SHA-256.
