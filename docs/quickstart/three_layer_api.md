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

Errors are part of the design. Passing an `asrt_id` to `fg.entities.get(...)` does not implicitly route through `fg.assertions.by_id(...)` — it raises an error telling you to use the correct layer. The same goes for passing a Field descriptor to `fg.entities.*` or an `EntityClass` to `fg.fields.*`. Each layer's mental model is distinct enough that silent fallback would mask programmer intent.

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

**EntityEditor — multi-field writes on one entity in one transaction:**

```python
with fg.entities.edit(User, user_id="u-1") as editor:
    editor.name.set("Alice")                # single-cardinality field
    editor.tags.add("engineer")             # multi-cardinality field
    editor.tags.add("reviewer")
    # commit on context exit; if any one operation raises,
    # the whole edit is abandoned
```

The editor exposes one attribute per declared field of the entity. Each attribute is a typed handle:

- `editor.<single_field>.set(value, meta=...)`
- `editor.<multi_field>.add(value, meta=...)`
- `editor.<field>.retract(asrt_id=..., meta=...)`

Using `.set` on a multi-cardinality field (or `.add` on a single) raises `CardinalityError` at dispatch. Identity fields expose a `.value` property for read but reject `.set` / `.add` / `.retract` with `INV_7C_IDENTITY_PROTECTED` (see §3.3).

**`fg.batch(...)` — multi-entity / multi-write in one transaction:**

```python
with fg.batch(meta={"source": "import"}) as tx:
    alice = tx.entity(User, user_id="u-1")
    bob   = tx.entity(User, user_id="u-2")
    alice.name.set("Alice")
    alice.tags.add("engineer")
    bob.name.set("Bob")
    # commit on context exit; atomic across all writes
```

`tx.entity(EntityCls, **identity)` returns a `ManagedEntityHandle` with the same `editor.<field>.set/add/retract` shape as `EntityEditor`. Use `fg.batch` when you need to coordinate writes across multiple entities; use `fg.entities.edit` when all writes target one entity.

### 2.3 Read methods

| Method | What it returns |
|---|---|
| `get(EntityCls, **identity)` | The full snapshot for one full identity, or `None` |
| `where(EntityCls, *, limit=None, _meta=None, **field_filters)` | Snapshots matching equality filters on entity/field values |
| `match(EntityCls, template, *, limit=None, **port_constraints)` | Snapshots selected by an application `Rule` or AND-only `RuleExpr`. **Replaces the older `Query` mechanism** — instead of constructing a query object you express the search as a rule/condition expression, and `match` returns the entities that satisfy it. See expansion below for `template`, `limit`, and `port_constraints`. |
| `ref(EntityCls, **identity)` | A managed `e_ref` string; does not write to the ledger |
| `exists(EntityCls, **identity)` | Boolean visibility check |

**`match` — ports, constraints, and connectivity**

The `template` is a `Rule` or AND-only `RuleExpr` that declares the search pattern. Among its declared ports, **exactly one must be an `entity_ref` port whose entity_type equals `EntityCls`** — that one is the **projection port**, and its bound values become the returned snapshots. The template may freely declare additional ports of other shapes (scalar Field ports, `entity_ref` ports for *different* entity types, etc.); only the one projection port drives the result set. Zero matching ports raises with a list of available port names; more than one matching port raises as ambiguous.

`port_constraints` narrow the match. Each keyword argument names a port declared in the template and pins it to one of two value shapes:

- A **concrete value** (scalar, `idref_v1` string, or an `EntitySnapshot`) — pins the port via equality
- A **`Field` descriptor of `EntityCls`** — binds the port to the value of that field on each candidate entity

```python
# Pin a port to a literal value
fg.entities.match(User, my_rule, region="US")

# Bind a port to a Field of the matched entity
fg.entities.match(User, tag_match_rule, tag=User.tag_seed)

# Multiple constraints stack via AND; mix literal pins and Field bindings freely
fg.entities.match(
    User, tag_match_rule,
    tag=User.tag_seed,        # bind port `tag` to the matched user's User.tag_seed value
    name=User.name,            # bind port `name` to the matched user's User.name value
    region="US",               # pin port `region` to a literal
)
```

There is no upper bound on how many `port_constraints` you can pass. Each one is independently translated and AND-joined into the template's body. A `Field` binding generates two implicit atoms — `(projected_entity, $hidden_var) ∈ <field_pred>` and `<port_var> == $hidden_var` — so you can think of `name=User.name` as "the named port equals whatever `User.name` is on the matched user".

Cross-entity `Field` constraints are **not** supported via `port_constraints`: every `Field` descriptor passed as a constraint must belong to `EntityCls`. If you pass a Field of a different entity class, the call raises `"cross-entity Field constraints are not supported by fg.read.match(...); use RuleExpr.join_by_ports(...) to connect entities"`. To match across entities, express the join inside the `RuleExpr` (e.g., `RuleExpr.join_by_ports(...)`) rather than as a port constraint.

**Connectivity requirement.** When you provide any `port_constraints`, every constrained port must be reachable from the projection port through the template's body atoms. A constraint on a port that the template does not connect to the projection port raises. In practice this means: for every constrained port, at least one atom in the rule body must transitively tie that port's variable to the projected entity's variable. The check fires before any ledger work, so disconnected templates fail fast rather than silently returning an empty result.

**`limit`** caps the number of distinct returned snapshots (the result is already deduplicated by `e_ref`). Pass a non-negative integer or `None` (default) for unlimited. `limit=0` returns an empty tuple. Negative values, booleans, or non-integer types raise `SDKStoreError`.

### 2.4 The EntitySnapshot

`get(...)` returns an `EntitySnapshot`; `where(...)` and `match(...)` return iterables of them. The snapshot is a read-only projection over one entity's current active state at the moment the read was issued.

```
EntitySnapshot
├── ref: str                              # e.g., "idref_v1:User:7c12...3a"
├── entity_type: str                      # e.g., "User"
├── identity: dict                        # e.g., {"user_id": "u-1", "locale": "en"}
├── identity_available: bool              # True after fg.entities.get / where / match
├── <field attribute access>              # snap.name, snap.tags, ...
│       └─ single → value or None
│          multi  → tuple or ()
├── assertions: AssertionView             # Layer 3 view scoped to this entity
│       ├── .active                       # AssertionRecordSet of non-revoked records
│       ├── .all                          # AssertionRecordSet of every record
│       └── .field(name) → AssertionView  # field-scoped sub-view
└── .field(name) → AssertionView          # shortcut to .assertions.field(name)
```

Snapshots are frozen (`FrozenSnapshotError` on attribute set). A reference projection over Identity field values goes through `snap.<identity_field>` or `snap.identity[<key>]`; Field values use the same `snap.<field>` syntax. The snapshot does not refresh on its own — re-read with `fg.entities.get(...)` to see later writes.

### 2.5 What Layer 1 rejects

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

**Value shape — one element per call:**

The `value` argument is always **one scalar** of the field's declared storage domain (see [`schema_definition.md`](schema_definition.md) §1.4). It is **not** a list, even for multi-cardinality fields. To add multiple elements to a multi-cardinality field, call `add` multiple times:

```python
fg.fields.add(User.tags, alice, "engineer")
fg.fields.add(User.tags, alice, "reviewer")
# Each call appends one element. Passing a list/tuple raises SDKValueError.
```

Passing `["engineer", "reviewer"]` as the value raises `SDKValueError` because `list` does not match the declared element type. The same rule applies to `set` (always one scalar) and `retract` (revoke one specific `(field, ref, value)` triple at a time).

Reads work the opposite way: `fg.fields.get(field, ref)` returns one scalar for single-cardinality fields and a `tuple` of scalars for multi-cardinality fields (possibly empty `()`).

### 3.3 Identity descriptors at Layer 2

Identity values can be **read** (via `snap.user_id` / `snap.identity[...]`) and **introspected** (via `fg.assertions.field(User.user_id)`), but never **mutated** — all four write methods (`set` / `add` / `retract` / `delete`) reject `Identity` descriptors with `SDKStoreError(code="INV_7C_IDENTITY_PROTECTED")`. Identity Claims are the immutable entity anchor per INV-7c.

To "change" an identity, delete and recreate: `fg.entities.delete(old_ref)` + `fg.entities.create(EntityCls, **new_identity)`.

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
| `field(Field)` | every record for one schema field; returns an `AssertionView` exposing `.active` (non-revoked) and `.all` (every record) |

The `_meta` filter accepts a dict and matches assertions whose meta values agree; flat `source=` / `trace_id=` etc. kwargs are not accepted.

### 4.3 Retract

`retract(asrt_id, *, meta=None)` is the only public assertion-id-level mutation. It returns the revoker's `asrt_id`.


### 4.4 Returned types

Layer 3 reads compose three types. All are read-only; mutation goes through `retract`.

**`AssertionRecord`** — one immutable record describing one assertion. Frozen dataclass with 9 fields:

```
AssertionRecord
├── asrt_id: str            # content-addressed assertion id
├── value: Any              # the stored value
├── value_tag: str          # storage tag (e.g., "string" / "int" / "entity_ref")
├── is_active: bool         # False if this assertion has been revoked
├── entity_type: str        # SDK entity type name (e.g., "User")
├── field_name: str         # SDK field name (e.g., "name")
├── pred_id: str            # kernel predicate id (e.g., "User.name")
├── e_ref: str              # idref_v1 entity reference
└── meta: AssertionMeta     # typed meta projection (see data_model.md §2.1)
```

**`AssertionRecordSet`** — an immutable `tuple` subclass holding a collection of `AssertionRecord`. Iterable, slice-able, addition-able. Chainable filter / lookup methods all return another `AssertionRecordSet` so you can pipeline them:

```
AssertionRecordSet  (extends tuple[AssertionRecord, ...])
├── .where(*, value=..., value_tag=..., _meta={...}) → AssertionRecordSet
├── .at(t: str)                                        → AssertionRecordSet  # business-time filter
├── .by_id(asrt_id: str)                               → AssertionRecordSet  # 0 or 1 match
├── .one()                                             → AssertionRecord     # raises if not exactly 1
├── .first()                                           → AssertionRecord | None
└── .all()                                             → tuple[AssertionRecord, ...]
```

**`AssertionView`** — a structured view over a subset of records, scoped either to one entity or one field. Returned by `fg.assertions.field(Field)`, `snap.assertions`, and `snap.field(name)`. Read-only (raises `FrozenSnapshotError` on attribute set).

```
AssertionView
├── .is_entity_scope: bool      # True if entity-scope, False if field-scope
├── .active: AssertionRecordSet # non-revoked records (aggregated across all
│                                 fields when entity-scope)
├── .all:    AssertionRecordSet # active + revoked records
├── .field(name_or_Field) → AssertionView    # descend to one field's view
│                                              # (meaningful on entity-scope only)
├── .by_id(asrt_id)            → AssertionRecord | None
├── .by_ids(asrt_ids, *, strict=False) → AssertionRecordSet
├── .where(*, field=..., e_ref=..., value=..., value_tag=..., _meta={...})
│                              → AssertionRecordSet  # filter over .active
├── .at(t)                     → AssertionRecordSet  # business-time filter over .active
└── view.<field_name>          → AssertionView       # __getattr__ shortcut to .field(name)
                                                       # for entity-scope views only
```

`AssertionView` has two scopes that share the same surface:

- **Entity-scope** — returned by `snap.assertions` on any `EntitySnapshot`. Holds an internal field-name → field-scope view map. `.active` / `.all` aggregate records across every field on the entity. `.field(name)` descends.
- **Field-scope** — returned by `fg.assertions.field(Field)`, `snap.field(name)`, or `entity_view.field(name)`. Exposes the field's records directly through `.active` and `.all`. `.field(...)` is not meaningful here.

A typical drill-down:

```python
snap = fg.entities.get(User, user_id="u-1")
snap.assertions                               # AssertionView (entity-scope)
snap.assertions.active                        # AssertionRecordSet, aggregated across all u-1's fields
snap.assertions.field("name")                 # AssertionView (field-scope for User.name on u-1)
snap.assertions.field("name").active          # AssertionRecordSet for name only
snap.assertions.field("name").all.where(_meta={"version": "v1"})  # filtered AssertionRecordSet
snap.assertions.field("name").all.where(_meta={"version": "v1"}).one()  # AssertionRecord
```

## 5. Crossing layers

Two bridge tokens wire the layers downward: an `e_ref` from Layer 1, an `asrt_id` from Layer 2.

```text
  Layer 1 — fg.entities                          key:    EntityCls + identity_kwargs
                                                 handle: e_ref (managed string)

            create(...) / ref(...)   ─── returns ───┐
            delete / edit / get / where / match
                                                    │
                                                    │ e_ref string
                                                    │ "idref_v1:<EntityType>:<digest>"
                                                    │ opaque; treat as a token
                                                    ▼
  Layer 2 — fg.fields                             key: Field + e_ref (+ value)

            set(...) / add(...)      ─── returns ───┐
            retract / delete / get
                                                    │
                                                    │ asrt_id string
                                                    │ content-addressed
                                                    ▼
  Layer 3 — fg.assertions                         key: asrt_id (or iterable)

            by_id / by_ids / where / field / active / all
            retract(asrt_id)  ── INV-7c + :exists guards apply
```

Remove verbs scale by layer to match granularity:

```text
  fg.entities.delete(e_ref)                 ► every claim on that entity
                                              (Identity + :exists + every Field)
  fg.fields.delete(field, e_ref)            ► every value at one field cell
                                              (fail-fast on first revoke error)
  fg.fields.retract(field, e_ref, value)    ► the one (field, ref, value) record
                                              (raises on 0 or >1 matches)
  fg.assertions.retract(asrt_id)            ► exactly one assertion id
                                              (Identity / :exists asrt_ids rejected)
```

Pick the smallest layer whose key you already have.

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
