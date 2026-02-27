# SDK Rules / Derivations (v1)

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
- `with vars() as (p, c)`

## 2. Rule DSL

```python
with vars("li", "p", "c") as (li, p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[LivesIn(li), li.user == p, li.country == c],
    )
rows = sdk.run(rule)
```

Supported in `where`:
- exists sugar (`LivesIn(li)`)
- path equality sugar (`li.user == p`)
- `Pred(...)`
- `RuleRef(...)`
- `Not([...])`
- comparisons (`== != > >= < <=`)
- OR bodies (`where=[[...], [...]]`)

Limits:
- no chain syntax (`LivesIn(li).user == p`)
- no attr-vs-attr sugar (`a.x == b.x`)
- no non-linear multiplication (`x * y`)
- no string DSL (`sdk.run("...")`)

## 3. `RuleRef` and Dependencies

- `RuleRef("rule_id", version="...")`
- `RuleRef(existing_rule_obj)`

Notes:
- RuleRef targets must be `expose=True`.
- With `sdk.run(...)`, dependency auto-registration happens only if `registry` is not provided.
- `Rule.dependency_rules()` returns direct where-level object dependencies.

## 4. Derivation DSL

```python
with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[LivesIn(li), li.user == u, li.country == c, HasLanguage(hl), hl.country == c, hl.language == l],
        head=Speaks(user=u, language=l),
        materialize_as="record",
    )
```

Head forms:
- fact head: `Entity.field(...)`
- record head: `RecordType(...)`

Field-head constraints:
- kwargs only (no positional args)
- requires at least one DSL value among kwargs

## 5. `run/evaluate/accept`

`sdk.run(...)` accepts:
- SDK `Rule`
- `RuleSpec`
- authoring payload dict
- compiled rule dict

`sdk.evaluate(...)` accepts:
- SDK `Derivation`
- authoring derivation payload dict
- compiled derivation dict
- pass-through call to underlying store evaluate

`sdk.accept(candidate_set, ...)`:
- one positional `CandidateSet`
- allowed override keys: `approved_by`, `note`, `dry_run` (or same keys via `meta_overrides`)

## 6. Schema-Aware Note

In SDK path, object DSL is lowered and then schema-aware compiled.  
Record path sugar is typically rewritten against schema predicates, including custom predicate ids.

