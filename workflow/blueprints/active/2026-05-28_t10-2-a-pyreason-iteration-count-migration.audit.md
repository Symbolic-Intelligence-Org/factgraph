# Audit: T10-2-A PyReason Iteration Count Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md`
- Stage: draft
- Class: S/M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-2-A PyReason iteration_count migration drafted | Triggered by T10-2 inventory split decision; Q1-Q10 pending Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-2 inventory archived at `f8e08905` selected T10-2-A C78 before T10-2-B
  C74, because `fixed_timesteps` must be clarified before T10-3 temporal work.
- C78 canonical `iteration_count` is absent from current `PyReasonSemantics`,
  `SemanticsProfile`, and PyReason adapter consumption.
- Current PyReason execution derives engine timesteps from legacy
  `temporal_projection.fixed_timesteps`; this is the compatibility seam.
- C78 design requires `iteration_count: int = 1`, orthogonal to fact temporal
  lifecycle and distinct from per-rule `timestep_delay`.
- Existing legacy `fixed_timesteps` tests in
  `tests/test_pyreason_semantics_profile_migration.py` must remain regression
  guards unless Step 4.6 explicitly changes compatibility policy.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which canonical carrier should C78 use: top-level `SemanticsProfile.iteration_count` or `engine_options["iteration_count"]`? | Pending Step 4.6. |
| Q2 | What SDK validation should `PyReasonSemantics.iteration_count` use? | Pending Step 4.6. |
| Q3 | How should SDK lowering emit the carrier? | Pending Step 4.6. |
| Q4 | How should adapter consumption prioritize canonical vs legacy carriers? | Pending Step 4.6. |
| Q5 | What is the conflict behavior when canonical and legacy are both specified? | Pending Step 4.6. |
| Q6 | What is the legacy `fixed_timesteps` compatibility policy? | Pending Step 4.6. |
| Q7 | What is the focused test matrix? | Pending Step 4.6. |
| Q8 | What is the implementation commit split? | Pending Step 4.6. |
| Q9 | Does T10-2-A change the T8-C-2 unblock map? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Carrier choice is under-specified | SDK field may lower into a path future T10-3 cannot reason about | Q1 must compare top-level carrier vs `engine_options` with source refs and future T10-3 impact. |
| `iteration_count` is confused with `timestep_delay` | Global round count and per-rule delay semantics drift | Q2/Q3 must keep validation and docs/errors distinct from existing `timestep_delay`. |
| Legacy `fixed_timesteps` silently wins over canonical field, or vice versa | User configuration becomes ambiguous | Q5 must require explicit conflict behavior and tests. |
| Compatibility policy breaks existing fixed_timesteps tests | T10-2-A regresses shipped PyReason behavior | Q6/Q7 must include legacy regression coverage. |
| C74 or C77 work sneaks in | Scope creep and invalidates T10-2 split | Scope locks exclude atom-bound conversion and temporal mode rename/time-binned. |
| Evidence/user docs are touched | T10-2-A is adapter execution semantics, not evidence/user docs | File scope must remain runtime/tests/blueprint only. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Step 4.7 must compare F/E counts to `2013 / 72F / 231E`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed plan complete.
- [ ] Q1-Q10 answered.
- [ ] SDK shell / lowering / carrier / adapter plan reviewed.
- [ ] Conflict and compatibility policy reviewed.
- [ ] Test matrix reviewed.
- [ ] Implementation review complete.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
