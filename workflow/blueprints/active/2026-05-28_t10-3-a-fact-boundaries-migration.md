# Task Blueprint: T10-3-A PyReason Fact Boundaries Migration

- Status: implemented
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

**Decision: Option A, preserve input spelling.**

Source-backed comparison:

| Option | Shape | Assessment | Decision |
|---|---|---|
| **A. Preserve input spelling** | `fact_boundaries` remains `fact_boundaries`; legacy input remains `valid_time_boundaries`. | Existing tests assert legacy normalized spelling (`tests/test_pyreason_semantics_profile_migration.py:437-443`). This option adds canonical observability without changing legacy inspection output. Adapter can handle both modes with one shared branch. | **Selected.** |
| B. Normalize to canonical | Both inputs normalize to `fact_boundaries`. | Would likely require changing existing legacy normalized-output tests and would make legacy profile inspection report a different mode than supplied. | Reject. |
| C. Normalize to legacy internal | Both inputs normalize to `valid_time_boundaries`. | Minimal adapter change, but hides the new canonical spelling after profile normalization and weakens the point of the alias migration. | Reject. |

Implementation implication: profile normalization preserves `mode` as supplied
for `fact_boundaries` or `valid_time_boundaries`; preview / inspection surfaces
therefore reveal whether the caller used canonical or legacy spelling. This is
consistent with T10-3 inventory Q2: add canonical spelling while keeping
legacy accepted through T10-3.

### 3.2 Profile `_normalize_temporal_projection` Extension

Current source:

- `src/factgraph/core/semantics/profile.py:164-181` dispatches modes and
  currently accepts `none`, `fixed_timesteps`, and `valid_time_boundaries`.
- The legacy branch calls `_normalize_valid_time_boundaries(raw)` at
  `profile.py:175-178`.
- `_normalize_valid_time_boundaries(...)` at `profile.py:193-209` only
  validates allowed keys `mode` / `universe`, universe shape, non-empty string
  bounds, and `start < end`.

**Decision: add the smallest possible `fact_boundaries` branch and call
`_normalize_valid_time_boundaries(raw)` directly.** Set
`normalized["mode"] = "fact_boundaries"` for canonical inputs. Update the
unsupported-mode allowlist string to include `fact_boundaries`.

No new `_normalize_fact_boundaries(...)` wrapper is needed for T10-3-A because
the validation rules and error paths are identical. Do not rename
`_normalize_valid_time_boundaries(...)`; that would create churn without
changing behavior. Do not touch SDK shell: T10-3 inventory classified
`PyReasonSemantics.temporal_projection` as generic pass-through, and
`sdk/store.py:3458-3464` already lowers the mapping unchanged.

### 3.3 Adapter `_resolve_temporal_projection_state` Extension

Current source:

- `src/factgraph/adapters/pyreason/engine_eval.py:301-336` handles
  `none`, `fixed_timesteps`, and `valid_time_boundaries`.
- The `valid_time_boundaries` branch calls
  `_reject_iteration_temporal_conflict(...)` at `engine_eval.py:317-321`.
- The same branch calls `_materialize_valid_time_boundaries(...)` at
  `engine_eval.py:322-328`, then rejects engine-options timesteps conflicts at
  `engine_eval.py:329-334`.
- `_materialize_valid_time_boundaries(...)` at `engine_eval.py:398-433`
  returns the `_TemporalProjectionState` shape T10-3 inventory selected for
  reuse.

**Decision: extend the existing valid-time branch to handle both
`valid_time_boundaries` and `fact_boundaries`.** Use the actual supplied mode
in the conflict carrier string:

```python
carrier = f"SemanticsProfile.temporal_projection.{mode}"
```

Then reuse `_reject_iteration_temporal_conflict(...)`,
`_materialize_valid_time_boundaries(...)`, and
`_reject_temporal_timesteps_conflict(...)` unchanged. No new helper and no new
materializer are needed for T10-3-A.

### 3.4 Test Matrix

Implementation tests:

1. Profile accepts `{"mode": "fact_boundaries", "universe": [...]}` and
   preserves normalized mode `fact_boundaries`.
2. Profile `fact_boundaries` rejects invalid universe shape through the same
   validation rules as `valid_time_boundaries`.
3. Adapter materializes `fact_boundaries` with the same active-step behavior as
   `valid_time_boundaries`.
4. Explicit `SemanticsProfile.iteration_count` plus `fact_boundaries` rejects,
   with message containing `SemanticsProfile.iteration_count` and
   `SemanticsProfile.temporal_projection.fact_boundaries`.
5. Existing `valid_time_boundaries` tests at
   `tests/test_pyreason_semantics_profile_migration.py:437-443,549-627`
   remain unchanged and green.
6. Existing T10-2-A tests at
   `tests/test_pyreason_semantics_profile_migration.py:384-423,464-546` remain
   green.
7. Existing T10-2-B tests at
   `tests/test_pyreason_semantics_profile_migration.py:293-410` remain green.
8. Full discover composition is compared against
   `2025 tests / 72 failures / 231 errors`.

Focused baseline for Step 4.6 remains `90 OK`:

```text
Ran 90 tests in 0.359s
OK
```

### 3.5 Shipped Invariants

T10-3-A must preserve the T10-3 inventory §3.7 manifest. The files touched by
T10-3-A (`profile.py`, `engine_eval.py`, and
`tests/test_pyreason_semantics_profile_migration.py`) overlap T10-2-A tests and
adapter conflict helpers, so the focused gate must keep those tests in scope.
T10-2-B implementation lives primarily in `sdk/semantics.py` and
`sdk/store.py`, which T10-3-A should not touch, but its tests remain in the
focused gate.

T10-2-A:

1. SDK `PyReasonSemantics.iteration_count: int = 1` with positive-int
   validation (`tests/test_pyreason_semantics_profile_migration.py:384-397`).
2. Optional top-level `SemanticsProfile.iteration_count`
   (`tests/test_pyreason_semantics_profile_migration.py:398-408`).
3. Lowering omission rule for default `1` plus legacy temporal mode
   (`tests/test_pyreason_semantics_profile_migration.py:410-423`).
4. Adapter consumption mapping canonical `iteration_count` to run timesteps
   (`tests/test_pyreason_semantics_profile_migration.py:464-480`).
5. Explicit conflicts with `fixed_timesteps` and `valid_time_boundaries`
   (`tests/test_pyreason_semantics_profile_migration.py:502-546`).
6. No-profile engine default timesteps remains 2
   (`tests/test_pyreason_engine_eval.py:355-377`).

T10-2-B:

1. SDK `derived_bound` / `atom_bounds` validation
   (`tests/test_pyreason_semantics_profile_migration.py:293-313`).
2. `rule_projection["pyreason"]` carrier reuse
   (`tests/test_pyreason_semantics_profile_migration.py:315-340`).
3. SDK atom-id conversion to `body_atom:0:<index>`
   (`tests/test_pyreason_semantics_profile_migration.py:315-340`).
4. Legacy Inference / missing application atom ids reject canonical
   `atom_bounds` (`tests/test_pyreason_semantics_profile_migration.py:342-377`).
5. Asymmetric conflict policy for `derived_bound` / `head_bound` and
   `atom_bounds` / `branch_bounds`
   (`tests/test_pyreason_semantics_profile_migration.py:379-410`).
6. No T8-B witness-key reuse
   (`tests/test_pyreason_semantics_profile_migration.py:315-331`).

### 3.6 Behavior Change Warning

Step 4.6 confirms the T10-3 inventory prediction: **no default behavior shift is
expected for T10-3-A**.

Reasoning:

- Default profile mode remains `none` (`profile.py:166-170`).
- `fixed_timesteps` branch remains unchanged (`profile.py:171-174`;
  `engine_eval.py:305-316`).
- `valid_time_boundaries` branch remains accepted and preserves its normalized
  spelling under Option A (`profile.py:175-178`; tests `:437-443`).
- No-profile engine default timesteps remains covered by
  `tests/test_pyreason_engine_eval.py:355-377`.

The only new behavior is additive: callers may spell the existing valid-time
boundary behavior as canonical `fact_boundaries`. Closure must still record the
chosen normalization strategy and any observed composition-shift delta.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Which normalization strategy wins: preserve input spelling, normalize canonical, or normalize legacy? | Answered: Option A preserve input spelling. It preserves legacy normalized output and exposes canonical spelling for canonical callers. |
| Q2 | What profile changes are required for `fact_boundaries` acceptance and universe validation? | Answered: add a `fact_boundaries` mode branch in `_normalize_temporal_projection`, call `_normalize_valid_time_boundaries(raw)`, then set mode to `fact_boundaries`; no SDK shell change. |
| Q3 | Can adapter consumption reuse `_materialize_valid_time_boundaries(...)` unchanged? | Answered: yes. `fact_boundaries` follows the existing valid-time branch and reuses the materializer unchanged. |
| Q4 | Does `fact_boundaries` reuse `_reject_iteration_temporal_conflict(...)`? | Answered: yes. Use the supplied mode in the carrier string so conflict messages name `fact_boundaries` for canonical inputs. |
| Q5 | What test matrix protects `fact_boundaries`, legacy `valid_time_boundaries`, T10-2-A, and T10-2-B? | Answered: new profile/materialization/conflict tests plus existing legacy `valid_time_boundaries`, T10-2-A, and T10-2-B tests in the focused PyReason suite. |
| Q6 | What implementation split should be used? | Answered: keep three implementation commits: profile alias, adapter alias, tests. Commits 3-4 may combine only if audit records anti-partial-ship rationale. |
| Q7 | How does T10-3-A update the T8-C-2 unblock map? | Answered: it does not fully unblock T8-C-2; `time_binned` and D11/Form 2 remain after T10-3-A. |
| Q8 | Are there behavior changes to warn about? | Answered: no default shift expected; additive alias only. Closure must record actual composition-shift results. |
| Q9 | Are there stop/amend findings? | Answered: none. |

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
PYTHONPATH=src python -m unittest discover tests
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

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed plan completed.
- [x] Q1-Q9 answered.
- [x] Profile accepts `fact_boundaries`.
- [x] Adapter consumes `fact_boundaries` through the existing valid-time
  substrate.
- [x] `fact_boundaries` + canonical `iteration_count` conflict behavior tested.
- [x] Legacy `valid_time_boundaries` behavior preserved.
- [x] T10-2-A and T10-2-B invariants preserved.
- [x] T10-3 inventory decisions preserved.
- [x] T8-A/B/C-1/D and T10-1 invariants preserved.
- [x] `git diff --check` clean.
- [x] Focused PyReason tests pass.
- [x] Full discover delta compared against
  `2025 tests / 72 failures / 231 errors`.
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

Implemented in three runtime commits:

1. `c5ea4a4b` `feat(profile): accept fact_boundaries as canonical alias`
   - Added the smallest possible `fact_boundaries` branch in
     `_normalize_temporal_projection`.
   - Reused `_normalize_valid_time_boundaries(...)` unchanged.
   - Preserved Option A input spelling and kept the allowed-mode string
     alphabetical.
2. `3d6fc258` `feat(pyreason): consume fact_boundaries via valid-time substrate`
   - Extended the existing valid-time branch to handle both
     `valid_time_boundaries` and `fact_boundaries`.
   - Reused `_reject_iteration_temporal_conflict(...)`,
     `_materialize_valid_time_boundaries(...)`, and
     `_reject_temporal_timesteps_conflict(...)` unchanged.
   - Switched the conflict carrier string to the supplied mode, so canonical
     callers see `SemanticsProfile.temporal_projection.fact_boundaries`.
3. `03f94aba` `test(pyreason): cover fact_boundaries alias migration`
   - Added four tests for profile acceptance, universe validation parity,
     `iteration_count` conflict behavior, and adapter materialization parity.

Verification:

- Focused PyReason suite:
  `PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration`
  -> `Ran 94 tests ... OK`.
- Full discover:
  `PYTHONPATH=src python -m unittest discover tests`
  -> `Ran 2029 tests ... FAILED (failures=72, errors=231)`.
  This is the expected clean composition delta from the T10-2-B baseline
  `2025 tests / 72 failures / 231 errors`: +4 tests, +0 failures, +0 errors.
- `ruff check src/factgraph/core/semantics/profile.py src/factgraph/adapters/pyreason/engine_eval.py tests/test_pyreason_semantics_profile_migration.py`
  -> clean.
- `git diff --check` -> clean.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`.

Deviations / notes:

- Source footprint is the smallest runtime footprint in this session: 9 source LOC
  plus 67 test LOC. This matches the Step 4.6 "absolute minimum viable" plan.
- Scoped §3.5 test line refs shifted after adding the four new tests, but the
  underlying T10-2-A and T10-2-B tests remained unchanged and passed in the
  focused 94 OK suite.
- An initial full-discover command was run without `PYTHONPATH=src`, producing
  import errors. The corrected `PYTHONPATH=src` command was rerun and is the
  verification result recorded above. Future cycles should keep `PYTHONPATH=src`
  explicit in full-discover commands or consolidate this into a checked script /
  Makefile target.
