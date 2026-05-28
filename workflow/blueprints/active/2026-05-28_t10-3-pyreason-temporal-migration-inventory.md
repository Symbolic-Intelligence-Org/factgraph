# Task Blueprint: T10-3 PyReason Temporal Migration Inventory

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (design-only inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-3-pyreason-temporal-migration-inventory.audit.md`
- Trigger: T10 inventory selected the staged hybrid split and left C77 PyReason
  temporal migration as the final adapter-semantics slice after T10-1 / T10-2.
  T10-2-A shipped at `65cc79a3`, decoupling canonical C78 `iteration_count`
  from legacy temporal `fixed_timesteps`. T10-2-B shipped at `92fd6013`,
  completing C74 canonical rule params and proving the existing PyReason
  lowering / adapter-consumption pattern. `workflow/memory/current.md` now lists
  T10-3 C77 PyReason temporal migration as the next recommended work.

## 0. Scope Locks

### In scope

This is a design-only inventory cycle before any T10-3 implementation.

1. Source-backed C77 layer inventory:
   - SDK shell state.
   - SDK lowering state.
   - `SemanticsProfile.temporal_projection` carrier state.
   - Adapter consumption state.
2. Source-backed legacy `valid_time_boundaries` versus canonical
   `fact_boundaries` rename analysis:
   - Rename / alias / deprecate / removal policy options.
   - Compatibility horizon.
3. Source-backed canonical `time_binned` mode design:
   - Whether it is truly new.
   - Relationship to existing `none`, `fixed_timesteps`, and
     `valid_time_boundaries` modes.
   - Adapter consumption shape.
4. T10-2-A-after legacy `fixed_timesteps` disposition:
   - Preserve, deprecate, or remove.
   - Relationship to already-shipped canonical `iteration_count`.
5. T10-3 implementation split decision:
   - Single cycle.
   - T10-3-A `valid_time_boundaries` -> `fact_boundaries` rename plus T10-3-B
     `time_binned` mode.
   - Other split if Step 4.6 finds a better shape.
   - T8-C-2 PyReason evidence unblock relationship.
6. Read-only overlap check for the four untracked active design-point files:
   - `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
   - `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`
   - `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
   - `workflow/design/design-points/active/ledger-schema-specification.zh.md`

### Out of scope

- Runtime code changes.
- Test code changes.
- T10-3 implementation itself.
- T10-2-A C78 `iteration_count` behavior; do not weaken, redo, or roll it back.
- T10-2-B C74 `derived_bound`, `atom_bounds`, atom-id conversion, asymmetric
  conflict policy, or existing-rule-projection carrier behavior; do not weaken,
  redo, or roll it back.
- C76 ProbLog or ProbLog adapter work; T10-1 already shipped it.
- T8-C-2 PyReason evidence enrichment implementation.
- Changes to T10-1, T8-C-1, or T8-D shipped behavior.
- D11 / Form 2 / Nemo / C119 / C136 / aggregate / failed graph / why-not /
  counterfactual / match witness.
- D20 / service / OpenAPI / Database/view / match API / `fg.eval.run` /
  release / PyPI / tags.
- `EvidenceGraph` DTO, 14-key metadata, `_FORM1_ROW_SUPPORT_KINDS`, or
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- T8-A 14-key validation, T8-B Form 1, T8-D round 1/2/3 user docs, or T10-1
  anti-silent-ignore behavior.
- C110 legacy `confidence` rejection.
- Audit module docs; this inventory ships no behavior.
- User-facing docs; a future T8-D round can follow after T10-2-A/B and T10-3
  all ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`; the four untracked design-point files
  remain adjacent and out-of-scope unless Step 4.6 proves otherwise.
- Reopening T10 inventory, T10-2 inventory, T10-2-A, or T10-2-B decisions. If
  Step 4.6 finds a contradiction, stop and amend the relevant archive instead
  of silently diverging.
- Absorbing or classifying untracked design-point files.

### Stop / amend triggers

Pause and amend if Step 4.6 shows:

1. T10 inventory's C77 deferred classification is materially wrong.
2. C77 canonical design contradicts the T10-2-A shipped `fixed_timesteps` /
   `iteration_count` decoupling policy.
3. `time_binned` cannot be designed independently from `fact_boundaries`.
4. T10-3 cannot be split safely if the rename plus new mode implementation is
   too large for one implementation cycle.
5. Any untracked design-point file is strongly coupled to C77 / temporal
   migration and must be adopted before T10-3.
6. Runtime, tests, user docs, governance, sacred `master`, dirty-baseline files,
   T10-2-A behavior, or T10-2-B behavior would be touched in this inventory.

## 1. Problem

T10-2-A moved PyReason global inference rounds into canonical
`iteration_count`, reducing the legacy coupling where
`temporal_projection.fixed_timesteps` carried execution-depth semantics. T10-3
is now the remaining PyReason semantics slice from the T10 staged-hybrid plan:
canonical C77 temporal projection.

Current shipped behavior is expected to still expose legacy temporal projection
modes, especially `valid_time_boundaries` and `fixed_timesteps`. The inventory
must determine whether C77 implementation should rename
`valid_time_boundaries` to `fact_boundaries`, add a new `time_binned` mode, keep
or remove `fixed_timesteps`, and whether those changes should be one
implementation cycle or split across T10-3-A/T10-3-B.

T10-3 should not start implementation until the current temporal carrier,
adapter consumption, and compatibility policy are source-backed. It must also
avoid regressing the already-shipped T10-2-A C78 and T10-2-B C74 slices.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md` | Parent T10 staged-hybrid split and C77 deferred classification. |
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md` | T10-2 split / fixed-timesteps decoupling source. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | Shipped C78 `iteration_count` behavior and compatibility policy. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | Shipped C74 canonical carrier/lowering pattern and T10-2-B invariants. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C77 / temporal projection canonical design anchor. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | Current roadmap overlay and T10/T8-C dependency framing. |
| `src/factgraph/sdk/semantics.py` | Public `PyReasonSemantics` wrapper surface. |
| `src/factgraph/sdk/store.py` | SDK wrapper -> `SemanticsProfile` lowering. |
| `src/factgraph/core/semantics/profile.py` | Canonical `SemanticsProfile.temporal_projection` substrate and validation. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | PyReason temporal projection / timesteps consumer. |
| PyReason tests | Focused regression baseline and current temporal behavior fixtures. |
| Four untracked active design-point files | Read-only overlap check only. |

## 3. Step 4.6 Source-Backed Inventory Skeleton

### 3.1 Current Temporal Projection State

Pending Step 4.6 source-back:

- Enumerate current `temporal_projection` modes in `SemanticsProfile`.
- Source-back SDK `PyReasonSemantics.temporal_projection` shell and validation.
- Source-back SDK lowering into `SemanticsProfile.temporal_projection`.
- Source-back adapter functions:
  - `_resolve_temporal_projection_state(...)`
  - `_materialize_valid_time_boundaries(...)`
  - `_engine_options_with_temporal_projection(...)`
- Identify which parts now belong to C78 compatibility after T10-2-A and which
  parts are true C77 temporal behavior.

### 3.2 C77 Canonical Design Source-Back

Pending Step 4.6 source-back:

- Locate C77 design anchor in `rule-expression-and-proof-attempt.zh.md`.
- Extract canonical names and intended semantics:
  - `fact_boundaries`
  - `time_binned`
  - any relation to legacy `valid_time_boundaries`
  - any relation to legacy `fixed_timesteps`
- Determine whether C77 is purely a rename/alias issue, a new-mode issue, or
  both.

### 3.3 `valid_time_boundaries` -> `fact_boundaries` Rename Policy

Pending Step 4.6 source-back:

- Compare policy candidates:
  - hard rename
  - alias with deprecation window
  - dual support through T10-3
  - defer rename and ship only docs/source-back
- Identify conflict behavior if both legacy and canonical names are supplied.
- Record whether T10-3 implementation should reject, prefer canonical, or
  preserve both.

### 3.4 `time_binned` New Mode Design

Pending Step 4.6 source-back:

- Determine whether `time_binned` is a real new mode or a spelling of existing
  valid-time boundaries behavior.
- Map it against shipped modes:
  - `none`
  - `fixed_timesteps`
  - `valid_time_boundaries`
- Determine adapter consumption shape and whether PyReason engine_eval already
  has enough substrate.

### 3.5 Legacy `fixed_timesteps` Disposition

Pending Step 4.6 source-back:

- Use T10-2-A archive to lock what already shipped:
  - canonical `iteration_count`
  - omission rule
  - conflict with legacy temporal timesteps modes
  - no warning in T10-2-A
- Decide what T10-3 owns now:
  - leave `fixed_timesteps` as compatibility alias
  - deprecate / warn
  - remove from `temporal_projection`
  - narrow to tests/docs-only policy

### 3.6 T10-3 Split Candidates and T8-C-2 Unblock

Pending Step 4.6 source-back:

- Compare split options:
  - single T10-3 implementation
  - T10-3-A `fact_boundaries` rename, then T10-3-B `time_binned`
  - T10-3-A compatibility cleanup, then T10-3-B new temporal mode
  - other shape Step 4.6 finds
- Update T8-C-2 PyReason evidence unblock map:
  - after T10-2-A and T10-2-B, does T10-3 remove the last semantics gate?
  - does D11/Form 2 remain the only non-semantics gate?

### 3.7 Shipped PyReason Invariants

Pending Step 4.6 source-back:

- T10-2-A C78 invariants:
  - SDK field.
  - profile carrier.
  - lowering omission rule.
  - adapter consumption.
  - dual conflict helpers.
  - error wording distinct from `timestep_delay`.
- T10-2-B C74 invariants:
  - SDK `derived_bound` / `atom_bounds`.
  - `rule_projection["pyreason"]` carrier reuse.
  - SDK atom-id conversion.
  - asymmetric conflict policy.
  - no T8-B witness-key reuse.
  - error wording distinct from `iteration_count`, `timestep_delay`,
    `head_bound`, and `branch_bounds`.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What is C77's current ship state across SDK shell, SDK lowering, profile carrier, and adapter consumption? | Layer table with `fact_boundaries`, `time_binned`, and legacy `valid_time_boundaries` / `fixed_timesteps` called out separately. |
| Q2 | What policy should govern `valid_time_boundaries` -> `fact_boundaries`? | Rename / alias / deprecate / removal decision with conflict behavior. |
| Q3 | What is the `time_binned` mode design and relationship to existing modes? | Source-backed mode semantics and adapter consumption shape. |
| Q4 | What should happen to legacy `fixed_timesteps` in T10-3? | Preserve / deprecate / remove / narrow decision, explicitly tied to T10-2-A. |
| Q5 | What is the T10-3 implementation split? | Single cycle versus T10-3-A/B and rationale. |
| Q6 | After T10-3 ships, does T8-C-2 PyReason evidence only lack D11/Form 2? | Updated unblock map. |
| Q7 | Do the four untracked design-point files overlap T10-3 strongly? | Four-file grep classification; stop if blocking. |
| Q8 | Do T10-2-A or T10-2-B shipped behaviors have hidden coupling with C77? | Explicit invariant and coupling assessment. |
| Q9 | Are there behavior changes that need warning, like T10-2-A's default timesteps 2 -> 1? | Closure-note candidates and default/compatibility changes. |
| Q10 | Are there stop/amend findings? | Yes/no with trigger-by-trigger status. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- T10-2-A C78 `iteration_count`: SDK field, profile carrier, lowering omission
  rule, adapter consumption, dual conflict helpers, and error wording.
- T10-2-B C74 canonical rule params: SDK `derived_bound` / `atom_bounds`,
  `rule_projection["pyreason"]` carrier reuse, SDK atom-id conversion,
  asymmetric conflict policy, no T8-B witness-key reuse, and distinct error
  wording.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10 inventory, T10-2 inventory Q1-Q8, T10-2-A scoped decisions, and T10-2-B
  scoped decisions remain locked unless this inventory stops and amends the
  relevant archive.
- Existing `timestep_delay`, `head_bound`, `branch_bounds`, and
  `iteration_count` behavior.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "temporal_projection|valid_time_boundaries|fact_boundaries|time_binned" src/factgraph workflow/design workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md
rg -n "C77|fixed_timesteps|_materialize_valid_time_boundaries|_resolve_temporal_projection_state" src/factgraph workflow/design
rg -n "PyReason|temporal|fact_boundaries|time_binned|C77" workflow/design/design-points/active/append-only-ledger-evaluation.zh.md workflow/design/design-points/active/identity-and-data-model-redesign.zh.md workflow/design/design-points/active/identity-mechanism-redesign.zh.md workflow/design/design-points/active/ledger-schema-specification.zh.md
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Current C77 layer table.
2. Canonical design anchor table.
3. Rename / alias / removal policy for `valid_time_boundaries`.
4. `time_binned` design classification.
5. `fixed_timesteps` T10-3 disposition.
6. Implementation split recommendation.
7. T8-C-2 unblock update.
8. Four-file design-point overlap classification.
9. Stop/amend assessment.

## 7. Proposed Output Shape

Blueprint-only inventory, matching the T10-2 inventory and T8-C-1 inventory
Option B shape. Durable output is the archived blueprint/audit pair. No runtime
code, test code, user docs, audit docs, or design-point note should be created
unless Step 4.6 proves an upstream archive amendment is required.

Candidate chain:

1. `docs(blueprint): draft T10-3 PyReason temporal inventory`
2. `docs(blueprint): scope T10-3 PyReason temporal inventory`
3. `docs(blueprint): close T10-3 PyReason temporal inventory`
4. `docs(blueprint): archive T10-3 PyReason temporal inventory`

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q10 answered.
- [ ] C77 current layer state recorded.
- [ ] `valid_time_boundaries` -> `fact_boundaries` policy recorded.
- [ ] `time_binned` design and split recommendation recorded.
- [ ] `fixed_timesteps` disposition recorded.
- [ ] T8-C-2 unblock map updated.
- [ ] Four untracked design-point files classified as blocking or adjacent.
- [ ] T10-2-A and T10-2-B invariants preserved.
- [ ] No runtime, test, user-doc, audit-doc, governance, sacred, or dirty
  baseline files touched.
- [ ] `git diff --check` clean.
- [ ] Focused PyReason no-op baseline remains `90 OK`.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Design-only no-op verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / closure.
