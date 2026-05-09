# SDK API Surface Index (Current Implementation)

This page tracks the public exports in `kernel/sdk/__init__.py` and the main class APIs. The SDK API surface is the Python product surface; runtime execution for query / ingest / compiled derivation paths is delegated to `kernel.application`, while SDK preserves outward adapters and compatibility shapes.

After the Batch 8 public-surface decision, the SDK surface remains narrow: the exports and existing `SDKStore` facade methods listed here are the v0.1 product public API. L Direction G1 added `SDKStore.check(...)` / `SDKStore.diagnose(...)` as narrow SDK shells for Check / Diagnose; G4 added `SDKStore.why_not(...)` as the narrow SDK shell for Why-not Universe Diagnose; G2 added `SDKStore.check_fact_overlay(...)` and `SDKStore.recheck_proof_frame(...)` as narrow SDK shells for Fact Overlay Check and ProofFrame Recheck; G3 added `SDKStore.check_rule_disable(...)` / `SDKStore.check_rule_literal_replace(...)` / `SDKStore.check_rule_add_condition(...)` as the three narrow rule-overlay SDK shells; G5 added `SDKStore.diff_proof_frames(...)` as the narrow SDK shell for ProofFrame Diff query side, and explicitly deferred Round events recorder lifecycle to advanced importable. None of the nine L methods extend `kernel.sdk.__all__` or re-export application or audit DTOs. G2 Phase 0 hygiene migrated the five then-extant shell modules into the `kernel/sdk/shells/` subpackage (with `#P1` carve-out retrofit of the G1 + G4 invariant tests); G3 Phases 1/2/3 added the three rule-overlay shell files under that subpackage and applied `#P1` retrofits to the three application-runtime boundary tests (`test_no_sdk_rule_{disable,literal_replace,add_condition}_surface`); G5 Phase 1 added `proof_frame_diff.py` under the subpackage (9 modules total post-G5), with no `#P1` retrofit needed (audit-layer tests never asserted "no SDK surface"). Rule-action runtimes are reachable through the G3 SDK shells; ProofFrame diff is reachable through the G5 SDK shell; Round events recorder lifecycle (`start_round` / `record_round_event` / `finalize_round`) and Frontier trace remain on the `kernel.audit.round_events` / `kernel.core.rules.frontier` advanced importable surfaces. Frontier was explicitly kept out of the SDK facade in G4 §5.4 (evaluator drift gate + application no-opt-in tests stay in force); Round events recorder was explicitly deferred in G5 §5.1 (stateful, raises, persistence-adjacent; existing UX already imports `from kernel.audit.round_events import ...` directly). Promoting any other family to an ergonomic SDK API requires a separate outward request/result shape and must not directly re-export application or audit DTOs.

L Direction cross-boundary DTO layer rule (locked at G5 §5.3 / §6, extending G2 §5.1+§5.2 + G3 §5.2): **raw cross-boundary DTOs at the SDK boundary must be "frozen canonical DTOs above `kernel.core` using `kernel.application.protocol` vocabulary"**. Concretely:

- **In scope** — `kernel.application.protocol` frozen DTOs (e.g., `EvaluationOverlay`, `SupportArtifact`, `RuleLiteralPath`, `RuleAddedAtom`) and `kernel.audit` frozen DTOs (e.g., `RoundEvent`, `ProofFrameDiff`, `FrameDelta`, `AtomDelta`, `FrameIdentity`, `FrameStatusChange`, `EventReference`, `WarningDTO`).
- **Out of scope** — `kernel.core.*` substrate IR (e.g., `kernel.core.rules.rule_ir.RuleSpec`). The SDK explicitly rejects raw `RuleSpec` and accepts SDK `Rule` objects instead, lowered internally via `_compile_rule_input(...)`.

This rule is encoded verbatim in §6 invariants and applies to any future SDK shell over audit-layer or application-protocol DTOs.

## 0. Post-L SDK teaching taxonomy (FactGraph)

The post-L SDK ergonomics redesign organizes 30 user-facing flat methods into 8 top-level taxonomy namespaces + 2 sub-namespaces (under `what_if`). `FactGraph` is the literal alias of `SDKStore`, serving as the canonical v0.1 SDK top-level entrypoint name; the flat `SDKStore.<method>` form remains supported as **foundational API** — neither deprecated nor scheduled for removal.

New code is encouraged to use the taxonomy form:

```python
from kernel.sdk import FactGraph

fg = FactGraph.from_schema_classes([User])

# Taxonomy form (preferred for new code)
fg.read.get(User, user_id="u-1")
fg.write.add(User.tag, alice, "engineer")
fg.what_if.check(rule, binding)
fg.what_if.fact_overlay.check(support, overlay)
fg.what_if.rule.disable(rule, support_artifact, ...)
fg.audit.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)

# Flat form (foundational API; permanently supported)
fg.get(User, user_id="u-1")
fg.add(User.tag, alice, "engineer")
fg.check(rule, binding)
fg.check_fact_overlay(support, overlay)
fg.check_rule_disable(rule, support_artifact, ...)
fg.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)
```

The 8 top-level namespaces:

| Namespace | Methods |
|---|---|
| `schema` | `ingest`, `validate_provenance` |
| `read` | `get`, `find`, `ref` |
| `write` | `set`, `add`, `retract`, `edit` |
| `eval` | `run`, `evaluate`, `evaluate_compiled`, `accept`, `accept_compiled`, `accept_many` |
| `what_if` (G1+G4 direct) | `check`, `diagnose`, `why_not` |
| `what_if.fact_overlay` (G2) | `check` (was `check_fact_overlay`), `recheck_proof_frame` |
| `what_if.rule` (G3) | `disable`, `literal_replace`, `add_condition` (prefix dropped at sub-namespace level) |
| `audit` | `explain_fact`, `conflicts`, `diff_proof_frames` (G5; placed here per §5.2.1 because it consumes recorded round events) |
| `package` | `export_package`, `run_package` |
| `views` (existing) | `create`, `update`, `delete`, `get`, `list` |

Manager classes (`_SDKSchemaManager`, etc.) are private and do not enter `kernel.sdk.__all__`; they are reachable only through `FactGraph.<namespace>` property accessors. Writes such as `fg.what_if.foo = ...` raise `FrozenSnapshotError`. See [post-L SDK ergonomics redesign blueprint](../../../../docs/blueprints/active/2026-05-09_post-l-sdk-ergonomics-redesign.md) §5.2 / §5.4 / §5.7.

## 1. Top-Level Exports (`from kernel.sdk import ...`)

### 1.1 Schema / Store / Registry

- `Entity`
- `Field`
- `Identity`
- `FactGraph` *(post-L; canonical taxonomy entrypoint; literal alias of `SDKStore`)*
- `SDKStore` *(foundational; permanently supported)*
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
- `check_rule_disable(...)`
- `check_rule_literal_replace(...)`
- `check_rule_add_condition(...)`
- `diff_proof_frames(...)`
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
- `check_rule_disable(rule, support, *, branch_index, atom_index, overlay=None, note=None)` accepts an SDK `Rule` (lowered internally via `_compile_rule_input` to a `RuleSpec`), a raw `SupportArtifact`, and an optional `EvaluationOverlay` (only `None` or an empty overlay is accepted; the rule-action overlay is constructed internally by the A helper). It returns the raw application `RuleDisableResult` DTO; the result type is not added to `kernel.sdk.__all__`. The SDK rejects raw `RuleSpec` (substrate IR layer mismatch per §5.2 lock) and SDK `Derivation`. The runtime represents unsupported support / rule_ref-bearing support / target-not-found / rule-id mismatch / native-eval failures as `RuleDisableResult(status="invalid_request"|"unsupported")` and the SDK passes that through. All non-SDK exceptions (`SDKStoreError` / `RuleCompileError` / `ValueError` from lowering, `RuleCompileError` from registry, `CapabilityHelperError` / `ProtocolShapeError` from the A helper, unexpected runtime) remap to `SDKStoreError(..., path="$.check_rule_disable[.rule|.support|.overlay|.dependencies|.request|]") from exc`.
- `check_rule_literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)` mirrors `check_rule_disable` but additionally accepts a raw `RuleLiteralPath` (`kernel.application.protocol.RuleLiteralPath`, a frozen application DTO covered by the G2 §5.1+§5.2 cross-cutting precedent) along with `old_literal` / `new_literal: Any`, and returns `RuleLiteralReplaceResult`. A non-`RuleLiteralPath` `literal_path` slips past SDK pre-validation (no shared validator exists for it) and is caught by the A helper / action DTO `__post_init__` as `ProtocolShapeError`, which remaps to `$.check_rule_literal_replace.request`. Other non-SDK exception remap paths follow the same shape as `check_rule_disable`.
- `check_rule_add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None)` mirrors `check_rule_disable` but **has no `atom_index` argument** (Add Condition appends a new atom at the end of the branch rather than pointing at an existing locator) and accepts a raw `RuleAddedAtom` (`kernel.application.protocol.RuleAddedAtom`, a frozen application DTO), returning `RuleAddConditionResult`. A non-`RuleAddedAtom` `added_atom` slips past SDK pre-validation and is caught by the A helper / action DTO `__post_init__` as `ProtocolShapeError`, which remaps to `$.check_rule_add_condition.request`. Other non-SDK exception remap paths follow the same shape as `check_rule_disable`.
- `diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)` accepts two non-empty round-id strings + two raw `tuple[RoundEvent, ...]` (`kernel.audit.round_events.RoundEvent`, frozen audit DTOs covered by the G5 §5.3 cross-boundary layer rule) + an optional `tuple[WarningDTO, ...]`, and returns the application-canonical `ProofFrameDiff` raw DTO (`kernel.audit.proof_frame_diff.ProofFrameDiff`); the result type is not added to `kernel.sdk.__all__`. The SDK shell is pure (no Store / no registry / no engine arg / no IO), mirroring `kernel.audit.proof_frame_diff.build_proof_frame_diff(...)` 1:1; users load events via `kernel.audit.load_audit_package` or hold them from a fresh recorder. **Round events recorder lifecycle (`start_round` / `record_round_event` / `finalize_round`) is explicitly deferred to `kernel.audit.round_events` advanced importable** (G5 §5.1 lock — recorder is mutable / stateful / persistence-adjacent; existing UX already imports `from kernel.audit.round_events import ...` directly). All non-SDK exceptions remap to `SDKStoreError(..., path="$.diff_proof_frames[.round_a_id|.round_b_id|.round_a_events|.round_b_events|.warnings|.include_unchanged|.request|]") from exc` (**8-path**: 6 inline pre-validation input paths + `ProofFrameDiffError` to `.request` + defensive `Exception` to base; `.include_unchanged` is a strict `isinstance(.., bool)` check, so `1` / `0` are also rejected — matching the established `return_display_meta` SDK precedent). Walker view `kernel.application.walker.ProofFrameDiffView` remains a Tier 2 advanced-importable opt-in; the SDK shell does not auto-wrap.
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
