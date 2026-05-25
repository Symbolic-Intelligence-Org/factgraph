# Rules and inferences

The previous pages wrote facts directly. Rules and inferences let you describe
patterns over those facts.

A `Rule` asks the graph what is already true. It is a reusable read query over
the current snapshot.

An `Inference` evaluates possible derived rows from existing facts. It does not
write by itself. Evaluation returns an `EvaluateResult`; explicit writes still
go through `fg.write.*` or `fg.batch(...)`.

The short version is:

| Need | Use |
| --- | --- |
| Read matching facts | `Rule` + `fg.eval.run(...)` |
| Propose new facts | `Inference` + `fg.eval.evaluate(...)` |
| Explain evaluated rows | `row.explain()` / `fg.eval.explain(...)` |
| Inspect rule shape | `fg.rules.inspect(...)` |

## Start with facts

Rules and inferences work over facts already in the graph. This example keeps
the schema small: `tag_seed` is a direct fact, and `tag` will be inferred from
it.

```python
from kernel.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Query,
    Rule,
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")
```

The predicate id for `User.tag_seed` is `user:tag_seed`. Rule bodies use these
predicate ids to match facts. Later docs cover more advanced authoring patterns;
this page keeps the shape explicit.

## Run a Rule

Use `vars(...)` to create logic variables, `Pred(...)` to match a predicate,
and `Rule(...)` to name the reusable pattern.

```python
with vars("u", "tag") as (u, tag):
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[
            Branch(
                [Pred("user:tag_seed", u, tag)],
                id="seed_path",
            )
        ],
    )
```

The `where` clause describes what must be found. The `select` list describes
what the rule returns. Running the rule is read-only.

```python
rows = fg.eval.run(seeded_tags)

assert rows == [
    {
        "u": alice,
        "tag": "engineer",
    }
]
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

The second assertion matters. The rule found the `tag_seed` fact, but it did
not write a `tag` fact.

## Use Query for one-off projections

Use `Query` when you want an ad-hoc result shape without saving a reusable
rule. It uses the same body language, but the head describes the projected
columns directly.

```python
with vars("u", "tag") as (u, tag):
    seeded_tag_query = Query(
        head=[User(u), User.tag_seed(value=tag)],
        where=[User(u), u.tag_seed == tag],
    )


query_rows = fg.eval.run(seeded_tag_query)

assert len(query_rows) == 1
assert query_rows[0]["u"].ref == alice
assert query_rows[0]["tag"] == "engineer"
```

Queries are read-time projections. They are useful for one-off shapes. Rules
and inferences remain Python value objects; keep reusable definitions in code
or application configuration.

## Evaluate an Inference

An inference can use the same body and propose a new target predicate.

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[
            Branch(
                [Pred("user:tag_seed", u, tag)],
                id="seed_path",
            )
        ],
        target="user:tag",
        head_vars=[u, tag],
    )
```

`fg.eval.evaluate(...)` returns an `EvaluateResult`. It is read-only.

```python
result = fg.eval.evaluate(tags_from_seed)

assert result.count() == 1
row = result.first()
assert row is not None
assert row.claim.name == "user:tag"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

The row says "this inference can derive `user:tag` for this user with this
value." It has not changed the graph.

## Explain a row

```python
explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(tags_from_seed, head=closed_head)

assert explanation.status == "passed"
assert manual.status == "passed"
```

Use explicit write APIs when you want to persist new facts.

## Inspect rule shape

`fg.rules.inspect(...)` shows the structure of a rule or inference without
executing it.

```python
inspected = fg.rules.inspect(tags_from_seed)

assert inspected["kind"] == "Inference"
assert inspected["id"] == "inf.tags_from_seed"
assert inspected["branches"][0]["id"] == "seed_path"
assert inspected["branches"][0]["fallback_id"] == "b0"
assert inspected["branches"][0]["atom_count"] == 1
```

Branch ids are structural names. Use explicit branch ids when a rule has
meaningful pathways that you may want to inspect or configure later. If you do
not provide an id, the SDK still exposes a fallback id such as `b0`.

## RuleRef composes in-memory rules

`RuleRef` is a lower-level body atom used when one rule body depends on another
rule. It is not a persistence handle and it does not read from a filesystem
registry.

In the quickstart, keep the model simple:

- `Rule` reads.
- `Inference` proposes.
- `EvaluateResult` rows wait for review.
- explicit writes persist changes.
- Keep reusable rule/inference definitions in Python code and pass the value
  objects directly to runtime methods.

## Where semantics engines fit

The default examples here use the native evaluation path. FactGraph also has
semantics options for engines such as ProbLog and PyReason. Those options
change how an inference is evaluated; they do not change the basic lifecycle:

```text
Inference -> evaluate -> EvaluateResult rows -> explain/close -> explicit writes if needed
```

Learn the lifecycle first. Engine-specific semantics are an advanced topic.

## Complete example

```python
from kernel.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Query,
    Rule,
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
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
    )

rows = fg.eval.run(seeded_tags)

assert rows == [{"u": alice, "tag": "engineer"}]

with vars("u", "tag") as (u, tag):
    seeded_tag_query = Query(
        head=[User(u), User.tag_seed(value=tag)],
        where=[User(u), u.tag_seed == tag],
    )

query_rows = fg.eval.run(seeded_tag_query)

assert query_rows[0]["tag"] == "engineer"

with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )

result = fg.eval.evaluate(tags_from_seed)

assert result.count() == 1
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()

fg.write.add(User.tag, alice, "engineer")
assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)

inspected = fg.rules.inspect(tags_from_seed)

assert inspected["kind"] == "Inference"
assert inspected["branches"][0]["id"] == "seed_path"
assert inspected["branches"][0]["fallback_id"] == "b0"
```

## Syntax checklist

- Use `vars(...)` to create logic variables for DSL bodies.
- Use `Pred("entity:field", ...)` for explicit predicate literals.
- Use `Branch([...], id="...")` when branch identity matters.
- Use `Rule(id=..., select=[...], where=[...])` for reusable read patterns.
- Run rules with `fg.eval.run(rule)`; running a rule does not write.
- Use `Query(head=..., where=[...])` for ad-hoc read projections.
- Use `Inference(id=..., where=[...], target=..., head_vars=[...])` for
  proposed facts.
- Evaluate inferences with `fg.eval.evaluate(inference)`; evaluation does not
  write.
- Explain rows with `row.explain()` or replay with
  `fg.eval.explain(expr, head=row.close())`.
- Inspect rule or inference structure with `fg.rules.inspect(...)`.
- `RuleRef` is a body-composition tool, not a persistence handle.
- Rule and inference persistence handles were removed; runtime methods consume
  in-memory value objects directly.
- Semantic engines are evaluation configuration; the evaluate/accept lifecycle
  stays the same.
