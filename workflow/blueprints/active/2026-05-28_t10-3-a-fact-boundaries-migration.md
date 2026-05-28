# Task Blueprint: T10-3-A PyReason Fact Boundaries Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-3-a-fact-boundaries-migration.audit.md`
- Trigger: T10-3 inventory archived at `da896f0c` selected the split
  T10-3-A `fact_boundaries` alias / compatibility migration followed by
  T10-3-B `time_binned`, and recorded the §3.7 12-item shipped PyReason
  invariant manifest. T10-2-A shipped at `65cc79a3`, proving the canonical
  profile/lowering/adapter-consumption pattern and locking C78
  `iteration_count` conflict behavior. T10-2-B shipped at `92fd6013`, proving
  the existing `rule_projection["pyreason"]` carrier reuse pattern and locking
  C74 behavior. `workflow/memory/current.md` lists T10-3-A
  `fact_boundaries` alias / compatibility as next work #1.

## 0. Scope Locks

### In scope

This is a runtime implementation cycle for the T10-3-A C77 alias slice only.

1. Profile carrier extension:
   - Extend `SemanticsProfile._normalize_temporal_projection` to accept
     `fact_boundaries`.
   - Route `fact_boundaries` to the existing valid-time-boundary validation
     substrate unless Step 4.6 proves that substrate cannot be reused.
2. Normalization strategy decision:
   - Option A: preserve input spelling. `fact_boundaries` input normalizes to
     mode `fact_boundaries`; `valid_time_boundaries` input preserves legacy
     mode `valid_time_boundaries`.
   - Option B: normalize both spellings to canonical mode `fact_boundaries`.
   - Option C: normalize both spellings to legacy internal mode
     `valid_time_boundaries`.
   - Step 4.6 must source-back the test impact and choose one.
3. Adapter consumption extension:
   - Extend `_resolve_temporal_projection_state(...)` to accept
     `fact_boundaries`.
   - Reuse `_materialize_valid_time_boundaries(...)` unchanged unless
     Step 4.6 proves a stop/amend trigger.
4. Conflict behavior consistency:
   - `fact_boundaries` must reject explicit canonical `iteration_count` the
     same way `valid_time_boundaries` rejects it.
   - Prefer reusing `_reject_iteration_temporal_conflict(...)`; a new helper is
     a stop/amend candidate unless source-backed as necessary.
5. Focused tests:
   - Profile accepts `fact_boundaries` and validates its universe shape.
   - Adapter materializes `fact_boundaries` through the existing valid-time
     substrate.
   - `fact_boundaries` conflicts with canonical `iteration_count`.
   - Legacy `valid_time_boundaries` behavior and tests remain unchanged.
   - T10-2-A `iteration_count` and T10-2-B C74 tests remain green.
   - Full discover delta is compared against baseline
     `2025 tests / 72 failures / 231 errors`.

### Out of scope

- `time_binned`; it belongs to T10-3-B.
- `fixed_timesteps` removal, deprecation, or warning. T10-3 inventory Q4
  selected preserve-compatibility for the first T10-3 implementation slice.
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
- Audit module docs; T10-3-A changes adapter execution semantics, not evidence
  module behavior.
- User-facing docs; a future T8-D round can teach PyReason canonical temporal
  semantics after T10-3-A/B ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including the four untracked active
  design-point files.
- Reopening T10 inventory, T10-2 inventory, T10-2-A, T10-2-B, or T10-3
  inventory decisions. If implementation contradicts an archive, stop and
  amend the relevant archive instead of silently diverging.
- Absorbing or classifying any untracked design-point file.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

1. T10-3 inventory §3.3 alias policy cannot reuse
   `_normalize_valid_time_boundaries(...)` or the existing valid-time substrate.
2. All three normalization strategies A/B/C break existing
   `valid_time_boundaries` tests.
3. `fact_boundaries` conflict behavior cannot remain symmetric with
   `valid_time_boundaries` conflict behavior against canonical
   `iteration_count`.
4. SDK shell changes are required. T10-3 inventory §3.1 classified the SDK
   shell as generic pass-through, so T10-3-A should not need public SDK field
   changes.
5. Conflict checking cannot reuse `_reject_iteration_temporal_conflict(...)`
   and needs a new helper.
6. Runtime/test/user-doc/governance/sacred/dirty-baseline files outside this
   cycle's planned implementation surface need edits, or T10-2-A/T10-2-B
   shipped behavior would be weakened.
7. Any untracked design-point file needs adoption or classification before
   T10-3-A.

## 1. Problem

T10-3 inventory determined that C77 temporal projection remains partial under
legacy names. `valid_time_boundaries` has shipped validation and adapter
materialization, while canonical `fact_boundaries` is missing. The same
inventory selected a risk-staged split: ship `fact_boundaries` first as a
canonical alias to the existing valid-time-boundary substrate, then ship
`time_binned` later as T10-3-B.

T10-3-A must add the canonical spelling without changing the underlying
valid-time materialization semantics, without reopening T10-2-A's
`iteration_count` conflict behavior, and without weakening T10-2-B's C74 rule
params. The main design question is the normalized spelling strategy:
preserve input spelling, normalize to canonical, or normalize to legacy
internal spelling.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t10-3-pyreason-temporal-migration-inventory.md` | Parent inventory; alias policy, split decision, invariant manifest. |
| `workflow/blueprints/archive/2026-05-28_t10-3-pyreason-temporal-migration-inventory.audit.md` | Review record and future implementation pings. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | T10-2-A canonical C78 behavior and conflict precedent. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | T10-2-B C74 invariants and carrier/lowering precedent. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C77 canonical design anchor for `fact_boundaries` and `time_binned`. |
| `src/factgraph/core/semantics/profile.py` | `SemanticsProfile.temporal_projection` validation and mode normalization. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | PyReason temporal projection consumption, conflict checks, and materializer. |
| `tests/test_pyreason_semantics_profile_migration.py` | Existing temporal projection, conflict, and T10-2-A/T10-2-B regression tests. |
| `tests/test_pyreason_engine_eval.py`, `tests/test_pyreason_rule_ext.py`, `tests/test_pyreason_evidence_graph.py` | Focused PyReason regression gate. |

## 3. Step 4.6 Source-Backed Implementation Plan

### 3.1 Normalization Strategy Decision

Step 4.6 must compare:

| Option | Shape | Required analysis |
|---|---|---|
| A. Preserve input spelling | `fact_boundaries` remains `fact_boundaries`; legacy input remains `valid_time_boundaries`. | Best external observability and compatibility, but adapter must handle both modes. |
| B. Normalize to canonical | Both inputs normalize to `fact_boundaries`. | Simplifies canonical internals, but may break tests or code that expects legacy normalized spelling. |
| C. Normalize to legacy internal | Both inputs normalize to `valid_time_boundaries`. | Minimizes adapter changes, but hides canonical spelling after profile normalization. |

The decision must be source-backed against existing tests around
`valid_time_boundaries` and the T10-3 inventory decision to keep legacy spelling
accepted through T10-3. The selected strategy must also state how preview /
inspection surfaces should display the mode.

### 3.2 Profile `_normalize_temporal_projection` Extension

Step 4.6 must locate the exact profile branch for current mode validation and
choose whether implementation should:

- call `_normalize_valid_time_boundaries(...)` directly for `fact_boundaries`;
- add a thin `_normalize_fact_boundaries(...)` wrapper that delegates to the
  existing helper but preserves canonical naming in errors or output; or
- refactor the helper name to neutral wording only if tests prove it is needed.

Default expectation: add the smallest possible `fact_boundaries` branch and
reuse existing universe validation. Do not change SDK shell behavior.

### 3.3 Adapter `_resolve_temporal_projection_state` Extension

Step 4.6 must source-back the current adapter branches and decide the exact
branch placement for `fact_boundaries`.

Default expectation:

- `fact_boundaries` follows the existing `valid_time_boundaries` branch.
- The branch calls `_reject_iteration_temporal_conflict(...)` before
  materialization, matching T10-2-A behavior.
- The branch reuses `_materialize_valid_time_boundaries(...)` unchanged.

If a new helper or new materializer is required, that is a stop/amend signal
unless the source-backed analysis shows the parent inventory was too narrow.

### 3.4 Test Matrix

Step 4.6 should lock focused tests for:

1. `SemanticsProfile(temporal_projection={"mode": "fact_boundaries", ...})`
   acceptance and normalized mode behavior per Q1.
2. `fact_boundaries` universe validation parity with `valid_time_boundaries`.
3. Adapter materialization parity with `valid_time_boundaries`.
4. Explicit `iteration_count` + `fact_boundaries` conflict rejection.
5. Legacy `valid_time_boundaries` tests unchanged.
6. T10-2-A `iteration_count` tests unchanged.
7. T10-2-B C74 canonical tests unchanged.
8. Full discover composition compared against
   `2025 tests / 72 failures / 231 errors`.

### 3.5 Shipped Invariants

T10-3-A must preserve the T10-3 inventory §3.7 manifest:

T10-2-A:

1. SDK `PyReasonSemantics.iteration_count: int = 1` with positive-int
   validation.
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

Step 4.6 should source-back whether T10-3-A touches any files containing these
behaviors and record the regression tests to keep in the focused gate.

### 3.6 Behavior Change Warning

T10-3 inventory predicted no default behavior shift for T10-3-A. Step 4.6 must
verify this. Any behavior change similar to T10-2-A's default-timesteps
`2 -> 1` shift must be recorded before implementation. Expected behavior:
`fact_boundaries` is additive alias behavior only; default `none`,
`fixed_timesteps`, `valid_time_boundaries`, and no-profile engine defaults do
not change.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which normalization strategy wins: preserve input spelling, normalize canonical, or normalize legacy? | Pick A/B/C with source-backed compatibility reasoning. |
| Q2 | What profile changes are required for `fact_boundaries` acceptance and universe validation? | Exact helper/branch choice and expected normalized output. |
| Q3 | Can adapter consumption reuse `_materialize_valid_time_boundaries(...)` unchanged? | Yes/no with source refs; no implies stop/amend unless justified. |
| Q4 | Does `fact_boundaries` reuse `_reject_iteration_temporal_conflict(...)`? | Prefer yes; otherwise explain why a new helper is unavoidable. |
| Q5 | What test matrix protects `fact_boundaries`, legacy `valid_time_boundaries`, T10-2-A, and T10-2-B? | Concrete focused tests plus full discover composition baseline. |
| Q6 | What implementation split should be used? | `profile` + `adapter` + `tests`, or combined if LOC is small with audit rationale. |
| Q7 | How does T10-3-A update the T8-C-2 unblock map? | It does not fully unblock T8-C-2; `time_binned` plus D11/Form 2 remain. |
| Q8 | Are there behavior changes to warn about? | Expected no default shift; verify explicitly. |
| Q9 | Are there stop/amend findings? | Yes/no, with trigger mapping. |

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
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10 inventory, T10-2 inventory, T10-2-A, T10-2-B, and T10-3 inventory remain
  locked unless this cycle stops and amends the relevant archive.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "_normalize_temporal_projection|_normalize_valid_time_boundaries|fact_boundaries|valid_time_boundaries" src/factgraph/core/semantics/profile.py
rg -n "_resolve_temporal_projection_state|_materialize_valid_time_boundaries|_reject_iteration_temporal_conflict|fact_boundaries" src/factgraph/adapters/pyreason/engine_eval.py
rg -n "valid_time_boundaries|fact_boundaries|iteration_count.*temporal" tests/test_pyreason_semantics_profile_migration.py
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
ruff check src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Normalization strategy decision.
2. Profile branch/helper plan.
3. Adapter branch/helper plan.
4. Test matrix.
5. Shipped invariant preservation map.
6. Behavior-change assessment.
7. Stop/amend assessment.

## 7. Implementation Split

Candidate chain:

1. `docs(blueprint): draft T10-3-A fact_boundaries migration`
2. `docs(blueprint): scope T10-3-A fact_boundaries migration`
3. `feat(profile): accept fact_boundaries as canonical alias`
4. `feat(pyreason): consume fact_boundaries via valid-time substrate`
5. `test(pyreason): cover fact_boundaries alias migration`
6. `docs(blueprint): close T10-3-A fact_boundaries migration`
7. `docs(blueprint): archive T10-3-A fact_boundaries migration`

If Step 4.6 shows the profile and adapter changes are very small, commits 3-4
may combine only if the audit records why alias profile acceptance and adapter
consumption are still reviewed together without partial-ship risk.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed plan completed.
- [ ] Q1-Q9 answered.
- [ ] Profile accepts `fact_boundaries`.
- [ ] Adapter consumes `fact_boundaries` through the existing valid-time
  substrate.
- [ ] `fact_boundaries` + canonical `iteration_count` conflict behavior tested.
- [ ] Legacy `valid_time_boundaries` behavior preserved.
- [ ] T10-2-A and T10-2-B invariants preserved.
- [ ] T10-3 inventory decisions preserved.
- [ ] T8-A/B/C-1/D and T10-1 invariants preserved.
- [ ] `git diff --check` clean.
- [ ] Focused PyReason tests pass.
- [ ] Full discover delta compared against
  `2025 tests / 72 failures / 231 errors`.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Runtime implementation verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
python -m unittest discover tests
ruff check src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
