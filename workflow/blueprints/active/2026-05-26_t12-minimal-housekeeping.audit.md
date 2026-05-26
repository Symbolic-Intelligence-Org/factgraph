# Audit: T12 Minimal Housekeeping

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t12-minimal-housekeeping.md`
- Stage: scoped
- Class: S/M (predicted docs / lifecycle housekeeping)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked must be preserved
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `03698d9c` | T12 minimal housekeeping blueprint pair drafted | Triggered by N1 roadmap §3.8 and user-selected N1 → N5 ordering after T5/T11.1 publication. |
| 2026-05-26 | scoped | pending | Step 4.6 inventory scoped | Added archive destination, track-plan reference blast radius, D16-D26 status table result, implementation-anchor policy, memory path inventory, and blueprint archive INVENTORY target. |

## 2. Initial Read Summary

| Source | Observation |
|---|---|
| `post-t5-completion-roadmap.zh.md` | §3.8 names T12 lifecycle/design housekeeping; §5 recommends N1 → T12 minimal housekeeping before T11 release machinery. |
| `workflow/design/design-points/README.md` | Design-points archive only when load-bearing questions are closed, implementation-eligible content shipped/deferred/superseded, and no active blueprint depends on it. |
| `workflow/design/decisions/README.md` | `adopted` decisions stay in `active/`; only `superseded` / `withdrawn` move to `archive/`. |
| D16/D26 spot reads | D16-D26 currently use `Status: proposed`; adoption must be explicit and source-backed. |
| `workflow/memory/current.md` | Repo-local memory is large (`168593` bytes at draft read); safe pruning requires separate inventory. |
| `/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` | Known global Claude memory index is `31523` bytes, above the user-reported 24.4KB target; outside repo write scope. |

## 3. Draft Scope Decisions

| Decision | Rationale |
|---|---|
| Single T12 blueprint pair covers T12.1-T12.4 | Roadmap classifies T12 as S/M housekeeping; candidates are tightly related lifecycle cleanup. |
| Step 4.6 may narrow | If any candidate needs semantic design work, external writes, or broad release machinery, defer it. |
| D-doc status changes are conservative | Shipped implementation is evidence, but decision lifecycle still requires explicit adopted/superseded reasoning. |
| Memory cleanup is conditional | Direct edits only for known writable paths and safe summarization. |

## 4. Step 4.6 Inventory Checklist

To fill during scoped inventory:

| # | Item | Result |
|---|---|---|
| 1 | Active design-point list and archive destination | Active design-points: evidence-tree, database-view, rule-expression parent, rule-expression track-plan, post-T5 roadmap. `workflow/design/design-points/archive/` exists. |
| 2 | Repo references to `rule-expression-and-proof-track-plan.zh.md` | Broad references across active audits, active decisions, archived blueprints, memory, and roadmap. T12.1 must classify live vs historical refs before any move. |
| 3 | T12.1 lifecycle decision candidate | Not pre-decided. Scoped candidate is archive/supersede only if live refs are updated or proven historical. |
| 4 | D16-D26 current statuses and shipped implementation anchors | All eleven D-docs currently `Status: proposed`; implementation anchors must be collected per file before adoption. |
| 5 | D16-D26 proposed lifecycle action table | To fill in implementation. Scoped policy: add `Implementation Anchors:` only for D-docs moved to `adopted`. |
| 6 | `workflow/design/decisions/README.md` adopted index state | Adopted index exists but is empty placeholder `(decisions 落地后填充)`. |
| 7 | `workflow/design/design-points/README.md` active inventory gap | Lifecycle rules exist; no active inventory table. Candidate update if track-plan/roadmap status changes. |
| 8 | Memory/progress paths, size, and writable status | Repo `workflow/memory/current.md` = 168,593 bytes; global `/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` = 31,523 bytes and outside repo write scope. |
| 9 | Dirty baseline verification | 6 modified + 1 untracked preserved. |
| 10 | Blueprint archive inventory | `workflow/blueprints/archive/INVENTORY.md` exists; active inventory does not. Archive must update archive inventory. |
| 11 | Scope reduction / deferral decisions | External global memory edit may require permission or follow-up; release machinery remains deferred to T11.3. |

## 5. Verification Plan

- `git diff --check`.
- `git status --short --branch`.
- `git rev-parse master` to confirm sacred branch.
- File move verification if T12.1 archives the track plan.
- Byte-count before/after if memory pruning occurs.

## 6. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] T12.1 implemented or explicitly deferred.
- [ ] T12.2 implemented or explicitly deferred.
- [ ] T12.3 implemented or no-op recorded.
- [ ] T12.4 implemented or explicitly deferred.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending.
