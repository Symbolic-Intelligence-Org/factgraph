# Task Blueprint Audit: Evidence Diff / Cross-Run(Batch 7)

- Blueprint: [2026-05-06_evidence-diff.md](./2026-05-06_evidence-diff.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 7 draft opened on `v0.1-evidence-diff-2026-05-06` off Batch 6 hardening final `95f0d14`. Scope is deliberately Step-0-first:the draft does not assume Batch 6 round events are sufficient for L4/L5,keeps Path B suspension and Path C split as live options,and forbids SDK/service/agent/runtime/protocol drift before Step 0 records a scoped need. |
| 2026-05-06 | draft | Pre-commit framing review pass 1 | Three framing tightenings per review before draft commit:(P3)added consumer-value falsifier #16 so L4 diff can be suspended if it has no value beyond existing ProofFrame narrative/raw event queries;(P3)made Path C trigger #8 testable by comparing diff vs aggregation identity/output overlap;(P3)added Step 0.B carry-over for diff input cardinality(bilateral vs baseline-plus-variants). |

## Decision Notes

- Batch 7 starts from the post-hardening Batch 6 contract:optional `audit/round_events.jsonl`,S3 first-slice event kinds,and `proof_frame_result` with `status + atom_verdicts`.
- Main false-merge risk:per-frame ProofFrame diff and cross-run module aggregation may share inputs but not identity or output shape.
- Key Step 0 risk:Batch 6 deliberately deferred module aggregation keys,Frontier events,and rule-action events. Batch 7 must prove a useful first slice exists over persisted rows instead of silently expanding Batch 6.
- Consumer-value risk:L4 diff should not ship as a vanity wrapper over existing ProofFrame narrative or raw round-event queries;Step 0.A falsifier #16 must identify the concrete consumer before implementation.
