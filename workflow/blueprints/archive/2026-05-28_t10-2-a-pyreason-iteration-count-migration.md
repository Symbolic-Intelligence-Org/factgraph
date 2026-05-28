# Task Blueprint: T10-2-A PyReason Iteration Count Migration

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.audit.md`
- Trigger: T10-2 inventory archived at `f8e08905` selected Option C:
  T10-2-A ships C78 canonical `iteration_count` before T10-2-B C74 atom-bound
  conversion. The same inventory confirmed C78 is missing at SDK/profile/adapter
  layers and that legacy `fixed_timesteps` can be decoupled from C77 temporal
  projection. T10-1 C76 shipped at `cde072fa`, providing the prior three-layer
  adapter-semantics implementation pattern.

## 0. Scope Locks

### In scope

This is a runtime implementation cycle for C78 only.

1. SDK shell:
   - Add `PyReasonSemantics.iteration_count: int = 1`.
   - Validate type and value according to Step 4.6.
   - Preserve existing `timestep_delay` semantics as per-rule delay, distinct
     from global inference round count.
2. SDK lowering:
   - Lower canonical `iteration_count` into `SemanticsProfile` using the
     Step 4.6-selected carrier.
   - Candidate carriers to source-back and decide:
     - Option A: new canonical `SemanticsProfile.iteration_count` field.
     - Option B: existing generic `engine_options["iteration_count"]`.
3. `SemanticsProfile` carrier:
   - Implement the selected carrier with validation.
   - Do not change EvidenceGraph metadata, row-result metadata, or existing
     `engine_options` semantics beyond the selected C78 path.
4. Adapter consumption:
   - Update `src/factgraph/adapters/pyreason/engine_eval.py` so canonical
     `iteration_count` is read first.
   - Fall back to legacy `temporal_projection.fixed_timesteps` only when
     canonical `iteration_count` is absent.
   - Define and implement explicit conflict behavior when canonical and legacy
     carriers are both supplied.
5. Legacy `fixed_timesteps` compatibility policy:
   - Choose alias / deprecate / warning behavior in Step 4.6.
   - Preserve legacy mode acceptance in this cycle unless Step 4.6 proves a
     stop/amend trigger. T10-3 owns eventual removal/narrowing.
6. Focused tests:
   - Canonical SDK shell / lowering / profile carrier.
   - Adapter consumption.
   - Canonical + legacy conflict.
   - Legacy `fixed_timesteps` regression.
   - Existing PyReason rule extension behavior remains intact.

### Out of scope

- C74: `derived_bound`, `atom_bounds`, full atom-id conversion, `head_bound`,
  and `branch_bounds` compatibility policy are T10-2-B.
- C77 temporal rename / `fact_boundaries` / `time_binned`; T10-3 owns temporal
  projection migration.
- C76 ProbLog / ProbLog adapter work; T10-1 already shipped it.
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
- Audit module docs; T10-2-A changes adapter execution semantics, not evidence
  module behavior.
- User-facing docs; T8-D round 4 can follow after T10-2-A and T10-2-B ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including the four untracked active
  design-point files.
- Reopening T10-2 inventory Q1-Q8. If implementation contradicts the archived
  inventory, stop and amend that inventory instead of silently diverging.
- Absorbing or classifying any untracked design-point file.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

1. T10-2 inventory's C78 four-layer state is materially wrong.
2. T10-2 inventory's `fixed_timesteps` decoupling assessment is wrong and C78
   cannot ship independently from C77.
3. SDK shell, lowering, carrier, or adapter consumption requires changing
   14-key metadata, `EvidenceGraph` DTO, or protocol evidence schemas.
4. The selected canonical carrier would break existing `SemanticsProfile`
   invariants or existing `engine_options` behavior.
5. Canonical + legacy conflict handling would require silent winner semantics
   instead of explicit rejection or explicit compatibility.
6. Runtime/test/user-doc/governance/sacred/dirty-baseline files outside this
   cycle's planned implementation surface need edits.
7. Any untracked design-point file needs adoption or classification before C78.

## 1. Problem

C78 defines `PyReasonSemantics.iteration_count: int = 1` as the global PyReason
inference round count. It is orthogonal to fact temporal lifecycle and distinct
from per-rule `timestep_delay`. Current code has no canonical field; instead,
legacy `temporal_projection.fixed_timesteps` is normalized as a temporal mode
and consumed as PyReason engine timesteps. T10-2 inventory selected T10-2-A to
decouple this before C74 atom-bound conversion and before T10-3 temporal
projection migration.

The implementation must avoid a partial ship: SDK shell, lowering/carrier,
adapter consumption, conflict behavior, and tests must land coherently.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md` | Parent inventory; C78 state, decoupling decision, and split order. |
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.audit.md` | Review/audit record for T10-2 split and invariants. |
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md` | Higher-level T10 staged hybrid and C78 missing classification. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C78 design anchor and `fixed_timesteps` migration note. |
| `src/factgraph/sdk/semantics.py` | Public `PyReasonSemantics` shell. |
| `src/factgraph/sdk/store.py` | Public wrapper -> `SemanticsProfile` lowering. |
| `src/factgraph/core/semantics/profile.py` | Candidate carrier location and temporal projection normalization. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | Adapter consumption of `fixed_timesteps` and engine timesteps. |
| `tests/test_pyreason_semantics_profile_migration.py` | Existing fixed-timesteps regression and future C78 tests. |
| `tests/test_pyreason_engine_eval.py`, `tests/test_pyreason_rule_ext.py`, `tests/test_pyreason_evidence_graph.py` | Focused PyReason regression coverage. |

## 3. Step 4.6 Source-Backed Implementation Plan

### 3.1 Canonical Carrier Decision

**Decision: Option A, with an optional top-level `SemanticsProfile.iteration_count` carrier.**

Source-backed state:

| Source | Finding |
|---|---|
| `rule-expression-and-proof-attempt.zh.md:1422-1446` | C78 says `temporal_projection` owns fact lifecycle only, while `iteration_count: int = 1` is the independent global PyReason inference round count. |
| `rule-expression-and-proof-attempt.zh.md:1468-1470` | The old `fixed_timesteps` name must be removed/split: temporal lifecycle and iteration depth are separate concerns. |
| `rule-expression-and-proof-attempt.zh.md:1603` | C78's public shell is `PyReasonSemantics.iteration_count: int = 1`. |
| `profile.py:39-48` | `SemanticsProfile` has top-level semantic carriers (`uncertainty_projection`, `temporal_projection`, `rule_projection`) and generic `engine_options`, but no `iteration_count`. |
| `engine_eval.py:129-155` | `engine_options` currently normalizes adapter-local run config only and supports exactly `timesteps`. Unknown keys are rejected. |

Rationale:

- A top-level carrier keeps C78 in the semantic profile layer, next to
  `temporal_projection`, instead of hiding it inside adapter-local
  `engine_options`.
- Keeping it out of `engine_options` preserves the existing
  `resolve_pyreason_run_config(...)` contract, where `engine_options` remains a
  low-level run-config override accepting `timesteps` only.
- T10-3 can later rename temporal modes without disentangling a canonical C78
  field from generic engine options.

Carrier shape:

- Add `SemanticsProfile.iteration_count: int | None = None`.
- `None` means "canonical C78 carrier absent"; this preserves direct low-level
  `SemanticsProfile(... temporal_projection={"mode": "fixed_timesteps", ...})`
  compatibility tests.
- Public `PyReasonSemantics.iteration_count` remains `int = 1`; the SDK lowering
  decides when to emit the carrier.

Option B (`engine_options["iteration_count"]`) is rejected because it would make
canonical C78 look like an adapter run option and would require widening
`engine_options` validation in `engine_eval.py:139-148`.

### 3.2 SDK Field Shape

**Decision: `PyReasonSemantics.iteration_count: int = 1`, positive int only.**

Source-backed state:

- `sdk/semantics.py:167-172` currently has `timestep_delay`, `head_bound`,
  `branch_bounds`, `rule_params`, `temporal_projection`, and
  `uncertainty_projection`, but no `iteration_count`.
- `sdk/semantics.py:183-186` rejects bool/non-int `timestep_delay` and allows
  `timestep_delay >= 0`.
- `engine_eval.py:146-148` already requires PyReason run `timesteps` to be a
  positive int.

Implementation lock:

- Add `iteration_count: int = 1` after `timestep_delay`.
- Reject bool and non-int with wording naming `PyReasonSemantics.iteration_count`.
- Reject values `< 1`. Do not allow `0`; zero inference rounds would not match
  the current positive-int PyReason run-config boundary.
- Error wording must not mention `timestep_delay`. `timestep_delay` remains a
  per-rule delay with `>= 0` validation; `iteration_count` is global and
  positive.

### 3.3 SDK Lowering Path

Source-backed state:

- `_preview_public_semantics(...)` lowers PyReason wrappers at
  `sdk/store.py:3375-3396`.
- `_lower_public_semantics(...)` lowers runtime PyReason wrappers at
  `sdk/store.py:3433-3465`.
- Both paths currently pass `rule_projection`, `temporal_projection`, and
  `uncertainty_projection`, but no `iteration_count`.

Implementation lock:

- Add a small helper for the PyReason wrapper lowering path:
  - emit `iteration_count=value.iteration_count` when
    `value.temporal_projection["mode"] == "none"`;
  - emit `iteration_count=value.iteration_count` when
    `value.iteration_count != 1`;
  - omit the carrier when the only C78 value is the SDK's implicit default `1`
    and a legacy temporal timesteps mode is present.
- The omission rule is a compatibility bridge: existing legacy
  `fixed_timesteps` wrapper usage should remain a fallback unless the user gives
  an explicit non-default canonical round count.
- Direct `SemanticsProfile(iteration_count=...)` still represents an explicit
  canonical carrier.

This keeps `PyReasonSemantics()` canonical by default for ordinary usage while
avoiding a false conflict for legacy `fixed_timesteps` users who never opted
into C78.

### 3.4 Adapter Consumption

Source-backed state:

- `_resolve_temporal_projection_state(...)` currently consumes
  `temporal_projection.fixed_timesteps` at `engine_eval.py:301-308`.
- `valid_time_boundaries` can also derive timesteps at `engine_eval.py:309-323`.
- `_engine_options_with_temporal_projection(...)` writes temporal-derived
  timesteps into effective `engine_options` at `engine_eval.py:327-336`.
- `_reject_temporal_timesteps_conflict(...)` currently rejects only differing
  temporal vs `engine_options.timesteps` values at `engine_eval.py:339-351`.

Implementation lock:

- Add a canonical iteration resolver that reads
  `semantics_profile.iteration_count`.
- If canonical iteration is present and `temporal_projection.mode == "none"`,
  write `engine_options["timesteps"] = iteration_count`.
- If canonical iteration is present and `temporal_projection.mode ==
  "fixed_timesteps"`, reject explicit conflict before constructing run options.
- If canonical iteration is absent, keep current legacy behavior exactly:
  `fixed_timesteps` and `valid_time_boundaries` continue through
  `_resolve_temporal_projection_state(...)`.
- Preserve existing no-profile behavior: `tests/test_pyreason_engine_eval.py`
  still expects default config timesteps `2` when no semantics profile or
  engine options are supplied (`:355-377`).

### 3.5 Conflict Behavior And Compatibility Policy

**Decision: alias/fallback compatibility for legacy `fixed_timesteps`, explicit reject for real dual carriers.**

Rules:

- `SemanticsProfile(iteration_count=N, temporal_projection={"mode":
  "fixed_timesteps", "timesteps": M})` rejects, even if `N == M`. This prevents
  dual source-of-truth configuration.
- `PyReasonSemantics(temporal_projection={"mode": "fixed_timesteps", ...})`
  with the implicit default `iteration_count=1` omits the canonical carrier
  during lowering and therefore remains a legacy alias/fallback.
- `PyReasonSemantics(iteration_count=N, temporal_projection={"mode":
  "fixed_timesteps", ...})` where `N != 1` lowers the canonical carrier and
  rejects the conflict.
- Existing direct low-level `engine_options={"timesteps": ...}` without a
  semantics profile remains valid (`tests/test_pyreason_semantics_profile_migration.py:498-514`).

T10-1 discipline reference: ProbLog raises explicitly for configured reject
policy at `problog_export.py:280-283`. C78's default is not reject, but explicit
dual carriers are similarly unsafe and must not silently choose a winner.

No warning is added in T10-2-A. Python warning policy would be a separate API
surface; this cycle records compatibility through tests and explicit errors.

### 3.6 Test Matrix

Focused baseline:

- `PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration`
- Result at Step 4.6: **78 OK**.

New/updated test coverage:

1. SDK accepts `PyReasonSemantics()` and exposes `iteration_count == 1`.
2. SDK rejects bool / non-int / zero / negative `iteration_count`, with error
   wording naming `iteration_count`.
3. Preview/runtime lowering emits canonical `SemanticsProfile.iteration_count`
   for default `PyReasonSemantics()` and for explicit non-default values.
4. `SemanticsProfile(iteration_count=...)` validates positive ints and rejects
   bool / non-int / zero.
5. Adapter uses canonical `iteration_count` to drive `PyReasonRunConfig.timesteps`.
6. Existing fixed-timesteps tests at
   `tests/test_pyreason_semantics_profile_migration.py:271-327` remain passing.
7. Canonical + legacy fixed_timesteps conflict raises and mentions both
   `iteration_count` and `fixed_timesteps`.
8. Existing no-profile engine option behavior remains passing:
   `tests/test_pyreason_engine_eval.py:355-401` and
   `tests/test_pyreason_semantics_profile_migration.py:498-514`.
9. Existing `timestep_delay`, `head_bound`, `branch_bounds`, and rule-extension
   tests remain passing through the focused suite.
10. Full discover after implementation must be compared with
    `2013 tests / 72 failures / 231 errors`.

### 3.7 Anti-Silent-Ignore Boundary

C78 differs from T10-1's ProbLog reject default:

- Missing public SDK `iteration_count` means the SDK default `1`, not an error.
- Missing low-level `SemanticsProfile.iteration_count` means "canonical C78
  carrier absent", so legacy profiles continue to behave as before.
- Explicit canonical + legacy fixed-timesteps dual carriers reject. They do not
  silently merge and do not silently choose a winner.

This boundary must be tested directly: one default success case and one explicit
conflict failure case are required before closure.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which canonical carrier should C78 use: top-level `SemanticsProfile.iteration_count` or `engine_options["iteration_count"]`? | **Option A**: optional top-level `SemanticsProfile.iteration_count: int \| None = None`. Keeps C78 semantic, avoids widening adapter-local `engine_options`, and lets T10-3 reason about temporal projection separately. |
| Q2 | What SDK validation should `PyReasonSemantics.iteration_count` use? | `int = 1`, bool rejected, non-int rejected, values `< 1` rejected. Error wording names global `iteration_count`, distinct from per-rule `timestep_delay`. |
| Q3 | How should SDK lowering emit the carrier? | Emit in preview/runtime PyReason lowering. For compatibility, suppress only the implicit default `1` when a legacy temporal timesteps mode is present; emit default `1` for ordinary `PyReasonSemantics()` and emit explicit non-default values. |
| Q4 | How should adapter consumption prioritize canonical vs legacy carriers? | Canonical carrier drives timesteps when present with temporal mode `none`. Legacy `fixed_timesteps` and `valid_time_boundaries` continue when canonical is absent. |
| Q5 | What is the conflict behavior when canonical and legacy are both specified? | Reject explicit canonical + `fixed_timesteps`; test must assert an error mentioning `iteration_count` and `fixed_timesteps`. |
| Q6 | What is the legacy `fixed_timesteps` compatibility policy? | Alias/fallback in T10-2-A. No warning. T10-3 owns rename/removal policy. Existing fixed_timesteps tests remain regression guards. |
| Q7 | What is the focused test matrix? | The 10-item matrix in §3.6, plus focused PyReason suite and full discover composition comparison. |
| Q8 | What is the implementation commit split? | Keep 4 implementation commits unless LOC is tiny: SDK shell, profile/lowering carrier, adapter consumption/compat, tests. Commits 1-3 may merge only with audit rationale. |
| Q9 | Does T10-2-A change the T8-C-2 unblock map? | It removes the C78/multi-round gate only. T10-2-B C74, T10-3 C77, and D11/Form 2 remain before PyReason evidence implementation. |
| Q10 | Are there stop/amend findings? | None. T10-2 inventory C78 state and decoupling assessment still hold; no archive amendment needed. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10-2 inventory Q1-Q8 decisions, especially Option C split and the
  `fixed_timesteps` decoupling assessment.
- Existing `timestep_delay` behavior: per-rule delay, not global round count.
- Existing `head_bound` / `branch_bounds` behavior; C74 compatibility is
  T10-2-B.
- Existing temporal projection modes `none`, `fixed_timesteps`, and
  `valid_time_boundaries`; T10-3 owns mode rename/removal.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "iteration_count|fixed_timesteps" src/factgraph workflow/design workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md
rg -n "PyReasonSemantics|class SemanticsProfile|engine_options|temporal_projection" src/factgraph/sdk/semantics.py src/factgraph/core/semantics/profile.py
rg -n "_engine_options_with_temporal_projection|_resolve_temporal_projection_state|fixed_timesteps" src/factgraph/adapters/pyreason/engine_eval.py
rg -n "iteration_count" tests/test_pyreason_semantics_profile_migration.py tests/test_pyreason_engine_eval.py
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Carrier decision.
2. SDK validation decision.
3. Lowering and adapter implementation plan.
4. Conflict / compatibility policy.
5. Test matrix.
6. Commit split.
7. Stop/amend assessment.

## 7. Proposed Implementation Split

Candidate commits:

1. `feat(sdk): add PyReasonSemantics.iteration_count`
2. `feat(profile): add canonical PyReason iteration carrier`
3. `feat(pyreason): consume canonical iteration_count`
4. `test(pyreason): cover iteration_count migration`
5. `docs(blueprint): close T10-2-A iteration_count migration`
6. `docs(blueprint): archive T10-2-A iteration_count migration`

If Step 4.6 shows the runtime changes are small, commits 1-3 may be combined
only if the audit records why the three-layer anti-partial-ship risk remains
controlled.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed plan completed.
- [x] Q1-Q10 answered.
- [x] SDK shell shipped.
- [x] SDK lowering / carrier shipped.
- [x] Adapter consumption shipped.
- [x] Legacy `fixed_timesteps` compatibility policy shipped.
- [x] Canonical + legacy conflict behavior tested.
- [x] Existing PyReason behavior preserved.
- [x] T8-A/B/C-1/D and T10-1 invariants preserved.
- [x] T10-2 inventory decisions preserved.
- [x] `git diff --check` clean.
- [x] Focused PyReason tests pass.
- [x] Full discover delta compared against `2013 tests / 72 failures / 231 errors`.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Planned implementation verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
ruff check src/factgraph/sdk/semantics.py src/factgraph/sdk/store.py src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py tests/test_pyreason_engine_eval.py
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Implemented T10-2-A C78 as scoped.

Implementation commits:

1. `8953f3ec` `feat(sdk): add PyReasonSemantics.iteration_count`
   - Added public `PyReasonSemantics.iteration_count: int = 1`.
   - Validation rejects bool, non-int, zero, and negative values.
   - Error wording names `iteration_count` and does not mention `timestep_delay`.
2. `c5cca89b` `feat(profile): add canonical PyReason iteration carrier`
   - Added optional top-level `SemanticsProfile.iteration_count: int | None = None`.
   - Added profile validation and inspection/preview output.
   - Added SDK preview/runtime lowering with the scoped omission rule:
     implicit default `1` is omitted only when a legacy temporal timesteps mode is present.
3. `1742bba2` `feat(pyreason): consume canonical iteration_count`
   - Added canonical adapter consumption into PyReason run `timesteps`.
   - Preserved no-profile engine default behavior.
   - Rejected explicit canonical `iteration_count` with `fixed_timesteps` or
     `valid_time_boundaries`.
   - Reused existing `_reject_temporal_timesteps_conflict(...)` for
     canonical-vs-`engine_options.timesteps`; added a focused helper for
     canonical-vs-temporal-mode conflict.
4. `f8d90307` `test(pyreason): cover iteration_count migration`
   - Added 6 tests covering SDK default/validation, profile validation,
     lowering + omission rule, adapter consumption, `fixed_timesteps` conflict,
     and `valid_time_boundaries` conflict.

Verification:

- Focused PyReason suite: `84 OK` (baseline `78 OK`, +6).
- Full discover: `2019 tests / 72 failures / 231 errors` versus baseline
  `2013 / 72 / 231`, so +6 tests and no failure/error composition regression.
- `ruff check` on touched runtime/test files: clean.
- `git diff --check`: clean.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`.

Notable implementation notes:

- `PyReasonSemantics()` now lowers canonical `iteration_count=1`, so adapter
  execution uses PyReason run `timesteps=1` for that wrapper instead of the old
  no-profile engine default `2`. This is the intentional C78 default; future
  T8-D round 4 user docs should document it.
- Low-level `SemanticsProfile(... temporal_projection={"mode": "fixed_timesteps"})`
  still omits canonical C78 by default and preserves legacy behavior.
- The implementation uses two small conflict helpers: existing
  `_reject_temporal_timesteps_conflict(...)` for run-config `timesteps`
  conflicts, and new `_reject_iteration_temporal_conflict(...)` for canonical
  `iteration_count` vs temporal-mode conflicts. This keeps call sites explicit.
- T10-2-A removes only the C78/multi-round PyReason gate. T10-2-B C74, T10-3
  C77, and D11/Form 2 remain before T8-C-2 PyReason evidence implementation.
