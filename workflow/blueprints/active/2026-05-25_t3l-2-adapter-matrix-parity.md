# Task Blueprint: T3L.2 Adapter Matrix Parity And Aggregate Preservation

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr_lowering.py`
  - `src/factgraph/adapters/souffle/where_compile.py`
  - `src/factgraph/adapters/problog/problog_export.py`
  - `src/factgraph/adapters/pyreason/where_compile.py`
  - `tests/application/protocol/test_rule_expr_lowering.py`
  - `tests/application/protocol/test_rule_expr_lowering_adapter.py` (new, expected)
- Related Docs:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
- Audit Log:
  - [2026-05-25_t3l-2-adapter-matrix-parity.audit.md](./2026-05-25_t3l-2-adapter-matrix-parity.audit.md)

## 1. Problem

T3L.1 archived the private RuleExpr lowering substrate and native materialization path. T3 later Stage 3 synthesis assigns T3L.2 to adapter matrix parity: keep public SDK dispatch closed, reuse the T3L.1 private lowering plan, and prove that Souffle / ProbLog / PyReason behavior matches D9's reviewed adapter matrix.

Canonical drivers:

- Stage 3 synthesis section 3 assigns T3L.2 to Souffle + ProbLog branch-list/equality/aggregate preservation and an internal PyReason pred-only classifier.
- D9 section 4.1 locks eventual branch-list materialization for supported engines.
- D9 section 4.2 locks engine-specific existing grammar floors, not a portable least-common-denominator grammar.
- D9 sections 4.4-4.5 classify Souffle and ProbLog as supported within shipped grammar.
- D9 section 4.6 classifies PyReason as pred-only and requires eq / non-pred / aggregate preflight rejection later.
- D9 section 4.7 locks aggregate-in-RuleExpr preservation without promoting aggregate-filter-local variables into D7 port bindings.
- D9 section 4.9 locks the future public `SDKStoreError` message contract; T3L.2 only prepares private classification data for T3L.3.
- D10 section 4.10 requires no silent downgrade of aliases, branch ids, joins, aggregates, or trace data.
- Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T3L.2 row defines the slice envelope.

This slice is M-class because it touches a private lowering module plus three adapter grammar surfaces through tests and preflight classification. It is not L-class because Stage 1 audit, D6-D10, Stage 3 synthesis, and T3L.1 already settled public boundaries and the lowering substrate.

M-to-L triggers:

- changing public `_SDKEvalManager.evaluate(...)` / `SDKStore.evaluate(...)` dispatch;
- changing adapter grammar support rather than consuming shipped grammar;
- adding PyReason Form 2 support;
- changing public `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, or `CompiledDerivationPlan` shapes;
- exposing `RuleExprLoweringPlan`, adapter support DTOs, or trace DTOs publicly;
- discovering Souffle / ProbLog cannot consume T3L.1 materialized WhereIR without a new D9 amendment.

If any trigger appears during Step 4.6 or implementation, pause and amend this blueprint before code.

## 2. Goals

1. Extend T3L.1 private RuleExpr materialization to adapter-aware private helpers for Souffle and ProbLog.

2. Preserve D7 branch order and D8 equality atom materialization for Souffle and ProbLog:
   - one branch remains one AND body;
   - multiple branches remain OR-of-AND branch-list bodies;
   - explicit joins remain `eq` atoms appended after source body atoms.

3. Preserve aggregate-in-RuleExpr for Souffle and ProbLog using shipped T2.3 aggregate adapter support:
   - outer Rule variables follow T3L.1 alias-local namespacing;
   - aggregate-filter-local variables remain T2.3 aggregate-local;
   - empty-set guard behavior is not changed.

4. Add an internal PyReason support classifier:
   - pred-only lowered branches classify as supported;
   - D8 eq joins classify as unsupported;
   - source-rule non-pred atoms classify as unsupported;
   - aggregate-containing branches classify as unsupported;
   - no PyReason compiler grammar is expanded.

5. Preserve future D9 public rejection data without exposing it:
   - selected engine;
   - unsupported lowered atom kind or feature;
   - rejection source (`ruleexpr-join`, `source-rule-grammar`, `aggregate`, or `branch-shape`);
   - supported alternative engines when known.

6. Add focused tests proving the matrix rows:
   - native remains covered by T3L.1 tests;
   - Souffle consumes branch-list / equality / aggregate materialized RuleExpr bodies through shipped grammar;
   - ProbLog consumes branch-list / equality / aggregate materialized RuleExpr bodies through shipped grammar;
   - PyReason classifier accepts pred-only branches and rejects eq / non-pred / aggregate branches.

7. Keep public SDK dispatch, public DTOs, public docs, and SDK exports untouched.

## 3. Non-goals

- No public `fg.eval.evaluate(rule_expr, head=...)` dispatch.
- No `_SDKEvalManager.evaluate(...)` / `SDKStore.evaluate(...)` RuleExpr branch.
- No SDK exports or protocol package exports.
- No public adapter support DTO, lowering plan DTO, trace DTO, or debug helper.
- No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shape changes.
- No adapter grammar upgrade for Souffle, ProbLog, or PyReason.
- No PyReason Form 2 support.
- No public docs or user-facing examples; T3L.3 owns docs.
- No external-head body concatenation semantics; T3L.3 owns the public external-head behavior.
- No legacy SDK `Rule` / `Inference` evaluation behavior changes.
- No changes to RuleExpr authoring semantics, equality/hash, join validation, inspect, or docs.
- No new public error subclass. Private helper failures may use `RuleExprError`; future public preflight errors remain D9/T3L.3 `SDKStoreError`.

## 4. Current Context

### 4.1 T3L.1 private lowering substrate

`src/factgraph/application/protocol/rule_expr_lowering.py` currently owns the T3L.1 private substrate:

- seven frozen private DTOs at lines 40-185.
- `_lower_application_rule(...)`, `_lower_rule_expr(...)`, `_materialize_native_derivation_plan(...)`, and `_evaluate_rule_expr_native_for_tests(...)` at lines 188-250.
- branch lowering and deterministic branch ids at lines 253-378.
- D8 join materialization at lines 381-416.
- endpoint resolution through `RuleExprPortBinding` at lines 418-436.
- D6 head binding and T3L.1 external-head defer at lines 439-464.
- alias-local variable namespacing and atom rewriting at lines 493-585.
- `__all__: list[str] = []` at line 612.

T3L.2 should extend this private module rather than changing public SDK dispatch.

### 4.2 Souffle shipped grammar surface

`src/factgraph/adapters/souffle/where_compile.py` already supports the relevant WhereIR shapes:

- `_compile_atom(...)` dispatch accepts branch and atom context at lines 443-459.
- `pred` atoms compile at lines 462-484.
- `eq` atoms compile at lines 486-580, including aggregate operands at lines 493-557.
- `not` atoms compile at lines 741-796.
- unsupported atom kinds raise `WhereValidationError` at line 798.
- `_normalize_where_subset(...)` accepts one-level AND and two-level OR-of-AND branch lists at lines 830-848.

T3L.2 should prove RuleExpr materialized branch-list / equality / aggregate bodies reach this shipped surface without changing Souffle grammar.

### 4.3 ProbLog shipped grammar surface

`src/factgraph/adapters/problog/problog_export.py` already supports the relevant export shapes:

- `export_problog(...)` writes one `rule_body_{idx}` per branch and answer disjunction at lines 97-106.
- `_normalize_where_bodies(...)` accepts OR branches at lines 113-121.
- `_compile_atom(...)` handles `pred`, `eq`, `ne`, comparisons, arithmetic, `in`, and `not` at lines 230-330.
- pred atoms with arity greater than 2 are rejected at line 259; T3L.2 must preserve that shipped limit.
- aggregate operands compile through `_compile_cmp_with_aggregate(...)` and `_compile_aggregate_parts(...)` at lines 337-384.
- aggregate filter validation rejects nested aggregates and unsupported filter atoms at lines 391-423.

T3L.2 should prove RuleExpr materialized branch-list / equality / aggregate bodies reach this shipped surface without changing ProbLog grammar.

### 4.4 PyReason shipped grammar surface

`src/factgraph/adapters/pyreason/where_compile.py` is intentionally narrower:

- `compile_where_ir_to_pyreason(...)` extracts branches and compiles each branch at lines 30-67.
- `_validate_pred_atom(...)` accepts only `pred` atoms at lines 113-128.
- `eq`, `not`, `ruleref`, and all other atom kinds are rejected at lines 129-137.
- `_extract_branches(...)` accepts branch-list shapes at lines 144-154.
- branch head bounds are already indexed by branch id position at lines 207-223.

T3L.2 should add a private classifier matching these limits. It must not expand PyReason grammar.

### 4.5 Reviewed decisions

- D8 locks explicit equality atom materialization and join provenance.
- D9 locks the adapter support matrix, aggregate preservation rules, and future public `SDKStoreError` rejection contract.
- D10 locks public result-shape restraint and private trace/provenance preservation.
- Stage 3 synthesis locks T3L.2 as adapter parity only; T3L.3 owns public dispatch and docs.

## 5. Proposed Shape

### 5.1 Module placement

Extend the private sibling module:

- `src/factgraph/application/protocol/rule_expr_lowering.py`

Default write scope:

- modify `src/factgraph/application/protocol/rule_expr_lowering.py`;
- add `tests/application/protocol/test_rule_expr_lowering_adapter.py`;
- optionally extend `tests/application/protocol/test_rule_expr_lowering.py` if shared fixtures are needed.

Adapter implementation files are read surfaces by default. If Step 4.6 shows Souffle / ProbLog / PyReason production adapter code must change to satisfy D9, pause for a scope amendment before editing adapter files.

### 5.2 Private adapter materialization helpers

Add private helpers or equivalent:

```python
RuleExprAdapterEngine = Literal["native", "souffle", "problog"]

def _materialize_adapter_derivation_plan(
    plan: RuleExprLoweringPlan,
    *,
    engine: RuleExprAdapterEngine,
) -> tuple[CompiledDerivationPlan, tuple[RuleExprEvaluationTrace, ...]]:
    ...
```

Implementation may keep `_materialize_native_derivation_plan(...)` as a wrapper around the shared helper. The shared helper must preserve T3L.1 native behavior and only generalize the private trace engine category from `"native"` to supported materialization engines.

Extending `RuleExprEvaluationTrace.engine` from `Literal["native"]` to `RuleExprAdapterEngine` (or an equivalent private union over materialization engines) is in T3L.2 scope. The T3L.1 `__post_init__` engine guard must be widened only to the supported materialization engines: `"native"`, `"souffle"`, and `"problog"`.

Minimum requirements:

- D7 branch order remains the runtime branch order.
- D8 materialized equality atoms remain in each branch body.
- `RuleExprEvaluationTrace.engine` records the selected materialization engine.
- D10 trace sidecar remains private and per-branch.
- External head body concatenation remains deferred to T3L.3.

### 5.3 Souffle parity

Souffle materialization uses the same D9 branch-list body shape as native:

- one branch -> one-level AND body;
- multiple branches -> two-level OR-of-AND body;
- explicit joins -> D8 `eq` atoms;
- aggregate terms remain existing `AggregateAtom` lowered tuples.

T3L.2 tests should compile or validate the materialized body through shipped Souffle grammar rather than adding a new Souffle grammar path.

Souffle adapter-time rejections, such as `WhereValidationError` for unsupported atom kinds, remain shipped adapter validation responsibility. T3L.3 owns conversion of those failures into public `SDKStoreError` messages per D9 section 4.9.

Expected test coverage:

- branch-list RuleExpr materializes to a Souffle-compatible OR-of-AND body;
- explicit RuleExpr join equality compiles through Souffle `eq`;
- aggregate-containing RuleExpr compiles through Souffle's existing aggregate operand support and preserves empty-set guard behavior where shipped tests expose it.

### 5.4 ProbLog parity

ProbLog materialization uses the same D9 branch-list body shape as native:

- one branch -> one-level AND body;
- multiple branches -> branch-list body consumed by `export_problog(...)`;
- explicit joins -> D8 `eq` atoms;
- aggregate terms remain existing `AggregateAtom` lowered tuples.

T3L.2 tests should export or compile the materialized body through shipped ProbLog grammar rather than adding a new ProbLog grammar path.

ProbLog adapter-time rejections, such as `ProbLogExportError` for pred arity greater than 2, remain shipped adapter validation responsibility. T3L.3 owns conversion of those failures into public `SDKStoreError` messages per D9 section 4.9.

Expected test coverage:

- branch-list RuleExpr creates multiple ProbLog rule bodies through shipped export behavior;
- explicit RuleExpr join equality exports as ProbLog equality;
- aggregate-containing RuleExpr exports through existing `findall(...)` / list predicate support;
- pred arity > 2 remains rejected by shipped ProbLog validation and is not papered over by RuleExpr lowering.

### 5.5 PyReason classifier

PyReason is intentionally excluded from `RuleExprAdapterEngine` in section 5.2 because D9 section 4.6 classifies it as a preflight rejection target, not a materialization engine. The classifier produces private support data for T3L.3 public dispatch.

Add a private classifier or equivalent:

```python
RuleExprAdapterSupport(
    engine: Literal["pyreason"],
    supported: bool,
    unsupported_feature: str | None,
    rejection_source: Literal["ruleexpr-join", "source-rule-grammar", "aggregate", "branch-shape"] | None,
    alternative_engines: tuple[str, ...],
)
```

Exact helper names may differ. `unsupported_feature` may be an atom kind such as `"eq"` / `"not"` / `"aggregate"` or a broader feature label such as `"non-pred-source-rule"` / `"branch-shape"`. The classifier must:

- classify pred-only lowered branches as supported;
- classify D8 materialized `eq` joins as unsupported with rejection source `ruleexpr-join`;
- classify source-rule non-pred atoms as unsupported with rejection source `source-rule-grammar`;
- classify aggregate-containing branches as unsupported with rejection source `aggregate`;
- preserve supported alternatives when known, expected as `("native", "souffle", "problog")` for eq/aggregate/non-pred cases;
- not call or change PyReason compiler internals to broaden support.

T3L.2 may return private classification data instead of raising. T3L.3 owns conversion of private classification into public `SDKStoreError` messages per D9 section 4.9.

### 5.6 Aggregate boundary

Aggregate preservation must follow D9 section 4.7:

- T3L.1 alias-local namespacing applies to outer Rule body variables.
- Aggregate-filter-local variables stay within T2.3 aggregate-local scope.
- Aggregate-filter-local variables are not promoted to `RuleExprPortBinding`.
- Joins may only target declared ports; joins into aggregate-local variables remain impossible.
- Native, Souffle, and ProbLog preserve aggregate behavior within existing grammar.
- PyReason classifies aggregate branches as unsupported unless a later Form 2 decision supersedes D9.

### 5.7 Error policy

Private T3L.2 helper failures use existing buckets:

- malformed RuleExpr lowering plans or impossible adapter materialization states use `RuleExprError`;
- shipped adapter compiler/export errors remain their existing adapter-specific exceptions in focused tests;
- public preflight `SDKStoreError` is not introduced until T3L.3 public dispatch.

Do not add a new public error class.

### 5.8 Preemptive scope lock

T3L.2 must not:

1. add public SDK dispatch for RuleExpr;
2. modify `_SDKEvalManager.evaluate(...)` or `SDKStore.evaluate(...)`;
3. add SDK or protocol exports;
4. expose private lowering / adapter support / trace DTOs;
5. change `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest`;
6. change adapter grammar support beyond shipped behavior;
7. add PyReason Form 2 support;
8. hide, drop, or silently downgrade joins, branch ids, aggregate atoms, or trace metadata;
9. change RuleExpr authoring semantics or inspect behavior;
10. add public docs or user-facing examples;
11. implement external-head body concatenation;
12. widen `RuleExprEvaluationTrace.engine` beyond `"native"`, `"souffle"`, and `"problog"` during this slice;
13. touch unrelated T1/T2/T3 archive docs.

### 5.9 Validation layers

T3L.2 follows the T3L.1 defense-in-depth pattern:

1. D7/T3L.1 plan construction invariants remain the first layer.
2. D8/T3L.1 join materialization invariants remain the second layer.
3. T3L.2 adapter materialization validates engine selection and trace engine categories.
4. T3L.2 PyReason classifier validates unsupported atom categories before T3L.3 public errors exist.
5. Shipped adapter compiler/export validation remains the final engine-specific layer.

## 6. Cross-Slice Contract Preservation

| Contract | Preservation |
|---|---|
| T1.4 `RulePortRef` / `PortType` substrate | T3L.2 consumes T3L.1 `RuleExprPortBinding`; no port substrate change. |
| T2.3 aggregates | Souffle / ProbLog aggregate behavior must remain shipped; aggregate-local variables are not promoted to RuleExpr ports. |
| T3.3 / T3.4 join semantics | Explicit joins remain D8 eq atoms; no same-name auto-join. |
| T3.5 inspect | `RuleExprInspect` remains non-execution IR. |
| T3.6 docs | Public docs remain deferred to T3L.3. |
| T3L.1 native lowering | Native behavior and 111-test baseline must remain green. |
| D9 PyReason boundary | Pred-only classifier only; no PyReason grammar expansion. |
| D10 public result boundary | No public result wrapper or CandidateSet shape change. |

## 7. Acceptance Criteria

1. Step 4.6 grep checks pass or trigger a pre-feat scope amendment.

2. G7 baseline preserves the T3L.1 final gate:
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
   Expected at draft time: 111 OK.

3. Focused T3L.2 tests cover:
   - Souffle branch-list materialization;
   - Souffle join equality atom compilation;
   - Souffle aggregate preservation;
   - ProbLog branch-list export;
   - ProbLog join equality export;
   - ProbLog aggregate preservation;
   - PyReason pred-only supported classification;
   - PyReason eq / non-pred / aggregate rejected classification.

4. T3L.1 native lowering tests remain green.

5. Public SDK dispatch remains untouched: no RuleExpr branch in `_SDKEvalManager.evaluate(...)` / `SDKStore.evaluate(...)`.

6. No SDK exports, protocol exports, public DTOs, or public docs are added.

7. Souffle / ProbLog production adapter files remain unchanged unless a reviewed Step 4.6 amendment explicitly expands scope.

8. PyReason grammar files remain unchanged; classifier is private and does not call PyReason compiler as an upgrade path.

9. `ruff` passes if Python files are changed.

10. Final preservation gate includes the G7 command plus new T3L.2 focused tests and reports the final OK count.

## 8. Implementation Plan

1. Run G7 baseline and record the 111 OK gate in the audit log.

2. Run Step 4.6 pre-implementation greps from the paired audit log.

3. If grep reveals adapter production changes are needed, pause for an A-fallback scope amendment before implementation.

4. Extend `rule_expr_lowering.py` with private adapter-aware materialization:
   - preserve `_materialize_native_derivation_plan(...)`;
   - add a shared materialization helper or explicit Souffle / ProbLog wrappers;
   - extend private trace engine categories without exporting them.

5. Add private PyReason classification data/helper.

6. Add focused adapter tests, expected in `tests/application/protocol/test_rule_expr_lowering_adapter.py`.

7. Run focused T3L.2 tests.

8. Run the full preservation gate and `ruff`.

9. Complete Step 4.7 review; fix P1/P2 test or scope findings before closure.

10. Close §10, transition `scoped -> implemented`, and archive the blueprint pair after implementation.

## 9. Reviewer Focus

Review should pay special attention to:

- whether adapter production files were changed without a Step 4.6 amendment;
- whether PyReason support is classification-only and pred-only;
- whether aggregate-filter-local variables remain out of `RuleExprPortBinding`;
- whether branch-list materialization is preserved across Souffle and ProbLog;
- whether D9 section 4.9 message contract data is preserved privately without public errors yet;
- whether T3L.3-owned public SDK dispatch is still untouched.

## 10. Outcome

Implemented by `a417fe73` with Step 4.7 docstring hardening in `f1726ef3`.

### Final Landed Code

- Extended private sibling module `src/factgraph/application/protocol/rule_expr_lowering.py` from the T3L.1 substrate:
  - added private `RuleExprAdapterEngine = Literal["native", "souffle", "problog"]`;
  - widened `RuleExprEvaluationTrace.engine` from native-only to the supported materialization engines, with the post-init guard widened to the same bounded set;
  - retained `_materialize_native_derivation_plan(...)` as a compatibility wrapper over the shared adapter materialization helper;
  - added private `_materialize_adapter_derivation_plan(plan, *, engine)` for native / Souffle / ProbLog materialization shape;
  - added private `RuleExprAdapterSupport` for D9-style classifier data;
  - added private PyReason support classification helpers without changing the PyReason compiler.
- Added `tests/application/protocol/test_rule_expr_lowering_adapter.py` with focused adapter matrix tests.
- Preserved all negative-action gates:
  - no public SDK dispatch changes;
  - no SDK or protocol exports;
  - no Souffle / ProbLog / PyReason production adapter edits;
  - no public docs;
  - no public DTO / result shape changes;
  - no PyReason Form 2 grammar expansion.

### Delivered Behavior

- Souffle consumes the T3L.1 branch-list materialization shape through shipped adapter grammar:
  - one branch remains an AND body;
  - multiple branches remain OR-of-AND bodies;
  - D8 equality joins compile through shipped Souffle `eq` support.
- ProbLog consumes the same branch-list / equality materialization shape through shipped export support:
  - branch-list bodies export as multiple rule bodies;
  - D8 equality joins export through shipped equality handling;
  - shipped ProbLog adapter validation still owns adapter-time grammar rejection such as pred arity greater than 2.
- Aggregate-in-RuleExpr preservation is verified for Souffle and ProbLog without promoting aggregate-filter-local variables into D7 `RuleExprPortBinding`.
- PyReason is classifier-only in this slice:
  - pred-only lowered branches classify as supported;
  - D8 eq joins, source-rule non-pred atoms, and aggregate-containing branches classify as unsupported;
  - the classifier uses private support data for T3L.3 and does not call or expand PyReason compiler grammar.
- `_classify_pyreason_rule_expr_support(...)` is explicitly documented as inline-head only; external-head plans still raise `RuleExprError` through materialization because external head body concatenation remains deferred to T3L.3.

### Test Gates

- G7 baseline `a9ddf924`: 111 preservation tests OK before implementation.
- Feature commit `a417fe73`: 121 preservation tests OK, including 10 new adapter tests.
- Step 4.7 fix `f1726ef3`: focused adapter tests remained 10 OK; `ruff` remained clean.
- Final focused lowering coverage: 22 tests OK (12 T3L.1 lowering + 10 T3L.2 adapter).

### Deviations / Follow-Ups

- Step 4.7 found 0 P0/P1 issues.
- One WC was addressed by `f1726ef3`: the PyReason classifier inline-head dependency is now documented in the function docstring.
- No T3L.2-specific follow-up remains open.
- Deferred to T3L.3:
  - public `fg.eval.evaluate(rule_expr, head=...)` dispatch;
  - public `SDKStoreError` conversion and message formatting from private adapter support data;
  - public docs;
  - external-head body concatenation semantics.
- Deferred beyond T3 later unless separately decided: PyReason Form 2 grammar expansion.

### Lessons

- The T3L.1 wrapper pattern worked: keeping `_materialize_native_derivation_plan(...)` as a wrapper let T3L.2 add shared adapter materialization without reopening native behavior.
- Shared materialization plus per-engine classification reduced duplication while preserving the D9 matrix boundaries.
- PyReason classification can inspect the lowered WhereIR via native materialization without treating PyReason as a materialization engine.
- Strong private DTO invariants on `RuleExprAdapterSupport` catch malformed support classifications before T3L.3 exposes public error conversion.

Ready to archive after this closure commit.
