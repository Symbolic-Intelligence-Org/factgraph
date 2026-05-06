# Application 模块总览(kernel)

- 范围:`src/kernel/application`
- 最后更新:2026-05-06
- 目标读者:需要理解 Python runtime authority、SDK adapter 边界与 service/agent consumer 约束的开发者

## 1. 模块职责

`application` 是 `core` 之上的 canonical Python runtime authority。它承接实体读写、query、ingest、compiled derivation evaluate/accept 这类 runtime-normalized 操作，并把它们表达成 SDK-independent protocol DTO 与 executor。

它负责:

- application protocol DTO 与 error/warning DTO shape
- schema runtime index、selector/ref 解析、field type 查询
- entity hydration / read request
- entity write planning / apply
- query runtime request/result execution
- normalized ingest request/result execution
- compiled derivation evaluate / accept orchestration
- explicit-binding derivation Check (`passed` / `failed` / `unsupported` / `invalid_request`)
- explicit-binding derivation Diagnose (`passed` / `failed.no_candidate` / `failed.atom_localized` / `unsupported` / `invalid_request`)
- explicit-binding Fact Overlay Check (`before` / `after` / `diff` under temporary fact replace/remove overlays, native-only MVP)
- narrow ProofFrame Rechecker (`still_valid` / `invalidated` / `unknown` over one native `SupportArtifact` under fact replace/remove overlay, with deterministic single-frame narrative)
- native Rule Disable (`completed` / `unsupported` / `invalid_request`) over one temporary rule-condition disable action,returning variant rows plus original-frame ProofFrame output
- explicit-universe Why-not Diagnose (`green` / `red` partition with row-level Diagnose summaries)
- capability ergonomics helpers for Fact Overlay replace/remove construction, `EvaluationOverlay` assembly, Why-not candidate-universe normalization, and Store-to-frontier `view_facts` projection

它不负责:

- `SDKStore` / `SDKBatchTx` / `EntitySnapshot` / `EntityEditor` 的 Python facade 外观
- SDK `Field` descriptor、metaclass、DSL sugar、`Query` / `Derivation` authoring object
- HTTP routes、session、registry delivery
- package export/run delivery surface
- named view registry(`sdk.views`)

## 2. 模块结构

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
  - `derivation_fact_overlay.py`: Fact Overlay Check protocol DTOs and shared overlay actions (`FactOverlayCheckRequest` / `FactOverlayCheckResult` / `EvaluationOverlay` / `FactValueOverride` / `FactRemoveAction` / `RuleDisableAction`)
  - `proofframe.py`: ProofFrame Rechecker protocol DTOs (`ProofFrameRecheckRequest` / `ProofFrameRecheckResult` / `ProofFrameAtomVerdict` / `ProofFrameStatus`)
  - `rule_disable.py`: Rule Disable protocol DTOs (`RuleDisableRequest` / `RuleDisableResult` / `RuleDisableStatus`)
  - `derivation_why_not.py`: Why-not Universe Diagnose protocol DTOs (`WhyNotUniverseRequest` / `WhyNotUniverseResult` / `WhyNotRedRow` / `WhyNotRowDiagnostic` / `WhyNotAtomLocator`)
- `schema_runtime.py`
  - schema index, identity materialization, ref encoding, field/type lookup
- `capability_helpers.py`
  - application-layer ergonomic helpers: `build_fact_value_override(...)`, `build_fact_remove_action(...)`, `build_evaluation_overlay(...)`, `build_why_not_candidate_universe(...)`, `build_frontier_view_facts(...)`
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
  - `check_derivation_binding(...)`: verify a complete or partial binding against a single compiled derivation plan; native/souffle/problog/pyreason are handled through representability-gated final-result matching.
- `diagnose_runtime.py`
  - `diagnose_derivation_binding(...)`: diagnose a complete or partial binding against a single compiled derivation plan; native can localize the failed atom, while souffle/problog/pyreason return coarse pass/fail/unsupported classifications through evidence-aware dispatch.
- `fact_overlay_runtime.py`
  - `check_fact_overlay_binding(...)`: check a requested binding under temporary fact replace/remove overlays without writing the ledger; native runs baseline plus overlay-applied phases and returns before/after/diff summaries, while souffle/problog/pyreason return `ENGINE_OVERLAY_NOT_SUPPORTED`.
- `proofframe_runtime.py`
  - `recheck_proof_frame(...)`: recheck one native `SupportArtifact` under an `EvaluationOverlay` without re-running derivation evaluation; returns per-atom verdicts and aggregate frame status. Non-native support artifacts and rule-ref frames return frame-level `unknown`; `not` steps are strictly deferred to `unknown`.
  - `render_proof_frame_narrative(...)`: deterministic English single-frame narrative formatter over a `ProofFrameRecheckResult`.
- `rule_disable_runtime.py`
  - `check_rule_disable_action(...)`: evaluate one native `RuleSpec` under exactly one temporary `RuleDisableAction`; returns normalized variant rows plus a `ProofFrameRecheckResult` for the original frame. RuleRef-bearing inputs are unsupported,variant support capture is deferred,and no ledger or registry mutation occurs.
- `why_not_runtime.py`
  - `check_why_not_universe(...)`: assemble a red/green board for an explicit finite head-binding universe, then diagnose each red row through `diagnose_derivation_binding(...)` while returning Why-not-owned row diagnostics.

## 3. Public Runtime Surface

`src/kernel/application/__init__.py` currently exports 45 public symbols. The main executor entry points are:

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
- `check_rule_disable_action(...)`
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

## 4. 与其他层的关系

- `core`
  - owns low-level ledger/store/rule/evidence primitives.
  - application composes these primitives into stable Python runtime contracts.
- `sdk`
  - owns product surface, authoring DSL, Python ergonomics, facade objects and compatibility aliases.
  - adapts SDK outward types into application DTOs and maps application results back to SDK outward types.
- `service` / `agent`
  - must not add production SDK runtime imports.
  - current allowed production SDK import is the agent extraction authoring helper `compile_schema_from_classes`.
- `adapters` / `domains`
  - some out-of-scope SDK consumers still exist, such as PyReason adapter DSL coupling and ECSS SDK helpers. These are tracked as future primitive-contract or domain-facade work.

## 5. SDK Adapter Status

Current SDK runtime delegation:

- `sdk.get(...)` / `sdk.find(...)` use application read/hydration DTOs.
- `SDKBatchTx.preview()` and `BatchPlan.apply()` delegate to application write planning/apply when the staged operations can be represented by application protocol.
- `sdk.run(Query(...))` lowers SDK `Query` to application `QueryRuntimeRequest`, then maps application `EntitySnapshotDTO` rows back to SDK `EntitySnapshot` / dict / instance shapes.
- `sdk.ingest(...)` keeps SDK descriptor parsing and diagnostics, then delegates cache-resolvable normalized set/add/retract items to `apply_ingest_request(...)`; cache misses fall back to the legacy SDK write path.
- `sdk.evaluate(...)` / compiled derivation evaluate delegate compiled plans to `evaluate_derivation_plans(...)`.
- Check, Diagnose, Fact Overlay Check, ProofFrame Rechecker, Rule Disable, Why-not Universe Diagnose, and the capability ergonomics helpers are currently exposed at the application layer only. No SDK shell is added in the MVP; any future SDK entrypoint must remain a thin delegate to `check_derivation_binding(...)`, `diagnose_derivation_binding(...)`, `check_fact_overlay_binding(...)`, `recheck_proof_frame(...)`, `check_rule_disable_action(...)`, `check_why_not_universe(...)`, or the application helper functions.

SDK outward behavior remains the compatibility contract for end users; application is the runtime authority behind that facade.

## 6. 保守边界

- Application protocol does not accept SDK-only types.
- Query lowering and authoring validation remain SDK responsibilities.
- Ingest descriptor parsing, item precheck diagnostics and user-facing `IngestResult` remain SDK responsibilities.
- Batch export/replay and wire plan compatibility remain SDK responsibilities.
- `sdk.set(...)` / `sdk.add(...)` / `sdk.retract(...)` remain low-level SDK convenience methods.
- Application write planning is single-target; multi-root atomic batch remains expressed by SDK batch staging.
- Full exception hierarchy migration is deferred. Query/ingest/derivation runtime paths use application DTO error shapes while SDK product-domain errors remain SDK-owned.

## 7. 测试入口

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
- `test_application_rule_disable_protocol.py`
- `test_application_rule_disable_runtime_native.py`
- `test_application_why_not_protocol.py`
- `test_application_why_not_runtime.py`
- `test_application_why_not_sibling_invariant.py`
- `test_sdk_facade_application_delegate.py`
- `test_sdk_batch_application_delegate.py`
- `test_sdk_query_policies.py`
- `test_sdk_ingest_application_delegate.py`
- `test_sdk_consumer_boundary.py`

## 8. 相关文档

- [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
- [src/kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/sdk/docs/README.md)
