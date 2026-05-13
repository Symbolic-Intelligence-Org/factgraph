# Task Blueprint Audit: Assertion Collection Scope Access

- Blueprint: [2026-05-13_assertion-collection-scope-access.md](./2026-05-13_assertion-collection-scope-access.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Initial draft records a unified assertion collection manager design for field, snapshot, and graph scopes. |
| 2026-05-13 | draft | Derived status cleanup candidate added | Added scope-freeze decision point for removing SDK `AssertionRecord.is_revoked` as a pure derivative of `not is_active`; service/audit/agent DTO fields are explicitly out of scope. |
| 2026-05-14 | draft | G0 scope-freeze candidates expanded | Added proposed hard-cut decisions, `field(...)` input asymmetry, eager graph-scan boundary, ledger-view invariant, record context rationale, frozen-view relation, and deferred Query/view composition note. |
| 2026-05-14 | scoped | G0 scope frozen | Locked manager verbs, field input asymmetry, three hard cuts (`snap.assertions.<field>`, field `.active/.history`, SDK `is_revoked`), graph eager-scan boundary, ledger-view semantics, frozen-view relation, and deferred Query/Search composition. |
| 2026-05-14 | scoped | G1 red baseline added | Added `src/kernel/tests/test_sdk_assertion_collection_scope.py` with 14 focused tests for snapshot/graph/field collection managers, field-name collision handling, record context, ledger-level graph semantics, hard cuts, and deferred Query witness scope. Baseline command: `PYTHONPATH=src python -m unittest -v kernel.tests.test_sdk_assertion_collection_scope` = 14 tests, 1 pass, 2 failures, 11 errors. |
| 2026-05-14 | scoped | G2 implementation landed locally | Added snapshot and graph assertion collection manager verbs, converted field scope to `active()` / `all()`, added `AssertionRecord` context fields, removed SDK `is_revoked`, migrated affected SDK tests, and added descriptor/entity mismatch coverage. Verification: `PYTHONPATH=src python -m unittest -v kernel.tests.test_sdk_assertion_collection_scope` = 15 OK; `PYTHONPATH=src python -m unittest discover -s src/kernel/tests` = 2214 OK, 1 skipped. |
| 2026-05-14 | implemented | Docs synced and outcome filled | Updated SDK module docs plus official assertion/namespace quickstart docs to the unified manager vocabulary. Filled blueprint acceptance and outcome. Verification: official docs baseline = 7 OK; full kernel discovery remains 2214 OK, 1 skipped. |
| 2026-05-14 | archived | Blueprint archived | Moved implemented blueprint and audit from `docs/blueprints/active/` to `docs/blueprints/archive/`. |

## Decision Notes

- 2026-05-13 draft: Preferred vocabulary is `active()` plus `all()`, not `history()`, because graph-level `history()` can be confused with ledger/audit event history.
- 2026-05-13 draft: `snap.assertions.field(name)` is proposed to replace attribute field access and avoid collisions with manager methods such as `active()` and `all()`.
- 2026-05-13 draft: `fg.assertions.field(User.name)` should prefer SDK field descriptors because string field names can collide across entity types.
- 2026-05-13 draft: `AssertionRecord` needs context fields (`entity_type`, `field_name`, `pred_id`, `e_ref`) once records can be returned from cross-field or graph-wide scopes.
- 2026-05-13 draft: Product is unreleased, so a hard cut of old field `.active` / `.history` properties is acceptable if tests and docs move together.
- 2026-05-13 draft: Local survey shows SDK `AssertionRecord.is_revoked` is constructed as `not active` and exposed in docs/tests, but not used as SDK runtime input. Removal should be considered with this slice because the record shape is already changing.
- 2026-05-14 draft: `fg.assertions.field(...)` should accept only `Field` descriptors; `snap.assertions.field(...)` may accept strings because snapshot entity type is fixed.
- 2026-05-14 draft: Graph-wide `fg.assertions.active()/all()` is a ledger-level eager scan for this slice, not snapshot projection, not read-policy filtering, and not a streaming/paginated query.
- 2026-05-14 draft: Current Query returns entity snapshots or scalar values, not assertion witness ids; Query/assertion-set composition is promising but requires a separate Query/Search taxonomy and fact-universe design.
- 2026-05-14 scoped: Scope-freeze confirms `fg.assertions.field(...)` accepts only `Field` descriptors, while `snap.assertions.field(...)` accepts string or matching `Field` descriptor.
- 2026-05-14 scoped: Scope-freeze confirms hard-cut removal of `snap.assertions.<field>` attribute access, field-level `.active` / `.history` properties, and SDK `AssertionRecord.is_revoked`.
- 2026-05-14 scoped: Query/Search taxonomy, Query witness assertion ids, assertion-set-scoped Query execution, and "view as new FactGraph" construction are deferred to a future blueprint.
- 2026-05-14 scoped: G1 tests intentionally keep the deferred Query witness guard in the same file: `AssertionRecordSet.match(query)` must remain absent, while Query-returned entity snapshots should continue to expose no assertion witness records after the new manager surface exists.
- 2026-05-14 scoped: G2 fixture adjustment filters by `source="correction"` for single-field record-set assertions because SDK single-field writes may leave multiple active assertion records; current projection selection remains outside this slice.
- 2026-05-14 scoped: Snapshot `field(FieldDescriptor)` now rejects descriptors owned by another entity type even when the field name collides, preserving the G0 "matching descriptor" decision.
