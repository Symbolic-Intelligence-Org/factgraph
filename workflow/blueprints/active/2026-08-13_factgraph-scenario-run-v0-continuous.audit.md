# Task Blueprint Audit: FactGraph ScenarioRun v0 continuous delivery

- Blueprint: [`2026-08-13_factgraph-scenario-run-v0-continuous.md`](./2026-08-13_factgraph-scenario-run-v0-continuous.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Scope reconstructed from Q7/Q11/F4 | Existing Scenario fast path is retained; it is not promoted by implication. |
| 2026-08-13 | scoped | User authorized project-level continuous delivery | One bounded ScenarioRun lifecycle is allowed; non-goals remain hard stops. |
| 2026-08-13 | implementing | Core receipt-capture seam selected | Capture stays ephemeral and cannot write Store support state. |

## Decision Notes

- Avoid treating two ordinary `EvaluationRunBundleV0` values as the public
  Scenario contract.  Their capture primitives are reused privately behind a
  Scenario-specific seal and source relabeling adapter.
- The implementation is deliberately compressed under the user's direction;
  checks are concentrated at semantic boundaries rather than repeated per file.
