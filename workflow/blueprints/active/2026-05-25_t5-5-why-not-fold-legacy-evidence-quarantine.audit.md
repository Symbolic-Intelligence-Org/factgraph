# Audit: T5.5 Why-Not Fold + Legacy Evidence Quarantine

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.md`
- Stage: T5.5 implementation blueprint draft
- Class: M (predicted; split if hard-cut deletion or service/docs migration leaks in)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | pending | Blueprint pair drafted | T5.5 Why-Not Fold + Legacy Evidence Quarantine draft created after T5.4 archive `7464c3e3`. Scope is M-class predicted and intentionally minimal: failed Explanation is v1 why-not envelope; legacy why-not hard-cut remains T5.7. |

## 2. Source Chain

T5.5 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D20 explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
- D22 why-not disposition: `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
- D23 legacy SDK hard-cut plan: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- T5.3 archive: `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`
- T5.4 archive: `workflow/blueprints/archive/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `src/factgraph/application/protocol/derivation_why_not.py` | module + DTO definitions | Confirms shipped WhyNot DTO family and atom locator still exist as legacy surface. |
| `src/factgraph/application/why_not_runtime.py` | `check_why_not_universe(...)` | Confirms shipped runtime computes explicit green/red candidate-universe boards. |
| `src/factgraph/sdk/store.py` | `SDKStore.why_not(...)` and T5.4 `explain(...)` | Confirms legacy SDK why_not remains and T5 manual explain is now the T5 evidence path. |
| `src/factgraph/sdk/shells/why_not.py` | `sdk_why_not(...)` | Confirms legacy shell returns `WhyNotUniverseResult` directly. |
| `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md` | T5.5 slice section | Confirms T5.5 must be quarantine/fold, not hard-cut deletion. |
| `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md` | sections 4.1-4.7 | Defines no public `.eval.why_not`, failed Explanation as envelope, legacy/internal classification, and future door. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| Public T5 why-not | No `fg.eval.why_not(...)` implementation exists; `_SDKEvalManager` has `evaluate`, `explain`, `inspect_semantics`, `accept`, and `accept_many`. |
| Legacy why-not | `SDKStore.why_not(...)`, `sdk.shells.why_not.sdk_why_not(...)`, application WhyNot DTOs, and `check_why_not_universe(...)` remain shipped. |
| Failed Explanation | T5.3/T5.4 provide `Explanation(status="failed")` paths for row/manual explain failures. |
| Atom locator | `WhyNotAtomLocator` remains in legacy protocol only; no T5 `Explanation` field references it. |
| Service/docs | Broad CandidateSet/why-not docs and service references remain future T5.7 hard-cut territory. |

## 5. Scope Mapping

| Stage 3 / D-doc item | T5.5 draft treatment |
|---|---|
| D22 no public `.eval.why_not(...)` | In scope through negative tests and surface guard. |
| D22 failed Explanation is v1 why-not envelope | In scope through tests and narrow quarantine markers. |
| D22 shipped WhyNot DTOs legacy/internal | In scope through classification markers and no-reexport/no-adoption tests. |
| D22 no lossy conversion | In scope through tests forbidding WhyNot/Diagnose payloads in failed Explanation. |
| D23 hard-cut mechanics | Out of scope; T5.7 owns deletion and broad migration. |
| D20 failure matrix | Preserved and tested. |
| Evidence-tree failed-node schema | Out of scope. |
| Future why-not API | Out of scope; new D-doc required. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.5 fold/quarantine scope | Satisfied; M-class predicted with hard-cut leak trigger. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft docs only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 170 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before scoped and record actual results.

| # | Check | Command shape | Expected / classification |
|---|---|---|
| 1 | Public eval why-not namespace | `rg "eval\\.why_not|def why_not\\(|why_not_v2|why_not_result|counterfactuals|\\.why_not\\(" src tests workflow` | Existing legacy `SDKStore.why_not` and docs expected; no `_SDKEvalManager.why_not`. |
| 2 | WhyNot DTO family | `rg "WhyNotUniverse|WhyNotRedRow|WhyNotRowDiagnostic|WhyNotAtomLocator|WhyNotStatus|WhyNotEngine|WhyNotFailureKind|WhyNotRowGranularity" src tests workflow` | Legacy protocol/runtime/tests/docs expected; T5.5 must not adopt as T5 public DTOs. |
| 3 | Failed Explanation paths | `rg "status=\\\"failed\\\"|failure_class|closed_head_false|no_matching_row|row_not_in_result|insufficient_closed_bindings" src tests workflow` | D20/T5.3/T5.4 substrate expected; T5.5 may add focused tests. |
| 4 | Lossy conversion guard | `rg "WhyNot.*Explanation|Explanation.*WhyNot|atom_locator.*Explanation|DiagnoseResult.*Explanation|diagnostic.*failure_class" src tests` | Should be absent except design text/tests asserting forbidden conversion. |
| 5 | Legacy hard-cut boundary | `rg "SDKStore\\.why_not|sdk_why_not|check_why_not_universe|fg\\.what_if\\.why_not|what_if\\.why_not" src tests docs workflow` | Existing legacy hits expected; deletion remains T5.7. |
| 6 | Service/OpenAPI/docs guard | `rg "why_not|WhyNot|counterfactual|inferences/why|what_if" src/service src/agent docs docs/api examples tests` | Broad hits expected; T5.5 should not migrate service/OpenAPI/examples. |
| 7 | SDK Rule / adapter guard | `rg "LegacyRule|ApplicationRule|src/factgraph/adapters|SemanticsProfile|raw_kind|bound" src tests workflow` | Existing substrate only; no T5.5 owner. |
| 8 | T5 public evidence surface | `rg "row\\.explain|eval\\.explain|EvaluateResult\\.why_not|Explanation\\.why_not" src tests workflow` | T5.3/T5.4 paths expected; no result why-not method. |

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

Expected result: 170 tests OK, inherited from T5.4 archive.

Baseline record:

| Field | Value |
|---|---|
| Branch | `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` |
| Sacred state | `master = 562c74195df43e933bed92a3ff25de94dd8ce666` |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | pending |
| Command | pending |
| Result | pending |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 9. Draft Review Checklist

| Item | Status |
|---|---|
| D22 no public `.eval.why_not` represented | Yes |
| D22 failed Explanation envelope represented | Yes |
| D22 shipped WhyNot DTO quarantine represented | Yes |
| D22 no lossy conversion represented | Yes |
| D22 future why-not door preserved | Yes |
| D23 deletion/migration excluded | Yes |
| D20 failure matrix preserved | Yes |
| Service/OpenAPI/docs migration excluded | Yes |
| SDK Rule flip excluded | Yes |
| Adapter semantics excluded | Yes |
| Step 4.6 grep plan present | Yes |
| G7 baseline plan present | Yes |

## 10. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| T5.5 may be too lightweight | Confirm quarantine/tests are enough before T5.7 hard-cut. |
| Legacy why-not behavior may be accidentally changed | Confirm behavior/signature changes are out of scope. |
| Negative tests may overfit symbol names | Confirm symbols are exactly the forbidden public surfaces from D22. |
| Failed Explanation may not yet cover enough failure paths | Confirm closed-head false/manual failed path is sufficient for T5.5. |
| Docs migration pressure may leak in | Confirm broad docs/OpenAPI/examples remain T5.7. |

## 11. Outcome

Pending.
