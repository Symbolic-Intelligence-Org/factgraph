# Semantics as evaluation configuration

An `Inference` says what could be derived. A semantics object says how an
engine should evaluate that inference.

Those are separate layers:

| Layer | Owns |
| --- | --- |
| `Inference` | reusable logical template |
| `Branch(id=...)` | stable structure names inside the template |
| `ProbLogSemantics` / `PyReasonSemantics` | public engine-specific call-site configuration |
| `SemanticsProfile` | advanced canonical profile consumed by runtime adapters |
| `CandidateSet` | proposed facts from one evaluation |

Keeping semantics outside the template lets the same inference be evaluated in
different ways without changing the authoring asset.

## Start with structure, then configure evaluation

Branch ids are the bridge between a readable template and engine-specific
configuration. Give important pathways explicit ids.

```python
from kernel.sdk import (
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
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    seed_tag: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.seed_tag, alice, "engineer")

with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:seed_tag", u, tag)], id="seed_path")],
        target="user:tags",
        head_vars=[u, tag],
    )

shape = fg.rules.inspect(tags_from_seed)

assert shape["branches"][0]["id"] == "seed_path"
assert shape["branches"][0]["fallback_id"] == "b0"
```

The inference did not mention ProbLog or PyReason. It only named its logical
pathway. The semantics object can later refer to that pathway.

## Public wrappers are the normal path

Use `ProbLogSemantics` or `PyReasonSemantics` when application code wants an
engine-specific option without constructing the full canonical profile.

```python
problog = ProbLogSemantics(branch_probabilities={"seed_path": 0.7})
pyreason = PyReasonSemantics(
    timestep_delay=2,
    head_bound=[0.7, 0.9],
    branch_bounds={"seed_path": [0.8, 1.0]},
)

assert problog.engine == "problog"
assert pyreason.engine == "pyreason"
```

The SDK can derive the engine from the wrapper. That is why the call site can
read naturally:

```text
fg.eval.evaluate(inference, semantics=pyreason)
```

The wrapper selects an engine; the inference remains an engine-independent
template.

## Inspection is structural

`fg.eval.inspect_semantics(...)` shows how a semantics object lowers toward the
canonical profile shape. It does not run an engine.

```python
problog_preview = fg.eval.inspect_semantics(problog)
pyreason_preview = fg.eval.inspect_semantics(pyreason)

assert problog_preview["semantics_type"] == "ProbLogSemantics"
assert problog_preview["engine"] == "problog"
assert problog_preview["lowered_profile"]["engine"] == "problog"

entries = pyreason_preview["lowered_profile"]["rule_projection"]["pyreason"]

assert pyreason_preview["semantics_type"] == "PyReasonSemantics"
assert {"target": "head:0", "kind": "interval", "value": [0.7, 0.9]} in entries
assert {"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]} in entries
assert {"target": "rule", "kind": "timestep_delay", "value": 2} in entries
```

The public wrapper used `seed_path`. The canonical projection uses
`branch:0`. That conversion happens at the SDK boundary while the original
`Inference` object is still available for branch inspection.

## SemanticsProfile is the advanced canonical form

`SemanticsProfile` is still public, but it is the lower-level profile shape.
Use it when you need direct canonical control or when you are working near
service/runtime integration.

```python
profile = SemanticsProfile(name="manual.native", engine="native")
profile_preview = fg.eval.inspect_semantics(profile)

assert profile_preview["profile"] == "manual.native"
assert profile_preview["engine"] == "native"
assert "lowered_profile" not in profile_preview
```

Wrappers lower into a profile. A `SemanticsProfile` is already canonical, so
inspection returns the canonical summary directly.

## Semantics do not change the write boundary

No semantics object writes facts by itself. Evaluation still produces
candidates, and acceptance still appends assertions.

```python
candidate = fg.eval.evaluate(tags_from_seed)[0]

assert tuple(fg.read.get(User, user_id="u-1").tags) == ()

fg.eval.accept(candidate)

assert tuple(fg.read.get(User, user_id="u-1").tags) == ("engineer",)
```

The example uses the native evaluator so it can run without external engines.
The lifecycle is the same when an engine-specific semantics wrapper is supplied:

```text
Inference + semantics -> evaluate -> CandidateSet -> accept -> ledger
```

## What not to encode in an Inference

Do not put engine-specific settings in the `Inference` template just because
one engine needs them. ProbLog branch probabilities, PyReason bounds, temporal
projection, and similar adapter concerns belong at evaluation time.

Do not use branch positions as your primary public vocabulary when a branch has
a meaningful business role. Prefer explicit `Branch(id="...")` names. Fallback
ids such as `b0` are useful for inspection and compatibility, but they are
positional.

Do not treat `inspect_semantics(...)` as execution. It is a shape preview.

## What to remember

- `Inference` describes what could be derived.
- Semantics objects describe how an engine evaluates it.
- `ProbLogSemantics` and `PyReasonSemantics` are the preferred user-facing
  wrappers.
- `SemanticsProfile` is the advanced canonical form.
- Public branch ids lower to canonical positional targets at the SDK boundary.
- `evaluate(...)` still returns candidates; `accept(...)` still writes facts.
