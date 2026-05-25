# Audit: T5.3 Explanation Envelope + Live Row Resolver

- Status: implemented
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
| 2026-05-25 | scoped | pending | Step 4.6 grep clean | Ten grep buckets completed. No shipped public `Explanation` or `row.explain()` production owner found; `EvidenceGraph`, Check/Diagnose, WhyNot, renderer, service, docs, and adapter hits are existing substrates or future-slice territory. Scope remains M-class. |
| 2026-05-25 | baseline | pending | G7 baseline recorded | Scoped anchor `c5e5c28b`; G7 command ran 166 tests in 0.085s, OK. Pytest remains deferred per existing SIGSEGV environment lock; `tests.test_public_inference_factgraph_create` remains outside the G7 command. |
| 2026-05-25 | feat | `53551cb6` | T5.3 live row explanations implemented | Added `Explanation`, live `EvaluateRow.explain()`, minimal row-sourced `EvidenceGraph`, checked-scope/metadata copying, and SDK/protocol re-exports. Gates: 35 focused OK, G7 166 OK, ruff clean, diff check clean. |
| 2026-05-25 | implemented | pending | Closure recorded | Blueprint and audit moved to implemented after Step 4.7 review reported 0 P0 / 0 P1 and no fix commit required. Future-slice boundaries for T5.4-T5.8 remain deferred. |

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

## 8. Step 4.6 Pre-Implementation Grep Results

| # | Check | Result | Scope decision |
|---|---|---|---|
| 1 | Explanation namespace | Hits are T5 design docs, synthesis, T5.3 blueprint pair, and historical references. No `src/factgraph` production T5 public `Explanation` DTO exists. | Clean. T5.3 owns the first public application-protocol `Explanation` implementation. |
| 2 | Row explain/close methods | No production `EvaluateRow.explain()` or `row.explain()` owner exists. `row.close` and manual explain hits are design docs, T5.3/T5.4 planning, or test data around closed-head digest helpers. | Clean. T5.3 owns only no-arg `EvaluateRow.explain()`; `row.close()` and manual explain remain T5.4. |
| 3 | EvidenceGraph consumers | `EvidenceGraph` is implemented in `src/factgraph/audit/evidence_graph.py`; existing consumers include service/static UI, audit readers, adapter provenance converters, and audit tests. | Expected substrate. T5.3 reuses graph type and must not promote renderer or engine_meta key contracts. |
| 4 | ErrorDTO / WarningDTO patterns | `ErrorDTO` / `WarningDTO` are defined in `application/protocol/common.py` and used broadly by Check/Diagnose/WhyNot/query/entity/rule action DTOs. | Expected. T5.3 should follow existing tuple validation/export patterns. |
| 5 | Check/Diagnose/WhyNot substrate | Existing Check/Diagnose/WhyNot protocol, runtime, shell, and test surfaces are broad. Why-not DTOs and atom locators remain independently tested. | Expected legacy/private substrate. T5.3 must not embed Diagnose/WhyNot DTOs in public Explanation or remove old shells. |
| 6 | T5.4 / manual explain guard | `fg.eval.explain`, manual explain, `closed_head`, and `row.close` hits are design docs, T5.4 planning, T5.1/T5.2 closed-head digest helpers, and T4.3 closed-head inspect code. No production manual explain entrypoint exists. | Clean guard. T5.3 must not implement manual explain or `row.close()`. |
| 7 | SDK exports and Rule gate | SDK namespace still has pre-D24 `Rule`, `LegacyRule`, and `ApplicationRule`; tests assert that behavior. No SDK `Explanation` export exists yet. | Add `Explanation` only; do not perform D24 final Rule flip. |
| 8 | Service/docs/renderer guard | Service docs/OpenAPI/runtime evaluate, static UI rendering, audit render helpers, and why-not tests have existing hits. | T5.7 / renderer-future territory. T5.3 does not migrate service/docs or add `Explanation.render()`. |
| 9 | Adapter / semantics guard | ProbLog/PyReason/Souffle provenance, semantics profiles, and raw_kind/bound carrier tests/docs have broad existing hits. | Existing substrate only. T5.3 copies row carriers and result semantics digest; no adapter production edits. |
| 10 | T5.2 evaluate preservation | `EvaluateResult` and `_candidate_sets_to_evaluate_result` are present from T5.1/T5.2. Agent-layer `EvaluateResult` is unrelated. SDK docs still contain deferred CandidateSet teaching from T5.7 scope. | T5.2 public evaluate hard-cut is baseline. T5.3 must preserve it and avoid broad docs/service migration. |

Step 4.6 scope decision: T5.3 remains one M-class slice. No A-fallback amendment is required. Existing EvidenceGraph adapter/service/rendering hits are substrate or future-slice scope, not implementation collisions.

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

Expected result: 166 tests OK, inherited from T5.2 archive.

Baseline record:

| Field | Value |
|---|---|
| Branch | `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` |
| Sacred state | `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666` |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | `c5e5c28b` |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | `Ran 166 tests in 0.085s`, `OK` |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 10. Draft Review Checklist

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
| Step 4.6 grep results clean | Yes |

## 11. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| Minimal EvidenceGraph may be too shallow | Decide whether T5.3 should allow a one-node passed graph or split richer evidence topology into a later slice. |
| Row explain may drift into manual replay | Confirm no kwargs and no `fg.eval.explain(...)` in T5.3. |
| Failed/unsupported/invalid states may overreach | Confirm T5.3 needs only enough envelope validation; why-not fold remains T5.5. |
| Graph metadata may become accidental public schema | Confirm D20 audit-facing metadata boundary is preserved. |
| Renderer helpers may become public | Confirm no `Explanation.render()` or SDK HTML helper. |
| Check/Diagnose may leak public DTOs into Explanation | Confirm they remain private substrate only. |
| Adapter semantics may leak through raw_kind/bound | Confirm carriers are copied from rows and no adapter edits occur. |

## 12. Outcome

### Final Code Scope

T5.3 touched only the scoped protocol / SDK export / focused test files:

- `src/factgraph/application/protocol/evaluate_result.py`
  - public `Explanation` DTO;
  - `EvaluateRow.explain()`;
  - private row explanation helper;
  - checked-scope and graph metadata copy helpers;
  - minimal row-sourced `EvidenceGraph` builder.
- `src/factgraph/application/protocol/__init__.py`
  - application protocol `Explanation` export.
- `src/factgraph/sdk/__init__.py`
  - SDK `Explanation` re-export.
- `tests/application/protocol/test_evaluate_result_dtos.py`
  - DTO, live row explain, detached row, failure, unsupported graph, checked-scope, metadata, and carrier tests.
- `tests/sdk/test_evaluate_result_exports.py`
  - SDK export coverage.
- `tests/sdk/test_rule_expr_evaluate.py`
  - public evaluate hard-cut test updated to expect live row `explain()`.

No service, OpenAPI, docs migration, adapter, renderer, public why-not, manual explain, row.close, or final SDK Rule files were touched.

### Verification

| Gate | Result |
|---|---|
| G7 baseline | `Ran 166 tests in 0.085s`, OK at scoped baseline `946d1e4d`. |
| G7 preservation after feat | `Ran 166 tests in 0.082s`, OK after `53551cb6`. |
| Focused T5.3/T5.2 suite | `35 OK`. |
| Touched-file ruff | Clean. |
| Diff check | `git diff --check` clean. |
| Pytest policy | Deferred per existing SIGSEGV environment lock. |
| Excluded public inference test | `tests.test_public_inference_factgraph_create` remains outside G7 command. |

### Scope Preservation

- `row.close()` remains absent; T5.4 owns it.
- Manual `fg.eval.explain(expr, head=closed_head, ...)` remains absent; T5.4 owns it.
- Public `.eval.why_not(...)` remains absent; D22/T5.5 owns why-not fold decisions.
- No renderer API or `Explanation.render()` was added.
- No new SDK-specific graph DTO was introduced; T5.3 reuses shipped `EvidenceGraph`.
- Engine-specific `engine_meta` key contracts remain audit-facing and non-public.
- T5.2 public `evaluate(...) -> EvaluateResult` behavior remains unchanged.
- SDK `Rule`, `LegacyRule`, and `ApplicationRule` namespace remains pre-D24; T5.6 owns final flip.
- Service routes, OpenAPI, agents, docs, and legacy shell hard-cut remain T5.7.
- Adapter production files and semantics-lite commitments remain T5.8 / post-T5.

### Step 4.7 Disposition

Claude review found 0 P0 / 0 P1 and no Step 4.7 fix commit was required.

Reviewed implementation highlights:

- D20 fields and status/evidence matrix implemented.
- Live row explanation path added without kwargs or alternate semantics.
- Detached row behavior remains `DetachedRowError`.
- D25 checked-scope five-key subset copied for row-sourced explanations.
- Minimal valid `EvidenceGraph` returned for passed explanations.
- Graph validation failure maps to `unsupported` with `GRAPH_VALIDATION_FAILED`.

### Deferred

- T5.4: `row.close()` and manual `fg.eval.explain(expr, head=closed_head, ...)`.
- T5.5: why-not fold and legacy evidence shell quarantine.
- T5.6: final SDK `Rule` flip.
- T5.7: legacy hard-cut, service/OpenAPI/docs migration, and old shell removal.
- T5.8 / post-T5: semantics-lite and adapter-touching C73-C78 work.
