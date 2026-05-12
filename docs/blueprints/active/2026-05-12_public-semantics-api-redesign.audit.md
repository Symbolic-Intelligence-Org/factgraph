# Task Blueprint Audit: Track 2 Public Semantics API Redesign

- Blueprint: [2026-05-12_public-semantics-api-redesign.md](./2026-05-12_public-semantics-api-redesign.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Track 3 and Track 1 publish. Source audit found that SDK can resolve branch ids only while SDK `Rule` / `Derivation` objects are still in hand; service and compiled paths currently carry only canonical `SemanticsProfile`. PyReason per-branch head bounds are mechanically feasible via per-branch rule compilation but not yet represented by `PyReasonRuleExt`. |

## Decision Notes

- 2026-05-12 draft: Track 2 starts from the post-Track-3 design-point doc plus Track 1 archive. The key design tension is whether Track 2 is a thin SDK wrapper layer over `SemanticsProfile`, or whether it absorbs the larger PyReason branch-bound carrier reshape currently identified as Track 3-post.
