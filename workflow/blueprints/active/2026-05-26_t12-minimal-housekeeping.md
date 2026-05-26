# Task Blueprint: T12 Minimal Housekeeping

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: S/M (predicted docs / lifecycle housekeeping)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t12-minimal-housekeeping.audit.md`
- Roadmap source: `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` §3.8, §4.1, §5, §7

## 0. Scope Locks

### In scope

T12 is a minimal post-T5 / post-T11.1 housekeeping slice. It does not implement product behavior. It reconciles lifecycle metadata after T5.1-T5.8 and T11.1 have shipped.

Candidate sub-slices:

1. **T12.1 track-plan lifecycle decision**: decide whether `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` should be archived, marked superseded, or left active with a status update now that T1-T5 are complete and `post-t5-completion-roadmap.zh.md` is working.
2. **T12.2 D16-D26 lifecycle review**: inspect the eleven T5 D-docs and update lifecycle status / index entries when the decision lifecycle permits it.
3. **T12.3 active design-point index update**: update `workflow/design/design-points/README.md` only if the active/archived set or roadmap status is stale.
4. **T12.4 memory / progress sync inventory and bounded cleanup**: inspect repo memory and known external memory/index files; prune or summarize only if paths are known and writable, or record a scoped follow-up if not.

### Out of scope

- Production code changes.
- SDK/API/docs behavior changes outside lifecycle metadata and memory/progress summaries.
- Re-opening T5.1-T5.8 or T11.1 implementation decisions.
- Moving adopted decisions to archive solely because their implementation shipped. Per `workflow/design/decisions/README.md`, adopted decisions stay active while they remain current constraints.
- Broad rewrite of active design-points (`rule-expression-and-proof-attempt`, `database-view-fg-layered-architecture`, `evidence-tree-rainbird-style-v1`).
- Dirty baseline files unless Step 4.6 explicitly reclassifies one as a T12 input and the user approves.
- Push; push requires a separate single-use authorization.

### Stop / amend triggers

Pause and amend if Step 4.6 finds:

- a candidate file is outside writable roots and requires approval;
- D16-D26 lifecycle cannot be resolved without reopening design decisions;
- `rule-expression-and-proof-track-plan.zh.md` still has live unimplemented load-bearing content not covered by newer active design-points or roadmap;
- memory cleanup would require broad deletion rather than summarization;
- any source change would touch production Python, tests, examples, notebooks, or dirty-baseline files.

## 1. Problem

T5 Core + Semantics Lite and T11.1 have landed, but some planning/lifecycle artifacts still reflect pre-completion state:

- `rule-expression-and-proof-track-plan.zh.md` was the T1-T5 decomposition plan; T1-T5 are now complete, and a new working roadmap exists for T6-T12.
- D16-D26 remain in `workflow/design/decisions/active/` with `Status: proposed`, even though many were validated by T5 implementation slices.
- `workflow/design/design-points/README.md` has lifecycle rules but no current active-design-point inventory.
- Memory/progress files may exceed the project’s preferred index size and may still point at pre-T5 state.

T12 should clean these lifecycle seams without changing product behavior.

## 2. Inputs

| Source | Purpose |
|---|---|
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | Current scheduling reference; T12 source scope. |
| `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` | Candidate for archive/supersede/status update. |
| `workflow/design/design-points/README.md` | Design-point lifecycle rules and active/archive semantics. |
| `workflow/design/decisions/README.md` | ADR lifecycle: proposed / adopted / superseded / withdrawn. |
| `workflow/design/decisions/active/2026-05-25_t5-d16-*.md` through `t5-d26-*.md` | D-doc lifecycle review target set. |
| `workflow/blueprints/archive/2026-05-25_t5-*.md`, `workflow/blueprints/archive/2026-05-26_t5-8-*.md` | Implementation evidence for D-doc status decisions. |
| `workflow/memory/current.md` | Repo-local memory/progress sync target; draft read measured 168,593 bytes. |
| `/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` | Known global Claude memory index; scoped read measured 31,523 bytes, above the user-reported 24.4KB target. Editing is outside repo and requires explicit handling before implementation. |

## 3. Proposed Shape

### 3.1 T12.1 Track-Plan Lifecycle

Step 4.6 must classify `rule-expression-and-proof-track-plan.zh.md`:

- **Archive** if all load-bearing T1-T5 work is complete or superseded by active roadmap/design-points.
- **Mark superseded / leave active** if there are still live T6+ references or unresolved decisions not covered elsewhere.
- **No move** if lifecycle rules make archive unsafe; record why.

If archived, use `git mv` into `workflow/design/design-points/archive/` and update any index/reference that must point to the archive path. Step 4.6 confirmed this archive directory already exists.

### 3.2 T12.2 D16-D26 Lifecycle

Step 4.6 must inspect each D16-D26 file and decide one of:

- `adopted`: current binding constraint validated by shipped T5/T5.8 work; remains in `active/`.
- `superseded`: no longer current because a newer decision/design-point replaces it; move to `archive/` only if justified.
- `proposed`: leave unchanged if the decision was never formally adopted or still has unresolved scope.

The default expectation is conservative: many D-docs may become `adopted`, but adoption is not automatic. Each row needs a source anchor to the relevant implemented T5 slice.

If a D-doc is adopted, add an `Implementation Anchors:` metadata line near the header with the relevant T5/T5.8 slice commit(s). If a D-doc remains proposed, do not add an implementation anchor merely as decoration.

### 3.3 T12.3 Active Design-Point Index

Inspect `workflow/design/design-points/README.md` and active design-points. Update only if needed:

- add a compact active design-point inventory;
- mark `post-t5-completion-roadmap.zh.md` as the working scheduling reference;
- keep lifecycle rules intact.

### 3.4 T12.4 Memory / Progress Sync

Step 4.6 must locate memory/progress files and classify them:

- repo-local writable memory (`workflow/memory/current.md`, currently 168,593 bytes);
- global Claude index (`/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md`, currently 31,523 bytes and the main over-limit prune target);
- other external index/progress files, if their paths are known and writable;
- inaccessible or unknown external files, which become follow-up instructions instead of direct edits.

Possible implementation actions:

- prune repetitive index history into compact T5/T11/T12 summaries;
- record T5.1-T5.8 and T11.1 as published;
- record N1 roadmap as working;
- bring repo memory under the project’s preferred size only if a safe summarization strategy is clear.

## 4. Expected Changes

Likely docs-only changes:

- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` status update or `git mv` to archive.
- `workflow/design/design-points/README.md` compact active inventory, if stale.
- D16-D26 files status changes and/or `workflow/design/decisions/README.md` adopted index population.
- `workflow/memory/current.md` compact summary, if safe.
- Possibly external memory/index files only with explicit path confirmation and write permission.
- `workflow/blueprints/archive/INVENTORY.md` entry for this T12 blueprint when it archives.

Blueprint/audit pair will be closed and archived after implementation.

## 5. Step 4.6 Inventory Plan

Before implementation, record:

1. Active design-point list and archive destination availability.
2. References to `rule-expression-and-proof-track-plan.zh.md` across the repo.
3. For each D16-D26: current status, implementation slice(s) that validated it, and proposed lifecycle action.
4. `workflow/design/decisions/README.md` current adopted index state.
5. `workflow/design/design-points/README.md` current active inventory state.
6. Memory/progress file paths, sizes, writable status, and safe-prune candidates.
7. Dirty baseline verification.
8. Blueprint archive `INVENTORY.md` update target.
9. Any candidate that must be deferred because it would exceed S/M housekeeping scope.

### 5.1 Scoped Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Active design-point archive destination | `workflow/design/design-points/archive/` exists; no setup directory cost if T12.1 archives the track plan. |
| 2 | Track-plan references | Broad repo references remain in audits, archived blueprints, active decisions, memory, and the new roadmap. Implementation must either preserve history links or update only current/live references; archive is not automatic. |
| 3 | T12.1 candidate | Scoped as "decide after reference classification": likely archive/supersede if only historical references remain, but active audit/decision references must be checked first. |
| 4 | D16-D26 current status | All eleven files currently say `Status: proposed`. |
| 5 | D-doc implementation-anchor metadata | Scoped yes for adopted D-docs only: add `Implementation Anchors:` when status moves to `adopted`; do not add it to unchanged proposed docs. |
| 6 | Decisions README adopted index | Exists but currently says `(decisions 落地后填充)`; if D16-D26 are adopted, update the adopted index. |
| 7 | Design-points README / active inventory | README has lifecycle rules but no active inventory table; scoped candidate for compact active inventory if track-plan status changes. |
| 8 | Repo memory path | `workflow/memory/current.md` exists and is 168,593 bytes; writable in repo. Needs size assessment before pruning. |
| 9 | Global memory path | `/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` exists and is 31,523 bytes; primary over-limit index target. It is outside repo writable roots, so implementation must request/obtain permission before editing or record a follow-up. |
| 10 | Blueprint archive inventory | `workflow/blueprints/archive/INVENTORY.md` exists; `workflow/blueprints/active/INVENTORY.md` does not. Archive step must update the archive inventory only. |
| 11 | Dirty baseline | Preserve existing 6 modified + 1 untracked; no T12 draft/scoped edit touches them. |

## 6. Verification

- `git diff --check` clean.
- No production Python, tests, examples, or notebooks touched.
- Dirty baseline remains 6 modified + 1 untracked.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- If files are moved, `git status` shows intentional renames, not delete/add churn where avoidable.
- If memory is pruned, before/after byte counts are recorded.
- Archive closure updates `workflow/blueprints/archive/INVENTORY.md`.

## 7. Risks

| Risk | Mitigation |
|---|---|
| D-doc adoption becomes a semantic decision rather than housekeeping | Require per-D-doc implementation anchor; leave as `proposed` if uncertain. |
| Track-plan archive breaks source links in D-docs | Step 4.6 repo-wide `rg`; update only necessary references or leave active with superseded status. |
| Memory pruning loses useful trace | Summarize, do not delete unique anchors; keep T5/T11 milestone anchors. |
| External memory files are outside writable roots | Record follow-up instead of editing unless explicit approval is granted. |
| Scope balloons into release machinery | Defer release-specific CI/package/tag work to T11.3. |

## 8. Acceptance

- [ ] Step 4.6 inventory records lifecycle status for track plan, D16-D26, design-point index, and memory/progress files.
- [ ] T12.1 outcome is explicit: archive, supersede-in-place, or no-op with reason.
- [ ] T12.2 outcome is explicit for all D16-D26.
- [ ] T12.3 either updates design-point index or records "no change needed".
- [ ] T12.4 either prunes/syncs memory safely or records scoped follow-up.
- [ ] `workflow/blueprints/archive/INVENTORY.md` updated when this blueprint archives.
- [ ] No production behavior changes.
- [ ] Dirty baseline and sacred master preserved.
