# Overview of the Application Module (`kernel`)

- Scope: `src/kernel/application`
- Last updated: 2026-05-05
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
- explicit-binding Fact Overlay Check (`before` / `after` / `diff` under temporary fact overrides, native-only MVP)
- explicit-universe Why-not Diagnose (`green` / `red` partition with row-level Diagnose summaries)

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
  - `derivation_fact_overlay.py`: Fact Overlay Check protocol DTOs (`FactOverlayCheckRequest` / `FactOverlayCheckResult` / `FactValueOverride`)
  - `derivation_why_not.py`: Why-not Universe Diagnose protocol DTOs (`WhyNotUniverseRequest` / `WhyNotUniverseResult` / `WhyNotRedRow` / `WhyNotRowDiagnostic` / `WhyNotAtomLocator`)
- `schema_runtime.py`
  - schema index, identity materialization, ref encoding, field/type lookup
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
  - `check_fact_overlay_binding(...)`: checks a requested binding under temporary fact overrides without writing the ledger; native runs baseline plus overlay-applied phases and returns before/after/diff summaries, while souffle/problog/pyreason return `ENGINE_OVERLAY_NOT_SUPPORTED`.
- `why_not_runtime.py`
  - `check_why_not_universe(...)`: assembles a red/green board for an explicit finite head-binding universe, then diagnoses each red row through `diagnose_derivation_binding(...)` while returning Why-not-owned row diagnostics.

## 3. Public Runtime Surface

`src/kernel/application/__init__.py` currently exports 36 public symbols. The main executor entry points are:

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
- `check_why_not_universe(...)`
- `accept_derivation_candidate_set(...)`
- `accept_derivation_candidate_sets(...)`

The main schema/runtime helpers are:

- `build_schema_index(...)`
- `resolve_selector(...)`
- `materialize_identity(...)`
- `encode_entity_ref(...)`
- `entity_info(...)`
- `field_predicate(...)`
- `field_value_type(...)`
- `entity_type_from_ref(...)`

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
- Check, Diagnose, Fact Overlay Check, and Why-not Universe Diagnose are currently exposed at the application layer only. No SDK shell is added in the MVP; any future SDK entrypoint must remain a thin delegate to `check_derivation_binding(...)`, `diagnose_derivation_binding(...)`, `check_fact_overlay_binding(...)`, or `check_why_not_universe(...)`.

SDK outward behavior remains the compatibility contract for end users; application is the runtime authority behind that facade.

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
- `test_application_fact_overlay_protocol.py`
- `test_application_fact_overlay_runtime_native.py`
- `test_application_fact_overlay_sibling_invariant.py`
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
