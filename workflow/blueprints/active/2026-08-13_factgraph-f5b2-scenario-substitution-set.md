# Task Blueprint: FactGraph F5B2 Scenario field substitution set

- Status: draft
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Related Modules:
  - `src/factgraph/application/protocol/evaluation_scenario.py`
  - `src/factgraph/application/evaluation_scenario_runtime.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - [`2026-08-13_q11-scenario-field-substitution-set-v0-decision.md`](../../design/decisions/active/2026-08-13_q11-scenario-field-substitution-set-v0-decision.md)
  - [`2026-08-13_q7-scenario-field-substitution-v0-decision.md`](../../design/decisions/active/2026-08-13_q7-scenario-field-substitution-v0-decision.md)
  - [`2026-08-13_q9-query-contains-expectation-v0-decision.md`](../../design/decisions/active/2026-08-13_q9-query-contains-expectation-v0-decision.md)
- Audit Log:
  - [`2026-08-13_factgraph-f5b2-scenario-substitution-set.audit.md`](./2026-08-13_factgraph-f5b2-scenario-substitution-set.audit.md)

## 1. Problem

The implemented Q7 form can alter only one direct scalar field.  Several
independent replacements need one shared baseline and one effective relation;
sequential Q7 calls cannot give a single atomic hypothetical result.

## 2. Goals

- Add a typed, canonical set of Q7 direct substitutions.
- Resolve all members against one dependency-complete baseline relation before
  either evaluator call, then apply all replacements to one immutable effective
  relation.
- Expose typed per-operation and set-level result metadata without changing Q7
  digest or result contracts.
- Preserve all F5A/F5B1/F4 capability exclusions and update module docs.

## 3. Non-goals

- General Scenario/What-if, premise add/delete/mask/negation, relationship or
  collection fields, entities not already visible, temporal history, Rule or
  Policy changes, source admission, Agent/Meander work.
- Expectation + Scenario, capture/bundle/anchor, close/explain/replay,
  persistence, non-native/config/premise-filter execution.

## 4. Current Context

- Q7's single resolver already projects an immutable dependency relation and
  uses the private materialized evaluator exactly twice.
- `EvaluateResult.scenario` currently admits only `ScenarioResolutionV0` and
  intentionally rejects anchors, bundles and expectations.
- F5B1 seals expectation inventory separately and rejects all Scenario input.

## 5. Proposed Shape

`ScenarioFieldSubstitutionSetV0` contains non-empty Q7 premise values.  A new
set resolver captures one baseline relation, resolves every target against it,
checks canonical uniqueness, then produces one effective relation and typed
parallel metadata.  The existing compiled Query entry invokes the same
baseline/effective evaluator pair and attaches only the set resolution to the
effective result.

## 6. Boundaries And Invariants

- Every member preserves Q7's direct active-entity, non-identity,
  single-scalar, dependency-predicate and schema-value rules.
- Resolution is all-or-nothing; no member can partially alter an effective
  relation or trigger a baseline/effective evaluation before the whole set is
  admitted.
- Canonical target duplicates and duplicate premise ids reject even when values
  are equal.  Input ordering cannot affect semantics or set identity.
- Old Q7 DTOs, `ScenarioResolutionV0` and their digest formulas remain
  unchanged.  New set metadata validates in parallel.
- Scenario retains no evidence/close/explain/anchor/bundle surface; F5B1's
  expectation-plus-Scenario rejection is preserved.

## 7. Acceptance

- [ ] Two or more direct substitutions use one baseline/effective evaluator
  pair and return the combined effective projection/diff.
- [ ] Canonical input permutations have the same set digest and effective rows.
- [ ] Invalid, duplicate, absent, ambiguous, external or type-invalid members
  fail before evaluator entry, without ledger/support/candidate side effects.
- [ ] Single Q7 substitution behavior and F5B1 expectation rejection regressions
  remain unchanged.
- [ ] Application/SDK docs describe the bounded set, no broader Scenario claim,
  and focused static/test suites pass.

## 8. Implementation Plan

1. Add parallel protocol DTOs and canonical digest/validation for a set and its
   operation/set-resolution metadata; retain Q7 forms untouched.
2. Refactor only the private resolver into a shared one-baseline/all-members
   path and expose a set resolver with atomic replacement construction.
3. Extend compiled Query Scenario admission/result validation and add focused
   protocol/runtime/SDK tests for atomicity and all excluded surfaces.
4. Update module docs, run cross-slice tests and independently review before
   closure.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

To be completed after implementation and independent review.
