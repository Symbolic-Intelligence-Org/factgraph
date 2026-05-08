# SDK API Surface Index (Current Implementation)

This page tracks the public exports in `kernel/sdk/__init__.py` and the main class APIs. The SDK API surface is the Python product surface; runtime execution for query / ingest / compiled derivation paths is delegated to `kernel.application`, while SDK preserves outward adapters and compatibility shapes.

After the Batch 8 public-surface decision, the SDK surface remains narrow: the exports and existing `SDKStore` facade methods listed here are the v0.1 product public API. L Direction G1 added `SDKStore.check(...)` / `SDKStore.diagnose(...)` as narrow SDK shells for Check / Diagnose; G4 added `SDKStore.why_not(...)` as the narrow SDK shell for Why-not Universe Diagnose; G2 added `SDKStore.check_fact_overlay(...)` and `SDKStore.recheck_proof_frame(...)` as narrow SDK shells for Fact Overlay Check and ProofFrame Recheck. None of the five L methods extend `kernel.sdk.__all__` or re-export application DTOs. G2 Phase 0 hygiene migrated the five shell modules into the `kernel/sdk/shells/` subpackage (with `#P1` carve-out retrofit of the G1 + G4 invariant tests). Rule-action runtimes, round events, ProofFrame diff, and Frontier trace remain on the `kernel.application` / `kernel.audit` / `kernel.core.rules.frontier` advanced importable surfaces. Frontier was explicitly kept out of the SDK facade in G4 §5.4; the evaluator drift gate and the application no-opt-in tests stay in force. Promoting any other family to an ergonomic SDK API requires a separate outward request/result shape and must not directly re-export application DTOs.

## 1. Top-Level Exports (`from kernel.sdk import ...`)

### 1.1 Schema / Store / Registry

- `Entity`
- `Field`
- `Identity`
- `SDKStore`
- `SDKRegistry`

Additional note:
- Plain `Entity` instances implement a debugging-friendly `__repr__()` that lists declared identity and field values in declaration order; unset `Field` values render as `None`.

### 1.2 DSL

- `Body`
- `Rule`
- `RuleRef`
- `Derivation`
- `Query`
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### 1.3 Schema compile helpers

- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### 1.4 Ingest / Provenance

- `IngestResult`
- `ValidationReport`

### 1.5 Errors and error codes

- Error classes: `SDKSchemaError`, `SDKStoreError`, `SDKRegistryError`, `EntityNotFoundError`, `FrozenSnapshotError`, `CardinalityError`, `EditorClosedError`
- Exported codes:
  - `INVALID_ROW_FORMAT`
  - `QUERY_MISSING_REF`
  - `QUERY_TYPE_MISMATCH`
  - `QUERY_ALIAS_CONFLICT`
  - `QUERY_UNBOUND_VAR`
  - `QUERY_INVALID_ROW_FORMAT`
  - `QUERY_NOT_IMPLEMENTED`

## 2. `SDKStore` Public Methods

- `from_schema_classes(..., ledger=None, ledger_path=None, artifact_store_root=None, default_row_format=None)`
- `batch(...)`
- `get(...)`
- `find(...)`
- `edit(...)`
- `ingest(...)`
- `validate_provenance(...)`
- `check(...)`
- `diagnose(...)`
- `why_not(...)`
- `check_fact_overlay(...)`
- `recheck_proof_frame(...)`
- `ref(...)`
- `set(...)`
- `add(...)`
- `retract(...)`
- `run(...)`
- `evaluate(...)`
- `evaluate_compiled(...)`
- `accept(...)`
- `accept_many(...)`
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

Key boundaries:
- `SDKStore` is the user entry point and facade aggregator, not the canonical runtime authority. Runtime-normalized query / ingest / compiled derivation orchestration now delegates to `kernel.application`.
- `from_schema_classes(...)` / `schema_preflight_from_classes(...)` class-validation failures raise `SDKSchemaError` (`SDKStore(...)` constructor-path checks raise `SDKStoreError`).
- `SDKStore.__init__(..., artifact_store_root=None)` and `from_schema_classes(..., artifact_store_root=None)` both support sidecar-backed explain artifact readback; if a fully constructed `store=...` is already supplied, the constructor-level `artifact_store_root` is ignored.
- `run(...)` supports Rule/Query and rejects Derivation.
- `run(rule, view=...)` supports named/inline views; Query path rejects `view` and `return_display_meta`.
- `evaluate(...)` explicitly rejects `view` and `temporal_view`.
- `evaluate(..., engine_options={...})` supports engine run-time configuration; it is call-time only and does not enter `Derivation` or authoring payloads.
- `evaluate(mode="native", engine_options={...})` fails explicitly; engine_options key validation and defaults remain adapter-owned.
- `check(Derivation(...), binding, *, engine="native", registry=None)` and `diagnose(...)` accept only SDK `Derivation` and `$`-prefixed binding `Mapping`; they return raw application `CheckResult` / `DiagnoseResult` DTOs that are not added to `kernel.sdk.__all__`.
- `why_not(Derivation(...), candidates, *, engine="native", registry=None)` accepts an SDK `Derivation` and an explicit finite candidate universe (`Sequence[Mapping[str, Any] | Sequence[Any]]`, mirroring `kernel.application.capability_helpers.build_why_not_candidate_universe(...)`). It returns the raw application `WhyNotUniverseResult` DTO; the result type is not added to `kernel.sdk.__all__`. Why-not rejects `CompiledDerivationPlan` at the SDK boundary and never auto-discovers the universe from the store. All non-SDK exceptions (`ValueError` / `RuleCompileError` / `CapabilityHelperError` / `ProtocolShapeError` / `WhyNotRuntimeError`) remap to `SDKStoreError(..., path="$.why_not[.derivation|.dependencies|.candidates|.request|]") from exc`.
- `check_fact_overlay(Derivation(...), binding, overlay, *, engine="native", registry=None)` accepts an SDK `Derivation`, a `$`-prefixed binding `Mapping`, and a raw `EvaluationOverlay` protocol DTO. It returns the raw application `FactOverlayCheckResult` DTO; the result type is not added to `kernel.sdk.__all__`. `EvaluationOverlay` is author-time intent (G1 §5.7's rejection of `CompiledDerivationPlan` does not apply because the overlay is not an already-lowered plan); the SDK explicitly rejects the `tuple[FactValueOverride, ...]` form even though the application `FactOverlayCheckRequest.overlay` field would otherwise tolerate it. The runtime represents unsupported overlay / `rule_actions` / inner phase failures as `FactOverlayCheckResult(status="invalid_request")` and the SDK passes that through; only truly unexpected runtime exceptions reach the base-path remap. All non-SDK exceptions (`ValueError` / `RuleCompileError` / `ProtocolShapeError` / other unexpected) remap to `SDKStoreError(..., path="$.check_fact_overlay[.derivation|.binding|.overlay|.dependencies|.request|]") from exc`.
- `recheck_proof_frame(support_artifact, overlay)` accepts a raw `SupportArtifact` (obtained from a prior `sdk.check(...)`'s `result.evidence_envelope.engine_payload`) and a raw `EvaluationOverlay`. It returns the raw application `ProofFrameRecheckResult` DTO; the result type is not added to `kernel.sdk.__all__`. There is no derivation lowering, registry resolution, or engine argument. The SDK never wraps `SupportArtifact`, never extracts it from a `CheckResult` argument, and never calls `sdk.check(...)` internally. All non-SDK exceptions (validation / `ProtocolShapeError` / unexpected runtime) remap to `SDKStoreError(..., path="$.recheck_proof_frame[.support_artifact|.overlay|.request|]") from exc`.
- Rule `row_format` precedence: call-site > `default_row_format` > `FACTPY_ROW_FORMAT` > `"dict"`.
- `FACTPY_ROW_FORMAT` is read once at `SDKStore` initialization and cached.
- `row_format="tuple"` still works but emits `DeprecationWarning`.
- Query defaults to `list[dict]`; it also supports `row_format="instance"` (only for single `Entity(var)` head).
- Invalid Query `row_format`, incompatible head shape for `instance`, or calling `run(...)` with Derivation raises `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.
- `accept(CandidateSet, ...)` accepts exactly one positional candidate; supported sugar keys are `approved_by`/`note`/`dry_run`/`identity_override` (also via `meta_overrides`).

## 3. `SDKRegistry` Public Methods

- `apply_schema_classes(...)`
- `apply_authoring_bundle(...)`
- `read_manifest(...)`
- `upsert_schema_ir(...)`
- `register_rule_spec(...)`
- `register_rule(...)`
- `register_derivation_spec(...)`
- `register_derivation(...)`
- `get_schema_entry(...)`
- `list_rule_ids(...)`
- `list_derivation_ids(...)`
- `list_rule_versions(...)`
- `list_derivation_versions(...)`
- `list_apply_run_ids(...)`
- `list_apply_runs(...)`
- `show_apply_run(...)`
- `get_latest_rule_spec(...)`
- `get_latest_derivation_spec(...)`
- `read_rule_spec(...)`
- `read_derivation_spec(...)`

Notes:
- `register_derivation(...)` is currently single-head-oriented.
- For multi-head publishing, expand into multiple single-head derivations first.

## 4. Common Facade Return Objects

- `EntitySnapshot`
  - attributes: `ref`, `entity_type`, `identity_available`, `identity`, `assertions`
  - method: `field(name)`
- `EntityEditor`
  - `preview()`, `commit(meta=...)`, `rollback()`
  - attributes: `ref`, `entity_type`
- `FieldEditor`
  - `set(...)`, `add(...)`, `retract(*, asrt_id=..., meta=...)` (keyword-only)

## 5. Batch Objects

- `SDKBatchTx`
  - `entity(...)`, `preview(...)`, `commit(...)`, `save(...)`
  - context manager `__exit__` does not auto-commit or auto-rollback
- `BatchPlan`
  - `ops`, `warnings`, `export(sdk)`, `to_json(sdk)`, `apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`, `to_json()`, `from_dict(...)`, `from_json(...)`, `apply(sdk, strict_schema=True)`

Additional note:
- Batch managed-handle retract method is `ManagedFieldHandle.retract(assertion_id, ...)` (parameter name is `assertion_id`; positional arg is also supported).

## 6. Query / Derivation Runtime Quick View

### 6.1 Query

- `sdk.run(Query(...)) -> list[dict]` (default) or `list[EntitySnapshot|None]` (`row_format="instance"` with single `Entity(var)` head)
- SDK retains `Query` DSL lowering and outward row formatting; application `execute_query(...)` executes the runtime-normalized request.
- `on_missing` / `on_type_mismatch`: `error|skip|null`
- Query field head supports only schema `single` fields

### 6.2 Derivation

- `sdk.evaluate(Derivation(...), mode="native|souffle|problog|pyreason") -> list[CandidateSet]`
- SDK retains `Derivation` DSL lowering, mode sugar, and compatibility checks; application `evaluate_derivation_plans(...)` executes compiled plan orchestration.
- Passing legacy `python|engine` raises explicit rename errors
- `head` shape determines candidate kind
- `head=[...]` is supported in evaluate (flattened output)
- `CandidateSet.confidence`: probability `float` for `problog`, lower bound `float` for `pyreason`, `None` for `native/souffle`
- `sdk.accept(...)` / `sdk.accept_many(...)` handle writes and idempotency
- `engine_ext`: shared definition-time engine semantics carrier on `Rule.engine_ext` or `Derivation.engine_ext` (for example `PyReasonRuleExt(timestep_delay=1)`); must inherit `EngineExtBase`
- `engine_options`: `sdk.evaluate(..., engine_options={"timesteps": 5})` passes runtime config; call-time only, never enters Derivation or Ledger
- `mode="native"` rejects non-empty `engine_options`
- Semantic annotations: PyReason results generate `pyreason/semantic/*`, ProbLog generates `problog/semantic/probability`; post-accept, call `persist_pyreason_annotations()` or `persist_problog_annotations()` to persist
