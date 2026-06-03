# Schema definition: declaring and evolving entity types

A schema declares the entity types your FactGraph holds. Each workspace is anchored to one `schema_digest` (the canonical hash of the compiled schema) at create time. The runtime supports additive evolution — adding new entity types and adding non-identity fields to existing ones — through the `fg.schema.*` namespace; destructive changes are not supported.

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

`Identity()` and `Field()` accept only two keyword arguments: `description=` (human-readable doc string) and `pattern=` (regex constraint, valid only for string-typed fields). Passing other kwargs (`primary_key=`, `default=`, `cardinality=`, etc.) raises `SDKSchemaError` at class definition time.

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
    """Used as description fallback only when Meta.description is absent."""

    class Meta:
        version = "v1"
        description = "Employment event"
        tags = ["employment", "event"]

    event_id: str = Identity()
    company: str = Field()
```

Only three keys are accepted: `version`, `description`, `tags`. Unsupported keys raise `SDKSchemaError` at class definition time. Detailed semantics of each Meta field is covered in the next chapter.

## 2. Compiling a schema and using it with FactGraph

A schema lives as Python classes during declaration and as a compiled JSON-like IR (the "schema IR") at runtime. `FactGraph.create(...)` and `FactGraph.load_workspace(...)` accept `schema_classes=[...]` and handle compilation internally.

```python
fg = FactGraph.create(path="path/to/workspace", schema_classes=[User])
```

If you need the compiled IR directly (for export, hashing, or preflight inspection), call:

```python
from factgraph.sdk import compile_schema_from_classes, schema_preflight_from_classes

schema_ir = compile_schema_from_classes([User])     # compile and return the IR
schema_preflight_from_classes([User])               # validate only; does not return IR
```

The `schema_digest` is the SHA-256 of the canonicalized schema IR (sorted-key JSON, UTF-8). Two workspaces created from the same set of `Entity` classes share the same digest; reopening with a different class set raises a mismatch error (see [load_and_save.md](load_and_save.md#65-schema-strong-correspondence)).

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

### 3.6 Workspace persistence timing

`fg.schema.register / extend / apply` update the in-memory schema state and the ledger's `schema_digest` metadata immediately. The workspace manifest digest is **not** rewritten until you call `fg.save_workspace()`. This means a runtime that has mutated its schema but not saved will load with the post-mutation schema digest from the ledger, but the on-disk manifest may still show the pre-mutation digest until the next save.

## 4. Schema mutation is additive-only (current scope)

Destructive operations (`delete`, `update`, `migrate`, `deprecate`) are not part of the current `fg.schema.*` surface. If you need a non-additive change today — removing a field, changing identity, retyping, or anything that retracts schema state — create a new workspace with the new schema and re-ingest.

This is the **current mode**. Broader schema evolution semantics (destructive operations, in-place migration, digest evolution) are an open design question.

## 5. Reference

### 5.1 Descriptors

```python
class Entity(metaclass=EntityMeta):
    """Subclass to declare an entity type. Must have at least one Identity() field."""

class Identity(_DataMember):
    def __init__(self, *, description: str | None = None, pattern: str | None = None): ...

class Field(_DataMember):
    def __init__(self, *, description: str | None = None, pattern: str | None = None): ...
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
compile_schema_from_classes(classes: list[type[Entity]]) -> dict       # returns schema IR
schema_preflight_from_classes(classes: list[type[Entity]]) -> None     # validate only
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
| `Identity(...)` / `Field(...)` with unknown kwarg | `SDKSchemaError` | — | `Identity() only accepts description= and pattern= in Form I; ...` |
| `Field(pattern="...")` on non-string field | `SDKSchemaError` | — | `pattern= is only supported for string-typed Identity/Field members` |
| `Field(pattern="...")` with invalid regex | `SDKSchemaError` | — | `pattern must be a valid regular expression: ...` |
| `Entity` subclass with no `Identity()` | `SDKSchemaError` | — | (raised by `EntityMeta`) |
| `fg.schema.register(EntityCls)` when registered | `SchemaConflictError` | `SCHEMA_CONFLICT` | `entity_type already registered: {entity_type}` |
| `fg.schema.extend(EntityCls)` when not registered | `SchemaNotFoundError` | `SCHEMA_NOT_FOUND` | `entity_type not registered: {entity_type}` |
| any non-additive change | `SchemaNonAdditiveError` | `SCHEMA_NON_ADDITIVE` | varies by violation category; see the design-point linked from §4 for the full taxonomy |
| using superseded class object after `extend` | `SDKStoreError` | — | `schema declaration was superseded; use the post-add class object` |

All schema errors inherit from `SDKStoreError`.

### 5.6 schema_digest

`schema_digest(schema_ir)` returns `"sha256:<hex>"`. The canonicalization sorts dict keys and emits compact UTF-8 JSON (`json.dumps(..., sort_keys=True, separators=(",", ":"))`), then hashes the bytes with SHA-256.
