# Task Blueprint Audit: Primary-Anchor Domain Read

- Blueprint: [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md)
- Parent Blueprint: [2026-05-10_primary-identity-domain-semantics.md](./2026-05-10_primary-identity-domain-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-10 | draft | Spin-off blueprint created from parent §5.5 / §5.6 | Parent judgment recommended separating read-layer concerns from primary-first completion; this seed carries §5.5 (Read layer) and §5.6 (Return type) plus newly seeded §5.A / §5.D / §5.E / §5.F / §5.G open questions. No code, tests, release refs, or memory updates. |

## Decision Notes

- 2026-05-10: Spin-off created per parent blueprint judgment recommendation #1. Parent §5.5 / §5.6 questions are out-of-scope for the parent and tracked here instead. Parent §5.5 / §5.6 sections in the parent blueprint should be marked DEFERRED with a pointer to this audit log when the parent's iterative gap pass reaches them.
- 2026-05-10: Adding a primary-anchor read API is treated as a NEW capability per [project_application_first_runtime_authority.md](../../../memory/project_application_first_runtime_authority.md): if §5.A locks "ship", application-layer DTO + pure function design must precede any SDK shell sketch.
- 2026-05-10: Parent blueprint's §6 invariant (`idref_v1 = all identity fields`) is preserved as input here; if §5.E proves a separate logical-entity-ref token is required, this blueprint must immediately re-scope and reopen the parent invariant.
- 2026-05-10: §5.G primary-anchor write API is recorded as DEFAULT NO and OUT-OF-SCOPE; recorded only to prevent quiet drift, not as an active design question.
