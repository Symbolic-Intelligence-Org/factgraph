# Task Blueprint Audit: Slice 5 — Narrow `:exists` Co-Emission Removal

- Blueprint: [2026-05-30_exists-removal.md](./2026-05-30_exists-removal.md)
- Branch: `v0.2.0-blueprint-exists-removal-2026-05-30`
- Fork point: `870e1f1f` (Q-EXISTS adopted decision head)
- Status: draft audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from adopted Q-EXISTS decision `870e1f1f`; scope is narrow user-path `:exists` co-emission removal + Identity-bundle `fg.entities.exists`; Q-PR1, shadow store, rule DSL virtual syntax, legacy data migration, and guard-code rename are explicitly out of scope. |
| 2026-05-30 | draft-amend | Step 4.2 reviewer findings applied | Added file:line Evidence column to shipped-surface table, clarified Step 0 inventory output format, tightened Identity-bundle value matching wording, added optional audit close-time update, added §10.1 acceptance-count hint, and simplified SF7 cite wording. |
| 2026-05-30 | preflight-amend | Step 4.3 preflight findings applied | Added `src/factgraph/sdk/batch.py` to scope as a user-facing `record_exists` emission path; preserved wire/protocol `record_exists` compatibility; added Step 0 visibility-helper inventory and SDK batch tests per PF-R1/PF-REC1/PF-REC2. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork blueprint from Q-EXISTS adopted head `870e1f1f`. | The blueprint must cite Q-EXISTS §4.1-§4.10 as binding constraints, including amend/adopt changes from `e9d67214` and `870e1f1f`. |
| 2026-05-30 | Keep next slice narrow. | Stage 1 audit `bd3ab5c3` rejected repo-wide `:exists` deletion; Q-EXISTS locks user-path co-emission cleanup plus Identity-bundle existence semantics. |
| 2026-05-30 | Preserve Q-PR1 sacred paths. | Q-EXISTS §4.8 leaves derivation accept `:exists` writes as out-of-scope legacy/derived markers; any exception requires user authorization and blueprint amendment. |
| 2026-05-30 | Preserve `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` name. | Q-EXISTS §4.5 locks the current code name for legacy direct-retract protection to keep this slice narrow. |

## Review Checklist

Reviewer should verify before scope flip:

- [ ] Q-EXISTS §4.1-§4.10 are represented in Scope Freeze.
- [ ] Q-PR1 sacred paths remain no-touch.
- [ ] Shadow store removal is not accidentally included.
- [ ] Rule DSL `Entity:exists` virtual syntax is not accidentally included for deletion.
- [ ] Legacy `:exists` Claims are preserved/protected and no destructive migration is planned.
- [ ] Implementation steps are commit-boundary sized and include a Stage 4 test inventory before runtime edits.
