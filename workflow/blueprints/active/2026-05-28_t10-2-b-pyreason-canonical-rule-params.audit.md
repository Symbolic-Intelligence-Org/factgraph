# Audit: T10-2-B PyReason Canonical Rule Params

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md`
- Stage: scoped
- Class: M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `109c4c6f` | T10-2-B PyReason C74 canonical rule params drafted | Triggered by T10-2 inventory split decision and T10-2-A C78 ship; Q1-Q12 pending Step 4.6. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed plan completed | Selected existing `rule_projection["pyreason"]` carrier, SDK-lowering atom-id conversion, and three-impl commit split. |

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

## 2.1 Step 4.6 Source-Backed Summary

- Carrier: use existing `SemanticsProfile.rule_projection["pyreason"]`, not new
  top-level C74 fields. Source refs: `profile.py:36, :46, :119-139`;
  `rule_ext.py:155-229`.
- SDK fields: add `PyReasonSemantics.derived_bound` and `atom_bounds` with
  canonical field-specific validation. Existing public shell lacks those fields
  (`sdk/semantics.py:150-176`).
- Atom-id conversion: SDK lowering converts application full ids
  `<rule_id>:atom_<index>` (`application/protocol/rule.py:98-100`) into
  existing positional `body_atom:{branch}:{atom}` targets. The private lowering
  context must gain atom-id data because it currently carries only name, branch
  indexes, known rule ids, and branch-specific allowance (`sdk/store.py:3357-3363`).
  T8-B witness keys (`core/store/_support.py:201-212`) remain out of scope and
  unused.
- Compatibility: `derived_bound` + `head_bound` rejects; `atom_bounds` +
  `branch_bounds` coexists because they lower to body-atom thresholds vs branch
  head intervals.
- Adapter: no new adapter carrier is required; existing `rule_ext.py` already
  consumes `head:0`, `branch:{index}`, and `body_atom:{branch}:{atom}` entries.
- Baseline: agreed four-module PyReason suite ran `84 OK`. Adding
  `tests.test_pyreason_branch_bounds_carrier` shows two pre-existing C110
  `meta[confidence]` errors, so that file remains source context rather than a
  T10-2-B focused gate.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which canonical carrier should C74 use for `derived_bound` / `atom_bounds`? | Answered: existing `rule_projection["pyreason"]`. |
| Q2 | What SDK validation should canonical fields use, and how do they coexist with legacy fields? | Answered: interval validation + full atom-id key validation; normalize independently before conflict checks. |
| Q3 | Where should atom-id conversion happen? | Answered: SDK lowering; never T8-B witness keys. |
| Q4 | How should SDK lowering implement the omission rule? | Answered: default canonical emits nothing; legacy-only preserved; canonical-only emits canonical; duplicate head carriers reject. |
| Q5 | How should adapter consumption prioritize canonical vs legacy carriers? | Answered: no new priority path; lowering emits existing adapter-local entries. |
| Q6 | What is the conflict behavior for canonical + legacy pairs? | Answered: `derived_bound` + `head_bound` rejects; `atom_bounds` + `branch_bounds` coexists. |
| Q7 | What is the legacy compatibility policy for `head_bound` / `branch_bounds`? | Answered: both remain accepted through T10-3; no warning in T10-2-B. |
| Q8 | What is the focused test matrix? | Answered: canonical SDK/lowering/conversion/conflict/coexistence + T10-2-A isolation + discover comparison. |
| Q9 | What is the implementation commit split? | Answered: SDK shell, lowering/conversion, tests, then close/archive. |
| Q10 | Does T10-2-B change the T8-C-2 unblock map? | Answered: removes C74 only; C77 and D11/Form 2 remain. |
| Q11 | Are there behavior changes that need explicit closure notes? | Answered: no default behavior shift expected; new dual head-bound spelling conflict should be recorded. |
| Q12 | Are there stop/amend findings? | Answered: none. |

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

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed plan complete.
- [x] Q1-Q12 answered.
- [x] SDK shell / lowering / carrier / adapter plan reviewed.
- [x] Atom-id conversion plan reviewed.
- [x] Conflict and compatibility policy reviewed.
- [x] Test matrix reviewed.
- [ ] Implementation review complete.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending implementation / closure.
