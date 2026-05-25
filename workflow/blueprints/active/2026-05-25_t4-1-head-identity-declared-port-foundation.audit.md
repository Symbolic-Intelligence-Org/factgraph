# Audit Log: T4.1 Head Identity + Declared-Port Foundation

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Blueprint: [2026-05-25_t4-1-head-identity-declared-port-foundation.md](./2026-05-25_t4-1-head-identity-declared-port-foundation.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | draft | T4.1 blueprint pair created | Scope consumes T4 Stage 3 synthesis T4.1 row, D11/D12 reviewed decisions, T3L.1-T3L.3 archived substrate, and shipped RuleExpr lowering / SDK dispatch evidence. |
| 2026-05-25 | draft-amend | Step 4.2 v1 precision amendments | Added an explicit upper-bound scope lock for private occurrence-version metadata, specified T4.1 validation ordering before the existing T3L.3 external-head rejection, and cross-referenced D11/D12 multi-occurrence ambiguity for identity state 5. |

## Decision Notes

### Source Chain

1. Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`.
2. Stage 2 decisions:
   - D11 `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
   - D12 `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
   - D13 `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md`
   - D14 `workflow/design/decisions/active/2026-05-25_t4-d14-rule-projection-sugar.md`
   - D15 `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
3. Stage 3 synthesis `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md`.
4. Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T4.1 row.
5. Archived implementation slices:
   - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`

### Shipped Source Read Before Draft

Read before drafting:

- `src/factgraph/application/protocol/rule.py`
- `src/factgraph/application/protocol/rule_expr.py`
- `src/factgraph/application/protocol/rule_expr_lowering.py`
- `src/factgraph/application/protocol/rule_expr_inspect.py`
- `src/factgraph/sdk/store.py`
- `tests/application/protocol/test_rule_expr_lowering.py`
- `tests/application/protocol/test_rule_expr_lowering_adapter.py`
- `tests/sdk/test_rule_expr_evaluate.py`
- `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`
- `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md`
- D11-D15 decision docs.

### Draft Scope Decision

T4.1 is the first implementation slice of the T4 Head + closed-head tranche. It builds only the shared D11/D12 foundation:

- existing-head id/digest validation and version warning;
- private branch-total declared-port helper;
- head port namespace / `PortType` validation;
- same-name ambiguity rejection unless explicit join materialization proves equivalence.

Rationale:

- T3L.3 public dispatch exists, so T4.1 can integrate foundation validation without re-opening SDK dispatch architecture.
- D13/D14/D15 are intentionally downstream and should consume the foundation after it is reviewed.
- Keeping external-head body concatenation and projection out of T4.1 reduces blast radius and keeps Step 4.7 review focused.

### Error Bucket Decision

T4.1 preserves D11/D6 buckets:

- public call-shape errors remain `SDKStoreError`;
- semantic head/expression validation errors use `RuleExprError`;
- version mismatch is `UserWarning`;
- Rule DTO construction remains `RuleValidationError`.

The main T4.1 behavior change from T3L.3 is that same-id/different-digest heads must no longer fall through to the public external-head `SDKStoreError`; they are D11 stale identity semantic failures and should raise `RuleExprError`.

### D13-D15 Deferral

T4.1 must leave these behaviors untouched:

- T3L.3 external-head rejection remains until T4.2.
- `Rule.projection(...)` does not exist until T4.2.
- closed-head inspect fields do not exist until T4.3.
- T5 evidence/result surfaces remain deferred.

## G1-G7 Visible Mapping

| Gate | Evidence |
|---|---|
| G1 canonical source citation | Blueprint §1 and §4 cite Stage 1 audit, Stage 3 synthesis, D11/D12, T3L archives, and shipped source ranges. |
| G2 shipped source read before drafting | This audit lists source files read; blueprint §4 records current Rule, RuleExpr lowering, inspect, and SDK dispatch ranges. |
| G3 file:line precision | Blueprint §4 cites exact line ranges for `Rule`, `RuleExprPortBinding`, `_head_binding`, `_materialize_branch`, RuleExpr joins, inspect DTOs, and SDK dispatch. |
| G4 goal-to-driver mapping | Blueprint §2 maps D11 identity/warning and D12 declared-port goals to implementation/test coverage. |
| G5 deviations / class triggers | Blueprint §1 M-to-L triggers, §3 non-goals, and §5.8 preemptive locks define escalation. |
| G6 reviewer spot-check | Reviewer should independently verify `_head_binding(...)`, `_materialize_branch(...)`, `SDKStore._evaluate_rule_expr_input(...)`, and `Rule.content_digest` ranges. |
| G7 pre-impl baseline | Blueprint §7 and this audit G7 plan require 131 OK baseline before feature code. |

## Class Trigger Analysis

Predicted class: M.

M-class reasons:

- touches private lowering validation substrate;
- changes public observable error/warning behavior for RuleExpr execution;
- creates reusable foundation for two downstream implementation slices;
- adds focused tests around branch/port semantics.

Not L-class because:

- D11/D12 are reviewed;
- T4.1 excludes D13/D14/D15 behavior;
- public SDK dispatch, adapter materialization, and public result boundary already exist from T3L.3.

Escalate to L-class or pause for a reviewed amendment if implementation needs external-head body concatenation, projection sugar, closed-head inspect fields, public declared-port API, result shape changes, or adapter grammar updates.

## Cross-Slice Contract Preservation

| Contract | Preservation requirement |
|---|---|
| T3L.3 public dispatch | Keep `fg.eval.evaluate(rule_expr_or_application_rule, head=...)` path and legacy fallback paths intact. |
| D6 call-shape bucket | Missing/invalid `head=` remains `SDKStoreError`. |
| D10 result boundary | Public success remains `list[CandidateSet]`; no trace/evidence DTO export. |
| D11 identity | Same id + same digest is existing head; version mismatch warns; digest mismatch errors. |
| D11 version metadata | Occurrence version may be added to private lowering metadata only for warning comparison; it must not alter identity or canonical ordering. |
| D12 declared ports | Private branch-total helper; no public `expr.declared_ports`. |
| D8 join semantics | Same-name equivalence requires explicit join materialization; no auto-join. |
| T3.5 inspect | Inspect shape remains unchanged in T4.1. |
| T4.2 boundary | No external-head body concatenation or projection sugar. |
| T4.3 boundary | No closed-head inspect fields. |
| T5 boundary | No EvaluateResult, Explanation, WhyNot, row.close, or evidence narrative. |

## Step 4.6 Pre-Implementation Grep Plan

Run before feature implementation:

| Check | Command | Expected use |
|---|---|---|
| 1. Existing head / declared-port helper names | `rg 'DeclaredPort|HeadValidation|head_validation|declared_port|RuleExprHead|is_closed|unbound_ports' src/factgraph tests` | Find name collisions and prevent accidental T4.3 closed-head scope. |
| 2. Lowering head identity substrate | `rg '_head_binding|_head_var_names|projection_occurrence_alias|head_binding|content_digest|version' src/factgraph/application src/factgraph/sdk tests` | Verify insertion points for D11 identity and warning behavior. |
| 3. Branch / join substrate | `rg 'RuleExprJoinMaterialization|pending_joins|join_materializations|join_by_ports|unjoined_same_name_ports' src/factgraph/application tests` | Confirm D12 same-name equivalence can use existing join substrate. |
| 4. Public dispatch and error buckets | `rg 'evaluate\\(|SDKStoreError|RuleExprError|warnings.warn|UserWarning|head=' src/factgraph/sdk src/factgraph/application tests` | Confirm SDK call-shape vs semantic error boundary. |
| 5. Projection / closed-head / T5 gates | `rg 'Rule\\.projection|projection\\(|is_closed|unbound_ports|EvaluateResult|row\\.close|why_not|Explanation' src/factgraph tests workflow` | Catch T4.2/T4.3/T5 scope creep before implementation. |
| 6. Public result / adapter gates | `rg 'CandidateSet|EvidenceEnvelope|SupportArtifact|CompiledDerivationPlan|DerivationEvaluateRequest|pyreason|souffle|problog' src/factgraph tests` | Confirm no result-shape or adapter grammar work is needed. |

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
  tests.sdk.test_rule_expr_evaluate \
  -v
```

Expected draft baseline: 131 OK.

Pytest remains deferred per existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded because failures are pre-existing and unrelated to RuleExpr / Head validation.

## Step 4.2 Draft Review Checklist

Reviewer should verify:

1. Blueprint status is `draft`.
2. T4.1 scope is limited to D11/D12 foundation.
3. External-head body concatenation remains T4.2.
4. `Rule.projection(...)` remains T4.2.
5. Closed-head inspect fields remain T4.3.
6. D11 identity states are complete and version is warning-only.
7. D12 declared-port semantics are branch-total and private.
8. Same-name equivalence requires explicit D8 join materialization.
9. Public result shape and legacy dispatch paths are preserved.
10. Error buckets follow D11/D6.
11. Step 4.6 grep covers projection/closed-head/T5 scope creep.
12. G7 baseline uses the post-T3 later 131 OK gate.
13. Sacred / dirty invariants are not touched.

## G7 Baseline Record

Pending.

## Closure Notes

Pending.
