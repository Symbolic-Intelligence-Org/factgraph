# Task Blueprint Audit: Durable Round Persistence(Batch 6)

- Blueprint: [2026-05-05_round-persistence.md](./2026-05-05_round-persistence.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial Batch 6 draft opened on `v0.1-round-persistence-2026-05-05` off `9ab282d`. Scope is deliberately Step-0-first:the draft does not assume a universal event schema,does not modify Store/sidecar semantics,and keeps Batch 7 diff/aggregation out of scope. |
| 2026-05-06 | draft | Pre-commit framing review pass 1 | Added three persistence-specific falsifiers before draft commit:event source mechanism(runtime emit vs wrapper/explicit recorder),explicit round lifecycle vs implicit time window,and atomic finalize vs streaming append. These are true Step 0 forks for persistence and now appear in §5.1 plus §5.3 carry-overs. |

## Decision Notes

### Initial Framing

Batch 6 is the first persistence-facing batch after the rule-action series. The draft therefore treats "capability-event JSONL audit trail" as a falsifiable proposal,not as a preselected implementation. The main false-merge risk is conflating existing audit package ledgers,ArtifactSidecar payload persistence,and new application capability result events into one schema without proving they share lifecycle identity.

Default lean is Path A(optional `round_events.jsonl` inside existing audit package)because the parent plan requires compatibility with `AuditQuery` / `load_audit_package`,but Path B(separate round package)and Path C(suspend/abandon as premature)remain valid Step 0 outcomes.
