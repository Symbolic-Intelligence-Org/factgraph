# Task Blueprint: FactGraph F5-Core unified Query target

- Status: implementing
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Related Modules:
  - `src/factgraph/application/evaluation_query_target_runtime.py`
  - `src/factgraph/application/evaluation_query_runtime.py`
  - `src/factgraph/application/evaluation_run_runtime.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/sdk/evaluation_query_builder.py`
- Related Docs:
  - [`2026-08-13_q8-unified-evaluation-query-target-v1-decision.md`](../../design/decisions/active/2026-08-13_q8-unified-evaluation-query-target-v1-decision.md)
  - [`src/factgraph/application/docs/rule.md`](../../../src/factgraph/application/docs/rule.md)
  - [`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`](../../../src/factgraph/sdk/docs/03_rules_and_inferences.en.md)
- Audit Log:
  - [`2026-08-13_factgraph-f5-core-unified-query.audit.md`](./2026-08-13_factgraph-f5-core-unified-query.audit.md)

## 1. Problem

The F3/F4/F5A chain has a sound compiled Query substrate but no public
Rule-or-Policy query entry. The missing layer is target normalization and a
thin SDK builder, not a new evaluator, new rows, or a general What-if system.

## 2. Goals

- Add resolved Rule lift and direct Policy target normalization.
- Add `fg.query(...).bind(...).select(...).compile()/evaluate()` as a thin
  facade over the existing exact compiled Query path.
- Preserve target kind in EvaluationRun anchors, including Rule lift.
- Preserve ordinary F4 and narrow F5A behavior through focused tests.

## 3. Non-goals

- `expect`, modes, completeness, limits/cursors, empty selection, navigation.
- General Scenario/Premise semantics or Scenario evidence/replay.
- Operators, external I/O, config/non-native engines, registries/Packages,
  wire APIs, Meander, Agent or Action surfaces.
- Changes to legacy `Query`, `QueryRuntimeRequest`, RuleExpr or result DTOs.

## 4. Current Context

- `CompiledEvaluationQueryV0` already seals Policy/address/schema/bind/select
  and executes through native `EvaluateResult`.
- `EvaluationRunTargetV0` already has exact `rule_lift_v0` validation but the
  current producer emits only `policy_direct_v0`.
- F5A safely accepts only `ScenarioFieldSubstitutionV0`, and explicitly blocks
  all ordinary ledger-backed evidence/replay surfaces.

## 5. Proposed Shape

1. An application runtime resolves `ResolvedRuleBundle` or `Policy +
   SemanticAddressSpace` into a sealed target context. Rule lift is one
   `target` occurrence and a reserved normalized Policy id.
2. A wrapper retains that target context alongside the pre-existing compiled
   Query. It delegates every bind/select/lowering invariant to F3A.
3. `SDKStore.query` owns fluent construction; `eval.evaluate` unwraps the
   wrapper and passes target identity only to the F4 anchor producer.
4. Scenario forwarding deliberately reuses Q7 unchanged. It does not attach
   a target-specific Scenario anchor or reuse F4 evidence.

## 6. Boundaries And Invariants

- Only structured direct `SemanticPortAddress` values are accepted.
- A bare Rule, a bare Policy, string lookup and ambient registry resolution
  fail closed.
- Rule lift must exactly contain alias `target`, one matching Rule pin, and
  `__factgraph_rule_lift__:<rule-id>` identity.
- Ordinary compiled Query identity, lowering plan, fingerprints, F4 capture,
  verification and Policy projection stay on their existing implementation.
- Scenario stays native/config-none/empty-premise-filter/replacement-only and
  must keep no anchor/bundle/support/provenance/close/live-Explain path.
- Existing SDK `Query` and application `QueryRuntimeRequest` receive no diff.

## 7. Acceptance

- [ ] Rule lift and direct Policy targets produce valid compiled Query wrappers.
- [ ] Query builder bind/select behavior matches the direct F3A compiler.
- [ ] Rule-lift ordinary execution/capture/detached Policy projection works;
  direct Policy anchor remains direct.
- [ ] Builder-forwarded F5A Scenario is equivalent to direct evaluation and
  retains every no-provenance guard.
- [ ] Invalid target/address shapes fail before the evaluator.
- [ ] Existing focused Query/F4/F5A suites and lint pass; module docs are synced.

## 8. Implementation Plan

1. Add target normalization and compiled-wrapper runtime values with exact
   validation for Rule lift and direct Policy targets.
2. Add SDK fluent builder and dispatch unwrapping; adapt only Run-anchor
   target construction where source target identity is needed.
3. Add focused application/SDK tests for positive paths, boundary rejections,
   F4 ordinary capture/evidence, and F5A Scenario preservation.
4. Update module docs, run scoped suites/static checks, and complete outcome.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

Pending implementation and verification.

## 11. Scope Freeze

Three independent read-only reviews of the F3/F4/F5A chain were completed
before this anchor. They jointly confirmed that resolved target normalization
has one existing evaluator seam, while expectation/completeness, Operator,
and Scenario evidence/replay do not. The branch therefore implements only the
contract in §§2–6; no placeholder API is added for excluded semantics.
