# Audit: T5.3 Explanation Envelope + Live Row Resolver

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`
- Stage: T5.3 implementation blueprint draft
- Class: M (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | pending | Blueprint pair drafted | T5.3 Explanation Envelope + Live Row Resolver draft created after T5.2 archive `4e590e8a`. Scope is M-class predicted and excludes row.close/manual explain, public why-not, renderer, service/docs migration, adapter work, and final SDK Rule flip. |

## 2. Source Chain

T5.3 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D17 result/row DTO foundation: `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
- D19 digest source-of-truth: `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
- D20 explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
- D21 row.close / closed-head gate: `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
- D22 why-not disposition: `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
- D23 legacy hard-cut plan: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- D25 evaluate/explain semantics consistency: `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
- D26 semantics adapter policy: `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `src/factgraph/application/protocol/evaluate_result.py` | `EvaluateRow`, `EvaluateResult`, digest helpers | T5.3 extends the live row resolver and adds the public Explanation DTO. |
| `src/factgraph/application/protocol/common.py` | `ErrorDTO`, `WarningDTO` | D20 Explanation uses existing error/warning DTOs. |
| `src/factgraph/audit/evidence_graph.py` | `EvidenceGraph`, `EvidenceNode`, `EvidenceEdge`, serialization/render helpers | D20 requires reuse of shipped EvidenceGraph and validation gate. |
| `src/factgraph/application/protocol/derivation_check.py` | `CheckResult`, `EvidenceEnvelope` | D20 allows Check as private substrate only. |
| `src/factgraph/application/protocol/derivation_diagnose.py` | `DiagnoseResult`, atom locators | D20 forbids embedding Diagnose as failed Explanation payload. |
| `src/factgraph/application/protocol/__init__.py` | protocol export pattern | T5.3 should re-export Explanation like T5.1 DTOs. |
| `src/factgraph/sdk/__init__.py` | SDK export pattern | T5.3 should re-export Explanation without D24 Rule flip. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| `Explanation` name | Existing hits are D20/D25/synthesis docs and old Check/Diagnose concepts; no T5 public DTO implementation exists. |
| Row live resolver | `EvaluateRow._require_live_result()` exists from T5.1/T5.2, but there is no public `row.explain()` method. |
| EvidenceGraph | Shipped audit graph has validation and rendering helpers; T5.3 should reuse graph type but not promote renderer. |
| Error/warning DTOs | `ErrorDTO` / `WarningDTO` already exist and are exported from application protocol. |
| Check/Diagnose | Protocol/runtime/test surfaces exist and remain legacy/private substrate for T5.3. |
| `row.close` / manual explain | Design docs only; no production owner yet. T5.3 must not implement them. |
| why-not | Existing protocol/runtime/shell surfaces remain D22/T5.5/T5.7 territory. |
| SDK exports | T5.1/T5.2 DTOs are exported; Explanation can follow that pattern without touching SDK Rule names. |

## 5. Scope Mapping

| Stage 3 item | T5.3 draft treatment |
|---|---|
| D20 Explanation DTO | In scope. |
| D20 live row explain | In scope. |
| D20 EvidenceGraph reuse | In scope; shipped graph type only. |
| D20 graph validation gate | In scope. |
| D20 manual explain | Out of scope; T5.4. |
| D21 row.close | Out of scope; T5.4. |
| D22 why-not | Out of scope; no public why-not. |
| D25 row-sourced semantics | In scope through checked_scope and row semantics reuse. |
| D26 adapter semantics | Out of scope. |
| T5.7 hard-cut/docs | Out of scope. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.3 row-explain scope | Satisfied; M-class predicted. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 166 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before implementation and record actual results in a scoped commit.

| # | Check | Command shape | Expected / classification |
|---|---|---|
| 1 | Explanation namespace | `rg "Explanation|class Explanation|Explanation\\(" src tests workflow` | Docs only plus new T5.3 target; no shipped public DTO owner. |
| 2 | Row explain/close methods | `rg "row\\.explain|\\.explain\\(|row\\.close|\\.close\\(" src/factgraph tests` | Existing unrelated methods/docs possible; T5.3 only owns no-arg `EvaluateRow.explain()`, not close/manual explain. |
| 3 | EvidenceGraph consumers | `rg "EvidenceGraph|EvidenceNode|EvidenceEdge|render_evidence_graph|evidence_graph_to_dict" src tests` | Existing audit helpers and tests; T5.3 should reuse graph type and avoid renderer product API. |
| 4 | ErrorDTO / WarningDTO patterns | `rg "ErrorDTO|WarningDTO|errors: tuple|warnings: tuple" src/factgraph/application/protocol tests` | Existing protocol validation patterns to follow. |
| 5 | Check/Diagnose/WhyNot substrate | `rg "CheckResult|DiagnoseResult|WhyNot|DiagnoseAtomLocator|EvidenceEnvelope" src/factgraph tests` | Existing legacy/private substrate; no public embedding in Explanation. |
| 6 | T5.4 / manual explain guard | `rg "fg\\.eval\\.explain|eval\\.explain|manual explain|closed_head|row\\.close" src tests workflow` | Design docs only or future owner; T5.3 must not implement manual explain/close. |
| 7 | SDK exports and Rule gate | `rg "Explanation|LegacyRule|ApplicationRule|Rule =" src/factgraph/sdk src/factgraph/application/protocol tests/sdk` | Add Explanation export only; no D24 Rule flip. |
| 8 | Service/docs/renderer guard | `rg "Explanation\\.render|render_evidence_graph|EvidenceGraph|why_not|OpenAPI|inferences/evaluate" docs docs/api src/service src/agent tests` | Existing service/docs/agent surfaces remain T5.7 or renderer future; no T5.3 migration. |
| 9 | Adapter / semantics guard | `rg "problog|pyreason|souffle|SemanticsProfile|raw_kind|bound|semantics_digest" src/factgraph tests` | Existing carrier/digest substrate; no adapter production edits. |
| 10 | T5.2 evaluate preservation | `rg "EvaluateResult|fg\\.eval\\.evaluate|tests\\.sdk\\.test_rule_expr_evaluate|_candidate_sets_to_evaluate_result" src tests` | Ensure row resolver source remains T5.2 and public evaluate stays stable. |

If Step 4.6 shows `EvidenceGraph` construction requires internal evidence schema redesign or adapter work, amend or split before scoped.

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

Expected result: 166 tests OK, inherited from T5.2 archive.

Baseline fields to fill after scoped:

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
| D20 Explanation fields represented | Yes |
| D20 status/evidence matrix represented | Yes |
| D20 EvidenceGraph reuse represented | Yes |
| D20 graph validation gate represented | Yes |
| D25 checked_scope subset represented | Yes |
| T5.4 row.close/manual explain excluded | Yes |
| D22 public why-not excluded | Yes |
| Renderer product API excluded | Yes |
| Adapter semantics excluded | Yes |
| D24 SDK Rule flip excluded | Yes |
| Step 4.6 grep plan present | Yes |
| G7 baseline plan present | Yes |

## 10. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| Minimal EvidenceGraph may be too shallow | Decide whether T5.3 should allow a one-node passed graph or split richer evidence topology into a later slice. |
| Row explain may drift into manual replay | Confirm no kwargs and no `fg.eval.explain(...)` in T5.3. |
| Failed/unsupported/invalid states may overreach | Confirm T5.3 needs only enough envelope validation; why-not fold remains T5.5. |
| Graph metadata may become accidental public schema | Confirm D20 audit-facing metadata boundary is preserved. |
| Renderer helpers may become public | Confirm no `Explanation.render()` or SDK HTML helper. |
| Check/Diagnose may leak public DTOs into Explanation | Confirm they remain private substrate only. |
| Adapter semantics may leak through raw_kind/bound | Confirm carriers are copied from rows and no adapter edits occur. |

## 11. Outcome

Pending.
