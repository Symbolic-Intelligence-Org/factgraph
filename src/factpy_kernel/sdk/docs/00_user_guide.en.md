# FactPy SDK User Guide

> This document describes implemented behavior; unimplemented capabilities are explicitly marked as "current boundaries."
> Behaviors in this document are classified using three labels: **stable contract** (recommended for strong assertion tests), **current behavior** (subject to evolution), and **planned** (not yet implemented).

---

## Table of Contents

1. [Installation and Initialization](#1-installation-and-initialization)
2. [Schema Definition](#2-schema-definition)
3. [Writing Data](#3-writing-data)
4. [The `meta` Field](#4-the-meta-field)
5. [Reading Data](#5-reading-data)
6. [Rule / Query / Derivation](#6-rule--query--derivation)
7. [Provenance Validation](#7-provenance-validation)
8. [Which Write Entry Point Should I Choose?](#8-which-write-entry-point-should-i-choose)
9. [Quick Error Handling Reference](#9-quick-error-handling-reference)
10. [Registry](#10-registry)
11. [Advanced APIs](#11-advanced-apis)
12. [Migration Notes (v2 → v3)](#12-migration-notes-v2--v3)

---

## 1. Installation and Initialization

### 1.1 Initializing a Store

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

If persistence is needed, specify `ledger_path`:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

If you also want explain artifacts to survive across later `SDKStore` instances, add `artifact_store_root`:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
    artifact_store_root="./data/artifacts",
)
```

If you want Rule query results to default to dict rows:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    default_row_format="dict",
)
```

**Stable contract**

* `classes` must be a non-empty `list[Entity subclass]`; the `from_schema_classes(...)` / `schema_preflight_from_classes(...)` path raises `SDKSchemaError`, while the `SDKStore(...)` constructor path raises `SDKStoreError`.
* `ledger` and `ledger_path` are mutually exclusive; they cannot be provided at the same time.
* `ledger_path` records `schema_digest` when opening/creating the ledger; it is validated on reopening, and a mismatch raises `SDKStoreError`.
* `artifact_store_root` is an optional `str`; when provided it enables sidecar-backed explain artifact readback across later `SDKStore` instances, and when omitted the default in-process explain-registry behavior remains unchanged.
* `default_row_format` only affects `sdk.run(rule, ...)`; valid values are `"tuple"` / `"dict"`, with default `"dict"`.
* When the parsed result is `"tuple"`, a `DeprecationWarning` is triggered; it is recommended to standardize on `"dict"`.
* The `FACTPY_ROW_FORMAT` environment variable is read and cached during `SDKStore` initialization (not dynamically read on each `run()`).

### 1.2 Schema Preflight

In scenarios where a runtime store is not needed (CI validation, module import phase), you can perform preflight separately:

```python
from factpy_kernel.sdk import schema_preflight_from_classes

preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])
print(preflight.get("warnings", []))
print(preflight.get("summary", {}))   # entity_count / predicate_count / pred_ids
```

**Stable contract**: returns a `dict`; core keys include `ok`, `warnings`, `errors`, `diagnostics`, and `summary` (on success).

---

## 2. Schema Definition

### 2.1 Basic Structure

```python
from factpy_kernel.sdk import Entity, Identity, Field

class User(Entity):
    """When description is not explicitly set, the docstring is used as a fallback."""

    class Meta:
        version = "v1"
        description = "User entity"
        tags = ["user", "profile"]

    user_id: str = Identity(primary_key=True, default_factory="uuid4")
    lang: str = Identity()

    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
    country: Country = Field(cardinality="single")
```

`Identity` locates a fact, while `Field` carries that fact’s value. On the read side, there is limited symmetry: snapshot **value access** (`snap.lang`, `snap.name`) is consistent for both; however, `snap.assertions.lang` is unavailable — the `assertions` namespace only covers `Field` fields, not `Identity` fields. On the write side, the distinction is explicit: calling `.set()` / `.add()` on an `Identity` field raises an exception.

**Stable contract**: every `Entity` must define at least one `Identity`, otherwise `SDKSchemaError` is raised at class definition time.

**Current behavior**

* `entity_type` is derived directly from the class name; no separate `schema_id` declaration is needed.
* `Entity.Meta` currently supports only `version`, `description`, and `tags`; any other keys raise `SDKSchemaError` at declaration time.
* Description resolution priority is `Meta.description > class docstring`; docstring is only used when no explicit `description` is provided.
* `version`, `description`, and `tags` are included in authoring / schema compilation output, but do not participate in runtime evaluation semantics.

### 2.2 Identity Parameters

| Parameter                 | Meaning                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `primary_key=True`        | Marks a join anchor; implicitly carried across Fields during Rule inference, and does not appear in the head |
| `default`                 | Static default value                                                                                         |
| `default_factory="uuid4"` | Automatically generates a UUID when absent                                                                   |

`primary_key=True` and `default_factory` are orthogonal — the former declares semantic responsibility, the latter declares a generation strategy. They may be used together or separately. For an Entity without any `primary_key=True` field, if cross-Field joins appear in a Rule, compilation fails.

**Recommendation**: `Identity` fields should point to business attributes of the entity (such as `user_id`, `lang`), rather than data management dimensions such as `source` or `version`. The latter belong in `meta`, not in `Identity`. This is a design recommendation only; the engine does not enforce it.

### 2.2.1 Declaration Metadata

Declaration metadata for an `Entity` is uniformly provided via `Meta`:

| Key           | Meaning                                       |
| ------------- | --------------------------------------------- |
| `version`     | Declaration version                           |
| `description` | Entity description for documentation and LLMs |
| `tags`        | Lightweight classification tags               |

```python
class EmploymentEvent(Entity):
    """If Meta.description is absent, this will be used as the description."""

    class Meta:
        version = "v2"
        description = "Employment event"
        tags = ["employment", "event"]

    event_id: str = Identity(primary_key=True)
    company: str = Field(cardinality="single")
```

**Current boundary**: `Meta` is not an open dictionary; fields such as `owner`, `llm_hint`, or `schema_id` are currently unsupported.

### 2.3 Field Parameters

| Parameter              | Meaning                                                                            |
| ---------------------- | ---------------------------------------------------------------------------------- |
| `cardinality="single"` | Single-valued view: reading `snap.<field>` returns a scalar; writing uses `.set()` |
| `cardinality="multi"`  | Multi-valued; all values at the same coordinate are retained                       |
| `description`          | Descriptive text for documentation and LLMs                                        |

**Current behavior supplement**: `single` does not automatically clean up old assertions during writes; multiple unretracted assertions may still appear in `active/history`, while `snap.<field>` returns the current single-valued view.

**Current boundary**: `dims` / `fact_key` / `pred_id` / `functional` / `temporal` have been removed.

### 2.4 Reified Record (Relationship Node)

All entities are based on `Entity`; relationship nodes are merely a usage convention:

```python
class LivesIn(Entity):
    uid: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")
```

**Stable contract**: after compilation, the schema generates a `<T>:exists` predicate for every `Entity`; batch field writes automatically insert the corresponding `<T>:exists` write op.

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

**Current behavior**: string annotations are also supported (such as `"str"`, `"datetime"`, `"uuid"`, `"entity_ref"`); unrecognized annotations fall back to `entity_ref`.

### 2.6 In-Memory Objects vs Managed Objects

```python
# Ordinary in-memory object (not bound to a store)
alice = User(user_id="u-001")
alice.name = "Alice"      # ordinary Python assignment

# sdk.batch-managed object (supports .set/.add/.retract)
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice_h = tx.entity(User, user_id="u-001", lang="zh")
    alice_h.name.add("Alice")
    tx.commit()
```

**Stable contract**: `.set` / `.add` / `.retract` are capabilities of batch/edit managed handles, not of ordinary in-memory objects.

---

## 3. Writing Data

### 3.1 `sdk.batch`

Primary entry point for batch writes; suitable for ETL, sample data construction, and scenarios requiring preview / wire plan.

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "hr"}) as tx:
    de = tx.entity(Country, iso_code="DE")
    de.name.set("Germany")

    # Provide all Identity fields at once
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")
    u.age.set(30)
    u.country.set(de)   # can directly reference a handle within the same tx

    # Or bind Identity step by step
    u2 = tx.entity(User, user_id="u-002")
    u2 = u2.bind(lang="en")
    u2.name.add("Alicia")

    plan = tx.preview()   # read-only preview, does not persist
    res = tx.commit()     # actual write
```

The `meta` of `batch` is inherited by all write operations; individual operations may override it with their own `meta`:

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")                                  # inherits batch meta
    u.name.add("Alice", meta={"valid_from": "2024-06"})    # per-operation override
    tx.commit()
```

**Meta merge precedence** (higher overrides lower): `commit_meta > field_op_meta > entity_meta > batch_meta`

**Stable contract**

* Use `.set()` for `single` fields and `.add()` for `multi` fields; misuse raises `SDKStoreError` (batch handle path), while the `sdk.edit` path raises `CardinalityError`.
* Batch handles use `.retract(assertion_id)` for retraction; `FieldEditor` in edit uses `.retract(asrt_id=...)`; neither supports value-based retraction.
* If Identity is incomplete, `.set()` / `.add()` immediately raises `SDKStoreError` (the error message lists missing fields; use `bind(...)` first to complete them).
* Calling `.set()` / `.add()` on an Identity field immediately raises `SDKStoreError` — once determined, Identity is immutable.
* `preview()` does not persist and may be called repeatedly; only `commit()` persists.
* The `SDKBatchTx` context manager itself does not auto-commit or auto-rollback (`__exit__` is a no-op); callers must explicitly call `commit()`, and exception handling is also the caller’s responsibility.

**`entity_ref` fields** (stable contract): may accept a "same-tx handle" or a "canonical idref_v1 token"; ordinary business strings (such as `"DE"`) are not allowed.

**Field cardinality quick reference**

| Field type | Allowed                                                           | Forbidden                                                           |
| ---------- | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| `single`   | `.set(value)`                                                     | `.add(value)` → `SDKStoreError` (batch) / `CardinalityError` (edit) |
| `multi`    | `.add(value)`                                                     | `.set(value)` → `SDKStoreError` (batch) / `CardinalityError` (edit) |
| any        | `.retract(assertion_id)` (batch) / `.retract(asrt_id=...)` (edit) | value-based retraction (unsupported)                                |

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

# replay across process/time
from factpy_kernel.sdk.batch import WireBatchPlan

plan2 = WireBatchPlan.from_json(wire_json)
plan2.apply(sdk, strict_schema=True)
```

**Current behavior**: `strict_schema=True` checks that the wire plan’s `schema_digest` matches the current SDK schema.

**Current behavior supplement**: wire export (`to_json` / `export`) does not accept raw `idref_v1` string values as `entity_ref` writes; to build replayable wire plans, use "same-tx handle references" in batch to express entity relationships.

### 3.3 Dependency Closure (`include_deps`)

By default, `include_deps=True`: committing an object automatically includes all dependency objects it references. Missing dependencies are not silently skipped; an error is raised directly (**stable contract**).

### 3.4 `sdk.edit`

Suitable for scenarios where the full Identity is known and only a small number of fields need modification:

```python
with sdk.edit(User, user_id="u-001", lang="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
    # normal exit from with: auto commit()
    # exception inside with block: auto rollback()
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

* If the entity does not exist, raises `EntityNotFoundError` (no implicit creation; use `sdk.batch()` for creation).
* After `commit()` or `rollback()`, the editor is closed; any further method call raises `EditorClosedError`.

### 3.5 `sdk.ingest`

Suitable for external imports or scenarios where only `ref + asrt_id` is available (without full Identity):

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

* Top-level `meta` is merged with item `meta`, with item keys overriding top-level keys of the same name.
* `kind=set` corresponds to `single` fields; `kind=add` corresponds to `multi` fields.
* If any `diagnostics` entry has `severity="error"`, the entire batch is not written (collect-and-stop).
* `allow_sensitive_meta=True` only suppresses sensitive warnings; it does not relax hard reserved constraints.

### 3.5.1 Typical Scenario: Entity Migration

When full Identity cannot be obtained via `find`, `ingest` serves as a fallback:

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

### 3.6 Low-Level Write Entry Points

```python
alice_ref = sdk.ref(User, user_id="u-001", lang="zh")
sdk.set(User.age, alice_ref, 31, meta={"source": "hr"})
sdk.add(User.name, alice_ref, "Alicia", meta={"source": "hr"})
sdk.retract("asrt_xxx", meta={"source": "hr"})
```

Minimal wrapping, directly writes to the ledger, with no preview/wire support.

**Current behavior**

* `sdk.set(...)` / `sdk.add(...)` only backfill the corresponding Identity predicate if the identity values of `e_ref` have already been recorded by the current `SDKStore`; arbitrary external canonical `idref_v1` values are not guaranteed to be auto-backfilled.
* `sdk.retract(...)` returns the revoker assertion id; if the target assertion has already been revoked, it returns the existing revoker id; if the assertion does not exist, it raises an error.

---

## 4. The `meta` Field

`meta` is not a free dictionary. Fields are grouped into four categories by responsibility:

**System-reserved (written by the ingest process, not user-writable)**

`ingested_at`, `ingest_key`, `revoked_asrt_id`

**Operation tracing (conventional fields, recommended)**

`source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`

**Derivation chain (automatically written by the accept process)**

`derived_rule_id`, `derived_rule_version`, `run_id`, `support_digest`, `support_kind`, `candidate_id`, `candidate_key`, `accepted_at`, etc.

**Business temporal fields (used to unlock temporal views)**

`valid_from`, `valid_to`, `version`

Business temporal fields are user-writable, recognized by the view layer, but not enforced. If omitted, only `.active` / `.history` views are available; once provided, `.at(t)` / `.version(v)` queries are enabled.

**Meta key stratification** (stable contract)

| Level              | Representative fields                                                         | Behavior                                   |
| ------------------ | ----------------------------------------------------------------------------- | ------------------------------------------ |
| hard reserved      | `ingested_at`, `ingest_key`, `revoked_asrt_id`                                | user cannot write                          |
| sensitive semantic | derivation-chain fields such as `derived_rule_id`, `run_id`, `support_digest` | warning by default, does not block writing |
| convention         | `source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`       | normal write                               |
| free               | business-defined custom keys                                                  | normal write                               |

**Meta kind system** (v3 update)

Meta numeric fields are stored by kind; kind names were renamed and extended in v3:

| kind      | Type    | Description                                                      |
| --------- | ------- | ---------------------------------------------------------------- |
| `"str"`   | `str`   | string                                                           |
| `"int"`   | `int`   | integer (formerly `"num"`, renamed in v3)                        |
| `"float"` | `float` | floating point (new in v3, used for fields such as `confidence`) |
| `"bool"`  | `bool`  | boolean                                                          |
| `"time"`  | `int`   | epoch nanosecond timestamp                                       |
| `"json"`  | `Any`   | JSON-serializable object                                         |

The kind of the `confidence` field is fixed to `"float"` and is inferred automatically by the write protocol; the user does not need to specify it.

`kind` is not visible to the caller: the write protocol first performs forced mapping using conventional keys (`_KEY_KIND_MAP`), then infers unknown keys from value types.
Coverage checks for conventional keys are performed at module load time (all `convention + sensitive` keys must exist in the mapping table).

Type inference rules for unknown keys (conventional keys take precedence over these rules):

* `bool` → `"bool"`
* `int` → `"int"`
* `float` → `"float"`
* `str` → `"str"`
* other types are unsupported and raise `WriteProtocolError`

**Stable contract (`confidence`)**

* `meta["confidence"]` must be a `float` with value in `(0, 1]`.
* `int` values (such as `1`) are not automatically promoted to `float`; they raise an error directly.

### 4.1 Common Examples (`confidence`)

```python
from factpy_kernel.core.store.types import ViewSpec

alice_ref = sdk.ref(User, user_id="u-001", lang="zh")

# ✅ valid: float and within (0,1]
sdk.set(User.age, alice_ref, 30, meta={"source": "hr", "confidence": 0.82})
sdk.set(User.age, alice_ref, 30, meta={"source": "model_v2", "confidence": 0.64})

# ❌ invalid: int is not auto-promoted to float
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1})      # WriteProtocolError

# ❌ invalid: out of range
sdk.set(User.age, alice_ref, 30, meta={"confidence": 1.2})    # WriteProtocolError

# aggregate by view during reading
row_max = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="max"))[0]
row_mean = sdk.find(User, user_id="u-001", lang="zh", view=ViewSpec(confidence_strategy="mean"))[0]
print(row_max.confidence)   # 0.82
print(row_mean.confidence)  # 0.73
```

**Deduplication basis**: `claim + source + source_loc + trace_id + valid_from + valid_to + version`

**Boundary note (important)**

* `confidence` does not participate in the ingest idempotency key.
* Therefore, under the same `trace_id` (in the accept path this typically equals the same `run_id`), if the claim and all other deduplication fields are identical, differing only in `confidence`, no new assertion is created; it is folded by idempotency.
* Coexistence of “same fact, different `confidence`” usually occurs across different reasoning batches (different `run_id/trace_id`) or different source fields (`source/source_loc`).

Note: `ingested_at` is the system write time, not the same as `valid_from` (business effective time). Using `ingested_at` in place of `valid_from` for temporal views causes semantic misalignment.

**Semantics of `trace_id`**: `trace_id` participates in idempotency calculation, but is not the sole determining factor; `valid_from` / `valid_to` / `version` also participate in deduplication. Under the same `trace_id`, different temporal dimensions still produce different assertions.

---

## 5. Reading Data

### 5.1 `sdk.get`

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

if snap is None:
    print("Does not exist")
else:
    print(snap.ref)                 # canonical idref_v1 token
    print(snap.entity_type)         # "User"
    print(snap.identity_available)  # True
    print(snap.identity)            # can be used as identity kwargs for sdk.edit(...)
```

**Stable contract**

* `get` accepts only Identity parameters; passing non-Identity fields raises `SDKSchemaError`.
* Returns `EntitySnapshot | None`.
* Snapshots returned via `get` have `identity_available=True`.

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
* When filtering by Identity, all Identity fields of that entity must be provided.
* `temporal_view` is not supported.
* Passing an unknown filter field raises `SDKSchemaError`.

**Current boundary**

* The `confidence_strategy` in the `view` parameter only affects the displayed `confidence` value in the returned result, not which assertions are returned.

**Identity availability in `find` results** (current behavior)

```python
records = sdk.find(LivesIn, user=alice_ref)
for rec in records:
    if rec.identity_available:
        with sdk.edit(LivesIn, **rec.identity) as editor:
            ...
    else:
        # use ingest: retract/set via rec.ref + asrt_id
        ...
```

* Without an identity filter: snapshots usually have `identity_available=False`.
* With a complete identity filter: returned snapshots have `identity_available=True`.

### 5.3 Assertion Views on `EntitySnapshot`

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

# current-view values
snap.name      # multi -> tuple[...]
snap.age       # single -> scalar or None
snap.country   # single entity_ref -> idref_v1 token or None

# assertion views
snap.assertions.name.active           # currently unretracted assertions
snap.assertions.name.history          # complete history (including revoked)
snap.assertions.name.at("2024-03-01") # business temporal filter
snap.assertions.name.version("v2")    # version filter
snap.field("name").active             # equivalent form
```

**View semantics** (stable contract)

| View          | Semantics                                                                          |
| ------------- | ---------------------------------------------------------------------------------- |
| `.active`     | currently unretracted, maintained by the store registry mechanism                  |
| `.history`    | complete history, including revoked assertions                                     |
| `.at(t)`      | over the active set: `valid_from <= t` and (`valid_to` is empty or `valid_to > t`) |
| `.version(v)` | over the active set: `version == v`                                                |

**Temporal view boundaries**

* Assertions missing `valid_from` do not match `.at(t)` and only appear in `.active`.
* Assertions missing `version` do not match `.version(v)`.
* `.at(t)` validates ISO 8601 format (both the `t` argument and the assertion’s `valid_from`/`valid_to` are validated); invalid format raises `SDKStoreError`.
* `.version(v)` only accepts `str | int` (`bool` is invalid).
* Temporal filtering is applied on top of the active set, not drawn from history.
* `EntitySnapshot` and the `assertions` namespace are both read-only; assignment raises `FrozenSnapshotError`.

---

## 6. Rule / Query / Derivation

### 6.1 Variable Declaration

```python
from factpy_kernel.sdk import vars

# recommended form
with vars("u", "l", "n") as (u, l, n):
    ...

# factory form
with vars() as V:
    u, l, n = V("u", "l", "n")
```

**Stable contract**: `with vars() as (u, l)` without-argument unpacking is not supported and raises `SDKDSLError`.

### 6.2 Rule: Immediate Query

```python
from factpy_kernel.sdk import Rule, Pred, Not, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_rule = Rule(
        id="q_speaks",
        version="1.0.0",
        description="Find languages a user may speak",
        tags=["demo", "query"],
        select=[u, l],
        where=[
            LivesIn(li),
            li.user == u,      # two-step form (chained form unsupported)
            li.country == c,
            HasLanguage(hl),
            hl.country == c,
            hl.language == l,
        ],
    )

rows = sdk.run(speaks_rule, row_format="dict")
# [{"u": "...", "l": "..."}, ...]

rows = sdk.run(speaks_rule, view="default", row_format="dict")
# by default returns rows, without injecting confidence into each row

rows, display_meta = sdk.run(
    speaks_rule,
    view="default",
    row_format="dict",
    return_display_meta=True,
)
# display_meta has the same length as rows; each item contains at least confidence / confidence_strategy / source_breakdown
```

**Stable contract**

* Chained syntax such as `LivesIn(li).user == u` is unsupported; use the two-step form.
* OR uses `where=[[...], [...]]` (OR-of-AND).
* `row_format` precedence has three levels: `run(..., row_format=...) > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`.
* Invalid `row_format` raises `SDKStoreError(code="INVALID_ROW_FORMAT")`.
* `RuleRef` targets must have `expose=True`, otherwise `RuleCompileError` is raised; `RuleRef` is not allowed inside `Not(...)`.
* `view` may be a named view or a `ViewSpec`, and only affects result presentation, not Rule evaluation scope.
* `sdk.run(rule, view=...)` returns only `rows` by default, without injecting `confidence` into each row.
* With `return_display_meta=True`, the return value is `(rows, display_meta)`; `view` must also be provided, otherwise `SDKStoreError` is raised.
* `Rule` supports two declaration fields: `description` and `tags`; they are included in compiler output, but do not affect query semantics.

**Current behavior**: linear arithmetic `+/-/constant multiples` is supported (such as `age == (2026 - by)`); non-linear multiplication such as `x * y` is unsupported.

### 6.3 Body: OR Branches with Confidence

In probabilistic reasoning scenarios, OR branches may be wrapped with `Body` and assigned branch confidence:

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

* `Body.confidence` must be in `(0, 1]`; `confidence=0` causes a compile-time error.
* `Body.confidence=None` is valid (meaning no confidence constraint).
* Mixing `Body(...)` and raw list branches in the same `where` is forbidden; violation causes compilation failure.
* Raw list form is retained; after compilation, `body_confidences=None`, and behavior remains as before.

**Supported scope**

* Rule: supports `Body(...)`, currently only for where normalization; `body_confidences` do not participate in Rule runtime evaluation.
* Derivation: supports `Body(...)`; after compilation, `body_confidences` are extracted into a sidecar for `mode="problog"`.
* Query: `Body.confidence` is unsupported and causes an error at construction time.

`body_confidences` pass-through path:
`SDK Derivation/authoring payload -> compile_authoring_derivation_v1 -> sdk.evaluate -> evaluate_store -> engine(problog)`.

### 6.3.1 Example of `Body` Mode Differences

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

# native: ignores body_confidences (same behavior as raw lists)
cands_native = sdk.evaluate(drv, mode="native")
print(cands_native[0].confidence)  # None

# problog: consumes body_confidences and returns probabilities
import factpy_kernel.adapters.problog
cands_prob = sdk.evaluate(drv, mode="problog")
print(cands_prob[0].confidence)    # float, e.g. 0.86
```

```python
# ❌ mixing Body and raw list (compile-time error)
with vars("u") as (u,):
    Rule(
        id="r.bad",
        version="1.0.0",
        select=[u],
        where=[Body([Pred("p", u)], confidence=0.9), [Pred("q", u)]],
    )
```

### 6.4 Query DSL

Identity and Field fields use exactly the same access syntax inside `where` clauses:

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

rows = sdk.run(q)   # default return type is list[dict]
```

**Stable contract**

* Query supports `row_format="dict"|"instance"`; default is `"dict"`.
* `row_format="instance"` is only valid when the head is a single `Entity(var)`; it returns `list[EntitySnapshot|None]`.
* If the Query head shape does not satisfy instance constraints, or if Query uses an invalid `row_format`, `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")` is raised.
* Valid head forms: `Entity(var)`, `[Entity(var1), ...]`, `Entity.field(...)`.
* Query performs alias conflict validation at construction time (raising `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`) and where-variable binding validation (raising `SDKDSLError(code="QUERY_UNBOUND_VAR")`).
* Entity head columns return `EntitySnapshot`; field projection columns return scalar values.
* `Query.where` does not support `Body.confidence`; passing it causes a compile-time error.
* `sdk.run(query, view=...)` is unsupported (raises `SDKStoreError`).
* `sdk.run(query, return_display_meta=True)` is unsupported (raises `SDKStoreError`).

**Current behavior**: `on_missing` / `on_type_mismatch` strategies:

* `error`: raises `SDKStoreError` (`QUERY_MISSING_REF` / `QUERY_TYPE_MISMATCH`)
* `skip`: drops the row
* `null`: sets that column to `None`, while keeping the row (it still participates in deduplication)

### 6.5 Derivation

```python
from factpy_kernel.sdk import Derivation, vars

with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    speaks_drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        description="Infer a user's language ability from residence and official language",
        tags=["demo", "derivation"],
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
    )

cands = sdk.evaluate(speaks_drv, mode="native")   # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="alice")

# atomic submission of multiple candidate sets
res = sdk.accept_many(cands, mode="atomic")
```

**Valid `mode` values** (stable contract, v3 update)

| mode        | Description                                              |
| ----------- | -------------------------------------------------------- |
| `"native"`  | Python built-in evaluator (formerly `"python"`, renamed) |
| `"souffle"` | Soufflé engine (formerly `"engine"`, renamed)            |
| `"problog"` | ProbLog probabilistic reasoning engine (new in v3)       |

Passing old names `"python"` / `"engine"` raises a clear error and suggests the new name.

The engine uses a name registry (not a singleton): `register_engine_evaluator(name -> fn)`.
Adapters auto-register upon import:

* `import factpy_kernel.adapters.souffle` registers `"souffle"`
* `import factpy_kernel.adapters.problog` registers `"problog"`

**Stable contract**

* `sdk.evaluate(...)` produces candidates and does not write to the ledger; only `sdk.accept(...)` writes.
* Multi-head `head=[H1, H2, ...]` is supported; `evaluate` returns flattened results sharing the same `run_id`.
* `sdk.accept(CandidateSet, ...)` accepts exactly one positional argument; allowed override keys are `approved_by`, `note`, `dry_run`, `identity_override` (also accepted via `meta_overrides`); unrecognized parameters raise `SDKStoreError`.
* `sdk.run(Derivation(...))` is unsupported; use `sdk.evaluate(...)`.
* `sdk.evaluate(..., view=...)` is unsupported; passing it raises `SDKStoreError` (reasoning always operates over the full active assertion set).
* If a dependency graph exists, `sdk.accept_many(..., mode="atomic")` should be preferred to guarantee atomicity.
* `Derivation` supports two declaration fields, `description` and `tags`; they are included in compiler output, but do not affect candidate generation semantics.

### 6.5.1 Example of `accept` Idempotency and Coexistence

```python
from dataclasses import replace
import factpy_kernel.adapters.problog

cands = sdk.evaluate(speaks_drv, mode="problog")
cand = cands[0]

# first write
r1 = sdk.accept(cand, approved_by="alice")
print(r1.accepted_count, r1.skipped_count)  # 1, 0

# writing the exact same candidate again: idempotently skipped
r2 = sdk.accept(cand, approved_by="alice")
print(r2.accepted_count, r2.skipped_count)  # 0, 1
print(r2.skipped_reason_counts)             # {"duplicate": 1}

# same claim, different confidence: coexistence (not duplicate)
cand_v2 = replace(cand, confidence=0.61)
r3 = sdk.accept(cand_v2, approved_by="alice")
print(r3.accepted_count, r3.skipped_count)  # 1, 0
```

**Current boundary**

* Temporal write semantics in Derivation heads (heads directly producing assertions with `valid_from`/`valid_to`/`version`) are not yet exposed. Temporal information can currently only be carried via `meta` in write paths (`sdk.batch` / `sdk.ingest`).

### 6.6 Identity Rules in the Head

```text
fields appearing in the head = all non-primary Identity fields + the target Field value
```

* **`primary_key` fields**: regardless of how many there are, they never appear in the head and are implicitly carried by entity bindings in the where clause.
* **Non-primary Identity fields**: must be explicitly specified in the head, otherwise the write target is ambiguous.

```python
# User has primary_key=user_id, non-primary Identity=lang
head=User.name(lang=l, name=n)   # user_id does not appear, lang must be given
```

It is a compile-time hard error for a `primary_key` field to appear in the head.

### 6.7 Cross-Coordinate Joins

Two facts of the same entity at different coordinates are represented as two different variables in a Rule, explicitly joined via `primary_key`:

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

* Only `primary_key` fields may participate in `==` comparisons for cross-coordinate joins.
* Equality comparisons across coordinates using non-`primary_key` fields are compile-time hard errors; the error message indicates which `primary_key` should be used instead.
* Cross-entity-type comparisons are compile-time hard errors.

### 6.8 Current Limitations of Rule / Derivation

| Limitation                                   | Description                                                |
| -------------------------------------------- | ---------------------------------------------------------- |
| String DSL                                   | `sdk.run("...")` / `sdk.evaluate("...")` unsupported       |
| `sdk.run(Derivation(...))`                   | unsupported; use `sdk.evaluate(...)`                       |
| Chained path comparisons                     | `LivesIn(li).user == p` unsupported; use two-step form     |
| Cross-coordinate non-primary_key comparisons | compile-time hard error                                    |
| Non-linear arithmetic                        | `x * y` unsupported                                        |
| `Not(...)` body                              | must be non-empty; safety checks apply with outer bindings |
| `RuleRef` inside `Not(...)`                  | compile-time error                                         |

---

## 7. Provenance Validation

`sdk.validate_provenance(...)` is a pure validation entry point. It does not write to the ledger and does not automatically block ingest/accept.

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

Optional keys `schema_digest` / `policy_digest` with invalid formats are written to `warnings` (not `errors`).

---

## 8. Which Write Entry Point Should I Choose?

| Scenario                                                                | Recommended entry point               |
| ----------------------------------------------------------------------- | ------------------------------------- |
| Constructing objects with references, and previewing before commit      | `sdk.batch()`                         |
| Full identity is known, and only a few fields need to be changed        | `sdk.edit(...)`                       |
| External system pushes item lists, or only `ref + asrt_id` is available | `sdk.ingest(...)`                     |
| Review and materialization of derived candidates                        | `sdk.evaluate(...) + sdk.accept(...)` |
| Single low-level write                                                  | `sdk.set / sdk.add / sdk.retract`     |

**Decision tree**

```text
Need to inspect the write plan (ops) first?
  ├─ Yes -> sdk.batch()
  └─ No
      ├─ Have full identity and only changing one entity?
      │    ├─ Yes -> sdk.edit(...)
      │    └─ No
      │         ├─ Is this a derived-candidate write?
      │         │    ├─ Yes -> sdk.evaluate(...) + sdk.accept(...)
      │         │    └─ No -> sdk.ingest(...)
```

**Common wrong choices**

| Wrong choice                                                        | Correct approach                                                     |
| ------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `find(...)` does not return identity but still trying to use `edit` | switch to `ingest(retract + set/add)`                                |
| Need cross-process replay of writes                                 | export a wire plan with `batch.preview().to_json(sdk)`               |
| Treating hard-reserved meta as ordinary keys during external import | remove reserved keys; use `validate_provenance(...)` first if needed |

---

## 9. Quick Error Handling Reference

### 9.0 Error Layers

| Layer                            | Representative errors                                                                    | Typical triggers                                                  |
| -------------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| SDK facade layer                 | `SDKSchemaError` / `SDKStoreError`                                                       | invalid argument shape, unmet constraints, unsupported boundaries |
| Entity read/write object layer   | `EntityNotFoundError` / `FrozenSnapshotError` / `CardinalityError` / `EditorClosedError` | edit/get/snapshot/assertions related                              |
| DSL construction layer           | `SDKDSLError`                                                                            | invalid vars/Rule/Derivation object construction                  |
| Core compilation/execution layer | `RuleCompileError`                                                                       | rule semantic constraints (e.g. RuleRef target not `expose=True`) |
| ingest diagnostic layer          | `result.diagnostics` (non-exception)                                                     | item-level validation failure (collect-and-stop)                  |

`SDKError` and its subclasses all provide structured fields: `code` (machine-readable error code), and `path` (`None` if unset).

### 9.1 Common Errors Quick Reference

| Error                                            | Common trigger                                                                                                                            | Suggested handling                                                                                                    |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `EntityNotFoundError`                            | target of `sdk.edit(...)` does not exist                                                                                                  | verify identity; use `sdk.batch()` to create new entities; `err.entity_type` and `err.identity_kwargs` can help debug |
| `FrozenSnapshotError`                            | assigning to `EntitySnapshot` or `assertions`                                                                                             | use `sdk.edit(...)` / `sdk.ingest(...)` instead                                                                       |
| `CardinalityError`                               | on `sdk.edit`: using `.add` on a `single` field, or `.set` on a `multi` field (same class of error raises `SDKStoreError` on `sdk.batch`) | choose the correct API based on field cardinality                                                                     |
| `EditorClosedError`                              | continuing to use an editor after `commit/rollback`                                                                                       | reopen with `sdk.edit(...)`                                                                                           |
| `SDKSchemaError`                                 | passing non-identity fields to `get`; invalid `find` field or incomplete identity                                                         | correct parameters according to schema                                                                                |
| `SDKStoreError`                                  | write type mismatch; unknown parameters passed to `accept`; string DSL passed to `run/evaluate`                                           | check parameter types and API boundaries                                                                              |
| `SDKStoreError(code="INVALID_ROW_FORMAT")`       | invalid `row_format` value                                                                                                                | change to `"dict"`                                                                                                    |
| `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")` | Query uses invalid `row_format`, `row_format="instance"` but head does not satisfy constraints, or calling `sdk.run(...)` on a Derivation | Query should use `"dict"`/`"instance"` with valid head constraints; use `sdk.evaluate(...)` for Derivation            |
| `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`       | duplicate output aliases in Query head                                                                                                    | adjust head variable naming                                                                                           |
| `SDKDSLError(code="QUERY_UNBOUND_VAR")`          | unbound variable used in Query where                                                                                                      | bind the variable in the head or a preceding atom                                                                     |
| `SDKDSLError`                                    | chained entity syntax; `with vars() as (u,)` unpacking without arguments                                                                  | use supported syntax (two-step form)                                                                                  |
| `RuleCompileError`                               | RuleRef target not `expose=True`                                                                                                          | correct the rule declaration                                                                                          |
| `IngestResult.diagnostics` contains `error`      | invalid item structure; unknown retract asrt_id                                                                                           | fix item-by-item according to `path`; any error prevents the whole batch from being written                           |

### 9.2 Diagnosing ingest

```python
res = sdk.ingest(items, meta=meta)
for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])
```

Suggested troubleshooting order: first inspect `diagnostics` (fastest way to locate structural errors) → then `warnings` (semantically sensitive keys) → finally `written_assertion_ids`.

---

## 10. Registry

### 10.1 Initialization

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
```

**Stable contract**: at least one of `root_dir` or `registry` must be provided; both may be provided simultaneously, but the paths must be consistent, otherwise `SDKRegistryError` is raised.

### 10.2 Applying a Schema

```python
res = reg.apply_schema_classes(
    [User, Country],
    apply_request_id="req-001",
    transaction_policy="best_effort_no_rollback_v1",
)

print(res["ok"])
print(res["apply_execute"]["idempotency"]["replayed"])
```

Replaying the same `apply_request_id` takes the idempotent replay path (current behavior).

### 10.3 Registering Rule / Derivation

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

You can also register already-compiled specs directly (skipping DSL compilation):

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

**Current behavior**: multi-head Derivation is supported only at runtime via `sdk.evaluate(...)`; `register_derivation(...)` processes it as single-head. If multi-head logic needs to be published, expand it into multiple single-head derivations before registration.

### 10.4 Reading and Listing

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

### 10.5 Apply Pipeline Queries

```python
reg.list_apply_run_ids()
reg.list_apply_runs()
reg.show_apply_run("req-001")
```

**Current behavior**: `show_apply_run(...)` returns `None` if not found; `list_apply_runs()` returns a list of apply execute run records (`list[dict]`).

### 10.6 Unified Low-Level Entry Point: `apply_authoring_bundle`

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    apply_request_id="req-002",
)
```

**Current behavior**: `apply_authoring_bundle(...)` is the low-level master entry point behind `apply_schema_classes(...)`, suitable for composing schema/rule/derivation changes in one shot.

### 10.7 Schema Metadata

```python
manifest = reg.read_manifest()          # registry manifest dict
entry = reg.get_schema_entry()          # schema entry metadata (dict | None)
res = reg.upsert_schema_ir(schema_ir)   # directly write compiled schema_ir
```

---

## 11. Advanced APIs

### 11.1 Direct Pass-Through After Compilation

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

Suitable for scenarios where compiled parameters are already available and SDK object compilation should be skipped (current behavior).

### 11.2 Package Export and Execution

```python
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

The export package format is v2. `manifest.json` contains `"export_version": "v2"`, and the facts directory structure is:

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

Floating-point meta uses reversible serialization: export writes `repr(value)`, import reads `float(raw)`; scientific notation is a valid format.

**Stable contract**: feeding a v1 package (containing `meta_num.facts` and lacking `export_version`) into the new reader raises a clear `unsupported export_version` error.

### 11.3 Configurable Views (`sdk.views`)

Views define “which perspective to use when reading data” and affect result presentation in `sdk.find()` and `sdk.run()`:

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

`sdk.views` is an in-process manager (non-persistent); after restarting the process, it returns to the built-in `"default"` view.

**`ViewSpec` parameters**

| Parameter             | Type          | Default | Description                                     |
| --------------------- | ------------- | ------- | ----------------------------------------------- |
| `active`              | `bool`        | `True`  | whether to look only at active assertions       |
| `confidence_strategy` | `str`         | `"max"` | confidence aggregation strategy                 |
| `prefer_source`       | `str \| None` | `None`  | only effective when strategy is `prefer_source` |

**Confidence aggregation strategies**

| Strategy          | Semantics                                                              |
| ----------------- | ---------------------------------------------------------------------- |
| `"max"`           | take the highest confidence (default)                                  |
| `"mean"`          | arithmetic mean                                                        |
| `"median"`        | median                                                                 |
| `"prefer_source"` | prefer values from `prefer_source`, falling back to `max` if not found |

**Scope of effect**: `confidence_strategy` only affects the presentation of `sdk.find()` / `sdk.run()` results, not the reasoning process. `sdk.evaluate()` does not accept a `view` parameter.

**Output contract for `sdk.run(..., view=...)`** (stable contract)

* Default: returns `rows` (`list[dict]` or `list[tuple]`), without injecting a `confidence` field into each row.
* With `return_display_meta=True`: returns `(rows, display_meta)`.
* `display_meta` has the same length as `rows`; each item contains at least `confidence`, `confidence_strategy`, and `source_breakdown`.
* `return_display_meta=True` must be used together with `view`, otherwise `SDKStoreError` is raised.

### 11.3.1 End-to-End Example: How `find` and `run` Obtain Confidence

```python
from factpy_kernel.core.store.types import ViewSpec

# 1) register a view (mean strategy)
sdk.views.create("risk_mean", ViewSpec(confidence_strategy="mean"))

# 2) find: read aggregated value directly from snapshot object
users = sdk.find(User, lang="zh", view="risk_mean")
print(users[0].confidence)  # e.g. 0.73

# 3) run: confidence is not injected by default
rows = sdk.run(speaks_rule, view="risk_mean", row_format="dict")
print(rows[0])  # {"u": "...", "l": "..."}

# 4) run + return_display_meta: obtain display metadata
rows, display_meta = sdk.run(
    speaks_rule,
    view="risk_mean",
    row_format="dict",
    return_display_meta=True,
)
print(display_meta[0]["confidence"])           # e.g. 0.73
print(display_meta[0]["confidence_strategy"])  # "mean"
print(display_meta[0]["source_breakdown"])     # source-wise aggregation breakdown
```

**Built-in view**: `"default"` (`active=True, confidence_strategy="max"`), and it cannot be deleted.

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

View management endpoints in service `runtime_v1` (current implementation):

| Method | Endpoint                                         |
| ------ | ------------------------------------------------ |
| `POST` | `/v1/runtime/sessions/{session_id}/views/create` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/update` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/delete` |
| `POST` | `/v1/runtime/sessions/{session_id}/views/get`    |
| `GET`  | `/v1/runtime/sessions/{session_id}/views`        |

### 11.4 ProbLog Probabilistic Reasoning

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
* Under the ProbLog path, it is the marginal probability value; under native/souffle paths, it is `None`
* Fully passed through serialization/deserialization, without loss across processes

**Accept semantics** (v3 update)

* Duplicate determination is: same claim, and same business-semantic meta (after excluding timestamp/run/candidate identifier fields)
* Assertions for the same fact with different `confidence` or different `source` may coexist and are not misclassified as duplicates

**Current boundaries**

* If ProbLog CLI is unavailable or times out, `ProbLogEngineError` is raised.
* If export-stage structure is unsupported or parameters are invalid, `ProbLogExportError` is raised.
* If result parsing fails, `ProbLogImportError` is raised.
* Within the same reasoning batch (same `run_id/trace_id`), repeated writes of the same claim are not forced into coexistence merely because `confidence` changes; coexistence is still governed by the ingest idempotency key.

### 11.5 Debugging Properties

```python
sdk.store        # underlying Store object
sdk.ledger       # underlying Ledger object
sdk.schema_ir    # compiled schema actually used by the current store
```

Plain `Entity` instances now expose a debugging-friendly `repr(...)` that previews declared identity and field values in declaration order; unset `Field` values render as `None`, for example `User(user_id='u-1', name='Alice', age=None)`.

### 11.6 Audit Queries

```python
audit = sdk.explain_fact("user:age", alice_ref)
conf = sdk.conflicts("user:age", alice_ref)
```

Both are computed over the current active assertion set (**stable contract**).

`explain_fact(pred_id, e_ref, *val_atoms)` returns (current behavior):

* `pred_id`, `e_ref`
* `active_claims`: `list[dict]`, each item containing `asrt_id`, `args`, `meta`
* `chosen_asrt_id`

The `*val_atoms` parameter filters `active_claims` by exact match on value atoms.

`conflicts(pred_id, e_ref)` returns (current behavior):

* `pred_id`, `e_ref`
* `active_asrt_ids`
* `chosen_asrt_id`

Pass predicate IDs as `pred_id` (such as `"user:age"`), and canonical `idref_v1` tokens as `e_ref`.

---

## 12. Migration Notes (v2 → v3)

### EvaluateMode Renaming

| Old        | New         | Behavior when old value is passed      |
| ---------- | ----------- | -------------------------------------- |
| `"python"` | `"native"`  | explicit error with new name suggested |
| `"engine"` | `"souffle"` | explicit error with new name suggested |
| ——         | `"problog"` | new in v3                              |

The default value is also updated to `"native"` (including authoring DTO/session and SDK derivation evaluate paths).

### Meta Kind Renaming + Addition

| Old     | New       | Description                       |
| ------- | --------- | --------------------------------- |
| `"num"` | `"int"`   | integer; write validation updated |
| ——      | `"float"` | new in v3; used by `confidence`   |

`Ledger.META_KINDS` has been updated from `{"str","num","bool","time","json"}` to `{"str","int","float","bool","time","json"}`. Code writing `kind="num"` must be changed to `kind="int"` (the system will raise a clear error during write validation).

### Export Package Format Upgrade (v1 → v2)

| v1                  | v2                                                |
| ------------------- | ------------------------------------------------- |
| `meta_num.facts`    | `meta_int.facts`                                  |
| ——                  | `meta_float.facts` (new)                          |
| no `export_version` | `manifest.json` contains `"export_version": "v2"` |

Feeding a v1 package into a v2 reader raises a clear error: `unsupported export_version: 'v1'; expected 'v2'`.

### Accept Semantics Change

| Old                                                                    | New                                                                         |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| duplicate detection only checks claim (`pred_id + e_ref + rest_terms`) | also compares business-semantic meta (excluding timestamps/run identifiers) |
| same fact with different confidence may be misclassified as duplicate  | naturally coexists, no longer misclassified                                 |

### Body DSL (New)

```python
# v2 form (still supported)
where=[[atom1, atom2], [atom3]]

# new v3 form (when confidence is needed)
from factpy_kernel.sdk import Body
where=[
    Body([atom1, atom2], confidence=0.9),
    Body([atom3], confidence=0.6),
]
# mixing the two forms is forbidden
```

### Tightened `run(view)` Result Contract

| Old assumption                                                 | Actual v3 behavior                                                                                    |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `sdk.run(rule, view=...)` may include `confidence` inside rows | by default no in-row fields are injected, and the return type remains consistent with `row_format`    |
| ——                                                             | to obtain aggregated confidence, use `return_display_meta=True`, which returns `(rows, display_meta)` |

### Schema Layer (v1 → v2, historical legacy)

* `Field.cardinality`: `"functional"` / `"temporal"` → `"single"`
* `Field.dims`, `Field.fact_key`, and `Field.pred_id` have been removed
* `Identity(primary_key=True)` is required for cross-coordinate joins
* `sdk_batch_plan_v1` wire payload no longer carries `dims` / `fact_key`
