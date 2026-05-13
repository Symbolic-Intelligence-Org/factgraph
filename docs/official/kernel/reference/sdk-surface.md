# SDK surface

This page maps the public `kernel.sdk` surface. It is a navigation reference,
not a tutorial. Start with the quickstart pages if you want a guided path.

## Import surface

`kernel.sdk.__all__` currently exports 41 names. They fall into these groups:

| Group | Exports |
| --- | --- |
| Graph entrypoints | `FactGraph`, `SDKStore` |
| Schema declarations | `Entity`, `Field`, `Identity`, `Relationship` |
| Rules, queries, inferences | `Rule`, `RuleRef`, `Inference`, `Query`, `Branch`, `Pred`, `Not`, `vars` |
| Semantics | `ProbLogSemantics`, `PyReasonSemantics`, `SemanticsProfile` |
| Persistence handles | `SavedRuleRef`, `SavedInferenceRef` |
| Schema mutation result | `SchemaAddResult` |
| Read policy | `ReadPolicy` |
| Ingest and validation DTOs | `IngestResult`, `ValidationReport` |
| Query constants | `INVALID_ROW_FORMAT`, `QUERY_MISSING_REF`, `QUERY_TYPE_MISMATCH`, `QUERY_ALIAS_CONFLICT`, `QUERY_UNBOUND_VAR`, `QUERY_INVALID_ROW_FORMAT`, `QUERY_NOT_IMPLEMENTED` |
| Error types | `SDKSchemaError`, `SDKStoreError`, `SDKRegistryError`, `EntityNotFoundError`, `FrozenSnapshotError`, `CardinalityError`, `EditorClosedError`, `SDKDSLError` |
| Advanced schema helpers | `build_authoring_schema_from_classes`, `compile_schema_from_classes`, `schema_preflight_from_classes` |

The ordinary entrypoint is:

```python
from kernel.sdk import FactGraph
```

Use advanced helpers only when you need schema compiler output directly. Most
applications should create a graph with `FactGraph.create(...)`.

## FactGraph namespaces

`FactGraph` groups user workflows into read-only namespaces. The namespaces are
stable entrypoints; they do not expose mutable manager state.

| Namespace | Purpose |
| --- | --- |
| `fg.schema` | Additive schema extension |
| `fg.read` | Build refs and read entity snapshots |
| `fg.write` | Append or retract assertions |
| `fg.rules` | Inspect and persist rules |
| `fg.inferences` | Persist inferences |
| `fg.eval` | Run rules, evaluate inferences, accept candidates, inspect semantics |
| `fg.what_if` | Hypothetical checks and diagnostics |
| `fg.audit` | Post-hoc explanation and conflict analysis |
| `fg.package` | Package export/run surface |
| `fg.views` | Named frozen assertion-id selections |

## Lifecycle entrypoints

| Method | Use |
| --- | --- |
| `FactGraph.create(schema_classes=[...])` | Create a graph from schema declarations |
| `FactGraph.create(path=..., schema_classes=[...])` | Create a graph bound to a workspace path |
| `fg.save()` | Save the bound workspace |
| `fg.save(path)` | Save to a workspace path and bind the graph there |
| `FactGraph.load(path, schema_classes=[...])` | Restore a saved workspace with matching schema classes |

`from_schema_classes(...)` remains a lower-level constructor path on
`SDKStore`. The official docs use `FactGraph.create(...)`.

## Schema namespace

| Method | Use |
| --- | --- |
| `fg.schema.add(EntityCls)` | Add a new entity type or add non-identity fields with a replacement class |
| `fg.schema.add(schema_classes=[...])` | Add one or more schema classes in one call |

Schema add is additive. It does not delete, rename, migrate, or change identity
fields.

## Read and write namespaces

| Method | Use |
| --- | --- |
| `fg.read.ref(EntityCls, **identity)` | Build an opaque `idref_v1` entity reference |
| `fg.read.get(EntityCls, **identity)` | Read one complete entity coordinate |
| `fg.read.find(EntityCls, **filters)` | Read snapshots matching partial identity and/or field filters |
| `fg.write.set(FieldDescriptor, ref, value, ...)` | Append a single-cardinality assertion |
| `fg.write.add(FieldDescriptor, ref, value, ...)` | Append a multi-cardinality assertion |
| `fg.write.retract(asrt_id, ...)` | Append a retraction for one assertion id |

Reads return snapshots over the assertion ledger. Writes append assertions; they
do not mutate Python entity objects in place.

## Rules and inferences

| Method | Use |
| --- | --- |
| `fg.rules.inspect(rule_or_inference)` | Inspect branch and atom structure |
| `fg.rules.save(rule)` | Persist a `Rule` as an authoring asset |
| `fg.rules.load(saved_ref)` | Load a persisted `Rule` value object |
| `fg.rules.list()` | List saved rule handles |
| `fg.rules.get(rule_id)` | Get the latest saved rule handle |
| `fg.inferences.save(inference)` | Persist an `Inference` as an authoring asset |
| `fg.inferences.load(saved_ref)` | Load a persisted `Inference` value object |
| `fg.inferences.list()` | List saved inference handles |
| `fg.inferences.get(inference_id)` | Get the latest saved inference handle |

`SavedRuleRef` and `SavedInferenceRef` are load handles. Runtime methods consume
loaded `Rule` and `Inference` objects, not saved refs.

## Evaluation

| Method | Use |
| --- | --- |
| `fg.eval.run(rule)` | Run a read-only `Rule` |
| `fg.eval.evaluate(inference, ...)` | Produce candidate facts from an `Inference` |
| `fg.eval.accept(candidate_or_set)` | Append accepted candidate facts to the ledger |
| `fg.eval.accept_many([...])` | Bulk accept multiple candidate sets or requests |
| `fg.eval.inspect_semantics(profile_or_wrapper)` | Inspect semantics configuration without running an engine |

Evaluation is read-only until `accept(...)` writes candidate facts.

## What-if and audit

| Method | Use |
| --- | --- |
| `fg.what_if.check(...)` | Run a one-shot hypothetical inference check |
| `fg.what_if.diagnose(...)` | Diagnose why a desired outcome did or did not appear |
| `fg.what_if.why_not(...)` | Inspect missing support paths |
| `fg.what_if.fact_overlay.check(...)` | Check a proposed fact overlay |
| `fg.what_if.fact_overlay.recheck_proof_frame(...)` | Re-run a fact-overlay check from a proof frame |
| `fg.what_if.rule.disable(...)` | Check behavior with a rule disabled |
| `fg.what_if.rule.literal_replace(...)` | Check behavior with a rule literal replaced |
| `fg.what_if.rule.add_condition(...)` | Check behavior with an extra rule condition |
| `fg.audit.explain_fact(...)` | Explain recorded support for a fact |
| `fg.audit.conflicts(...)` | Return conflict diagnostics |
| `fg.audit.diff_proof_frames(...)` | Compare recorded proof-frame outcomes |

These are advanced surfaces. The quickstart teaches the ordinary
read/write/rule/inference lifecycle first.

## Package and views

| Method | Use |
| --- | --- |
| `fg.package.export_package(...)` | Export an execution package |
| `fg.package.run_package(...)` | Run an exported package |
| `fg.views.create(name, ...)` | Create a named frozen assertion-id view |
| `fg.views.update(name, ...)` | Replace a frozen view's assertion ids |
| `fg.views.delete(name)` | Delete a frozen view |
| `fg.views.get(name)` | Return a frozen view |
| `fg.views.list()` | List frozen views |

Package export is not the same as `fg.save(...)`. A workspace saves graph state;
a package is an execution artifact.

Views are assertion-id selections. They are not read policies and they are not
persisted as part of `fg.save(...)`.
