# SDK Rules / Derivations Object DSL (v1)

Scope: `src/factpy_kernel/sdk/dsl` + `SDKStore.run/evaluate/accept`

---

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
- `with vars() as (p, c)`

---

## 2. Rule DSL

```python
with vars("li", "p", "c") as (li, p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[
            LivesIn(li),
            li.person == p,
            li.country == c,
            RuleRef("q_other", version="1.0.0")(p, c),
            Not([Pred("person:blacklist", p, "x")]),
        ],
        expose=True,
    )
rows = sdk.run(rule)
```

`Rule(...)` constraints:
- `id` / `version` must be non-empty strings
- `select` / `where` must be non-empty lists

Methods:
- `rule.to_authoring_payload()`
- `rule.dependency_rules()`
  - Returns direct `RuleRef(RuleObj)` dependencies visible in this rule's `where`.
  - Not a full transitive closure in one call.

---

## 3. `where` syntax support

Supported:
- record exists sugar: `LivesIn(li)`
- path equality sugar: `li.person == p`
- predicate atom: `Pred("person:country", p, c)`
- rule reference: `RuleRef(...)(...)`
- negation: `Not([...])`
- comparisons: `== != > >= < <=`
- OR branches: `where=[[...], [...]]`
- linear arithmetic: `age == (2026 - by)`, `x * 2`, `2 * x`

Limits:
- path sugar supports only `==`
- no attr-vs-attr sugar: `a.country == b.country`
- no non-linear multiplication: `x * y`
- no string DSL
- no chained form: `LivesIn(li).person == p`

---

## 4. `RuleRef`, `expose=True`, and dependency registration

Construction:

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

Call:

```python
RuleRef(...)(p, c)
```

Rules:
- RuleRef target must be `expose=True`, otherwise runtime `RuleCompileError`.
- With `sdk.run(..., registry=None)`, SDK auto-registers `RuleRef(RuleObj)` dependencies (including recursive object deps).
- If `registry` is explicitly provided, SDK does not auto-fill dependencies.
- Auto-registration only solves dependency presence in registry; it does not bypass the `expose=True` constraint.

---

## 5. Derivation DSL

```python
with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[
            LivesIn(li), li.user == u, li.country == c,
            HasLanguage(hl), hl.country == c, hl.language == l,
        ],
        head=Speaks(user=u, language=l),
        materialize_as="record",
    )
```

Fields:
- `id`, `version`, `where` (required)
- `head`
- `materialize_as`
- `target`
- `head_vars`
- `mode`
- `temporal_view`
- `status`
- `id_policy`

Method:
- `drv.to_authoring_payload()`

Head forms:
- fact head (common): `Entity.field(...)`
- record head (common): `RecordType(...)`

Field head constraints:
- kwargs only
- at least one DSL value in kwargs

Notes:
- `status` can be carried in DSL payload.
- Current `sdk.run/evaluate` compile path does not enforce runtime semantics for `status`.

---

## 6. `materialize_as` semantics (core)

`materialize_as` controls what `accept` writes:

| Value | Write behavior |
|---|---|
| `"fact"` | writes target business predicate assertion (no new entity creation) |
| `"record"` | materializes reified record: `<RecordType>:exists` + role facts |

### 6.1 `materialize_as="record"`

Hard constraints:
- requires `head`
- `head` must be entity head (`RecordType(...)`)
- in schema-aware compile path, head kwargs must match record role field names

Example:

```python
head = Speaks(user=u, language=l)
```

`uid=` and other identity fields are not role kwargs and will fail in compile/runtime checks.

### 6.2 `materialize_as="fact"`

Most common form is a field head:

```python
head = Person.country(person=p, value=c)
```

But this is not the only path. Current implementation also supports:
- direct `target + head_vars`
- entity-type head rewritten to projection fact in schema-aware compile (requires projection metadata in schema)

So describe field head as "common/recommended", not an exclusive hard requirement.

---

## 7. `id_policy` (record materialization identity policy)

`id_policy` is meaningful only for `materialize_as="record"`. It decides record e_ref derivation and idempotency behavior.

Supported in v1:
- `key_tuple_digest_v1`
- `identity_fields_v1`

### 7.1 `key_tuple_digest_v1`

Minimal policy; derives record identity from candidate key digest.

### 7.2 `identity_fields_v1`

Explicitly builds identity from selected role fields; typically better for production stability.

```python
id_policy={
  "kind": "identity_fields_v1",
  "fields": [
    {"name": "person", "role": "person", "type_domain": "entity_ref"},
    {"name": "language", "role": "language", "type_domain": "entity_ref"},
  ],
}
```

In schema-aware compile path, record derivations can auto-derive a default `identity_fields_v1` when omitted. Explicit declaration is still recommended for production.

---

## 8. `sdk.evaluate(...)` output: `CandidateSet`

Return type: `list[CandidateSet]`

Key fields:
- `derivation_id`
- `derivation_version`
- `run_id`
- `target`
- `key_tuple_digest`
- `tup_digest`
- `payload`
- `support_digest`
- `support_kind`
- `generated_at`
- `state`

Interpretation:
- `run_id`: evaluate run identifier
- `target`: usually predicate id for fact path, record type for record path
- `key_tuple_digest`: candidate idempotency key digest
- `support_*`: support/evidence digest metadata used by accept meta and provenance checks

Payload shapes:
- fact candidate: `{"e_ref": ..., "rest_terms": ...}`
- record candidate: `{"materialize_as": "record", "record_type": ..., "record_exists_pred_id": ..., "id_policy": ..., "roles": ...}`

---

## 9. `sdk.accept(...)`: result shape and idempotency

Main path:

```python
res = sdk.accept(candidate_set, approved_by="alice")
```

Facade sugar:
- `approved_by=...`
- `note=...`
- `dry_run=True`
- `meta_overrides={...}` (same keys only)

### 9.1 `AcceptResult` fields

- `materialize_id`
- `run_id`
- `accepted_count`
- `skipped_count`
- `written_assertions`
- `skipped_reason_counts`
- `diagnostics`
- `diagnostics_contract_version`

### 9.2 Idempotency behavior

Repeated accept of the same candidate becomes no-op:
- no extra writes
- `accepted_count=0`
- `skipped_count=1`
- `skipped_reason_counts={"duplicate": 1}`

### 9.3 `dry_run`

`dry_run=True` does not write ledger and returns a "would write" preview in `written_assertions`.

### 9.4 conflict / aborted

Record materialization may return:
- `skipped_reason_counts={"conflict": 1}` or `{"aborted": 1}`
- plus `diagnostics`

`aborted` is terminal for that materialization path and should not be auto-retried blindly.

---

## 10. `mode` / `temporal_view`

### 10.1 `sdk.run(...)`

```python
rows = sdk.run(rule, temporal_view="record")
```

- `temporal_view`: `"record"` | `"current"`

### 10.2 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="python", temporal_view="record")
```

- `mode`: `"python"` | `"engine"`
- `temporal_view`: `"record"` | `"current"`

Notes:
- default mode is `"python"`.
- `"engine"` requires a registered engine evaluator (Souffle adapter is typically registered by importing `factpy_kernel.adapters.souffle`).

---

## 11. Schema-aware note (sugar and custom predicate ids)

In SDK path, object DSL is lowered and then schema-aware compiled:
- exists sugar (for example `LivesIn(li)`) is rewritten to actual exists predicate in schema
- path sugar (for example `li.user == p`) is rewritten to canonical role predicates when schema_ir is available

So in standard `SDKStore.run/evaluate` flow, record sugar usually follows schema custom `pred_id` correctly.  
If you lower/compile outside schema-aware context, prefer explicit `Pred(...)`.
