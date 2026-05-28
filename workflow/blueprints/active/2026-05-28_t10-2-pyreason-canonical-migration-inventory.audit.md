# Audit: T10-2 PyReason Canonical Migration Inventory

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md`
- Stage: draft
- Class: S/M (design-only inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-2 PyReason canonical migration inventory drafted | Triggered by T10 staged-hybrid inventory and current memory next-work #1; Q1-Q8 pending Step 4.6. |

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

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is the precise C74 ship state for `timestep_delay`, `derived_bound`, and `atom_bounds`? | Pending Step 4.6. |
| Q2 | What is the precise C78 ship state and what does legacy `fixed_timesteps` cover today? | Pending Step 4.6. |
| Q3 | What are the three atom-id conventions, where do they originate, and is a conversion layer required? | Pending Step 4.6. |
| Q4 | Can `fixed_timesteps` be decoupled so C78 ships independently from C77? | Pending Step 4.6. |
| Q5 | Should T10-2 implementation be one cycle or split into T10-2-A/T10-2-B? | Pending Step 4.6. |
| Q6 | After T10-2 ships, does T8-C-2 PyReason evidence only lack C77, or are other gates still present? | Pending Step 4.6. |
| Q7 | Do the four untracked active design-point files overlap T10-2? | Pending Step 4.6. |
| Q8 | Are any stop/amend findings present? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| C74 legacy fields are mistaken for canonical fields | Future implementation ships wrong public surface | Per-layer C74 table must distinguish `head_bound` / `branch_bounds` from `derived_bound` / full atom-id `atom_bounds`. |
| C78 is hidden inside legacy `fixed_timesteps` | C78/C77 split becomes unsound | Step 4.6 must classify whether C78 can migrate independently from C77. |
| Atom-id conventions are conflated | Adapter consumes keys it cannot map to rules | Source-back all known conventions and require a conversion-layer decision. |
| Untracked design-point files are ignored despite strong coupling | Dirty baseline / design lifecycle violation | Grep and classify all three files; stop if blocking. |
| T10-2 drifts into C77 or T8-C-2 evidence | Scope creep | Keep temporal mode rename/time-binned and evidence enrichment out of scope. |
| Runtime/tests/docs are edited in inventory | Workflow violation | Design-only file scope until future implementation cycle. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q8 answered.
- [ ] C74/C78 per-layer state reviewed.
- [ ] Atom-id convention map reviewed.
- [ ] `fixed_timesteps` decoupling reviewed.
- [ ] Untracked design-point overlap reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / closure.
