# Audit: T5.6 Final SDK Rule Flip

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-25_t5-6-final-sdk-rule-flip.md`
- Stage: T5.6 implementation scoped
- Class: M (predicted; escalate to L if service/agent/docs imports require broad migration)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-25 | draft | `4f4fc8d4` | Blueprint pair drafted | T5.6 Final SDK Rule Flip draft created after T5.5 archive `ec45f12f`. Scope is predicted M-class: flip SDK top-level `Rule` to application protocol `Rule`, keep `ApplicationRule` as transition alias, remove top-level `LegacyRule`, and defer broad D23 hard-cut/docs migration to T5.7. |
| 2026-05-25 | scoped | pending | Step 4.6 grep clean | Grep found expected SDK namespace/test blast radius, `.dsl.Rule` preservation paths, and broad docs/examples deferred to T5.7. T5.6 remains one SDK-focused M-class namespace flip with no split before scoped. |

## 2. Source Chain

T5.6 consumes:

- Stage 1 audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D24 final SDK Rule flip: `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
- D23 legacy hard-cut plan: `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- T5.3 archive: `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`
- T5.4 archive: `workflow/blueprints/archive/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.md`
- T5.5 archive: `workflow/blueprints/archive/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md` | sections 4.1-4.8 | Defines final naming contract and ordering with D23. |
| `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md` | T5.6 slice section | Confirms predicted M-class and acceptance anchors. |
| `src/factgraph/sdk/__init__.py` | import block and `__all__` | Confirms current four-way namespace: `Rule`, `LegacyRule`, `ApplicationRule`, `Inference`. |
| `tests/sdk/test_rule_naming.py` | current assertions | Confirms tests still encode pre-D24 top-level legacy `Rule`. |
| `src/factgraph/sdk/dsl/rule.py` | legacy DSL `Rule` / `Inference` | Confirms T5.6 should not delete DSL classes. |
| `src/factgraph/application/protocol/rule.py` | application protocol `Rule` | Confirms final SDK `Rule` target class. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| SDK namespace | `src/factgraph/sdk/__init__.py` imports `.dsl.Rule` as top-level `Rule`, `.dsl.Rule` as `LegacyRule`, and protocol `Rule` as `ApplicationRule`. |
| Naming tests | `tests/sdk/test_rule_naming.py` asserts `sdk.Rule is dsl.Rule` and top-level legacy construction works. |
| Runtime use | T5 evaluate tests already reject legacy SDK Rule objects as application `head=` values. |
| D23 boundary | Broad docs/service/hard-cut migration remains future T5.7. |

## 5. Scope Mapping

| Stage 3 / D-doc item | T5.6 draft treatment |
|---|---|
| D24 top-level `Rule` = application protocol Rule | In scope through SDK import flip and identity tests. |
| D24 `ApplicationRule` transition alias | In scope; alias survives as `ApplicationRule is Rule`. |
| D24 top-level `LegacyRule` not final public alias | In scope as top-level export/attribute removal only. |
| D24 legacy DSL `Rule` stops owning top-level name | In scope; `.dsl.Rule` remains module-local until T5.7. |
| D24 `Inference` remains named | In scope as preservation test. |
| D23 hard-cut mechanics | Out of scope; T5.7 owns deletion and broad migration. |
| T5.1-T5.5 contracts | Preserved and tested. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.6 naming scope | Satisfied; M-class predicted with service/docs L trigger. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft docs only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 170 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before scoped and record actual results.

| # | Check | Command shape | Expected / classification |
|---|---|---|
| 1 | SDK namespace exports | `rg "Rule|LegacyRule|ApplicationRule|Inference|__all__" src/factgraph/sdk/__init__.py tests/sdk/test_rule_naming.py` | Current pre-D24 namespace expected; T5.6 owns. |
| 2 | Top-level legacy consumers | `rg "sdk\\.Rule|from factgraph\\.sdk import Rule|LegacyRule|ApplicationRule" src tests docs examples workflow` | Tests/docs expected; service/agent hits may trigger L or T5.7 deferral. |
| 3 | DSL module preservation | `rg "factgraph\\.sdk\\.dsl|dsl\\.Rule|from \\.dsl import|from factgraph\\.sdk\\.dsl import" src tests` | Existing legacy module use expected; T5.6 must not delete `.dsl.Rule`. |
| 4 | Runtime type checks | `rg "isinstance\\(.*Rule|head= must be application Rule|application Rule|ApplicationRule" src/factgraph tests` | May need narrow message updates; no runtime behavior change. |
| 5 | T5.1-T5.5 guard | `rg "EvaluateResult|EvaluateRow|Explanation|why_not|row\\.close|row\\.explain" src/factgraph/sdk src/factgraph/application tests/sdk` | Existing substrate expected; T5.6 should not edit behavior. |
| 6 | Service/docs/OpenAPI guard | `rg "LegacyRule|ApplicationRule|from factgraph\\.sdk import Rule|sdk\\.Rule|fg\\.eval\\.run|CandidateSet" src/service src/agent docs docs/api examples` | Broad hits expected; classify as T5.7 unless implementation needs them. |
| 7 | Adapter / semantics guard | `rg "SemanticsProfile|raw_kind|bound|src/factgraph/adapters" src tests workflow` | Existing substrate only; no T5.6 owner. |
| 8 | New-name alternatives guard | `rg "HeadRule|EvalRule|DerivationRule|LegacyInference" src tests workflow` | Should be absent except historical/design references. |

## 8. Step 4.6 Pre-Implementation Grep Results

| # | Check | Result | Classification |
|---|---|---|---|
| 1 | SDK namespace exports | `src/factgraph/sdk/__init__.py` still binds top-level `Rule` to `.dsl.Rule`, exposes `LegacyRule`, and exposes `ApplicationRule`; `tests/sdk/test_rule_naming.py` and `tests/sdk/test_evaluate_result_exports.py` assert that pre-D24 state. | T5.6 hard-cut update. |
| 2 | Top-level legacy consumers | SDK/protocol tests use `from factgraph.sdk import Rule` for legacy construction and need focused updates. Docs/examples contain broad historical/teaching uses. No production service route requires a T5.6 rename. | Focused tests in T5.6; broad docs/examples deferred to T5.7. |
| 3 | DSL module preservation | `factgraph.sdk.dsl.Rule`, `Inference`, `build_application_rule(...)`, and `DSLToApplicationRuleError` have active tests and runtime support. | Internal/transition preservation; no deletion in T5.6. |
| 4 | Runtime type checks and messages | `src/factgraph/sdk/store.py` already imports application protocol `Rule` for evaluate/explain checks under a local `ApplicationRule` alias. Local wording may still say `ApplicationRule`. | Narrow naming cleanup allowed; runtime behavior unchanged. |
| 5 | T5.1-T5.5 guard | `EvaluateResult`, `EvaluateRow`, `Explanation`, `row.explain`, `row.close`, and why-not quarantine surfaces are already implemented and have no T5.6 behavior owner. | Preservation tests only. |
| 6 | Service/docs/OpenAPI guard | Broad docs and SDK docs mention `ApplicationRule`, `LegacyRule`, `CandidateSet`, or legacy surfaces. `src/service` and OpenAPI hard-cut remain D23/T5.7 territory. | T5.7 deferred. |
| 7 | Adapter / semantics guard | SemanticsProfile/raw_kind/bound/adapters are existing substrate and do not need edits for SDK Rule naming. | No T5.6 owner. |
| 8 | New-name alternatives guard | `HeadRule`, `EvalRule`, `DerivationRule`, and `LegacyInference` appear only in design/blueprint references, not production owners. | Clean; no alternative public class introduced. |

Scope decision:

- T5.6 remains M-class.
- No T5.6a/T5.6b split is needed before scoped.
- Feature work is limited to SDK top-level namespace flip, focused import/naming tests, and narrow runtime naming cleanup if required.
- T5.7 owns broad service/docs/OpenAPI/examples migration and legacy hard-cut deletion.

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

Expected result: 170 tests OK, inherited from T5.5 archive.

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

## 10. Draft Review Checklist

| Item | Status |
|---|---|
| D24 top-level Rule flip represented | Yes |
| D24 ApplicationRule transition alias represented | Yes |
| D24 LegacyRule top-level removal represented | Yes |
| D24 Inference preservation represented | Yes |
| D23 deletion/migration excluded | Yes |
| Service/OpenAPI/docs migration excluded | Yes |
| T5.1-T5.5 behavior changes excluded | Yes |
| Adapter semantics excluded | Yes |
| Step 4.6 grep plan present | Yes |
| Step 4.6 grep results clean | Yes |
| G7 baseline plan present | Yes |

## 11. Risks For Reviewer

| Risk | Reviewer focus |
|---|---|
| T5.6 may accidentally become T5.7 hard-cut | Confirm only top-level naming changes and tests are in scope. |
| Legacy DSL class deletion leaks in | Confirm `.dsl.Rule` remains until T5.7. |
| ApplicationRule alias removed too early | Confirm transition alias survives. |
| Service/docs migration pressure leaks in | Confirm broad migration remains T5.7. |
| Import identity change breaks hidden tests | Confirm Step 4.6 finds broad consumers before feat. |

## 12. Outcome

Pending.
