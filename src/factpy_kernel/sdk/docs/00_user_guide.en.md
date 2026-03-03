# FactPy SDK User Guide (Current Code Baseline)

> Baseline: current implementation in `src/factpy_kernel/sdk`.  
> This guide documents only implemented behavior; unsupported areas are marked as explicit boundaries.

---

## 1. Initialization

```python
from factpy_kernel.sdk import SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

File-backed ledger:

```python
sdk = SDKStore.from_schema_classes(
    [User, Country, Language, LivesIn],
    ledger_path="./data/ledger.db",
)
```

Stable Contract:
- `classes` must be a non-empty `list[Entity subclass]`.
- `ledger` and `ledger_path` are mutually exclusive.
- First open writes `schema_digest`; reopen validates digest and raises `SDKStoreError` on mismatch.

---

## 2. Schema Definition

```python
from factpy_kernel.sdk import Entity, Identity, Field

class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="multi")
    age: int = Field(cardinality="single")
```

Stable Contract:
- Every `Entity` must declare at least one `Identity`.
- `Field.cardinality` only supports `single | multi`.
- Public `Field` parameters are only `cardinality` and `description`.
- `Identity` supports `default`, `default_factory`, and `primary_key`.

Current Boundary:
- `dims` / `fact_key` / `pred_id` / `functional` / `temporal` semantics are removed.

---

## 3. Writing Data (`sdk.batch` / `sdk.set` / `sdk.add` / `sdk.retract`)

### 3.1 `sdk.batch(...)`

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "seed"}) as tx:
    u = tx.entity(User, user_id="u-001", locale="zh")
    u.name.add("Alice")
    u.age.set(30)

    plan = tx.preview()
    res = tx.commit()
```

Stable Contract:
- Use `.set(...)` for `single`, `.add(...)` for `multi`.
- `.retract(asrt_id=...)` retracts by assertion id.
- `preview()` is read-only; `commit()` persists.

### 3.2 Identity Is Immutable

Stable Contract:
- `sdk.edit(...).<identity>.set/add/retract` always raises (identity fields are immutable).

### 3.3 Low-level write APIs

```python
sdk.set(User.age, e_ref, 31, meta={"source": "hr"})
sdk.add(User.name, e_ref, "Alicia", meta={"source": "hr"})
sdk.retract(asrt_id, meta={"source": "hr"})
```

---

## 4. Reading Data (`sdk.get` / `sdk.find` / `EntitySnapshot`)

### 4.1 `sdk.get(...)`

```python
snap = sdk.get(User, user_id="u-001", locale="zh")
```

Stable Contract:
- `get` accepts identity kwargs only.
- Returns `EntitySnapshot | None`.

### 4.2 `sdk.find(...)`

```python
rows = sdk.find(User, age=30, limit=20)
```

Stable Contract:
- `limit` must be a non-negative integer.
- If identity filters are used, all identity fields are required.
- `temporal_view` is not supported.

### 4.3 `EntitySnapshot` and assertion views

```python
snap.assertions.name.active
snap.assertions.name.history
snap.assertions.name.at("2024-03-01")
snap.assertions.name.version("v2")
```

Stable Contract:
- `active`: currently non-revoked assertions.
- `history`: full ledger history (including revoked assertions).
- `at(t)`: business-time filter on active assertions:
  `valid_from <= t` and (`valid_to` is missing or `valid_to > t`).
- `version(v)`: `version == v` filter on active assertions.

Temporal filter boundaries:
- Missing `valid_from`: excluded from `.at(t)`.
- Missing `version`: excluded from `.version(v)`.
- `.at(t)` validates ISO 8601 for input `t` and assertion `valid_from/valid_to`; invalid format raises `SDKStoreError`.
- `.version(v)` accepts `str|int` only (`bool` is invalid).

---

## 5. Editing Data (`sdk.edit`)

```python
with sdk.edit(User, user_id="u-001", locale="zh") as editor:
    editor.name.add("Alicia")
    editor.age.set(31)
```

Stable Contract:
- Missing entity raises `EntityNotFoundError`.
- Reusing a closed editor raises `EditorClosedError`.
- Wrong cardinality operation raises `CardinalityError`.

---

## 6. External Import (`sdk.ingest`)

```python
res = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": user_ref, "value": "Alias"},
        {"kind": "set", "field": User.age, "e_ref": user_ref, "value": 31},
        {"kind": "retract", "asrt_id": old_asrt_id},
    ],
    meta={"source": "hr", "trace_id": "hr-001"},
)
```

Stable Contract:
- `kind=set` is for `single`; `kind=add` is for `multi`.
- Top-level `meta` and item-level `meta` merge with item-level override.
- Any diagnostic error triggers collect-and-stop (no writes for the whole batch).

Meta highlights:
- Hard-reserved keys: `ingested_at`, `ingest_key`, `revoked_asrt_id` (user write forbidden).
- Business-temporal keys: `valid_from`, `valid_to`, `version`.
- `ingest_key` idempotency material:
  `claim + source + source_loc + trace_id + valid_from + valid_to + version`.

---

## 7. Rule / Query / Derivation

### 7.1 Rule

```python
from factpy_kernel.sdk import Rule, Pred, Not, vars

with vars("u") as (u,):
    r = Rule(
        id="q.vip",
        version="1.0.0",
        select=[u],
        where=[
            Pred("user:tag", u, "vip"),
            Not([Pred("user:tag", u, "blocked")]),
        ],
    )

rows = sdk.run(r, row_format="dict")
```

Stable Contract:
- `row_format` is supported only on the Rule path (`tuple|dict`).
- `RuleRef` targets must be `expose=True`.
- `RuleRef` is not allowed inside `Not(...)` body (compile-time error).

### 7.2 Query

```python
from factpy_kernel.sdk import Query, vars

with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        where=[User(u), u.locale == loc, u.name == nm],
    )

rows = sdk.run(q)  # always list[dict]
```

Stable Contract:
- Query always returns dict rows; `row_format` is not supported.
- Query head supports only `Entity(var)` and `Entity.field(...)`.

### 7.3 Derivation

```python
from factpy_kernel.sdk import Derivation, vars

with vars("u", "loc", "nm") as (u, loc, nm):
    d = Derivation(
        id="drv.copy_name",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

cands = sdk.evaluate(d, mode="python")
res = sdk.accept(cands[0], approved_by="alice")
```

Stable Contract:
- `head` shape decides candidate kind (fact/entity).
- Multi-head (`head=[H1, H2, ...]`) is supported; `evaluate` returns flattened candidates sharing one `run_id`.
- `materialize_as` / `id_policy` are removed.

Current Boundary:
- `sdk.evaluate(..., temporal_view=...)` is explicitly rejected.
- Derivation/runtime temporal write semantics (emitting assertions with `valid_from/valid_to/version` directly from head) are not open yet.

---

## 8. Temporal Semantics Status

Implemented:
- Write path persists `valid_from/valid_to/version`, and they are part of idempotency.
- Read path supports `snapshot.assertions.<field>.at(t)` and `.version(v)`.

Not implemented:
- Temporal write semantics in Rule/Derivation head.

---

## 9. Audit & Debugging

```python
sdk.explain_fact(pred_id, e_ref, *val_atoms)
sdk.conflicts(pred_id, e_ref)
```

Notes:
- Both operate on active assertions.
- For `single` fields, `chosen_asrt_id` is returned to explain conflict resolution.

---

## 10. Registry (`SDKRegistry`)

Common APIs:
- `apply_schema_classes(...)`
- `register_rule(...)` / `register_derivation(...)`
- `list_rule_ids()` / `list_derivation_ids()`
- `get_latest_rule_spec(...)` / `get_latest_derivation_spec(...)`

Current Boundary:
- Registry manages authoring assets; runtime execution remains on `SDKStore`.
- For multi-head derivations, expand into multiple single-head registrations when publishing.

---

## 11. v2 Migration Quick Notes

- `Field.cardinality`: `functional|temporal` -> `single`.
- Removed: `dims` / `fact_key` / `chosen`.
- `temporal_view` removed from evaluate/runtime entrypoints (explicit error).
- Cross-coordinate joins only allow primary_key equality; invalid forms fail at compile time.
