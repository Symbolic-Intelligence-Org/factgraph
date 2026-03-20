# Task Blueprint Audit: Engine Partial Witness — Audit/Static Surface

- Blueprint: [2026-03-20_engine-partial-witness-audit-static-surface.md](./2026-03-20_engine-partial-witness-audit-static-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Narrow audit/static witness-bearing parity scope recorded. |
| 2026-03-20 | scoped | Scope freeze completed | Freeze limited to query gate widening, DTO/static reuse, and docs sync. |
| 2026-03-20 | implemented | Query gate widened and docs/tests synced | `souffle_witness_v1` now round-trips through audit query, DTO, and static site without new shape branches. |

## Decision Notes

- `AuditQuery.get_candidate_evidence_tree(...)` is the only audit/static gate for `souffle_witness_v1`; `dto.py` and `static_ui.py` remain pure consumers.
- First-round change is `native_binding_v1` -> `_WITNESS_BEARING_SUPPORT_KINDS`; degraded handling remains unchanged.
- No new DTO fields or node shapes are introduced; `souffle_witness_v1` reuses the existing witness-bearing candidate tree contract.
- Module docs synced in `service/docs/03_runtime_queries_views.md` and `audit/docs/01_overview.md`; mother blueprint refreshed to record Souffle delivery-surface closure.
