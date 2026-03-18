# Task Blueprint Audit: AML Event Aggregation Semantics

- Blueprint: [2026-03-18_aml-event-aggregation-semantics.md](./2026-03-18_aml-event-aggregation-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the next AML analysis slice to determine whether first meaningful event aggregation can remain a pre-materialized helper contract or must move into T2-level sequence/state semantics. |
| 2026-03-18 | scoped | Scope freeze | Closed the route comparison by adopting pre-materialized aggregation as the first-round path and treating true in-rule aggregation as deferred T2 capability work. |
| 2026-03-18 | implemented | Analysis conclusion recorded | Resolved the blueprint to Route A, defined explain-honesty boundaries for materialized aggregation facts, and named the next slice `aml-aggregation-materialization-walkthrough`. |
| 2026-03-18 | archived | Blueprint archived | The analysis concluded without code changes: aggregation stays upstream of judgment and uncertainty, and first-round AML work should continue via a materialization walkthrough rather than T2. |

## Decision Notes

- 2026-03-18
  - Priority rule: aggregation is treated as upstream of judgment and uncertainty; those two should remain explicitly deferred unless aggregation analysis proves otherwise.
- 2026-03-18
  - Route comparison: the blueprint must compare pre-materialized helper contract vs true in-rule aggregation, rather than assuming T2 by default.
- 2026-03-18
  - Scope rule: this slice is analysis-only and must end with a single adopted next-slice recommendation.
- 2026-03-18
  - Adopted answer: Route A is sufficient for first-round. Materialized aggregation facts are explain-honest at the same level as existing T1 temporal anchors: the trace shows what the rule saw, not how upstream helpers originally computed those facts.
- 2026-03-18
  - Deferred capability boundary: Route B is explicitly reclassified as T2/kernel work, not an AML-local follow-on. It should open only when a scenario truly requires in-rule sequence/state semantics.
