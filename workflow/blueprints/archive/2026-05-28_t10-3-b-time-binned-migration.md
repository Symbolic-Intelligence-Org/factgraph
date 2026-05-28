# Task Blueprint: T10-3-B PyReason Time Binned Migration

- Status: implemented
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

Decision: accept only unambiguous positive day/hour/minute durations for v1.

Source-back:

- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1432`
  shows `time_binned` with `bin_size: "PT1H"`.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1436-1439`
  requires explicit ISO 8601 duration examples such as `P1D`, `PT1H`,
  `PT30M`, and `PT15M`; allows short forms `1d`, `1h`, `15m`, and `1m`; rejects
  arbitrary human-readable strings such as `1 month`; and says accepted values
  may be normalized internally to a duration value.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1602`
  repeats the same whitelist and rejection rule for C77.

Accepted v1 `bin_size` forms:

- ISO subset: `P<n>D`, `PT<n>H`, `PT<n>M`, where `<n>` is a positive integer.
- Short whitelist: exactly `1d`, `1h`, `15m`, and `1m`.

Rejected v1 forms:

- Month/year/seconds/combined/decimal/zero/negative forms such as `P1M`,
  `P1Y`, `PT1S`, `P1DT1H`, `PT1.5H`, `P0D`, and `0d`.
- Arbitrary prose or human-readable strings such as `1 month` or
  `approximately a week`.

The profile should preserve the supplied `bin_size` spelling for inspection;
the adapter materializer should parse it privately to `datetime.timedelta`.
Error wording should name `SemanticsProfile.temporal_projection.time_binned.bin_size`
and should not mention `iteration_count`, `fact_boundaries`, or
`valid_time_boundaries`.

### 3.2 Profile `_normalize_temporal_projection` Extension

Decision: add a `time_binned` branch in
`SemanticsProfile._normalize_temporal_projection(...)` and factor shared
universe validation without touching SDK shell.

Source-back:

- `src/factgraph/core/semantics/profile.py:164-186` currently dispatches
  `none`, `fixed_timesteps`, `valid_time_boundaries`, and `fact_boundaries`.
- `src/factgraph/core/semantics/profile.py:197-213` validates valid-time
  `universe` shape (`[start, end]`, string endpoints, start before end).
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1617`
  defers open universe / auto-from-facts behavior, so `time_binned` should
  require explicit `universe` in this cycle.

Implementation shape:

- Add `_normalize_time_binned(raw)` with allowed keys `mode`, `universe`, and
  `bin_size`.
- Factor the shared `[start, end]` universe validation out of
  `_normalize_valid_time_boundaries(...)` so both valid-boundary modes and
  `time_binned` use identical universe checks.
- Return `{"mode": "time_binned", "universe": [start, end], "bin_size": value}`
  while preserving the supplied `bin_size` spelling.
- Extend the allowed-mode error string to
  `fact_boundaries, fixed_timesteps, none, time_binned, valid_time_boundaries`.
- Do not edit `PyReasonSemantics`; the SDK shell remains generic mapping
  pass-through for temporal projection.

### 3.3 New `_materialize_time_binned` Materializer Design

Decision: implement a new materializer that returns the existing
`_TemporalProjectionState` shape and rejects non-divisible universes.

Source-back:

- T10-3 inventory classified `time_binned` as a true new mode, not a spelling
  alias. The design anchor says `time_binned` is "新增功能, v1 需要实现" at
  `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1471`.
- `src/factgraph/adapters/pyreason/engine_eval.py:35-38` defines the reusable
  `_TemporalProjectionState(timesteps, active_by_asrt_id)` shape.
- `src/factgraph/adapters/pyreason/engine_eval.py:399-434` is valid-boundary
  materialization, which builds boundaries from fact times. `time_binned` must
  instead build fixed-width bins.

Algorithm:

1. Parse the explicit `universe` start/end as temporal instants.
   - Accept ISO dates (`YYYY-MM-DD`) as midnight UTC.
   - Accept aware ISO datetimes with `Z` or explicit offset.
   - Reject naive datetime strings that include time but no timezone.
2. Parse `bin_size` to `datetime.timedelta` using the whitelist in §3.1.
3. Require `universe_end > universe_start`.
4. Require `(universe_end - universe_start)` to be exactly divisible by
   `bin_size`; reject partial final bins for v1. This matches the design's
   strict-parser posture and keeps the first implementation deterministic.
5. Set `timesteps = bin_count`.
6. For each fact in `schema_ir.asrt_ids`:
   - Missing `valid_from` maps to `universe_start`.
   - Missing `valid_to` maps to open-ended `active_to = None`.
   - Present fact times are parsed with the same instant parser.
   - Reject `valid_to <= valid_from`.
   - Reject fact ranges outside the explicit universe; open-ended ranges may
     start within the universe and remain active after the final bin.
   - `active_from` is the floor bin index of `valid_from`.
   - `active_to` is the ceiling bin index of `valid_to`, or `None` when
     `valid_to` is absent.
7. Return `_TemporalProjectionState(active_by_asrt_id=..., timesteps=bin_count)`.

This intentionally differs from `_materialize_valid_time_boundaries(...)`:
valid-boundary mode derives boundaries from facts, while `time_binned` derives
boundaries from the fixed `universe` / `bin_size` grid.

### 3.4 Adapter `_resolve_temporal_projection_state` Extension

Decision: use a distinct `if mode == "time_binned"` adapter branch.

Source-back:

- `src/factgraph/adapters/pyreason/engine_eval.py:282-337` is the temporal mode
  dispatch point.
- T10-3-A already uses a dynamic carrier for valid/fact boundaries at
  `src/factgraph/adapters/pyreason/engine_eval.py:317-335`.
- `src/factgraph/adapters/pyreason/engine_eval.py:376-397` contains the two
  conflict helpers to reuse.

Implementation shape:

- Add the `time_binned` branch after the valid/fact boundary branch.
- Use `carrier = f"SemanticsProfile.temporal_projection.{mode}"`.
- Call `_reject_iteration_temporal_conflict(iteration_count, carrier=carrier)`.
- Call `_materialize_time_binned(...)`.
- If materialized `timesteps` is present, call
  `_reject_temporal_timesteps_conflict(..., carrier=carrier)`.
- Preserve `fixed_timesteps`, `valid_time_boundaries`, and `fact_boundaries`
  branches exactly.

### 3.5 Conflict Behavior Symmetry

Decision: `time_binned` has the same explicit-conflict policy as
`fact_boundaries` and `valid_time_boundaries`.

Source-back:

- `src/factgraph/adapters/pyreason/engine_eval.py:319-322` rejects
  `iteration_count` with `valid_time_boundaries` / `fact_boundaries`.
- `tests/test_pyreason_semantics_profile_migration.py:566-587` verifies the
  `fact_boundaries` conflict message includes the canonical carrier.

T10-3-B must add the same coverage for `time_binned`: the error message names
both `SemanticsProfile.iteration_count` and
`SemanticsProfile.temporal_projection.time_binned`. No silent merge or winner
policy is allowed.

### 3.6 Test Matrix

Required implementation test surface:

1. Profile accepts `time_binned` with valid `universe` and `bin_size`, preserving
   `mode = "time_binned"` and the supplied `bin_size` spelling.
2. `bin_size` accepts ISO subset examples: `P1D`, `PT1H`, `PT30M`, `PT15M`.
3. `bin_size` accepts short whitelist examples: `1d`, `1h`, `15m`, `1m`.
4. `bin_size` rejects arbitrary / ambiguous / unsupported strings:
   `1 month`, `approximately a week`, `P1M`, `P1Y`, `PT1S`, `P1DT1H`, and
   `0d`.
5. `_materialize_time_binned` maps a fact with exact bin-aligned valid times.
6. `_materialize_time_binned` maps a fact spanning multiple bins using
   floor-start / ceil-end semantics.
7. Non-divisible universe / `bin_size` rejects.
8. Fact times outside the explicit universe reject; open-ended facts starting
   inside the universe remain active with `active_to = None`.
9. `time_binned` plus `iteration_count` rejects with canonical carrier names.
10. Existing `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps`
   tests remain green.
11. Existing T10-2-A C78, T10-2-B C74, and T10-3-A alias tests remain green.
12. Full discover composition is compared against
    `2029 tests / 72 failures / 231 errors`.

### 3.7 Shipped Invariants

T10-3-B must preserve a 14-item manifest. Step 4.6 uses current source/test
line refs because T10-3-A inserted tests after the inventory archive.

T10-2-A:

1. SDK `PyReasonSemantics.iteration_count: int = 1` with positive-int
   validation: `tests/test_pyreason_semantics_profile_migration.py:384-397`.
2. Optional top-level `SemanticsProfile.iteration_count`:
   `tests/test_pyreason_semantics_profile_migration.py:398-408`.
3. Lowering omission rule for default `1` plus legacy temporal mode:
   `tests/test_pyreason_semantics_profile_migration.py:410-423`.
4. Adapter consumption mapping canonical `iteration_count` to run timesteps:
   `tests/test_pyreason_semantics_profile_migration.py:483-498`.
5. Explicit conflicts with `fixed_timesteps` and valid-time modes:
   `tests/test_pyreason_semantics_profile_migration.py:520-587`.
6. No-profile engine default timesteps remains 2:
   `tests/test_pyreason_engine_eval.py:355-377`.

T10-2-B:

1. SDK `derived_bound` / `atom_bounds` validation:
   `tests/test_pyreason_semantics_profile_migration.py:293-313`.
2. `rule_projection["pyreason"]` carrier reuse:
   `tests/test_pyreason_semantics_profile_migration.py:315-340`.
3. SDK atom-id conversion to `body_atom:0:<index>`:
   `tests/test_pyreason_semantics_profile_migration.py:315-340`.
4. Legacy Inference / missing application atom ids reject canonical
   `atom_bounds`: `tests/test_pyreason_semantics_profile_migration.py:342-377`.
5. Asymmetric conflict policy for `derived_bound` / `head_bound` and
   `atom_bounds` / `branch_bounds`:
   `tests/test_pyreason_semantics_profile_migration.py:379-410`.
6. No T8-B witness-key reuse:
   `tests/test_pyreason_semantics_profile_migration.py:315-331`.

T10-3-A:

1. `fact_boundaries` accepted as canonical alias while preserving normalized
   input spelling: `tests/test_pyreason_semantics_profile_migration.py:446-453`.
2. `fact_boundaries` dynamic carrier appears in iteration conflict messages.
   `tests/test_pyreason_semantics_profile_migration.py:566-587`.

## 4. Open Questions

| ID | Question | Answer |
|---|---|---|
| Q1 | What exact `bin_size` whitelist should v1 accept? | ISO subset `P<n>D`, `PT<n>H`, `PT<n>M` plus exact short forms `1d`, `1h`, `15m`, `1m`; reject month/year/seconds/combined/decimal/zero/negative/prose forms. |
| Q2 | What profile validation shape should `time_binned` use? | `{"mode": "time_binned", "universe": [start, end], "bin_size": supplied}` with shared universe validation and field-specific `bin_size` errors. |
| Q3 | What is the `_materialize_time_binned` algorithm and edge-case policy? | New fixed-width bin materializer; reject partial final bins; floor valid_from, ceil valid_to; reject out-of-universe bounded ranges; return `_TemporalProjectionState`. |
| Q4 | How much of T10-3-A's dynamic carrier pattern is reused? | Reuse carrier string and both conflict helpers, but use an independent `time_binned` branch because the materializer differs. |
| Q5 | Is `time_binned` conflict behavior fully symmetric with `fact_boundaries`? | Yes. Explicit `iteration_count` plus `time_binned` rejects and names both canonical carriers. |
| Q6 | What tests cover whitelist, materializer, conflict behavior, and invariants? | Add whitelist, reject, materializer, partial-bin, out-of-universe, and conflict tests; keep focused 94 OK regression set and full discover delta baseline. |
| Q7 | What implementation split should be used? | Four impl commits: profile/parser, materializer, adapter, tests; close/archive after review. |
| Q8 | How does T10-3-B update the T8-C-2 unblock map? | After T10-3-B, C74/C77/C78 semantics gates are complete; T8-C-2 still needs D11/Form 2. |
| Q9 | What behavior changes must closure warn about? | New mode semantics: accepted `bin_size` set, exact universe divisibility, fact range bin mapping, and out-of-universe rejection. |
| Q10 | Are there stop/amend findings? | No. All stop triggers are not hit; source-back refined implementation details without contradicting locked archives. |

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

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed plan completed.
- [x] Q1-Q10 answered.
- [x] Profile accepts `time_binned` with strict `bin_size` validation.
- [x] New binned materializer shipped.
- [x] Adapter consumes `time_binned` through the new materializer.
- [x] `time_binned` + canonical `iteration_count` conflict behavior tested.
- [x] Legacy `fact_boundaries`, `valid_time_boundaries`, and `fixed_timesteps`
  behavior preserved.
- [x] T10-3-A, T10-2-A, and T10-2-B invariants preserved.
- [x] T10-3 inventory decisions preserved.
- [x] T8-A/B/C-1/D and T10-1 invariants preserved.
- [x] `git diff --check` clean.
- [x] Focused PyReason tests pass.
- [x] Full discover delta compared against
  `2029 tests / 72 failures / 231 errors`.
- [x] Sacred master and dirty baseline preserved.

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

Implemented and ready for archive.

Implementation commits:

1. `8f80ad7c` `feat(profile): accept time_binned with bin_size whitelist`
   - Added `time_binned` profile mode.
   - Added strict `bin_size` validation for `P<n>D`, `PT<n>H`, `PT<n>M`, and
     exact short forms `1d`, `1h`, `15m`, `1m`.
   - Refactored shared temporal universe validation for valid-time,
     fact-boundary, and time-binned modes.
2. `f6ab296e` `feat(pyreason): materialize time_binned temporal projection`
   - Added `_materialize_time_binned(...)`.
   - Uses microsecond integer arithmetic for exact bin divisibility.
   - Parses ISO dates as midnight UTC and timezone-aware datetimes with `Z` /
     explicit offset; rejects naive datetimes.
   - Implements floor-start / ceil-end fact bin mapping, open-ended facts as
     `active_to=None`, and out-of-universe rejection.
3. `e35abe66` `feat(pyreason): consume time_binned in temporal projection state`
   - Added an independent `time_binned` branch in
     `_resolve_temporal_projection_state(...)`.
   - Reuses T10-3-A dynamic carrier wording and both conflict helpers.
4. `c70574f6` `test(pyreason): cover time_binned migration`
   - Added 9 focused tests covering whitelist acceptance/rejection,
     materialization, divisibility, timezone rejection, conflict behavior, and
     engine-options conflict.

Verification:

- Focused PyReason: `103 OK` (`94 -> 103`, +9 tests).
- Full discover: `2038 tests / 72 failures / 231 errors`
  (`2029 -> 2038`, failures/errors unchanged).
- `ruff check` clean on touched files.
- `git diff --check` clean.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 6 U`.

Implementation notes / deviations:

- The materializer uses integer microsecond arithmetic instead of
  `total_seconds()` floating-point math to avoid divisibility drift.
- Datetime strings with time must include timezone; ISO dates remain accepted as
  midnight UTC.
- `Z` suffixes are normalized to `+00:00` before parsing for compatibility.
- `valid_to == universe_end` is accepted; only `valid_to > universe_end`
  rejects.
- The parser accepts ISO datetimes with either `T` or a space separator; this is
  an ergonomic parser detail, while `bin_size` remains strict.
- T10-3-B completes the T10 canonical PyReason semantics stack; T8-C-2 PyReason
  evidence remains gated on D11/Form 2, not on C74/C77/C78 semantics.
