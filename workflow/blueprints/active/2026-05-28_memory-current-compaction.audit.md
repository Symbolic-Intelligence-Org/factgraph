# Audit: Memory Current Compaction

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_memory-current-compaction.md`
- Stage: draft
- Class: S (housekeeping / docs-only memory compaction)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | Memory current compaction blueprint pair drafted | Triggered after T8-D round 3 `c23ce097`; Q1-Q6 pending Step 4.6. |

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
| Q1 | Which anchors must remain visible verbatim or near-verbatim? | Pending Step 4.6. |
| Q2 | Which sections should be compacted, and how? | Pending Step 4.6. |
| Q3 | Which cross-references replace detailed history? | Pending Step 4.6. |
| Q4 | Which stale anchors need repair? | Pending Step 4.6. |
| Q5 | What final length target should implementation meet? | Pending Step 4.6. |
| Q6 | Are any stop/amend triggers hit? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Unique history is deleted from `current.md` | Source-of-truth loss | Step 4.6 must verify archive/changelog ownership before deleting details. |
| Compaction becomes new narrative | Scope creep | Only compact and repair stale anchors; no new design conclusions. |
| Auto-memory is edited | Wrong maintenance mechanism | Explicitly exclude non-repo `MEMORY.md`. |
| Dirty baseline list is compressed too far | Future agent may accidentally absorb dirty files | Keep complete list visible. |
| Other workflow files are edited | Housekeeping scope creep | Implementation file scope must be exactly `workflow/memory/current.md`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q6 answered.
- [ ] Single-file implementation complete.
- [ ] Line target verified.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
