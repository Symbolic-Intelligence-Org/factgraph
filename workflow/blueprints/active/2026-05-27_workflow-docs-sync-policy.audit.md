# Audit: Workflow Docs Sync Policy Clarification

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_workflow-docs-sync-policy.md`
- Stage: draft
- Class: S (governance docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | Workflow docs sync policy blueprint pair drafted | Triggered after docs sync round 3 exposed that shipped-state sync policy existed only in transcript, not governance files. |

## 2. Draft Source Scan

Read-only orientation findings:

- `CLAUDE.md` contains the root Required Workflow and Exceptions sections.
- `workflow/AGENTS.md` is the canonical workflow governance file and already
  warns that tiny local fixes must not bypass blueprint requirements for
  workflow / architecture / protocol / cross-module behavior.
- `workflow/CADENCE.md` already records that docs-only slices can use full
  audit-to-archive cadence.
- The three docs-sync micro-passes were maintenance updates to state/index
  documents after shipped work, not new runtime/design behavior. Step 4.6 must
  decide whether this remains a lightweight exception or becomes a blueprint
  trigger for future syncs.

This draft scan does not lock policy wording.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What does current governance say about blueprint requirements and lightweight exceptions? | Pending Step 4.6. |
| Q2 | How should future docs-sync work be classified? | Pending Step 4.6. |
| Q3 | Which docs-sync cases may skip a blueprint? | Pending Step 4.6. |
| Q4 | Which docs-sync cases must use a blueprint cycle? | Pending Step 4.6. |
| Q5 | How should the three 2026-05-27 docs-sync micro-passes be recorded? | Pending Step 4.6. |
| Q6 | Which file(s) should change? | Pending Step 4.6. |
| Q7 | Does this require updating root `AGENTS.md`? | Pending Step 4.6. |
| Q8 | Verification plan? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Policy overcorrects and forces blueprints for tiny typo/docs nits | Slows maintenance and contradicts exception path | Define narrow skip criteria. |
| Policy undercorrects and lets multi-file governance/status sync skip blueprints | Future drift and transcript-only governance decisions | Define blueprint triggers for shipped-state sync. |
| Historical docs-sync rounds are treated as retroactive violations | Unnecessary churn | Record as historical exceptions / grandfathered maintenance. |
| Root and workflow governance files diverge | Confusing agent entry behavior | Decide canonical target and root pointer behavior. |
| Scope expands into full cadence rewrite | S-cycle becomes governance refactor | Stop/amend if more than docs-sync classification is needed. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q8 answered.
- [ ] Policy wording implemented.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / closure.
