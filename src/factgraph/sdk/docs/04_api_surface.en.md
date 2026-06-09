# SDK API Surface Reference

The exact public surface of `factgraph.sdk`. For tutorials see
[`00_user_guide.en.md`](00_user_guide.en.md).

---

## 0. Namespace Map

`FactGraph` is the canonical entry point. It is a literal alias of
`SDKStore` — both names refer to the same class object and accept the
same calls.

`FactGraph` exposes operations through focused namespaces. T5 keeps the public
evaluation/evidence path under `fg.eval`.

```python
from factgraph.sdk import FactGraph

fg = FactGraph.create(schema_classes=[User])

# Canonical namespaces
alice = fg.entities.ref(User, user_id="u-1")
fg.fields.add(User.tag, alice, "engineer")
fg.entities.get(User, user_id="u-1")
result = fg.eval.evaluate(inference)
row = result.first()
explanation = row.explain() if row is not None else None
fg.audit.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events)
```

| Namespace | Methods |
|---|---|
| `entities` | `get`, `where`, `match`, `ref`, `create`, `delete`, `exists`, `edit` |
| `fields` | `set`, `add`, `retract`, `delete`, `get` |
| `assertions` | `by_id`, `by_ids`, `where`, `retract`, `active`, `all` |
| `schema` | `register`, `extend`, `apply`, `ingest`, `validate_provenance` |
| `eval` | `evaluate`, `explain`, `preview_config` |
| `audit` | `explain`, `conflicts`, `diff_proof_frames` |
| `package` | `export_package`, `run_package` |
| `views` | `create`, `update`, `delete`, `get`, `list` |

Namespace accessors return private manager objects. The managers are
read-only — assigning attributes to namespace managers raises
`FrozenSnapshotError`. They are not part of `factgraph.sdk.__all__` and
should not be imported directly.

---

## 1. Top-Level Exports

Everything below is importable as `from factgraph.sdk import <name>`.
The export list currently has 59 names.

### 1.1 Schema and store

| Symbol | Purpose |
|---|---|
| `Entity` | Base class for entity declarations |
| `Field` | Descriptor for mutable field content; cardinality is inferred from the Python annotation |
| `Identity` | Descriptor for an immutable identity coordinate field |
| `Relationship` | Base class for relationship type declarations |
| `FactGraph` | Canonical entry point (alias of `SDKStore`) |
| `SDKStore` | Foundational entry point (same class as `FactGraph`) |

`Entity` instances render via `__repr__` showing identity and field
values in declaration order; unset `Field` values render as `None`.

`FactGraph.create(schema_classes=[...])` is the canonical constructor.
`FactGraph.load_workspace(path, schema_classes=[...])` restores a saved workspace.
`FactGraph.from_schema_classes([...])` remains available as the lower-level
class-first constructor name and does not accept workspace `path=`.

#### Form I schema descriptors

Entity schemas use Form I descriptors:

```python
from typing import Literal
from factgraph.sdk import Entity, Field, Identity


class User(Entity):
    tenant_id: str = Identity(description="tenant")
    user_id: str = Identity(pattern=r"^u-[0-9]+$")
    display_name: str = Field()
    status: Literal["active", "inactive"] = Field()
    tags: list[Literal["staff", "admin"]] = Field()
```

`Identity()` has no `primary_key`, `default`, or `default_factory` keyword.
Every Identity field is part of the immutable entity coordinate and must be
provided explicitly when constructing a ref. `Field()` has no `cardinality`
keyword. Cardinality is inferred from the annotation: scalar `T` is single,
`list[T]`, `tuple[T, ...]`, `set[T]`, and `frozenset[T]` are multi.
Both descriptors accept `repr=` explain-layer templates; S1 validates those
templates but keeps them out of compiled Schema IR.

`Literal[...]` annotations become schema enum constraints. `pattern=` is a
regular-expression constraint available on both `Identity` and `Field`, but
only for string-valued declarations. Compile-time validation rejects invalid
regex syntax, non-string pattern targets, mixed-type `Literal[...]`, float
literal enums, `Optional` / general `Union`, and `dict[...]` annotations.

At write time, enum and pattern constraints are enforced by the application
write path before ledger append. Invalid values raise `SDKValueError`.

Migration examples:

```python
# Old
user_id: str = Identity(primary_key=True)
locale: str = Identity(default="en")
tags: str = Field(cardinality="multi")

# New
user_id: str = Identity()
locale: str = Identity()
tags: list[str] = Field()
```

`_DataMember` is the internal shared base for `Identity` and `Field`. It is not
exported from `factgraph.sdk`.

### 1.2 DSL

| Symbol | Purpose |
|---|---|
| `Case` | Rule `where` branch constructor (alternative conjunction) |
| `Rule` | Application protocol Rule |
| `ApplicationRule` | Transitional alias for `Rule` |
| `RuleRef` | Where-clause reference to an exposed rule |
| `Inference` | Multi-rule inference envelope |
| `SchemaAddResult` | Result returned by `fg.schema.register(...)`, `extend(...)`, or `apply(...)`; fields are `old_digest`, `new_digest`, `added_entities`, `added_fields` |
| `Query` | Query over the current store |
| `Pred` | Predicate literal (fact reference) |
| `Not` | Negation operator for body literals |
| `vars` | Logic-variable factory for rule construction |
| `build_application_rule` | Build an application `Rule` from SDK DSL conditions |
| `DSLToApplicationRuleError` | Raised when SDK DSL conditions cannot lower to a `Rule` |
| `SDKDSLError` | Raised on DSL construction errors |
| `RuleExpr` | Base RuleExpr authoring surface; use `RuleExpr.all(...)` / `RuleExpr.any(...)` or application `Rule` `&` / `|` composition |
| `RuleExprError` (← `SDKDSLError`) | Raised when RuleExpr authoring input violates the expression contract |
| `RuleJoinConstraint` | Immutable RuleExpr join constraint produced by `occurrence.port.eq(other_port)` / `occurrence.port_name.eq(other.port_name)`; initial joins use explicit `.eq(...)`, not Python `==` |
| `RuleExprInspect` | Immutable object returned by `fg.rules.inspect(application_rule_or_rule_expr)`; exposes `ast`, `occurrences`, `joins`, `unjoined_same_name_ports`, `render()`, and `render_compact()` |
| `OccurrenceInspect` | Immutable occurrence descriptor used by `RuleExprInspect.occurrences`; exposes alias, template id, port names, and atom descriptors |
| `ConditionDescriptor` | Immutable authoring-time atom descriptor used by `OccurrenceInspect.atoms`; exposes structured fields plus a display `summary` |
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
| `IngestResult` | Result of `fg.schema.ingest(...)`: counts, ids, validation report |
| `ValidationReport` | Per-row provenance/shape validation outcome |

### 1.5 Errors and error codes

| Class | Triggered by |
|---|---|
| `SDKSchemaError` | Schema compilation, descriptor binding, preflight |
| `SDKStoreError` | Store operations (write, view, batch, query, eval shells) |
| `SDKValueError` (← `SDKStoreError`) | Enum or pattern value validation during application-layer writes |
| `EntityNotFoundError` (← `SDKStoreError`) | `fg.entities.get(...)` / `fg.entities.edit(...)` on missing identity |
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
| `INV_7C_IDENTITY_PROTECTED` | Identity field write or Identity Claim retract attempt (per ADR-IC §4.1 / INV-7c); see §7 |
| `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` | `<EntityType>:exists` Claim independent retract attempt (per ADR-IC §4.4 transitional guard); see §7 |
| `UNRESOLVABLE_E_REF` | `e_ref` string was not produced by `fg.entities.ref(...)` (shadow store fail-fast per ADR-IC §4.2.1); see §7 |

---

## 2. `FactGraph` / `SDKStore` Methods

Methods are listed once per logical operation. Operations are grouped under
namespace managers (`fg.entities.*`, `fg.fields.*`, `fg.assertions.*`,
`fg.schema.*`, ...). The legacy flat top-level shortcuts and `fg.read.*` /
`fg.write.*` managers were removed in Slice 3a.

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
FactGraph.load_workspace(path, *, schema_classes=[...], default_row_format=None)
fg.save_workspace(path=None)
```

`fg.save_workspace()` writes the bound workspace. `fg.save_workspace(path)` writes and rebinds the
graph to that workspace. An unbound graph raises
`SDKStoreError("workspace path not bound; pass fg.save_workspace(path=...) or create with FactGraph.create(path=...)")`.
`FactGraph.load_workspace(...)` requires Python schema classes and validates the workspace
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
| `register(EntityCls)` | Register a new entity type; rejects an existing entity type with `SchemaConflictError` |
| `extend(EntityCls)` | Add non-identity fields to an existing entity declaration; rejects non-additive schema changes with `SchemaNonAdditiveError` |
| `apply(EntityCls)` | Safe-diff helper: routes to `register` for new entity types and `extend` for existing entity types |
| `ingest(items, *, meta=None, allow_sensitive_meta=False)` | Bulk-insert assertions; `meta` merges into every item's meta. Returns `IngestResult` |
| `validate_provenance(obj, *, standard="derivation_v1")` | Inspect provenance shape without writing; returns `ValidationReport` |

`fg.schema.add(...)` was removed. Use `register`, `extend`, or `apply`.
Schema extension is additive-only. It validates that every existing entity,
identity field, ordinary field predicate, and generated `<EntityType>:exists`
predicate remains compatible before mutating any schema state. ADR-IC §4.3.6
is enforced here: Identity↔Field swaps, adding Identity fields, removing
fields, changing field type/cardinality, and changing the generated `:exists`
predicate are rejected with zero side effects.

On success, the in-memory schema, compiled SchemaIndex, class registry,
descriptor maps, ledger schema digest, and Database schema object are updated
as one schema transaction. If the graph is bound to a workspace, the manifest is
not rewritten until a later explicit `fg.save_workspace(...)`.

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

### 2.3 Entities namespace (`fg.entities.*`)

| Method | One-liner |
|---|---|
| `get(entity_cls, **identity)` | Fetch single entity by identity or `None` |
| `where(entity_cls, *, limit=None, _meta=None, **filters)` | Filter entities by identity/field values |
| `match(entity_cls, template, *, limit=None, **port_constraints)` | Return distinct snapshots selected by a `Rule` or AND-only `RuleExpr` |
| `ref(entity_cls, **identity)` | Encode an entity reference string |
| `create(entity_cls, *, meta=None, **identity)` | Eagerly materialize the complete Identity Claim bundle; returns e_ref |
| `delete(e_ref, *, meta=None)` / `delete(entity_cls, *, meta=None, **identity)` | Revoke the whole entity bundle and visible field claims |
| `exists(entity_cls, **identity)` | Return whether the complete active Identity Claim bundle is visible |
| `edit(entity_cls, **identity)` | Open an `EntityEditor` for an existing entity |

### 2.4 Fields namespace (`fg.fields.*`)

| Method | One-liner |
|---|---|
| `set(field, ref, value, *, meta=None)` | Set a single-cardinality field |
| `add(field, ref, value, *, meta=None)` | Append to a multi-cardinality field |
| `retract(field, ref, value, *, meta=None)` | Retract the unique active field assertion matching `(field, ref, value)` |
| `delete(field, ref, *, meta=None)` | Retract all active assertions for `(field, ref)`; fail-fast on the first error |
| `get(field, ref)` | Materialize the current field value for one entity ref |

`fg.batch(meta=None)` opens an `SDKBatchTx` for grouping multiple writes
into one transaction.

Writes enforce Form I value constraints before ledger append. `Literal[...]`
enum misses and `pattern=` mismatches raise `SDKValueError` through `fg.fields.set`,
`fg.fields.add`, batch commits, wire batch apply, and
`EntityEditor` field operations. Direct internal ledger/protocol paths are
trusted internal paths and do not run this SDK-layer validation.

### 2.5 Assertions namespace (`fg.assertions.*`)

| Method | One-liner |
|---|---|
| `by_id(asrt_id)` | Return `AssertionRecord | None` for one assertion id |
| `by_ids(asrt_ids)` | Return `AssertionRecordSet` for an iterable of assertion ids; unknown ids are skipped |
| `field(Field)` | Return `AssertionView` for one schema field; exposes `active_records` and `history_records` |
| `where(*, field=None, e_ref=None, value=None, value_tag=None, _meta=None)` | Filter active assertions by canonical Layer 3 criteria |
| `retract(asrt_id, *, meta=None)` | Retract a specific assertion id; Identity Claims and legacy `:exists` Claims are protected |
| `active` / `all` | Active or all assertion records |

`fg.assertions.retract(...)` is the only public assertion-id mutation entry.
Identity Claim retracts raise `INV_7C_IDENTITY_PROTECTED`; legacy
`<EntityType>:exists` retracts raise `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`.

### 2.6 Eval namespace (`fg.eval.*`)

| Method | One-liner |
|---|---|
| `evaluate(inference_or_expr, *, head=None, engine=None, config=None)` | Evaluate an `Inference`, `Rule`, or `RuleExpr`; returns `EvaluateResult`. `engine=None` resolves to `"native"`; explicit values must be one of `"native"`, `"souffle"`, `"problog"`, `"pyreason"`. |
| `explain(expr, *, head, engine=None, config=None)` | Replay a closed-head explanation; `head=` is required (no default). `engine=` resolves the same way as `evaluate`. Returns `Explanation`. |
| `preview_config(profile)` | Inspect public semantics wrappers or canonical `SemanticsProfile`. |

Public `evaluate(...)` rejects **seven** deprecated/blocked kwargs through two
distinct mechanisms:

- **Presence-rejected (5 kwargs)** — raises even when the value is `None`:
  `view=`, `policy=`, `semantics_profile=`, `mode=`, `temporal_view=`.
- **Non-None-rejected (2 kwargs)** — popped with a `None` default; raises
  only on a non-None value: `registry=`, `engine_options=`.

The mechanism distinction matters when threading kwargs through wrappers: a
wrapper that passes `view=None` to `evaluate(...)` will still raise, while
`registry=None` is silently dropped.

Pass `Rule` / `Inference` value objects directly to `run(...)` or
`evaluate(...)`. Registry-backed SavedRule/SavedInference persistence was
removed by Q8 Phase 2.

### 2.7 Rules namespace (`fg.rules.*`)

| Method | One-liner |
|---|---|
| `inspect(rule_or_inference)` | Inspect `Rule` / `Inference` branch ids, fallback ids, atom ids, and heads |

> Q8 Phase 2 (Slice 6) removed `fg.rules.save / load / list / get`. The
> namespace now exposes only `inspect(...)`. Construct `Rule(...)` values in
> memory and pass them to `fg.eval.evaluate(...)`.

### 2.8 Inferences namespace (`fg.inferences.*`)

> Q8 Phase 2 (Slice 6) removed the `fg.inferences.save / load / list / get`
> persistence methods. The namespace is now empty (no methods) and remains
> frozen via `FrozenSnapshotError` on attribute set. Construct `Inference(...)`
> values in memory and pass them to `fg.eval.evaluate(...)`.

### 2.9 Removed legacy evidence shells

Direct `check`, `diagnose`, `why_not`, `what_if.*`, `accept`, and
`accept_many` candidate workflows are not part of the T5 public SDK evidence
path. Use `fg.eval.evaluate(...)`, `row.explain()`, `row.close()`, and
`fg.eval.explain(...)`.

### 2.12 Audit namespace (`fg.audit.*`)

| Method | One-liner |
|---|---|
| `explain(asrt_id_or_record)` | Get proof explanation for a fact |
| `conflicts(target)` | Diagnose conflicts for an assertion record or entity field cell (see target shapes below) |
| `diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)` | Compare two recorded rounds; returns `ProofFrameDiff` |

`fg.audit.conflicts(target)` accepts four target shapes:

1. assertion id string (e.g. `"asrt:..."`);
2. object exposing `.asrt_id` (e.g. `AssertionRecord` or any record returned by
   `fg.assertions.*`);
3. `(entity, Field)` tuple, where `entity` is an `e_ref` string or any object
   with a `.ref` attribute (e.g. an `EntitySnapshot`);
4. `(entity, field_name: str)` tuple, with the same `entity` shape as (3).

`fg.audit.explain(target)` accepts only shapes 1 and 2 — the `(entity, field)`
tuple branch is specific to `conflicts` because it resolves to a cell, not a
specific assertion. Passing shapes 3 or 4 to `explain(...)` raises
`SDKStoreError`.

`diff_proof_frames` is pure (no store/registry/engine/IO). Load events
via `factgraph.audit.load_audit_package` or hold them from a recorder.
`include_unchanged` is a strict bool — `1` and `0` are rejected.

### 2.13 Package namespace (`fg.package.*`)

| Method | One-liner |
|---|---|
| `export_package(out_dir, options, **kwargs)` | Export Souffle-format package; `options` is a required `ExportOptions` instance |
| `run_package(package_dir, *, entrypoints, engine='souffle')` | Execute an exported package |

### 2.14 Views namespace (`fg.assertion_views.*`)

| Method | One-liner |
|---|---|
| `create(name, *, asrt_ids=[...])` | Create a frozen assertion view from assertion ids |
| `create(name, *, asrts=[...])` | Create a frozen assertion view from objects exposing `.asrt_id` |
| `update(name, *, asrt_ids=[...])` | Replace an existing view with frozen assertion-id membership |
| `update(name, *, asrts=[...])` | Replace an existing view from objects exposing `.asrt_id` |
| `delete(name)` | Delete a frozen assertion view |
| `get(name)` | Retrieve `FrozenAssertionSet` |
| `list()` | Return `dict[str, FrozenAssertionSet]` of all views |

`FrozenAssertionSet` is a returned-object surface with
`asrt_ids: frozenset[str]`; it is not exported from `factgraph.sdk.__all__`.
`fg.assertion_views` has no built-in `default` entry; `"default"` is just another
user-defined frozen assertion view name when created explicitly. Frozen
assertion views are not accepted as snapshot input to `fg.entities.where(...)`
or evaluation input to `fg.eval.evaluate(...)`; use
`fg.assertions.by_ids(fg.assertion_views.get(name).asrt_ids)` for record-level
readback.

Read-time confidence/display aggregation is not a public SDK surface.
`fg.entities.where(...)` and `fg.eval.evaluate(...)` do
not accept frozen views or read policies as input.

### 2.15 Result-type non-export

`EvaluateResult`, `EvaluateRow`, `ResultFingerprint`, and `Explanation`
are exported from `factgraph.sdk`. Legacy check/diagnose/why-not DTOs are not
SDK public result types. `Explanation.repr` is a computed property; no
additional SDK export is required for the protocol-layer evidence walker.

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
- `assertions` — `AssertionView` exposing entity-scoped assertion records

Method: `field(name)` returns a field-scoped `AssertionView`.

Assigning to a snapshot attribute raises `FrozenSnapshotError`.

### `EntityEditor`

Transactional editor obtained from `fg.entities.edit(...)`. Methods:
`preview()`, `commit(meta=...)`, `rollback()`. Attributes: `ref`,
`entity_type`. Operating on a committed/rolled-back editor raises
`EditorClosedError`.

### `FieldEditor`

Per-field editor on an `EntityEditor`: `set(value, *, meta=None)`,
`add(value, *, meta=None)`, `retract(*, asrt_id, meta=None)` (keyword-only).

### `AssertionView`, `AssertionRecordSet`, `AssertionRecord`, `AssertionMeta`

`AssertionView` is the unified read-only assertion view type. `snapshot.assertions`
is entity-scoped; `snapshot.field("name")` and
`snapshot.assertions.field("name")` are field-scoped. `FieldAssertions` and
`AssertionNamespace` were removed.

`.active` returns currently non-revoked records as `AssertionRecordSet`;
`.all` returns active plus revoked records. `.history` is a deprecated alias of
`.all`; it emits no warning by default and emits `DeprecationWarning` only when
`FACTGRAPH_WARN_DEPRECATED=1` is set. Legacy call forms such as `.active()` and
`.all()` remain accepted because `AssertionRecordSet` is callable and returns
itself.

`AssertionRecordSet` is a tuple-compatible returned object with
`.where(value=..., value_tag=..., _meta={...})`, `.at(...)`, `.by_id(...)`, `.one()`,
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
    .all.where(value="Alice", _meta={"source": "seed"})
    .one()
)
same = snapshot.field("name").history.by_id(target.asrt_id).one()
fg.assertions.retract(target.asrt_id)
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

- Public `fg.run(Query(...))` was removed by the T5 hard-cut.
- Use `fg.entities.where(...)` for simple snapshot reads and `fg.entities.match(...)`
  for application-rule snapshot reads.
- `on_missing` and `on_type_mismatch` accept `error | skip | null`
- Query head supports only schema `single` fields
- Legacy Query construction remains available for internal/future-track code,
  but it is not a public runtime entrypoint.

### 6.2 Inference

- `fg.evaluate(Inference(...), engine="native"|"souffle"|"problog"|"pyreason")`
  returns `EvaluateResult`
- Public SDK `evaluate(...)` does not accept `mode=`; use `engine=`.
- `head=[...]` is rejected in public SDK `Inference`; use one inference per head
- `EvaluateRow.raw_kind` and `EvaluateRow.bound` carry public quantitative
  results when an adapter produces them.
- `engine_options=` is rejected; use public `config=` wrappers.
- Public `Rule` / `Inference` objects do not carry adapter-specific
  `engine_ext` parameters. `SemanticsProfile.rule_projection` owns
  engine-specific rule projection.
- Track 2 exposes `factgraph.sdk.ProbLogConfig` and
  `factgraph.sdk.PyReasonConfig` as the preferred public SDK wrappers for
  engine-specific semantics. `factgraph.sdk.SemanticsProfile` remains exported
  as the advanced/canonical profile shape.
- Track 3-post extends `PyReasonConfig` with
  `case_bounds={branch_id: [lower, upper]}`. These bounds override the
  global `head_bound` for the referenced branch and may use explicit
  `Case(id=...)` names or fallback `c0` / `c1` ids.
- `fg.eval.preview_config(...)` accepts wrappers or `SemanticsProfile`;
  wrapper inspection includes a lowered canonical profile preview. Public
  SDK calls reject `mode=` and `semantics_profile=`; core/application
  internals keep using `Store.evaluate(..., mode=..., semantics_profile=...)`.
- Public `Rule.condition_weights` remains available as
  certainty/explain projection input. It is not an engine adapter
  parameter, and future runtime configuration for this lane belongs in
  `SemanticsProfile.certainty_projection`.
- Semantic annotations: PyReason and ProbLog may produce adapter-native
  evidence; T5 public SDK code consumes it through `EvaluateRow` and
  `Explanation`.
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

### 6.4 Candidate accept removal

`accept(CandidateSet, ...)` and `accept_many(...)` are removed from the public
SDK path. Evaluation is read-only; explicit writes go through `fg.fields.*`,
`fg.assertions.retract(...)`, `fg.entities.edit(...)`, or `fg.batch(...)`.

---

## 7. Identity Claim Emission and Reject Semantics

Per ADR-IC (Identity-as-Claim, adopted 2026-05-29 @ `2d0866ed`) and Slice 2
implementation (landed 2026-05-30 on
`v0.2.0-blueprint-slice-2-identity-claim-emission-2026-05-29`).

### 7.1 Identity Claim emission contract

Per ADR-IC §4.2: Identity Claim emission is owned by the **application
layer** (`factgraph.application.entity_write._materialization_ops`), not the
SDK shell. The SDK shell routes `fg.fields.set` / `fg.fields.add` / `EntityEditor.commit()`
/ `SDKBatchTx.commit()` through `plan_write_command`, which delegates
materialization to `_materialization_ops` when the target entity is not yet
visible.

**Emission input contract** (per ADR-IC §4.2.1) — emission only accepts an
`EntityRef` that **carries the complete identity bundle**. The SDK shell
shadow store (see §7.4) is a compatibility detail that lets
`fg.fields.set(Field, e_ref_string, value)` succeed by recovering the bundle
from a prior `fg.entities.ref(...)` call.

**What gets emitted on the first Field write to a freshly `fg.entities.ref`-ed
entity** (atomic, single `_write_session`):

| Claim | Count | Pred ID example (class `User`) |
|---|---|---|
| Identity Claim | N (one per `Identity` field) | `user:user_id`, `user:tenant_id`, ... |
| Field Claim | 1 (the triggering write) | `user:name` |

Pred ID convention (Slice 1 shipped):

- Identity / Field predicates → `<snake_owner_prefix>:<field_name>` (e.g.
  class `EmissionUser`'s Identity field `user_id` → `emission_user:user_id`)
- `:exists` predicates → `<EntityType>:exists` (Capitalized, e.g.
  `EmissionUser:exists`)

**Dedup**: subsequent Field writes on the **same** `e_ref` do NOT
re-emit Identity Claims. Dedup happens at two levels — within a
single `plan_write_command` call via `_materialization_ops`'s
`materialized_refs` set, and across calls via the `entity_visible` check
that gates materialization.

**User-facing materialization paths** (all atomic):

| Path | Materialization trigger |
|---|---|
| `fg.entities.create(EntityCls, **identity)` | Eagerly emits the complete Identity Claim bundle; no Field write required |
| `fg.fields.set(Field, e_ref, value)` / `fg.fields.add(Field, e_ref, value)` | Lazy compatibility path: materializes the Identity Claim bundle on first Field write when target not visible and the shadow store can recover identity values |
| `tx = fg.batch(); h = tx.entity(...); h.field.set(...); tx.commit()` | Materializes the Identity Claim bundle through the batch user-path planner |
| `editor = fg.entities.edit(...); editor.field.set(...); editor.commit()` | **NOT a materialization path** — `fg.entities.edit` pre-validates entity visibility (raises `EntityNotFoundError` if entity not materialized) |

`fg.entities.delete(...)` is the only public path that can revoke an entity's
Identity Claims as part of whole-entity deletion. Legacy `:exists` Claims,
when present, are handled by the same path-bound whole-entity delete path;
new user-facing materialization paths no longer emit them.

### 7.2 INV-7c Identity reject behavior

Per ADR-IC §4.1: Identity Claims are immutable anchors (`INV-7c`). The
following paths all raise with `code="INV_7C_IDENTITY_PROTECTED"`:

| Path | Layer | Behavior | Raise type |
|---|---|---|---|
| `editor.<identity_field>.set(value)` | Layer 2 (SDK shell) | Reject — `IdentityEditor.set/add/retract` is a write guard | `SDKStoreError` |
| `editor.<identity_field>.add(value)` / `.retract(value)` | Layer 2 (SDK shell) | Reject (delegate to `.set` wording) | `SDKStoreError` |
| `plan_write_command` with `FieldMutation` targeting an Identity field | Layer 2 (application source-of-truth) | Reject via `is_identity_field` check | `EntityWriteError` → `SDKStoreError` |
| `fg.assertions.retract(asrt_id)` where `asrt_id` is an Identity Claim | Layer 3 (SDK shell + application retract guard) | Reject via `check_retract_allowed` (Identity classification) | `SDKStoreError` |
| Application ingest path retract op on Identity Claim asrt | Layer 3 (application ingest) | Reject — code propagated directly (not wrapped as `INGEST_RETRACT_FAILED`) | `ErrorDTO(code=INV_7C_IDENTITY_PROTECTED)` |
| Application `_apply_op` retract branch on Identity Claim asrt | Layer 3 (application entity_write) | Reject — code propagated directly (not wrapped as `ENTITY_WRITE_FAILED`) | `EntityWriteError(code=INV_7C_IDENTITY_PROTECTED)` |

The `code="INV_7C_IDENTITY_PROTECTED"` is shared across all paths — single
source of truth for caller branching.

**Error message anatomy** (per ADR-IC §4.1 adopted wording):

- Cites `INV-7c` (the protected anchor invariant)
- Cites `INV-7a` (the underlying Identity immutable anchor)
- References `fg.entities.delete` + `fg.entities.create` as the future
  migration path
- References `ADR-IC §4.1` as the authoritative source

The protocol/core direct paths (`core/evidence/write_protocol.py` /
`core/store/ledger.py` / `core/derivation/accept.py:401` internal rollback)
are **intentionally unguarded** per the Q-PR1 carve-out — Slice 2 enforces
INV-7c only at the application source-of-truth and SDK shell layers
(defense-in-depth).

### 7.3 `<EntityType>:exists` legacy/transitional guard

Per ADR-IC §4.4 and Q-EXISTS §4.5: legacy `:exists` Claims are protected
by an **existence-claim transitional guard**, **NOT** by `INV-7c`. The two
guard lifecycles are explicitly decoupled:

- INV-7c is the permanent Identity anchor invariant.
- New user-facing materialization paths no longer emit `:exists` Claims.
- Legacy `:exists` Claims may still exist in older ledgers, wire/protocol
  compatibility paths, and out-of-scope derivation paths, and remain protected
  under the current guard code name.

Independent retract attempts on a legacy `<EntityType>:exists` Claim asrt raise
with `code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD"`. The error message
references `ADR-IC §4.4` and explicitly does **not** mention `INV-7c`
(per ADR-IC §4.4.2 naming).

`Entity:exists` in rule bodies remains virtual/internal syntax. Q-PR1
derivation accept may still produce derived-path `:exists` markers until a
future Q-PR1-authorized slice changes that surface. User-facing
`fg.entities.exists(...)` uses complete active Identity Claim bundle
visibility instead of reading `:exists` Claims.

### 7.4 Shadow store legacy positioning

`SDKStore._identity_values_by_e_ref` is a **legacy / internal compatibility
detail**, NOT part of the Layer 2 fields API contract (per ADR-IC §4.2.3).
It exists so that `fg.fields.set(Field, e_ref_string, value)` can succeed when
the shadow store has previously seen that `e_ref` via a prior
`fg.entities.ref(...)` call.

| Input | Behavior |
|---|---|
| `e_ref` **NOT** in shadow store (externally-constructed) | Fail-fast `SDKStoreError(code="UNRESOLVABLE_E_REF")` at `_apply_field_mutation` target check + at `_build_application_write_value` entity_ref value check |
| `e_ref` in shadow store, target not yet visible | Lazy materialization through `_materialization_ops` — emits the Identity bundle atomically with the Field write |
| `e_ref` in shadow store, target already visible | Field write only, no re-emission (dedup) |

**Carry-forward direction** (per ADR-IC §4.2.4 and Q-EXISTS §4.7):
shadow-store removal remains separate from `:exists` user-path cleanup.
This slice retires new user-path `:exists` co-emission but does not remove
`SDKStore._identity_values_by_e_ref`.

---

## 8. What's Not in the SDK

These are reachable via direct imports, not through `factgraph.sdk`:

| Capability | Importable from |
|---|---|
| Round events recorder lifecycle (`start_round`, `record_round_event`, `finalize_round`) | `factgraph.audit.round_events` |
| Frontier trace | `factgraph.core.rules.frontier` |
| Walker views (`ProofFrameDiffView`, etc.) | `factgraph.application.walker` |
| Raw cross-boundary DTOs (`FactOverlay`, `ConditionPath`, `AddedCondition`, `RoundEvent`) | `factgraph.application.protocol`, `factgraph.audit` |
| Audit package loading | `factgraph.audit.load_audit_package` |
| Engine adapter registration | `factgraph.adapters.{souffle,problog,pyreason}` |
| Aggregate DSL helpers (`agg_count`, `agg_sum`, `agg_min`, `agg_max`, `agg_mean`) | `factgraph.sdk.dsl` |

See [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for
when and why to drop down to these surfaces.

---

*Internal change history is recorded in the source repository's
blueprint archive (not shipped with the release).*
