# Audit: T10-3 PyReason Temporal Migration Inventory

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-3-pyreason-temporal-migration-inventory.md`
- Stage: scoped
- Class: S/M (design-only inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `bd24d2fb` | T10-3 PyReason temporal migration inventory drafted | Triggered by T10 staged-hybrid plan, T10-2-A C78 ship, T10-2-B C74 ship, and current memory next-work #1; Q1-Q10 pending Step 4.6. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed inventory completed | Confirmed C77 partial/legacy state, selected `fact_boundaries` alias first then `time_binned`, preserved `fixed_timesteps` compatibility, and classified design-point overlap as adjacent. |

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

### 2.1 Step 4.6 Source-Backed Summary

- C77 is **partial / legacy**. SDK shell and lowering pass through
  `temporal_projection`; `SemanticsProfile` and the PyReason adapter support
  `none`, `fixed_timesteps`, and legacy `valid_time_boundaries`; canonical
  `fact_boundaries` and `time_binned` are missing.
- `fact_boundaries` is a canonical rename / alias for the shipped
  `valid_time_boundaries` substrate. First implementation should add the
  canonical spelling while preserving legacy `valid_time_boundaries` through
  T10-3.
- `time_binned` is a true new mode, not an alias. It needs duration/bin-size
  validation and a new binned materializer, though it can reuse
  `_TemporalProjectionState` output shape.
- Legacy `fixed_timesteps` should remain accepted as a compatibility alias when
  canonical `iteration_count` is absent. T10-3 should preserve T10-2-A's
  explicit conflict between canonical `iteration_count` and temporal modes.
- Recommended split: T10-3-A for `fact_boundaries` alias / compatibility, then
  T10-3-B for `time_binned`.
- Four untracked design-point files are adjacent but not blocking. They discuss
  ledger valid time, identity/as-of, or PyReason edge modeling rather than C77
  adapter-local temporal mode implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is C77's current ship state across SDK shell, SDK lowering, profile carrier, and adapter consumption? | Answered: partial / legacy; `none`, `fixed_timesteps`, and `valid_time_boundaries` ship, while `fact_boundaries` / `time_binned` are missing. |
| Q2 | What policy should govern `valid_time_boundaries` -> `fact_boundaries`? | Answered: add canonical `fact_boundaries` alias while preserving legacy `valid_time_boundaries` through T10-3. |
| Q3 | What is the `time_binned` mode design and relationship to existing modes? | Answered: true new mode requiring bin-size validation and binned materialization; not an alias. |
| Q4 | What should happen to legacy `fixed_timesteps` in T10-3? | Answered: preserve as compatibility alias when canonical `iteration_count` is absent; keep explicit conflict with `iteration_count`. |
| Q5 | What is the T10-3 implementation split? | Answered: T10-3-A `fact_boundaries` alias/compatibility, then T10-3-B `time_binned`. |
| Q6 | After T10-3 ships, does T8-C-2 PyReason evidence only lack D11/Form 2? | Answered: after T10-3-B yes; after T10-3-A, `time_binned` remains a C77 gap. |
| Q7 | Do the four untracked design-point files overlap T10-3 strongly? | Answered: no; all four are adjacent and remain out-of-scope. |
| Q8 | Do T10-2-A or T10-2-B shipped behaviors have hidden coupling with C77? | Answered: T10-2-A's run-timesteps conflict remains a C77 implementation constraint; T10-2-B has no hidden C77 coupling. |
| Q9 | Are there behavior changes that need warning, like T10-2-A's default timesteps change? | Answered: no default shift expected for T10-3-A; T10-3-B must record bin boundary and conflict semantics. |
| Q10 | Are there stop/amend findings? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| C77 current state is misclassified | Future implementation may duplicate or remove shipped behavior | Mitigated: Q1 source-backed current modes and layers; C77 remains partial/legacy. |
| `valid_time_boundaries` rename is underspecified | Users may get silent behavior changes or duplicate modes | Mitigated: Q2 selects canonical alias plus legacy preservation, not hard cut. |
| `time_binned` is not distinct from existing behavior | Implementation could add a redundant mode | Mitigated: Q3 source-backed it as a true new equal-bin mode. |
| `fixed_timesteps` policy contradicts T10-2-A | C78 `iteration_count` migration regresses | Mitigated: Q4 preserves T10-2-A compatibility alias and conflict behavior. |
| T10-2-B C74 behavior regresses | The just-shipped canonical rule params become unstable | Mitigated: Q8 records no hidden C77 coupling and future implementation should keep C74 tests in gate. |
| C77 work expands into T8-C-2 evidence or D11/Form 2 | Scope creep | Scope locks exclude evidence enrichment and Form 2. |
| Untracked design-point coupling is missed | Dirty baseline/design lifecycle violation | Q7 must grep all four untracked active design-point files and stop if blocking. |
| Runtime/tests/user-docs are edited during inventory | Workflow violation | Design-only file scope until a future implementation cycle. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q10 answered.
- [x] C77 current layer state reviewed.
- [x] `valid_time_boundaries` / `fact_boundaries` policy reviewed.
- [x] `time_binned` design reviewed.
- [x] `fixed_timesteps` disposition reviewed.
- [x] T10-2-A / T10-2-B invariant protection reviewed.
- [x] Untracked design-point overlap reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / closure.
