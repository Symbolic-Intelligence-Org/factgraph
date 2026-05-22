# Task Blueprint Audit: ECSS Requirement Authoring Surface

- Blueprint: [2026-03-18_ecss-requirement-authoring-surface.md](./2026-03-18_ecss-requirement-authoring-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the next Scenario B slice after confirming that explainability phase 1 and compliance-matrix delivery had both reached stable stopping points. |
| 2026-03-18 | scoped | Scope frozen | Chose requirement authoring / data-entry surface as the next implementation target, kept `offline-query-first` unchanged, and froze the first-round boundary as `SDK-first` rather than new live service delivery. |
| 2026-03-18 | implementing | Implementation started | Confirmed the shared-preset direction as a new narrow `factpy_kernel.ecss` module, chose a schema-dict-only SDK convenience wrapper, and began moving the canonical ECSS VCD preset out of `audit`. |
| 2026-03-18 | implemented | Shared preset and SDK helper landed | Added the new `factpy_kernel.ecss` module, kept `audit` on compatibility re-export, and introduced a thin `sdk.ecss` write-side convenience wrapper to complete the authoring loop. |
| 2026-03-18 | implemented | Docs and regression synced | Added `ecss/docs`, updated `audit` / `authoring` / `sdk` docs and `docs/README.md`, then ran `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` with `50 tests` passing. |
| 2026-03-18 | archived | Blueprint archived | Moved the blueprint/audit pair to `docs/blueprints/archive/` after outcome, docs, and regression verification were completed. |

## Decision Notes

- 2026-03-18: The next Scenario B slice should start from requirement authoring / data-entry surface, not from more delivery work or a new live endpoint.
- 2026-03-18: `audit` should remain a consumer layer; the canonical ECSS VCD schema preset cannot stay owned only by an audit-side helper if write-side code needs to depend on it.
- 2026-03-18: First-round authoring ergonomics should be `SDK-first`, while validation continues to use the existing `packages/export -> AuditQuery/static_ui` offline loop.
- 2026-03-18: A schema-only helper was not enough for a real write-side loop because the ECSS preset predicates do not have matching `Entity` descriptors; a narrow `sdk.ecss.write_ecss_requirement_bundle(...)` helper was added instead of trying to force them through generic `sdk.batch()` handles.
