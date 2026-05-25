# Task Blueprint: T3L.1 Internal RuleExpr Lowering And Native Execution

- Status: implemented
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/application/protocol/rule_expr_lowering.py` (new, private sibling module; expected)
  - `src/factgraph/application/protocol/derivation.py`
  - `src/factgraph/application/derivation_runtime.py`
  - `src/factgraph/core/rules/where_ast.py`
  - `src/factgraph/core/rules/where_eval.py`
  - `src/factgraph/core/store/_evaluate.py`
  - `src/factgraph/core/store/_support.py`
  - `src/factgraph/core/store/_support_capture.py`
  - `tests/application/protocol/test_rule_expr.py`
  - `tests/application/protocol/test_rule_expr_lowering.py` (new, expected)
- Related Docs:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
  - `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
  - `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
  - `workflow/blueprints/archive/2026-05-24_t3-4-join-by-ports.md`
  - `workflow/blueprints/archive/2026-05-24_t3-5-ruleexpr-inspect.md`
  - `workflow/blueprints/archive/2026-05-24_t3-6-docs-and-examples.md`
- Audit Log:
  - [2026-05-25_t3l-1-internal-lowering-native.audit.md](./2026-05-25_t3l-1-internal-lowering-native.audit.md)

## 1. Problem

T3.1-T3.6 completed the initial RuleExpr authoring, inspect, and docs cycle. The later tranche now needs execution lowering. Stage 1 audit and D6-D10 reviewed decisions split that L-class cluster into three implementation slices. T3L.1 is the first implementation slice: it builds the private lowering core and proves native execution without exposing public SDK dispatch yet.

Canonical drivers:

- Stage 3 synthesis section 3 assigns T3L.1 to internal lowering core plus native execution.
- D6 section 4.1 and section 4.4 lock the eventual public entrypoint shape and minimal application `Rule` head subset, but permit internal staging before public dispatch.
- D7 section 4.2 locks the private `RuleExprLoweringPlan` categories and D7 section 4.5-4.8 locks alias-local variables, AND cartesian product, OR branch alternatives, and deterministic branch identity.
- D8 section 4.1-4.8 locks explicit equality atom materialization and join provenance.
- D9 section 4.1 and native matrix row lock eventual branch-list materialization for the native engine.
- D10 section 4.5 locks a private trace sidecar floor and correlation/lifetime invariants.
- Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T3L.1 row defines this slice's scope envelope.

This slice is M-class because it introduces a new private lowering module, multiple internal frozen DTO categories, native runtime materialization, trace sidecar plumbing, and focused tests across RuleExpr, WhereIR, derivation runtime, and native evaluation. It is not L-class because Stage 1 audit, D6-D10 decisions, Stage 3 synthesis, and track-plan sync are already complete; this blueprint consumes those reviewed decisions and implements only the first internal/native slice.

M-to-L triggers:

- exposing public SDK dispatch in `_SDKEvalManager.evaluate(...)`;
- adding Souffle, ProbLog, or PyReason parity;
- changing public `CandidateSet`, `SupportArtifact`, or `EvidenceEnvelope` shapes;
- adding SDK exports or public result wrappers;
- introducing T4 Head / closed-head behavior;
- discovering that native execution cannot be implemented without reopening D6-D10.

If any trigger appears during Step 4.6 or implementation planning, pause and amend this blueprint before code.

## 2. Goals

1. Add a private RuleExpr lowering module, expected as `src/factgraph/application/protocol/rule_expr_lowering.py`, instead of expanding `rule_expr.py`.

2. Add private internal lowering DTO categories aligned with D7:
   - `RuleExprLoweringPlan`
   - `RuleExprLoweringBranch`
   - `RuleExprOccurrenceBinding`
   - `RuleExprPortBinding`
   - `RuleExprHeadBinding`
   - `RuleExprJoinMaterialization`
   - `RuleExprEvaluationTrace`

3. Add private lowering entry helpers for application `Rule` and RuleExpr values:
   - application `Rule` inputs follow D6 C35 one-rule coercion.
   - RuleExpr inputs consume shipped `_RuleExpr` / `_RuleOperand` / `_AndGroup` / `_OrGroup`.
   - no helper is exported from `factgraph.sdk`.

4. Implement D7 branch lowering:
   - alias-local variable namespacing before AND concatenation.
   - AND cartesian product over child branch sets.
   - OR deterministic branch alternatives.
   - stable branch ids, paths, occurrence aliases, and canonical key.

5. Implement D8 join lowering:
   - resolve endpoints through D7 port bindings.
   - check `PortType` compatibility.
   - append explicit `CmpAtom(op="eq", lhs=..., rhs=...)` join atoms after branch body atoms.
   - preserve `RuleExprJoinMaterialization` metadata including materialized atom index.

6. Implement native-only runtime materialization:
   - materialize one D9 branch-list `CompiledDerivationPlan` body for native.
   - one branch materializes as one-level AND body.
   - multiple branches materialize as two-level OR-of-AND body in D7 branch order.
   - existing native evaluator returns existing `list[CandidateSet]` values.

7. Preserve D10 private trace sidecar data for native execution:
   - trace correlates selected candidates, invocation, and runtime branch index.
   - trace lives at least until the originating internal native evaluation helper completes.
   - persistence beyond invocation is not required.

8. Add focused private tests proving:
   - lowering plan shape and invariants.
   - native branch-list materialization.
   - explicit join equality atoms.
   - aggregate-containing application rules preserve native behavior.
   - native internal execution returns existing `CandidateSet` values.

## 3. Non-goals

- No public `fg.eval.evaluate(application_rule_or_rule_expr, head=...)` dispatch.
- No `_SDKEvalManager.evaluate(...)` or `SDKStore.evaluate(...)` public branch for RuleExpr.
- No Souffle, ProbLog, or PyReason parity.
- No PyReason preflight classifier.
- No public SDK exports, no `__all__` updates, and no docs/API-surface rows.
- No public `RuleExprLoweringPlan`, trace DTO, or debug/lower helper.
- No public `RuleExprEvaluateResult`, T5 `EvaluateResult`, or result wrapper.
- No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, or `branch_atom_projection` shape changes.
- No full T4 Head / closed-head behavior.
- No legacy SDK `Rule` / `Inference` evaluation behavior changes.
- No changes to RuleExpr authoring semantics, equality/hash, join validation, `join_by_ports`, or inspect.
- No new error subclass. Use `RuleExprError` for semantic/lowering failures inside this private slice.

## 4. Current Context

### 4.1 Shipped RuleExpr authoring substrate

`src/factgraph/application/protocol/rule_expr.py` currently owns:

- `RuleExprError`, `ExplicitBoolError`, `RuleJoinConstraint`, and public `RuleExpr` at lines 12-67.
- private `_RuleExpr`, `_RuleOperand`, `_AndGroup`, and `_OrGroup` at lines 73-131.
- C35 operand coercion at lines 134-152.
- `_combine(...)`, expression-scope validation, and operand traversal at lines 155-210.
- canonical child/join helpers at lines 213-236.
- `.join_by_ports(...)` expansion at lines 239-280.
- join shape, reach, and endpoint validation at lines 283-330.

T3L.1 should read these private values from a sibling lowering module, but it must not change authoring behavior.

### 4.2 Shipped derivation runtime target

`src/factgraph/application/protocol/derivation.py` provides runtime DTOs:

- `CompiledHeadCall` at lines 21-32.
- `CompiledDerivationPlan` at lines 34-43.
- `CompiledDerivationPlan.__post_init__` enforces non-empty heads and restricts `head_spec` to single-head plans at lines 45-67.
- `DerivationEvaluateRequest` begins at lines 75-90.

`src/factgraph/application/derivation_runtime.py:69-89` evaluates a `DerivationEvaluateRequest` into a flattened `list[CandidateSet]`. Lines 100-139 call `evaluate_store(...)` once for `head_spec` or for each head.

T3L.1 materializes native execution into these shipped runtime shapes. It does not change their public fields.

### 4.3 Shipped WhereIR and join atom target

`src/factgraph/core/rules/where_ast.py` provides:

- `Var` and `Const` terms at lines 19-29.
- `PredAtom` at lines 31-35.
- `CmpAtom(op, lhs, rhs)` at lines 46-51.
- `AggregateAtom` at lines 74-79.
- `AndExpr` / `OrExpr` at lines 82-91.
- `lower_ast_to_where_ir(...)` branch-list lowering at lines 109-114.

D8 requires explicit joins to lower to comparison equality atoms, not variable unification.

### 4.4 Stage 2 decisions

- D6 locks eventual public `fg.eval.evaluate(rule_expr, head=...)`, required minimal application `Rule` `head=`, and private staging before public exposure.
- D7 locks private `RuleExprLoweringPlan` categories, alias-local namespacing, AND/OR branch model, and plan-construction `RuleExprError` bucket.
- D8 locks explicit equality atom materialization, `PortType` compatibility, canonical join order, and join materialization metadata.
- D9 locks native engine support for branch-list body, equality atoms, existing grammar, and aggregate preservation.
- D10 locks public success as existing `list[CandidateSet]` later, but T3L.1 only preserves a private trace sidecar and keeps public dispatch closed.

## 5. Proposed Shape

### 5.1 Module placement

Add a private sibling module:

- `src/factgraph/application/protocol/rule_expr_lowering.py`

This module owns private RuleExpr lowering DTOs and helpers. It may import private RuleExpr classes from `rule_expr.py`, but it must not be imported by `factgraph.sdk` public dispatch in T3L.1.

Rationale:

- `rule_expr.py` is the authoring value/validation module and should remain stable.
- T3.5 proved sibling-module isolation for DTO-heavy read-only projection.
- T3L.1 lowering is larger than inspect because it owns branch products, variable namespacing, materialization, and trace categories.

No public imports are added to `factgraph.application.protocol.__init__` or `factgraph.sdk.__init__`.

### 5.2 Private DTO contract

Use frozen internal dataclasses or equivalent immutable structures. Exact helper names may change during implementation, but the categories must remain:

```python
RuleExprLoweringPlan(
    source_kind: Literal["rule", "rule_expr"],
    head: Rule,
    head_binding: RuleExprHeadBinding,
    branches: tuple[RuleExprLoweringBranch, ...],
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
    canonical_key: tuple[object, ...],
)
```

```python
RuleExprLoweringBranch(
    branch_id: str,
    path: tuple[int, ...],
    occurrence_aliases: tuple[str, ...],
    body_atoms: tuple[object, ...],
    pending_joins: tuple[RuleJoinConstraint, ...],
)
```

```python
RuleExprOccurrenceBinding(
    alias: str,
    rule_id: str,
    content_digest: str,
    port_bindings: tuple[RuleExprPortBinding, ...],
)
```

```python
RuleExprPortBinding(
    occurrence_alias: str,
    port_name: str,
    port_type: PortType,
    source_var: Var,
    alias_local_execution_var: Var,
)
```

```python
RuleExprHeadBinding(
    kind: Literal["external", "inline"],
    head_rule_id: str,
    head_content_digest: str,
    projection_occurrence_alias: str | None,
)
```

```python
RuleExprJoinMaterialization(
    branch_id: str,
    join_key: tuple[object, ...],
    left_occurrence_alias: str,
    left_port_name: str,
    right_occurrence_alias: str,
    right_port_name: str,
    materialized_atom_index: int,
)
```

```python
RuleExprEvaluationTrace(
    canonical_key: tuple[object, ...],
    engine: Literal["native"],
    branch_id: str,
    runtime_branch_index: int,
    occurrence_aliases: tuple[str, ...],
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...],
    join_materializations: tuple[RuleExprJoinMaterialization, ...],
    head_binding: RuleExprHeadBinding,
    support_digest: str | None,
    support_kind: str | None,
)
```

Trace `support_digest` / `support_kind` may be `None` before a candidate/support link exists. T3L.1 must preserve the rest of the trace data even if native execution produces no candidates.

Concrete types such as `PortType`, `Var`, and `Rule` refine D7 section 4.2 and D10 section 4.5 conceptual `object` categories for implementation. D7/D10 still allow concrete helper names to differ as long as these data categories are preserved.

### 5.3 Private entry helpers

Add private helpers only. Candidate names:

- `_lower_application_rule(rule: Rule, *, head: Rule) -> RuleExprLoweringPlan`
- `_lower_rule_expr(expr: _RuleExpr, *, head: Rule) -> RuleExprLoweringPlan`
- `_materialize_native_derivation_plan(plan: RuleExprLoweringPlan) -> tuple[CompiledDerivationPlan, tuple[RuleExprEvaluationTrace, ...]]`
- `_evaluate_rule_expr_native_for_tests(...) -> list[CandidateSet]`

The final helper names can change, but the slice must keep this path private. T3L.3 owns public SDK dispatch.

`RuleExprEvaluationTrace` is per branch. Native materialization returns a trace tuple keyed by branch id/runtime branch index so multi-branch RuleExpr values can later correlate candidates and support artifacts to the selected branch.

### 5.4 D6 head binding in T3L.1

T3L.1 supports D6 minimal head subset internally:

- `head` must be an application protocol `Rule`.
- legacy SDK `Rule` / `Inference` are rejected if used as head values in private tests.
- full T4 Head / closed-head behavior remains out of scope.
- same id + same content digest as an inline occurrence is represented with `projection_occurrence_alias`.
- external head is represented with `projection_occurrence_alias=None`.

T3L.1 records external head binding but does not implement external head body concatenation. T3L.1 focused execution tests should use inline/projected heads or head shapes that do not require additional body concatenation. T3L.3 owns the eventual public external-head body semantics when SDK dispatch is exposed.

### 5.5 Alias-local variable namespacing

Before concatenating AND branches, lower each occurrence body into alias-local variables:

```text
("a", Var("u")) -> alias-local-var(occurrence="a", source="u")
("b", Var("u")) -> alias-local-var(occurrence="b", source="u")
```

The concrete representation is an implementation detail per D7 section 4.5. It may be a renamed `Var`, wrapper object, or another runtime-local identity. Required invariant:

- variables from distinct occurrences must not compare equal only because their private source variable names match.

Port bindings map each declared port to its alias-local execution variable. D8 join lowering must never resolve by raw source variable name alone.

### 5.6 Branch lowering

Lower each node to a branch set:

- `_RuleOperand`: one branch with alias-local body atoms, occurrence alias, and no pending joins.
- `_AndGroup`: cartesian product of child branch sets, concatenating body atoms and carrying group joins into each product branch.
- `_OrGroup`: concatenation of child branch sets as deterministic alternatives; no joins are carried through OR.

Branch identity must be deterministic:

- `branch_id` stable within a lowering plan.
- `path` records deterministic child positions.
- `occurrence_aliases` preserve branch-local occurrence order.

### 5.7 Join materialization

For each branch, materialize pending joins after body atoms:

```python
materialized_body = [
    *branch.body_atoms,
    *materialized_join_eq_atoms,
]
```

Rules:

- resolve endpoints through `RuleExprPortBinding`;
- require `source_var` and `port_type` to match the `RulePortRef`;
- require left and right `PortType` equality;
- materialize `CmpAtom(op="eq", lhs=left_alias_var, rhs=right_alias_var)`;
- normalize duplicate joins by canonical join key;
- preserve `RuleExprJoinMaterialization.materialized_atom_index` as the 0-based position in `materialized_body`.

If any invariant fails, raise `RuleExprError`.

### 5.8 Native materialization

Materialize the lowered plan for native runtime only:

- One branch becomes a one-level AND body.
- Multiple branches become a two-level OR-of-AND branch list in D7 branch order.
- Existing aggregate atoms remain in shipped native grammar.
- Existing native branch and support behavior is used; no native evaluator rewrite is planned.

T3L.1 may use `lower_ast_to_where_ir(...)` or direct WhereIR construction, but it must preserve D8 equality atoms and D9 branch-list semantics.

### 5.9 Private native execution proof

T3L.1 should include a focused internal native execution helper for tests. This helper proves that:

- a lowered application Rule / RuleExpr can materialize to `CompiledDerivationPlan`;
- native runtime returns existing `CandidateSet` rows;
- support keys keep runtime branch/atom indexing compatible with D10;
- trace sidecar can correlate at least invocation, branch id, runtime branch index, and join metadata.

This helper is not public SDK dispatch and must not be documented as user API.

### 5.10 Error policy

T3L.1 uses `RuleExprError` for:

- invalid application Rule / RuleExpr lowering inputs;
- unsupported private head shape inside this slice;
- malformed lowering plans;
- alias-local variable collisions;
- join endpoint resolution failures;
- port-type incompatibility;
- empty branch sets.

Do not introduce a new error subclass. Do not raise `SDKStoreError` from private lowering helpers unless a test intentionally routes through an SDK boundary already owned by shipped code. T3L.3 owns public SDK preflight errors.

### 5.11 Preemptive scope lock

T3L.1 applies the T3.3-T3.6 zero-deviation pattern:

- Do not change `_SDKEvalManager.evaluate(...)` public dispatch.
- Do not change `SDKStore.evaluate(...)` public dispatch.
- Do not change legacy SDK `Rule` / `Inference` evaluation behavior.
- Do not export lowering DTOs or helpers from `factgraph.sdk`.
- Do not export lowering DTOs or helpers from `factgraph.application.protocol`.
- Do not modify `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, or `CompiledDerivationPlan` public shapes.
- Do not touch Souffle, ProbLog, or PyReason adapters except Step 4.6 grep/audit notes.
- Do not add full T4 Head / closed-head behavior.
- Do not add T5 `EvaluateResult` / WhyNot public surface.
- Do not reuse `RuleExprInspect` as execution IR.
- Do not auto-join same-name ports.
- Do not alter RuleExpr equality/hash/canonicalization.
- Do not add new error subclasses.

### 5.12 Validation layers

Use four validation layers:

1. DTO layer:
   - frozen internal dataclasses;
   - tuple-normalize collection fields;
   - basic field validation for branch ids, aliases, and head binding category.

2. lowering layer:
   - validate `_RuleOperand` / `_AndGroup` / `_OrGroup` traversal;
   - validate alias-local variable uniqueness;
   - validate occurrence and port binding maps.

3. join layer:
   - validate endpoint binding presence;
   - validate source var / port type match;
   - validate join `PortType` compatibility;
   - validate canonical dedupe and materialized atom indexes.

4. native materialization layer:
   - validate non-empty branch set;
   - validate branch-list body shape;
   - validate `CompiledDerivationPlan` construction before runtime evaluation.

## 6. Invariants

- T3.1-T3.6 authoring and inspect behavior is preserved.
- Legacy SDK evaluation paths are untouched.
- Public SDK dispatch remains unchanged until T3L.3.
- Lowering DTOs and helpers remain private.
- Application Rule C35 one-rule coercion uses existing RuleExpr coercion semantics.
- Alias-local variables prevent private source var name collisions across occurrences.
- Same-name ports do not auto-join.
- Explicit joins become equality atoms, not variable unification.
- OR branches are alternatives; joins do not look through OR.
- Native branch-list order follows D7 deterministic branch order.
- Aggregate atoms remain in shipped native grammar and preserve T2.3 aggregate-local scope.
- Public result shape remains existing `list[CandidateSet]` for any private native execution proof.
- `CandidateSet`, `SupportArtifact`, and `EvidenceEnvelope` public shapes do not change.
- `RuleExprInspect` remains an inspect projection, not execution IR.
- No new public DTOs, SDK exports, or error subclasses are added.

## 7. Acceptance

- [ ] No public SDK dispatch files are touched for RuleExpr execution.
- [ ] New lowering module is private and not exported.
- [ ] Application `Rule` input lowers through one-rule RuleExpr semantics.
- [ ] RuleExpr input lowers through `_RuleExpr` traversal.
- [ ] `RuleExprLoweringPlan` carries source kind, head binding, branches, occurrence map, and canonical key.
- [ ] Occurrence bindings carry alias, rule identity, content digest, and port bindings.
- [ ] Port bindings map occurrence alias + port name to source var, port type, and alias-local execution var.
- [ ] Head binding represents external and inline/projection cases.
- [ ] Alias-local variables prevent same private variable names from becoming implicit joins.
- [ ] Single rule lowers to one branch with no pending joins.
- [ ] AND lowers by cartesian product over child branch sets.
- [ ] OR lowers to deterministic branch alternatives.
- [ ] Joins resolve through port bindings, not raw variable names.
- [ ] Join lowering enforces `PortType` compatibility.
- [ ] Explicit joins materialize to `CmpAtom(op="eq", ...)` or equivalent raw WhereIR equality atoms.
- [ ] Join equality atoms append after branch body atoms.
- [ ] Duplicate joins normalize to one equality atom.
- [ ] `RuleExprJoinMaterialization.materialized_atom_index` is the position in materialized branch body.
- [ ] Native materialization uses one-level AND for one branch and OR-of-AND for multiple branches.
- [ ] Native aggregate-containing rules preserve T2.3 behavior.
- [ ] Private native execution proof returns existing `CandidateSet` objects.
- [ ] Private trace sidecar records canonical key, engine, branch id, runtime branch index, occurrence map, join materializations, head binding, support digest, and support kind.
- [ ] Trace sidecar is correlatable with invocation and branch index and is not exported.
- [ ] Invalid lowering/head/join states raise `RuleExprError`.
- [ ] Existing T3.1-T3.6 RuleExpr tests pass.
- [ ] Existing T2.3 aggregate tests pass.
- [ ] Existing native evaluation tests pass.
- [ ] Ruff passes on touched Python files.

## 8. Implementation Plan

1. Record G7 baseline before implementation:

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

   Expected baseline from T3.6 preservation gate: 99 OK.

2. Pre-impl grep:
   - locate existing `CompiledDerivationPlan` / `DerivationEvaluateRequest` construction.
   - locate native branch-list support in `where_eval.py` and support capture.
   - locate aggregate tests and adapter exclusions.
   - confirm no existing `RuleExprLoweringPlan`, `RuleExprEvaluationTrace`, or `rule_expr_lowering` names.
   - confirm public SDK evaluate dispatch stays untouched.

3. Add `rule_expr_lowering.py` with private frozen DTOs and lowering helpers.

4. Implement C35 application Rule coercion into one-rule plan.

5. Implement `_RuleExpr` traversal and D7 branch-set lowering.

6. Implement alias-local variable rewriting for current WhereAST atom shapes.

7. Implement D8 join endpoint resolution, equality atom materialization, and join provenance.

8. Implement native branch-list materialization to `CompiledDerivationPlan`.

9. Implement private trace sidecar construction and internal native execution helper for tests.

10. Add focused tests for plan DTOs, branch semantics, alias-local variables, joins, native materialization, aggregate preservation, and trace sidecar.

11. Run focused tests and preservation tests:

    ```bash
    PYTHONPATH=src python -m unittest \
      tests.application.protocol.test_rule \
      tests.application.protocol.test_rule_expr \
      tests.application.protocol.test_rule_expr_lowering \
      tests.sdk.test_ruleexpr_inspect \
      tests.sdk.test_rule_naming \
      tests.application.protocol.test_rule_aggregate \
      tests.test_branch_identity_rule_inspect \
      -v
    ```

12. Run ruff on touched Python files:

    ```bash
    python -m ruff check \
      src/factgraph/application/protocol/rule_expr.py \
      src/factgraph/application/protocol/rule_expr_lowering.py \
      tests/application/protocol/test_rule_expr.py \
      tests/application/protocol/test_rule_expr_lowering.py
    ```

13. Confirm no public SDK export or docs file changed unless a scoped amendment authorized it first.

## 9. Docs

No user-facing docs are planned for T3L.1. Public behavior is still closed. If implementation needs internal comments, keep them local and concise.

T3L.3 owns user-facing RuleExpr execution docs.

## 10. Outcome / Deviations

Implemented in `ec8ae668` with follow-up test hardening in `ebec1136`.

### Final Landed Code

- Added private sibling module `src/factgraph/application/protocol/rule_expr_lowering.py` (613 lines).
- Added focused test module `tests/application/protocol/test_rule_expr_lowering.py` (262 lines after Step 4.7 hardening).
- Kept the implementation private:
  - no `factgraph.sdk` export;
  - no `factgraph.application.protocol` export;
  - no public `SDKStore.evaluate(...)` / `_SDKEvalManager.evaluate(...)` dispatch;
  - no adapter changes;
  - no docs changes;
  - no `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, or `CompiledDerivationPlan` shape changes.

### Delivered Behavior

- Added 7 private frozen DTOs aligned with D7/D8/D10:
  - `RuleExprLoweringPlan`
  - `RuleExprLoweringBranch`
  - `RuleExprOccurrenceBinding`
  - `RuleExprPortBinding`
  - `RuleExprHeadBinding`
  - `RuleExprJoinMaterialization`
  - `RuleExprEvaluationTrace`
- Added private helpers:
  - `_lower_application_rule(...)`
  - `_lower_rule_expr(...)`
  - `_materialize_native_derivation_plan(...)`
  - `_evaluate_rule_expr_native_for_tests(...)`
- Implemented D6 C35 single-rule coercion for private lowering.
- Implemented D7 branch model:
  - alias-local variable namespacing;
  - AND cartesian product;
  - OR branch alternatives;
  - deterministic `b{index}` branch ids.
- Implemented D8 native join lowering:
  - explicit `CmpAtom(op="eq", ...)` materialization;
  - endpoint resolution through `RuleExprPortBinding`;
  - PortType compatibility checks;
  - duplicate join dedup via canonical join key;
  - `RuleExprJoinMaterialization` provenance metadata.
- Implemented D9 native-only materialization:
  - single branch lowers to one native body;
  - multi-branch RuleExpr lowers to branch-list body shape;
  - aggregate atoms remain in shipped native grammar.
- Implemented D10 private trace sidecar floor:
  - per-branch `RuleExprEvaluationTrace` tuple;
  - runtime branch index and branch id correlation;
  - head binding and join materialization metadata preserved.
- Explicitly deferred external head body concatenation to T3L.3.

### Test Gates

- G7 baseline before implementation: 99 tests OK.
- Focused T3L.1 tests after feature commit: 9 tests OK.
- Preservation gate after feature commit: 108 tests OK.
- Step 4.7 hardening added 3 test methods covering:
  - incompatible PortType joins;
  - duplicate join dedup;
  - critical DTO shape invariants.
- Final focused T3L.1 tests: 12 tests OK.
- Final preservation gate:

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

  Result: 111 tests OK.

- Ruff:

  ```bash
  PYTHONPATH=src python -m ruff check \
    src/factgraph/application/protocol/rule_expr_lowering.py \
    tests/application/protocol/test_rule_expr_lowering.py
  ```

  Result: all checks passed.

### Deviations / Follow-Ups

No P0/P1 deviations.

Step 4.7 review found 3 worth-considering test coverage gaps and 2 minor style nits:

| Finding | Disposition |
|---|---|
| WC1 PortType incompatibility negative test | Addressed in `ebec1136`. |
| WC2 duplicate join dedup test | Addressed in `ebec1136`. |
| WC3 DTO invariant negative tests | Addressed in `ebec1136`. |
| N1 `_resolve_endpoint` uses defensive `getattr(...)` | Skipped as style-only; no behavior risk. |
| N2 temporary empty `branch_id` placeholder before assignment | Skipped as style-only; existing invariant remains explicit in `_assign_branch_ids(...)`. |

No T3L.1-specific follow-up blocks T3L.2.

Deferred by scope:

- public `fg.eval.evaluate(rule_expr, head=...)` dispatch remains T3L.3;
- Souffle / ProbLog / PyReason parity remains T3L.2;
- public docs remain T3L.3;
- external head body concatenation public semantics remain T3L.3;
- T4 Head and T5 EvaluateResult / WhyNot remain out of scope.

### Lessons

- T3.5 sibling-module isolation pattern carried forward cleanly: `rule_expr_lowering.py` absorbed the new private projection layer without touching shipped `rule_expr.py` authoring behavior.
- The first T3 later implementation slice benefited from a Step 4.7 fix commit: the feature substrate was sound at 108 OK, and the extra 61 lines of tests raised the gate to 111 OK while keeping implementation untouched.
- D6-D10 reviewed decisions were sufficient as implementation contracts: no substrate amendment was needed during feat implementation.
- The v2 blueprint clarifications landed accurately:
  - native materialization returns a per-branch trace tuple;
  - external head body concatenation is explicitly deferred to T3L.3.

### Archive Readiness

Ready to archive after this closure commit.
