# Task Blueprint: T10-3-B PyReason Time Binned Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-3-b-time-binned-migration.audit.md`
- Trigger: T10-3 inventory archived at `da896f0c` selected the
  T10-3-A / T10-3-B split and classified `time_binned` as a true new C77 mode
  requiring `bin_size` validation and a new binned materializer. T10-3-A
  shipped at `e7bab90f`, proving the dynamic temporal carrier pattern and
  locking `fact_boundaries` alias behavior. T10-2-A shipped at `65cc79a3`,
  locking canonical C78 `iteration_count` and iteration/temporal conflict
  behavior. T10-2-B shipped at `92fd6013`, locking C74 canonical rule params
  and the PyReason lowering / adapter-consumption pattern. `workflow/memory/current.md`
  lists T10-3-B `time_binned` as next work #1.

## 0. Scope Locks

### In scope

This is a runtime implementation cycle for the T10-3-B C77 `time_binned` slice.

1. Profile carrier extension:
   - Extend `SemanticsProfile._normalize_temporal_projection` to accept
     `time_binned`.
   - Validate `time_binned` `universe` and `bin_size`.
2. Strict `bin_size` whitelist:
   - Accept only source-backed ISO 8601 duration forms such as `P1D` / `PT1H`
     and a small explicit short-form whitelist such as `1d`, `1h`, `15m`, `1m`.
   - Reject arbitrary human-readable strings such as `1 month` or
     `approximately a week`.
   - Step 4.6 must source-back the exact accepted set from the design anchor and
     current implementation constraints.
3. New `_materialize_time_binned(...)` materializer:
   - Input: `universe` and `bin_size`.
   - Output: existing `_TemporalProjectionState` shape with
     `active_by_asrt_id` and `timesteps`.
   - Compute ordered bin boundaries.
   - Map fact valid-time ranges to bin indexes.
   - Do not reuse `_materialize_valid_time_boundaries(...)` unchanged unless
     Step 4.6 proves T10-3 inventory was wrong.
4. Adapter consumption extension:
   - Extend `_resolve_temporal_projection_state(...)` with a `time_binned`
     branch.
   - Reuse T10-3-A's dynamic carrier pattern.
   - Reuse `_reject_iteration_temporal_conflict(...)` and
     `_reject_temporal_timesteps_conflict(...)`.
5. Conflict behavior symmetry:
   - `time_binned` plus canonical `iteration_count` must reject, symmetric with
     `fact_boundaries` and legacy `valid_time_boundaries`.
   - Error messages must name `SemanticsProfile.temporal_projection.time_binned`.
6. Focused tests:
   - Profile accepts `time_binned` with `bin_size` and `universe`.
   - `bin_size` validation accepts the chosen ISO / short whitelist and rejects
     arbitrary human-readable strings.
   - New materializer maps facts to bin indexes correctly and computes bin
     boundaries / `timesteps`.
   - `time_binned` conflicts with canonical `iteration_count`.
   - Existing `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps`
     behavior remains green.
   - T10-3-A, T10-2-A, and T10-2-B invariants remain green.
   - Full discover delta is compared against baseline
     `2029 tests / 72 failures / 231 errors`.

### Out of scope

- T10-3-A `fact_boundaries` alias behavior; do not weaken, redo, or roll it back.
- `fixed_timesteps` removal, deprecation, or warning. T10-3 inventory Q4
  preserved compatibility; cleanup remains a later cycle.
- T10-2-A C78 `iteration_count` behavior; do not weaken, redo, or roll it back.
- T10-2-B C74 `derived_bound`, `atom_bounds`, atom-id conversion, asymmetric
  conflict policy, or `rule_projection["pyreason"]` carrier behavior; do not
  weaken, redo, or roll it back.
- C76 ProbLog or ProbLog adapter work.
- T8-C-2 PyReason evidence enrichment.
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
- Audit module docs; T10-3-B changes adapter execution semantics, not evidence
  module behavior.
- User-facing docs; a future T8-D round can teach PyReason canonical temporal
  semantics after T10-3-A/B ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including the four untracked active
  design-point files.
- Reopening T10 inventory, T10-2 inventory, T10-2-A, T10-2-B, T10-3 inventory,
  or T10-3-A decisions. If implementation contradicts an archive, stop and
  amend the relevant archive instead of silently diverging.
- Absorbing or classifying any untracked design-point file.
- Accepting arbitrary human-readable duration strings outside the source-backed
  `bin_size` whitelist.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

1. T10-3 inventory §3.4 is wrong and `time_binned` does not need a new
   materializer.
2. The source-backed `bin_size` whitelist cannot cover the intended v1 use cases.
3. The new materializer cannot reuse `_TemporalProjectionState` output shape.
4. `time_binned` conflict behavior cannot remain symmetric with T10-3-A
   `fact_boundaries` conflict behavior.
5. SDK shell changes are required. T10-3 inventory classified the SDK shell as
   generic pass-through.
6. Existing `fact_boundaries`, `valid_time_boundaries`, or `fixed_timesteps`
   behavior must change.
7. Runtime/test/user-doc/governance/sacred/dirty-baseline files outside this
   cycle's planned implementation surface need edits, or T10-3-A / T10-2-A /
   T10-2-B shipped behavior would be weakened.
8. Any untracked design-point file needs adoption or classification before
   T10-3-B.

## 1. Problem

T10-3 inventory classified `time_binned` as the true new C77 temporal mode after
the smaller T10-3-A `fact_boundaries` alias slice. T10-3-A is now shipped:
canonical and legacy valid-time boundary spellings share the existing
valid-time materialization substrate and dynamic conflict carrier behavior.

T10-3-B must add the remaining canonical C77 runtime behavior: profile
validation for `time_binned`, strict `bin_size` validation, a new binned
materializer, adapter consumption, conflict tests, and composition-shift
verification. It must not reopen T10-3-A alias behavior or any shipped T10-2-A /
T10-2-B behavior.

The main design risks are `bin_size` validation scope and temporal materializer
semantics: how bin boundaries are computed, how facts that span bins become
active, and what happens when `universe` is not evenly divisible by `bin_size`.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t10-3-pyreason-temporal-migration-inventory.md` | Parent inventory; `time_binned` design, split decision, and invariant manifest. |
| `workflow/blueprints/archive/2026-05-28_t10-3-pyreason-temporal-migration-inventory.audit.md` | Review record and implementation pings for `bin_size`, fixed-timesteps, and invariants. |
| `workflow/blueprints/archive/2026-05-28_t10-3-a-fact-boundaries-migration.md` | Shipped `fact_boundaries` alias behavior and dynamic carrier precedent. |
| `workflow/blueprints/archive/2026-05-28_t10-3-a-fact-boundaries-migration.audit.md` | T10-3-A review notes and verification baseline. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | C78 `iteration_count` and iteration/temporal conflict precedent. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | C74 invariants and PyReason lowering / adapter-consumption precedent. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C77 canonical design anchor for `time_binned` and `bin_size`. |
| `src/factgraph/core/semantics/profile.py` | `SemanticsProfile.temporal_projection` validation and mode normalization. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | PyReason temporal projection consumption and materializers. |
| `tests/test_pyreason_semantics_profile_migration.py` | Existing T10-2-A, T10-2-B, T10-3-A, and temporal projection tests. |
| `tests/test_pyreason_engine_eval.py`, `tests/test_pyreason_rule_ext.py`, `tests/test_pyreason_evidence_graph.py` | Focused PyReason regression gate. |

## 3. Step 4.6 Source-Backed Implementation Plan

### 3.1 `bin_size` Strict Whitelist Design

Step 4.6 must source-back:

- The exact ISO 8601 duration subset allowed for v1.
- The exact short-form whitelist allowed for v1.
- Whether all accepted durations can be represented without month/year
  ambiguity.
- Error wording for invalid `bin_size`, including rejection of arbitrary
  human-readable strings.

Draft expectation from T10-3 inventory: accept explicit, unambiguous day/hour
and minute forms; reject ambiguous month/year and prose durations. If the design
anchor requires broader ISO support, Step 4.6 must record the parser scope and
test matrix before implementation.

### 3.2 Profile `_normalize_temporal_projection` Extension

Step 4.6 must source-back the minimal profile changes:

- Add `time_binned` to `_normalize_temporal_projection`.
- Reuse the existing valid-time `universe` validation if it is semantically
  identical, or factor a shared universe validator if direct reuse would force
  wrong `mode` semantics.
- Add `bin_size` validation and normalized output shape.
- Preserve existing `none`, `fixed_timesteps`, `valid_time_boundaries`, and
  `fact_boundaries` behavior.
- Do not touch public SDK shell unless a stop trigger fires.

### 3.3 New `_materialize_time_binned` Materializer Design

Step 4.6 must source-back the algorithm before code:

1. Parse `universe` start/end values.
2. Parse / normalize `bin_size`.
3. Compute ordered bin boundaries and final bin count.
4. Decide whether a non-divisible final partial bin is accepted or rejected.
5. Map fact valid-time ranges to active bin indexes.
6. Return `_TemporalProjectionState(active_by_asrt_id=..., timesteps=...)`.

The materializer may share parsing helpers with valid-time materialization, but
it must not pretend `time_binned` is a spelling alias for
`valid_time_boundaries`. T10-3 inventory classified it as a true new mode.

### 3.4 Adapter `_resolve_temporal_projection_state` Extension

Step 4.6 must identify the exact branch point in
`_resolve_temporal_projection_state(...)`:

- Add a `time_binned` mode branch.
- Use `carrier = f"SemanticsProfile.temporal_projection.{mode}"`, matching
  T10-3-A dynamic carrier behavior.
- Reuse `_reject_iteration_temporal_conflict(...)`.
- Reuse `_reject_temporal_timesteps_conflict(...)` when materialized timesteps
  conflicts with `engine_options["timesteps"]`.
- Preserve `fixed_timesteps`, `valid_time_boundaries`, and `fact_boundaries`
  paths.

### 3.5 Conflict Behavior Symmetry

`time_binned` must reject explicit canonical `iteration_count` the same way
`fact_boundaries` and `valid_time_boundaries` do. The error message must name:

- `SemanticsProfile.iteration_count`
- `SemanticsProfile.temporal_projection.time_binned`

No silent winner policy is allowed.

### 3.6 Test Matrix

Expected implementation test surface:

1. Profile accepts `time_binned` with valid `universe` and `bin_size`.
2. `bin_size` accepts source-backed ISO 8601 forms.
3. `bin_size` accepts source-backed short whitelist forms.
4. `bin_size` rejects arbitrary human-readable / ambiguous strings.
5. `_materialize_time_binned` maps single-bin facts correctly.
6. `_materialize_time_binned` maps facts spanning multiple bins correctly.
7. Edge behavior for non-divisible `universe` / `bin_size` is tested according
   to the Step 4.6 decision.
8. `time_binned` plus `iteration_count` rejects with canonical carrier names.
9. Existing `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps`
   tests remain green.
10. Existing T10-2-A C78 and T10-2-B C74 tests remain green.
11. Full discover composition is compared against
    `2029 tests / 72 failures / 231 errors`.

### 3.7 Shipped Invariants

T10-3-B must preserve a 14-item manifest:

T10-2-A:

1. SDK `PyReasonSemantics.iteration_count: int = 1` with positive-int validation.
2. Optional top-level `SemanticsProfile.iteration_count`.
3. Lowering omission rule for default `1` plus legacy temporal mode.
4. Adapter consumption mapping canonical `iteration_count` to run timesteps.
5. Explicit conflicts with `fixed_timesteps` and `valid_time_boundaries`.
6. No-profile engine default timesteps remains 2.

T10-2-B:

1. SDK `derived_bound` / `atom_bounds` validation.
2. `rule_projection["pyreason"]` carrier reuse.
3. SDK atom-id conversion to `body_atom:0:<index>`.
4. Legacy Inference / missing application atom ids reject canonical
   `atom_bounds`.
5. Asymmetric conflict policy for `derived_bound` / `head_bound` and
   `atom_bounds` / `branch_bounds`.
6. No T8-B witness-key reuse.

T10-3-A:

1. `fact_boundaries` accepted as canonical alias while preserving normalized
   input spelling.
2. `fact_boundaries` dynamic carrier appears in iteration conflict messages.

Step 4.6 must replace this draft manifest with source-backed line refs or
state why the existing T10-3-A archive line refs remain sufficient.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What exact `bin_size` whitelist should v1 accept? | Source-backed ISO subset and short-form set; explicit rejected examples. |
| Q2 | What profile validation shape should `time_binned` use? | `mode`, `universe`, `bin_size` normalized shape and error wording. |
| Q3 | What is the `_materialize_time_binned` algorithm and edge-case policy? | Ordered algorithm, partial-bin decision, fact-span mapping semantics. |
| Q4 | How much of T10-3-A's dynamic carrier pattern is reused? | Exact adapter branch and helper reuse map. |
| Q5 | Is `time_binned` conflict behavior fully symmetric with `fact_boundaries`? | Reject policy and error-message requirements. |
| Q6 | What tests cover whitelist, materializer, conflict behavior, and invariants? | Test matrix with existing regression anchors. |
| Q7 | What implementation split should be used? | 4-5 implementation commit plan or scoped merge rationale. |
| Q8 | How does T10-3-B update the T8-C-2 unblock map? | After T10-3-B, C74/C77/C78 semantics gates should be complete; D11/Form 2 remain. |
| Q9 | What behavior changes must closure warn about? | Bin boundary semantics, partial-bin behavior, and new materialization behavior. |
| Q10 | Are there stop/amend findings? | Trigger-by-trigger assessment. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- T10-2-A C78 `iteration_count`: SDK field, profile carrier, lowering omission
  rule, adapter consumption, dual conflict helpers, and distinct error wording.
- T10-2-B C74 canonical rule params: SDK `derived_bound` / `atom_bounds`,
  `rule_projection["pyreason"]` carrier reuse, SDK atom-id conversion,
  asymmetric conflict policy, no T8-B witness-key reuse, and distinct error
  wording.
- T10-3-A `fact_boundaries` alias acceptance and dynamic carrier conflict
  wording.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10 inventory, T10-2 inventory, T10-2-A, T10-2-B, T10-3 inventory, and
  T10-3-A remain locked unless this cycle stops and amends the relevant archive.
- Existing `timestep_delay`, `head_bound`, `branch_bounds`, `iteration_count`,
  `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps` behavior.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "time_binned|bin_size|fact_boundaries|valid_time_boundaries" src/factgraph workflow/design workflow/blueprints/archive/2026-05-28_t10-3-pyreason-temporal-migration-inventory.md
rg -n "_normalize_temporal_projection|_materialize_valid_time_boundaries|_resolve_temporal_projection_state" src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py
rg -n "PT1H|P1D|ISO 8601|duration" workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md
rg -n "fact_boundaries|time_binned" tests/test_pyreason_semantics_profile_migration.py
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
PYTHONPATH=src python -m unittest discover tests
ruff check src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. `bin_size` whitelist and parser scope.
2. Profile validation plan.
3. New materializer algorithm and edge-case policy.
4. Adapter branch/helper plan.
5. Conflict symmetry decision.
6. Test matrix.
7. 14-item invariant preservation map.
8. Behavior-change warning.
9. Stop/amend assessment.

## 7. Implementation Split

Candidate chain:

1. `docs(blueprint): draft T10-3-B time_binned migration`
2. `docs(blueprint): scope T10-3-B time_binned migration`
3. `feat(profile): accept time_binned with bin_size whitelist`
4. `feat(pyreason): materialize time_binned temporal projection`
5. `feat(pyreason): consume time_binned in temporal projection state`
6. `test(pyreason): cover time_binned migration`
7. `docs(blueprint): close T10-3-B time_binned migration`
8. `docs(blueprint): archive T10-3-B time_binned migration`

Commits 3-4 or 4-5 may combine only if Step 4.6 finds the materializer and
adapter surface are smaller than expected and the audit records why the
anti-partial-ship risk remains controlled.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed plan completed.
- [ ] Q1-Q10 answered.
- [ ] Profile accepts `time_binned` with strict `bin_size` validation.
- [ ] New binned materializer shipped.
- [ ] Adapter consumes `time_binned` through the new materializer.
- [ ] `time_binned` + canonical `iteration_count` conflict behavior tested.
- [ ] Legacy `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps`
  behavior preserved.
- [ ] T10-3-A, T10-2-A, and T10-2-B invariants preserved.
- [ ] T10-3 inventory decisions preserved.
- [ ] T8-A/B/C-1/D and T10-1 invariants preserved.
- [ ] `git diff --check` clean.
- [ ] Focused PyReason tests pass.
- [ ] Full discover delta compared against
  `2029 tests / 72 failures / 231 errors`.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Runtime implementation verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
PYTHONPATH=src python -m unittest discover tests
ruff check src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
