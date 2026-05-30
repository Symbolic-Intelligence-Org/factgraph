# Task Blueprint Audit: Slice 6 — Form I Legacy Debt Cleanup

- Blueprint: [2026-05-30_form-i-debt-cleanup.md](./2026-05-30_form-i-debt-cleanup.md)
- Branch: `v0.2.0-blueprint-form-i-debt-2026-05-30`
- Fork point: `fb744d95` (Slice 6 Stage 1 audit head)
- Status: draft audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from Stage 1 audit `fb744d95`; Stage 2 Q-decision skipped per reviewer verdict because no new design decision is required. Scope is Form I legacy callsite cleanup for live tests, sibling package tests/docs, current docs/tools/tutorials, with dirty/archive/historical carve-outs inherited from Slice 4/5. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork blueprint from Stage 1 audit head `fb744d95`. | The audit is the binding input and already passed reviewer verification. |
| 2026-05-30 | Skip Stage 2 Q-decision. | Reviewer agreed the slice has no new design tension; dirty/archive/historical policies inherit from Slice 4/5. |
| 2026-05-30 | Keep Slice 6 housekeeping-only. | Runtime descriptor behavior already shipped; the slice migrates stale callsites and current docs without changing semantics. |
| 2026-05-30 | Negative tests require semantic rewrite. | Stage 1 FI-R5 showed primary-key/default/cardinality tests can become meaningless if mechanically substituted. |
| 2026-05-30 | Dirty notebooks remain protected. | Active dirty notebooks contain stale Form I but must not be overwritten without per-file user authorization. |
| 2026-05-30 | Historical/archive references remain classified carve-outs. | Global zero grep across historical material would erase useful decision/audit context and violate Slice 4/5 precedent. |

## Review Checklist

Reviewer should verify before scope flip:

- [ ] Stage 1 audit `fb744d95` findings are represented in goals, non-goals, scope freeze, acceptance, and implementation plan.
- [ ] Stage 2 skip rationale is explicit and defensible.
- [ ] Negative-test semantic rewrite is separated from positive fixture migration.
- [ ] Sibling package paths are explicitly in scope.
- [ ] Root `README.md` stale current truth is explicitly in scope.
- [ ] Dirty notebook and archive/historical locks are explicit.
- [ ] Q-PR1 sacred paths remain no-touch.
- [ ] Implementation steps are commit-boundary sized.
