# Overview of the Application Module (`kernel`)

- Scope: `src/kernel/application`
- Last updated: 2026-05-07
- Target readers: developers who need to understand Python runtime authority, SDK adapter boundaries, and service/agent consumer constraints

## 1. Module Responsibilities

`application` is the canonical Python runtime authority above `core`. It owns runtime-normalized entity read/write, query, ingest, and compiled derivation evaluate/accept operations, expressed as SDK-independent protocol DTOs and executors.

It is responsible for:

- application protocol DTOs and error/warning DTO shapes
- schema runtime indexing, selector/ref resolution, and field/type lookup
- entity hydration / read requests
- entity write planning / apply
- query runtime request/result execution
- normalized ingest request/result execution
- compiled derivation evaluate / accept orchestration
- explicit-binding derivation Check (`passed` / `failed` / `unsupported` / `invalid_request`)
- explicit-binding derivation Diagnose (`passed` / `failed.no_candidate` / `failed.atom_localized` / `unsupported` / `invalid_request`)
- explicit-binding Fact Overlay Check (`before` / `after` / `diff` under temporary fact replace/remove overlays, native-only MVP)
- narrow ProofFrame Rechecker (`still_valid` / `invalidated` / `unknown` over one native `SupportArtifact` under fact replace/remove overlay, with deterministic single-frame narrative)
- native Rule Disable (`completed` / `unsupported` / `invalid_request`) over one temporary rule-condition disable action,returning variant rows plus original-frame ProofFrame output
- native Rule Literal Replace (`completed` / `unsupported` / `invalid_request`) over one temporary Const-to-Const native where literal replacement,returning variant rows plus original-frame ProofFrame output
- native Rule Add Condition (`completed` / `unsupported` / `invalid_request`) over one temporary filter-only native where atom insertion,returning variant rows plus original-frame ProofFrame output with a synthetic added-atom verdict
- explicit-universe Why-not Diagnose (`green` / `red` partition with row-level Diagnose summaries)
- capability ergonomics helpers for Fact Overlay replace/remove construction, `EvaluationOverlay` assembly, Why-not candidate-universe normalization, and Store-to-frontier `view_facts` projection
- application-layer walker views for SDK-independent traversal over selected DTO / IR structures (`IRBodyWalker`, `FrozenTupleView`, `AtomKeyView`, `SupportArtifactView`, `AssertionView`, `ProofFrameView`, and `ProofFrameDiffView` in the current slice)

It is not responsible for:

- the Python facade shape of `SDKStore` / `SDKBatchTx` / `EntitySnapshot` / `EntityEditor`
- SDK `Field` descriptors, metaclasses, DSL sugar, or `Query` / `Derivation` authoring objects
- HTTP routes, sessions, or registry delivery
- package export/run delivery surfaces
- the named view registry (`sdk.views`)

## 2. Module Structure

- `protocol/`
  - `common.py`: `ErrorDTO` / `WarningDTO` / JSON value validation
  - `schema_runtime.py`: `EntitySelector` / `EntityRef` / `FieldPath`
  - `entity_read.py`: read request/response, snapshot, field value/assertion DTOs
  - `entity_write.py`: write command/plan/result DTOs
  - `query.py`: `QueryRuntimeRequest` / `QueryRuntimeResponse` / return contract
  - `ingest.py`: normalized ingest item/request/result DTOs
  - `derivation.py`: compiled derivation evaluate/accept request DTOs
  - `derivation_check.py`: explicit-binding Check protocol DTOs (`CheckRequest` / `CheckResult` / `EvidenceEnvelope`)
  - `derivation_diagnose.py`: explicit-binding Diagnose protocol DTOs (`DiagnoseRequest` / `DiagnoseResult` / `DiagnoseAtomLocator`)
  - `derivation_fact_overlay.py`: Fact Overlay Check protocol DTOs and shared overlay actions (`FactOverlayCheckRequest` / `FactOverlayCheckResult` / `EvaluationOverlay` / `FactValueOverride` / `FactRemoveAction` / `RuleDisableAction` / `RuleLiteralReplaceAction` / `RuleAddConditionAction`)
  - `proofframe.py`: ProofFrame Rechecker protocol DTOs (`ProofFrameRecheckRequest` / `ProofFrameRecheckResult` / `ProofFrameAtomVerdict` / `ProofFrameStatus`)
  - `rule_disable.py`: Rule Disable protocol DTOs (`RuleDisableRequest` / `RuleDisableResult` / `RuleDisableStatus`)
  - `rule_literal_replace.py`: Rule Literal Replace protocol DTOs (`RuleLiteralReplaceRequest` / `RuleLiteralReplaceResult` / `RuleLiteralReplaceStatus`)
  - `rule_add_condition.py`: Rule Add Condition protocol DTOs (`RuleAddConditionRequest` / `RuleAddConditionResult` / `RuleAddConditionStatus`)
  - `derivation_why_not.py`: Why-not Universe Diagnose protocol DTOs (`WhyNotUniverseRequest` / `WhyNotUniverseResult` / `WhyNotRedRow` / `WhyNotRowDiagnostic` / `WhyNotAtomLocator`)
- `schema_runtime.py`
  - schema index, identity materialization, ref encoding, field/type lookup
- `capability_helpers.py`
  - application-layer ergonomic helpers: `build_fact_value_override(...)`, `build_fact_remove_action(...)`, `build_evaluation_overlay(...)`, `build_why_not_candidate_universe(...)`, `build_frontier_view_facts(...)`
- `walker/`
  - application-layer traversal views. Current implementation: `IRBodyWalker` / `IRAtomView` over `RuleSpec.where` and `CompiledDerivationPlan.body_ir`, `FrozenTupleView` / `frozen_collection(...)` for already-frozen tuple collections, `AtomKeyView` / `parse_atom_key(...)`, `SupportArtifactView` / `AssertionView` for `SupportArtifact` assertion cross-references, `ProofFrameView` for `ProofFrameRecheckResult`, and `ProofFrameDiffView` for `ProofFrameDiff`. B3 stream walkers are not implemented yet. See `walker/docs/README.md`.
- `entity_view.py`
  - `hydrate_entity(...)`, `hydrate_entities(...)`, `execute_read_request(...)`
- `entity_write.py`
  - `plan_write_command(...)`, `apply_write_plan(...)`
- `query_runtime.py`
  - `execute_query(...)`
- `ingest_runtime.py`
  - `apply_ingest_request(...)`
- `derivation_runtime.py`
  - `evaluate_derivation_plans(...)`, `accept_derivation_candidate_set(...)`, `accept_derivation_candidate_sets(...)`
- `derivation_check_runtime.py`
  - `check_derivation_binding(...)`: verifies a complete or partial binding against a single compiled derivation plan; native/souffle/problog/pyreason are handled through representability-gated final-result matching.
- `diagnose_runtime.py`
  - `diagnose_derivation_binding(...)`: diagnoses a complete or partial binding against a single compiled derivation plan; native can localize the failed atom, while souffle/problog/pyreason return coarse pass/fail/unsupported classifications through evidence-aware dispatch.
- `fact_overlay_runtime.py`
  - `check_fact_overlay_binding(...)`: checks a requested binding under temporary fact replace/remove overlays without writing the ledger; native runs baseline plus overlay-applied phases and returns before/after/diff summaries, while souffle/problog/pyreason return `ENGINE_OVERLAY_NOT_SUPPORTED`.
- `proofframe_runtime.py`
  - `recheck_proof_frame(...)`: rechecks one native `SupportArtifact` under an `EvaluationOverlay` without re-running derivation evaluation; returns per-atom verdicts and aggregate frame status. Non-native support artifacts and rule-ref frames return frame-level `unknown`; `not` steps are strictly deferred to `unknown`.
  - `render_proof_frame_narrative(...)`: deterministic English single-frame narrative formatter over a `ProofFrameRecheckResult`.
- `rule_disable_runtime.py`
  - `check_rule_disable_action(...)`: evaluates one native `RuleSpec` under exactly one temporary `RuleDisableAction`; returns normalized variant rows plus a `ProofFrameRecheckResult` for the original frame. RuleRef-bearing inputs are unsupported,variant support capture is deferred,and no ledger or registry mutation occurs.
- `rule_literal_replace_runtime.py`
  - `check_rule_literal_replace_action(...)`: evaluates one native `RuleSpec` under exactly one temporary `RuleLiteralReplaceAction`; supports existing Const leaves in predicate terms,comparison/filter sides,`in` members,and `addc` / `mulc` constants. RuleRef-bearing inputs are unsupported,variant support capture is deferred,and no ledger or registry mutation occurs.
- `rule_add_condition_runtime.py`
  - `check_rule_add_condition_action(...)`: evaluates one native `RuleSpec` under exactly one temporary `RuleAddConditionAction`; supports adding one filter-only atom over variables already bound in the selected branch. The runtime returns normalized variant rows plus an original-frame `ProofFrameRecheckResult` with a synthetic `b{branch}.add{action}:{kind}` atom verdict. RuleRef-bearing inputs,new-variable binding planner behavior,`not`,variant support capture,and multi-action ordering are deferred;no ledger or registry mutation occurs.
- `why_not_runtime.py`
  - `check_why_not_universe(...)`: assembles a red/green board for an explicit finite head-binding universe, then diagnoses each red row through `diagnose_derivation_binding(...)` while returning Why-not-owned row diagnostics.

## 3. Public Runtime Surface

`src/kernel/application/__init__.py` currently exports 57 public symbols. The main executor entry points are:

Batch 8 public-surface note:`kernel.application` is an **advanced importable** runtime authority in the kernel package. It is appropriate for automation,wire bridges,and callers that want SDK-independent DTOs. It is not the ergonomic SDK product facade,and Batch 8 does not add SDK shells or HTTP routes for the Batches 3-7 capability runtimes.

- `execute_read_request(...)`
- `hydrate_entity(...)`
- `hydrate_entities(...)`
- `plan_write_command(...)`
- `apply_write_plan(...)`
- `execute_query(...)`
- `apply_ingest_request(...)`
- `evaluate_derivation_plans(...)`
- `check_derivation_binding(...)`
- `diagnose_derivation_binding(...)`
- `check_fact_overlay_binding(...)`
- `check_rule_add_condition_action(...)`
- `check_rule_disable_action(...)`
- `check_rule_literal_replace_action(...)`
- `recheck_proof_frame(...)`
- `render_proof_frame_narrative(...)`
- `check_why_not_universe(...)`
- `accept_derivation_candidate_set(...)`
- `accept_derivation_candidate_sets(...)`

The main schema/runtime helpers are:

- `build_fact_value_override(...)`
- `build_fact_remove_action(...)`
- `build_evaluation_overlay(...)`
- `build_why_not_candidate_universe(...)`
- `build_frontier_view_facts(...)`
- `build_schema_index(...)`
- `resolve_selector(...)`
- `materialize_identity(...)`
- `encode_entity_ref(...)`
- `entity_info(...)`
- `field_predicate(...)`
- `field_value_type(...)`
- `entity_type_from_ref(...)`

The current walker entry points are:

- `AssertionView`
- `AtomKeyView`
- `FrozenTupleView`
- `IRBodyWalker`
- `IRAtomView`
- `ProofFrameDiffView`
- `ProofFrameView`
- `SupportArtifactView`
- `frozen_collection(...)`
- `parse_atom_key(...)`

## 4. Relationship with Other Layers

- `core`
  - owns low-level ledger/store/rule/evidence primitives.
  - application composes these primitives into stable Python runtime contracts.
- `sdk`
  - owns product surface, authoring DSL, Python ergonomics, facade objects, and compatibility aliases.
  - adapts SDK outward types into application DTOs and maps application results back to SDK outward types.
- `service` / `agent`
  - must not add production SDK runtime imports.
  - the current allowed production SDK import is the agent extraction authoring helper `compile_schema_from_classes`.
- `adapters` / `domains`
  - some out-of-scope SDK consumers remain, such as PyReason adapter DSL coupling and ECSS SDK helpers. These are tracked as future primitive-contract or domain-facade work.

## 5. SDK Adapter Status

Current SDK runtime delegation:

- `sdk.get(...)` / `sdk.find(...)` use application read/hydration DTOs.
- `SDKBatchTx.preview()` and `BatchPlan.apply()` delegate to application write planning/apply when staged operations can be represented by application protocol.
- `sdk.run(Query(...))` lowers SDK `Query` to application `QueryRuntimeRequest`, then maps application `EntitySnapshotDTO` rows back to SDK `EntitySnapshot` / dict / instance shapes.
- `sdk.ingest(...)` keeps SDK descriptor parsing and diagnostics, then delegates cache-resolvable normalized set/add/retract items to `apply_ingest_request(...)`; cache misses fall back to the legacy SDK write path.
- `sdk.evaluate(...)` / compiled derivation evaluate delegate compiled plans to `evaluate_derivation_plans(...)`.
- Check, Diagnose, Fact Overlay Check, ProofFrame Rechecker, Rule Disable, Rule Literal Replace, Why-not Universe Diagnose, and the capability ergonomics helpers are currently exposed at the application layer only. No SDK shell is added in the MVP; any future SDK entrypoint must remain a thin delegate to `check_derivation_binding(...)`, `diagnose_derivation_binding(...)`, `check_fact_overlay_binding(...)`, `recheck_proof_frame(...)`, `check_rule_disable_action(...)`, `check_rule_literal_replace_action(...)`, `check_why_not_universe(...)`, or the application helper functions.

SDK outward behavior remains the compatibility contract for end users; application is the runtime authority behind that facade.

## 5.5 Durable Round Persistence Boundary

Application capability runtimes return stable protocol DTOs, but they do not emit audit events internally. Batch 6 round persistence is owned by `kernel.audit.round_events` and is invoked by an external caller/recorder after a capability result exists.

Current persistable first-slice result surfaces are:

- Check
- Diagnose
- Fact Overlay Check
- Why-not Universe Diagnose
- ProofFrame Rechecker

Frontier projection and rule-action result events are deferred. This preserves the application boundary: no `kernel.application.*runtime` module imports `kernel.audit`, and no SDK/service/agent surface is introduced for round persistence.

## 6. Conservative Boundaries

- Application protocol does not accept SDK-only types.
- Query lowering and authoring validation remain SDK responsibilities.
- Ingest descriptor parsing, item precheck diagnostics, and user-facing `IngestResult` remain SDK responsibilities.
- Batch export/replay and wire plan compatibility remain SDK responsibilities.
- `sdk.set(...)` / `sdk.add(...)` / `sdk.retract(...)` remain low-level SDK convenience methods.
- Application write planning is single-target; multi-root atomic batch remains expressed by SDK batch staging.
- Full exception hierarchy migration is deferred. Query/ingest/derivation runtime paths use application DTO error shapes while SDK product-domain errors remain SDK-owned.

## 7. Test Entry Points

Core application and SDK adapter coverage is included in the kernel test segment:

```bash
python -m unittest discover -s src/kernel/tests -p 'test_*.py'
```

Key focused tests:

- `test_application_schema_runtime.py`
- `test_application_entity_view.py`
- `test_application_entity_write.py`
- `test_application_query_runtime.py`
- `test_application_ingest_runtime.py`
- `test_application_derivation_runtime.py`
- `test_application_check_protocol.py`
- `test_application_check_runtime.py`
- `test_application_diagnose_protocol.py`
- `test_application_diagnose_runtime_native.py`
- `test_application_diagnose_runtime_non_native.py`
- `test_application_diagnose_sibling_invariant.py`
- `test_application_capability_helpers.py`
- `test_application_fact_overlay_protocol.py`
- `test_application_fact_overlay_runtime_native.py`
- `test_application_fact_overlay_sibling_invariant.py`
- `test_application_proofframe_protocol.py`
- `test_application_proofframe_runtime_native.py`
- `test_application_proofframe_narrative.py`
- `test_walker_errors.py`
- `test_walker_ir.py`
- `test_walker_views_frozen_tuple.py`
- `test_walker_keys.py`
- `test_walker_views_support.py`
- `test_walker_views_proof_frame.py`
- `test_walker_views_proof_frame_diff.py`
- `test_application_rule_disable_protocol.py`
- `test_application_rule_disable_runtime_native.py`
- `test_application_rule_literal_replace_protocol.py`
- `test_application_rule_literal_replace_runtime_native.py`
- `test_application_why_not_protocol.py`
- `test_application_why_not_runtime.py`
- `test_application_why_not_sibling_invariant.py`
- `test_sdk_facade_application_delegate.py`
- `test_sdk_batch_application_delegate.py`
- `test_sdk_query_policies.py`
- `test_sdk_ingest_application_delegate.py`
- `test_sdk_consumer_boundary.py`

## 8. Related Documents

- [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
- [src/kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/sdk/docs/README.md)
