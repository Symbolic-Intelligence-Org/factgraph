# Audit: T10-3-A PyReason Fact Boundaries Migration

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-3-a-fact-boundaries-migration.md`
- Stage: implemented
- Class: S/M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `30240f16` | T10-3-A `fact_boundaries` alias migration drafted | Triggered by T10-3 inventory `da896f0c`, T10-2-A `65cc79a3`, T10-2-B `92fd6013`, and current memory next-work #1; Q1-Q9 pending Step 4.6. |
| 2026-05-28 | scoped | `30c253a9` | Step 4.6 source-backed implementation plan completed | Selected input-spelling-preserving normalization, direct valid-time validation reuse, existing materializer/conflict-helper reuse, and a focused test matrix with 90 OK baseline. |
| 2026-05-28 | implemented | this commit | Step 4.7 implementation closed | Three implementation commits shipped `fact_boundaries` alias support with focused 94 OK and full-discover `2029 / 72F / 231E`. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-3 inventory selected T10-3-A as the smaller alias / compatibility slice:
  add `fact_boundaries` before the larger T10-3-B `time_binned` mode.
- Existing profile code is expected to accept `none`, `fixed_timesteps`, and
  `valid_time_boundaries`, but not `fact_boundaries`. Step 4.6 must verify the
  exact line refs.
- Existing adapter code is expected to materialize `valid_time_boundaries`
  through `_materialize_valid_time_boundaries(...)` and reject
  `iteration_count` conflicts through `_reject_iteration_temporal_conflict`.
  Step 4.6 must verify whether `fact_boundaries` can reuse both paths.
- T10-2-A C78 behavior is a strict invariant: default `iteration_count`,
  optional profile carrier, lowering omission rule, adapter consumption, and
  conflict helpers must not regress.
- T10-2-B C74 behavior is also a strict invariant: canonical bounds, atom-id
  conversion, asymmetric conflict policy, and no witness-key reuse must not
  regress.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

### 2.1 Step 4.6 Source-Backed Summary

- Profile normalization currently accepts `none`, `fixed_timesteps`, and
  `valid_time_boundaries` at `profile.py:164-181`; `fact_boundaries` is missing.
- Existing `_normalize_valid_time_boundaries(...)` at `profile.py:193-209`
  validates exactly the universe shape T10-3-A needs, so `fact_boundaries` can
  reuse it directly.
- Adapter `_resolve_temporal_projection_state(...)` currently handles
  `valid_time_boundaries` at `engine_eval.py:317-335` by calling
  `_reject_iteration_temporal_conflict(...)`,
  `_materialize_valid_time_boundaries(...)`, and
  `_reject_temporal_timesteps_conflict(...)`.
- Step 4.6 selected input-spelling preservation: canonical inputs normalize to
  mode `fact_boundaries`, legacy inputs continue to normalize to
  `valid_time_boundaries`.
- Focused PyReason no-op baseline remains 90 OK.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which normalization strategy wins: preserve input spelling, normalize canonical, or normalize legacy? | Answered: preserve input spelling. |
| Q2 | What profile changes are required for `fact_boundaries` acceptance and universe validation? | Answered: add a `fact_boundaries` branch using `_normalize_valid_time_boundaries(...)`, no SDK shell change. |
| Q3 | Can adapter consumption reuse `_materialize_valid_time_boundaries(...)` unchanged? | Answered: yes. |
| Q4 | Does `fact_boundaries` reuse `_reject_iteration_temporal_conflict(...)`? | Answered: yes, with carrier string naming the supplied mode. |
| Q5 | What test matrix protects `fact_boundaries`, legacy `valid_time_boundaries`, T10-2-A, and T10-2-B? | Answered: new profile/materialization/conflict tests plus existing focused PyReason regression gate. |
| Q6 | What implementation split should be used? | Answered: profile alias, adapter alias, tests. |
| Q7 | How does T10-3-A update the T8-C-2 unblock map? | Answered: T8-C-2 remains gated by T10-3-B `time_binned` plus D11/Form 2. |
| Q8 | Are there behavior changes to warn about? | Answered: no default shift expected; additive alias only. |
| Q9 | Are there stop/amend findings? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Normalization strategy is ambiguous | Tests or users may see unstable spelling | Mitigated: Q1 selects input-spelling preservation and records preview/normalized output expectations. |
| Alias does not fit existing valid-time substrate | Implementation grows beyond scoped alias slice | Mitigated: Q2/Q3 verified direct reuse of valid-time validation and materializer. |
| `fact_boundaries` conflict behavior differs from legacy `valid_time_boundaries` | T10-2-A anti-silent conflict discipline regresses | Mitigated: Q4 requires the same `_reject_iteration_temporal_conflict(...)` helper and symmetric test coverage. |
| SDK shell is edited unnecessarily | Public API churn outside the generic temporal mapping surface | Mitigated: Q2 records no SDK shell change. |
| T10-2-A C78 behavior regresses | Recently shipped PyReason C78 becomes unstable | Mitigated: Q5 keeps T10-2-A focused tests and invariant spot-checks. |
| T10-2-B C74 behavior regresses | Recently shipped C74 canonical rule params become unstable | Mitigated: Q5 keeps C74 focused tests and invariant spot-checks. |
| Work drifts into `time_binned` or `fixed_timesteps` removal | Scope creep into T10-3-B or cleanup cycle | Keep `time_binned` and fixed-timesteps deprecation/removal out-of-scope. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Compare against `2025 tests / 72 failures / 231 errors`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed plan complete.
- [x] Q1-Q9 answered.
- [x] Normalization strategy reviewed.
- [x] Profile alias plan reviewed.
- [x] Adapter alias plan reviewed.
- [x] Conflict behavior reviewed.
- [x] T10-2-A / T10-2-B invariant protection reviewed.
- [x] Focused verification plan reviewed.
- [x] Closure notes filled.

## 6. Closure Notes

Implementation commits:

- `c5ea4a4b` `feat(profile): accept fact_boundaries as canonical alias`
- `3d6fc258` `feat(pyreason): consume fact_boundaries via valid-time substrate`
- `03f94aba` `test(pyreason): cover fact_boundaries alias migration`

Verification:

- Focused PyReason suite: `94 OK` (`90 -> 94`, +4).
- Full discover: `2029 tests / 72 failures / 231 errors`
  (`2025 -> 2029`, +4 tests, +0 failures, +0 errors).
- `ruff check` on touched files: clean.
- `git diff --check`: clean.
- Sacred `master`: `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline: `4 M + 1 D + 6 U`.

Implementation notes:

- The runtime footprint is 9 source LOC plus 67 test LOC, matching the scoped
  "absolute minimum viable" plan.
- The profile change preserves input spelling: canonical `fact_boundaries`
  normalizes to `fact_boundaries`; legacy `valid_time_boundaries` remains
  `valid_time_boundaries`.
- The adapter uses a dynamic carrier string, so conflict messages name
  `SemanticsProfile.temporal_projection.fact_boundaries` for canonical callers
  and preserve the legacy carrier for legacy callers.
- T10-2-A and T10-2-B invariant tests remain part of the focused 94 OK gate.

Deviations / future pings:

- Scoped §3.5 test line refs shifted after new test insertion, but the covered
  test logic remained unchanged.
- A full-discover command run without `PYTHONPATH=src` produced import errors;
  the corrected `PYTHONPATH=src` invocation produced the recorded composition
  delta. Future cycles should keep `PYTHONPATH=src` explicit or move this check
  into a small maintained command target.
