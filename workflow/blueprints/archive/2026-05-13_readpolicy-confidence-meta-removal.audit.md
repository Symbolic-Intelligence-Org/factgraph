# Task Blueprint Audit: ReadPolicy and Legacy Confidence Meta Removal

- Blueprint: [2026-05-13_readpolicy-confidence-meta-removal.md](./2026-05-13_readpolicy-confidence-meta-removal.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Initial draft records the proposed hard cut for `ReadPolicy`, read/display confidence aggregation, and user-authored `meta.confidence` / `meta.confidence_source`, while preserving candidate and engine confidence carriers. |
| 2026-05-13 | draft | Local survey completed | Verified current references with `rg`; baseline targeted tests `kernel.tests.test_confidence_evidence_meta_release_cleanup`, `kernel.tests.test_sdk_read_policy`, and `service.tests.test_runtime_query_policy` pass 60/60 before the hard cut. |
| 2026-05-13 | draft | Frame-pass wording tightened | Removed compatibility framing for the unreleased-product context, simplified the `ReadPolicy` removal error guidance, added an explicit test-fixture migration gate, and converted the outcome template to English. |
| 2026-05-13 | scoped | Scope frozen for Phase 1 | Locked hard-cut scope for Phase 1 red-baseline tests: remove `ReadPolicy`, `policy=`, `return_display_meta`, user-authored `meta.confidence` / `meta.confidence_source`, first-class assertion confidence, and `max_confidence`; preserve candidate and engine confidence carriers. |
| 2026-05-13 | scoped | Phase 1 red baseline added | Added `kernel.tests.test_readpolicy_confidence_meta_removal`; the scaffold executes 18 tests with current result 14 expected failures / 4 passing preservation guards. |
| 2026-05-13 | scoped | Phase 2 implementation added | Removed the runtime `ReadPolicy` DTO/export, SDK/service policy display paths, first-class assertion confidence, display aggregation, and `max_confidence`; rejected user-authored `meta.confidence` / `meta.confidence_source`; migrated affected test fixtures. |
| 2026-05-13 | scoped | Phase 3 docs sync expanded | Documentation grep found stale inline policy references outside the original docs list (`core/docs/04_service_layer.md`, `service/docs/02_runtime_sessions.md`, `service/docs/06_frontend_integration.md`, and `service/docs/README.md`); blueprint docs inventory expanded before committing docs sync. |
| 2026-05-13 | scoped | Phase 3 docs sync verified | Updated SDK/core/service/adapter docs and the tracked official read-write quickstart cleanup hunk; `rg` found no stale public `ReadPolicy`/display-confidence docs except explicit removed-surface wording, and `kernel.tests.test_readpolicy_confidence_meta_removal + kernel.tests.test_official_kernel_docs_baseline` passed 25/25. |
| 2026-05-13 | implemented | Close verification completed | Filled Outcome / Deviations after targeted close gate passed 100/100 and docs grep remained clean; archived the blueprint as implemented. |

## Decision Notes

- 2026-05-13 draft: Scope boundary is split between removed read/display assertion metadata (`ReadPolicy`, `policy=`, `return_display_meta`, `meta.confidence`, `meta.confidence_source`) and preserved engine/candidate/certainty carriers (`CandidateSet.confidence`, `confidence_kind`, ProbLog/PyReason outputs, certainty internals).
- 2026-05-13 draft: `return_display_meta=True` is proposed for same-slice removal because current output is only confidence display metadata (`confidence`, `confidence_strategy`, `source_breakdown`).
- 2026-05-13 draft: service `view-facts.policy` is proposed for same-slice removal because it is the same display projection path as SDK `ReadPolicy`.
- 2026-05-13 draft: `evaluate(view=...)` is explicitly non-goal. Frozen view inference scoping remains an independent design topic.
- 2026-05-13 draft: Additional cleanup item discovered during survey: `core.mapping.canon` supports `tie_break.mode == "max_confidence"` by reading `meta.confidence`; this must be removed or rejected with the same hard-cut.
- 2026-05-13 draft: Historical compatibility is not a design constraint because the product is not yet released. Raw metadata remains a generic escape hatch, but the cleanup does not need deprecation or compatibility scaffolding.
- 2026-05-13 scoped: Phase 1 may add red tests and preservation guards only. Runtime implementation and docs sync remain deferred to later phases.
- 2026-05-13 scoped: Phase 1 command `PYTHONPATH=src python -m unittest -v kernel.tests.test_readpolicy_confidence_meta_removal` fails by design before implementation. Passing guards cover `CandidateSet.confidence`, ProbLog probability annotations, PyReason shared-meta stripping, and `record.meta.raw["confidence"]`.
- 2026-05-13 scoped: Phase 2 verification passed:
  - `PYTHONPATH=src python -m unittest -v kernel.tests.test_readpolicy_confidence_meta_removal kernel.tests.test_sdk_read_policy service.tests.test_runtime_query_policy kernel.tests.test_sdk_frozen_view_read_runtime_boundaries kernel.tests.test_confidence_evidence_meta_release_cleanup kernel.tests.test_write_protocol_annotations kernel.tests.test_problog_export kernel.tests.test_sdk_assertion_record_set` (93 tests OK)
  - `PYTHONPATH=src python -m unittest -v kernel.tests.test_sdk_g1_invariants kernel.tests.test_sdk_g2_invariants kernel.tests.test_sdk_g3_invariants kernel.tests.test_sdk_g4_invariants kernel.tests.test_sdk_g5_invariants kernel.tests.test_sdk_redesign_invariants kernel.tests.test_sdk_find_partial_identity kernel.tests.test_sdk_frozen_view_surface` (72 tests OK)
  - `PYTHONPATH=src python -m unittest -v kernel.tests.test_authoring_asset_persistence_facade kernel.tests.test_factgraph_workspace_lifecycle kernel.tests.test_problog_engine_eval kernel.tests.test_problog_semantics_profile_migration kernel.tests.test_public_inference_factgraph_create kernel.tests.test_public_semantics_api_redesign kernel.tests.test_pyreason_branch_bounds_carrier kernel.tests.test_pyreason_e2e kernel.tests.test_schema_field_add_lifecycle kernel.tests.test_schema_mutation_lifecycle kernel.tests.test_sdk_service_semantics_callsite service.tests.test_problog_semantic_annotation_l4` (240 tests OK)
