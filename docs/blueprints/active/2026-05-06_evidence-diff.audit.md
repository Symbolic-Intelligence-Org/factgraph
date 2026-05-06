# Task Blueprint Audit: Evidence Diff / Cross-Run(Batch 7)

- Blueprint: [2026-05-06_evidence-diff.md](./2026-05-06_evidence-diff.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 7 draft opened on `v0.1-evidence-diff-2026-05-06` off Batch 6 hardening final `95f0d14`. Scope is deliberately Step-0-first:the draft does not assume Batch 6 round events are sufficient for L4/L5,keeps Path B suspension and Path C split as live options,and forbids SDK/service/agent/runtime/protocol drift before Step 0 records a scoped need. |
| 2026-05-06 | draft | Pre-commit framing review pass 1 | Three framing tightenings per review before draft commit:(P3)added consumer-value falsifier #16 so L4 diff can be suspended if it has no value beyond existing ProofFrame narrative/raw event queries;(P3)made Path C trigger #8 testable by comparing diff vs aggregation identity/output overlap;(P3)added Step 0.B carry-over for diff input cardinality(bilateral vs baseline-plus-variants). |
| 2026-05-06 | draft | Step 0.A spike completed | Synthesized 16 falsifier verdicts source-grounded against `round_events.py`(post-hardening @ `95f0d14`)+ `query.py` + `proofframe.py` + Batch 4 + Batch 6 archived blueprint outcomes. Verdicts:5 TRUE / 11 FALSE / 0 PARTIAL. Selected Path A with first slice NARROWED to L4 per-frame ProofFrame diff only;L5 cross-run aggregation deferred from first slice(per #5 no `module_id` derivable,#6 kinds don't share grouping key,#8 borderline DTO disjointness).Recorded 11 constraints frozen for Step 0.B and 7 carry-over decisions remaining;new §5.5 added to blueprint(no §6-§10 renumber).Status stays `draft` until Step 0.B finalizes. |
| 2026-05-06 | draft | Step 0.A pre-commit verification pass 1 | Source-verified atom identity before commit. Corrected §5.5 from `plan_digest` to `(support_digest, binding_items)` / same-`support_digest` scope for ProofFrame diff because `proof_frame_result` payload has `request.support_digest` and no `plan_digest`;support atom keys are branch/atom position keys stable inside the same `SupportArtifact`. Also tightened Path A-vs-Path C wording and made L5 reactivation triggers concrete(module mapping or per-kind grouping keys),leaving vague module aggregation out of first slice. |

## Decision Notes

- Batch 7 starts from the post-hardening Batch 6 contract:optional `audit/round_events.jsonl`,S3 first-slice event kinds,and `proof_frame_result` with `status + atom_verdicts`.
- Main false-merge risk:per-frame ProofFrame diff and cross-run module aggregation may share inputs but not identity or output shape.
- Key Step 0 risk:Batch 6 deliberately deferred module aggregation keys,Frontier events,and rule-action events. Batch 7 must prove a useful first slice exists over persisted rows instead of silently expanding Batch 6.
- Consumer-value risk:L4 diff should not ship as a vanity wrapper over existing ProofFrame narrative or raw round-event queries;Step 0.A falsifier #16 must identify the concrete consumer before implementation.
