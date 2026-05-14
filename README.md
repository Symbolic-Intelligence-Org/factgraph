# factgraph

Append-only fact storage and auditable reasoning for Python.

`factgraph` lets you model typed entities, write facts into an immutable ledger, read current snapshots, run rule-based inferences, and inspect why facts or candidates exist. It is built for systems where provenance matters: data does not just change, it leaves evidence.

## Install

```bash
pip install factgraph
```

## Quickstart

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")

fg.write.set(User.name, alice, "Alice")
fg.write.add(User.tags, alice, "engineer")

snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert tuple(snap.tags) == ("engineer",)
```

## Why factgraph?

Most application state overwrites history. `factgraph` keeps an append-only ledger of assertions and derives current views from that ledger.

That gives you:

- typed Python schemas with `Entity`, `Identity`, and `Field`
- append-only writes with assertion ids
- current read snapshots over active facts
- retractable assertions without deleting history
- rules and inferences that can propose new facts
- audit and what-if surfaces for evidence, checks, and explanation

## Core Model

A `FactGraph` has three everyday concepts:

| Concept | Meaning |
|---|---|
| Schema | The vocabulary of entities and fields the graph can talk about |
| Assertion | One ledger record saying a fact was written or retracted |
| Snapshot | The current read view resolved from active assertions |

Writes append facts. Reads resolve them.

## Rules And Inferences

Rules are read-only patterns over existing facts. Inferences propose new facts, but do not write automatically.

```python
from factgraph.sdk import Branch, Inference, Pred, vars

with vars("u", "tag") as (u, tag):
    infer_tags = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tags", u, tag)], id="seed")],
        target="user:tags",
        head_vars=[u, tag],
    )

candidates = fg.eval.evaluate(infer_tags)

# Review first, then commit:
# fg.eval.accept(candidates[0])
```

The lifecycle is explicit:

```text
Inference -> evaluate -> candidates -> accept -> ledger assertion
```

## Main API Surfaces

| Namespace | Purpose |
|---|---|
| `factgraph.sdk` | Public Python SDK |
| `fg.schema` | Add schema elements |
| `fg.read` | Create refs, get snapshots, find entities |
| `fg.write` | Set, add, retract facts |
| `fg.assertions` | Inspect assertion records |
| `fg.rules` | Save, load, inspect rules |
| `fg.inferences` | Save and load inference definitions |
| `fg.eval` | Run rules, evaluate inferences, accept candidates |
| `fg.what_if` | Check and diagnose counterfactuals |
| `fg.audit` | Explain persisted facts and proof changes |

## Persistence

Use a path-backed graph when you want to save and restore state:

```python
fg = FactGraph.create(schema_classes=[User], path="workspace")
fg.save()

restored = FactGraph.load("workspace", schema_classes=[User])
```

A workspace stores the ledger, schema metadata, registry, and manifest.

## Development

```bash
pixi run test
pixi run build
```

## License

Licensed under the Apache License, Version 2.0.

Copyright 2026 Symbolic Intelligence GbR.
