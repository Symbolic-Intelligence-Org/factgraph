# Audit: T5.2 Public Evaluate Return-Shape Flip

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- Stage: T5.2 implementation blueprint draft
- Class: L (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | pending | Blueprint pair drafted | T5.2 public evaluate return-shape flip draft created after T5.1 archive `53781419`. Scope is L-class default and requires D18/D23 blast-radius inventory before scoped. |

## 2. Source Chain

T5.2 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D17 result/row DTO foundation: `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
- D18 return-shape transition: `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
- D19 digest source-of-truth: `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
- D20 explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
- D21 row.close / closed-head gate: `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
- D22 why-not disposition: `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
- D23 legacy hard-cut plan: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- D24 final SDK Rule flip: `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
- D25 evaluate/explain semantics consistency: `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
- D26 semantics adapter policy: `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `src/factgraph/sdk/store.py` | `evaluate(...)`, `_evaluate_compiled_derivation_plans(...)`, `_evaluate_rule_expr_input(...)` | Main public SDK evaluate dispatcher and existing CandidateSet return shape. |
| `src/factgraph/application/derivation_runtime.py` | `evaluate_derivation_plans(...)`, `_evaluate_plan(...)` | Application runtime currently flattens raw `list[CandidateSet]`. |
| `src/service/runtime_v1.py` | runtime inference evaluate / accept routes | Service route still serializes CandidateSet and accept handshake. |
| `docs/api/openapi.yaml` | runtime evaluate endpoint docs | OpenAPI still documents CandidateSet output. |
| `src/factgraph/application/protocol/evaluate_result.py` | T5.1 DTO and digest helpers | Substrate for result envelope and digest population. |
| `tests/sdk/test_rule_expr_evaluate.py` | public RuleExpr evaluate tests | G7 suite currently asserts CandidateSet return shape. |
| SDK docs and official docs | CandidateSet, accept, `engine_options` references | D18/D23 blast radius and docs migration pressure. |

## 4. Pre-Draft Grep Snapshot

This draft ran a broad pre-draft grep to orient scope. A precise Step 4.6 grep will be recorded in the scoped commit.

| Area | Snapshot |
|---|---|
| Public SDK evaluate | `SDKStore.evaluate(...)` still returns `list[CandidateSet]`; `registry` and `engine_options` are popped and forwarded into internal paths. |
| Application runtime | `evaluate_derivation_plans(...)` returns `list[CandidateSet]`; existing comments explicitly say no application-side wrapping. |
| RuleExpr evaluate | Public RuleExpr path still calls `evaluate_derivation_plans(...)` and returns CandidateSet. |
| Legacy inference / dict evaluate | Both compile through `_evaluate_compiled_derivation_plans(...)` and return CandidateSet. |
| Service route | Runtime route `/v1/runtime/sessions/{session_id}/inferences/evaluate` serializes candidates and pairs with `/inferences/accept`. |
| OpenAPI | `docs/api/openapi.yaml` says "Evaluate an inference and return a CandidateSet." |
| Docs/examples/tests | Many CandidateSet / `engine_options` / `accept` assumptions exist across SDK docs, official docs, examples, and tests. |
| Agent layer | `src/agent/tools/evaluate.py` has an unrelated agent-layer `EvaluateResult`; namespace collision remains isolated. |

## 5. Scope Mapping

| Stage 3 item | T5.2 draft treatment |
|---|---|
| D18 public hard-cut | In scope: public evaluate returns `EvaluateResult`; no parallel shape. |
| D18 all paths together | In scope: RuleExpr, application Rule, legacy Inference, structured dict, fallback path decision. |
| D18 param removal | In scope: reject public `engine_options=` and `registry=`. |
| D17/T5.1 DTOs | Consumed; field contracts unchanged. |
| D19 digests | In scope: populate all result/row/context digests. |
| T5.1 view snapshot follow-up | In scope: decide real in-memory view digest source or raise. |
| D20/D21 row methods | Out of scope except private live resolver remains available. |
| D22 why-not | Out of scope; no public why-not surface. |
| D23 service hard-cut | Inventory required; full hard-cut deferred unless blueprint amended. |
| D24 Rule flip | Out of scope. |
| D26 semantics adapter work | Out of scope. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit public hard-cut scope | Satisfied; L-class default. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 163 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before implementation and record actual results in a scoped commit.

| # | Check | Command shape | Expected / classification |
|---|---|---|
| 1 | SDK evaluate return shape | `rg "def evaluate|_evaluate_compiled_derivation_plans|_evaluate_rule_expr_input|list\\[CandidateSet\\]" src/factgraph/sdk src/factgraph/application tests` | Identify all T5.2 public return-shape update sites and internal CandidateSet preservation sites. |
| 2 | CandidateSet public assumptions | `rg "CandidateSet|candidate_id|candidate_key|support_digest|confidence_kind|accept\\(" tests src/factgraph/sdk docs examples` | Classify as T5.2 update, T5.7 deferred, internal preservation, or unrelated. |
| 3 | Public param cleanup | `rg "engine_options|registry=" src/factgraph tests docs examples` | Public evaluate kwargs must be rejected; internal registry/plan options may remain. |
| 4 | Service route blast radius | `rg "inferences/evaluate|inferences/accept|CandidateSet|candidate_id|engine_options|registry" src/service docs/api src/agent tests docs examples` | Mandatory D23 inventory; decide service-aligned scope vs deferral. |
| 5 | DTO/digest helper use | `rg "EvaluateResult|EvaluateRow|result_id_for|view_snapshot_digest|semantics_digest_for|_candidate_set_to_evaluate_row" src tests` | Ensure T5.1 helper path is reused and no duplicate formula appears. |
| 6 | Row methods / Explanation gate | `rg "row\\.explain|row\\.close|Explanation|EvidenceGraph|checked_scope|failure_class" src/factgraph tests` | Existing/future surfaces only; T5.2 must not implement T5.3/T5.4. |
| 7 | SDK Rule naming gate | `rg "LegacyRule|ApplicationRule|from \\.dsl import.*Rule|Rule =" src/factgraph/sdk tests/sdk` | T5.2 must not perform D24 final flip. |
| 8 | Adapter / semantics gate | `rg "problog|pyreason|souffle|SemanticsProfile|ProbLogSemantics|PyReasonSemantics|adapter" src/factgraph tests` | Existing adapter code only; no adapter production edit target. |
| 9 | Direct store fallback | `rg "_store\\.evaluate|store\\.evaluate\\(" src/factgraph/sdk src/service tests` | Decide whether public fallback wraps, rejects, or remains internal. |
| 10 | Docs/OpenAPI final migration pressure | `rg "list\\[CandidateSet\\]|CandidateSet|accept_many|evaluate\\(.*engine_options|return a CandidateSet" docs docs/api examples src/service/docs` | Classify minimal T5.2 updates vs T5.7 deferred final migration. |

If Step 4.6 shows service route or docs blast radius is larger than T5.2 can safely absorb, amend this blueprint before scoped.

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

Expected result: 163 tests OK, inherited from T5.1 archive.

Baseline record fields to fill later:

| Field | Value |
|---|---|
| Branch | pending |
| Sacred state | pending |
| Dirty baseline | pending |
| Scoped anchor | pending |
| Command | pending |
| Result | pending |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 9. Draft Review Checklist

| Item | Status |
|---|---|
| D18 hard-cut represented | Yes |
| D17/T5.1 DTO substrate consumed without field changes | Yes |
| D19 digest population represented | Yes |
| T5.1 view snapshot follow-up carried forward | Yes |
| D23 service blast-radius inventory required | Yes |
| D20/D21 row methods excluded | Yes |
| D24 Rule flip excluded | Yes |
| D26 adapter semantics excluded | Yes |
| CandidateSet compatibility flags rejected | Yes |
| Step 4.6 grep plan present | Yes |
| G7 baseline plan present | Yes |

## 10. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| T5.2 may be too large as one L slice | Decide whether blueprint should pre-split before scoped. |
| Service route/OpenAPI blast radius may force scope amendment | Check D23 inventory requirements and T5.7 deferral boundary. |
| In-memory `view_snapshot_digest` source may be under-specified | Ensure T5.2 has a no-placeholder implementation path. |
| Direct store fallback may be ambiguous | Reviewer should decide whether public fallback wraps or rejects. |
| CandidateSet internal tests may need preservation | Confirm internal runtime helpers are allowed to keep CandidateSet. |
| `engine_options=` / `registry=` rejection may break many tests | Ensure this is intended D18/D23 hard-cut behavior. |

## 11. Outcome

Pending.
