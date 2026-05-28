# Audit: T10-2 PyReason Canonical Migration Inventory

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md`
- Stage: scoped
- Class: S/M (design-only inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `138a8461` | T10-2 PyReason canonical migration inventory drafted | Triggered by T10 staged-hybrid inventory and current memory next-work #1; Q1-Q8 pending Step 4.6. |
| 2026-05-28 | amend | `3efff8b9` | Dirty baseline drift recorded | Updated observed baseline from `5 U` to `6 U` and added `identity-mechanism-redesign.zh.md` to read-only overlap surface. |
| 2026-05-28 | scoped | pending | Step 4.6 source-backed inventory completed | C74/C78 per-layer states, atom-id conventions, fixed-timesteps decoupling, split recommendation, and untracked overlap classification recorded. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10 inventory already classifies C74 as partial/legacy and C78 as missing
  with legacy `fixed_timesteps` substrate.
- Current `PyReasonSemantics` exposes `timestep_delay`, `head_bound`,
  `branch_bounds`, `temporal_projection`, and `uncertainty_projection`, but no
  canonical `derived_bound`, `atom_bounds`, or `iteration_count`.
- SDK lowering currently emits PyReason profile entries with `head:0`,
  `branch:{index}`, and `rule` targets.
- PyReason adapter consumption currently accepts `body_atom:{branch}:{atom}`,
  `head:0`, `branch:{index}`, and `rule`.
- `SemanticsProfile.temporal_projection` currently supports legacy modes
  `none`, `fixed_timesteps`, and `valid_time_boundaries`.
- Four untracked active design-point files are present after baseline drift; the
  initial grep covered three and Step 4.6 must include
  `identity-mechanism-redesign.zh.md` before classifying overlap.
- The initially grepped design-point files mention PyReason only around ledger
  / valid-time / edge-model adjacency. Step 4.6 must
  classify whether that is blocking or out-of-scope.

### 2.1 Step 4.6 Inventory Summary

Source-backed findings:

- C74 remains **partial / legacy**. `timestep_delay` ships end-to-end through
  `PyReasonSemantics`, SDK lowering, `SemanticsProfile.rule_projection`, and
  PyReason adapter consumption. Canonical `derived_bound` is only legacy
  `head_bound`, and canonical full-atom-id `atom_bounds` is missing; current
  substrates are `branch_bounds`, `branch:{index}`, and
  `body_atom:{branch}:{atom}`.
- C78 remains **missing canonically**. `PyReasonSemantics` and
  `SemanticsProfile` have no `iteration_count`; legacy
  `temporal_projection.fixed_timesteps` currently feeds PyReason engine
  `timesteps`.
- Three atom-id conventions are distinct: application full atom ids
  (`<rule_id>:atom_<index>`), PyReason positional targets, and T8-B witness keys
  (`b<n>.a<n>:pred_id`). Future C74 needs a conversion layer and must not reuse
  witness keys.
- `fixed_timesteps` is a coupling point but not an inseparable dependency.
  C78 can ship first by introducing canonical `iteration_count` and preserving
  or explicitly aliasing legacy `fixed_timesteps`; T10-3 remains owner of
  canonical C77 temporal rename / `time_binned`.
- Recommended split: **T10-2-A C78 first**, then **T10-2-B C74** under the
  T10-2 umbrella.
- Four untracked design-point files were grep-classified as adjacent but not
  blocking. They discuss ledger valid time, identity/data model, or PyReason
  edge relationship modeling, not C74 atom-bound conversion or C78 iteration
  execution.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is the precise C74 ship state for `timestep_delay`, `derived_bound`, and `atom_bounds`? | Answered: `timestep_delay` shipped; `derived_bound` is legacy `head_bound`; `atom_bounds` missing as full atom-id shell/lowering. |
| Q2 | What is the precise C78 ship state and what does legacy `fixed_timesteps` cover today? | Answered: canonical `iteration_count` missing; `fixed_timesteps` currently covers engine iteration depth through temporal projection. |
| Q3 | What are the three atom-id conventions, where do they originate, and is a conversion layer required? | Answered: application full atom ids, PyReason positional targets, and T8-B witness keys are distinct; conversion layer required. |
| Q4 | Can `fixed_timesteps` be decoupled so C78 ships independently from C77? | Answered: yes, by introducing `iteration_count` and treating `fixed_timesteps` as compatibility/migration. |
| Q5 | Should T10-2 implementation be one cycle or split into T10-2-A/T10-2-B? | Answered: split as T10-2-A C78 first, then T10-2-B C74. |
| Q6 | After T10-2 ships, does T8-C-2 PyReason evidence only lack C77, or are other gates still present? | Answered: after both T10-2 sub-slices, T8-C-2 still needs T10-3 C77 and D11/Form 2 evidence design. |
| Q7 | Do the four untracked active design-point files overlap T10-2? | Answered: adjacent but not blocking; leave untouched. |
| Q8 | Are any stop/amend findings present? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| C74 legacy fields are mistaken for canonical fields | Future implementation ships wrong public surface | Per-layer C74 table must distinguish `head_bound` / `branch_bounds` from `derived_bound` / full atom-id `atom_bounds`. |
| C78 is hidden inside legacy `fixed_timesteps` | C78/C77 split becomes unsound | Step 4.6 must classify whether C78 can migrate independently from C77. |
| Atom-id conventions are conflated | Adapter consumes keys it cannot map to rules | Source-back all known conventions and require a conversion-layer decision. |
| Untracked design-point files are ignored despite strong coupling | Dirty baseline / design lifecycle violation | Grep and classify all four files; stop if blocking. Completed: adjacent but not blocking. |
| T10-2 drifts into C77 or T8-C-2 evidence | Scope creep | Keep temporal mode rename/time-binned and evidence enrichment out of scope. |
| Runtime/tests/docs are edited in inventory | Workflow violation | Design-only file scope until future implementation cycle. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q8 answered.
- [x] C74/C78 per-layer state reviewed.
- [x] Atom-id convention map reviewed.
- [x] `fixed_timesteps` decoupling reviewed.
- [x] Untracked design-point overlap reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending closure.
