# Audit: T10-3-A PyReason Fact Boundaries Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-3-a-fact-boundaries-migration.md`
- Stage: draft
- Class: S/M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-3-A `fact_boundaries` alias migration drafted | Triggered by T10-3 inventory `da896f0c`, T10-2-A `65cc79a3`, T10-2-B `92fd6013`, and current memory next-work #1; Q1-Q9 pending Step 4.6. |

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

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which normalization strategy wins: preserve input spelling, normalize canonical, or normalize legacy? | Pending Step 4.6. |
| Q2 | What profile changes are required for `fact_boundaries` acceptance and universe validation? | Pending Step 4.6. |
| Q3 | Can adapter consumption reuse `_materialize_valid_time_boundaries(...)` unchanged? | Pending Step 4.6. |
| Q4 | Does `fact_boundaries` reuse `_reject_iteration_temporal_conflict(...)`? | Pending Step 4.6. |
| Q5 | What test matrix protects `fact_boundaries`, legacy `valid_time_boundaries`, T10-2-A, and T10-2-B? | Pending Step 4.6. |
| Q6 | What implementation split should be used? | Pending Step 4.6. |
| Q7 | How does T10-3-A update the T8-C-2 unblock map? | Pending Step 4.6. |
| Q8 | Are there behavior changes to warn about? | Pending Step 4.6. |
| Q9 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Normalization strategy is ambiguous | Tests or users may see unstable spelling | Step 4.6 must choose A/B/C and record preview/normalized output expectations. |
| Alias does not fit existing valid-time substrate | Implementation grows beyond scoped alias slice | Stop/amend if `_normalize_valid_time_boundaries(...)` or `_materialize_valid_time_boundaries(...)` cannot be reused. |
| `fact_boundaries` conflict behavior differs from legacy `valid_time_boundaries` | T10-2-A anti-silent conflict discipline regresses | Require symmetric `_reject_iteration_temporal_conflict` behavior and tests. |
| SDK shell is edited unnecessarily | Public API churn outside the generic temporal mapping surface | Scope lock says SDK shell remains pass-through for T10-3-A. |
| T10-2-A C78 behavior regresses | Recently shipped PyReason C78 becomes unstable | Include T10-2-A focused tests and invariant spot-checks. |
| T10-2-B C74 behavior regresses | Recently shipped C74 canonical rule params become unstable | Include C74 focused tests and invariant spot-checks. |
| Work drifts into `time_binned` or `fixed_timesteps` removal | Scope creep into T10-3-B or cleanup cycle | Keep `time_binned` and fixed-timesteps deprecation/removal out-of-scope. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Compare against `2025 tests / 72 failures / 231 errors`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed plan complete.
- [ ] Q1-Q9 answered.
- [ ] Normalization strategy reviewed.
- [ ] Profile alias plan reviewed.
- [ ] Adapter alias plan reviewed.
- [ ] Conflict behavior reviewed.
- [ ] T10-2-A / T10-2-B invariant protection reviewed.
- [ ] Focused verification plan reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
