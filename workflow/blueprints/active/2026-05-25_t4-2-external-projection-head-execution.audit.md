# Audit Log: T4.2 External + Projection Head Execution

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Blueprint: [2026-05-25_t4-2-external-projection-head-execution.md](./2026-05-25_t4-2-external-projection-head-execution.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | draft | T4.2 blueprint pair created | Scope consumes T4 Stage 3 synthesis T4.2 row, D13/D14 reviewed decisions, T4.1 archived foundation, and shipped RuleExpr lowering / SDK dispatch evidence. Pre-draft grep found no A-fallback trigger. |
| 2026-05-25 | draft-amend | Step 4.2 v1 precision amendments | Locked D13 head-link materialization to sorted head port-name order, clarified head-side output vars for external/projection heads, documented inline/external/projection materialization subsets, surfaced aggregate x PyReason interaction, and specified projection recognition timing during head binding construction. |
| 2026-05-25 | scoped | Step 4.6 grep clean; scope locked | Seven pre-implementation grep checks found expected T4.1 validation consumers, existing external-head blockers, D13/D14 docs-only projection/head-link references, broad T4.3/T5/result-surface references, and existing adapter surfaces. No production collision or A-fallback amendment needed; T4.2 remains limited to D13 + D14. |

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
4. Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T4.2 row.
5. Archived implementation slices:
   - `workflow/blueprints/archive/2026-05-25_t4-1-head-identity-declared-port-foundation.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`

### Shipped Source Read Before Draft

Read before drafting:

- `src/factgraph/application/protocol/rule.py`
- `src/factgraph/application/protocol/rule_expr_lowering.py`
- `src/factgraph/sdk/store.py`
- `src/factgraph/core/rules/where_ast.py`
- `tests/application/protocol/test_rule_expr_head_validation.py`
- `tests/application/protocol/test_rule_expr_lowering.py`
- `tests/application/protocol/test_rule_expr_lowering_adapter.py`
- `tests/sdk/test_rule_expr_evaluate.py`
- T4 Stage 1 audit, Stage 3 synthesis, D13, D14, and T4.1 archived blueprint/audit.

### Draft Scope Decision

T4.2 is the second implementation slice of the T4 Head tranche. It should lift the T3L.3 external-head rejection and add D14 projection sugar, but it must stay inside D13/D14:

- external head body atoms are branch-wise materialized;
- head-port link equality atoms bind head vars to D12 declared branch sources;
- `Rule.projection(*port_names)` creates a normal application `Rule` with private recognizable placeholder shape;
- projection placeholders do not materialize as filters;
- public evaluation result remains `list[CandidateSet]`.

Rationale:

- T4.1 has already landed D11 identity and D12 declared-port validation, so T4.2 can consume that foundation rather than re-solving head validity.
- D13 and D14 are coupled: projection sugar depends on D13 head-port links, while D13 needs the same declared-port branch sources T4.1 provides.
- Keeping D15 and T5 out preserves a narrow public API and limits review to materialization behavior.

### Error Bucket Decision

T4.2 preserves prior buckets:

- projection construction errors use `RuleValidationError`;
- RuleExpr / head semantic validation errors use `RuleExprError`;
- public SDK call-shape errors remain `SDKStoreError`;
- adapter support rejections remain `SDKStoreError`;
- no new public error subclass.

### D15 / T5 Deferral

T4.2 must not add:

- `inspect.is_closed`;
- `inspect.unbound_ports`;
- closed-head validator public reporting;
- `EvaluateResult`;
- Explanation / WhyNot / `row.close()`;
- public trace or evidence DTOs.

T4.3 owns inspect/docs for closed-head behavior. T5 owns result/evidence surfaces.

## G1-G7 Visible Mapping

| Gate | Evidence |
|---|---|
| G1 canonical source citation | Blueprint §1 cites Stage 1 audit, Stage 3 synthesis, D13/D14, T4.1 archive, and shipped source ranges. |
| G2 shipped source read before drafting | This audit lists source files read; blueprint §1 records current Rule, lowering, materialization, and SDK dispatch ranges. |
| G3 file:line precision | Blueprint §1 cites exact lines for `Rule`, `where_ast`, lowering DTOs/helpers, external-head blockers, and SDK dispatch. |
| G4 goal-to-driver mapping | Blueprint §2 maps D13 external-head materialization and D14 projection sugar to implementation/test contracts. |
| G5 deviations / class triggers | Blueprint §0 and §7 list out-of-scope items, M-to-L triggers, and preemptive locks. |
| G6 reviewer spot-check | Reviewer should verify external-head blockers, projection zero-implementation state, D13/D14 source anchors, and T4.1 helper consumption. |
| G7 pre-impl baseline | Blueprint §4 requires the post-T4.1 145-test baseline before feature code. |

## Class Trigger Analysis

Predicted class: M.

M-class reasons:

- adds one public application `Rule` classmethod;
- changes public RuleExpr evaluation behavior for external heads;
- touches private lowering/materialization substrate shared by native/Souffle/ProbLog paths;
- consumes T4.1 declared-port foundation and T3L adapter materialization;
- adds focused application protocol and SDK tests.

Not L-class because:

- Stage 1-3 and D13/D14 already resolved the design questions;
- adapter grammar is unchanged;
- result shape is unchanged;
- D15/T5 surfaces are excluded;
- T1.3 final naming flip is excluded.

Escalate or split if implementation needs adapter file edits, result-shape changes, closed-head inspect fields, T5 evidence/result surfaces, or a global `Rule.where` invariant relaxation.

## Cross-Slice Contract Preservation

| Contract | Preservation requirement |
|---|---|
| T4.1 D11 identity | Stale digest and ambiguous inline matches still raise before materialization. Projection heads bypass D11 only when exact D14 recognizer matches. |
| T4.1 D12 declared ports | T4.2 consumes branch-total declared ports; it does not expose public `expr.declared_ports`. |
| D13 external head body | External head body atoms added to every executable branch under private alias. |
| D13 head-port links | Link atoms are separate private metadata, not D8 joins. |
| D14 projection shape | Projection returns application `Rule`; placeholders do not materialize. |
| T3L.3 public dispatch | `fg.eval.evaluate(rule_expr_or_application_rule, head=...)` stays the public path. |
| D10 result boundary | Success remains `list[CandidateSet]`; no public trace/evidence DTO. |
| Adapter matrix | No adapter production file or grammar edits. Unsupported plans reject through existing policy. |
| Legacy SDK paths | Legacy `Inference`, derivation dict, and fallback evaluation remain unchanged. |
| T4.3/T5 boundary | No closed-head inspect, `EvaluateResult`, Explanation, WhyNot, or `row.close()`. |

## Pre-Draft Grep Results

| Check | Result | T4.2 impact |
|---|---|---|
| 1. `_validate_rule_expr_head_foundation` callers | Hits are helper tests, the private helper definition, one `SDKStore._evaluate_rule_expr_input(...)` call, and T4.1 archive docs. | T4.1 validation has one production consumer; T4.2 can extend after that call without hidden call sites. |
| 2. `head_binding.kind == "external"` | Production hits are `_materialize_adapter_derivation_plan(...)` external guard and SDK external-head `SDKStoreError`; docs/archive hits are expected. | T4.2 has two blockers to replace: materializer guard and SDK rejection. |
| 3. `Rule.projection` | No production implementation; hits are parent/design/audit/archive docs and unrelated generic `projection` helper names. | D14 substrate is absent; T4.2 owns the public classmethod from scratch. |
| 4. D13 head-port link terms | Code has zero `HeadPortLink` implementation; hits are D13/D14/D15/synthesis docs. | D13 metadata can be added without collision. |
| 5. `_branch_declared_port_sources` / `_same_name_bindings_are_joined` | Hits are T4.1 helper definitions/tests and archive docs only. | T4.2 should reuse T4.1 declared-port results, not redefine graph-connectivity equivalence. |
| 6. `RuleExprHeadValidation.declared_ports` | No downstream production reader beyond T4.1 validation return construction; tests inspect it. | T4.2 introduces the first production consumer for D13 links/projection. |
| 7. Projection private metadata | `Origin(source="authoring", path="Rule.projection")` has no code hit. | Projection recognizer and placeholder shape are new T4.2 code. |

Conclusion: **clean**. No A-fallback amendment needed before draft.

## Step 4.6 Pre-Implementation Grep Plan

Run again after blueprint review and before scoping:

| Check | Command | Expected use |
|---|---|---|
| 1. T4.1 validator callers | `rg '_validate_rule_expr_head_foundation' src tests workflow/blueprints/active workflow/blueprints/archive` | Confirm no new consumer appeared before implementation. |
| 2. External-head blockers | `rg 'head_binding\\.kind == "external"|external head body concatenation|does not support external head' src tests workflow` | Confirm exact blockers to replace and no new external-head path. |
| 3. Projection substrate | `rg 'Rule\\.projection|path="Rule\\.projection"|projection head|ProjectionHead' src tests workflow` | Confirm no implementation collision and no public DTO. |
| 4. Head-port link metadata | `rg 'HeadPortLink|head-port link|head_port_link|RuleExprHeadPortLink' src tests workflow` | Confirm D13 metadata name space is clean. |
| 5. Declared-port helper consumers | `rg '_declared_ports_for_rule_expr_plan|RuleExprHeadValidation\\.declared_ports|_same_name_bindings_are_joined|_branch_declared_port_sources' src tests workflow` | Confirm T4.2 is the first production downstream consumer. |
| 6. T4.3/T5/public result gates | `rg 'is_closed|unbound_ports|EvaluateResult|row\\.close|why_not|Explanation|EvidenceEnvelope|SupportArtifact|CandidateSet' src tests workflow` | Catch closed-head/T5/result-shape creep. |
| 7. Adapter edit gates | `rg 'pyreason|souffle|problog|compile_where|export_problog' src/factgraph tests workflow/blueprints/active` | Confirm adapter grammar remains unchanged and unsupported cases use existing policy. |

If any grep result contradicts scope, pause for A-fallback amendment.

## Step 4.6 Pre-Implementation Grep Results

| Check | Result | T4.2 impact |
|---|---|---|
| 1. T4.1 validator callers | Hits are the T4.1 helper definition, helper tests, one production `SDKStore._evaluate_rule_expr_input(...)` call, active T4.2 blueprint text, and T4.1 archive docs. | No hidden production consumer appeared; T4.2 can extend behavior after the single SDK validation call. |
| 2. External-head blockers | Production hits remain `_materialize_adapter_derivation_plan(...)` external guard, `_head_var_names(...)` external guard, and SDK external-head `SDKStoreError`; focused tests and docs record the current deferred behavior. | Exact blockers to replace are visible; no parallel external-head path exists. |
| 3. Projection substrate | No production `Rule.projection(...)`, projection-head, or `ProjectionHead` implementation exists. Hits are T4 audit/synthesis/decisions/blueprint text, parent design examples, memory, and unrelated generic projection helpers/docs. | D14 implementation namespace is clean; no public projection DTO collision. |
| 4. Head-port link metadata | No production `HeadPortLink` / `RuleExprHeadPortLink` implementation exists. Hits are T4 synthesis, D13/D14/D15 decisions, T4.2 blueprint/audit, and track-plan text. | D13 private metadata can be added without collision. |
| 5. Declared-port helper consumers | Hits are T4.1 helper definitions/tests, active T4.2 blueprint/audit, and T4.1 archive docs. No production downstream reader of `RuleExprHeadValidation.declared_ports` exists. | T4.2 will be the first production consumer for D13 links/projection; it should reuse T4.1 helper results. |
| 6. T4.3/T5/public result gates | Broad expected hits across T4 synthesis/decisions/audits, old active blueprints, existing `CandidateSet` / `SupportArtifact` tests and docs, and legacy `why_not` surfaces. No T4.2 production implementation owner exists. | Closed-head/T5/result-shape terms remain pre-existing surfaces or docs; no scope amendment needed. |
| 7. Adapter edit gates | Broad expected hits across shipped adapter tests, adapter modules, old active blueprints, and T4.2 docs. No T4.2-specific adapter production edit target appeared. | Adapter grammar remains out of scope; unsupported plans continue through existing adapter policy. |

Step 4.6 conclusion: **clean**. No A-fallback scope amendment required. Proceed to G7 baseline from this scoped anchor.

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
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected draft baseline: 145 OK.

Pytest remains deferred per existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded because failures are pre-existing and unrelated to RuleExpr / Head work.

## Step 4.2 Draft Review Checklist

Reviewer should verify:

1. Blueprint status is `draft`.
2. Scope includes only D13 + D14 implementation behavior.
3. T4.1 validation is reused as prerequisite.
4. External head body atoms apply to every branch.
5. Head-port links use D12 declared branch sources and are not D8 joins.
6. Projection recognizer is exact enough to avoid accidental spoofing.
7. Projection placeholders are validation-only and never materialized.
8. Projection output order is preserved.
9. Public success remains `list[CandidateSet]`.
10. Adapter production files and grammar remain untouched.
11. D15/T5 surfaces remain excluded.
12. Step 4.6 grep plan covers T4.3/T5/public result gates.
13. G7 baseline starts from the post-T4.1 145 OK gate.

## G7 Baseline Record

Pending.
