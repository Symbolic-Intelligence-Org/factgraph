# Task Blueprint Audit: Candidate Confidence Kind

- Blueprint: [2026-03-20_candidate-confidence-kind.md](./2026-03-20_candidate-confidence-kind.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | scoped | Blueprint created | Child 1 of certainty-weight-vocabulary. Impact analysis identified 5 production sites, 2 propagation sites, 2 serialization sites, 6+ consumption sites. |
| 2026-03-20 | implementing | Core/service propagation landed | Added `CandidateSet.confidence_kind`, propagated it through builders/runtime/SDK/service/accept, and tagged ProbLog candidates as `probability` while deterministic paths default to `none`. |
| 2026-03-20 | implemented | Tests and docs synced | Added contract tests for validation, ProbLog tagging, runtime legacy fallback, and accept meta persistence; full suite passed (`175` tests). Synced core/service/adapter/protocol docs and prepared archive. |

## Decision Notes

- 2026-03-20: `confidence_kind` is a value-semantics annotation only. It must not affect evaluate/accept/chosen execution behavior.
- 2026-03-20: `confidence_kind` does not enter `candidate_key` or `candidate_id` computation — it is not part of candidate identity.
- 2026-03-20: First round does not change consumption-site behavior (confidence aggregation, mapping resolution). These sites become kind-aware in future rounds.
