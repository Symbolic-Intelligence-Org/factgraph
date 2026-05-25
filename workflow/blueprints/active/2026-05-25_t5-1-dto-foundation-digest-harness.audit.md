# Audit: T5.1 DTO Foundation + Digest Harness

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- Stage: T5.1 implementation blueprint draft
- Class: M (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | pending | Blueprint pair drafted | T5.1 DTO Foundation + Digest Harness draft created from reviewed-clean T5 Stage 1-3 design layer. |

## 2. Source Chain

T5.1 consumes the reviewed-clean design layer:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D17 DTO foundation: `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
- D18 return-shape transition: `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
- D19 digest source-of-truth: `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
- D20 Explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
- D21 row.close / closed-head gate: `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
- D23 legacy hard-cut: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- D24 final SDK Rule flip: `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
- D25 evaluate/explain semantics consistency: `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
- D26 semantics scope: `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `src/factgraph/core/derivation/candidates.py` | `CandidateSet` fields and identifier helpers | D17/D18 classify CandidateSet as internal but T5.1 needs conversion harness. |
| `src/factgraph/core/protocol/digests.py` | `sha256_hex`, `sha256_token` | D19 requires new T5 public digests to use `sha256:` tokens. |
| `src/factgraph/application/protocol/__init__.py` | public protocol export index | T5.1 DTOs must export from application protocol. |
| `src/factgraph/sdk/__init__.py` | SDK export index and current Rule namespace | T5.1 adds DTO re-exports but must not do D24 Rule flip. |
| `src/factgraph/core/store/database.py` | `view_digest_for(...)`, database view digest substrate | D19 makes `view_snapshot_digest` mandatory and forbids placeholders. |
| `src/factgraph/core/semantics/profile.py` | `SemanticsProfile` 10-field normalized shape | D19 semantics digest source-of-truth. |
| `src/factgraph/sdk/semantics.py` | `ProbLogSemantics`, `PyReasonSemantics` wrappers | Confirms wrapper lowering must not be identity-based. |
| `src/factgraph/sdk/store.py` | public semantics lowering and evaluation entry points | T5.1 must not flip public evaluate output. |

Pre-draft name grep found no existing production implementation of `EvaluateResult` / `EvaluateRow` as T5 DTOs.

## 4. Scope Mapping

| Stage 3 item | T5.1 draft treatment |
|---|---|
| D17 DTOs | In scope: `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`. |
| SDK re-exports | In scope for DTOs only. |
| CandidateSet conversion | In scope as internal harness only. |
| D19 digest helpers | In scope with centralized formulas and tests. |
| `view_snapshot_digest` | In scope and mandatory; no placeholder fallback. |
| Public evaluate flip | Out of scope; T5.2. |
| Explanation / row.explain | Out of scope; T5.3. |
| row.close / manual explain | Out of scope; T5.4. |
| Why-not | Out of scope; T5.5/D22. |
| SDK Rule flip | Out of scope; T5.6/D24. |
| Legacy hard-cut and service/docs migration | Out of scope; T5.7/D23. |
| Semantics adapter work | Out of scope; T5.8/D26 or post-T5. |

## 5. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 Stage 1-3 design inputs | Satisfied. |
| G2 | Has narrow implementation scope | Satisfied: DTO/digest only. |
| G3 | Has explicit negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in this audit section 3. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; no code changes in draft. |
| G7 | Establishes baseline plan before feat | Pending scoped + baseline commits. |

## 6. Step 4.6 Pre-Implementation Grep Plan

Run these before implementation and record actual results in a scoped commit.

| # | Check | Command shape | Expected |
|---|---|---|---|
| 1 | Existing result DTO names | `rg "EvaluateResult|EvaluateRow|EvidenceRef|DetachedRowError|class Claim" src tests workflow` | Docs only or unrelated storage-layer `Claim`; no shipped T5 DTO implementation. |
| 2 | CandidateSet public/internal references | `rg "CandidateSet|candidate_id|candidate_key|support_digest|confidence_kind" src tests` | Existing runtime/tests only; no public T5 output surface to preserve. |
| 3 | Digest helper namespace | `rg "sha256_token|sha256_hex|view_digest_for|semantics_digest|result_digest|row_id" src tests workflow` | Existing digest helpers plus T5 docs; no duplicate T5 helper path yet. |
| 4 | Public evaluate flip gates | `rg "evaluate_derivation_plans|_evaluate_rule_expr_input|SDKStore.evaluate|list\\[CandidateSet\\]|engine_options|registry=" src tests` | Identify callers for T5.2; T5.1 must not mutate public return shape. |
| 5 | Explanation / close / why-not gates | `rg "row\\.explain|row\\.close|Explanation|why_not|EvidenceGraph|CheckResult|DiagnoseResult" src tests` | Existing surfaces only; T5.1 must not implement D20-D22 behavior. |
| 6 | SDK Rule naming gate | `rg "LegacyRule|ApplicationRule|from \\.dsl import.*Rule|__all__|Rule =" src/factgraph/sdk src/factgraph/application/protocol tests/sdk` | Establish D24 boundary; T5.1 only adds DTO exports. |
| 7 | Adapter / semantics gate | `rg "problog|pyreason|souffle|SemanticsProfile|ProbLogSemantics|PyReasonSemantics" src/factgraph tests` | Existing adapter/semantics code only; no T5.1 adapter production edit target. |

If grep shows unexpected production DTO or digest substrate collisions, amend the blueprint before scoped.

## 7. G7 Baseline Plan

Command:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected result: 163 tests OK, inherited from the T4.3 final preservation gate.

Baseline record fields to fill later:

| Field | Value |
|---|---|
| Branch | Pending |
| Sacred state | Pending |
| Dirty baseline | Pending |
| Scoped anchor | Pending |
| Command | Pending |
| Result | Pending |
| Pytest policy | Deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 8. Draft Review Checklist

| Item | Status |
|---|---|
| D17 DTO fields represented | Yes |
| D19 digest formulas represented | Yes |
| D18 public return-shape flip excluded | Yes |
| D20/D21 row methods excluded except detached plumbing | Yes |
| D23 hard-cut excluded | Yes |
| D24 Rule flip excluded | Yes |
| D26 adapter semantics excluded | Yes |
| `view_snapshot_digest` no-placeholder rule explicit | Yes |
| Step 4.6 grep plan present | Yes |
| G7 baseline plan present | Yes |

## 9. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| `view_snapshot_digest` too broad | Confirm T5.1 can stay M-class or require split/amend. |
| DTO validation over-specified | Check that blueprint leaves implementation freedom where D17/D19 do not lock details. |
| CandidateSet helper leaks public compatibility | Confirm conversion helper is private and not a public evaluate flip. |
| Row methods accidentally implement T5.3/T5.4 | Confirm only detached/live plumbing is allowed. |
| SDK exports preempt D24 | Confirm only new DTO names are exported. |

## 10. Outcome

Pending.
