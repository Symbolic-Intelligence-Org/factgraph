# Audit: T5.1 DTO Foundation + Digest Harness

- Status: implemented
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
| 2026-05-25 | scoped | pending | Step 4.6 grep clean; scope locked | Grep found expected docs/history/agent/service/runtime hits, no shipped T5 `EvaluateResult` / `EvaluateRow` production owner, no public evaluate flip, no D20-D24 implementation collision, and no adapter edit target. |
| 2026-05-25 | baseline | pending | G7 preservation baseline recorded | Baseline command ran 163 tests in 0.077s, OK; scoped anchor `457b55d0`; pytest remains deferred and `tests.test_public_inference_factgraph_create` remains excluded. |
| 2026-05-25 | feat | `a3e96eb6` | DTO foundation + digest harness implemented | Added application-protocol result DTOs, digest helpers, private CandidateSet conversion harness, and SDK DTO re-exports. Gates: 13 focused DTO/digest/export tests OK, G7 preservation 163 tests OK, touched-file ruff clean. |
| 2026-05-25 | implemented | pending | Closure recorded after Step 4.7 review | Step 4.7 review found 0 P0/P1 and 3 optional nits; no fix commit required. T5.1 ready for archive after this closure. |

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
| G7 | Establishes baseline before feat | Satisfied: 163 tests OK recorded after scoped. |

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

## 7. Step 4.6 Pre-Implementation Grep Results

Executed on branch `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` after draft review.

| # | Check | Result | Scope decision |
|---|---|---|---|
| 1 | Existing result DTO names | Broad workflow/design docs mention T5 DTO names. `src/agent/` has an unrelated agent-layer `EvaluateResult`. `src/factgraph/core/store/ledger.py` has storage-layer `Claim`. No `src/factgraph` production implementation of T5 `EvaluateResult`, `EvaluateRow`, `EvidenceRef`, or `DetachedRowError` exists. | Expected; no collision with application-protocol T5 DTO namespace. |
| 2 | CandidateSet public/internal references | Many existing runtime, adapter, service, agent, docs, and tests references. `src/factgraph/application/derivation_runtime.py`, `src/factgraph/core/store/_evaluate.py`, adapters, and service routes still operate on `list[CandidateSet]`. | Expected. T5.1 may add a private conversion harness only; public flip remains T5.2 and service hard-cut remains T5.7. |
| 3 | Digest helper namespace | Existing `sha256_hex` / `sha256_token` helpers, `Rule.content_digest`, store `view_digest_for`, and semantics/design references found. No central T5 result/digest helper path exists yet. | Expected. T5.1 can introduce one authoritative helper path and must preserve shipped `Rule.content_digest` bare-hex format. |
| 4 | Public evaluate flip gates | `SDKStore.evaluate(...)` and application `evaluate_derivation_plans(...)` still return `list[CandidateSet]`; docs/tests still reference `engine_options`, `registry=`, and CandidateSet return shape. | Expected. T5.1 must not alter these; T5.2/D18 and T5.7/D23 own migration. |
| 5 | Explanation / close / why-not gates | Existing Check/Diagnose/WhyNot protocol/runtime/shells and audit/service `EvidenceGraph` surfaces found. No T5 public `Explanation` DTO or `row.explain` / `row.close` implementation owner exists in `src/factgraph` result DTO surface. | Expected. T5.1 remains DTO/digest only; D20-D22 own these surfaces. |
| 6 | SDK Rule naming gate | Current SDK namespace still has `Rule` as legacy DSL class, `LegacyRule` alias, and `ApplicationRule` alias to application protocol `Rule`; tests assert current pre-D24 behavior. | Expected. T5.1 may add DTO exports but must not change SDK `Rule` naming. |
| 7 | Adapter / semantics gate | Existing adapter production modules and semantics profile tests/docs are extensive for ProbLog, PyReason, and Souffle. `SemanticsProfile` is already exported from SDK. | Expected. T5.1 only consumes normalized `SemanticsProfile` for digest helper; adapter edits remain out of scope. |
| 8 | `Rule.content_digest` precision check | `Rule.content_digest` is implemented in `application/protocol/rule.py` and consumed by RuleExpr lowering/tests. It is bare 64-hex and order-sensitive. | Expected. T5.1 must embed it as named source data, not reformat or modify it. |
| 9 | Application protocol DTO pattern | Existing protocol modules define local `__all__` and are re-exported through `application/protocol/__init__.py`; Check/Diagnose/WhyNot patterns provide DTO validation precedent. | Expected. T5.1 should follow this module + `__all__` style. |
| 10 | T5.2-T5.8 guard words | Hits map to existing docs, tests, service/agent surfaces, or reviewed design artifacts. No unexpected implementation owner for public return-shape flip, row methods, hard-cut, final Rule flip, or adapter semantics was found. | Clean; no A-fallback amendment required. |

## 8. G7 Baseline Plan

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

Baseline record:

| Field | Value |
|---|---|
| Branch | `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` |
| Sacred state | `master = 562c74195df43e933bed92a3ff25de94dd8ce666`; untouched |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | `457b55d0` |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | `Ran 163 tests in 0.077s`, `OK` |
| Pytest policy | Deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 9. Draft Review Checklist

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
| Step 4.6 grep results clean | Yes |
| G7 baseline plan present | Yes |
| G7 baseline result recorded | Yes |

## 10. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| `view_snapshot_digest` too broad | Confirm T5.1 can stay M-class or require split/amend. |
| DTO validation over-specified | Check that blueprint leaves implementation freedom where D17/D19 do not lock details. |
| CandidateSet helper leaks public compatibility | Confirm conversion helper is private and not a public evaluate flip. |
| Row methods accidentally implement T5.3/T5.4 | Confirm only detached/live plumbing is allowed. |
| SDK exports preempt D24 | Confirm only new DTO names are exported. |

## 11. Outcome

### Final Code Scope

Production:

1. `src/factgraph/application/protocol/evaluate_result.py` added the five T5.1 DTOs, D19 digest helpers, private row digest helper, private CandidateSet conversion helper, and `view_snapshot_digest_for_parts(...)`.
2. `src/factgraph/application/protocol/__init__.py` added application-protocol DTO exports.
3. `src/factgraph/sdk/__init__.py` added SDK DTO exports while preserving current `Rule` / `LegacyRule` / `ApplicationRule` behavior.

Tests:

1. `tests/application/protocol/test_evaluate_result_dtos.py` covers DTO invariants, live/detached plumbing, duplicate row-id rejection, and CandidateSet conversion boundary.
2. `tests/application/protocol/test_evaluate_result_digests.py` covers deterministic digest helpers, namespace formats, result digest acyclicity, semantics digest behavior, and view snapshot substrate.
3. `tests/sdk/test_evaluate_result_exports.py` covers SDK re-exports and verifies no SDK Rule flip.

### Verification

| Gate | Result |
|---|---|
| G7 baseline | `6c4b2cba`: 163 tests OK. |
| Feature preservation | `a3e96eb6`: 163 tests OK. |
| Focused T5.1 tests | 13 DTO/digest/export tests OK. |
| Ruff | Touched production and test files clean. |
| Pytest | Deferred per existing SIGSEGV environment lock. |
| Excluded test | `tests.test_public_inference_factgraph_create` remains excluded. |

### Scope Preservation

1. No public `evaluate(...)->EvaluateResult` return-shape flip.
2. No public `row.explain()` or `row.close()`.
3. No `Explanation`, public evidence graph, why-not, or renderer surface.
4. No SDK top-level `Rule` naming flip.
5. No legacy hard-cut.
6. No service route, OpenAPI, or final docs migration.
7. No adapter production file edit.
8. No C73-C78 semantics implementation.
9. No `Rule.content_digest` format or formula change.
10. No public CandidateSet compatibility surface.
11. No storage-layer `ledger.Claim` re-export as T5 `Claim`.
12. Dirty baseline remained 6 modified + 1 untracked and was not included.

### Step 4.7 Disposition

- 0 P0 / 0 P1.
- No Step 4.7 fix commit required.
- Optional Nit N1: canonical bytes use deterministic JSON object normalization; accepted and covered by tests.
- Optional Nit N2: in-memory SDK-store view snapshot integration remains a T5.2 follow-up when public evaluation wiring exists.
- Optional Nit N3: CandidateSet conversion default `claim_kind="fact_triple"` is acceptable; future T5.2 callers can override.

### Deferred

1. T5.2: public `evaluate(...) -> EvaluateResult` wiring, runtime view snapshot source, and return-shape hard cut.
2. T5.3: `Explanation` and live row resolver behavior.
3. T5.4: `row.close()` and manual closed-head explain gate.
4. T5.5: why-not fold/quarantine.
5. T5.6: final SDK `Rule` flip.
6. T5.7: legacy hard-cut, service route/OpenAPI/docs migration.
7. T5.8 or post-T5: semantics lite / adapter-touching semantics work.
