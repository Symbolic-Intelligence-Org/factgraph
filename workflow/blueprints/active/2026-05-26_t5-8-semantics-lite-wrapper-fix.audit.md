# Audit: T5.8 Semantics Lite + Wrapper-Application Rule Path Fix

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Blueprint: `workflow/blueprints/active/2026-05-26_t5-8-semantics-lite-wrapper-fix.md`
- Stage: T5.8 draft
- Class: M (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | pending | Blueprint pair drafted | T5.8 Semantics Lite + Wrapper-Application Rule Path Fix draft created after user elevated Semantics Lite from optional to mandatory due to SDK public wrapper gap. Scope is predicted M-class and must stay wrapper/profile-only with no adapter production edits. |

## 2. Source Chain

T5.8 consumes:

- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
- D17 Result / Row DTO Foundation: `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
- D19 Digest Source of Truth: `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
- D25 Evaluate / Explain Semantics Consistency: `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
- D26 Semantics Commitments Scope and Adapter Policy: `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- T5.1 archive: `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.md`
- T5.2 archive: `workflow/blueprints/archive/2026-05-25_t5-2-public-evaluate-return-shape-flip.md`
- T5.3 archive: `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md`
- T5.4 archive: `workflow/blueprints/archive/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.md`
- T5.5 archive: `workflow/blueprints/archive/2026-05-25_t5-5-why-not-fold-legacy-evidence-quarantine.md`
- T5.6 archive: `workflow/blueprints/archive/2026-05-25_t5-6-final-sdk-rule-flip.md`
- T5.7 archive: `workflow/blueprints/archive/2026-05-25_t5-7-legacy-hard-cut-service-docs-migration.md`

## 3. Pre-Draft Shipped Source Reads

| Source | Lines / area | Reason |
|---|---|---|
| `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md` | sections 4.2-4.10 | Defines Semantics Lite eligibility and adapter-touching deferral. |
| `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md` | sections 4.1 and 4.8 | Confirms digest-content comparison and that D26 implementation must not change D25 policy. |
| `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md` | T5.8 optional slice | Confirms M-class optional Semantics Lite lane and stop trigger for adapter edits. |
| `src/factgraph/sdk/semantics.py` | wrapper dataclasses | Confirms wrappers are currently documented and shaped around inference evaluation. |
| `src/factgraph/sdk/store.py` | `_resolve_public_engine_and_semantics`, `_evaluate_rule_expr_input`, `_lower_public_semantics` | Confirms current resolver gap and lowering assumptions. |
| `src/factgraph/application/protocol/rule_expr_lowering.py` | branch id assignment | Confirms RuleExpr lowering has branch ids suitable for wrapper branch-key mapping. |
| `docs/official/kernel/quickstart/semantics.md` | semantics tutorial | Confirms current tutorial is inference-centered and needs narrow update. |

## 4. Pre-Draft Grep Snapshot

| Area | Snapshot |
|---|---|
| Public wrapper guard | `src/factgraph/sdk/store.py:2142-2144` rejects SDK public wrappers unless the supplied derivation has `.where`. |
| RuleExpr evaluate caller | `_evaluate_rule_expr_input(...)` passes `derivation=None` into `_resolve_public_engine_and_semantics(...)`, blocking wrapper + application `Rule` / `RuleExpr`. |
| Wrapper lowering | `_lower_public_semantics(...)` calls `_branch_id_index_for_derivation(derivation)` and assumes a legacy inference-like `.where` object. |
| Wrapper preview | `_preview_public_semantics(...)` can construct profile previews without derivation, but feature evaluate path uses lower, not preview. |
| Wrapper docs | `ProbLogSemantics` and `PyReasonSemantics` docstrings say to pass wrappers to `fg.eval.evaluate(inference, semantics=...)`. |
| RuleExpr branch substrate | RuleExpr lowering assigns branch ids such as `b0`, `b1`, and exposes compiled branch metadata. |
| Docs | `docs/official/kernel/quickstart/semantics.md` teaches wrappers through `Inference` examples. |
| Adapter guard | No T5.8 owner for adapter production files; D26 defers adapter-touching work. |

## 5. Scope Mapping

| Stage 3 / D-doc item | T5.8 draft treatment |
|---|---|
| D26 section 4.2 Semantics Lite lane | In scope as mandatory because a shipped public wrapper/application-rule gap was found. |
| D26 section 4.3 C73 | Wrapper-level `rule_params` shape, validation, and `SemanticsProfile.rule_projection` lowering are in scope; adapter consumption out of scope. |
| D26 section 4.5 C75 | Wrapper symmetry and carrier-model documentation are in scope; adapter math out of scope. |
| D25 section 4.1 | Normalized `semantics_digest` remains the comparison source. |
| D25 section 4.8 | D25 mismatch policy remains fixed across T5.8 outcomes. |
| D17 / D19 carriers and digests | `raw_kind` / `bound` carrier-only and digest formula contracts preserved. |
| User-found store.py guard | Primary implementation fix. |
| Adapter-touching C74/C76/C77/C78 | Out of scope; stop-and-amend if needed. |

## 6. G1-G7 Mapping

| Gate | Description | Draft status |
|---|---|---|
| G1 | Uses reviewed-clean T5 design inputs | Satisfied. |
| G2 | Has explicit T5.8 scope and stop triggers | Satisfied. |
| G3 | Has negative-action gates | Satisfied in blueprint section 0. |
| G4 | Includes shipped-source preflight | Satisfied in audit sections 3-4. |
| G5 | Defines tests and preservation gates | Satisfied in blueprint sections 4 and 6. |
| G6 | Preserves sacred branch and dirty baseline | Satisfied; draft docs only. |
| G7 | Establishes baseline before feat | Pending after scoped; expected 171 tests OK. |

## 7. Step 4.6 Pre-Implementation Grep Plan

Run before scoped and record actual results.

| # | Check | Command shape | Expected / classification |
|---|---|---|---|
| 1 | Public wrapper classes | `rg "class ProbLogSemantics|class PyReasonSemantics|rule_params|branch_probabilities|branch_bounds" src/factgraph/sdk` | Expected wrapper definitions in `sdk/semantics.py`; T5.8 update. |
| 2 | Resolver guard | `rg "_resolve_public_engine_and_semantics|derivation is None|not hasattr\\(derivation, \\\"where\\\"\\)" src/factgraph/sdk/store.py` | Expected shipped gap; T5.8 fix. |
| 3 | RuleExpr evaluate path | `rg "def _evaluate_rule_expr_input|derivation=None|_lower_rule_expr|_lower_application_rule" src/factgraph/sdk/store.py` | Expected caller passes no derivation; T5.8 fix. |
| 4 | Wrapper lowering assumptions | `rg "_lower_public_semantics|_branch_id_index_for_derivation|_inspect_where_branches|_default_semantics_name" src/factgraph/sdk/store.py` | Expected inference-shaped lowering; extend carefully. |
| 5 | RuleExpr branch ids | `rg "branch_id|_assign_branch_ids|RuleExprLoweringBranch" src/factgraph/application/protocol/rule_expr_lowering.py` | Expected branch-id substrate; reuse only. |
| 6 | SemanticsProfile digest consumers | `rg "semantics_digest_for|semantics_digest|SemanticsProfile" src/factgraph/application src/factgraph/sdk tests` | Existing substrate expected; no D25 policy changes. |
| 7 | Existing semantics tests | `rg "ProbLogSemantics|PyReasonSemantics|SemanticsProfile|branch_probabilities|branch_bounds" tests` | Expected focused tests to update/add. |
| 8 | Docs/docstrings | `rg "fg\\.eval\\.evaluate\\(inference|Inference.*semantics|ProbLogSemantics|PyReasonSemantics" docs/official/kernel/quickstart src/factgraph/sdk/docs src/factgraph/sdk/semantics.py` | Expected inference-centered docs; narrow update. |
| 9 | Adapter guard | `rg "ProbLogSemantics|PyReasonSemantics|rule_projection|branch_probabilities|branch_bounds" src/factgraph/adapters src/factgraph/core` | Existing adapter/core references only; no adapter edits. |
| 10 | Compatibility guard | `rg "evaluate_v2|result_shape|return_candidates|why_not_v2|Explanation\\.why_not|EvaluateResult\\.why_not" src tests docs` | Should be absent or historical; no new compat surface. |

Step 4.6 must also decide:

- whether T5.8 stays one M-class slice;
- exact single-application-rule branch-specific config policy;
- whether `rule_params` shape can remain wrapper-local without new DTOs;
- which docs are touched narrowly.

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

Expected result: 171 tests OK, inherited from T5.7 archive and post-T5 docs-only cleanup commits.

| Field | Value |
|---|---|
| Branch | `v0.2.0-t5-result-evidence-explain-audit-2026-05-25` |
| Sacred state | `master = 562c74195df43e933bed92a3ff25de94dd8ce666` |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | pending |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | pending |
| Pytest policy | deferred per existing SIGSEGV environment lock |
| Exclusion | `tests.test_public_inference_factgraph_create` remains outside G7 command |

## 9. Draft Review Checklist

- [ ] Step 4.2 reviewer confirms T5.8 is mandatory because of the wrapper/application-rule gap.
- [ ] Scope locks include wrapper-application Rule path, C73 wrapper-only params, C75 wrapper symmetry, and narrow docs.
- [ ] Out-of-scope section excludes adapter edits, service/OpenAPI edits, new DTOs, and D25 policy changes.
- [ ] Six-matrix test list is explicit.
- [ ] M-to-L triggers are explicit.
- [ ] Pre-implementation grep plan covers resolver, lowering, RuleExpr branch ids, docs, and adapters.

## 10. Closure Notes

Pending.
