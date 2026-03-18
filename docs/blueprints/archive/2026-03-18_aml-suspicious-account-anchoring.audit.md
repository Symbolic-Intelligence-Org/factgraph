# Task Blueprint Audit: AML Suspicious-Account Scenario Anchoring

- Blueprint: [2026-03-18_aml-suspicious-account-anchoring.md](./2026-03-18_aml-suspicious-account-anchoring.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened a new cross-domain scenario anchoring slice so the next workstream can stress-test the explain/delivery substrate outside the ECSS line. |
| 2026-03-18 | scoped | Scope frozen | Locked the two-cut memo shape (`AML-Review` vs `AML-Trigger`), added explicit substrate-tension checks for case-review fan-out and investigator-facing narrative, and recorded the gate that must be answered before any walkthrough implementation opens. |
| 2026-03-18 | implemented | Gate resolution recorded | Confirmed that single `rule_run_id` proof-entry is sufficient for a first-round walkthrough, while case-level aggregation remains out of scope and would require its own gap slice if needed later. |
| 2026-03-18 | archived | Analysis anchor completed | The memo now names `aml-case-review-walkthrough` as the next implementation-facing slice and archives after resolving the gate questions. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: this slice should anchor `AML/KYC suspicious-account` as a named scenario line, not jump directly into another temporal or uncertainty implementation task.
- 2026-03-18
  - Comparison structure: first-round memo should compare a near-term `AML-Review` cut with a medium-term `AML-Trigger` cut, because they stress different combinations of delivery, temporal aggregation, deontic judgment, and uncertainty.
- 2026-03-18
  - Authority boundary: AML/KYC references in working notes and Rainbird comparison material are design pressure only; they do not become regulatory truth or legal claims inside this blueprint.
- 2026-03-18
  - Implementation gate: before opening an AML walkthrough implementation slice, the anchoring memo must answer whether a single `rule_run_id` is a sufficient case-review entry point and whether the existing five-layer explain delivery stack already serves investigator-facing consumption without structural additions.
