# Task Blueprint Audit: Schema Mutation Lifecycle

- Blueprint: [2026-05-13_schema-mutation-lifecycle.md](./2026-05-13_schema-mutation-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Drafted schema mutation lifecycle slice after rc.3 publish. Source audit found `fg.schema` has no mutation methods, SDKStore caches multiple schema-derived indexes, and schema digest anchors now span ledger, registry, and workspace manifest. Draft recommends an additive-only first slice. |
| 2026-05-13 | scoped | G0 scope freeze | Locked 15 decisions: additive-only entity-class schema extension; `fg.schema.add(...)` public shape; immediate mutation; strict seven-category additive validator; active in-memory/ledger/registry digest update with workspace manifest save-time; no delete/deprecate/update/migrate; `kernel.application.schema_mutation_runtime`; `SchemaAddResult`; same-slice docs; idempotent re-add no-op. |
| 2026-05-13 | scoped | G1 red + guard baseline | Added `test_schema_mutation_lifecycle.py` with 39 tests: public API shape, `SchemaAddResult`, application runtime import, immediate mutation, seven-category strict validator, digest-anchor handling, workspace save-time behavior, post-add asset persistence, deferral guards, and preservation guards. Expected red shape: 2 failures + 28 errors + 9 passing guards. Preservation suites: 88/88 lifecycle-assets and 56/56 SDK invariants OK. |
| 2026-05-13 | scoped | G2.1 application runtime + DTO | Added `kernel.application.schema_mutation_runtime`, `SchemaAddResult`, `AdditiveExtensionResult`, strict additive validator, and SDK export. Updated SDK `__all__` invariants for the intentional public DTO (+1 entry). Schema mutation baseline moved to 1 failure + 19 errors + 19 passing tests. Preservation suites: 88/88 lifecycle-assets and 57/57 SDK invariants OK. |
| 2026-05-13 | scoped | G2.2 schema add in-memory refresh | Added `fg.schema.add(...)` via `_SDKSchemaManager`, delegated to `schema_mutation_runtime`, and refreshed SDK/core in-memory schema state (`_classes`, `_schema_ir`, `_schema_digest`, application schema index, field indexes). Schema mutation baseline moved to 4 failures + 1 error, all confined to ledger/registry digest-anchor handling. Preservation suites: 88/88 lifecycle-assets and 57/57 SDK invariants OK. |
| 2026-05-13 | scoped | G2.3 digest anchors + implementation complete | Added ledger metadata replacement for lifecycle-managed schema digest updates and wired `fg.schema.add(...)` to preflight/update ledger and registry schema digest anchors. This also satisfied workspace save-time and post-add asset persistence gates without additional code. Validation: 39/39 schema mutation, 88/88 lifecycle-assets preservation, and 57/57 SDK invariants OK. |
| 2026-05-13 | scoped | G3 docs sync | Updated SDK user/API docs, application docs, and lifecycle/assets design-point with landed additive `fg.schema.add(...)` behavior, `SchemaAddResult`, schema mutation runtime ownership, workspace save-time boundary, and deferred destructive schema migration scope. |
| 2026-05-13 | implemented | G4 close-out | Filled outcome/deviations, marked acceptance complete, archived blueprint pair, and prepared milestone publish. Final validation: 39/39 schema mutation, 88/88 lifecycle-assets preservation, 57/57 SDK invariants OK. |

## Decision Notes

- 2026-05-13 draft: first-slice recommendation is additive entity-class extension only; destructive delete, deprecate metadata, and full update/migrate machinery remain future unless G0 widens scope.
- 2026-05-13 draft: application-layer runtime ownership is recommended to follow the Blueprint 2/3 Path C pattern.
- 2026-05-13 draft polish: expanded the additive validator into explicit testable categories, added preflight/commit rollback semantics, added post-add asset persistence invariant, and added Q15 recommending idempotent re-add as a no-op.
- 2026-05-13 G0: accepted the recommended atomic path `S1a + S2a + S3a + S4a + S5a + S6a + S7a + S8a + S9a + S10a + S11a + S12a + S13a + S14a + S15a`.
- 2026-05-13 G1: baseline intentionally locks application helper names `validate_additive_schema_extension` and `add_schema_classes` in `kernel.application.schema_mutation_runtime` so G2 follows the application-first runtime pattern used by authoring/workspace lifecycle slices.
- 2026-05-13 G2.1: `SchemaAddResult` is the first schema-mutation DTO intentionally exported from `kernel.sdk`; prior shell result DTO non-export invariants were updated without exporting any shell/application result types.
- 2026-05-13 G2.2: in-memory refresh clears and rebuilds field/entity indexes instead of appending to old indexes, preserving write/read behavior for both old and newly-added classes.
- 2026-05-13 G2.3: `Ledger.set_ledger_meta(...)` remains insert-only; schema mutation uses new `replace_ledger_meta(...)` so the existing insert-preserve behavior stays intact for other callers.
- 2026-05-13 G3: design-point current-behavior section now treats `fg.schema.add(...)` as landed but keeps field-add, Relationship-class add, delete/deprecate, and update/migrate as future schema-evolution work.
