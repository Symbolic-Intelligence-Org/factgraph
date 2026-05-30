# Task Blueprint Audit: Slice 5 — Narrow `:exists` Co-Emission Removal

- Blueprint: [2026-05-30_exists-removal.md](./2026-05-30_exists-removal.md)
- Branch: `v0.2.0-blueprint-exists-removal-2026-05-30`
- Fork point: `870e1f1f` (Q-EXISTS adopted decision head)
- Status: scoped audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from adopted Q-EXISTS decision `870e1f1f`; scope is narrow user-path `:exists` co-emission removal + Identity-bundle `fg.entities.exists`; Q-PR1, shadow store, rule DSL virtual syntax, legacy data migration, and guard-code rename are explicitly out of scope. |
| 2026-05-30 | draft-amend | Step 4.2 reviewer findings applied | Added file:line Evidence column to shipped-surface table, clarified Step 0 inventory output format, tightened Identity-bundle value matching wording, added optional audit close-time update, added §10.1 acceptance-count hint, and simplified SF7 cite wording. |
| 2026-05-30 | preflight-amend | Step 4.3 preflight findings applied | Added `src/factgraph/sdk/batch.py` to scope as a user-facing `record_exists` emission path; preserved wire/protocol `record_exists` compatibility; added Step 0 visibility-helper inventory and SDK batch tests per PF-R1/PF-REC1/PF-REC2. |
| 2026-05-30 | scoped | Scope freeze accepted | Self-check complete: Q-EXISTS §4.1-§4.10 represented, SF1-SF10 locked, Non-goals N1-N11 complete, Step 0-8 implementation plan has commit-boundary deliverables, and §7 acceptance count updated to 26 checkboxes. |
| 2026-05-30 | implementing-step-0 | Pre-implementation inventory complete | Grep inventory found no new Q-PR1, rule-DSL deletion, shadow-store removal, or ledger-migration requirement; implementation can proceed under scoped constraints. |
| 2026-05-30 | implementing-step-1 | Identity-bundle visibility helper added | Added application-layer `is_entity_identity_bundle_active(...)` helper plus helper-level tests for complete bundle, no bundle, partial bundle, mismatched value, revoked Identity Claim, and ignored `:exists`-only visibility; no caller rewiring yet. |
| 2026-05-30 | implementing-step-2 | `fg.entities.exists` rewired | Replaced the SDK `:exists` scan with the application Identity-bundle helper; updated SDK existence tests for complete bundle, incomplete bundle, composite identity, post-delete, and `:exists`-only ignored semantics. Batch/co-emission paths remain unchanged for Step 3. |
| 2026-05-30 | implementing-step-3 | User-path `:exists` co-emission stopped | Removed user-path `record_exists` planning from application materialization and SDK batch staging; preserved application `record_exists` apply handling plus `WireRecordExistsOp` / `PlannedOpDTO(op="record_exists")` compatibility; updated create/emission/batch tests to N Identity + Field semantics with wire legacy coverage. |
| 2026-05-30 | implementing-step-4 | Delete semantics aligned | Confirmed delete succeeds without active `:exists` Claims by migrating delete counts to N Identity + Field; added legacy `:exists` fixtures verifying whole-entity delete can revoke legacy Claims while generic retract still raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`. |
| 2026-05-30 | implementing-step-5 | Legacy guard fixtures formalized | Updated SDK, ingest, and entity_write retract-guard integration tests to inject legacy `:exists` Claims explicitly after user-path co-emission removal; schema-cache and pure retract-guard tests continue to verify `exists_pred_ids` population and `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` classification. |
| 2026-05-30 | implementing-step-6 | Runtime regression sweep | Target migration/regression sweep passed 167 direct test invocations; rule/query `Entity:exists` virtual-syntax smoke passed 26 unittest cases. Sweep found one remaining user-path-emission assumption in `test_sdk_assertions_namespace.py`, fixed by converting that assertion-retract guard case to an explicit legacy `:exists` fixture. |
| 2026-05-30 | implementing-step-7 | Current docs and ADRs updated | Updated ADR-IC current status, Q-EXISTS implementation record, and current SDK docs to state that user-facing `:exists` co-emission is retired while legacy Claims, rule virtual syntax, Q-PR1 derivation markers, wire compatibility, and shadow store remain carry-forward/protected surfaces. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork blueprint from Q-EXISTS adopted head `870e1f1f`. | The blueprint must cite Q-EXISTS §4.1-§4.10 as binding constraints, including amend/adopt changes from `e9d67214` and `870e1f1f`. |
| 2026-05-30 | Keep next slice narrow. | Stage 1 audit `bd3ab5c3` rejected repo-wide `:exists` deletion; Q-EXISTS locks user-path co-emission cleanup plus Identity-bundle existence semantics. |
| 2026-05-30 | Preserve Q-PR1 sacred paths. | Q-EXISTS §4.8 leaves derivation accept `:exists` writes as out-of-scope legacy/derived markers; any exception requires user authorization and blueprint amendment. |
| 2026-05-30 | Preserve `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` name. | Q-EXISTS §4.5 locks the current code name for legacy direct-retract protection to keep this slice narrow. |
| 2026-05-30 | Step 0 runtime inventory closed without amendment. | In-scope runtime surfaces are `application/entity_write.py` (`_materialization_ops`, `_apply_op(record_exists)`, `_entity_visible`), `application/entity_view.py` (`_entity_visible`, `_enumerate_entity_refs`), `sdk/store.py` (`entities.exists`, `entities.delete`), and `sdk/batch.py` (`_handle_requires_record_exists_op`, application delegation, wire compatibility). `application/protocol/entity_write.py`, `schema_runtime.py`, and `retract_guard.py` remain compatibility/guard surfaces. |
| 2026-05-30 | Step 0 test inventory is complete enough for implementation. | Migration targets: `tests/test_application_entity_write.py`, `tests/test_emission_contract.py`, `tests/test_sdk_entities_create.py`, `tests/test_sdk_entities_delete.py`, `tests/test_sdk_entities_exists.py`, and SDK batch coverage in `tests/test_sdk_batch_application_delegate.py` / `tests/test_sdk_batch_primary_identity.py`. Guard/schema regression targets: `tests/test_application_retract_guard.py`, `tests/test_application_entity_write_retract_guard.py`, `tests/test_application_ingest_retract_guard.py`, `tests/test_sdk_retract_guard_integration.py`, `tests/test_application_schema_runtime_cache.py`, `tests/test_sdk_schema_three_split.py`, and `tests/test_sdk_assertions_namespace.py`. |
| 2026-05-30 | Batch implementation detail recorded for Step 3. | `sdk/batch.py` currently uses staged `RecordExistsOp` both as user-path `:exists` emission and as the application-delegation `create_if_missing` signal. Step 3 must stop new `RecordExistsOp` emission while preserving batch new-entity Identity-bundle creation through a non-wire/non-`RecordExistsOp` signal; `WireRecordExistsOp` and `PlannedOpDTO(op="record_exists")` parsing remain compatibility surfaces per N11. |
| 2026-05-30 | Rule/Q-PR1/shadow-store surfaces remain out of implementation scope. | Rule DSL/protocol/where planner `Entity:exists` hits are SF4 preserved virtual syntax; `core/derivation/accept.py` remains Q-PR1 no-touch; `_identity_values_by_e_ref` shadow-store behavior is not removed. |

## Review Checklist

Reviewer should verify before scope flip:

- [ ] Q-EXISTS §4.1-§4.10 are represented in Scope Freeze.
- [ ] Q-PR1 sacred paths remain no-touch.
- [ ] Shadow store removal is not accidentally included.
- [ ] Rule DSL `Entity:exists` virtual syntax is not accidentally included for deletion.
- [ ] Legacy `:exists` Claims are preserved/protected and no destructive migration is planned.
- [ ] Implementation steps are commit-boundary sized and include a Stage 4 test inventory before runtime edits.
