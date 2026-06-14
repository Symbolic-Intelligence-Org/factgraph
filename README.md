# FactGraph

FactGraph is a Python library for building auditable, explainable knowledge and reasoning systems.

It provides a structured way to store entities, facts, assertions, rules, provenance, and derived conclusions in a versioned graph. The goal is to make AI-assisted reasoning inspectable: what was known, what was inferred, which rule produced a result, and what evidence supports it.

## Installation

```bash
pip install factgraph
```

## Basic usage

```python
from factgraph.sdk import Entity, FactGraph


class Person(Entity):
    person_id: str
    mother: tuple[str, ...] = ()
    father: tuple[str, ...] = ()


fg = FactGraph.create(
    path="workspace",
    schema_classes=[Person],
)

ann = fg.entities.create(Person, person_id="ann")
fg.fields.add(Person.mother, ann, "amy")

fg.save_workspace()
```

## Core ideas

FactGraph is built around a few core concepts:

* entities: typed objects in the graph
* assertions: auditable claims about entities
* provenance: where a claim came from
* rules: logic used to derive new claims
* explanations: evidence for why a result holds

## Status

FactGraph is under active development. APIs may still change before a stable 1.0 release.

## License

This project is licensed under the Apache License 2.0; see [LICENSE](LICENSE).