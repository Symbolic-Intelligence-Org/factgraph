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
| ProbLog evaluation defaults or branch probabilities | `ProbLogSemantics(...)` |
| PyReason time delay or interval bounds | `PyReasonSemantics(...)` |
| Lower-level canonical control | `SemanticsProfile(...)` |
| See what a semantics object means | `fg.eval.inspect_semantics(...)` |

Most application code should start with `ProbLogSemantics` or
`PyReasonSemantics`. `SemanticsProfile` is public, but it is the advanced
canonical form that adapters consume internally.

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
you want the engine's default projection without branch-specific configuration.

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

## Use PyReasonSemantics with a Rule

`PyReasonSemantics` configures PyReason-specific time and interval behavior.
The common quickstart knobs are:

- `timestep_delay`: delay attached to compiled rules
- `head_bound`: global interval for rule heads
- `branch_bounds`: per-branch interval overrides keyed by branch id

For a single application `Rule`, use the global fields and leave
`branch_bounds` empty:

```python
pyreason = PyReasonSemantics(
    timestep_delay=2,
    head_bound=[0.7, 0.9],
)

assert pyreason.engine == "pyreason"
assert pyreason.head_bound == (0.7, 0.9)

preview = fg.eval.inspect_semantics(pyreason)
entries = preview["lowered_profile"]["rule_projection"]["pyreason"]

assert preview["semantics_type"] == "PyReasonSemantics"
assert preview["engine"] == "pyreason"
assert {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]} in entries
assert {"target": "rule", "kind": "timestep_delay", "value": 2} in entries
```

Branch-specific `branch_probabilities` and `branch_bounds` require a concrete
multi-branch context such as a `RuleExpr` OR expression or a v0.2 compatibility
`Inference` with explicit branch ids. A single application `Rule` has no public
branch ids, so branch-specific wrapper maps are rejected for that input shape.

## Use SemanticsProfile when you need the canonical form

`SemanticsProfile` is the lower-level profile shape consumed by runtime
adapters. It remains public for advanced users, service JSON compatibility,
and direct canonical configuration.

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
pyreason = PyReasonSemantics(timestep_delay=2, head_bound=[0.7, 0.9])

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
- Use `ProbLogSemantics(...)` for ProbLog defaults or branch probabilities.
- Use `PyReasonSemantics(...)` for PyReason delays, head bounds, and branch
  bounds.
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
