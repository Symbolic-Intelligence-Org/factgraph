# Task Blueprint: T3L.3 Public SDK Dispatch, Diagnostics, And Docs

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Related Modules:
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/application/protocol/rule_expr_lowering.py`
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
  - `src/factgraph/sdk/docs/00_user_guide.en.md`
  - `src/factgraph/sdk/docs/01_concepts.en.md`
  - `src/factgraph/application/docs/rule.md`
  - `tests/application/protocol/test_rule_expr_lowering.py`
  - `tests/application/protocol/test_rule_expr_lowering_adapter.py`
  - `tests/sdk/test_rule_expr_evaluate.py` (new, expected)
- Related Docs:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
- Audit Log:
  - [2026-05-25_t3l-3-public-dispatch-diagnostics-docs.audit.md](./2026-05-25_t3l-3-public-dispatch-diagnostics-docs.audit.md)

## 1. Problem

T3L.1 landed private RuleExpr lowering and native execution. T3L.2 extended the same private substrate across Souffle / ProbLog materialization and PyReason support classification. Stage 3 synthesis assigns T3L.3 to expose that completed private execution path through the public SDK, lock diagnostics, and document user-facing behavior.

Canonical drivers:

- Stage 3 synthesis section 3 assigns T3L.3 to public SDK dispatch, diagnostics, and docs.
- D6 section 4.1 locks the public target as `fg.eval.evaluate(rule_expr, head=...)`.
- D6 section 4.2 requires `head=` for application Rule / RuleExpr evaluation.
- D6 section 4.3 accepts only application protocol `Rule` / `ApplicationRule` as `head=`.
- D6 section 4.5 preserves legacy SDK `Inference` / derivation dict evaluation behavior.
- D9 section 4.9 locks public adapter preflight rejection to `SDKStoreError` and requires four message fields.
- D10 section 4.1 locks public success as existing `list[CandidateSet]`.
- D10 section 4.5 locks private trace correlation categories without public DTO export.
- T3.6 docs style requires staged imports, explicit joins, bool guards, same-name no-auto-join, and inspect return-shape boundaries to stay coherent in user docs.
- Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` T3L.3 row defines the final T3 later slice envelope.

This slice is M-class because it touches public SDK dispatch, public diagnostics, tests, and user-facing docs. It is not L-class because Stage 1 audit, D6-D10, Stage 3 synthesis, T3L.1, and T3L.2 already settled the lowering substrate, adapter matrix, public result boundary, and scope split.

M-to-L triggers:

- introducing a public result wrapper, public trace DTO, or `CandidateSet` / `SupportArtifact` / `EvidenceEnvelope` shape change;
- adding full T4 Head / closed-head behavior;
- expanding PyReason Form 2 grammar or changing adapter production grammar;
- changing legacy SDK `Inference` or derivation dict evaluation semantics;
- exporting private lowering / trace / adapter-support DTOs;
- discovering external-head body concatenation cannot be scoped without a new D6/D7/D10 decision.

If any trigger appears during Step 4.6 or implementation, pause for a blueprint amendment before code.

## 2. Goals

1. Add a public SDK dispatch path for application `Rule` and RuleExpr values in `SDKStore.evaluate(...)` / `fg.eval.evaluate(...)`.

2. Require `head=` for application `Rule` / RuleExpr inputs:
   - missing `head=` raises `SDKStoreError`;
   - `head=` must be an application protocol `Rule` / `ApplicationRule`;
   - legacy SDK `Rule`, legacy SDK `Inference`, dicts, strings, atom lists, and `RuleExprInspect` are rejected as `head=`.

3. Preserve existing evaluation behavior:
   - legacy SDK `Inference` / derivation object path remains unchanged;
   - structured derivation dict path remains unchanged;
   - direct lower-level `Store.evaluate(...)` fallback remains unchanged;
   - existing `engine=`, `semantics=`, `engine_options=`, and `registry=` semantics remain unchanged for legacy paths.

4. Evaluate RuleExpr paths through the T3L.1/T3L.2 private substrate:
   - application `Rule` inputs use D6 C35 one-rule coercion;
   - RuleExpr inputs use private `_lower_rule_expr(...)`;
   - native / Souffle / ProbLog use `_materialize_adapter_derivation_plan(...)`;
   - PyReason uses `_classify_pyreason_rule_expr_support(...)` before any adapter invocation.

5. Keep public success return shape as `list[CandidateSet]`.

6. Convert public adapter support rejections into `SDKStoreError` messages satisfying D9 section 4.9:
   - selected engine;
   - unsupported lowered atom kind or feature;
   - rejection source;
   - at least one supported alternative engine when known.

7. Preserve D10 private trace sidecar correlation internally:
   - selected candidate / invocation / runtime branch index remain correlatable during the call;
   - no public trace DTO or evidence shape is exported.

8. Document RuleExpr execution:
   - required `head=`;
   - supported engines and PyReason subset;
   - public result shape;
   - adapter preflight rejection behavior;
   - external-head limits if still constrained after implementation;
   - continued authoring rules: explicit `.eq(...)`, bool guards, same-name ports no auto-join, and inspect return-shape differences.

## 3. Non-goals

- No public `RuleExprEvaluateResult`, T5 `EvaluateResult`, or result wrapper.
- No public trace / evidence / lower-plan DTO export.
- No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shape change.
- No full T4 Head / closed-head utilities.
- No PyReason Form 2 grammar expansion.
- No Souffle / ProbLog / PyReason production adapter grammar changes unless a Step 4.6 amendment proves they are needed.
- No SDK top-level export changes unless implementation proves an import is already missing for existing T3 public authoring docs.
- No changes to RuleExpr authoring semantics, inspect behavior, equality/hash, joins, or `join_by_ports`.
- No legacy SDK `Rule` / `Inference` `head=` acceptance.
- No new public error subclass.
- No public debug/lower API.

## 4. Current Context

### 4.1 SDK evaluate dispatch surface

`src/factgraph/sdk/store.py` currently owns public `evaluate(...)` dispatch:

- top-level imports and application protocol imports at lines 1-67;
- `_SDKEvalManager.evaluate(...)` delegates directly to `SDKStore.evaluate(...)` at lines 406-434;
- `SDKStore.evaluate(...)` rejects removed kwargs and parses `registry`, `engine_options`, `engine`, and `semantics` at lines 2197-2214;
- string DSL is rejected at lines 2215-2218;
- legacy derivation-like objects using `to_authoring_payload` are lowered and evaluated at lines 2219-2235;
- structured derivation dicts are lowered and evaluated at lines 2236-2250;
- the fallback lower-level `Store.evaluate(...)` path is lines 2251-2264;
- `_evaluate_compiled_derivation_plans(...)` builds `DerivationEvaluateRequest` and returns `evaluate_derivation_plans(...)` at lines 2266-2299.

There is still no application `Rule` / RuleExpr dispatch branch.

### 4.2 Private RuleExpr lowering substrate

`src/factgraph/application/protocol/rule_expr_lowering.py` currently owns the private T3L.1/T3L.2 substrate:

- `RuleExprAdapterEngine` / `RuleExprAdapterRejectionSource` at lines 38-39;
- private lowering DTOs at lines 42-188;
- private `RuleExprAdapterSupport` at lines 191-216;
- `_lower_application_rule(...)` / `_lower_rule_expr(...)` at lines 219-228;
- `_materialize_native_derivation_plan(...)` and `_materialize_adapter_derivation_plan(...)` at lines 231-280;
- `_classify_pyreason_rule_expr_support(...)` at lines 283-306;
- native test helper `_evaluate_rule_expr_native_for_tests(...)` at lines 309-317;
- plan building, branch lowering, join materialization, endpoint resolution, and head binding at lines 320-553;
- alias-local variable rewriting and aggregate-preserving term rewriting at lines 560-653;
- PyReason classifier helper functions at lines 656-705;
- `__all__: list[str] = []` at line 731.

T3L.3 should consume and minimally extend this private module instead of exporting it.

### 4.3 Existing RuleExpr docs surface

T3.6 docs currently cover authoring and inspect:

- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:192-204` explains staged `ApplicationRule` / RuleExpr imports.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:240-258` covers `&` / `|` precedence and bool guards.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:267-300` covers explicit `.eq(...)`, `.join(...)`, `.join_by_ports(...)`, and same-name port no-auto-join.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:309-340` covers inspect return-shape differences.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:465-479` covers existing `sdk.evaluate(...)` inference behavior and engine options.
- `src/factgraph/application/docs/rule.md:71-82` covers the application RuleExpr authoring / inspect surface.

T3L.3 docs should extend this surface to execution without rewriting T3.6 authoring content.

### 4.4 Reviewed decisions and archived slices

- D6 locks public entrypoint, required `head=`, minimal application Rule head subset, and legacy evaluation preservation.
- D9 locks engine matrix and public `SDKStoreError` rejection message requirements.
- D10 locks public success result as `list[CandidateSet]` and private trace sidecar boundaries.
- T3L.1 archived at `797c93f1` with private native lowering and 111 preservation tests.
- T3L.2 archived at `9ab312b9` with adapter parity, PyReason classifier, and 121 preservation tests.

## 5. Proposed Shape

### 5.1 Public dispatch placement

Add a RuleExpr dispatch branch inside `SDKStore.evaluate(...)` before legacy derivation-like / dict / fallback paths:

- classify first positional argument as application protocol `Rule` or RuleExpr value;
- require exactly one RuleExpr positional input for the new path;
- require keyword-only `head=`;
- reject unsupported `head=` types before lowering;
- preserve all existing legacy dispatch branches.

`_SDKEvalManager.evaluate(...)` should remain a thin delegate to `SDKStore.evaluate(...)`.

Implementation should keep public dispatch small. Prefer a private helper such as `_evaluate_rule_expr_input(...)` on `SDKStore` or an internal helper in `rule_expr_lowering.py` for the actual RuleExpr materialization and evaluation.

### 5.2 RuleExpr input classification

The new path accepts:

- application protocol `Rule` / `factgraph.sdk.ApplicationRule`;
- RuleExpr values produced by application Rule composition.

The new path rejects:

- legacy SDK `Rule` and `Inference` as `head=`;
- strings;
- dicts;
- atom lists;
- `RuleExprInspect`;
- missing positional input;
- multiple RuleExpr positional inputs.

Single application `Rule` input follows D6 C35 coercion by using the private `_lower_application_rule(...)` helper.

RuleExpr input uses `_lower_rule_expr(...)`.

### 5.3 Engine and semantics handling

The RuleExpr public path should reuse the existing SDK engine / semantics resolution discipline:

- `engine=` selects native / Souffle / ProbLog / PyReason behavior just as existing `evaluate(...)` does for legacy derivations.
- `semantics=` wrappers may still derive engine when existing `_resolve_public_engine_and_semantics(...)` allows it.
- `engine_options=` is passed through only where existing evaluation machinery accepts it.
- legacy mode aliases and removed kwargs remain rejected by existing code before RuleExpr dispatch.

No new engine names are added.

### 5.4 Materialization and evaluation

For `engine in {"native", "souffle", "problog"}`:

1. Lower application Rule / RuleExpr to `RuleExprLoweringPlan`.
2. Materialize one branch-list `CompiledDerivationPlan` through `_materialize_adapter_derivation_plan(plan, engine=engine)`.
3. Evaluate through existing `evaluate_derivation_plans(...)` / `DerivationEvaluateRequest` machinery.
4. Return the existing `list[CandidateSet]` success shape.

For `engine == "pyreason"`:

1. Lower the RuleExpr input.
2. Classify support with `_classify_pyreason_rule_expr_support(...)`.
3. If unsupported, raise public `SDKStoreError` using D9 message fields.
4. If supported, materialize a branch-list plan and evaluate through existing PyReason runtime machinery.

Unexpected adapter/runtime errors after supported preflight may still surface existing adapter/core exceptions; D9 only requires public conversion for known matrix rejection before adapter invocation.

### 5.5 Head handling and external-head semantics

D6 requires `head=` to be an application protocol `Rule`.

T3L.1/T3L.2 currently defer external-head body concatenation. T3L.3 must choose one of these bounded public behaviors before feat:

- **Preferred narrow behavior**: support inline/projected heads publicly first; reject external-head body concatenation with `SDKStoreError` guidance that the head rule must be included as an occurrence in the expression for this tranche.
- **If implementation proves simple and bounded**: concatenate external head body atoms through the private lowering/materialization path without adding full T4 Head / closed-head behavior.

Either behavior must be documented in §10 Outcome and user docs. Full T4 Head / closed-head semantics remain non-goal.

### 5.6 Public diagnostics

Known public call-shape errors use `SDKStoreError`, including:

- missing `head=`;
- invalid `head=` type;
- unsupported `head=` legacy SDK objects;
- unsupported engine/grammar matrix cell;
- PyReason non-pred / eq / aggregate rejection from `RuleExprAdapterSupport`.

RuleExpr semantic/lowering errors from expression structure may continue to use `RuleExprError` when they are not SDK call-shape or adapter matrix problems.

For D9 adapter matrix rejection, `SDKStoreError` message text must include:

- selected engine;
- unsupported lowered atom kind or feature;
- rejection source;
- supported alternatives when known.

### 5.7 Private trace sidecar

T3L.3 must preserve D10 trace sidecar correlation during the public call:

- traces remain private;
- traces are not exported through SDK;
- traces are not stuffed into `CandidateSet.payload`;
- trace lifetime is at least the originating `evaluate(...)` invocation;
- selected candidate / invocation / runtime branch index remain correlatable for future T5.

If no persistent sidecar store is added in this slice, tests should still prove traces are produced and available inside the private helper boundary.

### 5.8 Docs scope

Update user-facing docs after behavior is implemented:

- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`:
  - add RuleExpr execution subsection near the RuleExpr authoring section or `sdk.evaluate(...)` section;
  - document required `head=`;
  - document supported engines and PyReason pred-only subset;
  - document public result shape as `list[CandidateSet]`;
  - document adapter preflight rejection behavior.
- `src/factgraph/sdk/docs/00_user_guide.en.md`:
  - extend the quick reference / rules section with one concise RuleExpr execution pointer.
- `src/factgraph/sdk/docs/01_concepts.en.md`:
  - update public surface table / compatibility notes for RuleExpr execution.
- `src/factgraph/application/docs/rule.md`:
  - note that public execution is through SDK `fg.eval.evaluate(expr, head=...)`, while application protocol docs remain authoring-focused.

Docs must not introduce `RuleExprEvaluateResult`, public trace DTOs, or T5 WhyNot claims.

### 5.9 Preemptive scope locks

Do not:

1. change `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` public shapes;
2. export `RuleExprLoweringPlan`, `RuleExprEvaluationTrace`, `RuleExprAdapterSupport`, or materialization helpers;
3. add SDK top-level exports for execution-specific DTOs;
4. change legacy SDK `Inference` / derivation dict evaluation behavior;
5. accept legacy SDK `Rule` / `Inference` as `head=`;
6. make `head=` optional for RuleExpr execution;
7. silently downgrade unsupported engines to another engine;
8. collapse PyReason unsupported cases into empty candidate lists;
9. expand PyReason Form 2 grammar;
10. edit adapter production files without a Step 4.6 amendment;
11. add full T4 Head / closed-head utilities;
12. mutate RuleExpr authoring / inspect semantics;
13. use public docs to promise T5 EvaluateResult / WhyNot behavior.

### 5.10 Validation layers

Layer 1: SDK public call-shape validation in `SDKStore.evaluate(...)`.

Layer 2: RuleExpr lowering validation in private `rule_expr_lowering.py` helpers.

Layer 3: adapter matrix preflight for PyReason and known unsupported public matrix cells.

Layer 4: shipped runtime / adapter validation after preflight passes.

## 6. Invariants

- Public success result remains `list[CandidateSet]`.
- Public diagnostics use `SDKStoreError` for SDK call-shape and known adapter matrix rejection.
- RuleExpr semantic/lowering errors remain `RuleExprError` unless they are being surfaced as public SDK call-shape / adapter matrix errors.
- Private trace data stays private.
- Legacy `fg.eval.evaluate(inference_or_derivation_dict, ...)` remains behaviorally unchanged.
- Application `Rule` input is equivalent to one-rule RuleExpr input.
- RuleExpr execution requires `head=`.
- Same-name ports still do not auto-join.
- PyReason is pred-only in this tranche.

## 7. Acceptance Criteria

1. G7 baseline records 121 OK before implementation using the T3L.2 final preservation gate.

2. Public `fg.eval.evaluate(expr, head=head_rule, engine="native")` returns `list[CandidateSet]` for a supported inline-head RuleExpr.

3. Public `fg.eval.evaluate(application_rule, head=head_rule, engine="native")` follows C35 one-rule coercion and returns `list[CandidateSet]`.

4. Missing `head=` raises `SDKStoreError`.

5. Invalid `head=` types and legacy SDK `Rule` / `Inference` as `head=` raise `SDKStoreError`.

6. Legacy SDK `Inference` / derivation dict evaluation tests remain green.

7. Souffle and ProbLog RuleExpr public paths pass through the T3L.2 materialization shape without adapter production edits.

8. PyReason public path:
   - accepts pred-only lowered RuleExprs when supported by shipped runtime;
   - rejects D8 eq joins / source non-pred atoms / aggregates with `SDKStoreError`.

9. D9 rejection messages include engine, unsupported feature, rejection source, and supported alternatives when known.

10. Public result tests assert no `CandidateSet` shape change and no provenance stuffing into payload.

11. Docs update the expected files and do not introduce T5 result/evidence claims.

12. Final gate includes T3.1-T3.6 + T3L.1 + T3L.2 preservation tests plus new T3L.3 focused tests and reports final OK count.

13. `ruff` passes if Python files are changed.

## 8. Implementation Plan

1. Run Step 4.6 pre-implementation greps from the paired audit log.

2. Record G7 baseline before implementation.

3. If Step 4.6 finds public dispatch collisions, external-head complexity, or adapter production write need, pause for A-fallback scope amendment.

4. Add minimal RuleExpr dispatch classification in `SDKStore.evaluate(...)`.

5. Add or extend private helper(s) to evaluate RuleExpr through T3L.1/T3L.2 materialization and existing `evaluate_derivation_plans(...)`.

6. Add public `SDKStoreError` conversion for known adapter matrix rejection, especially PyReason classifier output.

7. Decide and implement the bounded external-head behavior chosen in §5.5.

8. Add focused SDK tests, expected in `tests/sdk/test_rule_expr_evaluate.py`.

9. Update user-facing docs after behavior is in place.

10. Run focused tests, full preservation gate, and `ruff`.

11. Complete Step 4.7 review; fix P1/P2 findings before closure.

12. Close §10, transition `scoped -> implemented`, archive the blueprint pair, and consolidate memory.

## 9. Reviewer Focus

Review should pay special attention to:

- whether legacy `evaluate(...)` dispatch paths are unchanged;
- whether `head=` handling is narrow and D6-aligned;
- whether public result shape remains `list[CandidateSet]`;
- whether `SDKStoreError` messages satisfy D9's four-field contract;
- whether PyReason remains pred-only without grammar expansion;
- whether external-head behavior is explicitly bounded and documented;
- whether private trace / lowering DTOs remain private;
- whether docs avoid T5 / T4 claims.

## 10. Outcome

Pending.
