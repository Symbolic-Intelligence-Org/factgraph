# Task Blueprint: FactGraph EvaluationRun anchors

- Status: implemented
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F4A only.
- Inputs:
  - [`2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md`](../../design/decisions/active/2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md)
  - Q4B / F2B Policy compiler and Q5A-Q5C / F3A-F3C implementations
  - 2026-08-12 three-way read-only F4 entry audit
- Outputs / Downstream:
  - In-process `EvaluationRunAnchorV0`
  - Canonical authored `PolicyStructureV0`
  - F4B detached replay and F4C Policy-aware Explain inputs
- Related:
  - [`2026-08-12_factgraph-evaluation-run-anchors.audit.md`](./2026-08-12_factgraph-evaluation-run-anchors.audit.md)
- Related Modules:
  - `src/factgraph/application/protocol/policy.py`
  - `src/factgraph/application/policy_runtime.py`
  - `src/factgraph/application/protocol/evaluation_run.py`
  - `src/factgraph/application/evaluation_run_runtime.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/sdk/store.py`
- Audit Log:
  - [`2026-08-12_factgraph-evaluation-run-anchors.audit.md`](./2026-08-12_factgraph-evaluation-run-anchors.audit.md)
- Branch: `codex/v0.3.0-f4a-evaluation-run-anchors-2026-08-12`
- Base: `ca12b208`

## 1. Goal

Attach a self-checking, pure-data identity anchor to existing native
`EvaluationQuery` results without claiming snapshot capture or replay, and
preserve authored Policy topology needed by later Policy-aware Explain.

## 2. Invariants

- Existing `EvaluateResult` is the singular row envelope and execution return.
- Legacy evaluation semantics, positional construction and the documented
  service wire shape remain compatible with `run_anchor=None`; Python object
  `repr`, pickle and `asdict` shapes are not byte protocols.
- Query results receive exactly one anchor after result construction.
- Authored Policy structure is captured before lowering and participates in the
  Policy digest/integrity check.
- Run/row/summary anchors contain no callback, Store, schema object, support
  carrier or derivation/candidate identity.
- Semantic row identity excludes random run-local IDs; duplicate observations
  remain possible and explicit.
- Zero rows produce only a query-summary anchor and no truth interpretation.
- F4A remains native, identity-only, digest-only-live-view and non-replayable.
- Existing EvidenceGraph/EvidenceTree semantics remain unchanged.
- Gross added production Python is capped at 720 lines relative to `ca12b208`;
  the amendment covers strict seals, cross-object result matching and authored
  topology validation only.

## 3. Implementation Plan

1. Add canonical Policy structure DTOs and derive them directly from
   `Policy.when`; bind their digest into `CompiledPolicyV0` integrity.
2. Add immutable Run target/input/selection/profile/row/summary/anchor DTOs and
   strict shape validation.
3. Build the anchor from the already compiled Query and completed
   `EvaluateResult`; attach it only on the Query path and cross-check all result
   and row pins in `EvaluateResult.__post_init__`.
4. Add the anchor digest to Query Explanation checked scope without modifying
   engine evidence.
5. Add focused structure, stable-row, zero-row, duplicate, splice, stale-view
   and legacy compatibility tests.
6. Run the application/SDK Policy/Query/evaluate/Explain cohorts, Ruff, targeted
   mypy, diff/cap checks and independent adversarial review.

## 4. Acceptance

- [x] `PolicyStructureV0` exactly represents authored root/children/aliases/Unify endpoints.
- [x] Policy structure and total lineage are both digest-bound and splice-checked.
- [x] Query `EvaluateResult.run_anchor` is present, pure, self-checking and result-matched.
- [x] Legacy `EvaluateResult.run_anchor` remains `None`.
- [x] Row anchors are stable across repeated equivalent runs while run IDs differ.
- [x] Duplicate rows do not acquire false uniqueness; ordinal is observational only.
- [x] Empty results have a stable summary anchor, zero row anchors and no false claim.
- [x] Target/query/policy/profile/view/result/row mutations fail closed.
- [x] Row Explain checked scope names the exact Run anchor.
- [x] No replay/codec/registry/What-if/Policy-overlay surface is added.
- [x] Focused and legacy test/static cohorts pass within the line cap.

## 5. Preflight And Review Basis

The lightweight path uses three independent read-only audits instead of a
separate document-only preflight. They independently covered the existing Run
contract, snapshot/replay boundary and architectural scope. All converged on
the same three-slice split. This does not waive implementation tests or the
final independent review.

## 6. Outcome / Deviations

- Implementation `ab1e34b0` adds canonical authored `PolicyStructureV0`, binds
  it into compiled Policy integrity, and attaches an identity-only
  `EvaluationRunAnchorV0` to the existing native Query result envelope.
- Stable semantic row anchors exclude random run-local IDs; summary anchors
  preserve duplicate-row multiplicity and represent zero rows without a truth
  or completeness claim.
- Result construction independently matches the sealed anchor against the
  actual result, execution profile, timestamp, projection head and complete row
  semantics. Repository tests cover self-consistently resealed mismatch attacks.
- The application/SDK cohort passed **464 tests + 104 subtests**. Ruff, targeted
  mypy for the four F4A/Policy modules and `git diff --check` passed.
- Production Python growth is **708 gross additions / 720 allowed** relative to
  `ca12b208`. The remaining margin is intentionally unused.
- Two internal fixed-state reviews and the user-side independent review returned
  CLEAR with zero P0/P1/P2 after 27 additional attack probes.
- No durable codec, snapshot contents, replay, repository, registry, Scenario,
  Meander integration or Policy-aware Evidence overlay was introduced. Digest
  seals establish in-process consistency rather than cross-trust authentication;
  F4B and F4C retain those downstream responsibilities.
