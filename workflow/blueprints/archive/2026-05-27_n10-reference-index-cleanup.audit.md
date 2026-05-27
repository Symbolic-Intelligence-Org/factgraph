# Audit: N10 Reference Index Cleanup

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_n10-reference-index-cleanup.md`
- Stage: implemented
- Class: S (docs-only top-level index rebase)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 4 modified + 1 untracked must be preserved
- Ownership: Claude single-actor (cross-flip inverted for S-scope filler per user authorization)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `e5570dfb` | N10 blueprint pair drafted | Targets only top-level `docs/references/README.md`. Tier A scope per user authorization. |
| 2026-05-27 | scoped | `ef63ebcb` | Step 4.6 inventory filled, scope frozen | Stale lines 16/17/18/25; design-points content migrated to `workflow/design/design-points/{active,archive}/`; `factgraph-namespace-test-proposals` description captured; no inbound anchor references found. |
| 2026-05-27 | scoped (amend) | `a4c7de15` | Scope amended to index a second missing `working/` bundle | Pre-implementation re-read of full README found `working/post-routemap-direction-selection-input/` also unindexed; same class as `factgraph-namespace-test-proposals/`; both included for symmetry rather than leaving an immediate follow-up cycle. Class stays S. |
| 2026-05-27 | implemented | `06ada1b2` | `docs/references/README.md` rebased | Governance lines 16-18, 25 rebased; design-points subsection points to `workflow/design/design-points/{active,archive}/`; two new working/ bundle subsections added (post-routemap + factgraph-namespace-tests); anchor date refreshed; brittle count claim softened. |

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
| 1 | Exact line numbers in `docs/references/README.md` for each stale path | Line 16 `src/factpy_kernel/*/docs/`; line 17 `docs/blueprints/`; line 18 `docs/blueprint_history/` + `docs/blueprints/archive/`; line 25 `docs/architecture_principles.md`; line 28 anchor date `2026-05-06`. |
| 2 | `workflow/design/design-points/` structure (active + archive + README) | README present; `active/` 6 notes; `archive/` 9 migrated notes (incl. all four currently listed inline in the README plus five additional notes). |
| 3 | `factgraph-namespace-test-proposals` bundle description | Review packet for 2026-05-14 namespace-test-coverage blueprint; not part of root `tests/`, not discovered by unittest, not release-gate truth. |
| 4 | Dirty baseline verification | 4 M + 1 U. Confirmed preserved. |
| 5 | Sacred master verification | `562c74195df43e933bed92a3ff25de94dd8ce666`. Confirmed. |
| 6 | Inbound references to the about-to-change subsection anchors | None outside the N10 blueprint pair itself (`rg -l 'docs/references/README.md#' . --type md`). |

## 5. Verification Plan

- `git diff --check` after implementation.
- `git status --short --branch` after implementation; only the implementation-target file should be staged.
- `git rev-parse master` confirms `562c74195df43e933bed92a3ff25de94dd8ce666`.
- `rg -l 'src/factpy_kernel|docs/blueprints|docs/blueprint_history|docs/architecture_principles' docs/references/README.md` returns no matches after implementation (these strings appear only inside historical bundle sub-READMEs, not in the top-level file).
- `rg -l "docs/references/README.md#" .` to confirm no anchor links are broken by header text changes.

## 6. Review Checklist

- [x] Step 4.2 draft review complete.
- [x] Step 4.6 inventory complete.
- [x] Implementation diff matches scope.
- [x] Verification clean.
- [x] Closure notes filled.

## 7. Closure Notes

Implemented at `06ada1b2`. Cycle chain: draft `e5570dfb` → scoped `ef63ebcb` → scope amend `a4c7de15` → impl `06ada1b2` → closure (this commit) → archive (next commit).

### 7.1 Landed scope

- Single-file edit: `docs/references/README.md`.
- Governance lines 16-18, 25 rebased to current canonical workflow paths.
- Design-points subsection replaced inline per-note listing with canonical pointer to `workflow/design/design-points/{active,archive}/`; subsection header retained as breadcrumb.
- Two unindexed `working/` bundles indexed: `post-routemap-direction-selection-input/` (2026-05-07, A+B input) and `factgraph-namespace-test-proposals/` (2026-05-14, namespace tests).
- Anchor date refreshed to "2026-05-27 N10 cleanup 后"; brittle "全 56 个文件" claim softened.

### 7.2 Disposition

- No P0/P1 blockers found.
- One scope amend at Step 4.6 re-read (second unindexed bundle); recorded and incorporated symmetrically.
- No production Python / tests / examples / notebooks / SDK / service / agent / adapter changes.
- Historical bundle sub-READMEs (load-test-2026-04-11/, etc.) preserved verbatim per scope lock.
- Dirty-baseline `docs/references/working/design-points/readme.md` left untouched per scope lock; it remains a non-authoritative breadcrumb pointing at pre-migration paths. A separate cycle that owns the dirty baseline can later normalize it.

### 7.3 Verification

- `git diff --check`: clean.
- Sacred `master` unchanged at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline preserved at 4 modified + 1 untracked.
- All inline links in the modified + new subsections resolve to existing files.
- `grep -n 'src/factpy_kernel|docs/blueprints/|docs/blueprint_history|docs/architecture_principles' docs/references/README.md` returns no matches.

### 7.4 Follow-ups

- O-N10-1: `docs/references/working/design-points/readme.md` (dirty baseline) still lists migrated note files at non-existent local paths. When that file moves out of dirty-baseline status, a follow-up should either delete its inline list or rewrite each link to its `workflow/design/design-points/archive/` destination.
- O-N10-2: Historical bundle sub-READMEs (e.g. `working/load-test-2026-04-11/README.md`, `commit_path_plan_2026-04-11.md`) still reference `src/factpy_kernel/...` and `docs/blueprints/...` paths. These are time-frozen historical artifacts and are explicitly out of scope for N10. If a future cleanup batch decides historical bundles should be promoted to `bridges/`, that batch can also decide whether to add a top-of-bundle "paths reflect 2026-04-11 state" note.
