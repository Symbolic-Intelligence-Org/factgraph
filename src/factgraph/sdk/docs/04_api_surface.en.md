# SDK API Surface Reference

The exact public surface of `factgraph.sdk`. For tutorials see
[`00_user_guide.en.md`](00_user_guide.en.md). For what-if and proof
workflows see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

---

## 0. Namespace Map

`FactGraph` is the canonical entry point. It is a literal alias of
`SDKStore` — both names refer to the same class object and accept the
same calls.

`FactGraph` exposes operations through 8 top-level namespaces and 2
sub-namespaces under `what_if`. The same operations are also available
as flat methods on the same instance; both shapes are permanently
supported.

```python
from factgraph.sdk import FactGraph

fg = FactGraph.create(schema_classes=[User])

# Namespaced (preferred for new code)
fg.read.get(User, user_id="u-1")
fg.write.add(User.tag, alice, "engineer")
fg.what_if.check(inference, binding)
fg.what_if.fact_overlay.check(inference, binding, overlay)
fg.what_if.rule.disable(rule, support, branch_index=0, atom_index=0)
fg.audit.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events)

# Flat (foundational; permanent)
fg.get(User, user_id="u-1")
fg.add(User.tag, alice, "engineer")
fg.check(inference, binding)
fg.check_fact_overlay(inference, binding, overlay)
fg.check_rule_disable(rule, support, branch_index=0, atom_index=0)
fg.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events)
```

| Namespace | Methods |
|---|---|
| `schema` | `ingest`, `validate_provenance` |
| `read` | `get`, `find`, `ref` |
| `write` | `set`, `add`, `retract`, `edit` |
| `eval` | `run`, `evaluate`, `accept`, `accept_many`, `inspect_semantics` |
| `what_if` | `check`, `diagnose`, `why_not` |
| `what_if.fact_overlay` | `check`, `recheck_proof_frame` |
| `what_if.rule` | `disable`, `literal_replace`, `add_condition` |
| `audit` | `explain_fact`, `conflicts`, `diff_proof_frames` |
| `package` | `export_package`, `run_package` |
| `views` | `create`, `update`, `delete`, `get`, `list` |

Namespace accessors return private manager objects. The managers are
read-only — assigning attributes (`fg.what_if.foo = ...`) raises
`FrozenSnapshotError`. They are not part of `factgraph.sdk.__all__` and
should not be imported directly.

---

## 1. Top-Level Exports

Everything below is importable as `from factgraph.sdk import <name>`.
The export list currently has 53 names.

### 1.1 Schema and store

| Symbol | Purpose |
|---|---|
| `Entity` | Base class for entity declarations |
| `Field` | Descriptor for a field with cardinality |
| `Identity` | Descriptor for an identity (primary-key) field |
| `Relationship` | Base class for relationship type declarations |
| `FactGraph` | Canonical entry point (alias of `SDKStore`) |
| `SDKStore` | Foundational entry point (same class as `FactGraph`) |

`Entity` instances render via `__repr__` showing identity and field
values in declaration order; unset `Field` values render as `None`.

`FactGraph.create(schema_classes=[...])` is the canonical constructor.
`FactGraph.load(path, schema_classes=[...])` restores a saved workspace.
`FactGraph.from_schema_classes([...])` remains available as the lower-level
class-first constructor name and does not accept workspace `path=`.

### 1.2 DSL

| Symbol | Purpose |
|---|---|
| `Branch` | Rule `where` branch constructor (alternative conjunction) |
| `Rule` | Legacy-compatible declarative rule (head + body); final top-level `Rule` replacement is deferred to the later legacy hard-cut |
| `LegacyRule` | Explicit alias for the current legacy `Rule` |
| `ApplicationRule` | Transitional explicit alias for `factgraph.application.protocol.Rule` |
| `RuleRef` | Where-clause reference to an exposed rule |
| `Inference` | Multi-rule inference envelope |
| `SchemaAddResult` | Result returned by additive `fg.schema.add(...)`; fields are `old_digest`, `new_digest`, `added_entities`, `added_fields` |
| `Query` | Query over the current store |
| `Pred` | Predicate literal (fact reference) |
| `Not` | Negation operator for body literals |
| `vars` | Logic-variable factory for rule construction |
| `build_application_rule` | Build an `ApplicationRule` from SDK DSL conditions |
| `DSLToApplicationRuleError` | Raised when SDK DSL conditions cannot lower to an `ApplicationRule` |
| `SDKDSLError` | Raised on DSL construction errors |
| `RuleExpr` | Base RuleExpr authoring surface; use `RuleExpr.all(...)` / `RuleExpr.any(...)` or application `Rule` `&` / `|` composition |
| `RuleExprError` (← `SDKDSLError`) | Raised when RuleExpr authoring input violates the expression contract |
| `RuleJoinConstraint` | Immutable RuleExpr join constraint produced by `occurrence.port.eq(other_port)` / `occurrence.port_name.eq(other.port_name)`; initial joins use explicit `.eq(...)`, not Python `==` |
| `RuleExprInspect` | Immutable object returned by `fg.rules.inspect(application_rule_or_rule_expr)`; exposes `ast`, `occurrences`, `joins`, `unjoined_same_name_ports`, `render()`, and `render_compact()` |
| `OccurrenceInspect` | Immutable occurrence descriptor used by `RuleExprInspect.occurrences`; exposes alias, template id, port names, and atom descriptors |
| `AtomDescriptor` | Immutable authoring-time atom descriptor used by `OccurrenceInspect.atoms`; exposes structured fields plus a display `summary` |
| `PortInspect` | Immutable rich port descriptor used by `RuleExprInspect.ports`; exposes port name, kind, entity type, field, and value type |
| `ExplicitBoolError` (← `RuleExprError`) | Raised when application `Rule` or RuleExpr values are used in Python boolean contexts; use `&` / `|`, not `and` / `or` |

The application Rule bridge additionally exposes aggregate helpers from
`factgraph.sdk.dsl` only. `build_application_rule` is available from both
top-level `factgraph.sdk` and `factgraph.sdk.dsl`:

| Symbol | Purpose |
|---|---|
| `agg_count(where=[...])` | Count matching aggregate-filter rows |
| `agg_sum(target, where=[...])` | Sum a numeric target over matching filter rows |
| `agg_min(target, where=[...])` | Minimum target value over matching filter rows |
| `agg_max(target, where=[...])` | Maximum target value over matching filter rows |
| `agg_mean(target, where=[...])` | Mean numeric target value over matching filter rows |

These helpers are not re-exported from top-level `factgraph.sdk` in this slice.
Use `from factgraph.sdk import build_application_rule` and
`from factgraph.sdk.dsl import agg_sum`.

### 1.3 Schema compile helpers

| Symbol | Purpose |
|---|---|
| `build_authoring_schema_from_classes` | Build authoring schema from `Entity` classes |
| `compile_schema_from_classes` | Compile authoring schema into runtime IR |
| `schema_preflight_from_classes` | Validate classes; raise `SDKSchemaError` on issues |

### 1.4 Ingest

| Symbol | Purpose |
|---|---|
| `IngestResult` | Result of `fg.ingest(...)`: counts, ids, validation report |
| `ValidationReport` | Per-row provenance/shape validation outcome |

### 1.5 Errors and error codes

| Class | Triggered by |
|---|---|
| `SDKSchemaError` | Schema compilation, descriptor binding, preflight |
| `SDKStoreError` | Store operations (write, view, batch, query, eval shells) |
| `EntityNotFoundError` (← `SDKStoreError`) | `read.get(...)` / `write.edit(...)` on missing identity |
| `FrozenSnapshotError` (← `SDKStoreError`) | Assigning to read-only attribute (snapshot or namespace) |
| `CardinalityError` (← `SDKStoreError`) | `set` on multi-field, `add` on single-field |
| `EditorClosedError` (← `SDKStoreError`) | Operating on a committed/rolled-back `EntityEditor` |

| Error code | Where it appears |
|---|---|
| `INVALID_ROW_FORMAT` | Generic invalid `row_format=` |
| `QUERY_INVALID_ROW_FORMAT` | Query-specific invalid `row_format=` |
| `QUERY_MISSING_REF` | Query references undeclared field |
| `QUERY_TYPE_MISMATCH` | Query head/literal type mismatch |
| `QUERY_ALIAS_CONFLICT` | Query alias collision |
| `QUERY_UNBOUND_VAR` | Query variable not bound in body |
| `QUERY_NOT_IMPLEMENTED` | Query feature not yet implemented |

---

## 2. `FactGraph` / `SDKStore` Methods

Methods are listed once per logical operation. All have flat (`fg.X(...)`)
and namespaced (`fg.<ns>.X(...)`) call sites; both delegate to the same
implementation.

### 2.1 Constructor

```python
FactGraph.create(
    schema_classes,
    *,
    path=None,
    ledger=None,
    ledger_path=None,
    artifact_store_root=None,
    default_row_format=None,
)
```

Class-validation errors raise `SDKSchemaError`; constructor-path errors
raise `SDKStoreError`. `path=` binds the graph to a compact workspace root and
derives the default `ledger.db` component path and Database schema-object
anchor. Explicit `ledger_path=` may be supplied with `path=` only when it
matches the workspace default. `registry_root=` and `registry=` were removed by
A20(E) / Q6-A; passing either raises `SDKStoreError` with migration guidance.
`artifact_store_root` enables sidecar-backed
explain artifact readback (ignored if a fully constructed `store=` is
supplied).
`FactGraph.from_schema_classes(...)` remains available as the lower-level
class-first constructor name.

```python
FactGraph.load(path, *, schema_classes=[...], default_row_format=None)
fg.save(path=None)
```

`fg.save()` writes the bound workspace. `fg.save(path)` writes and rebinds the
graph to that workspace. An unbound graph raises
`SDKStoreError("workspace path not bound; pass fg.save(path=...) or create with FactGraph.create(path=...)")`.
`FactGraph.load(...)` requires Python schema classes and validates the workspace
manifest digest, ledger schema digest, Database schema object, any legacy
registry schema entry that is still present, and the digest compiled from the
supplied classes.

Workspace v1 layout:

```text
workspace/
  factgraph_workspace.json
  ledger.db
  db/
    objects/
      schema/
        <schema-digest>.json
```

`factgraph_workspace.json` records `factgraph_workspace_version="1"`,
`save_scope="level_4"`, `schema_digest`, component paths, and timestamps.
Level 4 includes the ledger and Database schema object. The top-level
`schema_digest` is a compatibility cross-check; the authoritative schema bytes
live under `db/objects/schema/`. Level 4 excludes artifact sidecars, in-memory
views, audit/evidence round files, package exports, saved rules/inferences, and
new registry content.

### 2.2 Schema namespace (`fg.schema.*`)

| Method | One-liner |
|---|---|
| `add(EntityCls, ...)` / `add(schema_classes=[...])` | Add new Entity classes or non-identity fields on existing Entity declarations; returns `SchemaAddResult` |
| `ingest(items, *, meta=None, allow_sensitive_meta=False)` | Bulk-insert assertions; `meta` merges into every item's meta. Returns `IngestResult` |
| `validate_provenance(obj, *, standard="derivation_v1")` | Inspect provenance shape without writing; returns `ValidationReport` |

`fg.schema.add(...)` is intentionally additive-only in this slice. It accepts
new `Entity` classes and replacement declarations with the same Python class
name when they add only non-identity fields. It validates that every existing
entity, identity field, and predicate remains compatible, then updates the
in-memory graph schema, core store schema, ledger schema digest, and
graph-bound registry schema entry if one was explicitly configured. If the graph
is bound to a workspace, the Database schema object is updated immediately, but
the workspace manifest is not rewritten until a later explicit `fg.save(...)`.

Field-add uses a replacement class object. After a field-add succeeds, reads
or writes through superseded entity classes or their descriptors raise
`SDKStoreError`; use the post-add class object. Existing assertions are not
backfilled. Missing added fields use normal read absence semantics: `None` for
single-cardinality fields and `()` for multi-cardinality fields.

Re-adding an equivalent existing class is an idempotent no-op:
`SchemaAddResult.added_entities == []` and
`SchemaAddResult.added_fields == []`. Destructive schema operations are not
public: `fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, and
`fg.schema.deprecate` are deferred to future migration-planning work.

### 2.3 Read namespace (`fg.read.*`)

| Method | One-liner |
|---|---|
| `get(entity_cls, **identity)` | Fetch single entity by identity or `None` |
| `find(entity_cls, *, limit=None, **filters)` | Filter entities |
| `ref(entity_cls, **identity)` | Encode an entity reference string |

### 2.4 Write namespace (`fg.write.*`)

| Method | One-liner |
|---|---|
| `set(field, ref, value, *, meta=None)` | Set a single-cardinality field |
| `add(field, ref, value, *, meta=None)` | Append to a multi-cardinality field |
| `retract(asrt_id, *, meta=None)` | Retract a specific assertion |
| `edit(entity_cls, **identity)` | Open an `EntityEditor` transaction |

`fg.batch(meta=None)` opens an `SDKBatchTx` for grouping multiple writes
into one transaction.

### 2.5 Assertions namespace (`fg.assertions.*`)

| Method | One-liner |
|---|---|
| `by_id(asrt_id)` | Return `AssertionRecord | None` for one assertion id |
| `by_ids(asrt_ids)` | Return `AssertionRecordSet` for an iterable of assertion ids; unknown ids are skipped |

This namespace is read-only and by-id only. It does not ship graph-wide
`active`, `history`, `where`, `at`, or `version` enumeration.

### 2.6 Eval namespace (`fg.eval.*`)

| Method | One-liner |
|---|---|
| `run(rule_or_query, *, row_format=None)` | Evaluate a `Rule` or `Query`; `RuleRef` remains a where-clause carrier, not a direct runtime selector |
| `evaluate(inference, *, engine='native', engine_options=None, semantics=None)` | Evaluate an `Inference`; returns list of `CandidateSet`. If `semantics` is `ProbLogSemantics`, `PyReasonSemantics`, or `SemanticsProfile`, `engine` may be omitted and is derived from the semantics object. |
| `accept(candidate, *, approved_by=None, note=None, dry_run=False, identity_override=None)` | Accept exactly one candidate; performs writes |
| `accept_many(candidates, *, ...)` | Accept multiple candidates idempotently |

`engine='native'` rejects non-empty `engine_options`. Adapter-owned engines
(`souffle`, `problog`, `pyreason`) consume `engine_options` at call time
and never propagate to `Inference` or ledger.

Pass `Rule` / `Inference` value objects directly to `run(...)` or
`evaluate(...)`. Registry-backed SavedRule/SavedInference persistence was
removed by Q8 Phase 2.

### 2.7 Rules namespace (`fg.rules.*`)

| Method | One-liner |
|---|---|
| `inspect(rule_or_inference)` | Inspect `Rule` / `Inference` branch ids, fallback ids, atom ids, and heads |

> Q8 Phase 2 (Slice 6) removed `fg.rules.save / load / list / get`. The
> namespace now exposes only `inspect(...)`. Construct `Rule(...)` values in
> memory and pass them to `fg.eval.run(...)`.

### 2.8 Inferences namespace (`fg.inferences.*`)

> Q8 Phase 2 (Slice 6) removed the `fg.inferences.save / load / list / get`
> persistence methods. The namespace is now empty (no methods) and remains
> frozen via `FrozenSnapshotError` on attribute set. Construct `Inference(...)`
> values in memory and pass them to `fg.eval.evaluate(...)`.

### 2.9 What-if namespace (`fg.what_if.*`)

For tutorial usage see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

| Method | One-liner |
|---|---|
| `check(inference, binding, *, engine='native', registry=None)` | Counterfactual evaluation; returns `CheckResult` |
| `diagnose(inference, binding, *, engine='native', registry=None)` | Trace why a fact was derived; returns `DiagnoseResult` |
| `why_not(inference, candidates, *, engine='native', registry=None)` | Explain why facts in an explicit candidate universe did not derive; returns `WhyNotUniverseResult` |

### 2.10 What-if fact overlay (`fg.what_if.fact_overlay.*`)

| Method | One-liner |
|---|---|
| `check(inference, binding, overlay, *, engine='native', registry=None)` | Re-check inference with fact-value overrides; returns `FactOverlayCheckResult` |
| `recheck_proof_frame(support_artifact, overlay)` | Re-evaluate a held `SupportArtifact` under a new overlay; returns `ProofFrameRecheckResult` |

`overlay` is a `factgraph.application.protocol.EvaluationOverlay`. The
`tuple[FactValueOverride, ...]` form is rejected at the SDK boundary.

### 2.11 What-if rule (`fg.what_if.rule.*`)

All three accept an SDK `Rule` (lowered internally; raw `RuleSpec` IR
is rejected) and a `SupportArtifact`. `overlay` may be `None` or empty;
the rule-action overlay is constructed internally.

| Method | One-liner |
|---|---|
| `disable(rule, support, *, branch_index, atom_index, overlay=None, note=None)` | Re-check with a literal disabled; returns `RuleDisableResult` |
| `literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)` | Re-check with a literal replaced; returns `RuleLiteralReplaceResult` |
| `add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None)` | Re-check with a condition appended (no `atom_index`); returns `RuleAddConditionResult` |

`literal_path` is a `factgraph.application.protocol.RuleLiteralPath`;
`added_atom` is a `factgraph.application.protocol.RuleAddedAtom`.

### 2.12 Audit namespace (`fg.audit.*`)

| Method | One-liner |
|---|---|
| `explain_fact(locator)` | Get proof explanation for a fact |
| `conflicts()` | Return active conflicting assertions |
| `diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)` | Compare two recorded rounds; returns `ProofFrameDiff` |

`diff_proof_frames` is pure (no store/registry/engine/IO). Load events
via `factgraph.audit.load_audit_package` or hold them from a recorder.
`include_unchanged` is a strict bool — `1` and `0` are rejected.

### 2.13 Package namespace (`fg.package.*`)

| Method | One-liner |
|---|---|
| `export_package(out_dir, options, **kwargs)` | Export Souffle-format package; `options` is a required `ExportOptions` instance |
| `run_package(package_dir, *, entrypoints, engine='souffle')` | Execute an exported package |

### 2.14 Views namespace (`fg.views.*`)

| Method | One-liner |
|---|---|
| `create(name, *, asrt_ids=[...])` | Create a frozen assertion view from assertion ids |
| `create(name, *, asrts=[...])` | Create a frozen assertion view from objects exposing `.asrt_id` |
| `update(name, *, asrt_ids=[...])` | Replace an existing view with frozen assertion-id membership |
| `update(name, *, asrts=[...])` | Replace an existing view from objects exposing `.asrt_id` |
| `delete(name)` | Delete a frozen assertion view |
| `get(name)` | Retrieve `FrozenAssertionView` |
| `list()` | Return `dict[str, FrozenAssertionView]` of all views |

`FrozenAssertionView` is a returned-object surface with
`asrt_ids: frozenset[str]`; it is not exported from `factgraph.sdk.__all__`.
`fg.views` has no built-in `default` entry; `"default"` is just another
user-defined frozen assertion view name when created explicitly. Frozen
assertion views are not accepted as snapshot input to `fg.read.find(...)`
or display-meta input to `fg.run(...)`; use
`fg.assertions.by_ids(fg.views.get(name).asrt_ids)` for record-level
readback.

Read-time confidence/display aggregation is not a public SDK surface.
`fg.read.find(...)`, `fg.eval.run(...)`, and `fg.eval.evaluate(...)` do
not accept frozen views or read policies as input.

### 2.15 Result-type non-export

`CheckResult`, `DiagnoseResult`, `WhyNotUniverseResult`,
`FactOverlayCheckResult`, `ProofFrameRecheckResult`, `RuleDisableResult`,
`RuleLiteralReplaceResult`, `RuleAddConditionResult`, and
`ProofFrameDiff` are returned by `fg.what_if.*` and `fg.audit.*` but
**are not in `factgraph.sdk.__all__`**. They are passthrough application
DTOs. Import them directly from `factgraph.application.protocol` or
`factgraph.audit` if your code needs to type-annotate them.

---

## 3. Registry Adapter Removal

`SDKRegistry` and `FileAuthoringRegistry` were removed by A20(E) / Q6-A.
SDK code should use `FactGraph.create(..., path=...)` for workspace
persistence, `Rule(...)` / `Inference(...)` as in-memory values, and
`python -m factgraph migrate-workspace <path>` for legacy workspaces that still
carry a filesystem `registry/` directory.

---

## 4. Facade Return Objects

### `EntitySnapshot`

Read-only view of an entity. Attributes:
- `ref` — encoded reference string
- `entity_type` — entity class name
- `identity_available` — whether the identity is usable for `.edit()`
- `identity` — dict of identity field values
- `assertions` — namespace exposing per-field assertion records

Method: `field(name)` returns a `FieldAssertions` for the given field.

Assigning to a snapshot attribute raises `FrozenSnapshotError`.

### `EntityEditor`

Transactional editor obtained from `fg.write.edit(...)`. Methods:
`preview()`, `commit(meta=...)`, `rollback()`. Attributes: `ref`,
`entity_type`. Operating on a committed/rolled-back editor raises
`EditorClosedError`.

### `FieldEditor`

Per-field editor on an `EntityEditor`: `set(value, *, meta=None)`,
`add(value, *, meta=None)`, `retract(*, asrt_id, meta=None)` (keyword-only).

### `FieldAssertions`, `AssertionRecordSet`, `AssertionRecord`, `AssertionMeta`

`FieldAssertions` exposes a field's active assertions plus history.
`.active()` returns currently non-revoked records as `AssertionRecordSet`;
`.all()` returns active plus revoked records. `FieldAssertions.at(iso8601_time)`
and `.version(v)` are active-only shortcuts for `.active().at(...)` and
`.active().version(...)`.

`AssertionRecordSet` is a tuple-compatible returned object with
`.where(...)`, `.at(...)`, `.version(...)`, `.by_id(...)`, `.one()`,
`.all()`, and `.first()` helpers. Non-terminal filters return
`AssertionRecordSet`, so chained selection remains available. It is not a
top-level `factgraph.sdk.__all__` export.

Each entry is an `AssertionRecord` with `asrt_id`, `value`, `is_active`,
context fields (`entity_type`, `field_name`, `pred_id`, `e_ref`), and
`meta: AssertionMeta`. Use `not record.is_active` for revoked/inactive
records.
`AssertionMeta` carries provenance fields (source, trace_id,
ingested_at, raw_kind, bound, approved_by, derived_rule_id,
candidate_id, ...). `raw_kind` / `bound` are mirrored in `meta_rows` for
exact assertion filtering; the canonical semantic copy lives in
`shared/semantic/raw_kind` and `shared/semantic/bound` annotation rows.

Example:

```python
target = (
    snapshot.field("name")
    .all().where(value="Alice", source="seed")
    .one()
)
same = snapshot.field("name").all().by_id(target.asrt_id).one()
sdk.retract(target.asrt_id)
```

---

## 5. Batch Objects

### `SDKBatchTx`

Returned by `fg.batch(meta=None)`. Methods: `entity(entity_cls,
**identity)`, `preview()`, `commit()`, `save()`. The context manager's
`__exit__` does **not** auto-commit or auto-rollback — call `commit()`
explicitly to persist. An unfinished tx writes nothing if `commit()`
is never called (there is no `rollback()` method on `SDKBatchTx`
itself; use `EntityEditor.rollback()` for editor-scoped rollback).

### `BatchPlan` / `WireBatchPlan`

`BatchPlan` (`ops`, `warnings`, `export(sdk)`, `to_json(sdk)`,
`apply(sdk)`) is the in-process batch plan. `WireBatchPlan`
(`to_dict()`, `to_json()`, `from_dict(...)`, `from_json(...)`,
`apply(sdk, strict_schema=True)`) is the serialization-friendly form
for cross-process / cross-language consumers.

### `ManagedFieldHandle`

Used inside batch context: `ManagedFieldHandle.retract(assertion_id, ...)`
(parameter name `assertion_id`; positional also supported).

---

## 6. Query / Inference Quick Reference

### 6.1 Query

- `fg.run(Query(...))` — defaults to `list[dict]`
- `row_format="instance"` returns `list[EntitySnapshot|None]` (only for
  single `Entity(var)` head)
- `on_missing` and `on_type_mismatch` accept `error | skip | null`
- Query head supports only schema `single` fields
- Invalid `row_format` or incompatible head raises
  `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`
- Calling `run(...)` with an `Inference` raises the same error

### 6.2 Inference

- `fg.evaluate(Inference(...), engine="native"|"souffle"|"problog"|"pyreason")`
  returns `list[CandidateSet]`
- Public SDK `evaluate(...)` does not accept `mode=`; use `engine=`.
- `head=[...]` is rejected in public SDK `Inference`; use one inference per head
- `CandidateSet.confidence` semantics depend on engine:
  - `native` / `souffle` → `None`
  - `problog` → probability `float`
  - `pyreason` → lower-bound `float`
- `engine_options`: call-time runtime config (e.g.
  `fg.evaluate(..., engine_options={"timesteps": 5})`); never enters
  `Inference` or ledger
- Public `Rule` / `Inference` objects do not carry adapter-specific
  `engine_ext` parameters. `SemanticsProfile.rule_projection` owns
  engine-specific rule projection.
- Track 2 exposes `factgraph.sdk.ProbLogSemantics` and
  `factgraph.sdk.PyReasonSemantics` as the preferred public SDK wrappers for
  engine-specific semantics. `factgraph.sdk.SemanticsProfile` remains exported
  as the advanced/canonical profile shape.
- Track 3-post extends `PyReasonSemantics` with
  `branch_bounds={branch_id: [lower, upper]}`. These bounds override the
  global `head_bound` for the referenced branch and may use explicit
  `Branch(id=...)` names or fallback `b0` / `b1` ids.
- `fg.eval.inspect_semantics(...)` accepts wrappers or `SemanticsProfile`;
  wrapper inspection includes a lowered canonical profile preview. Public
  SDK calls reject `mode=` and `semantics_profile=`; core/application
  internals keep using `Store.evaluate(..., mode=..., semantics_profile=...)`.
- Public `Rule.condition_weights` remains available as
  certainty/explain projection input. It is not an engine adapter
  parameter, and future runtime configuration for this lane belongs in
  `SemanticsProfile.certainty_projection`.
- Semantic annotations: PyReason produces `pyreason/semantic/*`,
  ProbLog produces `problog/semantic/probability`. Persist post-accept
  via `persist_pyreason_annotations()` or `persist_problog_annotations()`
- User-authored raw uncertainty uses paired
  `meta={"raw_kind": "probabilistic"|"possibilistic", "bound": [lower, upper]}`.
  `probability`, `bound_lower`, and `bound_upper` are not accepted as write
  meta keys.

### 6.3 Row format precedence

`row_format` resolves in order: call-site argument >
`default_row_format` constructor argument > `FACTPY_ROW_FORMAT`
environment variable > `"dict"` default.

`FACTPY_ROW_FORMAT` is read once at `SDKStore` initialization and
cached. `row_format="tuple"` still works but emits `DeprecationWarning`.

### 6.4 Accept

`accept(CandidateSet, ...)` accepts exactly one positional candidate.
Sugar keyword arguments: `approved_by`, `note`, `dry_run`,
`identity_override` (also via `meta_overrides`).

---

## 7. What's Not in the SDK

These are reachable via direct imports, not through `factgraph.sdk`:

| Capability | Importable from |
|---|---|
| Round events recorder lifecycle (`start_round`, `record_round_event`, `finalize_round`) | `factgraph.audit.round_events` |
| Frontier trace | `factgraph.core.rules.frontier` |
| Walker views (`ProofFrameDiffView`, etc.) | `factgraph.application.walker` |
| Raw cross-boundary DTOs (`EvaluationOverlay`, `RuleLiteralPath`, `RuleAddedAtom`, `RoundEvent`) | `factgraph.application.protocol`, `factgraph.audit` |
| Audit package loading | `factgraph.audit.load_audit_package` |
| Engine adapter registration | `factgraph.adapters.{souffle,problog,pyreason}` |
| Aggregate DSL helpers (`agg_count`, `agg_sum`, `agg_min`, `agg_max`, `agg_mean`) | `factgraph.sdk.dsl` |

See [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for
when and why to drop down to these surfaces.

---

*Internal change history is recorded in the source repository's
blueprint archive (not shipped with the release).*
