# Task Blueprint: FactGraph ScenarioRun v0 continuous delivery

- Status: implementing
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Branch: `codex/v0.3.0-factgraph-whatif-v1-continuous-2026-08-13`
- Related Modules:
  - `src/factgraph/core/store/_evaluate.py`
  - `src/factgraph/application/{derivation_runtime,evaluation_scenario_runtime,scenario_run_runtime}.py`
  - `src/factgraph/application/protocol/scenario_run.py`
  - `src/factgraph/sdk/{store,evaluation_query_builder}.py`
- Related Decision: [`Q13`](../../design/decisions/active/2026-08-13_q13-scenario-run-v0-decision.md)
- Audit Log: [`paired audit`](./2026-08-13_factgraph-scenario-run-v0-continuous.audit.md)

## 1. Problem

Q7/Q11 safely resolve a replacement-only hypothetical but intentionally stop
before evidence, capture, detached inspection and verification.  That makes
them unsuitable as the auditable What-if bridge envisaged by the FactGraph /
Meander design.

## 2. Goals

- Deliver one complete, bounded `ScenarioRunV0` lifecycle for Q7/Q11.
- Reuse the native Query compiler, F4 capture, EvidenceGraph, Policy projection
  and isolated verifier without changing their ordinary public contracts.
- Preserve clear provenance: a synthetic premise witness is never a ledger fact.

## 3. Non-goals

- General What-if/world synthesis, Policy overlay, source authority, Agent Plan,
  Meander integration, operators/actions, non-native parity or broad UI work.

## 4. Proposed Shape

`ScenarioRunV0` owns two private captured sides (baseline/effective), a sealed
plan/premise inventory and a result-multiset diff.  It offers detached evidence
and verification through Scenario-aware adapters.  The ordinary `EvaluateResult`
Scenario route remains non-captured and unchanged.

## 5. Boundaries And Invariants

- Q7/Q11 admission rules are the only premise grammar.
- Two evaluations consume the exact same materialized native plan and a frozen,
  dependency-complete relation per side.
- Receipt capture is ephemeral; Store support sidecars/backrefs remain unchanged.
- No live Store read after capture for `explain`, `diff`, `verify`, codec decode.
- All public source labels distinguish baseline relation, effective relation and
  Scenario hypothesis.  No F4 `captured_witness` label may escape unmodified.

## 6. Acceptance

- [ ] Protocol seal/codec rejects malformed or hybrid ScenarioRun payloads.
- [ ] SDK entry works for Rule and direct Policy targets.
- [ ] Same-value, zero-result, multi-premise and stale-view cases are covered.
- [ ] Detached Explain/Policy projection and isolated verification are covered.
- [ ] Existing scenario fast path and F3–F5 regression cohorts remain green.
- [ ] Application/SDK docs describe only shipped v0 semantics.

## 7. Implementation Plan

1. Add private ephemeral receipt capture to the effective-relation evaluator.
2. Add ScenarioRun DTO/runtime, sealing and bounded codec.
3. Integrate SDK/query-builder entrypoints and Scenario-aware detached evidence.
4. Add focused attack/regression tests and module docs.
5. Run concentrated and integrated checks, then an independent final review.

## 8. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/protocol/docs/README.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 9. Outcome / Deviations

Pending continuous implementation and final review.
