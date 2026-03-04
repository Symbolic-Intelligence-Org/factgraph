# FactPy SDK User Guide

> This document describes implemented behavior; unimplemented capabilities are explicitly labeled as “current boundary”.
> Behaviors in this document are tagged into three categories: **stable contract** (recommended to write strong-assert tests), **current behavior** (may evolve), **planned** (not implemented yet).

---

## Table of Contents

1. [Installation & Initialization](#1-installation--initialization)
2. [Schema Definition](#2-schema-definition)
3. [Writing Data](#3-writing-data)
4. [meta Fields](#4-meta-fields)
5. [Reading Data](#5-reading-data)
6. [Rule / Query / Derivation](#6-rule--query--derivation)
7. [Provenance Validation](#7-provenance-validation)
8. [Which Write Entry Should I Use?](#8-which-write-entry-should-i-use)
9. [Error Handling Cheat Sheet](#9-error-handling-cheat-sheet)
10. [Registry](#10-registry)
11. [Advanced APIs](#11-advanced-apis)
12. [Migration Notes (v2 → v3)](#12-migration-notes-v2--v3)

---

## 1. Installation & Initialization

### 1.1 Initialize a Store

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

When persistence is needed, specify `ledger_path`:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

To make Rule query results return dict rows by default:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    default_row_format="dict",
)
```

**Stable contract**

* `classes` must be a non-empty `list[Entity subclass]`; `from_schema_classes(...)` / `schema_preflight_from_classes(...)` paths raise `SDKSchemaError`, while the `SDKStore(...)` constructor path raises `SDKStoreError`.
* `ledger` and `ledger_path` are mutually exclusive; you cannot pass both.
* On first write, `ledger_path` records `schema_digest`; on reopen, it is validated and a mismatch raises `SDKStoreError`.
* `default_row_format` only affects `sdk.run(rule, ...)`; valid values are `"tuple"` / `"dict"`, default `"dict"`.
* When parsing results as `"tuple"`, a `DeprecationWarning` will be triggered; it is recommended to switch uniformly to `"dict"`.
* The `FACTPY_ROW_FORMAT` environment variable is read and cached when `SDKStore` initializes (not dynamically read on every `run()`).

### 1.2 Schema Preflight

For scenarios that do not require a runtime store (CI validation, module import phase), you can run preflight only:

```python
from factpy_kernel.sdk import schema_preflight_from_classes

preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])
print(preflight.get("warnings", []))
print(preflight.get("summary", {}))   # entity_count / predicate_count / pred_ids
```

**Stable contract**: returns a `dict` whose core keys include `ok`, `warnings`, `errors`, `diagnostics`, `summary` (on success).

---

## 2. Schema Definition

### 2.1 Basic Structure

```python
from factpy_kernel.sdk import Entity, Identity, Field

class User(Entity):
    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    lang: str = Identity()

    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
    country: Country = Field(cardinality="single")
```

`Identity` locates a fact; `Field` carries the value(s) of that fact. There is limited symmetry on the read side: snapshot **value access** (`snap.lang`, `snap.name`) works the same for both; however `snap.assertions.lang` is not available — the `assertions` namespace only covers `Field` fields, not `Identity` fields. The write side differs: calling `.set()` / `.add()` on an `Identity` field raises an exception.

**Stable contract**: each `Entity` must have at least one `Identity`, otherwise class definition raises `SDKSchemaError`.

**Current behavior**: an `Entity` class docstring is automatically written into the schema’s entity-level `description` (`schema_ir.entities[*].description`) for documentation/LLM descriptions.

### 2.2 `Identity` Parameters

| Parameter                 | Meaning                                                                                                          |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `primary_key=True`        | Marked as the join anchor; implicitly carried in cross-Field reasoning in Rules, and does not appear in the head |
| `default`                 | Static default value                                                                                             |
| `default_factory="uuid4"` | Auto-generate a UUID when missing                                                                                |

`primary_key=True` and `default_factory` are orthogonal — the former declares semantic responsibility and the latter declares a generation strategy; they can be used together or separately. For an Entity not marked with `primary_key=True`, if a Rule contains cross-Field joins, compilation fails.

**Recommendation**: `Identity` fields should point to business attributes of the entity (e.g., `user_id`, `lang`), not data-management dimensions such as `source` or `version`. The latter belong to meta, not Identity. This is a design recommendation; the engine does not enforce it.

### 2.3 `Field` Parameters

| Parameter              | Meaning                                                                     |
| ---------------------- | --------------------------------------------------------------------------- |
| `cardinality="single"` | Single-value view: `snap.<field>` returns a scalar; write API uses `.set()` |
| `cardinality="multi"`  | Multi-value; all values under the same coordinate are retained              |
| `description`          | Documentation / LLM-facing description text                                 |

**Current behavior note**: `single` does not automatically clear old assertions on write; `active/history` may still contain multiple non-retracted assertions, while `snap.<field>` returns the current single-value view.

**Current boundary**: `dims` / `fact_key` / `pred_id` / `functional` / `temporal` have been removed.

### 2.4 Reified Record (Relationship Node)

All entities are based on `Entity`; a relationship node is just a usage convention:

```python
class LivesIn(Entity):
    uid: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")
```

**Stable contract**: after compilation, the schema generates a `<T>:exists` predicate for every `Entity`; batch writes will automatically add a `<T>:exists` write op when writing fields.

### 2.5 Common Type Mapping

| Python annotation         | type_domain  |
| ------------------------- | ------------ |
| `str`                     | `string`     |
| `int`                     | `int`        |
| `bool`                    | `bool`       |
| `float`                   | `float64`    |
| `bytes`                   | `bytes`      |
| `datetime`                | `time`       |
| `UUID`                    | `uuid`       |
| other `Entity` subclasses | `entity_ref` |

**Current behavior**: string annotations are also supported (e.g., `"str"`, `"datetime"`, `"uuid"`, `"entity_ref"`); unrecognized annotations fall back to `entity_ref`.

### 2.6 In-memory Objects vs Managed Objects

```python
# Plain in-memory object (not bound to a store)
alice = User(user_id="u-001")
alice.name = "Alice"      # normal Python assignment

# sdk.batch managed object (supports .set/.add/.retract)
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice_h = tx.entity(User, user_id="u-001", lang="zh")
    alice_h.name.add("Alice")
    tx.commit()
```

**Stable contract**: `.set` / `.add` / `.retract` are capabilities of batch/edit managed handles, not of plain in-memory objects.

---

## 3. Writing Data

### 3.1 `sdk.batch`

The main entry for batch writes, suitable for ETL, sample data construction, and scenarios requiring preview / wire plans.

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "hr"}) as tx:
    de = tx.entity(Country, iso_code="DE")
    de.name.set("Germany")

    # Provide all Identity at once
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")
    u.age.set(30)
    u.country.set(de)   # can reference a handle within the same tx

    # Or bind Identity step-by-step
    u2 = tx.entity(User, user_id="u-002")
    u2 = u2.bind(lang="en")
    u2.name.add("Alicia")

    plan = tx.preview()   # read-only preview, not persisted
    res = tx.commit()     # actual write
```

`batch`-level `meta` is inherited by all write ops; a single op can override with its own `meta`:

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")                                  # inherits batch meta
    u.name.add("Alice", meta={"valid_from": "2024-06"})    # per-op override
    tx.commit()
```

**meta merge precedence** (higher overrides lower): `commit_meta > field_op_meta > entity_meta > batch_meta`

**Stable contract**

* `single` fields use `.set()`; `multi` fields use `.add()`. Misuse raises `SDKStoreError` (batch handle path; `sdk.edit` path raises `CardinalityError`).
* Batch handles retract via `.retract(assertion_id)`; edit `FieldEditor` retracts via `.retract(asrt_id=...)`. Neither supports retract-by-value.
* If Identity is incomplete, `.set()` / `.add()` immediately raises `SDKStoreError` (error message lists missing fields; you can `bind(...)` first and then write).
* Calling `.set()` / `.add()` on an Identity field immediately raises `SDKStoreError` — Identity is immutable once determined.
* `preview()` does not persist and may be called repeatedly; only `commit()` persists.
* `SDKBatchTx` as a context manager does not auto-commit and does not auto-rollback (`__exit__` is a no-op); callers must explicitly call `commit()` and handle exceptions themselves.

**entity_ref fields** (stable contract): you may pass a “handle within the same tx” or a “canonical idref_v1 token”; you may not pass a plain business string (e.g., `"DE"`).

**Cardinality rules quick reference**

| Field type | Allowed                                                           | Forbidden                                                           |
| ---------- | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| `single`   | `.set(value)`                                                     | `.add(value)` → `SDKStoreError` (batch) / `CardinalityError` (edit) |
| `multi`    | `.add(value)`                                                     | `.set(value)` → `SDKStoreError` (batch) / `CardinalityError` (edit) |
| any        | `.retract(assertion_id)` (batch) / `.retract(asrt_id=...)` (edit) | retract-by-value (not supported)                                    |

```python
# batch handle path
u.age.set(30)         # single ✅
u.age.add(30)         # ❌ SDKStoreError
u.name.add("Alice")   # multi ✅
u.name.set("Alice")   # ❌ SDKStoreError
```

### 3.2 Wire Plan (Serializable / Replayable)

```python
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("Alice")
    wire_json = tx.preview().to_json(sdk)

# Replay across process/time
from factpy_kernel.sdk.batch import WireBatchPlan

plan2 = WireBatchPlan.from_json(wire_json)
plan2.apply(sdk, strict_schema=True)
```

**Current behavior**: `strict_schema=True` checks that the wire plan’s `schema_digest` matches the current SDK schema.

**Current behavior note**: wire export (`to_json` / `export`) does not accept raw `idref_v1` string values as `entity_ref` writes; to create a replayable wire plan, express entity relationships using “handle references within the same tx” inside the batch.

### 3.3 Dependency Closure (`include_deps`)

Default `include_deps=True`: committing an object automatically includes dependency objects it references. Missing dependencies are not silently skipped; an error is raised immediately (**stable contract**).

### 3.4 `sdk.edit`

Suitable for “identity is fully known, modify only a few fields”:

```python
with sdk.edit(User, user_id="u-001", lang="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
    # normal exit: auto commit()
    # exception inside with: auto rollback()
```

Explicit version control:

```python
editor = sdk.edit(User, user_id="u-001", lang="zh")
editor.__enter__()
try:
    editor.name.add("Alicia")
    plan = editor.preview()
    editor.commit(meta={"trace_id": "manual-fix", "approved_by": "admin"})
except Exception:
    editor.rollback()
    raise
```

**Stable contract**

* If the entity does not exist, raises `EntityNotFoundError` (no implicit create; use `sdk.batch()` to create).
* After `commit()` or `rollback()`, the editor is closed; calling any method raises `EditorClosedError`.

### 3.5 `sdk.ingest`

Suitable for external imports, or when you only have `ref + asrt_id` (cannot get full identity):

```python
result = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Alicia"},
        {"kind": "set", "field": User.age, "e_ref": alice_ref, "value": 31},
        {"kind": "retract", "asrt_id": "asrt_old_xxx"},
    ],
    meta={"source": "hr", "trace_id": "hr-001"},
)

print(result.written_assertion_ids)
print(result.skipped_count)
print(result.duplicate_count)
print(result.warnings)
print(result.diagnostics)
```

**Item structure**

| `kind`    | Required fields           | Optional fields |
| --------- | ------------------------- | --------------- |
| `set`     | `field`, `e_ref`, `value` | `meta`          |
| `add`     | `field`, `e_ref`, `value` | `meta`          |
| `retract` | `asrt_id`                 | `meta`          |

**Stable contract**

* Top-level `meta` is merged with item `meta`; item keys override top-level keys on conflict.
* `kind=set` corresponds to `single` fields; `kind=add` corresponds to `multi` fields.
* If any `diagnostics` entry has `severity="error"`, the whole batch is not written (collect-and-stop).
* `allow_sensitive_meta=True` only suppresses sensitive warnings; it does not relax hard reserved constraints.

### 3.5.1 Typical scenario: entity migration

When you cannot obtain full identity via `find`, `ingest` is a workable fallback:

```python
records = sdk.find(LivesIn, user=alice.ref)
li = records[0]

old_asrt_id = li.assertions.country.active[0].asrt_id
fr_ref = sdk.get(Country, iso_code="FR").ref

sdk.ingest(
    [
        {"kind": "retract", "asrt_id": old_asrt_id},
        {"kind": "set", "field": LivesIn.country, "e_ref": li.ref, "value": fr_ref},
    ],
    meta={"source": "hr", "trace_id": "relocation-001", "note": "Alice moved to France"},
)
```

### 3.6 Low-level Write Entry

```python
alice_ref = sdk.ref(User, user_id="u-001", lang="zh")
sdk.set(User.age, alice_ref, 31, meta={"source": "hr"})
sdk.add(User.name, alice_ref, "Alicia", meta={"source": "hr"})
sdk.retract("asrt_xxx", meta={"source": "hr"})
```

Minimal wrapping; writes directly to the ledger; no preview/wire capability.

---

## 4. meta Fields

meta is not a free-form dict; fields fall into four responsibility categories:

**System reserved (written by ingest flow; not user-writable)**

`ingested_at`, `ingest_key`, `revoked_asrt_id`

**Operation tracking (conventional fields; recommended)**

`source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`

**Derivation chain (auto-written by accept flow)**

`derived_rule_id`, `derived_rule_version`, `run_id`, `support_digest`, `support_kind`, `candidate_id`, `candidate_key`, `accepted_at`, etc.

**Business temporality (unlocks time views)**

`valid_from`, `valid_to`, `version`

Business temporality fields are user-writable; the view layer is aware of them but they are not mandatory. If unset, only `.active` / `.history` views exist; if set, `.at(t)` / `.version(v)` queries are enabled.

**meta key stratification** (stable contract)

| Level              | Representative keys                                                         | Behavior                                 |
| ------------------ | --------------------------------------------------------------------------- | ---------------------------------------- |
| hard reserved      | `ingested_at`, `ingest_key`, `revoked_asrt_id`                              | user not allowed to write                |
| sensitive semantic | derivation-chain keys such as `derived_rule_id`, `run_id`, `support_digest` | warning by default; does not block write |
| convention         | `source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`     | normal write                             |
| free               | business-defined keys                                                       | normal write                             |

**meta kind system** (v3 update)

Numeric meta fields are stored by kind; kind names were renamed and extended in v3:

| kind      | Type    | Notes                                           |
| --------- | ------- | ----------------------------------------------- |
| `"str"`   | `str`   | string                                          |
| `"int"`   | `int`   | integer (formerly `"num"`, renamed in v3)       |
| `"float"` | `float` | float (new in v3; for fields like `confidence`) |
| `"bool"`  | `bool`  | boolean                                         |
| `"time"`  | `int`   | epoch nanosecond timestamp                      |
| `"json"`  | `Any`   | JSON-serializable object                        |

The `confidence` field’s kind is fixed as `"float"` and inferred automatically by the write protocol; callers do not need to specify it.

`kind` is not visible to callers: the write protocol first applies a forced mapping by conventional keys (`_KEY_KIND_MAP`), then infers unknown keys by value type.
Conventional key coverage checks run at module load time (`convention + sensitive` keys must all appear in the mapping table).

Type inference rules for unknown keys (conventional keys override these rules):

* `bool` → `"bool"`
* `int` → `"int"`
* `float` → `"float"`
* `str` → `"str"`
* other types are not supported and raise `WriteProtocolError`

**Stable contract (`confidence`)**

* `meta["confidence"]` must be a `float` and within `(0, 1]`.
* `int` (e.g., `1`) is not auto-promoted to `float`; it raises an error.

### 4.1 Common Example (`confidence`)

```python
from factpy_kernel.core.store.types import ViewSpec

alice_ref = sdk.ref(User, user_id="u-001", lang="zh")

# ✅ valid: float within (0,1]
sdk.set(User.age, alice_ref, 30, meta={"source": "hr", "confidence": 0.82})
sdk.set(User.age, alice_ref, 30, meta={"source": "model_v2", "confidence": 0.64})

# ❌ invalid: int is not auto-promoted to float
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1})      # WriteProtocolError

# ❌ invalid: out of range
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1.2})    # WriteProtocolError

# aggregate confidence on read by view
row_max = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="max"))[0]
row_mean = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="mean"))[0]
print(row_max.confidence)   # 0.82
print(row_mean.confidence)  # 0.73
```

**Deduplication basis**: `claim + source + source_loc + trace_id + valid_from + valid_to + version`

**Boundary notes (important)**

* `confidence` does not participate in ingest idempotency keys.
* Therefore, under the same `trace_id` (the accept path is usually the same `run_id`), if the claim and the other dedup fields are the same, differing `confidence` does not create a new assertion and will be folded by idempotency.
* “Same fact with different `confidence` coexisting” typically happens across different inference batches (different `run_id/trace_id`) or different sources (different `source/source_loc`).

Note: `ingested_at` is the system write time, not the business effective time `valid_from`. Using `ingested_at` as `valid_from` for time views causes semantic misalignment.

**`trace_id` semantics**: `trace_id` participates in idempotency computation, but is not the sole determinant; `valid_from` / `valid_to` / `version` also participate. Under the same `trace_id`, as long as the temporality dimensions differ, different assertions are still produced.

---

## 5. Reading Data

### 5.1 `sdk.get`

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

if snap is None:
    print("not found")
else:
    print(snap.ref)                 # canonical idref_v1 token
    print(snap.entity_type)         # "User"
    print(snap.identity_available)  # True
    print(snap.identity)            # identity kwargs usable for sdk.edit(...)
```

**Stable contract**

* `get` accepts Identity parameters only; passing non-Identity fields raises `SDKSchemaError`.
* Returns `EntitySnapshot | None`.
* Snapshots returned by `get` have `identity_available=True`.

### 5.2 `sdk.find`

```python
# single field: exact match
rows = sdk.find(User, age=30)

# multi field: containment match
rows = sdk.find(User, name="Alice")

# entity_ref field
de = sdk.get(Country, iso_code="DE")
rows = sdk.find(User, country=de.ref)   # ✅
rows = sdk.find(User, country=de)       # ✅ (internally uses .ref)

rows = sdk.find(User, age=30, limit=20)

from factpy_kernel.core.store.types import ViewSpec
rows = sdk.find(User, lang="zh", view=ViewSpec(confidence_strategy="mean"))
```

**Stable contract**

* `limit` must be a non-negative integer (`limit=0` returns an empty list).
* When filtering by Identity you must provide all Identity fields of that entity.
* `temporal_view` parameter is not supported.
* Passing unknown filter fields raises `SDKSchemaError`.

**Current boundary**

* `view.confidence_strategy` only affects the displayed `confidence` value in results; it does not affect which assertions are returned.

**Identity availability in `find` results** (current behavior)

```python
records = sdk.find(LivesIn, user=alice_ref)
for rec in records:
    if rec.identity_available:
        with sdk.edit(LivesIn, **rec.identity) as editor:
            ...
    else:
        # use ingest: retract/set using rec.ref + asrt_id
        ...
```

* Without identity filters: snapshots are typically `identity_available=False`.
* With a full identity filter: returned snapshots have `identity_available=True`.

### 5.3 `EntitySnapshot` Assertion Views

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

# current view values
snap.name      # multi -> tuple[...]
snap.age       # single -> scalar or None
snap.country   # single entity_ref -> idref_v1 token or None

# assertion views
snap.assertions.name.active           # current non-retracted assertions
snap.assertions.name.history          # full history (including retracted)
snap.assertions.name.at("2024-03-01") # business-temporal filter
snap.assertions.name.version("v2")    # version filter
snap.field("name").active             # equivalent
```

**View semantics** (stable contract)

| View          | Semantics                                                                    |
| ------------- | ---------------------------------------------------------------------------- |
| `.active`     | currently not retracted; maintained by store registry                        |
| `.history`    | full history, including retracted                                            |
| `.at(t)`      | on active set: `valid_from <= t` and (`valid_to` is empty or `valid_to > t`) |
| `.version(v)` | on active set: `version == v`                                                |

**Temporal view boundaries**

* Assertions missing `valid_from` do not match `.at(t)` and only appear in `.active`.
* Assertions missing `version` do not match `.version(v)`.
* `.at(t)` validates ISO 8601 format (both `t` and assertion `valid_from`/`valid_to`); invalid formats raise `SDKStoreError`.
* `.version(v)` only accepts `str | int` (`bool` is invalid).
* Temporal filtering is stacked on top of the active set; it does not draw from history.
* `EntitySnapshot` and the `assertions` namespace are read-only; assignment raises `FrozenSnapshotError`.

---

## 6. Rule / Query / Derivation

### 6.1 Variable Declaration

```python
from factpy_kernel.sdk import vars

# recommended
with vars("u", "l", "n") as (u, l, n):
    ...

# factory style
with vars() as V:
    u, l, n = V("u", "l", "n")
```

**Stable contract**: `with vars() as (u, l)` (no-arg unpacking) is not supported and raises `SDKDSLError`.

### 6.2 Rule: Immediate Query

```python
from factpy_kernel.sdk import Rule, Pred, Not, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_rule = Rule(
        id="q_speaks",
        version="1.0.0",
        select=[u, l],
        where=[
            LivesIn(li),
            li.user == u,      # two-step style (chaining not supported)
            li.country == c,
            HasLanguage(hl),
            hl.country == c,
            hl.language == l,
        ],
    )

rows = sdk.run(speaks_rule, row_format="dict")
# [{"u": "...", "l": "..."}, ...]

rows = sdk.run(speaks_rule, view="default", row_format="dict")
# by default returns rows; does not inject confidence into rows

rows, display_meta = sdk.run(
    speaks_rule,
    view="default",
    row_format="dict",
    return_display_meta=True,
)
# display_meta has the same length as rows; each item contains at least:
# confidence / confidence_strategy / source_breakdown
```

**Stable contract**

* Chained form `LivesIn(li).user == u` is not supported; use the two-step form.
* OR uses `where=[[...], [...]]` (OR-of-AND).
* `row_format` precedence (high to low): `run(..., row_format=...) > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`.
* Invalid `row_format` raises `SDKStoreError(code="INVALID_ROW_FORMAT")`.
* `RuleRef` target rules require `expose=True`, otherwise `RuleCompileError`; they are not allowed inside `Not(...)`.
* `view` can be a named view or a `ViewSpec`; it only affects presentation, not evaluation scope.
* `sdk.run(rule, view=...)` returns `rows` only by default; it does not inject `confidence` into row objects.
* With `return_display_meta=True`, returns `(rows, display_meta)`; and you must also provide `view`, otherwise raises `SDKStoreError`.

**Current behavior**: supports linear arithmetic `+/-/constant-multiple` (e.g., `age == (2026 - by)`); does not support non-linear multiplication `x * y`.

### 6.3 Body: OR Branches with Confidence

In probabilistic reasoning, OR branches can be wrapped with `Body` and annotated with branch confidence:

```python
from factpy_kernel.sdk import Body

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
        ],
        head=Speaks(user=u, language=lang),
    )
```

**Stable contract**

* `Body.confidence` range: `(0, 1]`; `confidence=0` is a compile-time error.
* `Body.confidence=None` is allowed (no confidence constraint).
* Mixing `Body(...)` branches and bare list branches in the same `where` is forbidden; violation fails compilation.
* Bare list form is retained; compiled `body_confidences=None` and behavior remains as before.

**Supported scope**

* Rule: supports `Body(...)`; currently used only for `where` normalization; `body_confidences` does not participate in Rule runtime evaluation.
* Derivation: supports `Body(...)`; compiled `body_confidences` is extracted as a sidecar for `mode="problog"`.
* Query: `Body.confidence` is not supported; construction raises an error.

`body_confidences` passthrough chain:
`SDK Derivation/authoring payload -> compile_authoring_derivation_v1 -> sdk.evaluate -> evaluate_store -> engine(problog)`.

### 6.3.1 `Body` Mode Difference Example

```python
from factpy_kernel.sdk import Body, Derivation, Pred, vars

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.lang",
        version="1.0.0",
        where=[
            Body([Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([Pred("user:lang_model", u, lang)], confidence=0.6),
        ],
        head=User.name(lang="zh", name=lang),
    )

# native: ignores body_confidences (same as bare list behavior)
cands_native = sdk.evaluate(drv, mode="native")
print(cands_native[0].confidence)  # None

# problog: consumes body_confidences and returns probabilities
import factpy_kernel.adapters.problog
cands_prob = sdk.evaluate(drv, mode="problog")
print(cands_prob[0].confidence)    # float, e.g., 0.86
```

```python
# ❌ mixing Body and bare list (compile-time error)
with vars("u") as (u,):
    Rule(
        id="r.bad",
        version="1.0.0",
        select=[u],
        where=[Body([Pred("p", u)], confidence=0.9), [Pred("q", u)]],
    )
```

### 6.4 Query DSL

Identity and Field fields have identical access syntax in the `where` clause:

```python
from factpy_kernel.sdk import Query, vars

with vars("u", "l", "n") as (u, l, n):
    q = Query(
        head=[User(u), User.name(lang=l, name=n)],
        where=[
            User(u),
            u.lang == l,    # constrain an Identity field
            u.name == n,    # constrain a Field field
        ],
    )

rows = sdk.run(q)   # default returns list[dict]
```

**Stable contract**

* Query supports `row_format="dict"|"instance"`; default `"dict"`.
* `row_format="instance"` is only allowed when the head is a “single `Entity(var)`”; returns `list[EntitySnapshot|None]`.
* If the Query head does not satisfy instance constraints, or Query uses an invalid `row_format`, raises `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.
* Valid head forms: `Entity(var)`, `[Entity(var1), ...]`, `Entity.field(...)`.
* Query construction performs alias conflict checks (raises `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`) and where-variable binding checks (raises `SDKDSLError(code="QUERY_UNBOUND_VAR")`).
* Entity head columns return `EntitySnapshot`; field projection columns return scalar values.
* `Query.where` does not support `Body.confidence`; passing it fails compilation.
* `sdk.run(query, view=...)` is not supported (raises `SDKStoreError`).
* `sdk.run(query, return_display_meta=True)` is not supported (raises `SDKStoreError`).

**Current behavior**: `on_missing` / `on_type_mismatch` strategies:

* `error`: raise `SDKStoreError` (`QUERY_MISSING_REF` / `QUERY_TYPE_MISMATCH`)
* `skip`: drop the row
* `null`: set that column to `None` and keep the row (still participates in dedup)

### 6.5 Derivation

```python
from factpy_kernel.sdk import Derivation, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
    )

cands = sdk.evaluate(speaks_drv, mode="native")   # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="alice")

# atomic commit for multiple candidate sets
res = sdk.accept_many(cands, mode="atomic")
```

**Valid `mode` values** (stable contract, v3 update)

| mode        | Description                                              |
| ----------- | -------------------------------------------------------- |
| `"native"`  | Python built-in evaluator (formerly `"python"`, renamed) |
| `"souffle"` | Souffle engine (formerly `"engine"`, renamed)            |
| `"problog"` | ProbLog probabilistic inference engine (new in v3)       |

Passing old names `"python"` / `"engine"` raises a clear error and suggests the new name.

Engines use a name registry (non-singleton): `register_engine_evaluator(name -> fn)`.
Adapters auto-register on import:

* `import factpy_kernel.adapters.souffle` registers `"souffle"`
* `import factpy_kernel.adapters.problog` registers `"problog"`

**Stable contract**

* `sdk.evaluate(...)` produces candidates and does not write the ledger; `sdk.accept(...)` writes the ledger.
* Supports multi-head `head=[H1, H2, ...]`; `evaluate` returns flattened results sharing the same `run_id`.
* `sdk.accept(CandidateSet, ...)` accepts exactly one positional argument; allowed override keys: `approved_by`, `note`, `dry_run`, `identity_override` (also via `meta_overrides`); unknown args raise `SDKStoreError`.
* `sdk.run(Derivation(...))` is not supported; use `sdk.evaluate(...)`.
* `sdk.evaluate(..., view=...)` is not supported; passing it raises `SDKStoreError` (inference always uses the full active assertion set).
* When a dependency graph exists, prefer `sdk.accept_many(..., mode="atomic")` for atomicity.

### 6.5.1 `accept` Idempotency and Coexistence Example

```python
from dataclasses import replace
import factpy_kernel.adapters.problog

cands = sdk.evaluate(speaks_drv, mode="problog")
cand = cands[0]

# first write
r1 = sdk.accept(cand, approved_by="alice")
print(r1.accepted_count, r1.skipped_count)  # 1, 0

# same candidate written again: idempotent skip
r2 = sdk.accept(cand, approved_by="alice")
print(r2.accepted_count, r2.skipped_count)  # 0, 1
print(r2.skipped_reason_counts)             # {"duplicate": 1}

# same claim, different confidence: coexists (not duplicate)
cand_v2 = replace(cand, confidence=0.61)
r3 = sdk.accept(cand_v2, approved_by="alice")
print(r3.accepted_count, r3.skipped_count)  # 1, 0
```

**Current boundary**

* Temporal write semantics in Derivation heads (producing assertions with `valid_from`/`valid_to`/`version` directly from the head) are not open yet. Temporal information can currently only be carried via meta in write paths (`sdk.batch`/`sdk.ingest`).

### 6.6 Identity Rule for `head`

```
Fields appearing in head = all non-primary Identity + target Field value
```

* **`primary_key` fields**: regardless of how many, they never appear in the head; they are implicitly carried by entity binding in `where`.
* **non-primary Identity fields**: must be explicitly provided in the head, otherwise the write target is ambiguous.

```python
# User has primary_key=user_id, non-primary Identity=lang
head=User.name(lang=l, name=n)   # user_id does not appear; lang must be provided
```

A `primary_key` field appearing in the head is a compile-time hard error.

### 6.7 Cross-coordinate Join

Two facts of the same entity under different coordinates are two different variables in a Rule; they are explicitly joined via the `primary_key`:

```python
with vars("u1", "u2", "n1", "n2") as (u1, u2, n1, n2):
    q = Query(
        head=[],
        where=[
            User(u1), u1.lang == "zh", u1.name == n1,
            User(u2), u2.lang == "en", u2.name == n2,
            u1.user_id == u2.user_id,   # primary_key cross-coordinate join
        ],
    )
```

**Stable contract**

* Cross-coordinate joins only allow `primary_key` fields to participate in `==` comparisons.
* Cross-coordinate equality comparisons on non-`primary_key` fields are compile-time hard errors; the error message suggests which `primary_key` field to use.
* Cross-entity-type comparisons are compile-time hard errors.

### 6.8 Rule / Derivation Current Limitations Quick Reference

| Limitation                                   | Notes                                                    |
| -------------------------------------------- | -------------------------------------------------------- |
| String DSL                                   | `sdk.run("...")` / `sdk.evaluate("...")` not supported   |
| `sdk.run(Derivation(...))`                   | not supported; use `sdk.evaluate(...)`                   |
| Chained path comparisons                     | `LivesIn(li).user == p` not supported; use two-step      |
| Cross-coordinate non-primary_key comparisons | compile-time hard error                                  |
| Non-linear arithmetic                        | `x * y` not supported                                    |
| `Not(...)` body                              | must be non-empty; has safety checks with outer bindings |
| `RuleRef` inside `Not(...)`                  | compile-time error                                       |

---

## 7. Provenance Validation

`sdk.validate_provenance(...)` is a pure validation entry; it does not write the ledger and does not automatically block ingest/accept.

```python
report = sdk.validate_provenance(candidate_set, standard="derivation_v1")

# or validate a dict
report = sdk.validate_provenance(
    {"derived_rule_id": "drv.speaks", "derived_rule_version": "1.0.0",
     "run_id": "run-001", "support_kind": "exact", "support_digest": "sha256:...."},
    standard="derivation_v1",
)

print(report.ok)
print(report.errors)
print(report.warnings)
```

**Required fields for `derivation_v1`** (stable contract)

| Field                  | Requirement      |
| ---------------------- | ---------------- |
| `derived_rule_id`      | non-empty string |
| `derived_rule_version` | non-empty string |
| `run_id`               | non-empty string |
| `support_kind`         | non-empty string |
| `support_digest`       | `sha256:<64hex>` |

Optional keys `schema_digest` / `policy_digest` with invalid formats are recorded in `warnings` (not in `errors`).

---

## 8. Which Write Entry Should I Use?

| Scenario                                                       | Recommended entry                     |
| -------------------------------------------------------------- | ------------------------------------- |
| Construct objects with references; need preview before commit  | `sdk.batch()`                         |
| Full identity known; modify a few fields                       | `sdk.edit(...)`                       |
| External system pushes item list; or only have `ref + asrt_id` | `sdk.ingest(...)`                     |
| Review and materialize derived candidates                      | `sdk.evaluate(...) + sdk.accept(...)` |
| Single low-level write                                         | `sdk.set / sdk.add / sdk.retract`     |

**Decision tree**

```text
Do you need to preview the write plan (ops) first?
  ├─ Yes -> sdk.batch()
  └─ No
      ├─ Do you have full identity and only modify one entity?
      │    ├─ Yes -> sdk.edit(...)
      │    └─ No
      │         ├─ Is this writing derived candidates?
      │         │    ├─ Yes -> sdk.evaluate(...) + sdk.accept(...)
      │         │    └─ No -> sdk.ingest(...)
```

**Common mis-selections**

| Mis-selection                                                  | Correct approach                                                               |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `find(...)` cannot provide identity but you still want `edit`  | use `ingest(retract + set/add)`                                                |
| Need cross-process replay of writes                            | export wire plan via `batch.preview().to_json(sdk)`                            |
| Treat hard reserved meta as normal keys during external import | remove reserved keys; if needed, validate via `validate_provenance(...)` first |

---

## 9. Error Handling Cheat Sheet

### 9.0 Error Stratification

| Layer                          | Representative errors                                                                    | Typical trigger                                                     |
| ------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| SDK facade layer               | `SDKSchemaError` / `SDKStoreError`                                                       | invalid input shapes, constraint violations, unsupported boundaries |
| Entity read/write object layer | `EntityNotFoundError` / `FrozenSnapshotError` / `CardinalityError` / `EditorClosedError` | edit/get/snapshot/assertions                                        |
| DSL construction layer         | `SDKDSLError`                                                                            | invalid vars/Rule/Derivation construction                           |
| Core compile/execute layer     | `RuleCompileError`                                                                       | semantic constraints (e.g., RuleRef target not `expose=True`)       |
| Ingest diagnostics layer       | `result.diagnostics` (non-exception)                                                     | item-level validation failure (collect-and-stop)                    |

`SDKError` and subclasses provide structured fields: `code` (machine-readable error code), `path` (`None` if unset).

### 9.1 Common Errors Quick Reference

| Error                                            | Common trigger                                                                                                  | Suggested handling                                                                                        |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `EntityNotFoundError`                            | `sdk.edit(...)` target missing                                                                                  | verify identity; create with `sdk.batch()`; use `err.entity_type` and `err.identity_kwargs` for debugging |
| `FrozenSnapshotError`                            | assigning to `EntitySnapshot` or `assertions`                                                                   | use `sdk.edit(...)` / `sdk.ingest(...)` instead                                                           |
| `CardinalityError`                               | edit path: using `.add` on `single` or `.set` on `multi` (batch path raises `SDKStoreError` for similar misuse) | choose the correct API by cardinality                                                                     |
| `EditorClosedError`                              | using editor after `commit/rollback`                                                                            | reopen via `sdk.edit(...)`                                                                                |
| `SDKSchemaError`                                 | `get` passed non-identity field; `find` field invalid or identity incomplete                                    | fix params against schema                                                                                 |
| `SDKStoreError`                                  | type mismatch on write; unknown params to `accept`; passing string DSL to `run/evaluate`                        | check parameter types and interface boundaries                                                            |
| `SDKStoreError(code="INVALID_ROW_FORMAT")`       | invalid `row_format`                                                                                            | use `"dict"`                                                                                              |
| `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")` | Query invalid `row_format`; `row_format="instance"` but head invalid; or calling `sdk.run(...)` on Derivation   | Query use `"dict"`/`"instance"` with valid head; Derivation use `sdk.evaluate(...)`                       |
| `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`       | Query head output aliases conflict                                                                              | rename head variables                                                                                     |
| `SDKDSLError(code="QUERY_UNBOUND_VAR")`          | Query where uses unbound variables                                                                              | bind variable in head or earlier atoms                                                                    |
| `SDKDSLError`                                    | chained entity syntax; `with vars() as (u,)` no-arg unpacking                                                   | switch to supported syntax (two-step form)                                                                |
| `RuleCompileError`                               | RuleRef target not `expose=True`                                                                                | fix rule declaration                                                                                      |
| `IngestResult.diagnostics` has `error`           | invalid item structure; unknown retract `asrt_id`                                                               | fix items by `path`; any error causes whole batch to not write                                            |

### 9.2 Ingest Diagnostics Triage

```python
res = sdk.ingest(items, meta=meta)
for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])
```

Triage order: first `diagnostics` (fastest structural localization) → then `warnings` (semantic sensitive keys) → finally `written_assertion_ids`.

---

## 10. Registry

### 10.1 Initialization

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
```

**Stable contract**: choose exactly one construction method: `SDKRegistry(root_dir=...)` or `SDKRegistry(registry=...)`; passing both with inconsistent paths raises `SDKRegistryError`.

### 10.2 Apply Schema

```python
res = reg.apply_schema_classes(
    [User, Country],
    apply_request_id="req-001",
    transaction_policy="best_effort_no_rollback_v1",
)

print(res["ok"])
print(res["apply_execute"]["idempotency"]["replayed"])
```

Replaying the same `apply_request_id` uses idempotent replay (current behavior).

### 10.3 Register Rule / Derivation

```python
with vars("u", "l") as (u, l):
    rule = Rule(
        id="rule.speaks", version="1.0.0",
        select=[u, l],
        where=[Pred("speaks:language", u, l)],
        expose=True,
    )
reg.register_rule(rule)

with vars("u", "l", "n") as (u, l, n):
    drv = Derivation(
        id="drv.copy_lang", version="1.0.0",
        head=User.name(lang=l, name=n),
        where=[User(u), u.lang == l, u.name == n],
    )
reg.register_derivation(drv)
```

You can also register precompiled specs directly (skipping DSL compile):

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

**Current behavior**: multi-head Derivation is supported only in the runtime `sdk.evaluate(...)` path; `register_derivation(...)` treats Derivations as single-head. If you need to publish multi-head logic, expand it into multiple single-head derivations and register each one.

### 10.4 Read and List

```python
reg.list_rule_ids()
reg.list_derivation_ids()
reg.list_rule_versions("rule.speaks")
reg.list_derivation_versions("drv.copy_lang")
reg.get_latest_rule_spec("rule.speaks")
reg.read_rule_spec("rule.speaks", "1.0.0")
reg.get_latest_derivation_spec("drv.copy_lang")
reg.read_derivation_spec("drv.copy_lang", "1.0.0")
```

**Stable contract**: `get_latest_*` / `read_*` return `None` if the target does not exist.

### 10.5 Publish-run Queries

```python
reg.list_apply_run_ids()
reg.list_apply_runs()
reg.show_apply_run("req-001")
```

**Current behavior**: `show_apply_run(...)` returns `None` if missing; `list_apply_runs()` returns a list of apply-execute run records (`list[dict]`).

### 10.6 Unified Low-level Entry: `apply_authoring_bundle`

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    apply_request_id="req-002",
)
```

**Current behavior**: `apply_authoring_bundle(...)` is the underlying unified entry for `apply_schema_classes(...)`, suitable for batching schema/rule/derivation changes together.

### 10.7 Schema Metadata

```python
manifest = reg.read_manifest()          # registry manifest dict
entry = reg.get_schema_entry()          # schema entry metadata (dict | None)
res = reg.upsert_schema_ir(schema_ir)   # write compiled schema_ir directly
```

---

## 11. Advanced APIs

### 11.1 Bypass After Compilation

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

Suitable when you already hold compiled parameters and want to skip SDK object compilation (current behavior).

### 11.2 Package Export and Execution

```python
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

Export package format is v2; `manifest.json` contains `"export_version": "v2"`. Facts directory structure:

```text
facts/
  claim.facts
  claim_arg.facts
  meta_str.facts
  meta_int.facts
  meta_float.facts
  meta_bool.facts
  meta_time.facts
  revokes.facts
```

Float meta uses reversible serialization: export writes `repr(value)`, import reads `float(raw)`; scientific notation is a valid format.

**Stable contract**: feeding a v1 package (with `meta_num.facts` and without `export_version`) to the new reader raises an explicit `unsupported export_version` error.

### 11.3 Configurable Views (`sdk.views`)

Views define “which perspective to read data from” and affect presentation in `sdk.find()` and `sdk.run()`:

```python
from factpy_kernel.core.store.types import ViewSpec

sdk.views.create("conservative", ViewSpec(confidence_strategy="max"))
sdk.views.create("hr_only", ViewSpec(
    confidence_strategy="prefer_source",
    prefer_source="HR system",
))
sdk.views.update("conservative", ViewSpec(confidence_strategy="mean"))
sdk.views.delete("hr_only")
sdk.views.get("conservative")
sdk.views.list()
```

`sdk.views` is an in-process manager (non-persistent); after process restart it returns to the built-in `"default"` view.

**`ViewSpec` parameters**

| Parameter             | Type          | Default | Notes                                       |
| --------------------- | ------------- | ------- | ------------------------------------------- |
| `active`              | `bool`        | `True`  | whether to consider only active assertions  |
| `confidence_strategy` | `str`         | `"max"` | confidence aggregation strategy             |
| `prefer_source`       | `str \| None` | `None`  | only effective for `prefer_source` strategy |

**Confidence aggregation strategies**

| Strategy          | Semantics                                             |
| ----------------- | ----------------------------------------------------- |
| `"max"`           | take the highest confidence (default)                 |
| `"mean"`          | arithmetic mean                                       |
| `"median"`        | median                                                |
| `"prefer_source"` | prefer `prefer_source`; if no hit, fall back to `max` |

**Scope**: `confidence_strategy` only affects presentation in `sdk.find()` / `sdk.run()`, not inference. `sdk.evaluate()` does not accept `view`.

**`sdk.run(..., view=...)` output contract** (stable contract)

* Default: returns `rows` (`list[dict]` or `list[tuple]`), without injecting `confidence` into row objects.
* With `return_display_meta=True`: returns `(rows, display_meta)`.
* `display_meta` has the same length as `rows`; each item contains at least `confidence`, `confidence_strategy`, `source_breakdown`.
* `return_display_meta=True` must be used with `view`, otherwise raises `SDKStoreError`.

### 11.3.1 End-to-end Example: How `find` and `run` Obtain Confidence

```python
from factpy_kernel.core.store.types import ViewSpec

# 1) register a view (mean strategy)
sdk.views.create("risk_mean", ViewSpec(confidence_strategy="mean"))

# 2) find: get the aggregated value on snapshot objects
users = sdk.find(User, lang="zh", view="risk_mean")
print(users[0].confidence)  # e.g., 0.73

# 3) run: does not inject confidence by default
rows = sdk.run(speaks_rule, view="risk_mean", row_format="dict")
print(rows[0])  # {"u": "...", "l": "..."}

# 4) run + return_display_meta: obtain display meta
rows, display_meta = sdk.run(
    speaks_rule,
    view="risk_mean",
    row_format="dict",
    return_display_meta=True,
)
print(display_meta[0]["confidence"])           # e.g., 0.73
print(display_meta[0]["confidence_strategy"])  # "mean"
print(display_meta[0]["source_breakdown"])     # aggregation by source
```

**Built-in view**: `"default"` (`active=True, confidence_strategy="max"`), cannot be deleted.

**Inline views** (temporary, not stored):

```python
sdk.find(User, view=ViewSpec(confidence_strategy="mean"))
sdk.run(rule, view="conservative", row_format="dict")
sdk.run(rule, view=ViewSpec(confidence_strategy="max"), row_format="dict")

rows, display_meta = sdk.run(
    rule,
    view="conservative",
    row_format="dict",
    return_display_meta=True,
)
```

Service `runtime_v1` view-management endpoints (current implementation):

| Method | Endpoint                                         |
| ------ | ------------------------------------------------ |
| `POST` | `/v1/runtime/sessions/{session_id}/views/create` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/update` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/delete` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/get`    |
| `GET`  | `/v1/runtime/sessions/{session_id}/views`        |

### 11.4 ProbLog Probabilistic Inference

```python
from factpy_kernel.sdk import Body
import factpy_kernel.adapters.problog

with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.infer_speaks",
        version="1.0.0",
        where=[
            Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
            Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
        ],
        head=Speaks(user=u, language=lang),
    )

cands = sdk.evaluate(drv, mode="problog")
res = sdk.accept(cands[0], approved_by="alice")
```

**`CandidateSet.confidence` field** (new in v3)

* Type: `float | None`
* ProbLog path: marginal probability; native/souffle path: `None`
* Fully preserved through serialization/deserialization; not lost across processes

**accept semantics** (v3 update)

* Duplicate is determined by: same claim, and same business-semantic meta (after excluding timestamp/run/candidate identifier fields)
* Assertions for the same fact with different `confidence` or different `source` can coexist; they will not be misclassified as duplicates

**Current boundary**

* If ProbLog CLI is unavailable or times out: raises `ProbLogEngineError`.
* If export-stage structure is unsupported or params invalid: raises `ProbLogExportError`.
* If result parsing fails: raises `ProbLogImportError`.
* Within the same inference batch (same `run_id/trace_id`), repeatedly writing the same claim does not force coexistence solely due to `confidence` changes; coexistence is still constrained by ingest idempotency keys.

### 11.5 Debug Attributes

```python
sdk.store        # underlying Store object
sdk.ledger       # underlying Ledger object
sdk.schema_ir    # compiled schema actually used by the current store
```

### 11.6 Audit Queries

```python
audit = sdk.explain_fact("user:age", alice_ref)
conf = sdk.conflicts("user:age", alice_ref)
```

Both are computed over the current active assertion set (**stable contract**).

`explain_fact(pred_id, e_ref, *val_atoms)` returns (current behavior):

* `pred_id`, `e_ref`
* `active_claims`: `list[dict]`, each includes `asrt_id`, `args`, `meta`
* `chosen_asrt_id`

`*val_atoms` filters `active_claims` by “exact value-atom match”.

`conflicts(pred_id, e_ref)` returns (current behavior):

* `pred_id`
* `active_asrt_ids`
* `chosen_asrt_id`

`pred_id` takes a predicate id (e.g., `"user:age"`); `e_ref` takes a canonical `idref_v1` token.

---

## 12. Migration Notes (v2 → v3)

### EvaluateMode Renaming

| Old        | New         | Behavior when passing old value   |
| ---------- | ----------- | --------------------------------- |
| `"python"` | `"native"`  | explicit error; suggests new name |
| `"engine"` | `"souffle"` | explicit error; suggests new name |
| ——         | `"problog"` | new in v3                         |

Default values are also updated to `"native"` (including authoring DTO/session and SDK derivation evaluate paths).

### meta kind Renaming + Addition

| Old     | New       | Notes                             |
| ------- | --------- | --------------------------------- |
| `"num"` | `"int"`   | integer; write validation updated |
| ——      | `"float"` | new in v3; used by `confidence`   |

`Ledger.META_KINDS` has been updated from `{"str","num","bool","time","json"}` to `{"str","int","float","bool","time","json"}`. Code writing `kind="num"` must change to `kind="int"` (write validation will raise a clear error).

### Export Package Format Upgrade (v1 → v2)

| v1                  | v2                                                |
| ------------------- | ------------------------------------------------- |
| `meta_num.facts`    | `meta_int.facts`                                  |
| ——                  | `meta_float.facts` (new)                          |
| no `export_version` | `manifest.json` includes `"export_version": "v2"` |

Feeding a v1 package to a v2 reader raises an explicit error: `unsupported export_version: 'v1'; expected 'v2'`.

### accept Semantics Change

| Old                                                                   | New                                                                        |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| duplicate check only considers claim (`pred_id + e_ref + rest_terms`) | also compares business-semantic meta (excluding timestamp/run identifiers) |
| same fact with different confidence was misclassified as duplicate    | naturally coexists; no longer misclassified                                |

### Body DSL (new)

```python
# v2 style (still supported)
where=[[atom1, atom2], [atom3]]

# v3 style (when confidence is needed)
from factpy_kernel.sdk import Body
where=[
    Body([atom1, atom2], confidence=0.9),
    Body([atom3], confidence=0.6),
]
# mixing the two forms is forbidden
```

### `run(view)` Result Contract Tightening

| Old assumption                                               | v3 actual behavior                                                                                      |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `sdk.run(rule, view=...)` might include `confidence` in rows | by default it does not inject fields into row objects; return type remains consistent with `row_format` |
| ——                                                           | to obtain aggregated confidence, use `return_display_meta=True`, which returns `(rows, display_meta)`   |

### Schema Layer (v1 → v2, historical)

* `Field.cardinality`: `"functional"` / `"temporal"` → `"single"`
* `Field.dims`, `Field.fact_key`, `Field.pred_id` removed
* `Identity(primary_key=True)` is required for cross-coordinate joins
* `sdk_batch_plan_v1` wire payload no longer carries `dims` / `fact_key`
