# Task Blueprint: FactGraph F5B1 Query expectation

- Status: scoped
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Related Modules:
  - `src/factgraph/application/protocol/evaluation_expectation.py`
  - `src/factgraph/application/evaluation_expectation_runtime.py`
  - `src/factgraph/application/evaluation_query_target_runtime.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/sdk/evaluation_query_builder.py`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - [`2026-08-13_q9-query-contains-expectation-v0-decision.md`](../../design/decisions/active/2026-08-13_q9-query-contains-expectation-v0-decision.md)
  - [`2026-08-13_factgraph-f5-core-unified-query.md`](./2026-08-13_factgraph-f5-core-unified-query.md)
  - [`src/factgraph/application/docs/rule.md`](../../../src/factgraph/application/docs/rule.md)
  - [`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`](../../../src/factgraph/sdk/docs/03_rules_and_inferences.en.md)
- Audit Log:
  - [`2026-08-13_factgraph-f5b1-query-expectation.audit.md`](./2026-08-13_factgraph-f5b1-query-expectation.audit.md)

## 1. Problem

The unified Query facade can return typed projection rows but not state a
narrow, auditable proposition over them.  A result-level observation must not
silently become a Policy condition, a generic truth/deny result, or a claim
that F4's historical anchor captured completeness.

## 2. Goals

- Add typed `contains_row` expectation intent to `fg.query(...).expect_contains(...)`.
- Compile it through the existing exact Query context and attach outcomes after
  the sole native evaluator returns ordinary rows.
- Bind every outcome to exact Query/wrapper/result/Run-anchor identities and
  matching row ids.
- Keep native complete enumeration strictly local to that outcome.

## 3. Non-goals

- Any generic expectation grammar, exists/count/set/bag modes or altered
  `EvaluateResult.exists()` semantics.
- F4 Run-summary changes, capture/replay/codec changes, expectation Explain,
  Scenario expectation, evidence/provenance, Agent/Meander surfaces.
- New evaluator, Policy lowering/body changes, row filtering, query digest
  changes, non-native/config/premise-filter execution.

## 4. Current Context

- F5-Core emits a sealed `TargetedCompiledEvaluationQueryV0` but leaves
  expectation/completeness out of scope.
- Native Query execution uses one materialized stored plan, no public
  pagination/limit/early-stop, and rechecks the exact artifact plus live view.
- F4 anchor summary is intentionally `not_asserted/unknown/unspecified`.
- F5A Scenario deliberately cannot carry F4 anchor/bundle/evidence surfaces.

## 5. Proposed Shape

1. Define source and compiled `contains_row` expectation DTOs, canonical
   selected values, result statuses and independent integrity digests.
2. Compile expectation values against selected aliases using the existing
   schema-aware binding normalizer; extend only the targeted Query wrapper seal.
3. Evaluate outcome after ordinary native rows and Run anchor exist, then
   attach `ExpectationResultV0` values to `EvaluateResult`.
4. Reject capture and Scenario before evaluator entry whenever the wrapper has
   expectations.  Retain raw F3 Query and legacy behavior exactly.

## 6. Boundaries And Invariants

- An expectation observes rows; it does not affect Policy, Query lowering,
  row identity/order, `query_digest`, or `EvaluateResult.result_digest`.
- An input is invalid if its id is duplicated, it has no expected values, it
  names an unselected alias, or a value cannot canonically inhabit that alias.
- A runtime outcome is never used as a product verdict or an authorization.
- `not_satisfied` requires the exact result-local
  `complete_native_enumeration_v0` basis.  No match without that basis is
  `underdetermined`, never false.
- F4 summary remains `not_asserted/unknown/unspecified`; it is not reused as
  the expectation basis.
- `capture=` and `scenario=` are presence-rejected for an expected targeted
  Query.  No outcome is persisted into the current bundle or attached to a
  hypothetical Scenario result.

## 7. Acceptance

- [ ] Builder supports one or more typed `expect_contains` calls without
  changing ordinary compile/evaluate behavior when absent.
- [ ] Compiler/runtime seals reject expectation, alias, value or wrapper splice.
- [ ] Positive, complete-negative, underdetermined and unsupported pure cases
  have distinct tested statuses and diagnostic codes.
- [ ] Runtime attaches matching row references only after the one native
  evaluator completes and all live guards pass.
- [ ] F4 anchor summary, F4 capture and F5A Scenario boundaries remain intact.
- [ ] Targeted Query, raw Query, legacy result and protocol tests plus lint pass;
  application and SDK docs state the limited semantics.

## 8. Implementation Plan

1. Add protocol/runtime values and focused source-level tests for canonical
   expectation intent, pure matching and status truth table.
2. Thread compiled expectations through only the F5-Core target wrapper and
   fluent builder; add seal/splice regression tests.
3. Attach results at the native targeted-query seam, add fail-closed guards and
   SDK integration tests, then update module docs and run scoped checks.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

To be completed after implementation and independent review.
