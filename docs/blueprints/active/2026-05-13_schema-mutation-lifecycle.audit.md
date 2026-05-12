# Task Blueprint Audit: Schema Mutation Lifecycle

- Blueprint: [2026-05-13_schema-mutation-lifecycle.md](./2026-05-13_schema-mutation-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Drafted schema mutation lifecycle slice after rc.3 publish. Source audit found `fg.schema` has no mutation methods, SDKStore caches multiple schema-derived indexes, and schema digest anchors now span ledger, registry, and workspace manifest. Draft recommends an additive-only first slice. |
| 2026-05-13 | scoped | G0 scope freeze | Locked 15 decisions: additive-only entity-class schema extension; `fg.schema.add(...)` public shape; immediate mutation; strict seven-category additive validator; active in-memory/ledger/registry digest update with workspace manifest save-time; no delete/deprecate/update/migrate; `kernel.application.schema_mutation_runtime`; `SchemaAddResult`; same-slice docs; idempotent re-add no-op. |

## Decision Notes

- 2026-05-13 draft: first-slice recommendation is additive entity-class extension only; destructive delete, deprecate metadata, and full update/migrate machinery remain future unless G0 widens scope.
- 2026-05-13 draft: application-layer runtime ownership is recommended to follow the Blueprint 2/3 Path C pattern.
- 2026-05-13 draft polish: expanded the additive validator into explicit testable categories, added preflight/commit rollback semantics, added post-add asset persistence invariant, and added Q15 recommending idempotent re-add as a no-op.
- 2026-05-13 G0: accepted the recommended atomic path `S1a + S2a + S3a + S4a + S5a + S6a + S7a + S8a + S9a + S10a + S11a + S12a + S13a + S14a + S15a`.
