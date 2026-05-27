# Task Blueprint: Memory Current Compaction

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (housekeeping / docs-only memory compaction)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_memory-current-compaction.audit.md`
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

Pending Step 4.6. Required subsections:

### 3.1 Current Sections Inventory

List current `workflow/memory/current.md` sections by line range and role:

- Operational anchors.
- Dirty baseline.
- Published milestone history.
- Current evidence shipped state.
- Recommended next work.
- Governance reminders.

### 3.2 Verbatim / Near-Verbatim Anchors

Decide which anchors must remain directly visible:

- Current branch.
- Published branch head.
- Sacred `master`.
- Dirty baseline full file list.
- One compact shipped-state summary.
- Recommended next work.
- Governance reminders.

### 3.3 Compaction Surface

Decide how to compact:

- Replace long milestone tables with grouped bullets and source-of-truth links.
- Remove stale local/pending-push statements after `c23ce097`.
- Keep enough cycle names / heads for immediate orientation without duplicating
  archive inventory.

### 3.4 Cross-Reference Strategy

Specify which details are delegated to:

- `workflow/blueprints/archive/INVENTORY.md`
- `CHANGELOG.md`
- Specific latest archive blueprints as needed

### 3.5 Stale Anchor Repair List

Source-back exact stale anchors:

- Last-updated line.
- Published branch head.
- Most recent local work.
- Evidence track current state.
- Recommended next work.

### 3.6 Target Length

Confirm target line count and verification method. Draft target: 60-80 lines,
validated with `wc -l workflow/memory/current.md`.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which anchors must remain visible verbatim or near-verbatim? | List and rationale. |
| Q2 | Which sections should be compacted, and how? | Per-section table with keep/compress/delete decisions. |
| Q3 | Which cross-references replace detailed history? | Source-of-truth mapping. |
| Q4 | Which stale anchors need repair? | Exact line refs and replacement decisions. |
| Q5 | What final length target should the implementation meet? | Numeric line target and `wc -l` verification. |
| Q6 | Are any stop/amend triggers hit? | None or explicit trigger with next action. |

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

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q6 answered.
- [ ] Implementation touches only `workflow/memory/current.md`.
- [ ] Stale anchors are repaired, including published head -> `c23ce097`.
- [ ] Final line count meets the Step 4.6 target.
- [ ] Dirty baseline full file list remains visible and complete.
- [ ] Archive/changelog/blueprint source-of-truth links remain clear.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Candidate checks:

```bash
wc -l workflow/memory/current.md
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
