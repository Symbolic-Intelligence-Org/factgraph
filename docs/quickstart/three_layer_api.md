# Three-layer API: entities, fields, assertions

The SDK exposes three namespaces — `fg.entities`, `fg.fields`, and `fg.assertions` — that are not just stylistic groupings. They are a deliberate role separation by **navigation key**: each layer accepts a different kind of identifier as its input, and using the wrong key raises an explicit error rather than silently doing the wrong thing.

This chapter explains the layer model, what each layer's methods do, and when to drop down a layer. It complements [`schema_definition.md`](schema_definition.md) (which declares the *types*) and [`data_model.md`](data_model.md) (which describes the *storage records*).

## 1. Why three layers

The model is a triangle:

- **Entity** answers *"what thing is this?"* — a coordinate identified by its identity bundle.
- **Field** answers *"what content does it have at one cell?"* — a `(Field descriptor, entity ref)` cell, plus a value when writing.
- **Assertion** answers *"who wrote this particular fact, and when?"* — one individual write record, identified by its content-addressed `asrt_id`.

Each layer's primary API takes its own navigation key:

| Layer | Namespace | Navigation key | Typical use |
|---|---|---|---|
| 1 | `fg.entities.*` | `EntityClass + identity_kwargs`, or a managed `e_ref` string | entity lifecycle + snapshot reads |
| 2 | `fg.fields.*` | `Field descriptor + e_ref` (+ value, when writing) | field-cell mutations + current-value reads |
| 3 | `fg.assertions.*` | `asrt_id` string (or iterable) | per-write introspection + targeted retract |

Errors are part of the design. Passing an `asrt_id` to `fg.entities.get(...)` does not implicitly route through `fg.assertions.by_id(...)` — it raises an error telling you to use the correct layer. The same goes for passing a Field descriptor to `fg.entities.*` or an `EntityClass` to `fg.fields.*`. The rationale is in [ADR-API §4.1.1](../../workflow/design/decisions/active/2026-05-29_q-api-namespace-decision.md): each layer's mental model is distinct enough that silent fallback would mask programmer intent.

## 2. Layer 1 — Entities (`fg.entities.*`)

Layer 1 owns entity lifecycle and snapshot reads.

### 2.1 Navigation key — two forms

```python
# Form 1: EntityClass + identity_kwargs
fg.entities.get(User, user_id="u-1", locale="en")
fg.entities.create(User, user_id="u-1", locale="en")

# Form 2: managed e_ref string (returned from a prior create/ref call)
alice = fg.entities.ref(User, user_id="u-1", locale="en")  # alice is a string
fg.entities.delete(alice)
```

Form 1 is for first-time lookup or creation; Form 2 is for following operations that already have a handle.

### 2.2 Lifecycle methods

| Method | What it does |
|---|---|
| `create(EntityCls, *, meta=None, **identity)` | Eagerly emits the complete Identity Claim bundle + `:exists` Claim; returns the new `e_ref` string |
| `delete(e_ref_or_cls, *, meta=None, **identity)` | Whole-entity revoke. Two forms: `delete(e_ref)` (string passed back from `ref`/`create`) or `delete(EntityCls, **identity)` (rebuilds the e_ref from the identity bundle) |
| `edit(EntityCls, **identity)` | Opens an `EntityEditor` context manager for staged multi-field writes against one entity |

### 2.3 Read methods

| Method | What it returns |
|---|---|
| `get(EntityCls, **identity)` | The full snapshot for one full identity, or `None` |
| `where(EntityCls, *, limit=None, _meta=None, **field_filters)` | Snapshots matching equality filters on entity/field values |
| `match(EntityCls, template, *, limit=None, **port_constraints)` | Snapshots selected by an application `Rule` or AND-only `RuleExpr` |
| `ref(EntityCls, **identity)` | A managed `e_ref` string; does not write to the ledger |
| `exists(EntityCls, **identity)` | Boolean visibility check |

### 2.4 What Layer 1 rejects

Passing the wrong navigation key raises immediately, before any ledger work:

```text
SDKStoreError: fg.entities.get() requires an Entity subclass + identity_kwargs
(Layer 1 navigation key); got str — pass asrt_id to fg.assertions.by_id(asrt_id)
or fg.assertions.retract(asrt_id) instead. See ADR-API §4.1.1.
```

```text
SDKStoreError: fg.entities.get() requires an Entity subclass + identity_kwargs
(Layer 1 navigation key); got Field descriptor — pass Field + e_ref + value to
fg.fields.* (Layer 2) instead. See ADR-API §4.1.1.
```

## 3. Layer 2 — Fields (`fg.fields.*`)

Layer 2 owns field-cell mutations. Its navigation key is a `Field` descriptor plus an `e_ref`, plus a value when writing.

### 3.1 Navigation key

```python
fg.fields.set(User.name, alice, "Alice")              # Field + e_ref + value
fg.fields.get(User.tags, alice)                       # Field + e_ref (no value)
```

`alice` here is a managed `e_ref` string (Layer 1 bridge — see §5.1).

### 3.2 Write methods

| Method | Single cardinality | Multi cardinality |
|---|---|---|
| `set(field, ref, value, *, meta=None)` | append a new value, returns `asrt_id` | rejected (`CardinalityError`) |
| `add(field, ref, value, *, meta=None)` | rejected (`CardinalityError`) | append one element, returns `asrt_id` |
| `retract(field, ref, value, *, meta=None)` | revoke the unique active `(field, ref, value)` assertion | revoke the unique active `(field, ref, value)` assertion |
| `delete(field, ref, *, meta=None)` | revoke every active assertion at the `(field, ref)` cell | revoke every active assertion at the `(field, ref)` cell |
| `get(field, ref)` | current value or `None` | current values as a tuple, possibly `()` |

The cardinality check fires at dispatch time. `fg.fields.add(User.name, ref, "Alice")` on a single-cardinality `name` field raises before any ledger work:

```text
CardinalityError: ... (code=FIELD_CARDINALITY_MISMATCH)
```

`retract` rejects when the `(field, ref, value)` triple matches zero or more than one active assertion — you must disambiguate by passing an `asrt_id` to `fg.assertions.retract(...)` (Layer 3) instead.

### 3.3 What Layer 2 rejects

```text
SDKStoreError: fg.fields.set() requires a Field descriptor (Layer 2 navigation
key); got str/asrt_id — pass assertion ids to fg.assertions.* (Layer 3)
instead. See ADR-API §4.1.1.
```

```text
SDKStoreError: fg.fields.set() requires a Field descriptor (Layer 2 navigation
key); got Entity class — use fg.entities.* (Layer 1) instead. See ADR-API §4.1.1.
```

There is also a special guard for passing an `Identity` descriptor to a value-write method:

```text
SDKStoreError: fg.fields.set() does not accept Identity descriptors for value
writes; Identity Claims are immutable anchors per INV-7c. Use fg.entities.delete
+ fg.entities.create for identity-bundle changes. See ADR-API §4.1.1.
```

## 4. Layer 3 — Assertions (`fg.assertions.*`)

Layer 3 owns per-write introspection and targeted retract. Its navigation key is an `asrt_id` string.

### 4.1 Lookup

| Method | What it returns |
|---|---|
| `by_id(asrt_id)` | `AssertionRecord \| None` — one record by exact id |
| `by_ids(asrt_ids, *, strict=False)` | `AssertionRecordSet` — multiple records; missing ids skipped unless `strict=True` |
| `active` | `AssertionRecordSet` of every non-revoked record in the ledger |
| `all` | `AssertionRecordSet` of every record (active and revoked) |

### 4.2 Filter

| Method | What it filters by |
|---|---|
| `where(*, field=None, e_ref=None, value=None, value_tag=None, _meta=None)` | active records matching the canonical Layer-3 criteria |
| `field(Field)` | every record (active and history) for one schema field; returns an `AssertionView` with `.active_records` and `.history_records` |

The `_meta` filter accepts a dict and matches assertions whose meta values agree; flat `source=` / `trace_id=` etc. kwargs are not accepted.

### 4.3 Retract

`retract(asrt_id, *, meta=None)` is the only public assertion-id-level mutation. It returns the revoker's `asrt_id`.

Two guards apply before the revoke is appended:

```text
SDKStoreError (code=INV_7C_IDENTITY_PROTECTED):
Identity Claim asrt:... is immutable per INV-7c.
Identity Claims can only be:
  (a) created via fg.entities.create(EntityCls, **identity_kwargs);
  (b) removed as part of fg.entities.delete(e_ref) (atomic full-entity revoke).
To modify the identity bundle of an entity, delete the old entity and create a
new one with the new identity values (Identity is immutable per INV-7a).
See ADR-IC §4.1.
```

```text
SDKStoreError (code=EXISTENCE_CLAIM_TRANSITIONAL_GUARD):
<EntityType>:exists Claim asrt:... cannot be retracted independently.
The :exists Claim is co-emitted atomically with Identity Claims and can only be
removed via fg.entities.delete(e_ref) (atomic full-entity revoke).
This guard is transitional — Step 2+ may remove :exists emission entirely
(see ADR-IC §4.4).
```

### 4.4 What Layer 3 rejects

```text
SDKStoreError: fg.assertions.where(field=...) expects sdk.Field descriptor;
pass assertion ids to by_id/by_ids or use fg.entities/fg.fields for other
navigation keys. See ADR-API §4.1.1.
```

`fg.assertions.retract(...)` rejects any input that is not a non-empty `asrt_id` string:

```text
SDKStoreError: fg.assertions.retract(asrt_id) expects non-empty string
(Layer 3); use fg.entities.delete(...) for entity-level delete.
See ADR-API §4.1.1.
```

### 4.5 Returned types

Layer 3 reads return `AssertionRecord` (one record), `AssertionRecordSet` (an iterable record bundle with `.where(...)` / `.at(t)` / `.by_id(...)` chainable), and `AssertionView` (a field-scoped view exposing `.active_records` / `.history_records`). All three are read-only objects; the only mutation on Layer 3 is `retract`.

## 5. Crossing layers

The three layers are connected by two bridge tokens.

### 5.1 The `e_ref` bridge — Layer 1 → Layer 2 (and 3)

`fg.entities.ref(EntityCls, **identity)` and `fg.entities.create(EntityCls, **identity)` both return a managed `e_ref` string. That string is what Layer 2's `Field` writes take as their second positional argument:

```python
alice = fg.entities.create(User, user_id="u-1")           # Layer 1 → e_ref
fg.fields.set(User.name, alice, "Alice")                  # Layer 2 consumes e_ref
fg.assertions.where(field=User.name, e_ref=alice)         # Layer 3 also consumes e_ref
```

The string is opaque — it's a content-derived hash (`idref_v1:<EntityType>:<digest>`), not a free-form id you should parse or construct yourself.

### 5.2 The `asrt_id` bridge — Layer 2 → Layer 3

Every Layer 2 write returns the `asrt_id` of the assertion it appended:

```python
name_asrt = fg.fields.set(User.name, alice, "Alice")      # returns str: asrt_id
# ... later, to revoke just this specific write:
fg.assertions.retract(name_asrt, meta={"source": "fix-001"})
```

This bridge is how you target one specific historical write without touching anything else.

### 5.3 Three ways to remove data — choose the layer

When you want to "remove" something, the layer matches the granularity:

| You want to remove | Use | Effect |
|---|---|---|
| The whole entity (all its claims) | `fg.entities.delete(e_ref)` | atomic revoke of every Identity Claim + `:exists` Claim + every Field Claim for that `e_ref` |
| Every active value at one field-cell | `fg.fields.delete(field, e_ref)` | sequential revoke of every active assertion at `(field, e_ref)`; fail-fast on first error |
| One specific historical value at a cell | `fg.fields.retract(field, e_ref, value)` | revoke the unique active `(field, e_ref, value)` assertion (raises if zero or more than one match) |
| One specific assertion id | `fg.assertions.retract(asrt_id)` | revoke exactly the named assertion; subject to INV-7c / `:exists` guards |

The decision boils down to: do you have the asrt_id (use Layer 3), do you have the field + value (use Layer 2's `retract`), do you want to wipe a cell (use Layer 2's `delete`), or do you want to delete the whole entity (use Layer 1)? Audit, replay, and provenance-aware fixes typically work at Layer 3 because they already carry assertion ids; ergonomic UI flows usually work at Layer 1 or Layer 2.

## 6. Reference

### 6.1 Method signatures by layer

```python
# Layer 1 — fg.entities
fg.entities.create(EntityCls, *, meta=None, **identity) -> str          # e_ref
fg.entities.delete(e_ref_or_cls, *, meta=None, **identity) -> int       # count revoked
fg.entities.edit(EntityCls, **identity) -> EntityEditor                 # context manager
fg.entities.get(EntityCls, **identity) -> EntitySnapshot | None
fg.entities.where(EntityCls, *, limit=None, _meta=None, **field_filters) -> Iterable[EntitySnapshot]
fg.entities.match(EntityCls, template, *, limit=None, **port_constraints) -> Iterable[EntitySnapshot]
fg.entities.ref(EntityCls, **identity) -> str                           # e_ref, no write
fg.entities.exists(EntityCls, **identity) -> bool

# Layer 2 — fg.fields
fg.fields.set(field, e_ref, value, *, meta=None) -> str                 # asrt_id
fg.fields.add(field, e_ref, value, *, meta=None) -> str                 # asrt_id
fg.fields.retract(field, e_ref, value, *, meta=None) -> str | None      # revoker asrt_id
fg.fields.delete(field, e_ref, *, meta=None) -> int                     # count revoked
fg.fields.get(field, e_ref) -> Any                                       # current value(s)

# Layer 3 — fg.assertions
fg.assertions.by_id(asrt_id) -> AssertionRecord | None
fg.assertions.by_ids(asrt_ids, *, strict=False) -> AssertionRecordSet
fg.assertions.where(*, field=None, e_ref=None, value=None, value_tag=None, _meta=None) -> AssertionRecordSet
fg.assertions.field(Field) -> AssertionView
fg.assertions.active -> AssertionRecordSet
fg.assertions.all -> AssertionRecordSet
fg.assertions.retract(asrt_id, *, meta=None) -> str                     # revoker asrt_id
```

### 6.2 Cross-layer error codes

| Code | Raised by | Trigger |
|---|---|---|
| (untyped layer mismatch) | every Layer manager | wrong navigation key shape; message names the correct layer |
| `FIELD_CARDINALITY_MISMATCH` | `fg.fields.set` / `add` | calling `set` on multi-cardinality field, or `add` on single-cardinality field |
| `INV_7C_IDENTITY_PROTECTED` | `fg.assertions.retract` | the target `asrt_id` is an Identity Claim |
| `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` | `fg.assertions.retract` | the target `asrt_id` is a `<EntityType>:exists` Claim |
| `UNRESOLVABLE_E_REF` | `fg.entities.delete(e_ref_str)`, `fg.fields.*` | the supplied `e_ref` string is not known to this runtime's shadow store (call `fg.entities.ref(...)` or `fg.entities.create(...)` first) |

All these inherit from `SDKStoreError`. Inspect `exc.code` to dispatch on category.
