# Audit: T5.5 Why-Not Fold + Legacy Evidence Quarantine

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.md`
- Stage: T5.5 implementation blueprint implemented
- Class: M (predicted; split if hard-cut deletion or service/docs migration leaks in)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | `62c8eb1a` | Blueprint pair drafted | T5.5 Why-Not Fold + Legacy Evidence Quarantine draft created after T5.4 archive `7464c3e3`. Scope is M-class predicted and intentionally minimal: failed Explanation is v1 why-not envelope; legacy why-not hard-cut remains T5.7. |
| 2026-05-25 | scoped | pending | Step 4.6 grep clean | Eight grep buckets completed. Existing WhyNot protocol/runtime/shells, round-event payloads, docs/examples, and T5.3/T5.4 explanation paths are expected substrate or future T5.7 territory. No public `.eval.why_not`, no result/explanation why-not method, and no lossy WhyNot/Diagnose-to-Explanation conversion path found. Scope remains M-class minimal. |
| 2026-05-25 | baseline | pending | G7 preservation baseline recorded | Ran inherited G7 command at scoped anchor `a27feb0f`: 170 tests OK in 0.098s. Pytest remains deferred per existing SIGSEGV environment lock; `tests.test_public_inference_factgraph_create` remains excluded. |
| 2026-05-25 | feat | pending | Why-not quarantine implemented | Added T5 quarantine markers to legacy WhyNot protocol/runtime/SDK shell surfaces and focused tests proving failed Explanation is the v1 why-not envelope, no T5 public why-not surface exists, legacy why-not remains quarantined, and no lossy conversion path exists. Verification: 4 T5.5 tests OK; 37 focused T5.1-T5.5 preservation tests OK; 170 G7 tests OK; touched-file ruff clean. |
| 2026-05-25 | implemented | pending | T5.5 closure recorded | Marked blueprint/audit implemented. Step 4.7 review was clean with 0 P0/P1. T5.6, T5.7, and optional T5.8 deferred boundaries remain explicit. |

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

## 8. Step 4.6 Pre-Implementation Grep Results

| # | Check | Actual result | Classification |
|---|---|---|---|
| 1 | Public eval why-not namespace | `SDKStore.why_not(...)`, `sdk_why_not(...)`, `fg.what_if.why_not(...)` docs/tests, and `why_not_result` round-event payload hits remain. No `_SDKEvalManager.why_not`, `fg.eval.why_not(...)`, `EvaluateResult.why_not(...)`, `why_not_v2`, or T5 public eval why-not owner exists. | Clean. Existing hits are legacy surfaces, historical docs, round events, or T5.7 hard-cut targets. |
| 2 | WhyNot DTO family | `WhyNotUniverseRequest`, `WhyNotUniverseResult`, red-row diagnostics, atom locator, and enums remain in application protocol/runtime/tests and application-protocol exports. SDK `__all__` still does not expose `WhyNotUniverseResult`. | Expected. T5.5 classifies these as legacy/internal relative to T5; D23/T5.7 owns deletion or migration. |
| 3 | Failed Explanation paths | `Explanation.failure_class`, the five failure classes, and `status="failed"` are present in T5.3/T5.4 implementation/tests. Other `status="failed"` hits belong to Check/Diagnose/Overlay/service payloads. | Clean substrate. T5.5 may add narrow tests; no WhyNot conversion found here. |
| 4 | Lossy conversion guard | `rg "WhyNot.*Explanation|Explanation.*WhyNot|atom_locator.*Explanation|DiagnoseResult.*Explanation|diagnostic.*failure_class" src tests` returned no hits. | Clean. No shipped lossy WhyNot/Diagnose-to-Explanation conversion path exists. |
| 5 | Legacy hard-cut boundary | `SDKStore.why_not`, `sdk_why_not`, `check_why_not_universe`, and `fg.what_if.why_not` hits are present in legacy runtime, shell tests, SDK docs, and older blueprint/archive material. | Expected. Behavior/signature changes are out of T5.5 scope; hard-cut remains T5.7. |
| 6 | Service/OpenAPI/docs guard | Service/docs/examples/tests include broad why-not, counterfactual, and `what_if` references, including examples and public docs that still teach legacy why-not. | Expected. T5.5 does not migrate service/OpenAPI/examples; T5.7 owns broad migration. |
| 7 | SDK Rule / adapter / semantics guard | `LegacyRule`, `ApplicationRule`, `SemanticsProfile`, `raw_kind`, and `bound` hits are existing T3/T4/T5 substrate, design docs, tests, and archived adapter semantics work. | Clean guard. No T5.5 implementation owner in SDK Rule naming, adapters, or C73-C78 semantics. |
| 8 | T5 public evidence surface | `row.explain()` and `fg.eval.explain(...)` hits are T5.3/T5.4 implementation/tests and design/archive docs. No `EvaluateResult.why_not(...)` or `Explanation.why_not(...)` production owner exists. | Clean. T5.5 preserves row/manual explain as the only T5 evidence path. |

Scope decision: T5.5 remains a minimal M-class quarantine/fold slice. The grep results do not trigger A-fallback, a split, D23 deletion, service/docs migration, SDK Rule work, or adapter work.

## 9. G7 Baseline Plan

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
| Scoped anchor | `a27feb0f` |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | `Ran 170 tests in 0.098s, OK` |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 10. Draft Review Checklist

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
| Step 4.6 grep results clean | Yes |
| G7 baseline plan present | Yes |

## 11. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| T5.5 may be too lightweight | Confirm quarantine/tests are enough before T5.7 hard-cut. |
| Legacy why-not behavior may be accidentally changed | Confirm behavior/signature changes are out of scope. |
| Negative tests may overfit symbol names | Confirm symbols are exactly the forbidden public surfaces from D22. |
| Failed Explanation may not yet cover enough failure paths | Confirm closed-head false/manual failed path is sufficient for T5.5. |
| Docs migration pressure may leak in | Confirm broad docs/OpenAPI/examples remain T5.7. |

## 12. Closure Notes

### Commit References

- `62c8eb1a` — draft blueprint pair.
- `a27feb0f` — scoped Step 4.6 grep results.
- `879b0d56` — G7 baseline, 170 OK.
- `5113e13d` — feat implementation.
- Closure commit: pending.

### Final State

T5.5 is implemented as a minimal M-class quarantine/fold slice. The T5 public evidence path stays `row.explain()` and `fg.eval.explain(...)`; no public `.eval.why_not(...)` or result/explanation why-not method was added.

### Verification Summary

- 4 T5.5 quarantine tests OK.
- 37 focused T5.1-T5.5 preservation tests OK.
- 170 G7 preservation tests OK.
- Touched-file ruff clean.
- `git diff --check` clean.

### Deferred Work

- T5.6: final SDK `Rule` flip.
- T5.7: broad legacy hard-cut, service/OpenAPI/docs migration, and final WhyNot shell/DTO disposition.
- T5.8 optional: Semantics Lite.
- Post-T5: any new why-not product/API requires a new D-doc, non-lossy algorithm, and evidence-tree support.

### Dirty / Sacred State

Sacred `master` remains untouched. Dirty baseline remains 6 modified + 1 untracked and was not folded into T5.5.
