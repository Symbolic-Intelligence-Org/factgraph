# Configure evaluation semantics

The previous pages used the default native evaluator. This page shows how to
attach engine-specific semantics when evaluating an application `Rule` or a
`RuleExpr`. Legacy `Inference` values remain supported for v0.2 compatibility,
but new examples should prefer application `Rule` values.

Semantics are call-time configuration. They do not live inside the rule, and
they do not change the ledger lifecycle:

```text
Rule or RuleExpr -> evaluate -> EvaluateResult rows -> explain/close -> explicit writes if needed
```

Use this page to learn the shape of the public API. It does not teach the
mathematics of ProbLog or PyReason.

## Which semantics object should I use?

| Need | Use |
| --- | --- |
| ProbLog branch probabilities or raw-uncertainty projection | `ProbLogSemantics(...)` |
| PyReason iteration count, rule bounds, or temporal projection | `PyReasonSemantics(...)` |
| Lower-level canonical control | `SemanticsProfile(...)` |
| See what a semantics object means | `fg.eval.inspect_semantics(...)` |

Most application code should start with `ProbLogSemantics` or
`PyReasonSemantics`. `SemanticsProfile` is public, but it is the advanced
canonical form that adapters consume internally.

### Wrappers lower into `SemanticsProfile`

`ProbLogSemantics(...)` and `PyReasonSemantics(...)` are **high-level
wrappers** with engine-specific ergonomics. Internally, both lower into a
canonical `SemanticsProfile` value before any adapter sees them:

| Surface | Accepts | Role |
| --- | --- | --- |
| `ProbLogSemantics(branch_probabilities=..., uncertainty_projection=..., ...)` | ProbLog-specific kwargs | Engine-flavored ergonomic factory. Lowers to `SemanticsProfile` internally. |
| `PyReasonSemantics(iteration_count=..., derived_bound=..., atom_bounds=..., temporal_projection=..., ...)` | PyReason-specific kwargs | Engine-flavored ergonomic factory. Lowers to `SemanticsProfile` internally. |
| `SemanticsProfile(name=..., engine=..., iteration_count=..., uncertainty_projection=..., temporal_projection=..., rule_projection=...)` | Canonical fields | Lower-level data shape. Adapter consumes this directly. |

This is the same high-level-factory / low-level-data-shape pattern as
`build_application_rule(...)` vs `Rule(...)` in
[Rules and inferences](rules-and-inferences.md#why-build_application_rule-instead-of-rule-directly).
The lowering result is visible at the `lowered_profile` field of
`fg.eval.inspect_semantics(wrapper)`; for a `SemanticsProfile` argument the
inspection returns the canonical form directly (no `lowered_profile`).

## Build an application Rule

Application `Rule` is the primary public evaluation input. Use
`build_application_rule(...)` when authoring through the SDK entity DSL.

```python
from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    ProbLogSemantics,
    PyReasonSemantics,
    SDKStoreError,
    SemanticsProfile,
    build_application_rule,
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")

with vars("u", "tag") as (u, tag):
    tags_from_seed = build_application_rule(
        id="rule.tags_from_seed",
        where=[User(u), User(u).tag_seed == tag],
        ports={"user": u, "tag": tag},
    )
```

The same `Rule` is both the evaluated expression and the evaluation head for a
single-rule call:

```python
result = fg.eval.evaluate(tags_from_seed, head=tags_from_seed)

assert result.count() == 1
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

Evaluation returns `EvaluateResult`; it does not write derived facts.

## Use ProbLogSemantics with a Rule

`ProbLogSemantics` selects the ProbLog engine. Empty wrappers are useful when
you want ProbLog evaluation without branch-specific configuration.

```python
problog = ProbLogSemantics()

assert problog.engine == "problog"

preview = fg.eval.inspect_semantics(problog)

assert preview["semantics_type"] == "ProbLogSemantics"
assert preview["engine"] == "problog"
assert preview["lowered_profile"]["engine"] == "problog"
```

Engine-specific evaluation uses the same public call site:

```python
# Shape only. This page does not require a ProbLog runtime to be installed.
# result = fg.eval.evaluate(tags_from_seed, head=tags_from_seed, semantics=problog)
```

If you pass `engine=...` explicitly, it must match the wrapper:

```python
try:
    fg.eval.evaluate(tags_from_seed, head=tags_from_seed, engine="pyreason", semantics=problog)
except SDKStoreError as exc:
    assert "does not match" in str(exc)
else:
    raise AssertionError("mismatched engine should be rejected")
```

Most code should omit `engine=` when using a public wrapper. The SDK derives
the engine from `ProbLogSemantics` or `PyReasonSemantics`.

### ProbLog raw uncertainty projection

Facts can carry raw uncertainty as paired `raw_kind` and `bound` fields; see
[Write assertions](assertions.md#raw-uncertainty-raw_kind-and-bound) for the
write-side contract. ProbLog consumes the probabilistic lane natively, but it
does not silently choose a projection for intervals.

By default, `ProbLogSemantics()` rejects raw uncertainty unless you explicitly
choose a projection policy:

```python
assert problog.uncertainty_projection == {
    "probabilistic": {"policy": "reject"},
    "possibilistic": {"policy": "reject"},
    "fallback": "reject_unconfigured",
}
```

Use an explicit policy when you want to project a raw interval into the point
probability that ProbLog exports:

```python
project_midpoint = ProbLogSemantics(
    uncertainty_projection={
        "probabilistic": {"policy": "midpoint"},
        "fallback": "reject_unconfigured",
    }
)

profile = fg.eval.inspect_semantics(project_midpoint)["lowered_profile"]
assert profile["uncertainty_projection"]["probabilistic"] == {"policy": "midpoint"}
```

ProbLog point export supports `lower`, `midpoint`, and `upper` for interval
bounds. It also supports `identity_probability` for probabilistic degenerate
bounds such as `[0.7, 0.7]`. `probability_interval` and
`possibility_interval` are canonical policy names, but they are not accepted by
ProbLog point export.

This is intentionally anti-silent-ignore: midpoint is a semantic choice, not a
default. If raw uncertainty is present and no matching policy is configured,
the adapter rejects instead of guessing.

## Use PyReasonSemantics with a Rule

`PyReasonSemantics` configures PyReason-specific iteration count, rule bounds,
and temporal projection. The canonical quickstart knobs are:

- `iteration_count`: global PyReason inference round count. The wrapper
  default is `1`.
- `derived_bound`: canonical interval for rule heads.
- `atom_bounds`: body atom intervals keyed by application atom id
  (`<rule_id>:atom_<index>`).
- `temporal_projection`: temporal mode, such as `fact_boundaries` or
  `time_binned`.

For a single application `Rule`, prefer canonical `derived_bound` and
`atom_bounds`:

```python
pyreason = PyReasonSemantics(
    timestep_delay=2,
    iteration_count=3,
    derived_bound=[0.7, 0.9],
    atom_bounds={"rule.tags_from_seed:atom_1": [0.4, 0.8]},
)

assert pyreason.engine == "pyreason"
assert pyreason.iteration_count == 3
assert pyreason.derived_bound == (0.7, 0.9)
assert pyreason.atom_bounds["rule.tags_from_seed:atom_1"] == (0.4, 0.8)

preview = fg.eval.inspect_semantics(pyreason)
entries = preview["lowered_profile"]["rule_projection"]["pyreason"]

assert preview["semantics_type"] == "PyReasonSemantics"
assert preview["engine"] == "pyreason"
assert {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]} in entries
assert {"target": "rule", "kind": "timestep_delay", "value": 2} in entries
```

`atom_bounds` uses the application atom id, not the PyReason positional target
and not an evidence witness key. For a rule with id `rule.tags_from_seed`, body
atoms are addressed as `rule.tags_from_seed:atom_0`,
`rule.tags_from_seed:atom_1`, and so on.

Legacy names remain accepted for compatibility:

- `head_bound` is the old spelling for the rule-head interval. Do not pass both
  `derived_bound` and `head_bound`; that conflict is rejected.
- `branch_bounds` is still accepted for branch-head intervals keyed by explicit
  branch id or fallback branch id. It can coexist with `atom_bounds` because
  body-atom intervals and branch-head intervals are different surfaces.

### PyReason temporal projection

Use `fact_boundaries` for canonical valid-time projection:

```python
by_fact_time = PyReasonSemantics(
    temporal_projection={
        "mode": "fact_boundaries",
        "universe": ["2026-01-01", "2026-12-31"],
    }
)
```

Legacy `valid_time_boundaries` remains accepted for existing profiles, but new
examples should use `fact_boundaries`.

Use `time_binned` when you want a fixed temporal grid:

```python
hourly = PyReasonSemantics(
    temporal_projection={
        "mode": "time_binned",
        "universe": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
        "bin_size": "PT1H",
    }
)
```

`time_binned.bin_size` is intentionally strict. Accepted forms are:

- ISO-style positive days/hours/minutes: `P<n>D`, `PT<n>H`, `PT<n>M`
- short forms: `1d`, `1h`, `15m`, `1m`

The universe duration must be an exact multiple of `bin_size`. Universe
endpoints may be ISO dates or timezone-aware ISO datetimes; datetimes without a
timezone are rejected. Prose such as `"1 month"` or `"approximately a week"` is
not accepted.

`iteration_count` is a global round count and cannot be combined with temporal
modes that also imply PyReason timesteps (`fixed_timesteps`,
`fact_boundaries`, `valid_time_boundaries`, or `time_binned`). The adapter
rejects explicit conflicts instead of choosing a winner.

The default is worth calling out: `PyReasonSemantics()` lowers to canonical
`iteration_count=1`. Direct no-profile PyReason adapter execution still keeps
its existing engine default.

Branch-specific `branch_probabilities` and `branch_bounds` require a concrete
multi-branch context such as a `RuleExpr` OR expression or a v0.2 compatibility
`Inference` with explicit branch ids. A single application `Rule` has no public
branch ids — application `Rule` bodies are **AND-only by design**, with OR
branches expressed at the composition layer via `RuleExpr` or in the
compatibility `Inference` shape — so branch-specific wrapper maps are
rejected for that input shape.

## Use SemanticsProfile when you need the canonical form

`SemanticsProfile` is the lower-level profile shape consumed by runtime
adapters. It remains public for advanced users, service JSON compatibility,
and direct canonical configuration. Public wrappers lower into this shape,
including `iteration_count`, `uncertainty_projection`, `temporal_projection`,
and per-engine `rule_projection` entries.

```python
profile = SemanticsProfile(name="manual.native", engine="native")
profile_preview = fg.eval.inspect_semantics(profile)

assert profile_preview["engine"] == "native"
assert profile_preview["profile"] == "manual.native"
assert "lowered_profile" not in profile_preview
```

Public wrappers return wrapper metadata plus a lowered-profile preview.
`SemanticsProfile` is already canonical, so inspection returns the canonical
inspection directly.

## Semantics do not write facts

Semantics choose how rows are evaluated. Evaluation is still read-only.

```python
before = fg.read.get(User, user_id="u-1")
assert tuple(before.tag) == ()

result = fg.eval.evaluate(tags_from_seed, head=tags_from_seed, semantics=ProbLogSemantics())
row = result.first()
assert row is not None

# A probabilistic adapter may populate raw_kind/bound carriers on rows.
# Deterministic/native rows keep both fields as None.
# See assertions.md "Canonical quantitative carrier" for the underlying
# contract: raw_kind and bound are paired (both None or both populated),
# and deterministic is None/None rather than (1.0, 1.0).
assert (row.raw_kind is None) == (row.bound is None)

row.explain()
row.close()

after = fg.read.get(User, user_id="u-1")
assert tuple(after.tag) == ()
```

Keep this separation in mind:

| Step | Question |
| --- | --- |
| `Rule` / `RuleExpr` | What should be evaluated? |
| `semantics=...` | How should an engine evaluate it? |
| `EvaluateResult` / `EvaluateRow` | What did evaluation derive? |
| explicit writes | Which facts enter the ledger? |

## Compatibility with Inference branch ids

`Inference` and `Branch` remain available as v0.2 compatibility surfaces.
Use them when you need the legacy branch-id authoring shape; prefer application
`Rule` or `RuleExpr` for new examples.

```python
from factgraph.sdk import Branch, Inference, Pred

with vars("u", "tag") as (u, tag):
    inference = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )

branch_profile = ProbLogSemantics(branch_probabilities={"seed_path": 0.7})
```

The branch id `seed_path` is resolved against that concrete `Inference` during
evaluation. The same branch-specific maps can also target RuleExpr branch ids
such as `b0` and `b1`.

## What not to do

Do not put engine semantics inside a `Rule` or `Inference` definition. The same
logic can be evaluated with different semantics objects at call time.

Do not use `SemanticsProfile` for basic ProbLog or PyReason examples unless
you need the advanced canonical form. The wrappers are easier to read.

Do not assume `inspect_semantics(...)` runs an engine. It only shows structure.

Do not expect `evaluate(...)` to write facts. It returns rows; explicit write
APIs decide which facts enter the ledger.

## Complete example

```python
from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    ProbLogSemantics,
    PyReasonSemantics,
    SDKStoreError,
    build_application_rule,
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")

with vars("u", "tag") as (u, tag):
    tags_from_seed = build_application_rule(
        id="rule.tags_from_seed",
        where=[User(u), User(u).tag_seed == tag],
        ports={"user": u, "tag": tag},
    )


problog = ProbLogSemantics()
pyreason = PyReasonSemantics(
    timestep_delay=2,
    iteration_count=3,
    derived_bound=[0.7, 0.9],
    atom_bounds={"rule.tags_from_seed:atom_1": [0.4, 0.8]},
)

assert fg.eval.inspect_semantics(problog)["engine"] == "problog"
assert fg.eval.inspect_semantics(pyreason)["engine"] == "pyreason"

try:
    fg.eval.evaluate(tags_from_seed, head=tags_from_seed, engine="pyreason", semantics=problog)
except SDKStoreError as exc:
    assert "does not match" in str(exc)
else:
    raise AssertionError("mismatched engine should be rejected")

result = fg.eval.evaluate(tags_from_seed, head=tags_from_seed)
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()

row = result.first()
assert row is not None
assert row.explain().status == "passed"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

## Syntax checklist

- Semantics are evaluate-time configuration.
- Use `ProbLogSemantics(...)` for ProbLog defaults, branch probabilities, or
  explicit raw-uncertainty projection.
- ProbLog raw uncertainty defaults to reject; configure
  `uncertainty_projection` when projecting `raw_kind` + `bound` intervals.
- Use `PyReasonSemantics(...)` for PyReason delays, iteration count, canonical
  rule bounds, and temporal projection.
- Prefer `derived_bound` over legacy `head_bound`.
- Use `atom_bounds={"<rule_id>:atom_<index>": [lower, upper]}` for body atom
  intervals.
- Prefer `temporal_projection={"mode": "fact_boundaries", ...}` over legacy
  `valid_time_boundaries`.
- Use `temporal_projection={"mode": "time_binned", "universe": [...],
  "bin_size": ...}` for fixed temporal bins.
- Use `SemanticsProfile(...)` only when you need the canonical lower-level
  profile.
- `fg.eval.inspect_semantics(...)` inspects configuration; it does not run an
  engine.
- The SDK derives `engine=` from public wrappers; explicit mismatches are
  rejected.
- Branch-level semantics require RuleExpr branch ids or compatibility
  `Inference` branch ids.
- Branch ids are lowered to adapter branch indexes such as `branch:0`.
- `evaluate(...)` returns `EvaluateResult` rows and does not write facts.
