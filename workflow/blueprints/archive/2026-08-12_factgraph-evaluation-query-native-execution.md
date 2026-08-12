# Task Blueprint: FactGraph EvaluationQuery native execution

- Status: archived
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F3B only.
- Inputs:
  - [`2026-08-12_q5b-evaluation-query-native-execution-decision.md`](../../design/decisions/active/2026-08-12_q5b-evaluation-query-native-execution-decision.md)
  - [`2026-08-12_q5a-evaluation-query-projection-v0-decision.md`](../../design/decisions/active/2026-08-12_q5a-evaluation-query-projection-v0-decision.md)
- Outputs / Downstream:
  - Native SDK execution bridge, focused tests and current-truth docs
- Related:
  - [`2026-08-12_factgraph-evaluation-query-native-execution.audit.md`](./2026-08-12_factgraph-evaluation-query-native-execution.audit.md)
- Related Modules:
  - `src/factgraph/application/evaluation_query_runtime.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/sdk/store.py`
- Audit Log:
  - [`2026-08-12_factgraph-evaluation-query-native-execution.audit.md`](./2026-08-12_factgraph-evaluation-query-native-execution.audit.md)
- Branch: `codex/v0.3.0-f3b-evaluation-query-execution-2026-08-12`
- Base: `5a6f4a55`

## 1. Goal

Execute the exact F3A `CompiledEvaluationQueryV0` through the shipped native
evaluator and return the existing `EvaluateResult`, while preserving a strict
boundary before F4 snapshot/replay semantics.

## 2. Invariants

- Compiler-issued Query state is revalidated immediately before execution.
- The receiving FactGraph schema equals the Query schema pin.
- The exact stored lowering plan is materialized; no reconstruction or re-lowering occurs.
- CandidateSet remains internal and cannot be accepted through the Query path.
- Query rows are ordered typed projections in the existing result envelope.
- Query/Policy/occurrence identity is committed in result fingerprints.
- Evaluation performs no fact/ledger mutation and requires an unchanged live view across the call; normal support-artifact caching remains allowed.
- Lazy close/explain is valid only while that same live view remains current.
- Premise-filtered execution is rejected until F4 can capture its policy with the view.
- Only native execution with no config is admitted.
- F4 bundle/replay and F3 expectation/completeness work remain deferred.
- Added production Python is capped at 320 lines relative to `5a6f4a55`.

## 3. Implementation Plan

1. Factor F3A artifact validation into a reusable internal execution-time guard.
2. Add a native-only SDK dispatch that validates schema/view, materializes the exact plan and invokes the existing application evaluator once.
3. Extend the existing result adapter narrowly for Query fingerprints, projection kind, typed term restoration and live-view guards.
4. Add focused native positive/negative, stale-artifact, read-only, fingerprint and view-mutation tests.
5. Run legacy Query/RuleExpr/evaluate/Explain/Match cohorts, Ruff, targeted mypy, diff/cap checks and adversarial probes.
6. Update application and SDK current-truth docs, then hand a bounded read-only review packet to the user's Agent.

## 4. Acceptance

- [x] Exact native bind/select execution returns the expected ordered rows.
- [x] Non-matching binding returns an empty `EvaluateResult`, not a false claim.
- [x] Query execution never mutates facts/the ledger and does not expose candidates.
- [x] Artifact/schema/view changes fail closed at the documented boundary.
- [x] Projection kind, typed tags and Query/Policy fingerprints are correct.
- [x] Live row close/explain works before, and rejects after, view mutation.
- [x] Non-native/config/manual-explain/candidate surfaces reject.
- [x] Premise-filtered execution and later premise-policy changes reject.
- [x] Legacy cohorts and static checks pass within the production line cap.
- [x] Current-truth docs state the live-view and native-only limits.

## 5. Outcome / Deviations

- Implementation `c94c5bf9` executes the exact F3A plan through the native
  evaluator and returns the existing result model; CandidateSet remains private.
- The full application/SDK cohort is 458 tests passing with 96 subtests. Ruff,
  targeted mypy for the new runtime module and `git diff --check` pass.
- Production Python is 317 gross additions relative to `5a6f4a55`, within the
  320-line stop. The remaining margin is intentionally unused.
- Three internal independent reviews returned CLEAR with zero blocking
  findings. The user-side read-only review independently repeated 458 tests,
  static checks and 33 adversarial probes and returned CLEAR with zero P0/P1/P2.
- The independent review clarified one non-finding boundary: stale
  `row.close()` raises while stale `row.explain()` returns an unsupported
  Explanation under the shipped error-envelope contract. Both paths fail
  closed and neither emits stale evidence.
- Candidate identity is not a durable Query identity. F4 must bind any bundle
  or replay anchor to the Query/result fingerprints rather than CandidateSet IDs.
- The base interpreter still exits 139 during broad pytest startup; the pinned
  `factpy` environment completes the stated cohorts. No engine parity beyond
  native, immutable replay, expectations or completeness is claimed.
- This blueprint and its paired audit are archived together after the external
  CLEAR review; current implementation truth remains in the module docs.
