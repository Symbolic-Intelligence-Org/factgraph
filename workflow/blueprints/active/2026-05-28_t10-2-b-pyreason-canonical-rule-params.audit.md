# Audit: T10-2-B PyReason Canonical Rule Params

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md`
- Stage: draft
- Class: M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-2-B PyReason C74 canonical rule params drafted | Triggered by T10-2 inventory split decision and T10-2-A C78 ship; Q1-Q12 pending Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-2 inventory archived at `f8e08905` selected T10-2-A C78 before T10-2-B
  C74 and recorded three distinct atom-id conventions.
- T10-2-A shipped at `65cc79a3` with optional canonical profile carrier,
  wrapper lowering, adapter consumption, omission rule, and explicit conflict
  tests. T10-2-B should reuse the pattern but not modify C78.
- C74 remains larger than T10-2-A because it has two canonical public fields,
  atom-id conversion, and compatibility policy for two legacy fields.
- Existing `head_bound` and `branch_bounds` behavior must remain regression
  guarded until Step 4.6 defines explicit compatibility policy.
- T8-B witness keys (`b<n>.a<n>:pred_id`) are evidence support identity, not a
  C74 atom-id substrate.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which canonical carrier should C74 use for `derived_bound` / `atom_bounds`? | Pending Step 4.6. |
| Q2 | What SDK validation should canonical fields use, and how do they coexist with legacy fields? | Pending Step 4.6. |
| Q3 | Where should atom-id conversion happen? | Pending Step 4.6. |
| Q4 | How should SDK lowering implement the omission rule? | Pending Step 4.6. |
| Q5 | How should adapter consumption prioritize canonical vs legacy carriers? | Pending Step 4.6. |
| Q6 | What is the conflict behavior for canonical + legacy pairs? | Pending Step 4.6. |
| Q7 | What is the legacy compatibility policy for `head_bound` / `branch_bounds`? | Pending Step 4.6. |
| Q8 | What is the focused test matrix? | Pending Step 4.6. |
| Q9 | What is the implementation commit split? | Pending Step 4.6. |
| Q10 | Does T10-2-B change the T8-C-2 unblock map? | Pending Step 4.6. |
| Q11 | Are there behavior changes that need explicit closure notes? | Pending Step 4.6. |
| Q12 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Carrier choice duplicates or bypasses `rule_projection` semantics | Canonical C74 might diverge from adapter consumption | Q1 must compare top-level carrier vs `rule_projection` extension with source refs. |
| Atom-id conventions are conflated | Bounds could attach to the wrong atom or reuse evidence witness identity | Q3 must source-back all three conventions and prohibit witness-key reuse. |
| Legacy compatibility is under-specified | Existing `head_bound` / `branch_bounds` behavior regresses or silently loses to canonical fields | Q6/Q7 must define explicit conflict and fallback behavior. |
| T10-2-A C78 behavior regresses | The prior PyReason slice becomes unstable | Q8 must include the T10-2-A focused tests in regression verification. |
| C77/T8-C-2 work sneaks in | Scope creep invalidates T10-2 split | Scope locks exclude temporal migration and evidence enrichment. |
| Evidence/user/audit docs are touched | T10-2-B is adapter execution semantics, not evidence/user docs | File scope must remain runtime/tests/blueprint/state docs only. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Step 4.7 must compare F/E counts to `2019 / 72F / 231E`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed plan complete.
- [ ] Q1-Q12 answered.
- [ ] SDK shell / lowering / carrier / adapter plan reviewed.
- [ ] Atom-id conversion plan reviewed.
- [ ] Conflict and compatibility policy reviewed.
- [ ] Test matrix reviewed.
- [ ] Implementation review complete.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
