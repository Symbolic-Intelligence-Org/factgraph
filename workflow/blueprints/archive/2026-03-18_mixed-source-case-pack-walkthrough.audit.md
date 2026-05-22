# Task Blueprint Audit: Mixed-Source Case Pack Walkthrough

- Blueprint: [2026-03-18_mixed-source-case-pack-walkthrough.md](./2026-03-18_mixed-source-case-pack-walkthrough.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the first implementation-facing mixed-source same-case slice after the anchoring concluded that a controlled case pack is the highest-value post-validation pressure source. |
| 2026-03-18 | scoped | Scope freeze | Locked the walkthrough to a mixed-source same-case test-only slice with cross-source distinguishability as the new load-bearing check, requiring assertion-detail-based proof that feed-derived, form-derived, and note-derived facts remain separable without new package/linkage contracts. |
| 2026-03-18 | implemented | Mixed-source case-pack walkthrough regression landed | Added a synthetic mixed-source same-case walkthrough to `test_phase3_contracts_v1.py`, combining feed, form, and note helpers into one downstream AML-style rule run with assertion-detail-based distinguishability checks. |
| 2026-03-18 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 75 tests, confirming the mixed-source walkthrough fits inside the current explain substrate without new case/package, source-linkage, durable-ingest, or snippet/span contracts. |
| 2026-03-18 | archived | Blueprint archived | The walkthrough concluded that first-round mixed-source same-case validation can remain a test-scope vertical slice; no immediate package/linkage/durable-ingest blocker was exposed. |

## Decision Notes

- 2026-03-18
  - Direction rule: the new load-bearing check is cross-source distinguishability, not another single-source extraction proof.
- 2026-03-18
  - Scope rule: the walkthrough must stay test-only and must not silently upgrade into a first-class case/package or source-linkage feature.
- 2026-03-18
  - Validation rule: mixed-source distinguishability must be proven through `assertion_index.get_assertion_detail()` and source-family-specific refs in `claim_args`, not by relying on test variable names or fixture context.
- 2026-03-18
  - Outcome: the existing explain stack remained honest enough for first-round mixed-source same-case pressure. Feed-derived, form-derived, and note-derived facts stayed independently inspectable and distinguishable through assertion detail surfaces, while runtime/audit wording did not over-claim package-level synthesis.

