# Audit: Memory Current Compaction

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_memory-current-compaction.md`
- Stage: scoped
- Class: S (housekeeping / docs-only memory compaction)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `0af67764` | Memory current compaction blueprint pair drafted | Triggered after T8-D round 3 `c23ce097`; Q1-Q6 pending Step 4.6. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed inventory completed | Target implementation: single-file `workflow/memory/current.md` compaction to <=80 lines, published head refreshed to `c23ce097`, dirty list preserved. |

## 2. Draft Source Scan

Read-only orientation findings:

- `workflow/memory/current.md` is currently 132 lines.
- It still says published branch head is `cde072fa`, while the working branch
  has shipped through `c23ce097`.
- It repeats detailed milestone tables that are better owned by archive
  inventory / changelog / blueprint archives.
- Dirty baseline currently appears as `4 M + 1 D + 5 U` and must remain visible.
- Claude auto-memory `MEMORY.md` is a separate non-repo surface and not in
  scope.

This draft scan is not a Step 4.6 answer. Step 4.6 must source-back exact line
ranges, staleness, and target length before implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which anchors must remain visible verbatim or near-verbatim? | Answered: branch/head/sacred/full dirty list/current shipped state/next candidates/governance reminders remain visible. |
| Q2 | Which sections should be compacted, and how? | Answered: milestone tables compress to grouped bullets plus source-of-truth links; repeated verification detail leaves `current.md`. |
| Q3 | Which cross-references replace detailed history? | Answered: archive INVENTORY for per-cycle ledger, CHANGELOG for release-facing shipped state, latest archive blueprints for full review chains. |
| Q4 | Which stale anchors need repair? | Answered: current.md lines 3, 9, 11-15, 93-94, 103-105, and 109-110; published head must become `c23ce097`. |
| Q5 | What final length target should implementation meet? | Answered: <=80 lines, expected 65-75, verified by `wc -l workflow/memory/current.md`. |
| Q6 | Are any stop/amend triggers hit? | Answered: none; compressed history is recoverable from INVENTORY lines 11-24 and CHANGELOG lines 12-75. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Unique history is deleted from `current.md` | Source-of-truth loss | Step 4.6 must verify archive/changelog ownership before deleting details. |
| Compaction becomes new narrative | Scope creep | Only compact and repair stale anchors; no new design conclusions. |
| Auto-memory is edited | Wrong maintenance mechanism | Explicitly exclude non-repo `MEMORY.md`. |
| Dirty baseline list is compressed too far | Future agent may accidentally absorb dirty files | Keep complete list visible. |
| Other workflow files are edited | Housekeeping scope creep | Implementation file scope must be exactly `workflow/memory/current.md`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure. |

## 4.1 Step 4.6 Source-Backed Findings

- `workflow/memory/current.md` is 132 lines.
- Operational anchors live at lines 3, 7, 9, 17-18, and 20-34.
- Detailed milestone tables live at lines 38-94 and duplicate archive /
  changelog ownership.
- Stale local-pending wording appears at lines 3, 11-15, 93-94, 103-105, and
  109-110.
- Archive inventory lines 11-24 cover the recent evidence / adapter cycles in
  detail, including T8-D round 3, T8-C-1 runtime, T8-C-1 inventory, and T10-1.
- Changelog lines 12-75 cover release-facing shipped and deferred states,
  including native/Souffle/ProbLog evidence and PyReason future boundaries.
- No unique historical detail requiring a source-of-truth amendment was found.

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q6 answered.
- [ ] Single-file implementation complete.
- [ ] Line target verified.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
