# Audit: T10-1 ProbLog Uncertainty Projection

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t10-1-problog-uncertainty-projection.md`
- Stage: draft
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 4 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T10-1 ProbLog uncertainty projection blueprint pair drafted | Triggered after T10 inventory selected T10-1 C76 as the first staged hybrid implementation slice; Q1-Q10 intentionally pending for Step 4.6. |

## 2. Draft Inventory Summary

Draft orientation only:

- T10 inventory selected T10-1 as ProbLog C76 full three-layer ship.
- Reviewer due diligence reports two pre-existing ProbLog migration errors from
  legacy `meta[confidence]` fixture writes.
- Reviewer due diligence reports C76 gaps at SDK shell, SDK lowering, and
  adapter consumption layers, with only generic
  `SemanticsProfile.uncertainty_projection` substrate shipped.

Step 4.6 must independently verify or correct each finding before
implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should the two ProbLog migration errors be fixed inside T10-1, before T10-1, or left as known drift? | Pending Step 4.6. |
| Q2 | What is the verified C76 three-layer current state? | Pending Step 4.6. |
| Q3 | What SDK field shape should `ProbLogSemantics.uncertainty_projection` expose? | Pending Step 4.6. |
| Q4 | What is the default lowering policy when SDK callers omit `uncertainty_projection`? | Pending Step 4.6. |
| Q5 | What adapter consumption semantics should v1 ship? | Pending Step 4.6. |
| Q6 | Which policies are supported in v1? | Pending Step 4.6. |
| Q7 | What is the focused test matrix? | Pending Step 4.6. |
| Q8 | Does full T10-1 ship unblock T8-C-1? | Pending Step 4.6. |
| Q9 | Do audit docs or user docs change? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Fixture drift is treated as unrelated and left to keep failing | T10-1 verification remains noisy and may hide regressions | Decide Q1 before implementation. |
| Runtime bug is misclassified as fixture drift | T10-1 builds on broken ProbLog write/evaluate path | Verify write protocol rejection and fixture setup source. |
| SDK shell ships without lowering or adapter consumption | `uncertainty_projection` silently appears supported but does nothing | Require all three C76 layers in one coherent scope or stop. |
| Adapter silently ignores raw uncertainty rows | User configuration has no effect; T8-C-1 starts on false prerequisite | Q5 must choose explicit reject/substitution semantics. |
| C110 carrier is weakened to make tests pass | Reintroduces removed uncertainty keys | Preserve write protocol legacy-key rejection. |
| T10-1 drifts into T8-C evidence enrichment | Scope expands beyond adapter execution semantics | Keep T8-C-1 out of scope. |
| Dirty baseline is touched | Workflow violation | Stage only T10-1 files. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q10 answered.
- [ ] Implementation commits reviewed.
- [ ] Focused verification recorded.
- [ ] Full discover delta recorded.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending scoped inventory / implementation.
