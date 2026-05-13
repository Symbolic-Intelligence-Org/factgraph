# Namespace map

The quickstart examples use namespaced methods because they make the API shape
easy to scan. The flat methods on `FactGraph` remain supported, but the
namespaced form is the teaching path.

This page is the map. It is not a separate subsystem.

## Main graph namespaces

| Namespace | Use it for |
| --- | --- |
| `fg.schema` | Schema validation and additive schema changes |
| `fg.read` | Entity references, snapshots, and snapshot search |
| `fg.write` | Assertion writes and retractions |
| `fg.assertions` | Direct assertion-record lookup by assertion id |
| `fg.rules` | Rule inspection and saved rule assets |
| `fg.inferences` | Saved inference assets |
| `fg.eval` | Rule/query execution, inference evaluation, and candidate acceptance |
| `fg.what_if` | Counterfactual checks and proof-frame rechecks |
| `fg.audit` | Fact explanations, conflicts, and proof-frame diffs |
| `fg.package` | Package export and package execution |
| `fg.views` | Named frozen assertion-id selections |

`FactGraph` itself is still the single entry point:

```python
from kernel.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


fg = FactGraph.create(schema_classes=[User])
```

## Schema, read, write, and assertions

| Surface | Typical calls |
| --- | --- |
| `fg.schema` | `add(...)`, `ingest(...)`, `validate_provenance(...)` |
| `fg.read` | `ref(...)`, `get(...)`, `find(...)` |
| `fg.write` | `set(...)`, `add(...)`, `retract(...)`, `edit(...)` |
| `fg.assertions` | `by_id(...)`, `by_ids(...)` |

The normal flow is:

```text
schema declaration -> managed ref -> assertion write -> snapshot read
```

Assertion ids are ledger records. Entity refs are coordinates. Keep those two
ideas separate when reading examples.

## Rules, inferences, and evaluation

| Surface | Typical calls |
| --- | --- |
| `fg.rules` | `inspect(...)`, `save(...)`, `load(...)`, `list(...)`, `get(...)` |
| `fg.inferences` | `save(...)`, `load(...)`, `list(...)`, `get(...)` |
| `fg.eval` | `run(...)`, `evaluate(...)`, `accept(...)`, `accept_many(...)`, `inspect_semantics(...)` |

`Rule` and `Query` are read-time objects. `Inference` proposes candidate facts.
`SavedRuleRef` and `SavedInferenceRef` are registry handles; load them before
passing the value object to `fg.eval`.

## What-if, audit, packages, and views

| Surface | Typical calls |
| --- | --- |
| `fg.what_if` | `check(...)`, `diagnose(...)`, `why_not(...)` |
| `fg.what_if.fact_overlay` | `check(...)`, `recheck_proof_frame(...)` |
| `fg.what_if.rule` | `disable(...)`, `literal_replace(...)`, `add_condition(...)` |
| `fg.audit` | `explain_fact(...)`, `conflicts(...)`, `diff_proof_frames(...)` |
| `fg.package` | `export_package(...)`, `run_package(...)` |
| `fg.views` | `create(...)`, `update(...)`, `delete(...)`, `get(...)`, `list(...)` |

These namespaces are still kernel surfaces. Service routes, agent workflows,
extraction pipelines, and domain bundles are outside this documentation set.

`fg.audit` is the user-facing bridge into evidence and explanation. In the
quickstart, the practical path is assertion records first, then
`explain_fact(...)` / `conflicts(...)` for fact-level inspection. Durable
cross-engine `EvidenceGraph` objects and rendered proof pages are audit-layer
advanced surfaces, not the beginner read/write path.

## Registry and workspace are supporting layers

The authoring registry backs `fg.rules.*` and `fg.inferences.*`.
The workspace lifecycle backs `FactGraph.create(path=...)`, `fg.save(...)`,
and `FactGraph.load(...)`.

Use those public surfaces directly. `SDKRegistry` and file-layout details are
implementation support, not the beginner API.

## Syntax checklist

- `fg.schema.add(...)` extends the schema additively.
- `fg.read.ref(...)`, `fg.read.get(...)`, and `fg.read.find(...)` are the read
  entry points.
- `fg.write.set(...)`, `fg.write.add(...)`, and `fg.write.retract(...)` append
  ledger assertions or retractions.
- `fg.assertions.by_id(...)` and `fg.assertions.by_ids(...)` look up exact
  assertion records.
- `fg.eval.run(rule_or_query)` reads; `fg.eval.evaluate(inference)` proposes;
  `fg.eval.accept(candidate)` writes.
- `fg.rules.*` and `fg.inferences.*` persist authoring assets through saved
  refs.
- `fg.save(...)` and `FactGraph.load(...)` persist whole workspaces.
- `fg.audit.explain_fact(...)` and `fg.audit.conflicts(...)` inspect evidence
  around existing facts; `fg.audit.diff_proof_frames(...)` compares recorded
  inference rounds.
- Flat `FactGraph` methods remain supported, but new docs use namespaces.
