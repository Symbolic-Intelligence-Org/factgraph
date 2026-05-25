# Audit Log: T3L.2 Adapter Matrix Parity And Aggregate Preservation

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Blueprint: [2026-05-25_t3l-2-adapter-matrix-parity.md](./2026-05-25_t3l-2-adapter-matrix-parity.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | draft | T3L.2 blueprint pair created | Scope consumes Stage 3 synthesis T3L.2 row, D8-D10, T3L.1 archived substrate, and shipped Souffle / ProbLog / PyReason adapter evidence. |

## Decision Notes

### Source Chain

1. Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`.
2. Stage 2 decisions:
   - D8 `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
   - D9 `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
   - D10 `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
3. Stage 3 synthesis `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`.
4. Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T3L.2 row.
5. T3L.1 archived blueprint pair:
   - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
   - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.audit.md`

### Shipped Source Read Before Draft

Read before drafting:

- `src/factgraph/application/protocol/rule_expr_lowering.py`
- `src/factgraph/adapters/souffle/where_compile.py`
- `src/factgraph/adapters/problog/problog_export.py`
- `src/factgraph/adapters/pyreason/where_compile.py`
- `tests/test_problog_export.py`
- `tests/test_pyreason_branch_bounds_carrier.py`
- `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
- `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`

### Draft Scope Decision

T3L.2 defaults to extending the private T3L.1 lowering module and adding focused adapter tests. Adapter production files are read surfaces by default. If Step 4.6 finds that Souffle / ProbLog / PyReason production code must change, this blueprint needs an amendment before feature implementation.

Rationale:

- D9 says Souffle and ProbLog support the needed shapes within shipped grammar.
- D9 says PyReason is pred-only and must reject non-pred shapes; this is classification, not grammar expansion.
- T3L.3 owns public dispatch and public error conversion.

## G1-G7 Visible Mapping

| Gate | Evidence |
|---|---|
| G1 canonical source citation | Blueprint §1 and §4 cite Stage 3 synthesis, D8-D10, track plan, T3L.1 archive, and shipped adapter file ranges. |
| G2 shipped source read before drafting | This audit lists read source files; blueprint §4 records shipped line ranges. |
| G3 file:line precision | Blueprint §4 cites exact line ranges for T3L.1 lowering and three adapters. |
| G4 goal-to-driver mapping | Blueprint §2 maps goals to D9 adapter rows, D10 trace boundary, and Stage 3 T3L.2 scope. |
| G5 deviations / class triggers | Blueprint §1 M-to-L triggers and §5.8 preemptive locks define escalation. |
| G6 reviewer spot-check | Reviewer should independently verify Souffle eq/aggregate lines, ProbLog OR/eq/aggregate lines, and PyReason pred-only rejection lines. |
| G7 pre-impl baseline | Blueprint §7 and this audit G7 plan require 111 OK baseline before feature code. |

## Class Trigger Analysis

Predicted class: M.

Why M:

- Uses a shipped private lowering substrate from T3L.1.
- Adds adapter-aware private helpers and tests across three engine surfaces.
- Consumes reviewed D9/D10 decisions rather than reopening public API shape.

Escalate to L or pause for amendment if:

- adapter production grammar must change;
- PyReason support expands beyond pred-only classification;
- public SDK dispatch is touched;
- public result / trace / support DTOs change;
- T3L.2 cannot satisfy Souffle or ProbLog through shipped grammar.

## Preemptive Scope Check

| Risk | Lock |
|---|---|
| Public dispatch creep | No `_SDKEvalManager.evaluate(...)` or `SDKStore.evaluate(...)` changes. |
| Adapter grammar creep | Adapter production files are read surfaces unless Step 4.6 amendment expands scope. |
| PyReason Form 2 creep | Private classifier only; no PyReason grammar changes. |
| Public DTO creep | No CandidateSet / SupportArtifact / EvidenceEnvelope / CompiledDerivationPlan shape changes. |
| Docs creep | No public docs or examples; T3L.3 owns docs. |
| Trace/export creep | Private trace and adapter support data are not exported. |
| Aggregate scope creep | Aggregate-filter-local variables remain T2.3-local, not RuleExpr ports. |

## Reviewer Focus Areas

1. Verify Souffle source lines support OR-of-AND, `eq`, and aggregate operands as claimed.
2. Verify ProbLog source lines support OR branches, `eq`, and aggregate export as claimed.
3. Verify PyReason source lines remain pred-only and reject `eq` / non-pred atoms.
4. Confirm T3L.2 does not touch public SDK dispatch.
5. Confirm no adapter grammar file changes occur without an amendment.
6. Confirm PyReason classifier preserves D9 section 4.9 future message fields privately.
7. Confirm aggregate-filter-local variables are not surfaced as `RuleExprPortBinding`.
8. Confirm T3L.1 native tests remain green.

## Cross-Slice Contract Preservation

| Slice / Decision | Preservation |
|---|---|
| T1.4 ports | T3L.2 consumes T3L.1 port bindings; no port substrate change. |
| T2.3 aggregates | Souffle / ProbLog aggregate behavior remains shipped; PyReason rejects aggregates. |
| T3.3 / T3.4 joins | Explicit joins remain D8 eq atoms; no auto-join. |
| T3.5 inspect | Inspect remains separate from execution lowering. |
| T3.6 docs | Public docs remain deferred to T3L.3. |
| T3L.1 native lowering | Native helper behavior and tests remain preserved. |
| D8 join lowering | T3L.2 consumes D8 materialized eq atoms and metadata. |
| D9 adapter matrix | Souffle / ProbLog supported within shipped grammar; PyReason pred-only. |
| D10 result boundary | No public result wrapper or support-shape expansion. |

## Step 4.6 Pre-Implementation Grep Plan

Run before feature implementation:

| Check | Command | Expected use |
|---|---|---|
| 1. Existing adapter helper names | `rg '_materialize_.*derivation_plan|RuleExprAdapter|AdapterSupport|pyreason' src/factgraph/application/protocol/rule_expr_lowering.py tests/application/protocol` | Detect naming collisions and existing helper shape. |
| 2. Branch-list runtime assumptions | `rg 'OrExpr|branches|branch_index|branch_head_bounds|CompiledDerivationPlan' src/factgraph/adapters src/factgraph/application tests` | Confirm branch-list assumptions and PyReason branch-index support. |
| 3. Equality atom adapter support | `rg 'kind == "eq"|CmpAtom|Equality comparisons|to_number|= ' src/factgraph/adapters tests` | Verify eq support/rejection paths. |
| 4. Aggregate adapter support | `rg 'AggregateAtom|aggregate|findall|sum_list|min_list|max_list|empty-set|empty set' src/factgraph/adapters tests` | Identify aggregate preservation tests and adapter support boundaries. |
| 5. PyReason pred-only boundary | `rg 'compile_where_ir_to_pyreason|_validate_pred_atom|not supported in PyReason|branch_head_bounds' src/factgraph/adapters/pyreason tests` | Confirm classifier expectations and no Form 2 work. |
| 6. Public dispatch untouched | `rg 'def evaluate\\(|SDKStore.evaluate|_SDKEvalManager|RuleExprLoweringPlan' src/factgraph/sdk tests` | Confirm T3L.3 public dispatch remains untouched. |

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
  -v
```

Expected draft baseline: 111 OK.

Pytest remains deferred per existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded because failures are pre-existing and unrelated to RuleExpr lowering.

## Step 4.2 Draft Review Checklist

Reviewer should verify:

1. Blueprint status is `draft`.
2. Class prediction and M-to-L triggers are explicit.
3. D9 Souffle / ProbLog / PyReason matrix is accurately reflected.
4. D10 public result restraint is preserved.
5. T3L.1 native substrate is treated as dependency, not reopened.
6. Adapter production files are not pre-authorized for edits without Step 4.6 amendment.
7. PyReason Form 2 remains deferred.
8. Public SDK dispatch remains deferred to T3L.3.
9. Step 4.6 grep commands cover adapter grammar and public dispatch.
10. G7 baseline uses the post-T3L.1 111 OK gate.
11. Acceptance includes adapter-focused tests.
12. Cross-slice contract table covers T2.3 aggregates and T3L.1.
13. Sacred / dirty invariants are not touched.

## G7 Baseline Record

Pending.

## Closure Notes

Pending.
