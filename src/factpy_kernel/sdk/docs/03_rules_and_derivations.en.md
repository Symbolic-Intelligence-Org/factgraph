# SDK Rule / Query / Derivation DSL (Current Implementation)

Scope: `src/factpy_kernel/sdk/dsl` + `SDKStore.run/evaluate/accept`

## 1. `vars(...)`

Supported:

```python
with vars("p", "c") as (p, c):
    ...
```

```python
with vars() as V:
    p, c = V("p", "c")
```

Unsupported:
- `with vars() as (p, c)` (SDK raises `SDKDSLError` due Python runtime limits)

## 2. Rule DSL

```python
with vars("li", "u", "c") as (li, u, c):
    rule = Rule(
        id="q_user_country",
        version="1.0.0",
        select=[u, c],
        where=[
            LivesIn(li),
            li.user == u,
            li.country == c,
        ],
        expose=True,
    )

rows = sdk.run(rule, row_format="dict")
```

Stable contract:
- `Rule.id/version` must be non-empty strings.
- `Rule.select/where` must be non-empty lists.
- `row_format` is supported only on the Rule path.
- `row_format` precedence is: call-site > `SDKStore(default_row_format=...)` > `FACTPY_ROW_FORMAT` > `"dict"`.
- Resolving to `"tuple"` emits `DeprecationWarning` (prefer `"dict"`).

## 3. `where` Syntax and Limits

Supported:
- entity-exists sugar: `LivesIn(li)`
- path equality sugar: `li.user == u`, `li.country == c`
- attr-vs-attr comparison: `u1.user_id == u2.user_id`
- explicit predicate atom: `Pred("user:tag", u, "vip")`
- rule reference: `RuleRef(...)(...)`
- negation: `Not([...])`
- comparisons: `== != > >= < <=`
- OR branches: `where=[[...], [...]]`
- linear arithmetic inside comparisons (for example `age == (2026 - by)`, `x * 2`)

Limits:
- path sugar supports only `==`.
- attr-vs-attr comparisons support only `==`, and require schema-aware compilation.
- non-linear multiplication (`x * y`) is unsupported.
- string DSL is unsupported (`sdk.run("...")`, `sdk.evaluate("...")`).

## 4. RuleRef and Dependency Registration

Construction:

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

Rules:
- RuleRef target must be `expose=True`, otherwise runtime `RuleCompileError`.
- `RuleRef` is forbidden inside `Not(...)` body (compile-time error).
- `sdk.run(..., registry=None)` auto-registers `RuleRef(RuleObj)` dependencies.
- If `registry` is explicitly provided, SDK does not auto-fill dependencies.

## 5. Query DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        where=[User(u), u.locale == loc, u.name == nm],
        on_missing="error",
        on_type_mismatch="error",
    )

rows = sdk.run(q)  # list[dict]
```

Stable contract:
- Query head only supports `Entity(var)` and `Entity.field(...)`.
- Query always returns `list[dict]`; `row_format` is not supported.
- Field projection must resolve to schema `single` fields.
- Unbound variables in `where` fail at construction with `SDKDSLError(code="QUERY_UNBOUND_VAR")`.
- `on_missing` / `on_type_mismatch` only allow `error|skip|null`.
- Passing `row_format` for Query raises `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.

## 6. Derivation DSL

```python
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

Fields:
- required: `id`, `version`, `where`
- optional: `head`, `target`, `head_vars`, `mode`, `status`

Stable contract:
- `head` shape infers candidate kind (fact/entity).
- Multi-head (`head=[H1, H2, ...]`) is supported; `evaluate` returns flattened candidates sharing one `run_id`.
- `sdk.run(derivation)` is not supported; use `sdk.evaluate(...)`.
- `sdk.run(derivation)` fails with code `QUERY_INVALID_ROW_FORMAT` (error message directs callers to `evaluate()`).

## 7. Compile-Time Hard Constraints (v2)

### 7.1 `head` and primary key

- Any primary-key field in `head` -> compile error.
- Missing entity binding in `where` for implicit primary-key carry -> compile error.
- Multiple same-type bindings in `where` that cannot be disambiguated -> compile error.

### 7.2 Cross-coordinate attr comparison

`u1.user_id == u2.user_id` is legal only when:
- both sides are the same entity type
- both sides use the same field
- that field is declared as `primary_key`

Otherwise, compilation fails (no implicit guessing).

### 7.3 Lowering shape

Valid cross-coordinate primary-key comparison is lowered to shared system vars (`$__pk_N`):

```python
("pred", "user:user_id", ["$u1", "$__pk_0"])
("pred", "user:user_id", ["$u2", "$__pk_0"])
```

System-prefixed temporary names are reserved.

## 8. `evaluate/accept` Runtime Semantics

### 8.1 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="python")
```

- `mode`: `python` (default) or `engine`.
- `engine` requires a registered runtime adapter (for example Souffle).

### 8.2 `CandidateSet` key fields

- `candidate_id`: per-run handle
- `candidate_key`: cross-run stable key
- `candidate_kind`: `fact` / `entity`
- `payload`:
  - fact: `{"pred_id": ..., "terms": [...]}`
  - entity: `{"entity_type": ..., "resolved_identity": ..., ...}`

### 8.3 `sdk.accept(...)`

```python
sdk.accept(candidate, approved_by="alice", note="ok", dry_run=False)
```

Accept sugar keys:
- `approved_by`
- `note`
- `dry_run`
- `identity_override` (for incomplete entity identity)
- `meta_overrides` (can carry the same sugar keys)

Parameter boundaries:
- `accept(CandidateSet, ...)` accepts exactly one positional argument; extra positional arguments raise `SDKStoreError`.
- `meta_overrides` only supports `approved_by` / `note` / `dry_run` / `identity_override`; unknown keys fail.
- If the same sugar key is provided in both `meta_overrides` and top-level keyword args, SDK raises duplicate-option error.

Repeated accept on the same candidate is idempotent no-op (`duplicate`).

## 9. Temporal Boundary (Current Status)

Implemented:
- Read-side temporal filtering via `snapshot.assertions.<field>.at(t)` and `.version(v)`.

Not open yet:
- derivation/runtime `temporal_view` parameter.
- temporal write semantics in Rule/Derivation head.

Explicit behavior:
- Authoring derivation payload with `temporal_view` fails compile.
- `sdk.evaluate(..., temporal_view=...)` raises `SDKStoreError`.

## 10. Minimal End-to-End Examples

### 10.1 Fact candidate

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    drv = Derivation(
        id="drv.alias",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

fact = next(c for c in sdk.evaluate(drv) if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 10.2 Entity candidate + dependent facts

```python
with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[User(u), Pred("user:lang_pref", u, lang)],
        head=Speaks(user=u, language=lang),
    )

rows = sdk.accept_many(sdk.evaluate(drv), mode="atomic")
```
