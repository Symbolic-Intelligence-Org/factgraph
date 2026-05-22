# Task Blueprint Audit: AML Transaction Feed Normalization Anchoring

- Blueprint: [2026-03-18_aml-transaction-feed-normalization-anchoring.md](./2026-03-18_aml-transaction-feed-normalization-anchoring.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened an upstream anchoring slice after the cross-domain walkthrough phase concluded that runtime/explain had reached a stable stopping point and the thinnest remaining layer was Source/Ingestion/Normalize. |
| 2026-03-18 | scoped | Scope freeze | Closed the route comparison by adopting structured transaction-feed normalization as the first upstream vertical slice and by treating document/narrative extraction as a deferred route. |
| 2026-03-18 | implemented | Gate answers recorded | Resolved all three gates to walkthrough-level answers: assertion-level source drill-down is sufficient, explicit lineage remains deferred, and first implementation should include a synthetic normalize step rather than a durable ingest API. |
| 2026-03-18 | archived | Blueprint archived | The anchoring concluded without code changes: the next slice is `aml-transaction-feed-materialization-walkthrough`, while source identity, lineage contract, and document extraction remain deferred. |

## Decision Notes

- 2026-03-18
  - Direction rule: the next slice must rebalance the system upward toward source/ingestion/normalize, not continue thickening explain delivery.
- 2026-03-18
  - Comparison rule: structured transaction-feed normalization is the default near-term candidate; document/narrative extraction is only a comparison route, not the assumed first implementation.
- 2026-03-18
  - Scope rule: this anchoring must choose the first upstream vertical slice, not design a generalized ingestion platform.
- 2026-03-18
  - Gate answer: first-round source-record identity does not need to be first-class; assertion-level drill-down is sufficient until multi-source merge or dedup pressure appears.
- 2026-03-18
  - Gate answer: explicit lineage between normalized facts and helper outputs is deferred; current assertion graph and audit package are enough for a first walkthrough.
- 2026-03-18
  - Gate answer: the first implementation should still be a walkthrough/regression, but it must include an explicit synthetic normalize step so source-to-fact shape is exercised rather than assumed.
