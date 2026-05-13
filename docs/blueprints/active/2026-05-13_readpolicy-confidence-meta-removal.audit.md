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

## Decision Notes

- 2026-05-13 draft: Scope boundary is split between removed read/display assertion metadata (`ReadPolicy`, `policy=`, `return_display_meta`, `meta.confidence`, `meta.confidence_source`) and preserved engine/candidate/certainty carriers (`CandidateSet.confidence`, `confidence_kind`, ProbLog/PyReason outputs, certainty internals).
- 2026-05-13 draft: `return_display_meta=True` is proposed for same-slice removal because current output is only confidence display metadata (`confidence`, `confidence_strategy`, `source_breakdown`).
- 2026-05-13 draft: service `view-facts.policy` is proposed for same-slice removal because it is the same display projection path as SDK `ReadPolicy`.
- 2026-05-13 draft: `evaluate(view=...)` is explicitly non-goal. Frozen view inference scoping remains an independent design topic.
- 2026-05-13 draft: Additional cleanup item discovered during survey: `core.mapping.canon` supports `tie_break.mode == "max_confidence"` by reading `meta.confidence`; this must be removed or rejected with the same hard-cut.
- 2026-05-13 draft: Historical compatibility is not a design constraint because the product is not yet released. Raw metadata remains a generic escape hatch, but the cleanup does not need deprecation or compatibility scaffolding.
- 2026-05-13 scoped: Phase 1 may add red tests and preservation guards only. Runtime implementation and docs sync remain deferred to later phases.
- 2026-05-13 scoped: Phase 1 command `PYTHONPATH=src python -m unittest -v kernel.tests.test_readpolicy_confidence_meta_removal` fails by design before implementation. Passing guards cover `CandidateSet.confidence`, ProbLog probability annotations, PyReason shared-meta stripping, and `record.meta.raw["confidence"]`.
