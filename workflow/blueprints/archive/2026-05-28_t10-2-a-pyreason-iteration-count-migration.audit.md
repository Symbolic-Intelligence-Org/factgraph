# Audit: T10-2-A PyReason Iteration Count Migration

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md`
- Stage: closure
- Class: S/M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `0b76ec4f` | T10-2-A PyReason iteration_count migration drafted | Triggered by T10-2 inventory split decision; Q1-Q10 pending Step 4.6. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed plan completed | Selected optional top-level `SemanticsProfile.iteration_count` carrier; locked alias/fallback compatibility for legacy `fixed_timesteps` and explicit conflict rejection. |
| 2026-05-28 | implementation | `8953f3ec` / `c5cca89b` / `1742bba2` / `f8d90307` | C78 implementation shipped | SDK shell, optional profile carrier + lowering, adapter consumption, conflict policy, and tests. |
| 2026-05-28 | closure | this commit | Cycle closed | Step 4.7 review passed with no amend findings; archive next. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-2 inventory archived at `f8e08905` selected T10-2-A C78 before T10-2-B
  C74, because `fixed_timesteps` must be clarified before T10-3 temporal work.
- C78 canonical `iteration_count` is absent from current `PyReasonSemantics`,
  `SemanticsProfile`, and PyReason adapter consumption.
- Current PyReason execution derives engine timesteps from legacy
  `temporal_projection.fixed_timesteps`; this is the compatibility seam.
- C78 design requires `iteration_count: int = 1`, orthogonal to fact temporal
  lifecycle and distinct from per-rule `timestep_delay`.
- Existing legacy `fixed_timesteps` tests in
  `tests/test_pyreason_semantics_profile_migration.py` must remain regression
  guards unless Step 4.6 explicitly changes compatibility policy.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 2.1 Step 4.6 Source-Backed Summary

Step 4.6 verified the C78 implementation surface without changing runtime code:

- `rule-expression-and-proof-attempt.zh.md:1422-1446` and `:1603` define
  canonical `iteration_count: int = 1` as global PyReason inference rounds,
  orthogonal to fact temporal lifecycle and distinct from `timestep_delay`.
- `sdk/semantics.py:167-172` has no `iteration_count`; `:183-186` shows the
  existing `timestep_delay` validation pattern and confirms the semantic
  distinction needed in error wording.
- `profile.py:39-48` has top-level semantic carriers but no `iteration_count`;
  `engine_options` is generic and copied at `:65-76`.
- `engine_eval.py:129-155` treats `engine_options` as adapter-local run config
  and accepts only `timesteps`; therefore C78 should not be hidden under
  `engine_options["iteration_count"]`.
- `engine_eval.py:301-308` consumes legacy `fixed_timesteps`;
  `:309-323` consumes `valid_time_boundaries`; `:327-336` writes temporal
  timesteps into effective engine options.
- Legacy tests at `tests/test_pyreason_semantics_profile_migration.py:271-327`
  and `:498-514`, plus `tests/test_pyreason_engine_eval.py:355-401`, must
  remain regression guards.
- Focused PyReason baseline was run at Step 4.6: `78 OK`.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which canonical carrier should C78 use: top-level `SemanticsProfile.iteration_count` or `engine_options["iteration_count"]`? | Answered: optional top-level `SemanticsProfile.iteration_count: int \| None = None`. |
| Q2 | What SDK validation should `PyReasonSemantics.iteration_count` use? | Answered: `int = 1`, bool/non-int rejected, values `< 1` rejected; wording names global `iteration_count`. |
| Q3 | How should SDK lowering emit the carrier? | Answered: emit for ordinary/default PyReason semantics and explicit non-default values; suppress only implicit default `1` when a legacy timesteps mode would otherwise create false conflict. |
| Q4 | How should adapter consumption prioritize canonical vs legacy carriers? | Answered: canonical drives timesteps when present with temporal mode `none`; legacy temporal modes continue when canonical absent. |
| Q5 | What is the conflict behavior when canonical and legacy are both specified? | Answered: explicit canonical + `fixed_timesteps` rejects. |
| Q6 | What is the legacy `fixed_timesteps` compatibility policy? | Answered: alias/fallback in T10-2-A; no warning; T10-3 owns removal/rename. |
| Q7 | What is the focused test matrix? | Answered: SDK default/invalid/lowering/profile/adapter/conflict/legacy/no-profile/regression/full-discover composition matrix. |
| Q8 | What is the implementation commit split? | Answered: four implementation commits unless LOC is tiny and audit records merge rationale. |
| Q9 | Does T10-2-A change the T8-C-2 unblock map? | Answered: removes only C78/multi-round gate; C74/C77/D11 remain. |
| Q10 | Are there stop/amend findings? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Carrier choice is under-specified | SDK field may lower into a path future T10-3 cannot reason about | Q1 must compare top-level carrier vs `engine_options` with source refs and future T10-3 impact. |
| `iteration_count` is confused with `timestep_delay` | Global round count and per-rule delay semantics drift | Q2/Q3 must keep validation and docs/errors distinct from existing `timestep_delay`. |
| Legacy `fixed_timesteps` silently wins over canonical field, or vice versa | User configuration becomes ambiguous | Q5 must require explicit conflict behavior and tests. |
| Compatibility policy breaks existing fixed_timesteps tests | T10-2-A regresses shipped PyReason behavior | Q6/Q7 must include legacy regression coverage. |
| C74 or C77 work sneaks in | Scope creep and invalidates T10-2 split | Scope locks exclude atom-bound conversion and temporal mode rename/time-binned. |
| Evidence/user docs are touched | T10-2-A is adapter execution semantics, not evidence/user docs | File scope must remain runtime/tests/blueprint only. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Step 4.7 must compare F/E counts to `2013 / 72F / 231E`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed plan complete.
- [x] Q1-Q10 answered.
- [x] SDK shell / lowering / carrier / adapter plan reviewed.
- [x] Conflict and compatibility policy reviewed.
- [x] Test matrix reviewed.
- [x] Implementation review complete.
- [x] Closure notes filled.

## 6. Closure Notes

Outcome:

- C78 canonical `iteration_count` shipped end-to-end for PyReason:
  `PyReasonSemantics.iteration_count`, optional
  `SemanticsProfile.iteration_count`, SDK lowering, and adapter consumption.
- Legacy `temporal_projection.fixed_timesteps` remains an alias/fallback when
  canonical C78 is absent. Explicit canonical `iteration_count` conflicts with
  both `fixed_timesteps` and `valid_time_boundaries`; tests cover both.
- Implementation commits:
  - `8953f3ec` SDK shell.
  - `c5cca89b` profile carrier + lowering / omission rule.
  - `1742bba2` adapter consumption + conflict helpers.
  - `f8d90307` six tests.
- Verification:
  - Focused PyReason suite: `84 OK`.
  - Full discover: `2019 tests / 72 failures / 231 errors`, compared with
    baseline `2013 / 72 / 231`.
  - `ruff check` on touched files: clean.
  - `git diff --check`: clean.
  - Sacred master and dirty baseline preserved.

Implementation notes / future pings:

- `PyReasonSemantics()` now intentionally drives `timesteps=1` through
  canonical `iteration_count=1`; the old no-profile adapter default remains
  `timesteps=2`. Future user docs should teach the wrapper default.
- The dual-helper conflict shape is deliberate: existing
  `_reject_temporal_timesteps_conflict(...)` still owns run-config timesteps
  conflicts, while `_reject_iteration_temporal_conflict(...)` owns canonical
  iteration-vs-temporal-mode conflicts.
- C74 and C77 were not touched. T10-2-B and T10-3 remain separate cycles.
