# Task Blueprint: T11.2.5 Dirty Baseline Triage

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: S/M (predicted verdict-only release prerequisite)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t11-2-5-dirty-baseline-triage.audit.md`
- Roadmap source: `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` §7.3 open question: dirty baseline should be triaged before T11.3 release machinery

## 0. Scope Locks

### In scope

T11.2.5 is a release-path prerequisite between T11.2 and T11.3. It classifies
the existing dirty baseline so T11.3 release machinery can treat the tree as a
known state rather than discovering ownership-sensitive changes for the first
time.

The seven inputs are:

1. `docs/references/working/design-points/readme.md`
2. `examples/01_sdk_check_diagnose.ipynb`
3. `examples/02_overlay_why_not_frontier.ipynb`
4. `examples/archive/01_sdk_basics.ipynb`
5. `src/factgraph/sdk/facade.py`
6. `tests/test_sdk_assertion_record_set_view_filters.py`
7. `rainbird-ai sdk code/`

For each item, produce one verdict:

| Verdict | Meaning |
|---|---|
| Include as own behavior slice | Needs a dedicated blueprint before release, usually because it changes SDK behavior or tests. |
| Defer as notebook/docs cleanup | Not release-blocking for T11.3; should be handled later in a docs/example polish cycle. |
| Ignore / untracked reference | Leave as-is for now; explicitly keep out of release projection and out of accidental adds. |
| Revert only on explicit user request | Do not revert in this cycle; user must separately authorize if they want it removed. |
| Quick fix in this cycle | Optional only if an item is a tiny, obvious mistake and fixing it does not touch production behavior or user-owned work. |

### Out of scope

- Release machinery changes (`release.sh`, allowlist, README, CHANGELOG, CI, version, tags).
- Production behavior changes.
- Notebook execution / rewrite.
- Reverting dirty files without explicit user request.
- Adding `rainbird-ai sdk code/` or any external reference tree to git.
- Editing external/global memory files.
- Push; push requires a separate single-use authorization.

### Stop / amend triggers

Pause and amend if triage shows:

- `facade.py` change is required for release and cannot be separated cleanly;
- a notebook/example dirty file is already part of the release projection and must be fixed before T11.3;
- `rainbird-ai sdk code/` has licensing/provenance obligations that require immediate action;
- any verdict would require modifying production code, tests, notebooks, or external files rather than merely classifying them;
- dirty baseline changes while this cycle is running.

## 1. Problem

T11.3 release machinery cannot dry-run with tracked dirty files:
`scripts/release.sh` explicitly fails if tracked unstaged or staged changes
exist. The current dirty baseline includes production SDK code, tests, examples,
reference docs, and an untracked external SDK directory.

Bundling first-time ownership decisions into T11.3 would make release machinery
too broad. T11.2.5 records the release-facing disposition of each dirty item so
T11.3 can verify that no unclassified dirty baseline remains.

## 2. Inputs

| Source | Purpose |
|---|---|
| Laplace read-only audit | Pre-draft inventory of dirty baseline, release machinery, and v0.1 release traps. |
| `git status --short --branch` | Authoritative dirty set. |
| `git diff --stat -- <dirty files>` | Size/type of tracked dirty changes. |
| `scripts/release.sh` | Confirms tracked dirty files block release dry-run. |
| `scripts/project_release_surface.sh` | Confirms release projection deny/allow behavior for refs/examples. |
| `pyproject.toml`, `README.md`, `CHANGELOG.md`, `.github/workflows/factpy-kernel-tests.yml` | T11.3 release machinery context, not implementation scope. |

## 3. Preliminary Inventory

Laplace returned the following read-only findings:

| Path | Finding | Draft expectation |
|---|---|---|
| `docs/references/working/design-points/readme.md` | `+2`; links to missing reference notes; denied from release projection. | Defer or ignore unless target notes are restored. |
| `examples/01_sdk_check_diagnose.ipynb` | Notebook output/metadata; contains `ModuleNotFoundError: No module named 'kernel'`. | Defer notebook cleanup; not part of release projection today. |
| `examples/02_overlay_why_not_frontier.ipynb` | Partial `kernel` -> `factgraph` modernization; bottom summary still says `kernel.*`. | Defer until full example migration cycle. |
| `examples/archive/01_sdk_basics.ipynb` | Archived notebook with execution/output drift and `kernel` import failure. | Ignore for release or defer archive hygiene. |
| `src/factgraph/sdk/facade.py` | Public SDK behavior change: property-style assertion access with callable `AssertionRecordSet` compatibility. | Likely include as dedicated behavior slice with docs/tests. |
| `tests/test_sdk_assertion_record_set_view_filters.py` | Companion compatibility test for `facade.py`. | Keep paired with `facade.py`; not standalone. |
| `rainbird-ai sdk code/` | Untracked Go + Vite external SDK/demo tree with `.DS_Store`. | Ignore/untracked reference unless a future provenance/license review adopts it. |

Release machinery context from the same audit:

- `scripts/release.sh` requires clean tracked tree.
- v0.2 release machinery needs its own L-class work for `src/kernel` ->
  `src/factgraph`, allowlist, README, CHANGELOG, CI, version, projection tests,
  release branch, and tag.
- T11.2.5 should not start those repairs.

## 4. Proposed Shape

### 4.1 Step 4.6 Inventory

Before implementation, record:

1. exact dirty set and diff sizes;
2. whether any dirty file is in release projection allowlist/denylist;
3. whether each dirty tracked file is production, test, docs, example, or archive material;
4. likely owner/provenance where inferable;
5. final verdict for each of seven inputs;
6. follow-up cycle names and predicted class for any non-ignore verdict;
7. T11.3 handoff rule: release machinery must verify no unclassified dirty file remains.

### 4.2 Implementation

The implementation is mostly the triage record itself:

- fill the audit verdict table;
- optionally add a compact handoff note to `workflow/memory/current.md` if useful;
- do not modify the dirty files being classified.

If the user explicitly asks for a quick fix during this cycle, record it as an
amendment before changing any dirty file.

## 5. Expected Output

Expected docs-only files:

- this blueprint pair;
- possibly `workflow/memory/current.md` with a short T11.2.5 handoff;
- maybe `workflow/blueprints/archive/INVENTORY.md` when the blueprint archives.

Expected follow-up candidates:

- **SDK assertion property access behavior slice** for `facade.py` +
  `tests/test_sdk_assertion_record_set_view_filters.py`, if accepted.
- **Notebook/example namespace cleanup** for current and archived examples.
- **Rainbird reference provenance review** only if user wants to retain the
  external SDK reference tree in-repo.

## 6. Verification

- `git status --short --branch` before and after: dirty baseline remains the
  same unless an explicit amend authorizes a quick fix.
- `git diff --check` clean.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- No release machinery files touched.
- No production/test/notebook dirty file modified.
- T11.3 handoff sentence exists in outcome or memory: "dirty baseline triaged;
  T11.3 only verifies no unclassified dirty remains."

## 7. Acceptance

- [ ] All seven dirty baseline items have verdicts and short rationales.
- [ ] Follow-up cycles are named for any include/defer verdict.
- [ ] `rainbird-ai sdk code/` has an explicit ignore/provenance decision.
- [ ] T11.3 handoff rule is recorded.
- [ ] Dirty baseline preserved unless explicitly amended.
- [ ] No release machinery changes.
- [ ] No push without separate authorization.

