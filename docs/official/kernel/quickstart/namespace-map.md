# Namespace map

This page is a map. It is not a separate subsystem. After the earlier quickstart
pages, this is where you scan the full kernel SDK surface, see the design
philosophy behind each namespace, and find the right call when you know what
you want to do.

Two reading paths:

- If you want to know **what to import**, see the public imports table at the
  bottom.
- If you want to know **which method to call**, scan the namespace tables.

Flat methods on `FactGraph` are still supported for backwards compatibility,
but the namespaced form is the teaching path and the form used by every other
quickstart page.

## Why these namespaces

The public surface is organized concept-first, not storage-first. The
principles below trace back to two architecture commitments in the
layered-architecture design:

- **`FactGraph` is the runtime / connection layer** — the per-session entry
  point that owns reads, writes, evaluation, and evidence helpers.
- **`Database` is the only persistent write point** — the lower identity
  boundary, where durable transactions and content-addressed objects live.
  `FactGraph.attach(db, ...)` binds a runtime over a Database; the Database
  itself is the persistent identity (see
  [Database and durable views](database.md)).

A few principles run through the whole map:

1. **`FactGraph` owns lifecycle.**
   Creating, loading, and saving a graph workspace are top-level entry points,
   not methods on a sub-namespace. Lifecycle answers "where does this graph
   live?", which is a property of the graph itself.

2. **Assertion surfaces are invariant.**
   `fg.read`, `fg.write`, `fg.assertions`, and `fg.assertion_views` describe how facts
   enter and leave the ledger. Those surfaces are stable across releases; new
   capabilities should not reshape them.

3. **Authoring assets live in domain namespaces.**
   `fg.rules.*` and `fg.inferences.*` own save/load/list/get for reusable
   authoring assets. Registry mechanics back them, but the user-facing verb is
   the asset domain, not the storage layer.

4. **Evaluation evidence and persisted review are different surfaces.**
   `fg.eval.evaluate(...)` returns rows that can explain or close themselves.
   `fg.audit` is persisted-record explanation and cross-round review. Mixing
   them would obscure the difference between "this evaluation row" and "what is
   already stored."

5. **Semantics are evaluate-time configuration.**
   `ProbLogSemantics` and `PyReasonSemantics` are call-time arguments to
   `fg.eval.evaluate(...)`. They do not live inside the `Inference` template
   and they do not change the candidate -> accept -> ledger lifecycle.

6. **Public SDK uses `Inference`; substrate may still use `Derivation`.**
   The public candidate-producing value object is `Inference`. Some internal
   protocol, service payload, and proof/audit names still use `derivation_*`
   during the rename window. Tutorials prefer `Inference`.

7. **Workspace is the persistence mechanism; filesystem registry adapters are gone.**
   A20(E) / Q6-A removed `SDKRegistry`, `FileAuthoringRegistry`,
   `registry_root=`, and `registry=`. The normal product path is in-memory
   `Rule(...)` / `Inference(...)`, `FactGraph.create(path=...)`, `fg.save_workspace(...)`,
   and `FactGraph.load_workspace(...)`.

## FactGraph entry points

The top of the map. These are class methods, instance methods, and properties
that live directly on `FactGraph`, not on a namespace.

| Surface | Use it for |
| --- | --- |
| `FactGraph.create(schema_classes=[...])` | Build a new graph. Pass `path=` for a path-backed workspace; pass `ledger_path=` or `artifact_store_root=` for explicit supported components. |
| `FactGraph.load_workspace(path, schema_classes=[...])` | Restore a saved workspace. The loader validates the workspace schema digest against the supplied classes. |
| `FactGraph.attach(db, schema_classes=[...], view=None)` | Bind the SDK to a `Database`. Passing a durable `db.create_view(...)` view creates a read-only, view-scoped runtime. See [Database and durable views](database.md) for the full Database / view tutorial. The signature deliberately **does not include `rules=`** — rule sets are code artifacts, not part of the attach contract; their content digest is computed at `fg.eval.evaluate(...)` time and recorded as `EvaluateResult.rule_set_digest`. |
| `FactGraph.from_schema_classes([...])` | Lower-level class-first constructor. `create(...)` is the normal teaching path. |
| `fg.save_workspace(path=None)` | Persist the graph to its workspace. No-arg save requires a bound path; passing `path` rebinds the graph. |
| `fg.batch(meta=None)` | Open a batch transaction context for grouped writes. |
| `fg.store` | Underlying core store (advanced). |
| `fg.ledger` | Underlying append-only ledger (advanced). |
| `fg.schema_ir` | Compiled schema IR snapshot (advanced). |

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity()
    name: str = Field()


fg = FactGraph.create(schema_classes=[User])
```

## Schema, entities, fields, and assertions

The append-only side of the graph. These four namespaces are the invariant
core: they decide how vocabulary, coordinates, assertions, and frozen
selections appear to the user.

| Surface | Methods | Notes |
| --- | --- | --- |
| `fg.schema` | `register(EntityCls)`, `extend(EntityCls)`, `apply(EntityCls)`, `ingest(...)`, `validate_provenance(obj, *, standard="derivation_v1")` | Schema mutation is explicit: register new entity types, extend existing entity types additively, or apply either safe path. Delete, rename, identity changes, and destructive migrations are not part of the current surface. |
| `fg.entities` | `create(EntityCls, **identity)`, `delete(...)`, `exists(EntityCls, **identity)`, `edit(EntityCls, **identity)`, `ref(EntityCls, **identity)`, `get(EntityCls, **identity)`, `where(EntityCls, **partial_filters)`, `match(EntityCls, rule_or_expr, **ports)` | Owns entity lifecycle, deterministic refs, full-coordinate snapshots, matching-snapshot collections, and rule-backed snapshot reads. |
| `fg.fields` | `set(field, ref, value, meta=None)`, `add(field, ref, value, meta=None)`, `retract(field, ref, value, meta=None)`, `delete(field, ref, meta=None)`, `get(field, ref)` | Appends or retracts field assertions. `set` is for single-cardinality fields; `add` is for multi-cardinality fields. |
| `fg.assertions` | `by_id(asrt_id)`, `by_ids(asrt_ids)`, `field(Field)`, `where(...)`, `active`, `all`, `retract(asrt_id, meta=None)` | Graph-scoped assertion-record readback, selection, and assertion-id retract. See [Assertion records and views](assertions.md) for the full assertion model. |

```text
schema declaration -> managed ref -> assertion write -> snapshot read
```

Assertion ids are ledger records. Entity refs are coordinates. Keep those two
ideas separate when reading the rest of the API.

## Frozen views

`fg.assertion_views` stores session-local named frozen selections of assertion ids. A view
is not a read policy and not a dynamic query.

| Surface | Methods | Returns |
| --- | --- | --- |
| `fg.assertion_views` | `create(name, asrt_ids=[...])`, `update(name, asrt_ids=[...])`, `delete(name)`, `get(name)`, `list()` | `FrozenAssertionSet` per item; `dict[str, FrozenAssertionSet]` for `list()`. |

Session-local `fg.assertion_views` entries are in-memory and are not part of the
workspace save format. Durable Database views are created with
`db.create_view(...)`; consume those through `FactGraph.attach(db, view=view)`.
The attached runtime is read-only and automatically scopes reads and evaluation
to the view's assertion ids. Method-level `view=` on read/evaluate calls remains
unsupported.

## Rules, inferences, and evaluation

The reasoning side. These namespaces own how rule/inference values are
described and executed.

| Surface | Methods | Notes |
| --- | --- | --- |
| `fg.rules` | `inspect(rule_or_inference_or_query)` | `inspect(...)` shows structure for in-memory `Rule`, `Inference`, or `Query` values. |
| `fg.inferences` | *(empty namespace)* | Inferences are in-memory `Inference(...)` values evaluated through `fg.eval.evaluate(...)`. The empty namespace is a deliberate **v0.2 compatibility placeholder** — `Inference` authoring stays available but new code prefers application `Rule` (`build_application_rule(...)`) + `RuleExpr` composition (see [Rules and inferences](rules-and-inferences.md#evaluate-an-inference)); the namespace remains as a reserved name without removal date. |
| `fg.eval` | `evaluate(inference_or_expr, *, head=None, engine=None, semantics=None)`, `explain(expr, *, head=closed_head)`, `inspect_semantics(semantics_or_profile)` | `evaluate(...)` is read-only and returns `EvaluateResult`. `explain(...)` replays a closed-head explanation. `inspect_semantics(...)` previews wrapper or profile shape without running an engine. |

Public DSL value objects are `Rule`, `Inference`, `Query`, `Case`, `Pred`,
`Not`, `RuleRef`, and `vars`. Saved rule/inference handles were removed; pass
the value objects directly to `fg.eval.*`.

## Evidence and audit

Different review surfaces with different boundaries.

| Surface | Methods | Notes |
| --- | --- | --- |
| `EvaluateRow` | `explain()`, `close()` | Row-level evidence and closed-head replay anchors. |
| `fg.eval` | `explain(expr, head=closed_head)` | Manual closed-head replay. |
| `fg.audit` | `explain(asrt_id_or_record)`, `conflicts(record_or_entity_field)`, `diff_proof_frames(...)` | Persisted-fact explanation and cross-round proof-frame diff. |

`fg.audit.explain(...)` is the user-facing bridge into evidence in the
quickstart path: assertion ids first, then fact-level explanation. Durable
cross-engine `EvidenceGraph` objects, rendered proof pages, and round-event
archives are audit-layer advanced surfaces, not the beginner read/write path.

## Package surface

`fg.package` is for portable distribution and replay, not workspace
persistence.

| Surface | Methods | Notes |
| --- | --- | --- |
| `fg.package` | `export_package(out_dir, options)`, `run_package(package_dir, entrypoints=[...], engine="souffle")` | Packages and workspaces have different scopes. Workspace lifecycle is `FactGraph.create(path=...)`, `fg.save_workspace(...)`, and `FactGraph.load_workspace(...)`. |

## Public imports panorama

Everything in `factgraph.sdk.__all__`, grouped by purpose. The intent of this
table is to answer "what should I import for this task?" without scanning the
whole module.

| Group | Names | Use it for |
| --- | --- | --- |
| Graph entry point | `FactGraph`, `SDKStore` | Create / load / save the graph. `FactGraph` is the alias used in docs; `SDKStore` is the same class for advanced use. |
| Schema declaration | `Entity`, `Identity`, `Field`, `Relationship` | Define entity vocabulary and field coordinates. |
| Rule DSL | `Rule`, `Inference`, `Query`, `Case`, `Pred`, `Not`, `RuleRef`, `vars` | Author saved rules, inferences, ad-hoc queries, and rule-body atoms. |
| Persistence handles | `SchemaAddResult` | Return type from `fg.schema.register`, `extend`, or `apply`. Rule/inference persistence handles were removed. |
| Ingest results | `IngestResult`, `ValidationReport` | Return types from `fg.schema.ingest(...)` and `fg.schema.validate_provenance(...)`. |
| Semantics | `ProbLogSemantics`, `PyReasonSemantics`, `SemanticsProfile` | Configure inference evaluation. Wrappers are the teaching path; `SemanticsProfile` is the canonical lower form. |
| Error types | `SDKSchemaError`, `SDKStoreError`, `EntityNotFoundError`, `FrozenSnapshotError`, `CardinalityError`, `EditorClosedError`, `SDKDSLError` | Catch these for kernel-level failure modes. |
| Error codes (advanced) | `INVALID_ROW_FORMAT`, `QUERY_ALIAS_CONFLICT`, `QUERY_INVALID_ROW_FORMAT`, `QUERY_MISSING_REF`, `QUERY_NOT_IMPLEMENTED`, `QUERY_TYPE_MISMATCH`, `QUERY_UNBOUND_VAR` | Stable string constants used inside error messages. |
| Schema compile helpers (advanced) | `build_authoring_schema_from_classes`, `compile_schema_from_classes`, `schema_preflight_from_classes` | Lower-level schema compilation. Not part of the normal teaching path. |

## What is not on this surface

The kernel SDK does not own these surfaces. Some are different layers of the
same project; some are out of scope for `factpy-kernel` entirely.

- Service routes, HTTP payloads, and service authentication.
- Agent workflows, dialog runtime, and conversation memory.
- Extraction pipelines and document ingestion stacks.
- Domain bundles and prepackaged applications.
- Filesystem registry wrappers; they were removed by A20(E) / Q6-A. Use
  in-memory `Rule(...)` / `Inference(...)` values and migrate legacy workspaces
  with `python -m factgraph migrate-workspace <path>`.
- Substrate `derivation_*` names in protocol, registry, and proof internals;
  public SDK uses `Inference`.
- Round capture (`start_round`, `record_round_event`, `finalize_round` in
  `factgraph.audit.round_events`) and audit package loading
  (`factgraph.audit.load_audit_package`); the SDK ships the query-side
  `fg.audit.diff_proof_frames(...)` but not the recorder lifecycle.
- Walker views over evidence results (`ProofFrameView`,
  `SupportArtifactView`, `ProofFrameDiffView` in `factgraph.application.walker`);
  the SDK methods return raw frozen DTOs.
- Frontier introspection (`factgraph.core.rules.frontier`); Why-not requires an
  explicit candidate universe.
- Long-form proof / evidence rendering pipelines beyond the structured DTOs
  returned by `fg.eval.*` and `fg.audit.*`.

## Syntax checklist

- `FactGraph.create(schema_classes=[...], path=...)` is the normal constructor.
- `FactGraph.load_workspace(path, schema_classes=[...])` restores a workspace.
- `fg.save_workspace(path=None)` persists ledger, schema IR, registry, and manifest.
- `fg.batch(meta=...)` opens a batch transaction; batch `save(...)` is unrelated
  to graph save.
- `fg.schema.register(...)`, `fg.schema.extend(...)`, and
  `fg.schema.apply(...)` return `SchemaAddResult`.
- `fg.entities.ref(...)`, `fg.entities.get(...)`, and
  `fg.entities.where(...)` are the entity read entry points.
- `fg.fields.set(...)`, `fg.fields.add(...)`, and `fg.assertions.retract(...)` append
  ledger assertions or retractions.
- `fg.assertions.by_id(...)`, `fg.assertions.by_ids(...)`,
  `fg.assertions.field(Field)`, `fg.assertions.active`, and
  `fg.assertions.all` read assertion records. Chain `.where(...)`,
  `.at(...)`, and `.by_id(...)` after a returned `AssertionRecordSet`;
  use `.where(_meta={"version": v})` for version metadata filters.
- `fg.assertion_views.create/update/delete/get/list` manages frozen assertion-id
  selections.
- `fg.rules.inspect(...)` previews structure for rules, inferences, and
  queries.
- Rules and inferences are in-memory value objects; keep reusable definitions in
  Python code or application configuration.
- `fg.eval.evaluate(inference, engine=..., semantics=...)` returns
  `EvaluateResult`; rows can be explained or closed for manual replay.
- `fg.eval.inspect_semantics(...)` previews semantics shape; it does not run an
  engine.
- `fg.audit.explain(...)`, `fg.audit.conflicts(...)`, and
  `fg.audit.diff_proof_frames(...)` inspect persisted records.
- `fg.package.export_package(...)` / `fg.package.run_package(...)` is for
  portable distribution, distinct from workspace save.
- Flat `FactGraph` methods remain supported, but new docs prefer namespaces.
