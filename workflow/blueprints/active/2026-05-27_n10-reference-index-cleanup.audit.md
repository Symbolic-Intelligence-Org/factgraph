# Audit: N10 Reference Index Cleanup

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_n10-reference-index-cleanup.md`
- Stage: draft
- Class: S (docs-only top-level index rebase)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 4 modified + 1 untracked must be preserved
- Ownership: Claude single-actor (cross-flip inverted for S-scope filler per user authorization)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | (pending) | N10 blueprint pair drafted | Targets only top-level `docs/references/README.md`. Tier A scope per user authorization. |

## 2. Initial Read Summary

| Source | Observation |
|---|---|
| `docs/references/README.md` | 109 lines. Lines 16-18, 25 use pre-rename / pre-workflow paths (`src/factpy_kernel`, `docs/blueprints`, `docs/blueprint_history`, `docs/architecture_principles.md`). Line 28 anchor date is 2026-05-06. Lines 53-62 list per-note inline links under `working/design-points/` that no longer exist at the referenced path. |
| `workflow/design/design-points/` | Canonical home with `active/` (6 working notes incl. roadmap, parent essay, evidence v1, db-view, match-api, track-plan) and `archive/` (9 migrated notes incl. identity-primary-key, post-track3-semantics-public-api, rule-query-inference-head-semantics, read-write-snapshot-assertion-selection, etc.). README.md present. |
| `docs/references/working/design-points/` | Contains only `readme.md`; that file is in the preserved dirty baseline. The inline notes it lists do not exist on disk at the listed paths. |
| `docs/references/working/factgraph-namespace-test-proposals/README.md` | Present; bundle holds three SDK-namespace test-proposal markdowns + the corresponding Python test files. |
| Historical bundles | `working/load-test-2026-04-11/`, `working/rule-replay-line-redesign-input/`, `working/post-routemap-direction-selection-input/` — time-frozen, properly indexed, preserved verbatim. |

## 3. Draft Scope Decisions

| Decision | Rationale |
|---|---|
| Single-file Tier A scope | User-chosen scope. Avoids touching time-frozen historical bundles and the dirty-baseline `working/design-points/readme.md`. |
| Replace per-note inline listing with canonical pointer | The inline links currently point to non-existent files. Re-pointing them inline to `workflow/design/design-points/archive/<note>` is feasible but creates a confusing "directory at A contains notes at B" frame; a single canonical-location pointer is clearer. |
| Keep subsection header `#### working/design-points/ ——` | Avoid breaking any inbound anchor link; provide a breadcrumb for readers who land on the old path. |
| Refresh anchor date to "2026-05-27 N10 cleanup 后" | Make the listing's vintage explicit so future drift is easier to spot. |
| Leave historical-bundle path strings (`src/factpy_kernel`, `docs/blueprints/...`) untouched | These are time-frozen captures of the 2026-04-11 state; rewriting them would corrupt historical evidence. |

## 4. Step 4.6 Inventory Checklist

To fill during scoped commit:

| # | Item | Result |
|---|---|---|
| 1 | Exact line numbers in `docs/references/README.md` for each stale path | (to fill) |
| 2 | `workflow/design/design-points/` structure (active + archive + README) | (to fill) |
| 3 | `factgraph-namespace-test-proposals` bundle description | (to fill) |
| 4 | Dirty baseline verification | (to fill) |
| 5 | Sacred master verification | (to fill) |
| 6 | Inbound references to the about-to-change subsection anchors | (to fill) |

## 5. Verification Plan

- `git diff --check` after implementation.
- `git status --short --branch` after implementation; only the implementation-target file should be staged.
- `git rev-parse master` confirms `562c74195df43e933bed92a3ff25de94dd8ce666`.
- `rg -l 'src/factpy_kernel|docs/blueprints|docs/blueprint_history|docs/architecture_principles' docs/references/README.md` returns no matches after implementation (these strings appear only inside historical bundle sub-READMEs, not in the top-level file).
- `rg -l "docs/references/README.md#" .` to confirm no anchor links are broken by header text changes.

## 6. Review Checklist

- [ ] Step 4.2 draft review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Implementation diff matches scope.
- [ ] Verification clean.
- [ ] Closure notes filled.

## 7. Closure Notes

To fill at closure.
