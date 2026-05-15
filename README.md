# factgraph

`factgraph` is a Python library for append-only facts, rule-based inference, and auditable reasoning.

It provides a typed fact ledger, a small logic DSL, explicit inference review, assertion-level inspection, named assertion views, and evidence-oriented APIs. The purpose is not only to represent what is currently true, but also to preserve how facts were asserted, derived, revised, and explained.

## Overview

Many applications treat state as mutable data: a value changes, and the previous state disappears unless a separate audit system is added later.

`factgraph` uses an append-only model. Facts are written as assertions into a ledger. Current application state is resolved from the active assertions. Rules and inferences can reason over those facts, propose derived facts, and produce candidates that must be explicitly accepted before they become part of the ledger.

```text
schema -> assertions -> snapshots -> rules/inferences -> candidates -> accepted facts -> evidence
```

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
    role_seed: str = Field(cardinality="single")
    roles: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")

name_id = fg.write.set(User.name, alice, "Alice")
fg.write.set(User.role_seed, alice, "engineer")

snap = fg.read.get(User, user_id="u-1")

assert snap is not None
assert snap.name == "Alice"
assert snap.role_seed == "engineer"
```

A write returns an assertion id. A read returns a snapshot resolved from the current active assertions.

## Assertions And Views

Assertions are the durable records behind facts. Every write returns an `asrt_id`, which can be used for precise lookup, review, retraction, or grouping.

Graph-level assertion access lives under `fg.assertions`:

```python
record = fg.assertions.by_id(name_id)

assert record is not None
assert record.value == "Alice"
assert record.asrt_id == name_id
```

Snapshot-level assertion access lives under `snap.assertions`:

```python
name_record = snap.assertions.field("name").active().by_id(name_id).one()

assert name_record.value == "Alice"
assert name_record.asrt_id == name_id
```

The key distinction is:

| Surface | Purpose |
|---|---|
| `fg.assertions` | Graph-level assertion lookup and selection |
| `snap.assertions` | Assertion access scoped to one entity snapshot |
| `snap.field("name")` | Field-level assertion selection shortcut |

Retractions are explicit and id-based:

```python
fg.write.retract(name_id)
```

The original assertion is not deleted. It remains in history and is no longer active.

Views are named selections of assertion ids. They are created from assertion ids or from objects that carry an `.asrt_id` attribute.

```python
review_view = fg.views.create(
    "name_review",
    asrt_ids=[name_id],
)

records = fg.assertions.by_ids(review_view.asrt_ids)

assert review_view.asrt_ids == frozenset({name_id})
assert records.one().value == "Alice"
```

A view is therefore an assertion-level object:

```text
assertion ids -> named view -> selected assertion records
```

Views are useful for review sets, audit selections, and evidence workflows. They do not change the active fact projection and are not passed as `view=` parameters to `fg.eval.evaluate(...)`.

## Reasoning

`factgraph` includes a small logic DSL for describing patterns over facts.

A `Rule` reads matching facts. An `Inference` proposes new facts. Evaluation is read-only; it produces candidates. Accepting a candidate is the step that writes derived facts into the ledger.

```python
from factgraph.sdk import Branch, Inference, Pred, vars

with vars("u", "role") as (u, role):
    roles_from_seed = Inference(
        id="inf.roles_from_seed",
        version="v1",
        where=[
            Branch(
                [Pred("user:role_seed", u, role)],
                id="seed_path",
            )
        ],
        target="user:roles",
        head_vars=[u, role],
    )

candidates = fg.eval.evaluate(roles_from_seed)

assert len(candidates) == 1
assert tuple(fg.read.get(User, user_id="u-1").roles) == ()

fg.eval.accept(candidates[0])

assert tuple(fg.read.get(User, user_id="u-1").roles) == ("engineer",)
```

The reasoning lifecycle is explicit:

```text
Inference -> evaluate -> CandidateSet -> accept -> ledger assertion
```

This separation allows applications to inspect, compare, approve, or reject derived facts before committing them.

## Logic DSL

Rules, queries, and inferences are built from body atoms:

- `Pred(...)` matches a predicate in the ledger.
- `Entity(var)` requires an entity to exist.
- `var.field == value` matches a typed field.
- `Not([...])` expresses absence.
- `Branch([...], id="...")` names an alternative reasoning path.
- `vars(...)` creates scoped logic variables.

The same structure supports reusable rules, ad-hoc queries, and inference definitions.

## Semantics

Inference evaluation can use different semantics without changing the ledger lifecycle.

`factgraph` exposes public semantics objects for engine-specific configuration:

- `ProbLogSemantics` for ProbLog-style branch probabilities
- `PyReasonSemantics` for PyReason-style time delays and interval bounds
- `SemanticsProfile` for lower-level canonical configuration

Semantics are evaluate-time configuration. They do not live inside the inference template.

## Evidence And What-If

Reasoning systems need inspection surfaces, not just results. `factgraph` includes APIs for checking and explaining whether a fact or inference is supported.

The `fg.what_if` namespace provides read-only counterfactual tools:

- `check(...)` asks whether a concrete inference binding holds.
- `diagnose(...)` localizes why a check failed.
- `why_not(...)` compares a finite candidate universe.
- fact overlays ask what would happen if selected facts changed.
- rule overlays ask what would happen if selected rule atoms changed.

The `fg.audit` namespace supports persisted explanation and proof comparison, including fact explanations and proof-frame diffs.

## API Surfaces

| Surface | Purpose |
|---|---|
| `fg.schema` | Add schema elements |
| `fg.read` | Create entity refs, read snapshots, find entities |
| `fg.write` | Set, add, and retract facts |
| `fg.assertions` | Inspect graph-level assertion records |
| `snap.assertions` | Inspect assertion records for one snapshot |
| `fg.views` | Create named assertion-id selections |
| `fg.rules` | Save, load, and inspect rules |
| `fg.inferences` | Save and load inference definitions |
| `fg.eval` | Run rules, evaluate inferences, accept candidates |
| `fg.what_if` | Check, diagnose, and explore counterfactuals |
| `fg.audit` | Explain persisted facts and compare proof frames |

## Persistence

Graphs can be kept in memory or backed by a workspace path.

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
