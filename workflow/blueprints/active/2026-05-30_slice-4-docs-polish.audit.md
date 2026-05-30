# Task Blueprint Audit: Slice 4 — Docs Polish for Form I / Identity-as-Claim / API Namespace

- Blueprint: [2026-05-30_slice-4-docs-polish.md](./2026-05-30_slice-4-docs-polish.md)
- Branch: `v0.2.0-blueprint-slice-4-docs-polish-2026-05-30`
- Fork point: `722595ba`(Slice 3a archive head plus N1 ingest docstring fix)
- Status: draft audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from Stage 1 audit `1012c6e4`; OQ1-OQ5 locked; D1-D10 in scope; D11-D12 represented as scope-freeze rules; strict cadence branch separation restored after Slice 3a V1 deviation. |
| 2026-05-30 | draft-amend | Step 4.2 reviewer findings applied | Added `src/factgraph/sdk/docs/README.md` and `explanation-completion-roadmap.zh.md` to scope; broadened final grep carve-out wording; clarified dirty-notebook default and per-commit ritual. |
| 2026-05-30 | preflight-amend | Step 4.3 preflight findings applied | Applied PF-R1 broad `Identity(...primary_key...)` gate and PF-R2 Step 0 added-target checks before scoped transition. |
| 2026-05-30 | scoped | Preflight amendments and self-check passed | PF-R1 and PF-R2 covered by `16907310`; self-check found no remaining blockers; Status flipped to `scoped`. |
| 2026-05-30 | implementing-step-1 | Step 0 grep gate + Step 1 quickstart rewrite | Step 0 found no new drift beyond scoped inventory; Step 1 rewrote `first-factgraph.md` and `read-write.md` to Form I + canonical `fg.entities.*` / `fg.fields.*` / `fg.assertions.*`. |
| 2026-05-30 | implementing-step-2 | Step 2 quickstart rewrite | Rewrote `assertions.md` for `AssertionView`, canonical `_meta`, and `fg.assertions.retract`; rewrote `schema.md` for Form I and `fg.schema.register/extend/apply`. |
| 2026-05-30 | implementing-step-3 | Step 3 mechanical quickstart migration | Migrated `namespace-map.md`, `evidence.md`, `database.md`, `persistence.md`, `rules-and-inferences.md`, and `semantics.md`; stale API/Form-I grep is clean and 4 complete examples pass. |
| 2026-05-30 | implementing-step-4 | Active examples migration(non-dirty) | Migrated `05_sdk_assertion_views.ipynb`, `03_proofframe_rule_overlays.ipynb`, `04_round_persistence_diff.ipynb`, and `round_story_full_demo.py` to Form I + `factgraph.*` imports + canonical assertion/entity APIs; dirty notebooks intentionally untouched. |
| 2026-05-30 | implementing-step-5 | Dirty notebook decision point | Defaulted to untouched per SF3: active dirty notebooks `01_sdk_check_diagnose.ipynb` and `02_overlay_why_not_frontier.ipynb` were not edited; archive dirty notebook remains out of scope per SF4. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork Slice 4 blueprint from `722595ba`, not `33090323`. | `722595ba` includes the N1 ingest docstring fix, so Slice 4 does not rediscover a closed audit item; Slice 3a archive head `33090323` remains an ancestor. |
| 2026-05-30 | Skip Stage 2 ADR / Q-resolution. | Slice 4 is documentation drift cleanup against shipped Slice 1/2/3a behavior; no unresolved design decision was surfaced by the Stage 1 audit. |
| 2026-05-30 | Scope D1-D10 only. | Required findings D1-D7 plus Recommended findings D8-D10 form the docs polish slice; D11-D12 become scope-freeze rules, and D15 remains out of scope. |
| 2026-05-30 | Preserve dirty notebooks unless explicitly authorized per file. | Slice 3a dirty-notebook guard remains in force; active dirty notebooks require per-file diff review and user authorization before edit. |
| 2026-05-30 | Use hybrid docs implementation strategy. | Four high-density quickstarts need section-level rewrite; lower-density files should receive mechanical or local migrations to reduce unnecessary churn. |
| 2026-05-30 | Add `src/factgraph/sdk/docs/README.md` after Step 4.2 review. | Reviewer found live `fg.read.*` / `fg.write.*` current-truth examples missed by Stage 1 D7 grep; this is a Required-bucket scope gap for Slice 4. |
| 2026-05-30 | Add `explanation-completion-roadmap.zh.md` with narrow current-API scope. | Reviewer found current/deferred API table references to `fg.read.match(...)`; Slice 4 should update namespace naming without changing deferred-roadmap semantics. |
| 2026-05-30 | PF-R1: broaden Form I legacy detection to `Identity(...primary_key...)`. | The invariant is removal of the `primary_key` argument, not only the `primary_key=True` spelling; Step 0 and Step 9 must use `Identity\([^)]*primary_key`. |
| 2026-05-30 | PF-R2: Step 0 includes Step 4.2 added-target checks. | Stage 1 grep missed `src/factgraph/sdk/docs/README.md` and under-reported `explanation-completion-roadmap.zh.md`; implementation preflight must explicitly include both. |

## Review Checklist

Reviewer should verify before scope flip:

- [ ] OQ1-OQ5 are represented in Scope Freeze.
- [ ] D1-D10 are in scope and D11-D12 are not accidentally converted into implementation work.
- [ ] Dirty notebook guard is explicit enough to prevent accidental overwrite.
- [ ] Implementation steps are commit-boundary sized and follow the Stage 1 audit phase order.
- [ ] Q-PR1 sacred paths and sacred branches are explicitly preserved.
