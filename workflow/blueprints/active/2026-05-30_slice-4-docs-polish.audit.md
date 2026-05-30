# Task Blueprint Audit: Slice 4 — Docs Polish for Form I / Identity-as-Claim / API Namespace

- Blueprint: [2026-05-30_slice-4-docs-polish.md](./2026-05-30_slice-4-docs-polish.md)
- Branch: `v0.2.0-blueprint-slice-4-docs-polish-2026-05-30`
- Fork point: `722595ba`(Slice 3a archive head plus N1 ingest docstring fix)
- Status: draft audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from Stage 1 audit `1012c6e4`; OQ1-OQ5 locked; D1-D10 in scope; D11-D12 represented as scope-freeze rules; strict cadence branch separation restored after Slice 3a V1 deviation. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork Slice 4 blueprint from `722595ba`, not `33090323`. | `722595ba` includes the N1 ingest docstring fix, so Slice 4 does not rediscover a closed audit item; Slice 3a archive head `33090323` remains an ancestor. |
| 2026-05-30 | Skip Stage 2 ADR / Q-resolution. | Slice 4 is documentation drift cleanup against shipped Slice 1/2/3a behavior; no unresolved design decision was surfaced by the Stage 1 audit. |
| 2026-05-30 | Scope D1-D10 only. | Required findings D1-D7 plus Recommended findings D8-D10 form the docs polish slice; D11-D12 become scope-freeze rules, and D15 remains out of scope. |
| 2026-05-30 | Preserve dirty notebooks unless explicitly authorized per file. | Slice 3a dirty-notebook guard remains in force; active dirty notebooks require per-file diff review and user authorization before edit. |
| 2026-05-30 | Use hybrid docs implementation strategy. | Four high-density quickstarts need section-level rewrite; lower-density files should receive mechanical or local migrations to reduce unnecessary churn. |

## Review Checklist

Reviewer should verify before scope flip:

- [ ] OQ1-OQ5 are represented in Scope Freeze.
- [ ] D1-D10 are in scope and D11-D12 are not accidentally converted into implementation work.
- [ ] Dirty notebook guard is explicit enough to prevent accidental overwrite.
- [ ] Implementation steps are commit-boundary sized and follow the Stage 1 audit phase order.
- [ ] Q-PR1 sacred paths and sacred branches are explicitly preserved.
