# Task Blueprint Audit: T3L.1 Internal RuleExpr Lowering And Native Execution

- Blueprint: [2026-05-25_t3l-1-internal-lowering-native.md](./2026-05-25_t3l-1-internal-lowering-native.md)
- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-25 | draft | Blueprint created | Initial T3L.1 M-class scope drafted from reviewed Stage 1 audit, reviewed D6-D10, Stage 3 synthesis, track-plan sync, and archived T3.1-T3.6 substrate. Scope is private RuleExpr lowering core plus native execution only; public SDK dispatch and adapter parity remain later slices. |
| 2026-05-25 | draft-amend | Step 4.2 v1 precision amendments | T3L.1-WC1 native materialization now returns per-branch trace tuple; T3L.1-WC2 external head body concatenation explicitly deferred to T3L.3; WC3 concrete typing refinement, WC4 abstract alias-local example, and N1 track-plan cite added. |
| 2026-05-25 | scoped | Step 4.6 grep clean; scope locked | Six pre-implementation grep checks found no `RuleExprLoweringPlan` / `RuleExprEvaluationTrace` / `rule_expr_lowering` collisions, confirmed existing runtime/native/aggregate/adapter substrates, and found no need to touch public SDK dispatch in T3L.1. Blueprint status moved from draft to scoped. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
- Stage 3 synthesis: `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`
- D6 public entrypoint/head boundary: `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
- D7 lowering plan shape: `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
- D8 join lowering semantics: `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
- D9 adapter matrix/rejection policy: `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
- D10 result/evidence boundary: `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
- Track plan sync: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
- T3 substrate archives: T3.1, T3.2, T3.3, T3.4, T3.5, and T3.6 archive pairs under `workflow/blueprints/archive/`

### G1-G7 Visible Mapping

| Gate | T3L.1 mapping |
|---|---|
| G1 | Canonical source chain includes Stage 1 audit, Stage 3 synthesis, D6-D10 reviewed decisions, track-plan sync, and T3.1-T3.6 archives. |
| G2 | Blueprint section 4 cites shipped RuleExpr, derivation runtime, and WhereAST source with file:line ranges. |
| G3 | File citations include `rule_expr.py:12-330`, `derivation.py:21-90`, `derivation_runtime.py:69-139`, and `where_ast.py:19-114`. |
| G4 | Goals map to D6 C35/head, D7 plan/branch model, D8 join materialization, D9 native matrix, and D10 trace sidecar. |
| G5 | Non-goals and section 5.11 preserve public SDK dispatch, adapter parity, public result shapes, T4/T5 boundaries, legacy evaluation, exports, and error subclass boundaries. |
| G6 | Reviewer should spot-check module placement, DTO categories, alias-local variable invariant, join materialization semantics, native-only scope, and trace sidecar boundary. |
| G7 | Section 8 requires baseline checks before implementation, with T3.6 preservation gate expected at 99 OK. |

### Class Trigger Analysis

T3L.1 is M-class.

M-class reasons:

- Adds a private lowering module with multiple internal DTO categories.
- Implements branch-set lowering, alias-local variable namespacing, join materialization, and native runtime materialization.
- Consumes five reviewed Stage 2 decisions and the Stage 3 synthesis.
- Adds focused native execution tests spanning protocol lowering, WhereIR, derivation runtime, and aggregate preservation.
- Must preserve many public negative-action gates while adding internal execution behavior.

Why not L:

- Stage 1 audit, D6-D10, Stage 3 synthesis, and track-plan sync already decomposed the L-class cluster.
- T3L.1 does not expose public SDK dispatch.
- T3L.1 does not implement Souffle, ProbLog, or PyReason parity.
- T3L.1 does not add public result DTOs, T4 Head, or T5 WhyNot/EvaluateResult behavior.

M-to-L triggers:

- public SDK dispatch enters this slice;
- adapter parity enters this slice;
- public result/support/evidence shapes change;
- T4/T5 scope enters this slice;
- implementation discovers D6-D10 must be reopened.

### Preemptive Scope Check

T3L.1 carries forward the T3.3-T3.6 zero-deviation discipline:

- Public SDK evaluate dispatch remains untouched.
- Legacy SDK evaluation remains untouched.
- New lowering helpers stay private.
- No SDK exports or docs rows are added.
- `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, and `CompiledDerivationPlan` public shapes remain untouched.
- Souffle, ProbLog, and PyReason adapters remain untouched.
- T4 Head / closed-head behavior remains out of scope.
- T5 EvaluateResult / WhyNot remains out of scope.
- `RuleExprInspect` is not reused as execution IR.
- No same-name auto-join.
- No RuleExpr equality/hash/canonicalization changes.
- No new error subclass.

### Reviewer Focus Areas

- Whether T3L.1's scope is narrow enough for M-class.
- Whether `rule_expr_lowering.py` is the right sibling module boundary.
- Whether private DTO categories faithfully reflect D7/D8/D10 without becoming public API.
- Whether D6 head binding is represented without importing full T4 Head behavior.
- Whether alias-local variable namespacing is explicit enough to prevent accidental joins.
- Whether D8 equality atom materialization and provenance are testable.
- Whether D9 native-only materialization avoids adapter parity drift.
- Whether D10 trace sidecar stays private and does not mutate `CandidateSet` / support / evidence shapes.
- Whether G7 baseline and Step 4.6 grep are sufficient before implementation.

### Cross-Slice Contract Preservation

| Prior slice / decision | Expected preservation |
|---|---|
| T1.4 alias/port substrate | `Rule`, `RuleOccurrence`, `RulePortRef`, `PortType`, alias regex, and port APIs unchanged. |
| T2.3 aggregate track | Aggregate-local scope and native aggregate behavior preserved; PyReason aggregate exclusion remains D9/T3L.2+ concern. |
| T3.1 base RuleExpr | Bool guards and public exports unchanged. |
| T3.2 scope validation | Alias uniqueness and explicit alias semantics preserved. |
| T3.3 joins/reach | `RuleJoinConstraint`, reach validation, same-occurrence rejection, and no OR reach lookthrough preserved. |
| T3.4 join_by_ports | Explicit-name expansion remains authoring-time only; no same-name auto-join added. |
| T3.5 inspect | `RuleExprInspect` remains inspect DTO and not execution IR. |
| T3.6 docs | User-facing docs remain current; no docs change unless scoped amendment. |
| D6 | Eventual public entrypoint/head boundary respected while public dispatch stays closed. |
| D7 | Private lowering plan categories and branch model implemented without public export. |
| D8 | Explicit equality atom joins and materialization metadata implemented. |
| D9 | Native matrix row implemented; non-native adapters deferred. |
| D10 | Public result shape untouched; private trace sidecar preserved. |

### Step 4.6 Pre-Implementation Grep Plan

| Check | Command | Expected use |
|---|---|---|
| Existing lowering names | `rg 'RuleExprLoweringPlan|RuleExprEvaluationTrace|rule_expr_lowering' src/factgraph tests` | Confirm no shipped name collision. |
| Runtime plan construction | `rg 'CompiledDerivationPlan|DerivationEvaluateRequest' src/factgraph tests` | Locate construction patterns before adding native materialization. |
| Native branch-list support | `rg 'OrExpr|branches|branch_index|support_key|b\\{branch' src/factgraph/core src/factgraph/application tests` | Verify runtime branch/support assumptions before code. |
| Aggregate tests | `rg 'AggregateAtom|aggregate|empty-set|empty set|count|sum' tests src/factgraph` | Identify preservation tests for T2.3 aggregate behavior. |
| Public evaluate dispatch | `rg 'def evaluate\\(|SDKStore.evaluate|_SDKEvalManager' src/factgraph/sdk src/factgraph/application tests` | Confirm public SDK dispatch stays untouched in T3L.1. |
| Adapter boundaries | `rg 'pyreason|souffle|problog|where_compile|problog_export' src/factgraph/adapters tests` | Confirm adapter work is deferred to T3L.2. |

If grep finds a needed Python touch outside scoped modules or a public dispatch dependency, pause for a scope amendment before implementation.

### Step 4.6 Pre-Implementation Grep Results

| Check | Result | Implementation impact |
|---|---|---|
| Existing lowering names | `rg 'RuleExprLoweringPlan\|RuleExprEvaluationTrace\|rule_expr_lowering' src/factgraph tests` returned no matches. | Clean namespace for new private `rule_expr_lowering.py` module and internal DTO names. |
| Runtime plan construction | `rg 'CompiledDerivationPlan\|DerivationEvaluateRequest' src/factgraph tests` found existing construction in application runtime, SDK store, capability helpers, docs, and established tests. | Use existing runtime plan patterns; no unexpected RuleExpr lowering owner exists. |
| Native branch/support substrate | `rg 'OrExpr\|branches\|branch_index\|support_key\|b\{branch' src/factgraph/core src/factgraph/application tests` found expected branch-list, support-key, walker, rule-disable, diagnose/check, and native evaluator substrates. | Confirms D9/D10 branch-index assumptions are backed by shipped substrate; no scope amendment needed. |
| Aggregate preservation tests | `rg 'AggregateAtom\|aggregate\|empty-set\|empty set\|count\|sum' tests/application tests/test_application* tests/test_core_rules* src/factgraph/application/protocol src/factgraph/core/rules src/factgraph/application/docs/rule.md` found T2.3 aggregate substrate and tests including `tests/application/protocol/test_rule_aggregate.py`. | T3L.1 should reuse existing aggregate tests and add focused native RuleExpr aggregate preservation tests. |
| Public evaluate dispatch | `rg 'def evaluate\(\|SDKStore.evaluate\|_SDKEvalManager' src/factgraph/sdk src/factgraph/application tests` found only `src/factgraph/sdk/store.py` plus SDK namespace/invariant tests. | Confirms T3L.1 can keep public SDK dispatch untouched; T3L.3 owns public dispatch changes. |
| Adapter boundaries | `rg 'pyreason\|souffle\|problog\|where_compile\|problog_export' src/factgraph/adapters tests` found expected adapter implementations and tests. | Confirms non-native adapter work is present but deferred to T3L.2; no T3L.1 adapter touch needed. |

### G7 Baseline Plan

Baseline command:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  -v
```

Expected starting point: 99 OK from the T3.6 preservation gate.

Do not use `tests.test_public_inference_factgraph_create` as a T3L.1 blocking gate; it has documented pre-existing failures unrelated to RuleExpr execution lowering.

### Step 4.2 Draft Review Checklist

- [ ] M-class declaration is justified and L triggers are explicit.
- [ ] Stage 1 audit + D6-D10 + synthesis cite chain is complete.
- [ ] T3L.1 scope matches synthesis section 3.
- [ ] Non-goals keep T3L.2/T3L.3 work out.
- [ ] Module placement uses sibling isolation or explains any alternative.
- [ ] Private DTO categories match D7/D8/D10.
- [ ] D6 head binding does not import full T4 behavior.
- [ ] D7 AND/OR branch model is explicit.
- [ ] D8 equality atom materialization and provenance are explicit.
- [ ] D9 native-only matrix row is explicit.
- [ ] D10 private trace sidecar is explicit and public result shapes are untouched.
- [ ] Preemptive scope locks preserve legacy SDK, public dispatch, adapters, exports, T4/T5, and error hierarchy.
- [ ] Acceptance gates are testable and include preservation tests.
- [ ] Step 4.6 grep plan is specific enough to catch scope creep before code.
