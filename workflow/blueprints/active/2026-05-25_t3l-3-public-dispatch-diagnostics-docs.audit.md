# Audit Log: T3L.3 Public SDK Dispatch, Diagnostics, And Docs

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Blueprint: [2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md](./2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | draft | T3L.3 blueprint pair created | Scope consumes Stage 3 synthesis T3L.3 row, D6/D9/D10, T3L.1/T3L.2 archived substrate, and shipped SDK dispatch/docs evidence. |

## Decision Notes

### Source Chain

1. Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`.
2. Stage 2 decisions:
   - D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
   - D9 `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
   - D10 `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
3. Stage 3 synthesis `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`.
4. Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T3L.3 row.
5. Archived implementation slices:
   - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`

### Shipped Source Read Before Draft

Read before drafting:

- `src/factgraph/sdk/store.py`
- `src/factgraph/application/protocol/rule_expr_lowering.py`
- `src/factgraph/application/protocol/rule_expr.py`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/00_user_guide.en.md`
- `src/factgraph/sdk/docs/01_concepts.en.md`
- `src/factgraph/application/docs/rule.md`
- `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
- `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`

### Draft Scope Decision

T3L.3 is the final T3 later implementation slice. It should make the private T3L.1/T3L.2 execution substrate reachable from the public SDK and document that behavior, without expanding T4/T5 surfaces.

Rationale:

- D6 intentionally delayed public exposure until lowering and adapter matrix were stable.
- T3L.1 and T3L.2 now provide the private materialization and classifier substrate.
- D10 rejects a public result wrapper in this tranche, so the public path can remain `list[CandidateSet]`.
- T3.6 docs already teach RuleExpr authoring; T3L.3 only needs to add execution-specific behavior.

### External-Head Risk

T3L.1 and T3L.2 explicitly deferred external-head body concatenation. T3L.3 must not accidentally smuggle in full T4 Head behavior. The draft records two bounded options:

1. reject external-head body concatenation publicly with `SDKStoreError` guidance to include the head as an expression occurrence; or
2. implement narrowly bounded concatenation if Step 4.6 and implementation prove it is local and does not require T4 semantics.

Reviewer should verify this boundary before scoped status.

## G1-G7 Visible Mapping

| Gate | Evidence |
|---|---|
| G1 canonical source citation | Blueprint §1 and §4 cite Stage 3 synthesis, D6/D9/D10, T3L.1/T3L.2 archives, and shipped SDK/docs line ranges. |
| G2 shipped source read before drafting | This audit lists source files read; blueprint §4 records current SDK dispatch, private lowering substrate, and docs ranges. |
| G3 file:line precision | Blueprint §4 cites exact line ranges for `SDKStore.evaluate(...)`, `_SDKEvalManager.evaluate(...)`, `rule_expr_lowering.py`, and docs surfaces. |
| G4 goal-to-driver mapping | Blueprint §2 maps public dispatch, head requirement, diagnostics, result shape, trace, and docs to D6/D9/D10 and synthesis drivers. |
| G5 deviations / class triggers | Blueprint §1 M-to-L triggers, §3 non-goals, and §5.9 preemptive locks define escalation. |
| G6 reviewer spot-check | Reviewer should independently verify SDK dispatch lines, `rule_expr_lowering.py` helper lines, and docs ranges. |
| G7 pre-impl baseline | Blueprint §7 and this audit G7 plan require 121 OK baseline before feature code. |

## Class Trigger Analysis

Predicted class: M.

M-class reasons:

- touches public SDK dispatch;
- adds public diagnostics behavior;
- updates user-facing docs;
- relies on multiple private substrate slices.

Not L-class because:

- Stage 1 audit and D6-D10 decisions are complete;
- T3L.1/T3L.2 implementation substrate is complete;
- public result and T4/T5 boundaries are locked;
- this slice has one final public exposure target.

Escalate to L-class or pause for a reviewed amendment if implementation needs public result DTOs, T4 Head semantics, adapter grammar upgrades, or public trace/evidence surfaces.

## Cross-Slice Contract Preservation

| Contract | Preservation requirement |
|---|---|
| T1.3 staged naming | `factgraph.sdk.Rule` remains legacy; `ApplicationRule` / application protocol `Rule` are accepted for RuleExpr head. |
| T1.4 alias / port contract | explicit occurrence aliases and port refs remain unchanged. |
| T3.1 bool guards | no bool semantics change for RuleExpr values. |
| T3.3/T3.4 joins | explicit `.eq(...)` / `.join_by_ports(...)`; no same-name auto-join. |
| T3.5 inspect | `fg.rules.inspect(...)` return shapes remain unchanged. |
| T3.6 docs | execution docs extend authoring docs without rewriting staged import guidance. |
| T3L.1 native substrate | `_materialize_native_derivation_plan(...)` behavior remains compatible. |
| T3L.2 adapter parity | Souffle / ProbLog materialization and PyReason classifier are consumed, not reopened. |
| D6 head boundary | required application Rule `head=`; full T4 Head remains out. |
| D9 matrix | public rejection uses SDKStoreError and four message fields. |
| D10 result boundary | public success remains `list[CandidateSet]`; trace stays private. |

## Step 4.6 Pre-Implementation Grep Plan

Run before feature implementation:

| Check | Command | Expected use |
|---|---|---|
| 1. Existing RuleExpr public dispatch | `rg 'RuleExpr|_RuleExpr|_lower_rule_expr|_materialize_adapter_derivation_plan|RuleExprAdapterSupport' src/factgraph/sdk src/factgraph/application tests` | Find existing private/public touch points and prevent duplicate dispatch helpers. |
| 2. SDK evaluate dispatch paths | `rg 'def evaluate\\(|_SDKEvalManager|to_authoring_payload|_evaluate_compiled_derivation_plans|_resolve_public_engine_and_semantics' src/factgraph/sdk/store.py tests/sdk` | Verify insertion point and legacy path tests. |
| 3. Head and ApplicationRule usage | `rg 'ApplicationRule|build_application_rule|head=|RuleExprInspect|legacy SDK Rule|Inference' src/factgraph tests workflow/blueprints/archive/2026-05-25_t3l-*.md` | Confirm accepted/rejected public head shapes and docs wording. |
| 4. SDKStoreError diagnostics | `rg 'SDKStoreError|unsupported_feature|rejection_source|alternative_engines|pyreason' src/factgraph tests` | Locate current error message style and T3L.2 classifier data. |
| 5. Public result/evidence boundaries | `rg 'CandidateSet|RuleExprEvaluateResult|EvaluateResult|EvidenceEnvelope|branch_atom_projection|payload' src/factgraph tests` | Confirm no public result/evidence shape expansion. |
| 6. Docs update surface | `rg 'RuleExpr|evaluate\\(|head=|pyreason|CandidateSet|same-name|bool guards' src/factgraph/sdk/docs src/factgraph/application/docs` | Lock docs files and avoid stale/contradictory execution guidance. |

If any grep result contradicts the blueprint scope, pause for an A-fallback amendment.

## G7 Baseline Plan

Run before implementation:

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
  -v
```

Expected draft baseline: 121 OK.

Pytest remains deferred per existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded because failures are pre-existing and unrelated to RuleExpr lowering.

## Step 4.2 Draft Review Checklist

Reviewer should verify:

1. Blueprint status is `draft`.
2. T3L.3 is explicitly final T3 later slice.
3. D6 public entrypoint and head requirements are accurately reflected.
4. Legacy SDK `Inference` / derivation dict paths are protected.
5. D9 public error message contract is testable.
6. D10 public result boundary is preserved.
7. T3L.1/T3L.2 private substrate is consumed without export.
8. External-head behavior is bounded before implementation.
9. PyReason remains pred-only and classifier-driven.
10. Docs scope extends T3.6 content without T5/T4 promises.
11. Step 4.6 grep plan covers dispatch, head, diagnostics, result shape, and docs.
12. G7 baseline uses the post-T3L.2 121 OK gate.
13. Sacred / dirty invariants are not touched.

## G7 Baseline Record

Pending.

## Closure Notes

Pending.
