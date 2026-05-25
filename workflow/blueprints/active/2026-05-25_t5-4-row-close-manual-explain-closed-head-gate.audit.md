# Audit: T5.4 Row Close + Manual Explain Closed-Head Gate

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.md`
- Stage: T5.4 implementation blueprint scoped
- Class: M (predicted; split if Step 4.6 shows broader runtime/service scope)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | `f755749b` | Blueprint pair drafted | T5.4 Row Close + Manual Explain Closed-Head Gate draft created after T5.3 archive `ba5e5c26`. Scope is M-class predicted, but Step 4.6 must decide whether row-close and manual explain stay one slice or split. |
| 2026-05-25 | scoped | pending | Step 4.6 grep clean | Ten grep buckets matched expected shipped/design hits. No A-fallback triggered; T5.4 remains a single SDK/protocol-scoped M-class slice. Service/docs, why-not, SDK Rule flip, and adapter semantics remain future-slice territory. |

## 2. Source Chain

T5.4 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D17 result/row DTO foundation: `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
- D19 digest source-of-truth: `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
- D20 explanation envelope: `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
- D21 row-close / closed-head gate: `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
- D25 evaluate/explain semantics consistency: `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
- D26 semantics adapter policy: `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- T4 D15 closed-head inspect: `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- T5.3 archive: `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `src/factgraph/application/protocol/evaluate_result.py` | `EvaluateRow`, `Explanation`, live resolver | T5.4 adds `EvaluateRow.close()` next to existing live-only `explain()`. |
| `src/factgraph/sdk/store.py` | `_SDKEvalManager`, `SDKStore.evaluate`, `_candidate_sets_to_evaluate_result` | Manual `fg.eval.explain(...)` belongs in eval namespace and should reuse evaluate/result substrate. |
| `src/factgraph/application/protocol/rule_expr_inspect.py` | `_inspect_closed_head`, D15 value/entity closure helpers | T5.4 should reuse closed-head validation substrate without public export. |
| `src/factgraph/application/protocol/rule.py` | `Rule`, `PortType`, `_is_projection_rule`, projection placeholders | Row-close construction must preserve Rule invariants and strip projection placeholders. |
| `src/factgraph/application/protocol/schema_runtime.py` | `EntityRef`, `IdentityFieldInfo`, `EntityTypeInfo`, identity predicates | Entity-ref close construction requires primary identity metadata. |
| `tests/sdk/test_rule_expr_evaluate.py` | T5.2 public evaluate expectations | T5.4 must preserve EvaluateResult return-shape and existing row explain. |
| `tests/application/protocol/test_rule_expr_head_validation.py` | projection tests | Projection placeholder behavior must remain validation-only. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| `row.close` / `EvaluateRow.close` | Design docs and future-slice mentions only; no production method exists. |
| Manual `fg.eval.explain` | Design docs only; `_SDKEvalManager` currently exposes `evaluate`, `run`, and semantics helpers, not `explain`. |
| Closed-head helper | T4.3 helper is private in `rule_expr_inspect.py`; no public closed-head DTO exists. |
| Projection markers | `_is_projection_rule` and placeholder constants exist in `rule.py`; T5.4 can detect and strip projection placeholders. |
| Entity-ref identity metadata | `SchemaIndex.entities[entity_type].identity_predicates[field_name].pred_id` exists through schema runtime. |
| T5.3 row explain | `EvaluateRow.explain()` exists and must remain no-arg. |
| Service/docs/adapter | Broad existing hits remain future-slice territory; T5.4 should stay SDK/protocol scoped. |

## 5. Scope Mapping

| Stage 3 item | T5.4 draft treatment |
|---|---|
| D21 `row.close()` | In scope. |
| D21 D15 closure construction | In scope. |
| D21 projection placeholder stripping | In scope. |
| D21 manual explain closed-head gate | In scope. |
| D20 manual explain output shape | In scope through `Explanation`. |
| D25 standalone manual semantics | In scope. |
| D25 row-anchored mismatch | Guarded; row-anchored replay not added unless amended. |
| D22 why-not | Out of scope. |
| D23 service/docs hard-cut | Out of scope. |
| D24 SDK Rule flip | Out of scope. |
| D26 adapter semantics | Out of scope. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.4 row-close/manual-explain scope | Satisfied; M-class predicted with split trigger. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; scoped docs only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 166 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Results

Ran before implementation and recorded actual results in this scoped commit.

| # | Check | Command shape | Expected / classification |
|---|---|---|
| 1 | Row-close namespace | `rg "row\\.close|EvaluateRow\\.close|def close\\(" src tests workflow` | No production `EvaluateRow.close`; existing docs/future notes expected. |
| 2 | Manual explain namespace | `rg "fg\\.eval\\.explain|eval\\.explain|def explain\\(" src/factgraph/sdk src/factgraph/application tests workflow` | T5.3 row `explain()` exists; SDK eval manual explain should be absent. |
| 3 | Closed-head helper substrate | `rg "_inspect_closed_head|_ClosedHeadInspect|is_closed|unbound_ports" src/factgraph/application/protocol tests` | T4.3 private helper and tests expected; no public DTO/export changes. |
| 4 | Projection placeholder guard | `rg "__factgraph_projection|_is_projection_rule|Rule\\.projection" src tests` | Existing D14/T4.2 substrate; T5.4 should strip placeholders in row.close. |
| 5 | Entity-ref identity metadata | `rg "identity_predicates|identity_fields|IdentityFieldInfo|EntityRef|entity_type_from_ref" src/factgraph/application src/factgraph/sdk tests` | Existing schema substrate; no schema API redesign expected. |
| 6 | D15 forbidden closure forms | `rg "InAtom|BuiltinAtom|NotAtom|AggregateAtom|transitive|Var == Var|head-port link" src tests workflow` | Existing docs/tests; T5.4 must not broaden closure inference. |
| 7 | D19 closed_head_digest consumers | `rg "closed_head_digest|closed_head_digest_for" src tests workflow` | T5.1/T5.2/T5.3 digest substrate and design docs expected. |
| 8 | Service/docs/agent guard | `rg "eval\\.explain|row\\.close|why_not|OpenAPI|inferences/evaluate|inferences/accept" docs docs/api src/service src/agent tests` | Existing future-slice/service/docs hits should remain deferred. |
| 9 | SDK Rule namespace guard | `rg "LegacyRule|ApplicationRule|from factgraph\\.sdk import Rule|Rule =" src/factgraph/sdk tests/sdk` | Pre-D24 namespace must remain unchanged. |
| 10 | Adapter / semantics guard | `rg "problog|pyreason|souffle|SemanticsProfile|raw_kind|bound|adapter" src/factgraph tests` | Existing substrate only; no adapter edits. |

Actual classification:

| # | Result |
|---|---|
| 1 | Clean. No production `EvaluateRow.close`; hits are design docs, active T5.4 draft, and unrelated `close()` methods in service/agent/ledger classes. |
| 2 | Clean. Production has only T5.3 `EvaluateRow.explain()` in `evaluate_result.py`; SDK eval manual `explain(...)` is absent. |
| 3 | Expected. T4.3 private helpers and inspect tests exist; no public closed-head DTO/export exists. |
| 4 | Expected. D14/T4.2 projection constants, recognizer, lowering/inspect tests, and docs exist; T5.4 owns stripping placeholders from row-close output. |
| 5 | Expected. SchemaIndex, EntityRef, identity field/predicate metadata, and SDK normalization helpers are present; no schema API redesign needed. |
| 6 | Expected. Core atom classes/tests and D15/D21 docs exist; T5.4 must keep strict v1 closure and not broaden inference. |
| 7 | Expected. T5.1 digest helpers, T5.2 consumers, T5.3 tests, and D21/docs exist; T5.4 can reuse `closed_head_digest_for(...)`. |
| 8 | Clean guard. Hits are service/OpenAPI routes, legacy why-not/docs/tests, T5.4 draft text, and static UI render helpers. Service/docs/agent migration stays T5.7; why-not stays T5.5; renderer remains out of scope. |
| 9 | Expected. Pre-D24 SDK namespace remains in `sdk/__init__.py`, docs, and tests. T5.4 must not alter `Rule` / `LegacyRule` / `ApplicationRule`. |
| 10 | Expected broad substrate hits in adapter/runtime/semantics/tests. No T5.4 adapter production edit target found. |

Scope decision: keep T5.4 as one SDK/protocol-scoped M-class slice. Manual explain does not require service/OpenAPI work before implementation; service/docs remain T5.7 deferred.

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

Expected result: 166 tests OK, inherited from T5.3 archive.

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
| D21 row.close represented | Yes |
| D21 D15 closure construction represented | Yes |
| D21 projection placeholder stripping represented | Yes |
| D21 manual explain closed-head gate represented | Yes |
| D20 Explanation output represented | Yes |
| D25 standalone semantics represented | Yes |
| D15 strict closure preserved | Yes |
| D22 why-not excluded | Yes |
| D23 service/docs hard-cut excluded | Yes |
| D24 SDK Rule flip excluded | Yes |
| D26 adapter semantics excluded | Yes |
| Step 4.6 grep plan present | Yes |
| Step 4.6 grep results clean | Yes |
| G7 baseline plan present | Yes |

## 10. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| Manual explain might be too much for one M slice | Decide whether row-close and manual explain should split before scoped. |
| Entity-ref binding normalization may be underspecified | Confirm accepted binding shapes are sufficient or narrow them before implementation. |
| Projection closed heads may accidentally retain placeholders | Confirm explicit placeholder-strip tests are required. |
| Closed-head validation may need private helper export | Confirm private import/adapter is acceptable without public API change. |
| Standalone manual explain may overpromise replay fidelity | Confirm manual path can use current evaluate substrate and status matrix without new evidence runtime. |
| D25 row-anchored mismatch complexity may leak in | Confirm row-anchored manual replay is not in scope unless amended. |
| Service/docs migration may leak early | Confirm T5.7 remains owner. |

## 11. Outcome

Pending.
