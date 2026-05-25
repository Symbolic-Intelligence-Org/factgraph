# Configure inference semantics

The previous pages used the default native evaluator. This page shows how to
attach engine-specific semantics when evaluating an `Inference`.

Semantics are call-time configuration. They do not live inside the inference
template, and they do not change the ledger lifecycle:

```text
Inference -> evaluate -> EvaluateResult rows -> explain/close -> explicit writes if needed
```

Use this page to learn the shape of the public API. It does not teach the
mathematics of ProbLog or PyReason.

## Which semantics object should I use?

| Need | Use |
| --- | --- |
| ProbLog branch probabilities | `ProbLogSemantics(...)` |
| PyReason time delay or interval bounds | `PyReasonSemantics(...)` |
| Lower-level canonical control | `SemanticsProfile(...)` |
| See what a semantics object means | `fg.eval.inspect_semantics(...)` |

Most application code should start with `ProbLogSemantics` or
`PyReasonSemantics`. `SemanticsProfile` is public, but it is the advanced
canonical form that adapters consume internally.

## Build an inference with a stable branch id

Branch ids matter because public semantics wrappers refer to branches by id.
Use explicit `Branch(id=...)` values when you plan to configure branch-level
semantics.

```python
from factgraph.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    ProbLogSemantics,
    PyReasonSemantics,
    SemanticsProfile,
    SDKStoreError,
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
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )


inspection = fg.rules.inspect(tags_from_seed)

assert inspection["kind"] == "Inference"
assert inspection["branches"][0]["id"] == "seed_path"
assert inspection["branches"][0]["fallback_id"] == "b0"
```

The explicit id `seed_path` is the stable user-facing key. The fallback id
`b0` is also accepted, but explicit ids make later examples easier to read.

## Inspect ProbLog semantics

`ProbLogSemantics` lets you attach probabilities to branch ids. The SDK can
derive `engine="problog"` from the wrapper, so you usually do not need to pass
`engine=` yourself.

```python
problog = ProbLogSemantics(branch_probabilities={"seed_path": 0.7})

assert problog.engine == "problog"
assert problog.branch_probabilities["seed_path"] == 0.7

preview = fg.eval.inspect_semantics(problog)

assert preview["semantics_type"] == "ProbLogSemantics"
assert preview["engine"] == "problog"
assert preview["lowered_profile"]["engine"] == "problog"
```

The preview is structural. It tells you which engine the wrapper selects and
what canonical profile shape it lowers toward. Branch probabilities are
resolved against a concrete `Inference` when you evaluate that inference,
because only the inference knows which branch id maps to which branch index.

The evaluation call keeps the same lifecycle:

```python
candidates = fg.eval.evaluate(tags_from_seed)

assert len(candidates) == 1
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

Engine-specific evaluation uses the same public call site:

```python
# Shape only. This page does not require a ProbLog runtime to be installed.
# candidates = fg.eval.evaluate(tags_from_seed, semantics=problog)
```

Whether the evaluator is native, ProbLog, or PyReason, `evaluate(...)` produces
candidates. It does not write accepted facts.

If you pass `engine=...` explicitly, it must match the wrapper:

```python
try:
    fg.eval.evaluate(tags_from_seed, engine="pyreason", semantics=problog)
except SDKStoreError as exc:
    assert "does not match" in str(exc)
else:
    raise AssertionError("mismatched engine should be rejected")
```

Most code should omit `engine=` when using a public wrapper. The SDK derives
the engine from `ProbLogSemantics` or `PyReasonSemantics`.

## Inspect PyReason semantics

`PyReasonSemantics` configures PyReason-specific time and interval behavior.
The common quickstart knobs are:

- `timestep_delay`: delay attached to compiled rules
- `head_bound`: global interval for rule heads
- `branch_bounds`: per-branch interval overrides keyed by branch id

```python
pyreason = PyReasonSemantics(
    timestep_delay=2,
    head_bound=[0.7, 0.9],
    branch_bounds={"seed_path": [0.8, 1.0]},
)

assert pyreason.engine == "pyreason"
assert pyreason.head_bound == (0.7, 0.9)
assert pyreason.branch_bounds["seed_path"] == (0.8, 1.0)

preview = fg.eval.inspect_semantics(pyreason)
entries = preview["lowered_profile"]["rule_projection"]["pyreason"]

assert preview["semantics_type"] == "PyReasonSemantics"
assert preview["engine"] == "pyreason"
assert {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]} in entries
assert {"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]} in entries
assert {"target": "rule", "kind": "timestep_delay", "value": 2} in entries
```

The branch-specific bound overrides the global `head_bound` for that branch.
Branches without a branch-specific bound keep the global value.

`inspect_semantics(...)` can preview the wrapper shape without running an
engine. During real evaluation, branch ids are resolved against the concrete
`Inference`. That is why explicit branch ids are useful.

The user-facing branch id is lowered to the adapter's branch index. In the
preview above, `"seed_path"` becomes `"branch:0"` because it is the first branch
in the inference.

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

result = fg.eval.evaluate(inference, semantics=ProbLogSemantics(...))
row = result.first()
assert row is not None
assert row.raw_kind == "probabilistic"

after = fg.read.get(User, user_id="u-1")
assert tuple(after.tag) == ()
```

Keep this separation in mind:

| Step | Question |
| --- | --- |
| `Inference` | What could be derived? |
| `semantics=...` | How should an engine evaluate it? |
| `EvaluateResult` / `EvaluateRow` | What did evaluation derive? |
| explicit writes | Which facts enter the ledger? |

## What not to do

Do not put engine semantics inside the `Inference` definition. The same
inference can be evaluated with different semantics objects.

Do not use `SemanticsProfile` for basic ProbLog or PyReason examples unless
you need the advanced canonical form. The wrappers are easier to read.

Do not assume `inspect_semantics(...)` runs an engine. It only shows structure.

Do not expect `evaluate(...)` to write facts. It returns candidates; accepting
them writes ledger assertions.

## Complete example

```python
from factgraph.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    ProbLogSemantics,
    PyReasonSemantics,
    SDKStoreError,
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
    inference = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )


problog = ProbLogSemantics(branch_probabilities={"seed_path": 0.7})
pyreason = PyReasonSemantics(
    timestep_delay=2,
    head_bound=[0.7, 0.9],
    branch_bounds={"seed_path": [0.8, 1.0]},
)

assert fg.eval.inspect_semantics(problog)["engine"] == "problog"
assert fg.eval.inspect_semantics(pyreason)["engine"] == "pyreason"

try:
    fg.eval.evaluate(inference, engine="pyreason", semantics=problog)
except SDKStoreError as exc:
    assert "does not match" in str(exc)
else:
    raise AssertionError("mismatched engine should be rejected")

result = fg.eval.evaluate(inference)
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()

row = result.first()
assert row is not None
assert row.explain().status == "passed"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

## Syntax checklist

- Semantics are evaluate-time configuration.
- Use `ProbLogSemantics(...)` for ProbLog branch probabilities.
- Use `PyReasonSemantics(...)` for PyReason delays, head bounds, and branch
  bounds.
- Use `SemanticsProfile(...)` only when you need the canonical lower-level
  profile.
- `fg.eval.inspect_semantics(...)` inspects configuration; it does not run an
  engine.
- The SDK derives `engine=` from public wrappers; explicit mismatches are
  rejected.
- Branch-level semantics should use explicit `Branch(id=...)` names.
- Branch ids are lowered to adapter branch indexes such as `branch:0`.
- `evaluate(...)` still returns candidates, and `accept(...)` still writes
  accepted facts.
