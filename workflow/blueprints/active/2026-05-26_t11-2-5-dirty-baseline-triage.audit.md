# Audit: T11.2.5 Dirty Baseline Triage

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-5-dirty-baseline-triage.md`
- Stage: draft
- Class: S/M (predicted verdict-only release prerequisite)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked must be classified, not accidentally changed
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | TBD | T11.2.5 blueprint pair drafted | Triggered by T11.3 release prerequisite and Laplace read-only audit. |

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

## 4. Step 4.6 Inventory Checklist

To fill during scoped inventory:

| # | Item | Result |
|---|---|---|
| 1 | Current dirty status | TBD |
| 2 | Diff size/type per tracked dirty file | TBD |
| 3 | Release projection inclusion/denial per dirty item | TBD |
| 4 | `facade.py` behavior summary and companion test status | TBD |
| 5 | Notebook/example import/output status | TBD |
| 6 | Untracked Rainbird tree size/provenance risk | TBD |
| 7 | Verdict per dirty item | TBD |
| 8 | Follow-up cycle names/class predictions | TBD |
| 9 | T11.3 handoff rule | TBD |
| 10 | Dirty baseline preservation check | TBD |

## 5. Verification Plan

- `git status --short --branch`.
- `git diff --stat -- <tracked dirty paths>`.
- `git diff --check`.
- `git rev-parse master`.
- `rg` release projection allow/deny references for examples/docs/reference paths.
- If no dirty files are changed, no tests are required.

## 6. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Seven verdicts recorded.
- [ ] Follow-up cycles named.
- [ ] Dirty baseline preservation verified.
- [ ] Closure notes filled.

