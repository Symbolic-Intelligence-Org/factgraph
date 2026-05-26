# Audit: T11.2.5 Dirty Baseline Triage

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-5-dirty-baseline-triage.md`
- Stage: scoped
- Class: S/M (predicted verdict-only release prerequisite)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked must be classified, not accidentally changed
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `f0174d4e` | T11.2.5 blueprint pair drafted | Triggered by T11.3 release prerequisite and Laplace read-only audit. |
| 2026-05-26 | scoped | TBD | Step 4.6 dirty baseline inventory recorded | Final verdicts assigned for all seven dirty baseline entries; no dirty file edited. |

## 2. Read-only Audit Summary

Laplace completed a read-only audit before drafting. No files were edited.

Key findings:

- `scripts/release.sh` requires a clean tracked tree, so tracked dirty files
  block release dry-run.
- The dirty set mixes SDK behavior, tests, notebooks, references, and an
  external SDK tree; a single blanket action would be unsafe.
- T11.3 already has substantial release machinery work, so dirty ownership
  decisions should happen first.

## 3. Dirty Baseline Inputs

| # | Path | Draft classification target |
|---|---|---|
| 1 | `docs/references/working/design-points/readme.md` | Reference docs / broken-link risk. |
| 2 | `examples/01_sdk_check_diagnose.ipynb` | Notebook cleanup candidate. |
| 3 | `examples/02_overlay_why_not_frontier.ipynb` | Notebook cleanup candidate. |
| 4 | `examples/archive/01_sdk_basics.ipynb` | Archive hygiene candidate. |
| 5 | `src/factgraph/sdk/facade.py` | Public SDK behavior candidate. |
| 6 | `tests/test_sdk_assertion_record_set_view_filters.py` | Companion test candidate. |
| 7 | `rainbird-ai sdk code/` | Untracked external reference candidate. |

## 4. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Current dirty status | `git status --short --branch` shows 6 tracked modified files plus untracked `rainbird-ai sdk code/`; branch is one commit ahead from draft only. |
| 2 | Diff size/type per tracked dirty file | `git diff --stat` shows 209 insertions / 68 deletions: references README `+2`; notebooks `+39/-19`, `+88/-33`, `+48/-14`; SDK production `facade.py +17/-2`; companion test `+15`. |
| 3 | Release projection inclusion/denial per dirty item | `scripts/project_release_surface.sh` denies `docs/references/*`, `examples/*`, and `scripts/*`; exact dirty paths are not allowlisted. Production `src/factgraph/sdk/facade.py` is package code and must be resolved before release. Tests are not release package payload but tracked dirty tests still block `scripts/release.sh`. |
| 4 | `facade.py` behavior summary and companion test status | `AssertionRecordSet.__call__` preserves legacy call form; `FieldAssertions.active/history/all` become property-style accessors; `AssertionNamespace.__getattr__` exposes field assertions by field name. Companion test asserts property and call compatibility. This is public SDK behavior and needs a dedicated behavior slice. |
| 5 | Notebook/example import/output status | `examples/01_sdk_check_diagnose.ipynb` and `examples/archive/01_sdk_basics.ipynb` contain `ModuleNotFoundError: No module named 'kernel'`; `examples/02_overlay_why_not_frontier.ipynb` imports `factgraph` but still documents `kernel.*` boundaries. All are notebook cleanup, not release machinery. |
| 6 | Untracked Rainbird tree size/provenance risk | `rainbird-ai sdk code/` is 536K / 71 files, containing Go SDK and Vite demo material plus `.DS_Store`. It remains untracked; do not add or `.gitignore` in this cycle. Optional future provenance/license review may decide retention. |
| 7 | Verdict per dirty item | Final verdict table recorded in §4.1 below. |
| 8 | Follow-up cycle names/class predictions | `T11.2.6 SDK assertion property access` (S/M behavior slice); `T11.x notebook namespace cleanup` (M docs/examples); `Rainbird reference provenance review` (S/M docs/legal-provenance, optional). |
| 9 | T11.3 handoff rule | T11.3 may rely on the classification and should not re-decide ownership. Before running release dry-runs, tracked dirty files must be landed in follow-up cycles or explicitly stashed/reverted by the user because `scripts/release.sh` requires a clean tracked tree. |
| 10 | Dirty baseline preservation check | Scoped commit edits only blueprint/audit files. The 6 M + 1 U dirty baseline remains unchanged. |

### 4.1 Final Verdict Table

| Path | Verdict | Rationale |
|---|---|---|
| `docs/references/working/design-points/readme.md` | Defer as docs cleanup | Adds two links to missing reference notes; `docs/references/*` is denied from release projection, so this is not T11.3 release machinery work. |
| `examples/01_sdk_check_diagnose.ipynb` | Defer as notebook/docs cleanup | Dirty notebook still contains `kernel.*` imports and `ModuleNotFoundError`; should be cleaned in a notebook namespace/output cycle, not during release machinery. |
| `examples/02_overlay_why_not_frontier.ipynb` | Defer as notebook/docs cleanup | Partially modernized to `factgraph` but retains stale `kernel.*` summary text; needs full notebook sweep to avoid half-migration. |
| `examples/archive/01_sdk_basics.ipynb` | Ignore for release / defer archive hygiene | Archived notebook with stale `kernel` import failure; not release-facing unless archive hygiene is explicitly activated. |
| `src/factgraph/sdk/facade.py` | Include as own behavior slice | Changes public assertion access behavior; should be reviewed, tested, and documented as an SDK behavior slice before release. |
| `tests/test_sdk_assertion_record_set_view_filters.py` | Include with `facade.py` behavior slice | Companion focused test belongs with the `facade.py` behavior change and should not be committed separately. |
| `rainbird-ai sdk code/` | Ignore / untracked reference | External Go/Vite reference tree remains untracked; no `.gitignore` change in T11.2.5. Future provenance/license review may decide whether to retain or remove. |

## 5. Verification Plan

- `git status --short --branch`.
- `git diff --stat -- <tracked dirty paths>`.
- `git diff --check`.
- `git rev-parse master`.
- `rg` release projection allow/deny references for examples/docs/reference paths.
- Check T11.3 handoff text in blueprint/audit: `dirty baseline` + `release dry-runs`.
- If no dirty files are changed, no tests are required.

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Seven verdicts recorded.
- [x] Follow-up cycles named.
- [x] Dirty baseline preservation verified.
- [ ] Closure notes filled.
