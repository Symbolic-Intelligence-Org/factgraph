# Audit: T10-1 ProbLog Uncertainty Projection

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t10-1-problog-uncertainty-projection.md`
- Stage: implemented
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 4 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T10-1 ProbLog uncertainty projection blueprint pair drafted | Triggered after T10 inventory selected T10-1 C76 as the first staged hybrid implementation slice; Q1-Q10 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | pending | Source-backed T10-1 C76 inventory completed | Fixture drift included in scope; C76 three-layer gap verified; v1 adapter consumption selects explicit reject plus point-projection policies, with no silent ignore. |
| 2026-05-27 | implementation | `4d3ed74e` / `bb619279` / `b7823086` / `efcaa36f` | C76 implementation and tests landed | Fixture drift fixed, SDK shell/lowering added, ProbLog adapter consumption added, and policy tests covered. |
| 2026-05-27 | amend | `e7cad68c` | Step 4.7 blocker fixed | Direct `_claim_probability(...)` callers now default to the reject projection, resolving the silent replacement of two fixed fixture errors with two new direct-call errors. |
| 2026-05-27 | closure | pending | Closure prepared | Verification records 113 focused tests OK and full discover at 2011 tests / 72 failures / 231 errors. |

## 2. Draft Inventory Summary

Source-backed scoped findings:

- T10 inventory selected T10-1 as ProbLog C76 full three-layer ship.
- Two existing ProbLog migration errors are fixture drift: `_make_sdk()` in
  `tests/test_problog_semantics_profile_migration.py:160-172` writes legacy
  `meta={"confidence": 1.0}` and the current write protocol rejects it at
  `src/factgraph/core/evidence/write_protocol.py:268-274`.
- C76 SDK shell is missing:
  `src/factgraph/sdk/semantics.py:73-114` defines `ProbLogSemantics` without
  `uncertainty_projection`.
- C76 lowering is missing: generic
  `SemanticsProfile.uncertainty_projection` exists and normalizes at
  `src/factgraph/core/semantics/profile.py:43,66-77,128-147`, but ProbLog
  lowering at `src/factgraph/sdk/store.py:3385-3414` does not populate it.
- C76 adapter consumption is missing:
  `src/factgraph/adapters/problog/rule_ext.py:72-117` consumes only
  branch-probability carriers, and
  `src/factgraph/adapters/problog/problog_export.py:82-100,124-169`
  materializes fact probabilities from explicit probability annotations or
  default `1.0`, not `raw_kind` / `bound`.
- C76 design at
  `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1360-1418,1601`
  requires SDK shell, lowering, and adapter consumption together, with
  conservative default reject and explicit opt-in for midpoint-like policies.

Step 4.6 must independently verify or correct each finding before
implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should the two ProbLog migration errors be fixed inside T10-1, before T10-1, or left as known drift? | Answered: include in T10-1 as first implementation commit; closure baseline should show the two errors fixed. |
| Q2 | What is the verified C76 three-layer current state? | Answered: SDK shell, lowering, and adapter consumption are missing; generic core substrate exists. |
| Q3 | What SDK field shape should `ProbLogSemantics.uncertainty_projection` expose? | Answered: same schema as `SemanticsProfile.uncertainty_projection`. |
| Q4 | What is the default lowering policy when SDK callers omit `uncertainty_projection`? | Answered: lower the C76 default reject projection. |
| Q5 | What adapter consumption semantics should v1 ship? | Answered: explicit consumption; reject raises, point-projection policies materialize probabilities, and silent ignore is forbidden. |
| Q6 | Which policies are supported in v1? | Answered: `reject`, `lower`, `midpoint`, `upper`, and degenerate `identity_probability`; interval-valued policies are rejected for ProbLog v1 point export. |
| Q7 | What is the focused test matrix? | Answered: fixture fix, field/lowering/default/explicit/adapter policy behavior, unsupported interval policies, and branch-probability regressions. |
| Q8 | Does full T10-1 ship unblock T8-C-1? | Answered: yes for C76 after all three layers ship; T8-C-1 remains a separate evidence cycle. |
| Q9 | Do audit docs or user docs change? | Answered: no. |
| Q10 | Are there stop/amend findings? | Answered: none. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Fixture drift is treated as unrelated and left to keep failing | T10-1 verification remains noisy and may hide regressions | Decide Q1 before implementation. |
| Runtime bug is misclassified as fixture drift | T10-1 builds on broken ProbLog write/evaluate path | Verify write protocol rejection and fixture setup source. |
| SDK shell ships without lowering or adapter consumption | `uncertainty_projection` silently appears supported but does nothing | Require all three C76 layers in one coherent scope or stop. |
| Adapter silently ignores raw uncertainty rows | User configuration has no effect; T8-C-1 starts on false prerequisite | Q5 must choose explicit reject/substitution semantics. |
| C110 carrier is weakened to make tests pass | Reintroduces removed uncertainty keys | Preserve write protocol legacy-key rejection. |
| T10-1 drifts into T8-C evidence enrichment | Scope expands beyond adapter execution semantics | Keep T8-C-1 out of scope. |
| Dirty baseline is touched | Workflow violation | Stage only T10-1 files. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q10 answered.
- [x] Implementation commits reviewed.
- [x] Focused verification recorded.
- [x] Full discover delta recorded.
- [x] Closure notes filled.

## 6. Closure Notes

T10-1 shipped C76 across all three scoped layers:

- SDK shell: `ProbLogSemantics.uncertainty_projection` now exists, uses the
  canonical `SemanticsProfile.uncertainty_projection` schema, and defaults to
  the C76 reject projection.
- Lowering: ProbLog SDK semantics preview/lowering now passes the projection
  into `SemanticsProfile`.
- Adapter consumption: ProbLog export consumes `shared/semantic/raw_kind` and
  `shared/semantic/bound` with explicit point-projection policy handling.

Implementation chain:

- `4d3ed74e` fixed the two pre-existing ProbLog migration fixture errors
  without weakening C110 legacy `confidence` rejection.
- `bb619279` added the SDK field and lowering path.
- `b7823086` threaded projection into ProbLog export and added explicit
  raw-uncertainty consumption.
- `efcaa36f` added the T10-1 focused policy tests.
- `e7cad68c` fixed the Step 4.7 blocker by defaulting direct
  `_claim_probability(...)` callers to the reject projection.

Verification:

- `tests.test_problog_export.TestProbLogExportReadsSharedProbability` plus
  `tests.test_problog_semantics_profile_migration`: 24 tests OK.
- Focused suite including ProbLog export, ProbLog semantics migration, ProbLog
  evidence graph, audit evidence graph, protocol DTOs, and SDK RuleExpr
  evaluation: 113 tests OK.
- Ruff on changed runtime/test files: clean.
- `git diff --check`: clean.
- Full discover: 2011 tests / 72 failures / 231 errors. This is a real
  two-error improvement from the T10 inventory baseline of 2004 tests /
  72 failures / 233 errors, with seven new T10-1 tests added.

Step 4.7 caught a baseline-equivalence hazard: the first full discover run
still showed 233 errors because T10-1 fixed two known ProbLog fixture errors
but introduced two new direct-call `TypeError`s in `tests/test_problog_export`.
The amend commit removed the replacement errors. Future cycles that fix known
baseline failures should compare failure/error composition, not just totals.

Non-blocking notes:

- The fixture fix moved through an intermediate raw-uncertainty fixture before
  the final source-only fixture state; final behavior is correct because raw
  uncertainty now rejects by default unless projected explicitly.
- Some defensive malformed-annotation branches remain production-guarded but
  not exhaustively unit-tested.
- T10-1 only ships adapter execution semantics. T8-C-1 ProbLog evidence
  enrichment remains a future cycle, now unblocked from the C76 side.
