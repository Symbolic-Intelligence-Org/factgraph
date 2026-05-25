# Audit: T5.7 Legacy Hard-Cut + Service/Docs Migration

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-7-legacy-hard-cut-service-docs-migration.md`
- Stage: T5.7 implemented
- Class: L (scoped; implement as three adjacent M-class local sub-slices)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | pending | Blueprint pair drafted | T5.7 Legacy Hard-Cut + Service/Docs Migration draft created after T5.6 archive `7aa1c6a3`. Scope is predicted L-class: complete D23 hard-cut, migrate service/OpenAPI/docs, decide legacy DSL Rule and why-not final disposition, and preserve private CandidateSet runtime as needed. |
| 2026-05-25 | scoped | pending | Step 4.6 inventory recorded | Grep found 99 files with service, agent, OpenAPI, docs, examples, tests, CandidateSet, accept, what-if, why-not, `ApplicationRule`, or legacy DSL Rule references. T5.7 remains one L-class blueprint but will implement through T5.7a/T5.7b/T5.7c local M-class sub-slices; no sub-slice is push-ready until the full public story is coherent. |
| 2026-05-25 | baseline | pending | G7 baseline recorded | Ran inherited G7 preservation command at scoped anchor `272a57f4`: 171 tests in 0.100s, OK. Pytest remains deferred and `tests.test_public_inference_factgraph_create` remains excluded from G7. |
| 2026-05-25 | feat-a | `41f7e60f` | Service / agent / OpenAPI migrated | Runtime evaluate returns an `EvaluateResult` envelope, accept is rejected as removed, OpenAPI no longer exposes CandidateSet round-trips, and agent evaluation consumes rows without candidate cache state. |
| 2026-05-25 | feat-b | `63718d09` | Final active docs migration | Active SDK, service, and official docs were moved to final T5 Rule / EvaluateResult / explanation language. Historical/reference docs and dirty notebooks were preserved. |
| 2026-05-25 | feat-c | `62279515` | Legacy SDK shells hard-cut | `fg.eval` legacy methods and `fg.what_if` were removed from public namespace; direct legacy shells reject with T5 guidance; DSL Rule is internal-only; hard-cut tests were added. |
| 2026-05-25 | implemented | pending | T5.7 closure recorded | G7, focused SDK, service/agent, ruff, and diff-check gates passed. Blueprint and audit moved to implemented. |

## 2. Source Chain

T5.7 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D18 return-shape transition: `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition-strategy.md`
- D20 explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope-evidencegraph-integration.md`
- D22 why-not disposition: `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
- D23 legacy SDK hard-cut plan: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- D24 final SDK Rule flip: `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- T5.3 archive: `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`
- T5.4 archive: `workflow/blueprints/archive/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.md`
- T5.5 archive: `workflow/blueprints/archive/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.md`
- T5.6 archive: `workflow/blueprints/archive/2026-05-25_t5-6-final-sdk-rule-flip.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md` | T5.7 slice | Confirms L-class default and acceptance anchors. |
| `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md` | sections 4.1-4.8 | Defines hard-cut targets, service inventory, and docs timing. |
| `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md` | scope + outcome | Confirms service/OpenAPI/docs deferred from SDK-only evaluate flip. |
| `workflow/blueprints/archive/2026-05-25_t5-6-final-sdk-rule-flip.md` | scope + outcome | Confirms final SDK `Rule` naming is available for docs migration. |
| `src/service/runtime_v1.py` | evaluate / accept runtime derivation routes | Confirms CandidateSet serialization and accept cache remain service-facing. |
| `src/service/app_v1.py` | route registration | Confirms evaluate and accept routes are still registered. |
| `docs/api/openapi.yaml` | `/runtime/inferences/evaluate` and `/runtime/inferences/accept` | Confirms public OpenAPI still documents CandidateSet and accept handshake. |
| `src/factgraph/sdk/store.py` | eval, accept, direct check/diagnose/why_not, what_if managers | Confirms legacy shell targets remain after T5.6. |
| `src/factgraph/sdk/docs/*.en.md`, `docs/official`, `examples`, `tests` | broad grep snapshot | Confirms docs/tests still contain CandidateSet, accept, what-if, and legacy naming references. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| Service evaluate | `src/service/runtime_v1.py` calls `session.store.evaluate(...)`, caches CandidateSets, and serializes `candidates`. |
| Service accept | `src/service/runtime_v1.py` accepts a serialized candidate and calls `session.store.accept(...)`. |
| OpenAPI | `docs/api/openapi.yaml` describes CandidateSet v2 output and an accept handshake. |
| SDK hard-cut | `src/factgraph/sdk/store.py` still contains accept/accept_many, direct check/diagnose/why_not, and what-if managers. |
| Why-not | T5.5 quarantine markers exist, but shipped why-not DTO/runtime/shell code still exists. |
| DSL Rule | T5.6 removed top-level `LegacyRule`, but `.sdk.dsl.Rule` remains. |
| Docs/examples | CandidateSet, accept, check, diagnose, why-not, what-if, `ApplicationRule`, and legacy DSL examples remain broad. |
| Adapter guard | No T5.7 owner for `src/factgraph/adapters/` or C73-C78. |

## 5. Scope Mapping

| Stage 3 / D-doc item | T5.7 draft treatment |
|---|---|
| D23 hard-cut target inventory | In scope; Step 4.6 must classify before scoped. |
| D23 service route migration | In scope; evaluate route and accept route must align with T5 EvaluateResult model. |
| D23 OpenAPI/docs migration | In scope after T5.6 final Rule naming. |
| D18 no public CandidateSet compatibility | In scope as a negative gate. |
| D22 no public why-not API | In scope as a negative gate; final disposition of legacy why-not code decided here. |
| D24 final SDK `Rule` naming | In scope for docs/examples and legacy DSL cleanup. |
| T5.1-T5.6 contracts | Preserved; T5.7 must not alter DTO/evaluate/explain/close/Rule contracts. |
| D26 adapter/Semantics Lite | Out of scope. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.7 scope and split rules | Satisfied; L-class default. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft docs only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 171 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before scoped and record actual results.

| # | Check | Command shape | Expected / classification |
|---|---|---|---|
| 1 | Service routes | `rg "inferences/evaluate|inferences/accept|CandidateSet|candidate|accept_runtime_derivation|evaluate_runtime_derivation" src/service` | Expected broad hits; classify T5.7 service update or route removal/redesign. |
| 2 | OpenAPI and service docs | `rg "CandidateSet|accept|inferences/evaluate|inferences/accept|EvaluateResult" docs/api src/service docs` | Expected broad hits; T5.7 OpenAPI/docs update. |
| 3 | SDK legacy shells | `rg "def accept|accept_many|def check|def diagnose|def why_not|what_if|_SDKWhatIf|eval\\.run|eval\\.accept" src/factgraph/sdk tests` | Expected hits; classify removal/rejection/internal preservation. |
| 4 | Public CandidateSet exposure | `rg "CandidateSet|candidate_id|support_digest|return_candidates|result_shape|evaluate_v2|evaluate_candidates" src tests docs examples` | CandidateSet internal hits expected; public teaching/route hits T5.7 update. |
| 5 | Docs/examples/notebooks | `rg "CandidateSet|accept_many|accept\\(|check\\(|diagnose\\(|why_not|what_if|ApplicationRule|LegacyRule" src/factgraph/sdk/docs docs/official examples tests` | Broad hits expected; classify rewrite/archive/historical exception. |
| 6 | Why-not final disposition | `rg "WhyNotUniverse|WhyNotRedRow|WhyNotRowDiagnostic|WhyNotAtomLocator|WhyNotStatus|check_why_not_universe|sdk_why_not|why_not" src tests` | Expected legacy quarantine hits; decide internal preserve/delete. |
| 7 | Legacy DSL Rule final disposition | `rg "factgraph\\.sdk\\.dsl|from factgraph\\.sdk\\.dsl import Rule|dsl\\.Rule|LegacyRule|ApplicationRule|Inference" src tests docs examples` | Expected legacy tests/docs; decide final public cleanup. |
| 8 | T5.1-T5.6 contract guard | `rg "EvaluateResult|EvaluateRow|Explanation|row\\.explain|row\\.close|fg\\.eval\\.explain|Rule.content_digest|semantics_digest" src/factgraph tests` | Existing substrate expected; no contract changes. |
| 9 | Adapter / Semantics Lite guard | `rg "src/factgraph/adapters|SemanticsProfile|C73|C74|C75|C76|C77|C78|iteration_count|temporal" src tests workflow` | Existing references only; no adapter edits. |
| 10 | Compatibility surface guard | `rg "evaluate_v2|why_not_v2|result_shape|return_candidates|as_candidates|EvaluateResult\\.why_not|Explanation\\.why_not|counterfactual" src tests docs examples` | Should be absent except design references; no new compat surface. |

Step 4.6 must also decide:

- one L-class implementation or T5.7a/T5.7b/T5.7c split;
- service accept removal versus redesign;
- why-not DTO delete versus internal preserve;
- legacy DSL Rule delete versus internal preserve;
- any future-track deferral for `what_if.fact_overlay.*` or `what_if.rule.*`.

## 8. Step 4.6 Pre-Implementation Grep Results

| # | Check | Result | Classification |
|---|---|---|---|
| 1 | Service routes | `src/service/runtime_v1.py` still imports `CandidateSet`, serializes `candidates`, caches CandidateSet payloads, implements `_candidate_to_dict` / `_candidate_from_dict`, and supports evaluate plus accept routes. `src/service/app_v1.py` still registers both inference routes. | T5.7a service/OpenAPI update. |
| 2 | OpenAPI and service docs | `docs/api/openapi.yaml` still describes `/inferences/evaluate` as CandidateSet output and `/inferences/accept` as the accept handshake. Service docs still mention runtime evaluate/accept policy. | T5.7a update, with T5.7b docs follow-through. |
| 3 | SDK legacy shells | `src/factgraph/sdk/store.py` still owns `_SDKEvalManager.accept`, `_SDKEvalManager.accept_many`, direct `check`, `diagnose`, `why_not`, `_SDKWhatIfManager`, `_SDKWhatIfFactOverlayManager`, and `_SDKWhatIfRuleManager`. Tests still assert these managers exist. | T5.7c hard-cut/delete/reject decision. |
| 4 | Public CandidateSet exposure | CandidateSet public assumptions remain across service, OpenAPI, agent tools, docs, examples, and tests; internal runtime tests also legitimately use CandidateSet. | Public hits T5.7a/T5.7b; private runtime hits preserved. |
| 5 | Docs/examples/notebooks | SDK docs, official quickstarts, examples, and notebooks still teach CandidateSet, accept, run, check/diagnose/why-not, what-if, `ApplicationRule`, or legacy DSL Rule. | T5.7b migration; dirty notebook baseline must be preserved and edited carefully. |
| 6 | Why-not final disposition | WhyNot protocol/runtime/shells and tests remain broad. T5.5 quarantine is present; SDK does not re-export WhyNot DTOs, but tests still validate the old runtime and shell. | T5.7c decide internal preserve vs deletion. |
| 7 | Legacy DSL Rule final disposition | `factgraph.sdk.dsl.Rule` is still used by legacy helper tests and DSL bridge tests. Docs still contain `ApplicationRule` and `LegacyRule` references. | T5.7c final disposition; T5.7b docs cleanup. |
| 8 | T5.1-T5.6 contract guard | `EvaluateResult`, `EvaluateRow`, `Explanation`, `row.explain`, `row.close`, manual explain, digests, and final SDK `Rule` substrate are present and not owned by T5.7. | Preserve; no contract changes. |
| 9 | Adapter / Semantics Lite guard | Adapter and semantics references are unrelated substrate or design references. No T5.7 implementation owner. | Clean guard; no adapter edits. |
| 10 | Compatibility surface guard | No production `evaluate_v2`, `result_shape`, `return_candidates`, `EvaluateResult.why_not`, or `Explanation.why_not` owner found. Remaining `counterfactual` references are docs/legacy what-if language. | No new compatibility surface; docs cleanup in T5.7b. |

Split decision:

- T5.7 remains one L-class blueprint and one archive unit.
- Implement as three adjacent M-class local sub-slices:
  - T5.7a: service routes, agent/runtime candidate workflow alignment, and OpenAPI.
  - T5.7b: final SDK/service/official docs, examples, and notebook migration.
  - T5.7c: legacy SDK shell deletion/rejection, legacy DSL Rule final disposition, and why-not final disposition.
- No sub-slice is push-ready by default; the full T5.7 closure must record SDK/service/OpenAPI/docs agreement.
- Service accept final path is removal or rejection unless T5.7a review explicitly accepts a redesign that does not expose CandidateSet.
- Why-not DTOs and legacy DSL Rule default to internal preserve if deletion breaks private tests; final public exposure remains forbidden.
- `what_if.fact_overlay.*` and `what_if.rule.*` stay T5.7c hard-cut targets unless T5.7c records an explicit future-track deferral.

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

Expected result: 171 tests OK, inherited from T5.6 archive.

| Field | Value |
|---|---|
| Branch | `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` |
| Sacred state | `master = 562c74195df43e933bed92a3ff25de94dd8ce666` |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | `272a57f4` |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | 171 tests in 0.100s, OK |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 10. Draft Review Checklist

| Item | Status |
|---|---|
| D23 hard-cut targets represented | Yes |
| Service/OpenAPI migration represented | Yes |
| Final docs migration represented | Yes |
| D18 CandidateSet compat ban represented | Yes |
| D22 why-not replacement ban represented | Yes |
| D24 final Rule naming represented | Yes |
| T5.1-T5.6 contracts protected | Yes |
| C73-C78 / adapter work excluded | Yes |
| Step 4.6 split decision required | Yes |
| Step 4.6 grep results clean | Yes |
| Split policy recorded | Yes |

## 11. Reviewer Focus

- Is T5.7 scope broad enough to close D23 without accidentally adding new public compatibility?
- Are split rules strict enough to prevent incoherent public milestones?
- Is service/OpenAPI/docs migration tied to the same public target shape?
- Are legacy DTO deletion/internal-preserve decisions deferred only to Step 4.6, not implementation guesswork?
- Are dirty notebooks and existing dirty files protected from unrelated overwrite?

## 12. Outcome

### Commit References

- `41f7e60f` — service, agent runtime, and OpenAPI migration.
- `63718d09` — final active docs / examples migration.
- `62279515` — legacy SDK shell hard-cut and hard-cut tests.

### Closure Notes

- Service evaluate now returns a T5 `EvaluateResult` representation and the
  accept route rejects the removed CandidateSet echo workflow.
- Active docs no longer teach CandidateSet, accept, check, diagnose, why-not,
  what-if, or `fg.eval.run(...)` as public T5 evidence paths except as explicit
  removed/internal notes.
- SDK hard-cut behavior is explicit: public legacy shells reject with
  `SDKStoreError` guidance to `fg.eval.evaluate(...)`, `row.explain()`,
  `row.close()`, or manual `fg.eval.explain(...)`.
- Why-not protocol/runtime/shell code remains internal/quarantined; no public
  why-not replacement or lossy conversion path was added.
- Legacy DSL Rule is preserved as an internal import path but removed from
  public `factgraph.sdk.dsl.__all__`.

### Verification

- G7 preservation: `PYTHONPATH=src python -m unittest ... -v` ran 171 tests in
  0.113s, OK.
- Focused SDK hard-cut / namespace / quarantine suite:
  `tests.test_sdk_redesign_namespace_shape`, `tests.test_sdk_redesign_alias_parity`,
  `tests.sdk.test_t5_legacy_hard_cut`, and
  `tests.sdk.test_t5_why_not_quarantine` ran 37 tests in 0.071s, OK.
- Focused service/agent suite:
  `src.service.tests.test_problog_candidate_evidence_tree` and
  `src.agent.tests.test_agent_layer2_runtime_api` ran 8 tests in 0.011s, OK.
- Touched-file ruff passed.
- `git diff --check` passed.

### Residual / Deferred

- C73-C78 Semantics Lite remains optional T5.8 / post-T5 work.
- Historical/reference docs and pre-existing dirty notebooks retain legacy
  mentions outside the active T5 public-docs scope.
- Private legacy helper code can be physically deleted in a future cleanup if
  all non-G7 tests are migrated; T5.7 only hard-cuts the public surface.
