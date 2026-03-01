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
    )
```

Fields:
- `id`, `version`, `where` (required)
- `head`
- `target`
- `head_vars`
- `mode`
- `temporal_view`
- `status`
- `materialize_as` (compatibility field, usually optional)
- `id_policy` (compatibility field, only used by legacy `record` path)

Method:
- `drv.to_authoring_payload()`

Head forms:
- fact head: `Entity.field(...)`
- entity head: `EntityType(...)`

Field head constraints:
- kwargs only
- at least one DSL value in kwargs

Notes:
- `status` can be carried in DSL payload.
- Current `sdk.run/evaluate` compile path does not enforce runtime semantics for `status`.

---

## 6. `head` and `materialize_as` (v2)

### 6.1 Default inference (recommended)

When `materialize_as` is omitted, compiler behavior is inferred from head shape:

| Head shape | Default path | Evaluate output |
|---|---|---|
| `EntityType(...)` | entity path | one entity candidate + dependent fact candidates |
| `EntityType.field(...)` | fact path | fact candidates |

Compatibility:
- without `head`, `target + head_vars` still works as fact-only legacy path.

### 6.2 Current role of `materialize_as`

- explicit `materialize_as="fact" | "record"` is still accepted for compatibility.
- new code should prefer omitting it and rely on head inference.
- `materialize_as="record"` is a legacy spelling for the entity path in current runtime behavior.

---

## 7. `id_policy` (compatibility only)

`id_policy` is mainly relevant for legacy `materialize_as="record"` inputs; it is generally unnecessary on the v2 default path.

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

In schema-aware compile path, legacy record derivations can still auto-derive default `identity_fields_v1` when omitted.

---

## 8. `sdk.evaluate(...)` output: `CandidateSet`

Return type: `list[CandidateSet]`

Key fields:
- `candidate_id` (per-run handle)
- `candidate_key` (cross-run stable key)
- `candidate_kind` (`"fact"` / `"entity"`)
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
- `target`: usually `pred_id` for fact candidates, `entity_type` for entity candidates
- `key_tuple_digest`: candidate idempotency key digest
- `support_*`: support/evidence digest metadata used by accept meta and provenance checks

Payload shapes:
- entity candidate (v2):
  - `{"entity_type": ..., "identity_fields": [...], "resolved_identity": {...}, "missing_identity_fields": [...], "proposed_entity_ref": ...}`
- fact candidate (v2):
  - `{"pred_id": ..., "terms": [{"kind": "entity_ref" | "candidate_ref" | "literal", ...}, ...]}`
  - `terms[0]` is always the subject slot (arg0).
- compatibility inputs may still contain `e_ref/rest_terms` or legacy record payloads; new code should prefer v2 payloads.

Note:
- for entity-head derivations, evaluate commonly returns a small graph: one entity candidate plus N dependent fact candidates linked via `candidate_ref`.

---

## 9. `sdk.accept(...)`: result shape and idempotency

Main path:

```python
res = sdk.accept(candidate_set, approved_by="alice")
```

Batch path (recommended for dependency graphs):

```python
rows = sdk.accept_many(cands, mode="atomic")
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
- `entity_ref` (present when an entity candidate is accepted)

### 9.2 Idempotency behavior

Repeated accept of the same candidate becomes no-op:
- no extra writes
- `accepted_count=0`
- `skipped_count=1`
- `skipped_reason_counts={"duplicate": 1}`

### 9.3 `dry_run`

`dry_run=True` does not write ledger and returns a "would write" preview in `written_assertions`.

### 9.4 `accept_many(...)` states

Per-candidate states include:
- `ACCEPTED`
- `DUPLICATE`
- `BLOCKED_DEPENDENCY`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`

Default mode is `atomic`; `best_effort` is optional.

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
