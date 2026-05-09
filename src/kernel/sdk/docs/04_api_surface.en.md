# SDK API Surface Reference

The exact public surface of `kernel.sdk`. For tutorials see
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
from kernel.sdk import FactGraph

fg = FactGraph.from_schema_classes([User])

# Namespaced (preferred for new code)
fg.read.get(User, user_id="u-1")
fg.write.add(User.tag, alice, "engineer")
fg.what_if.check(derivation, binding)
fg.what_if.fact_overlay.check(derivation, binding, overlay)
fg.what_if.rule.disable(rule, support, branch_index=0, atom_index=0)
fg.audit.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events)

# Flat (foundational; permanent)
fg.get(User, user_id="u-1")
fg.add(User.tag, alice, "engineer")
fg.check(derivation, binding)
fg.check_fact_overlay(derivation, binding, overlay)
fg.check_rule_disable(rule, support, branch_index=0, atom_index=0)
fg.diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events)
```

| Namespace | Methods |
|---|---|
| `schema` | `ingest`, `validate_provenance` |
| `read` | `get`, `find`, `ref` |
| `write` | `set`, `add`, `retract`, `edit` |
| `eval` | `run`, `evaluate`, `evaluate_compiled`, `accept`, `accept_compiled`, `accept_many` |
| `what_if` | `check`, `diagnose`, `why_not` |
| `what_if.fact_overlay` | `check`, `recheck_proof_frame` |
| `what_if.rule` | `disable`, `literal_replace`, `add_condition` |
| `audit` | `explain_fact`, `conflicts`, `diff_proof_frames` |
| `package` | `export_package`, `run_package` |
| `views` | `create`, `update`, `delete`, `get`, `list` |

Namespace accessors return private manager objects. The managers are
read-only — assigning attributes (`fg.what_if.foo = ...`) raises
`FrozenSnapshotError`. They are not part of `kernel.sdk.__all__` and
should not be imported directly.

---

## 1. Top-Level Exports

Everything below is importable as `from kernel.sdk import <name>`.

### 1.1 Schema, store, registry

| Symbol | Purpose |
|---|---|
| `Entity` | Base class for entity declarations |
| `Field` | Descriptor for a field with cardinality |
| `Identity` | Descriptor for an identity (primary-key) field |
| `Relationship` | Base class for relationship type declarations |
| `FactGraph` | Canonical entry point (alias of `SDKStore`) |
| `SDKStore` | Foundational entry point (same class as `FactGraph`) |
| `SDKRegistry` | Schema/rule/derivation registry |

`Entity` instances render via `__repr__` showing identity and field
values in declaration order; unset `Field` values render as `None`.

### 1.2 DSL

| Symbol | Purpose |
|---|---|
| `Body` | Rule body constructor (literal conjunction) |
| `Rule` | Declarative rule (head + body) |
| `RuleRef` | Reference to a registered rule by id |
| `Derivation` | Multi-rule derivation envelope |
| `Query` | Query over the current store |
| `Pred` | Predicate literal (fact reference) |
| `Not` | Negation operator for body literals |
| `vars` | Logic-variable factory for rule construction |
| `SDKDSLError` | Raised on DSL construction errors |

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
| `SDKRegistryError` | Registry/rule registration failures |
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
FactGraph.from_schema_classes(
    classes,
    *,
    ledger=None,
    ledger_path=None,
    artifact_store_root=None,
    default_row_format=None,
)
```

Class-validation errors raise `SDKSchemaError`; constructor-path errors
raise `SDKStoreError`. `artifact_store_root` enables sidecar-backed
explain artifact readback (ignored if a fully constructed `store=` is
supplied).

### 2.2 Schema namespace (`fg.schema.*`)

| Method | One-liner |
|---|---|
| `ingest(items, *, meta=None, allow_sensitive_meta=False)` | Bulk-insert assertions; `meta` merges into every item's meta. Returns `IngestResult` |
| `validate_provenance(obj, *, standard="derivation_v1")` | Inspect provenance shape without writing; returns `ValidationReport` |

### 2.3 Read namespace (`fg.read.*`)

| Method | One-liner |
|---|---|
| `get(entity_cls, **identity)` | Fetch single entity by identity or `None` |
| `find(entity_cls, *, view=None, limit=None, **filters)` | Filter entities; returns list of `EntitySnapshot` |
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

### 2.5 Eval namespace (`fg.eval.*`)

| Method | One-liner |
|---|---|
| `run(rule_or_query, *, view=None, row_format=None)` | Evaluate a `Rule`, `RuleRef`, or `Query`; not for `Derivation` |
| `evaluate(derivation, *, mode='native', engine_options=None)` | Evaluate a `Derivation`; returns list of `CandidateSet` |
| `evaluate_compiled(plans, *, mode='native', engine_options=None)` | Evaluate already-compiled derivation plans |
| `accept(candidate, *, approved_by=None, note=None, dry_run=False, identity_override=None)` | Accept exactly one candidate; performs writes |
| `accept_compiled(...)` | Accept against already-compiled plans |
| `accept_many(candidates, *, ...)` | Accept multiple candidates idempotently |

`mode='native'` rejects non-empty `engine_options`. Adapter-owned engines
(`souffle`, `problog`, `pyreason`) consume `engine_options` at call time
and never propagate to `Derivation` or ledger.

### 2.6 What-if namespace (`fg.what_if.*`)

For tutorial usage see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

| Method | One-liner |
|---|---|
| `check(derivation, binding, *, engine='native', registry=None)` | Counterfactual evaluation; returns `CheckResult` |
| `diagnose(derivation, binding, *, engine='native', registry=None)` | Trace why a fact was derived; returns `DiagnoseResult` |
| `why_not(derivation, candidates, *, engine='native', registry=None)` | Explain why facts in an explicit candidate universe did not derive; returns `WhyNotUniverseResult` |

### 2.7 What-if fact overlay (`fg.what_if.fact_overlay.*`)

| Method | One-liner |
|---|---|
| `check(derivation, binding, overlay, *, engine='native', registry=None)` | Re-check derivation with fact-value overrides; returns `FactOverlayCheckResult` |
| `recheck_proof_frame(support_artifact, overlay)` | Re-evaluate a held `SupportArtifact` under a new overlay; returns `ProofFrameRecheckResult` |

`overlay` is a `kernel.application.protocol.EvaluationOverlay`. The
`tuple[FactValueOverride, ...]` form is rejected at the SDK boundary.

### 2.8 What-if rule (`fg.what_if.rule.*`)

All three accept an SDK `Rule` (lowered internally; raw `RuleSpec` IR
is rejected) and a `SupportArtifact`. `overlay` may be `None` or empty;
the rule-action overlay is constructed internally.

| Method | One-liner |
|---|---|
| `disable(rule, support, *, branch_index, atom_index, overlay=None, note=None)` | Re-check with a literal disabled; returns `RuleDisableResult` |
| `literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)` | Re-check with a literal replaced; returns `RuleLiteralReplaceResult` |
| `add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None)` | Re-check with a condition appended (no `atom_index`); returns `RuleAddConditionResult` |

`literal_path` is a `kernel.application.protocol.RuleLiteralPath`;
`added_atom` is a `kernel.application.protocol.RuleAddedAtom`.

### 2.9 Audit namespace (`fg.audit.*`)

| Method | One-liner |
|---|---|
| `explain_fact(locator)` | Get proof explanation for a fact |
| `conflicts()` | Return active conflicting assertions |
| `diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)` | Compare two recorded rounds; returns `ProofFrameDiff` |

`diff_proof_frames` is pure (no store/registry/engine/IO). Load events
via `kernel.audit.load_audit_package` or hold them from a recorder.
`include_unchanged` is a strict bool — `1` and `0` are rejected.

### 2.10 Package namespace (`fg.package.*`)

| Method | One-liner |
|---|---|
| `export_package(out_dir, options, **kwargs)` | Export Souffle-format package; `options` is a required `ExportOptions` instance |
| `run_package(package_dir, *, entrypoints, engine='souffle')` | Execute an exported package |

### 2.11 Views namespace (`fg.views.*`)

| Method | One-liner |
|---|---|
| `create(name, view_spec)` | Create a named view |
| `update(name, view_spec)` | Update an existing view |
| `delete(name)` | Delete a view (not `"default"`) |
| `get(name)` | Retrieve a view spec |
| `list()` | Return `dict[str, ViewSpec]` of all views |

### 2.12 Result-type non-export

`CheckResult`, `DiagnoseResult`, `WhyNotUniverseResult`,
`FactOverlayCheckResult`, `ProofFrameRecheckResult`, `RuleDisableResult`,
`RuleLiteralReplaceResult`, `RuleAddConditionResult`, and
`ProofFrameDiff` are returned by `fg.what_if.*` and `fg.audit.*` but
**are not in `kernel.sdk.__all__`**. They are passthrough application
DTOs. Import them directly from `kernel.application.protocol` or
`kernel.audit` if your code needs to type-annotate them.

---

## 3. `SDKRegistry` Methods

| Method | Purpose |
|---|---|
| `apply_schema_classes(classes)` | Compile and register schema from classes |
| `apply_authoring_bundle(bundle)` | Apply a full authoring bundle |
| `read_manifest()` | Read the registry manifest |
| `upsert_schema_ir(schema_ir)` | Insert/update compiled schema IR |
| `register_rule_spec(spec)` | Register a low-level rule spec |
| `register_rule(rule)` | Register an SDK `Rule` |
| `register_derivation_spec(spec)` | Register a low-level derivation spec |
| `register_derivation(derivation)` | Register an SDK `Derivation` (single- or multi-head; multi-head heads serialize as `head: [...]`) |
| `get_schema_entry(...)` | Fetch a schema entry by id |
| `list_rule_ids()` / `list_derivation_ids()` | Enumerate registered ids |
| `list_rule_versions(id)` / `list_derivation_versions(id)` | Version history |
| `list_apply_run_ids()` / `list_apply_runs()` | Enumerate apply runs |
| `show_apply_run(run_id)` | Inspect a specific apply run |
| `get_latest_rule_spec(id)` / `get_latest_derivation_spec(id)` | Latest version lookup |
| `read_rule_spec(id, version)` / `read_derivation_spec(id, version)` | Specific version read |

`register_derivation` and `fg.eval.evaluate` both accept multi-head
Derivations. The single-head constraint applies only at the
**capability shell** layer — `fg.what_if.{check, diagnose, why_not}`
reject plans with `len(plan.heads) != 1`
(`kernel.application.capability_helpers.why_not.py:23` and siblings).
Registry storage and authoring payload serialization are head-agnostic.

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

### `FieldAssertions`, `AssertionRecord`, `AssertionMeta`

`FieldAssertions` exposes a field's active assertions plus history.
Supports time-slice access via `.at(iso8601_time)` and version slice via
`.version(v)`. Each entry is an `AssertionRecord` with `asrt_id`,
`value`, `is_active`, `is_revoked`, and `meta: AssertionMeta`.
`AssertionMeta` carries provenance fields (source, trace_id,
ingested_at, confidence, approved_by, derived_rule_id, candidate_id, ...).

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

## 6. Query / Derivation Quick Reference

### 6.1 Query

- `fg.run(Query(...))` — defaults to `list[dict]`
- `row_format="instance"` returns `list[EntitySnapshot|None]` (only for
  single `Entity(var)` head)
- `on_missing` and `on_type_mismatch` accept `error | skip | null`
- Query head supports only schema `single` fields
- Invalid `row_format` or incompatible head raises
  `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`
- Calling `run(...)` with a `Derivation` raises the same error

### 6.2 Derivation

- `fg.evaluate(Derivation(...), mode="native"|"souffle"|"problog"|"pyreason")`
  returns `list[CandidateSet]`
- Legacy `python` / `engine` keyword arguments raise explicit rename errors
- `head=[...]` is supported (flattened output)
- `CandidateSet.confidence` semantics depend on engine:
  - `native` / `souffle` → `None`
  - `problog` → probability `float`
  - `pyreason` → lower-bound `float`
- `engine_ext`: definition-time engine semantics carrier on
  `Rule.engine_ext` or `Derivation.engine_ext` (e.g.
  `PyReasonRuleExt(timestep_delay=1)`); must inherit `EngineExtBase`
- `engine_options`: call-time runtime config (e.g.
  `fg.evaluate(..., engine_options={"timesteps": 5})`); never enters
  `Derivation` or ledger
- Semantic annotations: PyReason produces `pyreason/semantic/*`,
  ProbLog produces `problog/semantic/probability`. Persist post-accept
  via `persist_pyreason_annotations()` or `persist_problog_annotations()`

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

These are reachable via direct imports, not through `kernel.sdk`:

| Capability | Importable from |
|---|---|
| Round events recorder lifecycle (`start_round`, `record_round_event`, `finalize_round`) | `kernel.audit.round_events` |
| Frontier trace | `kernel.core.rules.frontier` |
| Walker views (`ProofFrameDiffView`, etc.) | `kernel.application.walker` |
| Raw cross-boundary DTOs (`EvaluationOverlay`, `RuleLiteralPath`, `RuleAddedAtom`, `RoundEvent`) | `kernel.application.protocol`, `kernel.audit` |
| Audit package loading | `kernel.audit.load_audit_package` |
| Engine adapter registration | `kernel.adapters.{souffle,problog,pyreason}` |

See [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md) for
when and why to drop down to these surfaces.

---

*Internal change history is recorded in `docs/blueprints/archive/` (not
shipped with the release).*
