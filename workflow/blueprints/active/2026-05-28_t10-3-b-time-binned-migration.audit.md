# Audit: T10-3-B PyReason Time Binned Migration

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t10-3-b-time-binned-migration.md`
- Stage: draft
- Class: M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T10-3-B `time_binned` migration drafted | Triggered by T10-3 inventory `da896f0c`, T10-3-A `e7bab90f`, T10-2-A `65cc79a3`, T10-2-B `92fd6013`, and current memory next-work #1; Q1-Q10 pending Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T10-3 inventory classified `time_binned` as a true new C77 temporal mode, not
  a spelling alias for `valid_time_boundaries` / `fact_boundaries`.
- T10-3 inventory recorded strict `bin_size` validation requirements: ISO 8601
  examples such as `P1D` / `PT1H`, short-form examples such as `1d` / `1h` /
  `15m` / `1m`, and rejection of ambiguous human-readable strings.
- T10-3-A shipped `fact_boundaries` as an input-spelling-preserving alias and
  established the dynamic conflict carrier pattern for temporal modes.
- Existing focused PyReason baseline after T10-3-A is expected to be 94 OK, and
  full discover baseline is expected to be `2029 tests / 72 failures /
  231 errors`.
- T10-2-A C78 and T10-2-B C74 remain strict invariants. T10-3-B must extend
  temporal projection without weakening those behaviors.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify or correct each
claim with source refs.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What exact `bin_size` whitelist should v1 accept? | Pending Step 4.6. |
| Q2 | What profile validation shape should `time_binned` use? | Pending Step 4.6. |
| Q3 | What is the `_materialize_time_binned` algorithm and edge-case policy? | Pending Step 4.6. |
| Q4 | How much of T10-3-A's dynamic carrier pattern is reused? | Pending Step 4.6. |
| Q5 | Is `time_binned` conflict behavior fully symmetric with `fact_boundaries`? | Pending Step 4.6. |
| Q6 | What tests cover whitelist, materializer, conflict behavior, and invariants? | Pending Step 4.6. |
| Q7 | What implementation split should be used? | Pending Step 4.6. |
| Q8 | How does T10-3-B update the T8-C-2 unblock map? | Pending Step 4.6. |
| Q9 | What behavior changes must closure warn about? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| `bin_size` whitelist under-specified | Parser accepts ambiguous inputs or rejects intended canonical inputs | Source-back exact whitelist and rejected examples before implementation. |
| New materializer semantics unclear | Facts may attach to wrong bins or produce unstable timesteps | Record universe/bin-size divisibility and fact-span mapping semantics in Q3. |
| `_TemporalProjectionState` shape does not fit | Adapter/run-config plumbing grows beyond scoped slice | Stop if new output shape is needed. |
| Conflict behavior differs from T10-3-A | T10-2-A anti-silent conflict discipline regresses | Require `_reject_iteration_temporal_conflict(...)` reuse and canonical `time_binned` carrier tests. |
| T10-3-A `fact_boundaries` regresses | Recently shipped alias behavior becomes unstable | Include T10-3-A tests and 14-item invariant manifest in focused gate. |
| T10-2-A / T10-2-B behavior regresses | PyReason canonical migration slices become unstable | Keep C78 and C74 focused tests in verification. |
| Work drifts into fixed-timesteps cleanup or docs | Scope creep into cleanup / T8-D round | Keep removal, warning, and user docs out-of-scope. |
| Full discover composition shifts silently | T10-1 Step 4.7 lesson regresses | Compare against `2029 tests / 72 failures / 231 errors`. |
| Sacred / dirty baseline touched | Workflow violation | Status checks before closure and push. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed plan complete.
- [ ] Q1-Q10 answered.
- [ ] `bin_size` whitelist reviewed.
- [ ] Profile validation plan reviewed.
- [ ] New materializer algorithm reviewed.
- [ ] Adapter consumption plan reviewed.
- [ ] Conflict behavior reviewed.
- [ ] T10-3-A / T10-2-A / T10-2-B invariant protection reviewed.
- [ ] Focused verification plan reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
