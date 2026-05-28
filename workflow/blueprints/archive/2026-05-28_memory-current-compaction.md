# Task Blueprint: Memory Current Compaction

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (housekeeping / docs-only memory compaction)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-28_memory-current-compaction.audit.md`
- Trigger: T8-D round 3 shipped at `c23ce097`, leaving the repo-local `workflow/memory/current.md` stale (`Published branch head` still `cde072fa`) and at 132 lines. This cycle compacts the committed repo-local memory handoff before the next large T10/T8 cycle.

## 0. Scope Locks

### In scope

This is a repo-local memory housekeeping cycle. It updates only
`workflow/memory/current.md`.

1. Source-backed inventory of current `workflow/memory/current.md` sections,
   line ranges, and content role.
2. Compaction strategy:
   - Keep essential operational anchors verbatim or near-verbatim.
   - Compress milestone-history tables into compact grouped bullets.
   - Delegate detailed history to archive inventory, changelog, and blueprint
     archives.
3. Stale-anchor repair:
   - Last updated line.
   - Published branch head.
   - Most recent work / shipped state.
   - Recommended next work.
4. Target final length decision. Draft target: 60-80 lines, to be confirmed in
   Step 4.6.

### Out of scope

- Runtime code.
- Tests.
- Governance/workflow rule changes.
- Sacred `master` changes.
- Dirty baseline changes. Current observed baseline remains `4 M + 1 D + 5 U`.
- Any file other than `workflow/memory/current.md`.
- Claude auto-memory `MEMORY.md`; it is outside repo and maintained by a
  different mechanism.
- Archive inventory / changelog / roadmap / blueprint archive edits.
- New design decisions, new cycle summaries, or new historical analysis beyond
  compacting and de-duplicating current memory.
- Changing `current.md`'s role: it remains operational memory + session
  handoff, not a full history ledger.

### Stop / amend triggers

Pause and amend if Step 4.6 shows:

1. `workflow/memory/current.md` contains historical information that is not
   recoverable from archive inventory, changelog, or blueprint archives.
2. Compaction requires changing the role or location of `current.md`.
3. Any file other than `workflow/memory/current.md` must be edited.
4. Runtime, tests, dirty baseline, or sacred `master` would be touched.

## 1. Problem

`workflow/memory/current.md` is only 132 lines, but it has started to grow by
copying milestone tables that already exist in archive inventory / changelog /
blueprints. The file also has stale operational anchors after T8-D round 3 was
pushed:

- Last-updated line still says the round 3 docs were local / pending push.
- Published branch head still says `cde072fa`.
- Current-state prose still frames ProbLog user docs as locally pending rather
  than pushed to `c23ce097`.

This cycle should reduce future churn by keeping `current.md` as a compact
handoff file: current branch/head, sacred and dirty anchors, current shipped
state, source-of-truth links, and next candidates.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/memory/current.md` | Sole implementation target. |
| `workflow/blueprints/archive/INVENTORY.md` | Source of truth for archived cycle history. |
| `CHANGELOG.md` | Release-facing shipped-state summary. |
| `workflow/blueprints/archive/2026-05-28_t8-d-round3-problog-user-docs.md` | Latest completed cycle anchor. |
| `workflow/blueprints/archive/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md` | Runtime behavior anchor for ProbLog row provenance. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 Current Sections Inventory

| Lines | Section | Role | Step 4.6 decision |
|---:|---|---|---|
| 1-3 | Title + last-updated anchor | Operational anchor | Keep, but refresh line 3 from "archived locally; pending push gate" to the current pushed state after `c23ce097`. |
| 5-18 | Current phase branch/head/work/sacred | Operational anchors | Keep near-verbatim. Line 9 must change from `cde072fa` to `c23ce097`; lines 11-15 should become a compact pushed-state sentence instead of local-pending prose. |
| 20-34 | Dirty baseline | Safety anchor | Keep full file list visible. Do not compress to only "4 M + 1 D + 5 U". |
| 36-52 | T5 published milestone table | Historical ledger | Compress to one grouped bullet and delegate details to archive inventory. |
| 54-69 | T11 / release-path table | Historical ledger + release gate reminder | Compress to one grouped bullet plus keep the live release / PyPI gate reminder. |
| 71-75 | Reference/docs housekeeping table | Historical ledger | Compress into the grouped history summary; no standalone table needed. |
| 77-94 | Evidence track table | Historical ledger | Compress into grouped evidence status with key heads only; detailed per-cycle summaries live in archive inventory lines 11-24 and changelog lines 15-75. |
| 96-105 | Evidence track current state | Shipped-state summary | Keep as compact bullets, but remove "locally and pending push"; ProbLog runtime and user docs are now pushed through `c23ce097`. |
| 107-120 | Recommended next work | Operational handoff | Keep, but remove stale "T8-D round 3 push gate" item and keep only post-`c23ce097` candidates. |
| 122-132 | Governance reminders | Operational safety reminders | Keep compact; preserve push/master/dirty-baseline reminders. |

### 3.2 Verbatim / Near-Verbatim Anchors

Must remain directly visible in `current.md`:

| Anchor | Current source | Implementation requirement |
|---|---:|---|
| Current branch | line 7 | Preserve exact branch name. |
| Published branch head | line 9 | Preserve as direct anchor, updated to `origin/... @ c23ce097`. |
| Sacred `master` | lines 17-18 | Preserve exact SHA `562c74195df43e933bed92a3ff25de94dd8ce666`. |
| Dirty baseline summary and full file list | lines 20-34 | Preserve all 10 entries and warning not to absorb them. |
| Shipped-state summary | lines 96-105 | Keep compact current truth: native/Souffle/ProbLog evidence lanes shipped; PyReason remains gated. |
| Recommended next work | lines 107-120 | Keep current candidate list, excluding already-completed push gate. |
| Governance reminders | lines 122-132 | Keep push/master/dirty-baseline reminders; may compress design-point lifecycle bullets. |

### 3.3 Compaction Surface

| Surface | Current lines | Decision |
|---|---:|---|
| T5 table | 38-52 | Replace 8-row table with one sentence: T5.1-T5.8 completed on the T5 branch; detailed slices are in archive inventory. |
| T11 table | 54-67 | Replace 10-row table with grouped release-path sentence naming T11.1/T11.2/T11.3 and keeping live release as a separate explicit gate. |
| N10 table | 71-75 | Fold into a housekeeping bullet. |
| Evidence track table | 77-94 | Replace 14-row table with grouped bullets: foundation/native/Souffle/ProbLog lanes shipped, inventories complete, PyReason/T10-2/T10-3 remain future. Keep key recent heads `cde072fa`, `5ffd4850`, and `c23ce097` for orientation. |
| Repeated verification details | 91-94 and archive/changelog overlap | Delete from `current.md`; archive inventory lines 11-14 and changelog lines 30-75 retain the detailed shipped-state and verification summaries. |
| Stale local-pending wording | lines 3, 11-15, 93-94, 103-105, 109-110 | Replace with pushed-state wording anchored to `c23ce097`. |

### 3.4 Cross-Reference Strategy

| Detail class | Source of truth | Source refs |
|---|---|---|
| Per-cycle archive summaries and commit chains | `workflow/blueprints/archive/INVENTORY.md` | Recent entries at lines 11-24 cover T8-D round 3, T8-C-1 runtime/inventory, T10-1, T10/T8-C inventories, T8-D round 2, T8-B/T8-A, and T7/T6. |
| Release-facing shipped-state summary | `CHANGELOG.md` | Unreleased Added/Changed/Deferred at lines 12-75 cover OR match, native/Souffle/ProbLog evidence, T10/T8-C planning, and future PyReason/aggregate/failed/match evidence tracks. |
| Latest user-doc cycle details | `workflow/blueprints/archive/2026-05-28_t8-d-round3-problog-user-docs.md` | Use only as a cross-reference target if needed; do not duplicate its review narrative. |
| Latest runtime cycle details | `workflow/blueprints/archive/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md` | Use only as a cross-reference target if needed; do not duplicate implementation/test details. |

### 3.5 Stale Anchor Repair List

| Current line(s) | Stale text / issue | Replacement decision |
|---:|---|---|
| 3 | Says T8-D round 3 is archived locally and pending push. | Update to "2026-05-28 (T8-D round 3 pushed; current memory compaction in progress)" or equivalent. |
| 9 | Published branch head `cde072fa`. | Update to `origin/v0.2.0-t11-1-attach-view-scope-2026-05-26 @ c23ce097`. |
| 11-15 | "Most recent local work" says round 3 was archived locally after review. | Replace with pushed-state summary: T8-D round 3 shipped to origin and user docs now align with ProbLog row provenance. |
| 93-94 | T8-C-1 runtime and T8-D round 3 heads listed as `pending push`. | Remove table rows through compaction; compact shipped-state summary should name `5ffd4850` and `c23ce097` as shipped. |
| 103-105 | ProbLog runtime/docs are "shipped locally and pending push". | Replace with pushed-state wording and keep PyReason gating. |
| 109-110 | Recommended next work is T8-D round 3 push gate. | Remove; next candidates begin with T10-2 / T8-C-2 / memory or dirty-baseline housekeeping. |

### 3.6 Target Length

Implementation target: `<= 80` lines, verified with:

```bash
wc -l workflow/memory/current.md
```

Expected implementation shape is roughly 65-75 lines: full dirty-baseline list
remains visible, while milestone tables are replaced by grouped bullets and
source-of-truth links.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which anchors must remain visible verbatim or near-verbatim? | List and rationale. |
| Q2 | Which sections should be compacted, and how? | Per-section table with keep/compress/delete decisions. |
| Q3 | Which cross-references replace detailed history? | Source-of-truth mapping. |
| Q4 | Which stale anchors need repair? | Exact line refs and replacement decisions. |
| Q5 | What final length target should the implementation meet? | Numeric line target and `wc -l` verification. |
| Q6 | Are any stop/amend triggers hit? | None or explicit trigger with next action. |

### Q1. Visible anchors

Keep current branch, published head, sacred master, full dirty-baseline list,
compact shipped-state summary, next candidates, and governance reminders.
Rationale: these are operational handoff facts a future agent needs before
choosing or executing a cycle.

### Q2. Compaction strategy

Compress the T5, T11, N10, and evidence milestone tables into grouped bullets.
Delete repeated per-cycle verification detail from `current.md` after verifying
the same details are recoverable from archive inventory and changelog. Preserve
enough recent heads for orientation: `cde072fa` (T10-1), `5ffd4850`
(T8-C-1 runtime), and `c23ce097` (T8-D round 3).

### Q3. Cross-references

Use `workflow/blueprints/archive/INVENTORY.md` as the detailed cycle ledger,
`CHANGELOG.md` as the release-facing shipped-state summary, and specific archive
blueprints only for the latest runtime/docs cycles when a reader needs the full
review chain.

### Q4. Stale anchors

Repair lines 3, 9, 11-15, 93-94, 103-105, and 109-110 as listed in §3.5.
The key required replacement is published branch head -> `c23ce097`.

### Q5. Target length

Target `<= 80` lines, with an expected implementation around 65-75 lines.
Verify with `wc -l workflow/memory/current.md`.

### Q6. Stop/amend assessment

No stop/amend trigger is hit. The detailed history to be compressed is covered
by archive inventory lines 11-24 and changelog lines 12-75; the cycle does not
need to change `current.md`'s role or edit any file besides
`workflow/memory/current.md`.

## 5. Existing Invariants To Preserve

- `workflow/memory/current.md` remains operational memory + session handoff.
- Immediate branch/head/sacred/dirty anchors stay easy to read.
- Dirty baseline file list remains complete.
- Historical cycle details remain recoverable from archive inventory, changelog,
  and blueprint archives.
- Claude auto-memory `MEMORY.md` is not touched.
- Sibling workflow files are not touched.
- No runtime, tests, governance, dirty-baseline, or sacred-master changes.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
nl -ba workflow/memory/current.md
wc -l workflow/memory/current.md
rg -n "Published branch head|pending push|Most recent local work|Recommended Next Work|Dirty baseline" workflow/memory/current.md
rg -n "t8-d-round3|t8-c-1-problog|T10-2|T8-C-2|ProbLog" workflow/blueprints/archive/INVENTORY.md CHANGELOG.md
```

Expected outputs:

1. Section inventory with line ranges.
2. Keep/compress/delete table.
3. Stale-anchor repair list.
4. Target line count.

## 7. Proposed Implementation Shape

Candidate split:

1. `docs(memory): compact current memory and refresh anchors`
2. `docs(blueprint): close memory current compaction`
3. `docs(blueprint): archive memory current compaction`

A single implementation commit is preferred because this is one-file
housekeeping. If Step 4.6 finds hidden source-of-truth gaps, stop instead of
rewriting history into `current.md`.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q6 answered.
- [x] Implementation touches only `workflow/memory/current.md`.
- [x] Stale anchors are repaired, including published head -> `c23ce097`.
- [x] Final line count meets the Step 4.6 target.
- [x] Dirty baseline full file list remains visible and complete.
- [x] Archive/changelog/blueprint source-of-truth links remain clear.
- [x] `git diff --check` clean.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Candidate checks:

```bash
wc -l workflow/memory/current.md
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Implemented as a single-file housekeeping slice.

Commit chain:

- Draft: `0af67764`
- Scoped: `95b2cdbb`
- Implementation: `eb7f5edb`
- Closure: this commit
- Archive: this commit

Outcome:

- `workflow/memory/current.md` was compacted from 132 lines to 80 lines,
  meeting the Step 4.6 hard target (`<= 80`).
- Six stale anchors were repaired: last-updated text, published branch head,
  most-recent-work wording, pending-push evidence rows, local-pending evidence
  state, and the recommended next-work push-gate item.
- Published branch head now points to `c23ce097`.
- The full `4 M + 1 D + 5 U` dirty-baseline file list remains visible.
- Long milestone tables were replaced by compact grouped bullets plus source
  links to `workflow/blueprints/archive/INVENTORY.md` and `CHANGELOG.md`.
- No runtime, tests, governance, sibling workflow files, auto-memory
  `MEMORY.md`, dirty-baseline files, or sacred `master` were touched.

Verification:

- `wc -l workflow/memory/current.md`: 80.
- Stale local-pending grep returned no matches.
- `git diff --check`: clean.
- `git status --short --branch`: expected dirty baseline preserved.
- `git rev-parse master`: `562c74195df43e933bed92a3ff25de94dd8ce666`.

Deviations / notes:

- The target reached the hard upper bound of 80 lines rather than the
  aspirational 65-75 range because the full dirty-baseline list is intentionally
  preserved.
- The governance reminder section replaced two detailed lifecycle reminders
  with one role reminder: archive inventory, changelog, and archived blueprint
  pairs are the historical source of truth; this file remains operational
  handoff only.
- Cross-references use stable file paths rather than line-number anchors to
  avoid future rot as archive inventory grows.
