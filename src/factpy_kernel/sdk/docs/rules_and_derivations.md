# SDK Rules / Derivations (v1)

## Recommended user-facing style

Use SDK object APIs instead of raw spec dicts for common workflows:

```python
from factpy_kernel.sdk import Rule, Derivation, RuleRef, Pred, Not, vars

with vars("p", "c") as (p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[Pred("person:country", p, c), Not([Pred("person:blacklist", p, "x")])],
    )
```

Run/evaluate/accept:

```python
rows = sdk.run(rule)
cands = sdk.evaluate(derivation)
res = sdk.accept(cands[0], meta_overrides={"approved_by": "admin"})
```

## v1 where support (SDK object DSL)

Supported:

- record exists: `LivesIn(li)`
- path equality sugar: `li.person == p`
- infix comparisons for vars/literals: `x == y`, `x != y`, `x >= 3`, `x < 10`
- `RuleRef("id", version="1.0.0")(...)`
- raw predicate helper: `Pred("person:country", p, c)`
- `Not([...])`
- OR via two-level `where=[[...], [...]]`

Known v1 limitations (documented by design):

- attribute-to-attribute sugar (e.g. `a.country == b.country`) is not lowered automatically in object DSL; bind one side to a variable first
- linear arithmetic lowering is supported for common cases (e.g. `age == (2026 - by)`); non-linear terms such as `x * y` remain unsupported in v1

## Compatibility notes

- SDK object DSL lowers to authoring payload/spec and reuses existing authoring/core compile paths.
- Raw dict/spec payload APIs remain available for advanced users and tooling integration.
- `Pred(...)` / `Not(...)` can be mixed directly with tuple-form atoms inside `where`.
