# Audit: T10-3 PyReason Temporal Migration Inventory

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-3-pyreason-temporal-migration-inventory.md`
- Stage: draft
- Class: S/M (design-only inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-3 PyReason temporal migration inventory drafted | Triggered by T10 staged-hybrid plan, T10-2-A C78 ship, T10-2-B C74 ship, and current memory next-work #1; Q1-Q10 pending Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10 inventory left C77 as the final PyReason adapter-semantics slice after
  C76 / C74 / C78.
- T10-2-A shipped canonical `iteration_count`, moving global inference rounds
  out of the temporal-projection design space and leaving `fixed_timesteps`
  compatibility for T10-3 to decide.
- T10-2-B shipped canonical C74 rule params through SDK lowering and existing
  `rule_projection["pyreason"]`; T10-3 must not reopen that carrier/lowering
  pattern.
- Existing temporal names are expected to include `none`, `fixed_timesteps`,
  and `valid_time_boundaries`; Step 4.6 must verify exact source locations.
- C77 canonical names are expected to include `fact_boundaries` and
  `time_binned`; Step 4.6 must source-back whether `time_binned` is truly new
  or an alias of existing behavior.
- Four untracked active design-point files remain in the dirty baseline and
  must be read-only grep-classified before any T10-3 implementation planning
  conclusion.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is C77's current ship state across SDK shell, SDK lowering, profile carrier, and adapter consumption? | Pending Step 4.6. |
| Q2 | What policy should govern `valid_time_boundaries` -> `fact_boundaries`? | Pending Step 4.6. |
| Q3 | What is the `time_binned` mode design and relationship to existing modes? | Pending Step 4.6. |
| Q4 | What should happen to legacy `fixed_timesteps` in T10-3? | Pending Step 4.6. |
| Q5 | What is the T10-3 implementation split? | Pending Step 4.6. |
| Q6 | After T10-3 ships, does T8-C-2 PyReason evidence only lack D11/Form 2? | Pending Step 4.6. |
| Q7 | Do the four untracked design-point files overlap T10-3 strongly? | Pending Step 4.6. |
| Q8 | Do T10-2-A or T10-2-B shipped behaviors have hidden coupling with C77? | Pending Step 4.6. |
| Q9 | Are there behavior changes that need warning, like T10-2-A's default timesteps change? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| C77 current state is misclassified | Future implementation may duplicate or remove shipped behavior | Q1 must source-back all temporal layers and current modes. |
| `valid_time_boundaries` rename is underspecified | Users may get silent behavior changes or duplicate modes | Q2 must define rename / alias / deprecate / removal policy and conflicts. |
| `time_binned` is not distinct from existing behavior | Implementation could add a redundant mode | Q3 must prove whether the mode is new or a canonical spelling. |
| `fixed_timesteps` policy contradicts T10-2-A | C78 `iteration_count` migration regresses | Q4/Q8 must source-back T10-2-A invariants before choosing policy. |
| T10-2-B C74 behavior regresses | The just-shipped canonical rule params become unstable | Q8 must include T10-2-B invariants and future implementation verification should include C74 tests. |
| C77 work expands into T8-C-2 evidence or D11/Form 2 | Scope creep | Scope locks exclude evidence enrichment and Form 2. |
| Untracked design-point coupling is missed | Dirty baseline/design lifecycle violation | Q7 must grep all four untracked active design-point files and stop if blocking. |
| Runtime/tests/user-docs are edited during inventory | Workflow violation | Design-only file scope until a future implementation cycle. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q10 answered.
- [ ] C77 current layer state reviewed.
- [ ] `valid_time_boundaries` / `fact_boundaries` policy reviewed.
- [ ] `time_binned` design reviewed.
- [ ] `fixed_timesteps` disposition reviewed.
- [ ] T10-2-A / T10-2-B invariant protection reviewed.
- [ ] Untracked design-point overlap reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / closure.
