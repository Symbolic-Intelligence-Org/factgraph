# Task Blueprint Audit: AML Case-Review Walkthrough

- Blueprint: [2026-03-18_aml-case-review-walkthrough.md](./2026-03-18_aml-case-review-walkthrough.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the first AML implementation-facing slice after the anchoring memo resolved that single `rule_run_id` proof-entry and the current five-layer explain delivery stack are sufficient for a first-round walkthrough. |
| 2026-03-18 | scoped | Scope frozen | Locked the walkthrough to a single composite rule run and added minimum fact-diversity constraints (`>=3` transactions, `>=2` signal types, linked beneficiary/jurisdiction risk fact) so the slice actually pressures multi-entity fan-out instead of passing on a flat happy path. |
| 2026-03-18 | implemented | AML walkthrough regression landed | Added a synthetic suspicious-account walkthrough to `test_phase3_contracts_v1.py` and validated the existing raw/summary/narrative/NL/static explain stack without changing any runtime or audit contract. |
| 2026-03-18 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 65 tests, confirming the AML walkthrough does not regress the existing explain delivery stack. |
| 2026-03-18 | archived | Blueprint archived | The walkthrough concluded that the current substrate is sufficient for a single-rule-run AML case-review slice; no gap blueprint is required before archive. |

## Decision Notes

- 2026-03-18
  - Scope lock candidate: this walkthrough should stay a single composite rule-run regression slice, not drift into case-level aggregation or AML ontology work.
- 2026-03-18
  - Delivery boundary: the walkthrough must validate existing raw/summary/narrative/NL/static surfaces as-is, rather than using AML as a reason to redesign explain delivery.
- 2026-03-18
  - Failure handling: if the walkthrough exposes a real substrate gap, that gap should become its own follow-on blueprint rather than being absorbed into this walkthrough slice.
- 2026-03-18
  - Pressure constraint: the AML walkthrough must include enough fact diversity to stress repeated witnesses and cross-entity linkage; otherwise it would not meaningfully answer the anchoring gate about multi-entity explain fan-out.
- 2026-03-18
  - Outcome: the first-round AML walkthrough can stay entirely inside the existing explain delivery stack; case-level aggregation and new delivery surfaces remain explicitly out of scope until a later scenario proves they are necessary.
