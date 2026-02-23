# SDK Rules / Derivations (v1)

## Recommended user-facing style

Use SDK object APIs instead of raw spec dicts for common workflows:

```python
from factpy_kernel.sdk import Rule, Derivation, RuleRef, vars

with vars("p", "c") as (p, c):
    rule = Rule(
        id="q_country_rows",
        version="1.0.0",
        select=[p, c],
        where=[("pred", "person:country", ["$p", "$c"])],
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
- `Not([...])`
- OR via two-level `where=[[...], [...]]`

Known v1 limitations (documented by design):

- attribute-to-attribute sugar (e.g. `a.country == b.country`) is not lowered automatically in object DSL; bind one side to a variable first
- arithmetic expressions in where terms (e.g. `age == (2026 - by)`) are not supported by the current core where runtime and therefore rejected early by SDK object DSL

## Compatibility notes

- SDK object DSL lowers to authoring payload/spec and reuses existing authoring/core compile paths.
- Raw dict/spec payload APIs remain available for advanced users and tooling integration.
