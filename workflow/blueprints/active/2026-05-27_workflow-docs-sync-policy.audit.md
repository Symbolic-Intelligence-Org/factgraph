# Audit: Workflow Docs Sync Policy Clarification

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_workflow-docs-sync-policy.md`
- Stage: scoped
- Class: S (governance docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | Workflow docs sync policy blueprint pair drafted | Triggered after docs sync round 3 exposed that shipped-state sync policy existed only in transcript, not governance files. |
| 2026-05-27 | scoped | pending | Source-backed policy inventory completed | Middle path selected: tiny docs fixes may skip; future multi-file shipped-state/status sync should use a small blueprint/audit cycle; rounds 1/2/3 grandfathered as historical maintenance exceptions. |

## 2. Step 4.6 Inventory Summary

Source-backed findings:

- `CLAUDE.md:26-43` requires blueprints for non-trivial / architecture-facing
  tasks and limits exceptions to tiny typo, comment-only, and clearly local
  test fixes.
- `workflow/AGENTS.md:21-25` allows tiny local fixes but warns they must not
  bypass blueprint requirements for workflow / architecture / protocol /
  cross-module behavior.
- `workflow/CADENCE.md:21-29` mirrors the lightweight cases and says
  workflow/architecture/protocol/cross-module changes require cadence.
- `workflow/CADENCE.md:44` explicitly validates docs-only cadence.
- `workflow/blueprints/README.md:24-39` lists blueprint-required classes and
  skip cases; skip cases are local typos, comments, and tiny test fixes that
  cannot cause docs drift.
- Docs sync rounds `d281a5f8`, `0a2e1926`, and `3a8afee6` each touched 3-5
  state/index docs. They are historical maintenance exceptions and should not
  be retroactively wrapped.

Policy decision:

- Selected middle path: future multi-file shipped-state/status sync should use
  a small blueprint/audit cycle; tiny local docs fixes may still skip.
- Edit scope locked to `CLAUDE.md`, `workflow/AGENTS.md`, and
  `workflow/blueprints/README.md`.
- Root `AGENTS.md` remains a pointer only; `workflow/CADENCE.md` already has
  compatible docs-only cadence language.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What does current governance say about blueprint requirements and lightweight exceptions? | Answered with refs to `CLAUDE.md`, `workflow/AGENTS.md`, `workflow/CADENCE.md`, and `workflow/blueprints/README.md`. |
| Q2 | How should future docs-sync work be classified? | Answered: middle path. |
| Q3 | Which docs-sync cases may skip a blueprint? | Answered: tiny local docs fixes only. |
| Q4 | Which docs-sync cases must use a blueprint cycle? | Answered: future multi-file shipped-state/status sync and workflow/design-changing docs. |
| Q5 | How should the three 2026-05-27 docs-sync micro-passes be recorded? | Answered: historical maintenance exceptions, no retroactive blueprints. |
| Q6 | Which file(s) should change? | Answered: `CLAUDE.md`, `workflow/AGENTS.md`, `workflow/blueprints/README.md`. |
| Q7 | Does this require updating root `AGENTS.md`? | Answered: no. |
| Q8 | Verification plan? | Answered: docs-only checks and dirty baseline preservation. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Policy overcorrects and forces blueprints for tiny typo/docs nits | Slows maintenance and contradicts exception path | Define narrow skip criteria. |
| Policy undercorrects and lets multi-file governance/status sync skip blueprints | Future drift and transcript-only governance decisions | Define blueprint triggers for shipped-state sync. |
| Historical docs-sync rounds are treated as retroactive violations | Unnecessary churn | Record as historical exceptions / grandfathered maintenance. |
| Root and workflow governance files diverge | Confusing agent entry behavior | Decide canonical target and root pointer behavior. |
| Scope expands into full cadence rewrite | S-cycle becomes governance refactor | Stop/amend if more than docs-sync classification is needed. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q8 answered.
- [ ] Policy wording implemented.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / closure.
