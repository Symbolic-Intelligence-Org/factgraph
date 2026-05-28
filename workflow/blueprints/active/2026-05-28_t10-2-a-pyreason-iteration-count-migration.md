# Task Blueprint: T10-2-A PyReason Iteration Count Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-2-a-pyreason-iteration-count-migration.audit.md`
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

Pending Step 4.6. Required subsections:

### 3.1 Canonical Carrier Decision

Compare:

- Option A: `SemanticsProfile.iteration_count` top-level field.
- Option B: `SemanticsProfile.engine_options["iteration_count"]`.

Step 4.6 must source-back validation impact, existing `engine_options` behavior,
future T10-3 compatibility, and implementation/test surface before selecting.

### 3.2 SDK Field Shape

Decide default and validation for `PyReasonSemantics.iteration_count`.

Questions to answer:

- Does validation require `>= 1` or allow `0`?
- Is `bool` rejected like `timestep_delay`?
- How does error wording distinguish global `iteration_count` from per-rule
  `timestep_delay`?

### 3.3 SDK Lowering Path

Source-back exactly where `_preview_public_semantics(...)` and
`_lower_public_semantics(...)` should emit the canonical carrier, and how it
coexists with existing `temporal_projection`, `uncertainty_projection`, and
`rule_projection` lowering.

### 3.4 Adapter Consumption

Source-back changes around `_resolve_temporal_projection_state(...)` and
`_engine_options_with_temporal_projection(...)` in `engine_eval.py`.

Required decision:

- Canonical `iteration_count` takes precedence when present.
- Legacy `fixed_timesteps` remains fallback when canonical is absent.
- Conflict behavior must be explicit.

### 3.5 Conflict Behavior And Compatibility Policy

Decide:

- canonical + legacy both supplied: reject vs winner.
- Legacy `fixed_timesteps` policy: alias, deprecate, warning, or other.
- Error/warning wording.

Default expectation: reject explicit conflicts, following the explicit-reject
discipline established in T10-1 for unsafe ambiguity.

### 3.6 Test Matrix

At minimum:

- SDK accepts default `iteration_count=1`.
- SDK rejects invalid `iteration_count` values.
- Lowering emits the selected canonical carrier.
- Adapter drives PyReason run timesteps from canonical `iteration_count`.
- Legacy `fixed_timesteps` behavior remains covered by existing tests.
- Canonical + legacy conflict raises.
- Existing `timestep_delay`, `head_bound`, `branch_bounds`, and rule-extension
  tests still pass.
- Full discover delta is compared against `2013 tests / 72 failures / 231
  errors`.

### 3.7 Anti-Silent-Ignore Boundary

`iteration_count` default is not an error: absence means default 1. However,
explicit canonical and legacy carriers must not be silently merged. Step 4.6
must define tests that prove conflict behavior is explicit.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which canonical carrier should C78 use: top-level `SemanticsProfile.iteration_count` or `engine_options["iteration_count"]`? | Source-backed selection with tradeoffs and future T10-3 impact. |
| Q2 | What SDK validation should `PyReasonSemantics.iteration_count` use? | Decide `>= 1` vs `>= 0`, bool rejection, and error wording. |
| Q3 | How should SDK lowering emit the carrier? | Preview/runtime lowering plan with file/function refs. |
| Q4 | How should adapter consumption prioritize canonical vs legacy carriers? | Canonical-first / legacy-fallback or alternate plan with rationale. |
| Q5 | What is the conflict behavior when canonical and legacy are both specified? | Reject/winner decision, with test expectation. |
| Q6 | What is the legacy `fixed_timesteps` compatibility policy? | Alias/deprecate/warning decision and scope. |
| Q7 | What is the focused test matrix? | Concrete test list plus regression suite. |
| Q8 | What is the implementation commit split? | Commit plan and anti-partial-ship rationale. |
| Q9 | Does T10-2-A change the T8-C-2 unblock map? | Expected: it removes the C78/multi-round gate only; C74/C77/D11 remain. |
| Q10 | Are there stop/amend findings? | None or explicit trigger with next action. |

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

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed plan completed.
- [ ] Q1-Q10 answered.
- [ ] SDK shell shipped.
- [ ] SDK lowering / carrier shipped.
- [ ] Adapter consumption shipped.
- [ ] Legacy `fixed_timesteps` compatibility policy shipped.
- [ ] Canonical + legacy conflict behavior tested.
- [ ] Existing PyReason behavior preserved.
- [ ] T8-A/B/C-1/D and T10-1 invariants preserved.
- [ ] T10-2 inventory decisions preserved.
- [ ] `git diff --check` clean.
- [ ] Focused PyReason tests pass.
- [ ] Full discover delta compared against `2013 tests / 72 failures / 231 errors`.
- [ ] Sacred master and dirty baseline preserved.

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

Pending Step 4.6 / implementation / closure.
