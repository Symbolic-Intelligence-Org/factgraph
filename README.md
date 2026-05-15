# FactGraph

FactGraph is a Python framework for symbolic knowledge graphs, rule-based inference, provenance, and explainable fact auditing.

It lets you declare typed entity schemas, write facts into an append-only ledger, evaluate symbolic rules and inferences, inspect candidate evidence, and persist complete graph workspaces.

## Installation

```bash
pip install factgraph
```

FactGraph requires Python 3.11 or newer.

## Minimal example

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

assert snap.name == "Alice"
assert tuple(snap.tags) == ("engineer",)
```

## Core idea

FactGraph is not a mutable table. Writes append assertions to a ledger. Reads resolve the active assertions into read-only snapshots. This makes fact history, retractions, provenance, and audit workflows first-class instead of incidental.

```text
schema declaration -> entity reference -> assertion write -> snapshot read
```

## Public API shape

FactGraph uses a namespaced SDK surface. Flat methods remain possible where supported, but the namespaced form is the recommended path.

| Namespace | Purpose |
| --- | --- |
| `FactGraph.create(...)` / `FactGraph.load(...)` | Create, save, and restore graph workspaces. |
| `fg.schema` | Add schema classes and validate provenance objects. |
| `fg.read` | Create entity references, fetch snapshots, and find entities. |
| `fg.write` | Append facts and retract assertion ids. |
| `fg.assertions` | Read assertion records by id, field, active state, or full ledger view. |
| `fg.views` | Manage named frozen selections of assertion ids. |
| `fg.rules` | Inspect, save, load, list, and get reusable rules. |
| `fg.inferences` | Save, load, list, and get reusable inference templates. |
| `fg.eval` | Run rules, evaluate inferences, inspect semantics, and accept candidates. |
| `fg.what_if` | Perform read-only counterfactual checks and diagnostics. |
| `fg.audit` | Explain persisted facts and compare recorded proof frames. |
| `fg.package` | Export and run portable graph packages. |

## Schema declaration

Schemas are regular Python classes. `Identity` fields define entity identity; `Field` descriptors define facts the graph can store about that entity.

```python
from factgraph.sdk import Entity, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    email: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")
```

Single-cardinality fields keep one current value. Multi-cardinality fields collect values. In both cases, writes append ledger assertions rather than mutating Python objects.

## Assertions and retractions

Every write returns an assertion id. Keep the id when you need precise inspection or retraction.

```python
email_asrt = fg.write.set(User.email, alice, "alice@example.com")
tag_asrt = fg.write.add(User.tags, alice, "reviewer")

record = fg.assertions.by_id(email_asrt)
fg.write.retract(tag_asrt)
```

This is the basis for audit-friendly edits: the read side finds which assertion matters, and the write side revokes that exact assertion id.

## Rules and inferences

Rules read what is already true. Inferences propose new facts. Accepting a candidate writes the proposed fact into the ledger.

```python
from factgraph.sdk import Branch, Inference, Pred, Rule, vars


with vars("u", "tag") as (u, tag):
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:tags", u, tag)], id="seed_path")],
    )

rows = fg.eval.run(seeded_tags)
```

An inference has the same body shape but also names a target predicate and head variables:

```python
with vars("u", "tag") as (u, tag):
    infer_tag = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tags", u, tag)], id="seed_path")],
        target="user:tags",
        head_vars=[u, tag],
    )

candidate_sets = fg.eval.evaluate(infer_tag)

for candidate_set in candidate_sets:
    for candidate in candidate_set.candidates:
        fg.eval.accept(candidate)
```

## Inference semantics

Engine-specific semantics are evaluation-time configuration. They do not live inside the inference template and do not change the candidate lifecycle.

```text
Inference -> evaluate -> CandidateSet -> accept -> ledger assertion
```

FactGraph exposes public wrappers such as `ProbLogSemantics` and `PyReasonSemantics`, plus the lower-level `SemanticsProfile` form for adapter-level control.

```python
from factgraph.sdk import ProbLogSemantics

semantics = ProbLogSemantics(branch_probabilities={"seed_path": 0.8})
inspection = fg.eval.inspect_semantics(semantics)
```

## What-if and audit

`fg.what_if` is for live counterfactual exploration. It does not write to the ledger.

`fg.audit` is for persisted-record explanation, conflicts, and cross-round comparison.

```python
check = fg.what_if.check(...)
diagnosis = fg.what_if.diagnose(...)
explanation = fg.audit.explain_fact("user:tags", "user:u-1", "engineer")
```

Use `what_if` when asking what could happen. Use `audit` when asking what already happened and why.

## Persistence

A path-backed graph can save and load a complete workspace. A workspace contains the ledger, schema metadata, registry, and workspace manifest.

```python
from pathlib import Path

workspace = Path("./factgraph-workspace")
fg = FactGraph.create(schema_classes=[User], path=workspace)

fg.save()

restored = FactGraph.load(workspace, schema_classes=[User])
```

Reusable authoring assets are saved through their own namespaces:

```python
rule_ref = fg.rules.save(seeded_tags)
loaded_rule = fg.rules.load(rule_ref)
```

## Documentation path

A recommended reading order for new users:

1. Your first FactGraph
2. Define a schema
3. Read and write facts
4. Assertion records and views
5. Rules and inferences
6. Configure inference semantics
7. Evidence: what-if and audit
8. Save rules, inferences, and workspaces
9. Namespace map

## Development

This repository uses Pixi for reproducible local environments.

```bash
pixi install
pixi run test
pixi run build
```

Do not commit `.pixi/`; commit `pyproject.toml` and `pixi.lock`.

## Project links

- Homepage: https://symbolic-intelligence.de
- Documentation: https://factgraph.docs.symbolic-intelligence.de
- Repository: https://github.com/Symbolic-Intelligence-Org/factgraph
- Issues: https://github.com/Symbolic-Intelligence-Org/factgraph/issues

## License

See `LICENSE`.