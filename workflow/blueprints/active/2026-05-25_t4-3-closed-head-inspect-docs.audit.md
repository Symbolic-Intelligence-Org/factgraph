# Audit - T4.3 Closed-Head Inspect Utilities + Docs

Status: draft
Branch: `v0.2.0-t4-3-closed-head-inspect-docs-2026-05-25`
Blueprint: `workflow/blueprints/active/2026-05-25_t4-3-closed-head-inspect-docs.md`

## Event Log

| Date | Stage | Actor | Notes |
|---|---|---|---|
| 2026-05-25 | draft | Codex | Drafted T4.3 blueprint after pre-draft grep against the post-T4.2 baseline. Scope covers D15 closed-head inspect fields plus bounded docs updates; T5/result/evidence/adapter changes remain locked out. |
| 2026-05-25 | draft-amend | Codex | Addressed Step 4.2 v1 WCs: append-only `RuleExprInspect` field lock, RuleExpr structural inspect "not applicable" defaults, D15 section 4.4 entity-ref atom/schema path, and projection inspect-time vs D12 evaluation-time validation boundary. |

## Source Chain

| Source | Role |
|---|---|
| Stage 1 audit `2026-05-25_t4-head-closed-head-vs-shipped.md` | Identifies Q6/Q7/Q8/Q9 and F7/F8/F9 for closed-head inspect. |
| D15 `2026-05-25_t4-d15-closed-head-inspect.md` | Canonical decision for strict closed-head algorithm, inspect field location, and T5 boundary. |
| Stage 3 synthesis `2026-05-25_post-q-t4-head-closed-head-synthesis.md` | Defines T4.3 as the final T4 implementation slice. |
| T4.1 archive | Provides D11/D12 foundation and declared-port validation context. |
| T4.2 archive | Provides D13/D14 external/projection execution and projection recognizer context. |
| T3.5/T3.6 archives | Inspect and docs discipline precedent. |

## Shipped Source Read Before Draft

| Area | Files / Ranges | Notes |
|---|---|---|
| Inspect DTOs | `rule_expr_inspect.py:36-49`, `:89-136` | `RuleExprInspect` is the intended additive public surface. |
| Inspect dispatch | `rule_expr_inspect.py:155-172`, `sdk/store.py:2102-2111` | SDK currently calls `_inspect_application_rule(obj)` without schema context. |
| SDK schema context | `sdk/store.py:700-728` | `_application_schema_index` already exists and can be passed into inspect. |
| Schema metadata | `schema_runtime.py:13-57`, `:82-112`, `:189-222` | Existing schema index carries entity identity predicate metadata. |
| T4.1 validation | `rule_expr_lowering.py:277-300` | `RuleExprHeadValidation` remains private; no public declared-port export. |
| T4.2 materialization | `rule_expr_lowering.py:321-363`, `:726-793` | Runtime head-link atoms are private sidecar/materialization behavior, not D15 closure proof. |
| Existing tests | `tests/sdk/test_ruleexpr_inspect.py` | Public inspect suite to extend. |
| Docs | SDK docs + application rule docs | Need bounded T4 behavior update without T5 claims. |

## Pre-Draft Grep Results

| Check | Command intent | Result | Impact |
|---|---|---|---|
| 1 | `_validate_rule_expr_head_foundation` callers | Helper definitions/tests plus one SDK production caller; no hidden consumer. | T4.3 does not need to alter validation ordering. |
| 2 | `_materialize_branch` / `_materialize_adapter_derivation_plan` consumers | Existing protocol/SDK consumers only. | Closed-head inspect should not reuse runtime-augmented materialization as proof. |
| 3 | `RuleExprHeadValidation.declared_ports` downstream | No T4.3 implementation consumer; current readers are T4.2 materialization/testing. | No public declared-port surface exists. |
| 4 | `is_closed` / `unbound_ports` / `closed_head` | No production implementation owner. | Namespace is clear for D15 fields. |
| 5 | `RuleExprInspect` fields | Existing inspect DTO and tests only. | Additive fields belong here. |
| 6 | T5 guard terms | Pre-existing docs/tests/surfaces only; no T4.3 production owner. | No T5 collision; keep docs locked. |
| 7 | Adapter guard terms | Existing adapters/tests/docs only; no T4.3 adapter target. | No adapter edit needed. |

Conclusion: pre-draft grep is clean. No A-fallback scope amendment is needed before draft.

## Draft Scope Decision

T4.3 remains M-class. The slice is bounded to additive inspect metadata and docs. It consumes D15 and the already-archived T4.1/T4.2 helpers but does not change evaluation result shape, adapter grammar, or public evidence.

The central scope decision is to add `is_closed` and `unbound_ports` to existing `RuleExprInspect` with defaults. This keeps D15 inside the T3.5 inspect surface instead of creating a new public DTO.

## Error Bucket Decision

T4.3 reports open heads; it does not reject them.

| Case | Bucket |
|---|---|
| Open application head | `RuleExprInspect(is_closed=False, unbound_ports=...)`, no exception |
| Missing schema metadata | Conservative unbound entity-ref port, no exception |
| Unsupported inspect input at SDK boundary | Existing SDK inspect error path |
| Malformed protocol object | Existing `RuleExprError` / `RuleValidationError` construction/inspection path |
| Future must-be-closed caller | Deferred to T5; not implemented here |

## G1-G7 Mapping

| Gate | Evidence |
|---|---|
| G1 canonical source | Stage 1 audit + D15 + Stage 3 synthesis + T4.1/T4.2 archives. |
| G2 shipped source read | Inspect DTO/dispatch, schema runtime, SDK schema context, and tests read before draft. |
| G3 file:line citations | Blueprint section 1 lists shipped source ranges. |
| G4 goal-to-driver | Scope maps to D15 sections 4.1-4.10 and Stage 3 T4.3. |
| G5 deviations/class triggers | Blueprint section 0 lists M-to-L triggers and negative scope locks. |
| G6 reviewer focus | Blueprint section 8 lists concrete reviewer checks. |
| G7 pre-impl precondition | Baseline command and expected 155 OK recorded in blueprint section 6 and audit below. |

## Class Trigger Analysis

| Trigger | Status |
|---|---|
| New public DTO | Not triggered; fields added to existing inspect DTO. |
| Public result shape change | Not triggered; evaluation remains `list[CandidateSet]`. |
| Adapter grammar/edit | Not triggered. |
| T5 Explain/WhyNot/row-close | Not triggered; explicit lock. |
| Schema API redesign | Not triggered; reuse existing `SchemaIndex`. |
| Rule invariant relaxation | Not triggered. |

## Cross-Slice Contract Preservation

| Contract | T4.3 handling |
|---|---|
| T4.1 declared-port validation | Read-only context; no public declared-port export. |
| T4.2 head-link materialization | Not used as closure proof; D15 operates on user-authored head atoms. |
| D15 strict closure forms | Implement only direct value literal and primary-identity entity-ref literal forms. |
| D10 public result boundary | No evaluation result change. |
| T3.5 inspect surface | Extend existing inspect DTO, no new DTO. |
| T3.6 docs discipline | Docs update only shipped behavior; no T5 promises. |
| Legacy SDK evaluation | Not touched. |
| Adapter matrix | Not touched. |

## Step 4.6 Pre-Implementation Grep Plan

Run after draft review, before scoped anchor:

| # | Check | Command intent |
|---|---|---|
| 1 | T4.1 validator callers | `rg -n "_validate_rule_expr_head_foundation" src tests workflow` |
| 2 | Materialization consumers | `rg -n "_materialize_branch|_materialize_adapter_derivation_plan" src tests workflow` |
| 3 | Declared-port consumers | `rg -n "RuleExprHeadValidation\\.declared_ports|validation\\.declared_ports|_declared_ports_for_rule_expr_plan" src tests workflow` |
| 4 | Closed-head namespace | `rg -n "is_closed|unbound_ports|closed_head|closed-head" src tests workflow` |
| 5 | Inspect DTO surface | `rg -n "class RuleExprInspect|_inspect_application_rule|_inspect_rule_expr|RuleExprInspect\\(" src tests` |
| 6 | T5/public result guards | `rg -n "EvaluateResult|Explanation|why_not|row\\.close|EvidenceEnvelope|SupportArtifact|CandidateSet" src tests workflow` |
| 7 | Adapter guards | `rg -n "pyreason|souffle|problog|compile_where|export_problog" src tests workflow` |

Expected: no production owner conflicts and no A-fallback scope amendment.

## G7 Baseline Plan

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

Expected result: 155 tests OK, matching the T4.2 final preservation gate.

Pytest remains deferred because of the existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded due to pre-existing failure.

## Step 4.2 Draft Review Checklist

| Item | Status |
|---|---|
| D15 strict two-form closure represented | Pending reviewer |
| D15 inspect location honored | Pending reviewer |
| RuleExpr structural inspect does not overclaim | Pending reviewer |
| Schema missing case conservative | Pending reviewer |
| Projection closed-by-construction bounded | Pending reviewer |
| No T5 result/evidence surfaces | Pending reviewer |
| No adapter edit | Pending reviewer |
| Docs scope bounded | Pending reviewer |
| G7 baseline plan complete | Pending reviewer |

## Closure Notes

Pending.
