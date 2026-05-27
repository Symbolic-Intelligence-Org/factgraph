# Task Blueprint: Workflow Docs Sync Policy Clarification

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S (governance docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_workflow-docs-sync-policy.audit.md`
- Trigger: Three docs-sync micro-passes were treated as lightweight maintenance, but the distinction between tiny typo/comment exceptions and multi-file shipped-state synchronization is not persisted in governance docs.

## 0. Scope Locks

### In scope

1. Source-backed inventory of existing governance wording for blueprint
   requirements and lightweight exceptions.
2. Source-backed inventory of the three 2026-05-27 docs-sync micro-passes as
   historical exceptions / precedent.
3. Clarify future policy for shipped-state docs sync work:
   - when a docs sync may skip a blueprint;
   - when a docs sync must open a blueprint cycle;
   - how to handle status/memory/roadmap/changelog-only maintenance.
4. Decide target files for the policy update: likely `CLAUDE.md`,
   `workflow/AGENTS.md`, and/or `workflow/blueprints/README.md`.
5. Implement governance-doc wording only after Step 4.6 locks the file scope.

### Out of scope

- Runtime, test, SDK, service, adapter, release, notebook, examples, or public
  quickstart behavior changes.
- Rewriting the full workflow cadence.
- Retrospectively opening blueprints for already-pushed docs sync rounds.
- Dirty baseline cleanup.
- Changing sacred branch rules or push-gate policy.
- Changing the 8-state blueprint lifecycle beyond docs-sync applicability.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 finds:

- The policy needs broader cadence changes than docs-sync classification.
- More than three governance files need non-trivial edits.
- The change would contradict `workflow/CADENCE.md` or per-pillar README state
  machines.
- Any runtime/test/dirty-baseline edit appears necessary.

## 1. Problem

The repo already says tiny typo fixes, comment-only edits, and clearly local
test fixes may skip a blueprint. It also says architecture-facing or workflow
tasks must use a blueprint. The recent docs-sync micro-passes sat between
those categories: they changed multiple state/index documents but only
reflected already-shipped work.

Without a persistent policy note, a future session may repeat the same
judgment call inconsistently. This cycle should formalize the boundary without
over-expanding lightweight exceptions.

## 2. Inputs

| Source | Role |
|---|---|
| `CLAUDE.md` Required Workflow + Exceptions | Repo entry wording for blueprint requirements and skip cases. |
| `workflow/AGENTS.md` primary work mode lock-in | Canonical workflow governance and cross-pillar priority. |
| `workflow/CADENCE.md` docs-only cadence note | Existing proof that docs-only work can use full cadence. |
| `workflow/blueprints/README.md` | 8-state lifecycle and lightweight exception details. |
| Recent docs sync commits | Historical examples to classify: docs sync round 1, round 2, round 3. |

## 3. Step 4.6 Inventory Results

### 3.1 Current governance wording

| Source | Existing wording / finding |
|---|---|
| `CLAUDE.md:26-43` | Required workflow says non-trivial feature/refactor/protocol/cross-module/architecture-facing tasks must create or reuse a blueprint. Exceptions are "Tiny typo fixes, comment-only edits, and clearly local test fixes". No shipped-state docs-sync category is defined. |
| `workflow/AGENTS.md:21-25` | Primary work mode applies to large-scope workflow, architecture, migration, and audit-first implementation work. Tiny local fixes may use the lightweight path but must not bypass blueprint requirements for workflow, architecture, protocol, or cross-module behavior. |
| `workflow/CADENCE.md:21-29` | Cadence is not mandatory for tiny typo/comment/test-helper/internal-refactor cases, but workflow/architecture/protocol/cross-module changes must follow cadence regardless of size. |
| `workflow/CADENCE.md:44` | Docs-only work can follow audit-to-archive cadence when it has a defined deliverable. |
| `workflow/blueprints/README.md:24-39` | Blueprint required for cross-module, protocol/contract/DTO/DSL, architecture, new module docs / main docs entry, or complex drift-prone tasks. Skip cases are local typos, non-behavior comments, and tiny test fixes that cannot cause docs drift. |
| `AGENTS.md:1-5` | Root compatibility file only points to `CLAUDE.md`; substantive content lives in `CLAUDE.md`. |

### 3.2 Historical docs-sync rounds

| Commit | Files | Classification |
|---|---|---|
| `d281a5f8` `docs: sync shipped session state` | 5 files: `CHANGELOG.md`, `docs/README.md`, `workflow/design/design-points/README.md`, roadmap, memory. | Multi-file shipped-state/status sync. Historical maintenance exception; no retroactive blueprint. |
| `0a2e1926` `docs: sync evidence track shipped state` | 3 files: `CHANGELOG.md`, roadmap, memory. | Multi-file shipped-state/status sync. Historical maintenance exception; no retroactive blueprint. |
| `3a8afee6` `docs: sync roadmap after T10 inventory` | 3 files: `CHANGELOG.md`, roadmap, memory. | Multi-file shipped-state/status sync. Historical maintenance exception; no retroactive blueprint. |

### 3.3 Policy decision

Selected policy: **middle path**.

- Do **not** extend the tiny-exception path to all shipped-state docs sync:
  multi-file state/index sync can affect future agent orientation and should
  not live only in transcript judgment.
- Do **not** require full heavy cadence for every typo or single-file status
  correction: local typo/comment/docs nits remain lightweight exceptions.
- Future multi-file shipped-state synchronization that updates workflow memory,
  roadmap, changelog, docs index, design-point inventory, or similar state
  surfaces should use a small blueprint/audit cycle. It may be S-class and
  docs-only, but it should still record scope, source refs, closure, and
  archive.

### 3.4 File scope decision

Edit three governance files:

1. `CLAUDE.md` — root entry where agents first see Required Workflow /
   Exceptions.
2. `workflow/AGENTS.md` — canonical workflow governance and cross-pillar
   lock-in.
3. `workflow/blueprints/README.md` — blueprint pillar rule where skip cases are
   already listed.

Leave alone:

- Root `AGENTS.md`: compatibility pointer only; changing it would duplicate
  substantive governance already delegated to `CLAUDE.md`.
- `workflow/CADENCE.md`: already states docs-only work can use cadence and that
  workflow/architecture changes cannot bypass cadence. No contradiction; no
  edit required.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What does current governance say about blueprint requirements and lightweight exceptions? | `CLAUDE.md`, `workflow/AGENTS.md`, `workflow/CADENCE.md`, and `workflow/blueprints/README.md` all limit lightweight exceptions to tiny local fixes; none defines multi-file shipped-state sync. |
| Q2 | How should future docs-sync work be classified? | Middle path: tiny local docs fixes may skip; multi-file shipped-state/status sync should use a small blueprint/audit cycle; workflow/design-changing docs already require cadence. |
| Q3 | Which docs-sync cases may skip a blueprint? | Single-file typo/link wording fixes, comment/prose-only nits, or local doc corrections that do not update state/index surfaces or affect future planning. |
| Q4 | Which docs-sync cases must use a blueprint cycle? | Multi-file shipped-state sync across changelog/memory/roadmap/docs index/design inventory; any docs sync that changes workflow status, planning priorities, active/archive inventories, or cross-session handoff truth. |
| Q5 | How should the three 2026-05-27 docs-sync micro-passes be recorded? | Grandfather as historical maintenance exceptions: `d281a5f8`, `0a2e1926`, `3a8afee6` are not retroactive workflow violations and need no retroactive blueprints. |
| Q6 | Which file(s) should change? | Edit `CLAUDE.md`, `workflow/AGENTS.md`, and `workflow/blueprints/README.md`; leave root `AGENTS.md` and `workflow/CADENCE.md` unchanged. |
| Q7 | Does this require updating `AGENTS.md` at repo root? | No. Root `AGENTS.md` is a compatibility pointer to `CLAUDE.md`; duplicating policy there would create drift risk. |
| Q8 | Verification plan? | `git diff --check`, grep for docs-sync policy wording, and status check preserving dirty baseline. |

## 5. Existing Invariants To Preserve

- This is governance docs-only.
- Do not change runtime, tests, public API, release machinery, examples, or
  notebooks.
- Do not absorb dirty baseline `4 M + 1 D + 3 U`.
- Do not rewrite full cadence or alter sacred branch/push-gate rules.
- Preserve `CLAUDE.md` as the root entry and `workflow/AGENTS.md` as canonical
  workflow governance.

## 6. Step 4.6 Inventory Plan

Step 4.6 must:

1. Re-read `CLAUDE.md`, `workflow/AGENTS.md`, `workflow/CADENCE.md`, and
   `workflow/blueprints/README.md`.
2. Identify current exception wording and any conflicts.
3. Classify docs sync rounds 1/2/3 as historical shipped-state maintenance.
4. Decide whether future multi-file shipped-state sync requires a blueprint.
5. Lock exact file scope and wording approach.

## 7. Proposed Implementation Shape

Likely commits:

1. Draft blueprint/audit.
2. Scoped inventory.
3. Governance docs implementation.
4. Closure.
5. Archive.

## 8. Acceptance

- [x] Step 4.6 source-backed inventory complete.
- [x] Future docs-sync policy is explicit and bounded.
- [x] Historical docs-sync rounds are recorded without retroactive churn.
- [x] File scope is no broader than Step 4.6 locks.
- [ ] No runtime/test/dirty-baseline files are edited.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Draft expected checks:

```bash
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Pending scoped inventory / closure.
