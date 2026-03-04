# FactPy SDK User Guide

> This document describes implemented behavior; unimplemented capabilities are explicitly marked as “Current boundary”.
> Behaviors in this document are categorized with three labels: **Stable contract** (recommended to enforce with strong assertion tests), **Current behavior** (may evolve), **Planned** (not implemented yet).

---

## Table of Contents

1. [Installation and Initialization](#1-installation-and-initialization)
2. [Schema Definition](#2-schema-definition)
3. [Writing Data](#3-writing-data)
4. [meta Fields](#4-meta-fields)
5. [Reading Data](#5-reading-data)
6. [Rule / Query / Derivation](#6-rule--query--derivation)
7. [Provenance Validation](#7-provenance-validation)
8. [Which Write Entry Should I Use?](#8-which-write-entry-should-i-use)
9. [Error Handling Quick Reference](#9-error-handling-quick-reference)
10. [Registry](#10-registry)
11. [Advanced APIs](#11-advanced-apis)
12. [Migration Notes (v2)](#12-migration-notes-v2)

---

## 1. Installation and Initialization

### 1.1 Initialize the Store

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

Specify `ledger_path` when persistence is required:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

If you want Rule query results to be returned as dict rows by default:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    default_row_format="dict",
)
```

**Stable contract**

* `classes` must be a non-empty `list[Entity subclass]`. The `from_schema_classes(...)` / `schema_preflight_from_classes(...)` path raises `SDKSchemaError`; the `SDKStore(...)` constructor path raises `SDKStoreError`.
* `ledger` and `ledger_path` are mutually exclusive; both cannot be provided at the same time.
* On first write, `ledger_path` records `schema_digest`; on reopen it is validated, and mismatch raises `SDKStoreError`.
* `default_row_format` only affects `sdk.run(rule, ...)`. Allowed values are `"tuple"` / `"dict"`, default is `"dict"`.
* When the parsed result is `"tuple"`, a `DeprecationWarning` is emitted; migrating uniformly to `"dict"` is recommended.
* Environment variable `FACTPY_ROW_FORMAT` is read and cached during `SDKStore` initialization (not read dynamically on each `run()`).

### 1.2 Schema Preflight

For scenarios where a runtime store is not needed (CI checks, module import time), you can run preflight only:

```python
from factpy_kernel.sdk import schema_preflight_from_classes

preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])
print(preflight.get("warnings", []))
print(preflight.get("summary", {}))   # entity_count / predicate_count / pred_ids
```

**Stable contract**: returns a `dict` whose core keys include `ok`, `warnings`, `errors`, `diagnostics`, and `summary` (on success).

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

`Identity` locates a fact, while `Field` carries the fact’s value. On the read side there is limited symmetry: snapshot **value access** (`snap.lang`, `snap.name`) works the same for both; but `snap.assertions.lang` is not available — the `assertions` namespace covers only `Field` fields, not `Identity` fields. On the write side, the difference is explicit: calling `.set()` / `.add()` on an `Identity` field raises an exception.

**Stable contract**: every `Entity` must have at least one `Identity`, otherwise class definition raises `SDKSchemaError`.

**Current behavior**: an `Entity` class docstring is automatically emitted as entity-level `description` (`schema_ir.entities[*].description`) for docs/LLM-facing context.

### 2.2 Identity Parameters

| Parameter                 | Meaning                                                                                                  |
| ------------------------- | -------------------------------------------------------------------------------------------------------- |
| `primary_key=True`        | Marks a join anchor; implicitly carried across Fields in Rule inference, and does not appear in the head |
| `default`                 | Static default value                                                                                     |
| `default_factory="uuid4"` | Auto-generate a UUID when missing                                                                        |

`primary_key=True` and `default_factory` are orthogonal — the former declares semantic responsibility, the latter declares generation strategy; they can be used together or separately. For an `Entity` without any `primary_key=True`, if a Rule contains cross-Field joins, compilation fails.

**Recommendation**: `Identity` fields should point to business attributes of the entity (e.g., `user_id`, `lang`), not data-management dimensions like `source` or `version`. The latter belong to meta rather than Identity. This is only a design recommendation; the engine does not enforce it.

### 2.3 Field Parameters

| Parameter              | Meaning                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------ |
| `cardinality="single"` | Single-valued view: reading `snap.<field>` returns a scalar; write API uses `.set()` |
| `cardinality="multi"`  | Multi-valued; all values at the same coordinate are preserved                        |
| `description`          | Documentation/LLM-facing description text                                            |

**Current behavior note**: `single` does not automatically clean up old assertions on write; `active/history` may still show multiple non-retracted assertions, while `snap.<field>` returns the current single-value view.

**Current boundary**: `dims` / `fact_key` / `pred_id` / `functional` / `temporal` have been removed.

### 2.4 Reified Record (Relationship Node)

All entities are based on `Entity`; relationship nodes are simply a usage convention:

```python
class LivesIn(Entity):
    uid: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")
```

**Stable contract**: after compilation, schema generates a `<T>:exists` predicate for every `Entity`; when batch-writing fields, the `<T>:exists` write op is automatically added.

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

**Current behavior**: string annotations (e.g., `"str"`, `"datetime"`, `"uuid"`, `"entity_ref"`) are also supported; unrecognized annotations fall back to `entity_ref`.

### 2.6 In-memory Objects vs Managed Objects

```python
# Ordinary in-memory object (not bound to a store)
alice = User(user_id="u-001")
alice.name = "Alice"      # plain Python assignment

# sdk.batch managed object (supports .set/.add/.retract)
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

    # Provide all Identity at once
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")
    u.age.set(30)
    u.country.set(de)   # can directly reference a handle within the same tx

    # Or bind Identity step-by-step
    u2 = tx.entity(User, user_id="u-002")
    u2 = u2.bind(lang="en")
    u2.name.add("Alicia")

    plan = tx.preview()   # read-only preview, not persisted
    res = tx.commit()     # actual write
```

The `meta` of `batch` is inherited by all write operations; a single operation may override with its own `meta`:

```python
with sdk.batch(meta={"source": "hr", "valid_from": "2024-01"}) as tx:
    u = tx.entity(User, user_id="u-001", lang="zh")
    u.name.add("艾丽西亚")                                  # inherits batch meta
    u.name.add("Alice", meta={"valid_from": "2024-06"})    # per-op override
    tx.commit()
```

**meta merge precedence** (higher overrides lower): `commit_meta > field_op_meta > entity_meta > batch_meta`

**Stable contract**

* Use `.set()` for `single` fields; use `.add()` for `multi` fields. If misused: raises `SDKStoreError` (batch handle path); raises `CardinalityError` (the `sdk.edit` path).
* Batch handles retract via `.retract(assertion_id)`; edit’s `FieldEditor` retracts via `.retract(asrt_id=...)`. Neither supports retract-by-value.
* If Identity is incomplete, `.set()` / `.add()` raises `SDKStoreError` immediately (error message lists missing fields; you may `bind(...)` first to complete it).
* Calling `.set()` / `.add()` on an `Identity` field raises `SDKStoreError` immediately — once Identity is determined it is immutable.
* `preview()` is non-persistent and can be called repeatedly; only `commit()` persists.
* `SDKBatchTx`’s context manager does not auto-commit and does not auto-rollback (`__exit__` is a no-op). Callers must call `commit()` explicitly and handle exceptions themselves.

**`entity_ref` fields** (Stable contract): may accept either “a handle in the same tx” or a “canonical idref_v1 token”; may not accept ordinary business strings (e.g., `"DE"`).

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

# Replay across processes / time
from factpy_kernel.sdk.batch import WireBatchPlan

plan2 = WireBatchPlan.from_json(wire_json)
plan2.apply(sdk, strict_schema=True)
```

**Current behavior**: `strict_schema=True` checks that the wire plan’s `schema_digest` matches the current SDK schema.

**Current behavior note**: wire export (`to_json` / `export`) does not accept raw `idref_v1` string values for `entity_ref` writes. To produce a replayable wire plan, express entity relationships via “handle references in the same tx”.

### 3.3 Dependency Closure (`include_deps`)

Default `include_deps=True`: committing an object automatically includes dependency objects it references. Missing dependencies are not silently skipped; an error is raised directly (**Stable contract**).

### 3.4 `sdk.edit`

Suitable when you “know full identity and only modify a few fields”:

```python
with sdk.edit(User, user_id="u-001", lang="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
    # normal exit from with: auto commit()
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

* If the entity is not found, raises `EntityNotFoundError` (no implicit creation; use `sdk.batch()` for creation).
* After `commit()` or `rollback()`, the editor is closed; calling any method raises `EditorClosedError`.

### 3.5 `sdk.ingest`

Suitable for external ingestion, or scenarios where you only have `ref + asrt_id` (cannot obtain full identity):

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
* If `diagnostics` contains any entry with `severity="error"`, the entire batch is not written (collect-and-stop).
* `allow_sensitive_meta=True` only suppresses sensitive warnings; it does not relax hard reserved constraints.

### 3.5.1 Typical Scenario: Entity Migration

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

### 3.6 Low-level Write Entry Points

```python
alice_ref = sdk.ref(User, user_id="u-001", lang="zh")
sdk.set(User.age, alice_ref, 31, meta={"source": "hr"})
sdk.add(User.name, alice_ref, "Alicia", meta={"source": "hr"})
sdk.retract("asrt_xxx", meta={"source": "hr"})
```

Minimal wrapping; writes directly to the ledger without preview/wire capabilities.

---

## 4. meta Fields

meta is not a free-form dict; keys are categorized into four responsibility groups:

**System reserved (written by ingest pipeline; user cannot write)**
`ingested_at`, `ingest_key`, `revoked_asrt_id`

**Operation tracing (convention keys; recommended to fill)**
`source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`

**Derivation chain (auto-written by accept pipeline)**
`derived_rule_id`, `derived_rule_version`, `run_id`, `support_digest`, `support_kind`, `candidate_id`, `candidate_key`, `accepted_at`, etc.

**Business temporality (used to unlock temporal views)**
`valid_from`, `valid_to`, `version`

Business temporal keys are user-writable; the view layer is aware of them but does not enforce them. If absent, only `.active` / `.history` are available; when present, `.at(t)` / `.version(v)` queries are unlocked.

**meta key tiers** (**Stable contract**)

| Tier               | Representative keys                                                            | Behavior                                  |
| ------------------ | ------------------------------------------------------------------------------ | ----------------------------------------- |
| hard reserved      | `ingested_at`, `ingest_key`, `revoked_asrt_id`                                 | user cannot write                         |
| sensitive semantic | derivation-chain keys like `derived_rule_id`, `run_id`, `support_digest`, etc. | warning by default; does not block writes |
| convention         | `source`, `source_loc`, `trace_id`, `confidence`, `approved_by`, `note`        | written normally                          |
| free               | business-defined keys                                                          | written normally                          |

**Dedup basis**: `claim + source + source_loc + trace_id + valid_from + valid_to + version`

Note: `ingested_at` is system ingestion time, not equal to `valid_from` (business effective time). Using `ingested_at` in place of `valid_from` for temporal views causes semantic misalignment.

**`trace_id` semantics**: `trace_id` participates in idempotency computation but is not the sole determining factor; `valid_from` / `valid_to` / `version` also participate in dedup. Under the same `trace_id`, different temporal dimensions still produce different assertions.

---

## 5. Reading Data

### 5.1 `sdk.get`

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

if snap is None:
    print("Not found")
else:
    print(snap.ref)                 # canonical idref_v1 token
    print(snap.entity_type)         # "User"
    print(snap.identity_available)  # True
    print(snap.identity)            # usable as identity kwargs for sdk.edit(...)
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
```

**Stable contract**

* `limit` must be a non-negative integer (`limit=0` returns an empty list).
* When filtering by Identity, all Identity fields of that entity must be provided.
* `temporal_view` is not supported.
* Passing an unknown filter field raises `SDKSchemaError`.

**Identity availability of `find` results** (**Current behavior**)

```python
records = sdk.find(LivesIn, user=alice_ref)
for rec in records:
    if rec.identity_available:
        with sdk.edit(LivesIn, **rec.identity) as editor:
            ...
    else:
        # use ingest: retract/set with rec.ref + asrt_id
        ...
```

* Without an identity filter: snapshots typically have `identity_available=False`.
* With a complete identity filter: snapshots returned have `identity_available=True`.

### 5.3 `EntitySnapshot` Assertion Views

```python
snap = sdk.get(User, user_id="u-001", lang="zh")

# current-view values
snap.name      # multi -> tuple[...]
snap.age       # single -> scalar or None
snap.country   # single entity_ref -> idref_v1 token or None

# assertion views
snap.assertions.name.active           # currently non-retracted assertions
snap.assertions.name.history          # full history (including retracted)
snap.assertions.name.at("2024-03-01") # business-temporal filter
snap.assertions.name.version("v2")    # version filter
snap.field("name").active             # equivalent form
```

**View semantics** (**Stable contract**)

| View          | Semantics                                                                 |
| ------------- | ------------------------------------------------------------------------- |
| `.active`     | currently non-retracted, maintained by store registry                     |
| `.history`    | full history including retracted                                          |
| `.at(t)`      | on active set: `valid_from <= t` and (`valid_to` empty or `valid_to > t`) |
| `.version(v)` | on active set: `version == v`                                             |

**Temporal view boundaries**

* Assertions missing `valid_from` do not match `.at(t)`; they only appear in `.active`.
* Assertions missing `version` do not match `.version(v)`.
* `.at(t)` validates ISO 8601 (both `t` and assertions’ `valid_from`/`valid_to` are validated); invalid formats raise `SDKStoreError`.
* `.version(v)` accepts only `str | int` (`bool` is invalid).
* Temporal filtering is applied on the active set, not drawn from history.
* `EntitySnapshot` and the `assertions` namespace are read-only; assignments raise `FrozenSnapshotError`.

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

**Stable contract**: `with vars() as (u, l)` unpacking without args is not supported and raises `SDKDSLError`.

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
            li.user == u,      # two-step form (chaining not supported)
            li.country == c,
            HasLanguage(hl),
            hl.country == c,
            hl.language == l,
        ],
    )

rows = sdk.run(speaks_rule, row_format="dict")
# [{"u": "...", "l": "..."}, ...]
```

**Stable contract**

* Chained form like `LivesIn(li).user == u` is not supported; use the two-step form.
* OR uses `where=[[...], [...]]` (OR-of-AND).
* `row_format` precedence across three layers: `run(..., row_format=...) > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`.
* Invalid `row_format` raises `SDKStoreError(code="INVALID_ROW_FORMAT")`.
* A `RuleRef` target rule must have `expose=True`, otherwise `RuleCompileError`; it is not allowed inside `Not(...)`.

**Current behavior**: linear arithmetic `+/-/constant-multiple` is supported (e.g., `age == (2026 - by)`); nonlinear multiplication `x * y` is not supported.

### 6.3 Query DSL

Identity and Field fields use exactly the same access syntax in the where clause:

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

rows = sdk.run(q)   # always returns list[dict]
```

**Stable contract**

* Query returns dict rows only; `row_format` is not supported.
* Valid head forms: `Entity(var)`, `[Entity(var1), ...]`, `Entity.field(...)`.
* Query construction performs alias-conflict validation (raises `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`) and where variable-binding validation (raises `SDKDSLError(code="QUERY_UNBOUND_VAR")`).
* Entity head columns return `EntitySnapshot`; field projection columns return scalar values.

**Current behavior**: `on_missing` / `on_type_mismatch` strategies:

* `error`: raises `SDKStoreError` (`QUERY_MISSING_REF` / `QUERY_TYPE_MISMATCH`)
* `skip`: drop the row
* `null`: set the column to `None` and keep the row (still participates in dedup)

### 6.4 Derivation

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

cands = sdk.evaluate(speaks_drv, mode="python")   # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="alice")

# Atomic commit for multiple candidate sets
res = sdk.accept_many(cands, mode="atomic")
```

**Stable contract**

* `sdk.evaluate(...)` produces candidates and does not write the ledger; `sdk.accept(...)` writes the ledger.
* Multiple heads are supported via `head=[H1, H2, ...]`; `evaluate` returns flattened results sharing the same `run_id`.
* `sdk.accept(CandidateSet, ...)` accepts exactly one positional argument; override keys allowed: `approved_by`, `note`, `dry_run`, `identity_override` (also accepted via `meta_overrides`). Unknown parameters raise `SDKStoreError`.
* `sdk.run(Derivation(...))` is not supported; use `sdk.evaluate(...)`.
* When a dependency graph exists, prefer `sdk.accept_many(..., mode="atomic")` to ensure atomicity.

**Current boundary**

* `sdk.evaluate(..., temporal_view=...)` is explicitly rejected.
* Temporal write semantics in Derivation head (head directly producing assertions with `valid_from`/`valid_to`/`version`) are not yet open. Temporal information can currently only be carried via meta in write paths (`sdk.batch`/`sdk.ingest`).

### 6.5 Identity Rules for Head

```
Fields appearing in head = all non-primary Identity + the target Field value
```

* **`primary_key` fields**: regardless of count, they never appear in head; they are implicitly carried by entity binding in where.
* **Non-primary Identity fields**: must be explicitly provided in head, otherwise the write target is ambiguous.

```python
# User has primary_key=user_id, non-primary Identity=lang
head=User.name(lang=l, name=n)   # user_id does not appear; lang must be provided
```

Including a `primary_key` field in head is a compile-time hard error.

### 6.6 Cross-Coordinate Joins

Two facts of the same entity at different coordinates are two different variables in a Rule, and must be joined explicitly via `primary_key`:

```python
with vars("u1", "u2", "n1", "n2") as (u1, u2, n1, n2):
    q = Query(
        head=[],
        where=[
            User(u1), u1.lang == "zh", u1.name == n1,
            User(u2), u2.lang == "en", u2.name == n2,
            u1.user_id == u2.user_id,   # primary_key join across coordinates
        ],
    )
```

**Stable contract**

* Cross-coordinate joins allow only `primary_key` fields in `==` comparisons.
* Cross-coordinate equality comparison on a non-`primary_key` field is a compile-time hard error; the error message indicates which `primary_key` field to use.
* Cross-entity-type comparisons are compile-time hard errors.

### 6.7 Rule / Derivation Current Limitations Quick Reference

| Limitation                                   | Notes                                                         |
| -------------------------------------------- | ------------------------------------------------------------- |
| String DSL                                   | `sdk.run("...")` / `sdk.evaluate("...")` not supported        |
| `sdk.run(Derivation(...))`                   | not supported; use `sdk.evaluate(...)`                        |
| Chained path comparisons                     | `LivesIn(li).user == p` not supported; use two-step form      |
| Cross-coordinate non-primary_key comparisons | compile-time hard error                                       |
| Nonlinear arithmetic                         | `x * y` not supported                                         |
| `Not(...)` body                              | must be non-empty; includes safety checks with outer bindings |
| `RuleRef` inside `Not(...)`                  | compile-time error                                            |

---

## 7. Provenance Validation

`sdk.validate_provenance(...)` is a pure validation entry; it does not write the ledger and does not automatically block ingest/accept.

```python
report = sdk.validate_provenance(candidate_set, standard="derivation_v1")

# Or validate a dict
report = sdk.validate_provenance(
    {"derived_rule_id": "drv.speaks", "derived_rule_version": "1.0.0",
     "run_id": "run-001", "support_kind": "exact", "support_digest": "sha256:...."},
    standard="derivation_v1",
)

print(report.ok)
print(report.errors)
print(report.warnings)
```

**Required fields for `derivation_v1`** (**Stable contract**)

| Field                  | Requirement      |
| ---------------------- | ---------------- |
| `derived_rule_id`      | non-empty string |
| `derived_rule_version` | non-empty string |
| `run_id`               | non-empty string |
| `support_kind`         | non-empty string |
| `support_digest`       | `sha256:<64hex>` |

Optional keys `schema_digest` / `policy_digest` with invalid formats go to `warnings` (not `errors`).

---

## 8. Which Write Entry Should I Use?

| Scenario                                                               | Recommended entry                     |
| ---------------------------------------------------------------------- | ------------------------------------- |
| Construct objects with references; want preview before commit          | `sdk.batch()`                         |
| Full identity known; modify a few fields                               | `sdk.edit(...)`                       |
| External system pushes item list, or only `ref + asrt_id` is available | `sdk.ingest(...)`                     |
| Review and materialize derived candidates                              | `sdk.evaluate(...) + sdk.accept(...)` |
| Single low-level write                                                 | `sdk.set / sdk.add / sdk.retract`     |

**Decision tree**

```text
Do you need to see the write plan (ops) first?
  ├─ Yes -> sdk.batch()
  └─ No
      ├─ Do you have full identity and only change one entity?
      │    ├─ Yes -> sdk.edit(...)
      │    └─ No
      │         ├─ Is this about writing derived candidates?
      │         │    ├─ Yes -> sdk.evaluate(...) + sdk.accept(...)
      │         │    └─ No -> sdk.ingest(...)
```

**Common mis-selections**

| Mis-selection                                                   | Correct approach                                                      |
| --------------------------------------------------------------- | --------------------------------------------------------------------- |
| `find(...)` cannot provide identity but you still want `edit`   | use `ingest(retract + set/add)` instead                               |
| Need cross-process replay of writes                             | export a wire plan via `batch.preview().to_json(sdk)`                 |
| Treat hard reserved meta as ordinary keys in external ingestion | remove reserved keys; if needed, run `validate_provenance(...)` first |

---

## 9. Error Handling Quick Reference

### 9.0 Error Layering

| Layer                          | Representative errors                                                                    | Typical triggers                                                     |
| ------------------------------ | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| SDK facade layer               | `SDKSchemaError` / `SDKStoreError`                                                       | invalid argument shapes, constraints not met, unsupported boundaries |
| Entity read/write object layer | `EntityNotFoundError` / `FrozenSnapshotError` / `CardinalityError` / `EditorClosedError` | edit/get/snapshot/assertions related                                 |
| DSL construction layer         | `SDKDSLError`                                                                            | illegal construction of vars/Rule/Derivation                         |
| Core compile/exec layer        | `RuleCompileError`                                                                       | rule semantic constraints (e.g., RuleRef target not `expose=True`)   |
| ingest diagnostics layer       | `result.diagnostics` (not an exception)                                                  | item-level validation failure (collect-and-stop)                     |

`SDKError` and subclasses provide structured fields: `code` (machine-readable error code), `path` (`None` if not set).

### 9.1 Common Errors Quick Reference

| Error                                            | Common trigger                                                                                                                   | Suggested handling                                                                                        |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `EntityNotFoundError`                            | edit target does not exist in `sdk.edit(...)`                                                                                    | verify identity; create with `sdk.batch()`; use `err.entity_type` and `err.identity_kwargs` for debugging |
| `FrozenSnapshotError`                            | assigning to `EntitySnapshot` or `assertions`                                                                                    | use `sdk.edit(...)` / `sdk.ingest(...)`                                                                   |
| `CardinalityError`                               | on `sdk.edit`: using `.add` for `single` or `.set` for `multi` (`sdk.batch` raises `SDKStoreError` for the same class of errors) | choose API based on field cardinality                                                                     |
| `EditorClosedError`                              | using editor after `commit/rollback`                                                                                             | reopen via `sdk.edit(...)`                                                                                |
| `SDKSchemaError`                                 | `get` passed non-Identity; `find` field illegal or identity incomplete                                                           | fix per schema                                                                                            |
| `SDKStoreError`                                  | write type mismatch; unknown `accept` parameters; passing string DSL to `run/evaluate`                                           | verify parameter types and interface boundaries                                                           |
| `SDKStoreError(code="INVALID_ROW_FORMAT")`       | illegal `row_format`                                                                                                             | use `"dict"`                                                                                              |
| `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")` | passing `row_format` on Query, or calling `sdk.run(...)` on Derivation                                                           | do not pass `row_format` for Query; use `sdk.evaluate(...)` for Derivation                                |
| `SDKDSLError(code="QUERY_ALIAS_CONFLICT")`       | duplicate aliases in Query head                                                                                                  | adjust head variable names                                                                                |
| `SDKDSLError(code="QUERY_UNBOUND_VAR")`          | using an unbound var in Query where                                                                                              | bind the var in head or earlier atoms                                                                     |
| `SDKDSLError`                                    | chained entity syntax; `with vars() as (u,)` unpacking without args                                                              | switch to supported syntax (two-step form)                                                                |
| `RuleCompileError`                               | RuleRef target missing `expose=True`                                                                                             | fix rule declaration                                                                                      |
| `IngestResult.diagnostics` contains `error`      | illegal item structure; unknown retract asrt_id                                                                                  | fix per-item by `path`; any error prevents the whole batch from writing                                   |

### 9.2 Investigating ingest Diagnostics

```python
res = sdk.ingest(items, meta=meta)
for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])
```

Order of investigation: first `diagnostics` (fastest structural localization) → then `warnings` (sensitive semantic keys) → finally `written_assertion_ids`.

---

## 10. Registry

### 10.1 Initialization

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
```

**Stable contract**: choose exactly one construction mode: `SDKRegistry(root_dir=...)` or `SDKRegistry(registry=...)`. If both are provided and the paths differ, raises `SDKRegistryError`.

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

Replays with the same `apply_request_id` are handled via idempotent replay (**Current behavior**).

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

You can also register compiled specs directly (skipping DSL compile):

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

**Current behavior**: multi-head Derivation is supported only at runtime via `sdk.evaluate(...)`; `register_derivation(...)` treats Derivation as single-head. To publish multi-head logic, expand into multiple single-head derivations and register separately.

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

### 10.6 Low-level Unified Entry: `apply_authoring_bundle`

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    apply_request_id="req-002",
)
```

**Current behavior**: `apply_authoring_bundle(...)` is the underlying unified entry for `apply_schema_classes(...)`, suitable for combining schema/rule/derivation changes in one request.

### 10.7 Schema Metadata

```python
manifest = reg.read_manifest()          # registry manifest dict
entry = reg.get_schema_entry()          # schema entry metadata (dict | None)
res = reg.upsert_schema_ir(schema_ir)   # directly write compiled schema_ir
```

---

## 11. Advanced APIs

### 11.1 Pass-through with Compiled Inputs

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

Suitable when you already hold compiled parameters and want to skip SDK object compilation (**Current behavior**).

### 11.2 Package Export and Execution

```python
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

Depends on adapter implementations; currently primarily the Soufflé adapter (**Current behavior**).

### 11.3 Debug Attributes

```python
sdk.store        # underlying Store object
sdk.ledger       # underlying Ledger object
sdk.schema_ir    # compiled schema actually used by the current store
```

### 11.4 Audit Queries

```python
audit = sdk.explain_fact("user:age", alice_ref)
conf  = sdk.conflicts("user:age", alice_ref)
```

Both are computed from the current active assertion set (**Stable contract**).

`explain_fact(pred_id, e_ref, *val_atoms)` returns (**Current behavior**):

* `pred_id`, `e_ref`
* `active_claims`: `list[dict]`, each containing `asrt_id`, `args`, `meta`
* `chosen_asrt_id`

The `*val_atoms` parameters filter `active_claims` by “exact match on value atoms”.

`conflicts(pred_id, e_ref)` returns (**Current behavior**):

* `pred_id`, `e_ref`
* `active_asrt_ids`
* `chosen_asrt_id`

`pred_id` should be a predicate id (e.g., `"user:age"`); `e_ref` should be a canonical `idref_v1` token.

---

## 12. Migration Notes (v2)

**Schema layer**

* `Field.cardinality`: `functional` / `temporal` → `single`
* `Field.dims`, `Field.fact_key`, `Field.pred_id` removed
* `Identity` adds `primary_key` parameter; Entities without `primary_key=True` raise a compile error when Rules attempt cross-Field joins

**Rule / DSL layer**

* Having a `primary_key` field appear in head is a compile-time hard error
* `temporal_view` parameter removed from evaluate/runtime entry points (explicit error)
* Cross-coordinate `==` comparisons on non-`primary_key` fields are compile-time hard errors
* `.chosen` view removed; use `.active` uniformly

**Protocol layer (`sdk_batch_plan_v1`)**

* `dims`, `fact_key` removed from wire protocol
* `cardinality` enum values changed (`functional` / `temporal` → `single`)

**Current temporal semantics**

| Capability                                                            | Status        |
| --------------------------------------------------------------------- | ------------- |
| Write: persist `valid_from`/`valid_to`/`version` and include in dedup | ✅ Implemented |
| Read: `snapshot.assertions.<field>.at(t)` / `.version(v)`             | ✅ Implemented |
| Rule/Derivation head produces temporal assertions                     | ⬜ Planned     |
