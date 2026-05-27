# Task Blueprint: Workflow Docs Sync Policy Clarification

- Status: draft
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

## 3. Draft Source Scan

Draft orientation only:

- `CLAUDE.md` currently allows tiny typo, comment-only, and clearly local test
  fixes to skip a blueprint, but does not classify multi-file shipped-state
  docs sync.
- `workflow/AGENTS.md` states tiny local fixes may use the lightweight path but
  must not bypass blueprint requirements when the task changes workflow,
  architecture, protocol, or cross-module behavior.
- `workflow/CADENCE.md` explicitly says docs-only work can follow the full
  audit-to-archive cadence when it has a defined deliverable.
- The docs-sync micro-passes changed changelog/memory/roadmap style files and
  reflected already-shipped state; they did not create new runtime behavior or
  design commitments.

This draft scan does not lock final wording or target files. Step 4.6 must
replace it with source-backed file:line evidence and policy decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What does current governance say about blueprint requirements and lightweight exceptions? | Source-backed summary with file:line refs. |
| Q2 | How should future docs-sync work be classified? | Policy distinction between tiny local docs fixes, status/index sync, and design/workflow-changing docs. |
| Q3 | Which docs-sync cases may skip a blueprint? | Narrow criteria and examples. |
| Q4 | Which docs-sync cases must use a blueprint cycle? | Trigger list, including multi-file shipped-state sync if selected. |
| Q5 | How should the three 2026-05-27 docs-sync micro-passes be recorded? | Historical exception / grandfathering wording without retroactive blueprint requirement. |
| Q6 | Which file(s) should change? | Target file list with rationale and max edit scope. |
| Q7 | Does this require updating `AGENTS.md` at repo root? | Yes/no with compatibility rationale. |
| Q8 | Verification plan? | Docs-only checks (`git diff --check`, status, maybe grep) and dirty baseline preservation. |

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

- [ ] Step 4.6 source-backed inventory complete.
- [ ] Future docs-sync policy is explicit and bounded.
- [ ] Historical docs-sync rounds are recorded without retroactive churn.
- [ ] File scope is no broader than Step 4.6 locks.
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
