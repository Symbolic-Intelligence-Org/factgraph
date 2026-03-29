# Task Blueprint Audit: replace_field Atomicity Fix

- Blueprint: [2026-03-29_replace-field-atomicity.md](./2026-03-29_replace-field-atomicity.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | F-CORE-1 fix scope recorded. |
| 2026-03-29 | scoped | Scope frozen | Preflight validation in replace_field only; no set_field/retract/ledger changes. |
| 2026-03-29 | implementing | write_protocol.py changes applied | User applied _preflight_new_assertion + replace_field restructure. |
| 2026-03-29 | implementing | Tests added | 3 new tests in test_write_protocol_annotations.py: invalid meta, invalid probability, valid regression. |
| 2026-03-29 | implementing | Docs synced | 01_architecture.md F-CORE-1 marked RESOLVED. |
| 2026-03-29 | implemented | Regression passed | 587 tests, 0 failures. |

## Decision Notes

- Use preflight validation pattern: run all set_field checks with sentinel values, discard results, then proceed with retract+set.
- Sentinel values `"_preflight_"` / `0` are never written to DB — only used for row construction validation.
- set_field re-runs the same validation (idempotent); no shortcut path needed.
