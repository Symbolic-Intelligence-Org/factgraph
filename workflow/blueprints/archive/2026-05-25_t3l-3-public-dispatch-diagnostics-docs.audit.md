# Audit Log: T3L.3 Public SDK Dispatch, Diagnostics, And Docs

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Blueprint: [2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md](./2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | draft | T3L.3 blueprint pair created | Scope consumes Stage 3 synthesis T3L.3 row, D6/D9/D10, T3L.1/T3L.2 archived substrate, and shipped SDK dispatch/docs evidence. |
| 2026-05-25 | draft-amend | Step 4.2 v1 precision amendments | Locked the external-head public behavior to conservative inline/projected-head support with SDKStoreError rejection for external heads, clarified missing/invalid `head=` as SDK call-shape errors per D6, and specified RuleExpr `engine_options` forwarding through existing evaluation machinery. |
| 2026-05-25 | scoped | Step 4.6 grep clean; scope locked | Six pre-implementation grep checks found expected T3L.1/T3L.2 lowering substrate, SDK evaluate dispatch surface, head/application Rule call sites, SDKStoreError diagnostics, result/evidence surfaces, and docs update targets. No A-fallback amendment needed; external-head conservative rejection and public result boundary remain locked. |
| 2026-05-25 | baseline | G7 preservation baseline | Ran the scoped baseline command covering T3.1-T3.6, T3L.1, and T3L.2 preservation suites; result matched expectation: 121 tests OK. Pytest remains deferred per SIGSEGV environment lock; unrelated `tests.test_public_inference_factgraph_create` remains excluded. |
| 2026-05-25 | implemented | Step 4.7 fix + closure | Feature commit `25b71e64` added public SDK RuleExpr dispatch, 10 focused SDK tests, and 4 docs file updates; Step 4.7 fix `762731fa` replaced fragile string matching with explicit `_RULE_EXPR_DEFAULT_ALIAS_RE` validation and surfaced fallback behavior in user docs. Final gates: 10 focused SDK tests OK, 131 preservation tests OK, ruff clean. |

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

### External-Head Boundary

T3L.1 and T3L.2 explicitly deferred external-head body concatenation. T3L.3 locks the conservative public behavior:

- inline/projected heads are supported;
- external `head=` values requiring body concatenation raise `SDKStoreError`;
- the message guides callers to include the head rule as an expression occurrence for this tranche.

This avoids smuggling full T4 Head behavior into the final T3 later slice.

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

## Step 4.6 Pre-Implementation Grep Results

| Check | Result | T3L.3 impact |
|---|---|---|
| 1. Existing RuleExpr public dispatch | Expected hits in T3L.1/T3L.2 lowering substrate, focused tests, docs, and `SDKStore.inspect_rule(...)`. The only `src/factgraph/sdk/store.py` `_RuleExpr` hit is the existing inspect helper, not `evaluate(...)`. | Public evaluate dispatch can be added in T3L.3 without colliding with an existing RuleExpr evaluate branch. |
| 2. SDK evaluate dispatch paths | Expected hits in `_SDKEvalManager.evaluate(...)`, `SDKStore.evaluate(...)`, `_resolve_public_engine_and_semantics(...)`, `to_authoring_payload(...)`, and `_evaluate_compiled_derivation_plans(...)`. | Insertion point and legacy path are clear; no amendment needed. |
| 3. Head and ApplicationRule usage | Expected hits across application `Rule`/`ApplicationRule`, `head=` docs/tests, `RuleExprInspect`, legacy SDK `Inference`, and archived T3L.1/T3L.2 blueprint decisions. | Accepted/rejected head shapes remain consistent with D6 and the v2 external-head rejection lock. |
| 4. SDKStoreError diagnostics | Existing `SDKStoreError` usage, PyReason semantics paths, and T3L.2 classifier fields are present; no conflicting public diagnostic owner exists. | T3L.3 can convert RuleExpr call-shape and adapter preflight failures to `SDKStoreError` under D9 section 4.9. |
| 5. Public result/evidence boundaries | `CandidateSet`, `EvidenceEnvelope`, `branch_atom_projection`, and payload surfaces are existing protocol/test surfaces. No public `RuleExprEvaluateResult` owner exists. | D10 public result boundary stays locked: success returns `list[CandidateSet]`; trace/evidence DTOs remain private. |
| 6. Docs update surface | Expected RuleExpr authoring docs, existing `evaluate(...)` sections, `CandidateSet` docs, PyReason notes, same-name-port/no-auto-join guidance, and bool guard docs are present. | Docs update surface is known and bounded; T3L.3 should extend, not rewrite, T3.6 guidance. |

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

| Item | Result |
|---|---|
| Branch | `v0.2.0-t3l-3-public-dispatch-diagnostics-docs-2026-05-25` |
| Sacred / dirty state | Sacred `master` untouched; existing 4M + 1U dirty set preserved. |
| Step 4.6 precondition | Clean at scoped commit `5f607628`; no A-fallback amendment required. |
| Baseline command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter -v` |
| Result | 121 tests OK. |
| Pytest status | Deferred per existing SIGSEGV environment lock. |
| Excluded unrelated suite | `tests.test_public_inference_factgraph_create` remains excluded due to pre-existing failures outside T3L.3 scope. |

## Closure Notes

### Final code scope

- `src/factgraph/sdk/store.py` now contains the public RuleExpr / application Rule dispatch branch, SDK call-shape validation, conservative external-head rejection, private adapter-support-to-`SDKStoreError` conversion, and explicit non-identifier rule-id fallback.
- `tests/sdk/test_rule_expr_evaluate.py` adds 10 focused SDK tests for public success, C35 coercion, missing / invalid `head=`, external-head rejection, Souffle / ProbLog request shape, PyReason classifier conversion, and legacy `Inference` preservation.
- Four docs files were updated: `03_rules_and_inferences.en.md`, `00_user_guide.en.md`, `01_concepts.en.md`, and `application/docs/rule.md`.

### Verification

- G7 baseline before implementation: 121 tests OK.
- Feature commit `25b71e64`: 131 preservation tests OK.
- Step 4.7 fix `762731fa`: 10 focused SDK tests OK, 131 preservation tests OK, and `ruff` clean.
- Pytest remains deferred under the existing SIGSEGV environment lock; `tests.test_public_inference_factgraph_create` remains excluded as unrelated pre-existing failure coverage.

### Scope preservation

- No adapter production files were edited.
- No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` public shape changed.
- No public RuleExpr lowering, trace, or adapter-support DTO was exported.
- No T4 Head / closed-head behavior, T5 `EvaluateResult` / WhyNot surface, or PyReason Form 2 grammar expansion was introduced.
- Legacy SDK `Inference` and derivation dict evaluation paths remain preserved.

### Step 4.7 disposition

- WC1: addressed by replacing private exception-message matching with `_RULE_EXPR_DEFAULT_ALIAS_RE`.
- WC2: addressed by documenting the stable `head` occurrence fallback for application Rule ids that are not valid default aliases.
- No P0/P1 issues remained at closure.

### Deferred

- PyReason Form 2 grammar expansion remains beyond T3 later.
- T4 Head / closed-head behavior remains an independent track.
- T5 `EvaluateResult`, WhyNot, public trace DTOs, and public evidence expansion remain independent T5 work.

Ready for archive commit.
