# Task Blueprint Audit: FactGraph Query/Scenario continuous delivery program

- Blueprint: [2026-08-13_factgraph-query-scenario-program.md](./2026-08-13_factgraph-query-scenario-program.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | scoped | Program scope frozen | User authorized project-level continuous delivery. Q14 is the baseline; work is grouped by semantic package rather than micro-slice lifecycle. |
| 2026-08-13 | scoped | P1 design audit complete | F4 already provides exact capture, isolated verification and detached evidence. A new sealed outer Query-run artifact is required because Q9 correctly keeps ordinary expectation and capture separate. |
| 2026-08-13 | scoped | P2 design audit complete | Existing Scenario replacement relations are Query-dependency scoped, and old Scenario digests include result diff. A future identity must be parallel/adaptive, not a silent v0 rewrite. |

## Decision notes

- P1 preserves `EvaluationRunBundleV0` and `EvaluateResult`; it does not add
  expectations to either historical contract.
- P2 must be called a query-scoped effective snapshot, never a global ledger or
  historical snapshot.
- M0 is not part of this program until separately rebased and revalidated; its
  synthetic shadow fixture is not Meander product integration.

