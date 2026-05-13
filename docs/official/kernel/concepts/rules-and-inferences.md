# Rules, inferences, and candidate facts

Rules and inferences are both reusable descriptions over a `FactGraph`, but
they answer different questions.

| Question | Object |
| --- | --- |
| What already matches in the current graph? | `Rule` |
| What new facts could be proposed from current facts? | `Inference` |
| What exactly would be written if approved? | `CandidateSet` |
| What appends proposed facts to the ledger? | `fg.eval.accept(...)` |

The distinction is not just naming. It is what keeps read-only analysis,
candidate review, and ledger writes separate.

## Rule: a reusable read pattern

A `Rule` reads the graph. It has a `where` body that matches facts and a
`select` list that chooses the output variables.

```python
from kernel.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Rule,
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
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:seed_tag", u, tag)], id="seed_path")],
    )

rows = fg.eval.run(seeded_tags)

assert rows == [{"u": alice, "tag": "engineer"}]
assert tuple(fg.read.get(User, user_id="u-1").tags) == ()
```

The final assertion is the point: running a rule did not write `User.tags`.
The rule observed `seed_tag` and returned a row.

## Inference: a candidate producer

An `Inference` has a similar body, but its result is a proposed target fact.
Evaluation produces candidates. It still does not write to the graph.

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:seed_tag", u, tag)], id="seed_path")],
        target="user:tags",
        head_vars=[u, tag],
    )

candidates = fg.eval.evaluate(tags_from_seed)

assert len(candidates) == 1
assert candidates[0].target == "user:tags"
assert tuple(fg.read.get(User, user_id="u-1").tags) == ()
```

This is the second important boundary: `evaluate(...)` creates a reviewable
candidate set. It does not commit the candidate.

## Accept: the write boundary

`fg.eval.accept(...)` is where an inference result becomes a ledger assertion.

```python
accepted = fg.eval.accept(candidates[0])

assert accepted.accepted_count == 1
assert accepted.written_assertions[0]["pred_id"] == "user:tags"
assert tuple(fg.read.get(User, user_id="u-1").tags) == ("engineer",)
```

This two-step lifecycle is deliberate:

- You can inspect candidates before writing them.
- You can compare different engines or semantics settings.
- You can put approval, review, or audit around the write boundary.
- The ledger records only what you explicitly accept.

In short:

```text
Rule      -> run      -> rows
Inference -> evaluate -> CandidateSet -> accept -> assertions
```

## Branches give structure a name

`Branch(...)` groups one pathway through a rule body. The optional `id` gives
that pathway a stable structural name.

```python
inspected = fg.rules.inspect(tags_from_seed)

assert inspected["kind"] == "Inference"
assert inspected["branches"][0]["id"] == "seed_path"
assert inspected["branches"][0]["fallback_id"] == "b0"
assert inspected["branches"][0]["atom_count"] == 1
```

Branch ids matter when a rule has more than one pathway or when an engine
configuration needs to refer to a particular pathway later. If you omit the
id, the SDK still exposes positional fallback ids such as `b0`, but explicit
ids are easier to keep stable.

## RuleRef is not SavedRuleRef

The SDK has two similarly named reference concepts. They live at different
layers.

| Name | Layer | Use |
| --- | --- | --- |
| `RuleRef` | Rule body syntax | Refer to another rule inside a `where` clause |
| `SavedRuleRef` | Authoring registry | Load a persisted rule value object |
| `SavedInferenceRef` | Authoring registry | Load a persisted inference value object |

`RuleRef` is not a runtime selector:

```text
rows = fg.eval.run(RuleRef("rule.id"))        # wrong mental model
```

The saved-asset path is:

```text
saved = fg.rules.save(rule)
rule = fg.rules.load(saved)
rows = fg.eval.run(rule)
```

The extra `load(...)` step is intentional. Runtime methods consume value
objects such as `Rule` and `Inference`; saved refs are durable handles.

## Semantics configure evaluation, not the template

Semantics wrappers such as `ProbLogSemantics` and `PyReasonSemantics` are
call-site evaluation configuration. They do not belong inside the `Inference`
template itself.

That means the same `Inference` can be evaluated under different engines or
profiles without rewriting the template. The lifecycle remains the same:

```text
Inference + semantics -> evaluate -> CandidateSet -> accept -> ledger
```

The quickstart page on semantics shows the public wrapper syntax. The concept
to keep is simpler: a rule template describes what can be derived; semantics
describe how an evaluation engine should interpret that template at runtime.

## What to remember

- `Rule` is a read-only reusable pattern.
- `Inference` is a candidate producer.
- `evaluate(...)` is reviewable and read-only.
- `accept(...)` is the write boundary.
- `Branch(id=...)` gives rule structure a stable name.
- `RuleRef` is a rule-body atom, not a saved-rule handle.
- Saved refs must be loaded before runtime execution.
- Engine semantics are call-site configuration, not part of the rule template.
