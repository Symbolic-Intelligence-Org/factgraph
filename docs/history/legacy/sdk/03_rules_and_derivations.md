> Archived legacy snapshot.
>
> This file reflects an older SDK semantic layer and is not authoritative for current development.
> Current authoritative source: [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
> Review rationale: [docs/plans/sdk_old_review.md](../../../plans/sdk_old_review.md)

# SDK Rules / Derivations (v1)

This file documents the runtime SDK object DSL (`factpy_kernel.sdk`).

## 1. Rule object DSL

```python
from factpy_kernel.sdk import Rule, RuleRef, Pred, Not, vars

with vars("li", "p", "c") as (li, p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[
            LivesIn(li),        # exists atom
            li.person == p,     # path equality sugar
            li.country == c,
            RuleRef("q_other", version="1.0.0")(p, c),
            Not([Pred("person:blacklist", p, "x")]),
        ],
        expose=True,
    )

rows = sdk.run(rule)
```

`Rule(...)` constraints:

- `id`: non-empty string
- `version`: non-empty string
- `select`: non-empty list
- `where`: non-empty list

## 2. Where syntax supported in SDK object DSL

### 2.1 Atoms

- record exists: `LivesIn(li)`
- predicate atom: `Pred("person:country", p, c)`
- rule reference atom: `RuleRef("q_x", version="1.0.0")(...)`
- negation: `Not([...])`
- tuple atom passthrough: `("pred", "person:country", ["$p", "$c"])`

### 2.2 Comparisons

- `==`, `!=`, `>`, `>=`, `<`, `<=`
- path sugar (equality only): `li.country == c`

Path sugar boundaries:

- only supports `==`
- variable must already be bound by exists atom (`LivesIn(li)` first)
- attribute-to-attribute form is rejected: `a.country == b.country`

### 2.3 OR bodies

Use two-level list form:

```python
where=[
    [LivesIn(li), li.person == p, li.country == c],
    [Pred("person:nationality", p, c)],
]
```

Outer list = OR, each inner list = AND body.

### 2.4 Arithmetic lowering (where)

Linear arithmetic in comparisons is lowered to builtin atoms.

```python
with vars("p", "by", "age") as (p, by, age):
    rule = Rule(
        id="q_adults",
        version="1.0.0",
        select=[p, age],
        where=[
            Pred("person:birth_year", p, by),
            age == (2026 - by),
            age >= 18,
        ],
    )
```

Current boundary:

- `x * const` / `const * x` supported
- `x * y` rejected (non-linear)

## 3. Record path sugar and `pred_id` caveat

`li.field == x` lowers by naming convention:

- exists: `("pred", "<EntityType>:exists", ["$li"])`
- path: `("pred", "<entitytype_lower>:<field>", ["$li", ...])`

This does **not** consult schema `pred_id` override during lowering.
If your schema uses custom `pred_id` names that differ from convention, use `Pred(...)` explicitly.

## 4. Rule references

```python
with vars("p", "c") as (p, c):
    base = Rule(
        id="q_base",
        version="1.0.0",
        select=[p, c],
        where=[Pred("person:country", p, c)],
        expose=True,
    )

with vars("p", "c") as (p, c):
    top = Rule(
        id="q_top",
        version="1.0.0",
        select=[p],
        where=[RuleRef(base)(p, c)],
    )

rows = sdk.run(top)
```

`RuleRef(base_rule_obj)` preserves rule dependency object; `sdk.run(...)` auto-registers dependencies when it builds a local registry.

## 5. Derivation object DSL

### 5.1 Head forms

Fact head (field reference):

```python
head = Person.country(person=p, value=c)
```

Record head (entity call with DSL kwargs):

```python
head = Speaks(user=u, language=l)
```

Note: runtime entity-call DSL mode requires DSL values in kwargs (for example vars).

### 5.2 Derivation declaration

```python
from factpy_kernel.sdk import Derivation

with vars("p", "c") as (p, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country(person=p, value=c),
        where=[Pred("person:country", p, c)],
        materialize_as="fact",  # "fact" | "record"
    )
```

### 5.3 Evaluate and accept

```python
cands = sdk.evaluate(drv)          # list[CandidateSet]
res = sdk.accept(cands[0], approved_by="admin")
```

`sdk.accept(...)` in SDK facade accepts one `CandidateSet` positional argument.
Supported option keys are limited to:

- `approved_by`
- `note`
- `dry_run`

Can be passed as keywords or through `meta_overrides={...}` with the same keys.

## 6. Runtime SDK DSL constraints

- `sdk.run("...")` string DSL is not supported.
- `sdk.evaluate("...")` string DSL is not supported.
- `with vars() as (p, c):` unpack is not supported at runtime; use named/factory mode.
- `Not(...)` requires non-empty list body.
- `Pred(...)` requires non-empty `pred_id` and at least one term.

## 7. Interop note

Object DSL lowers to authoring payload and then goes through the same authoring/core compile path used by non-SDK inputs.
This preserves runtime semantics while keeping user-facing syntax Pythonic.
