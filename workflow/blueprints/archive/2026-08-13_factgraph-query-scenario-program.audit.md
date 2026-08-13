# Task Blueprint Audit: FactGraph Query/Scenario continuous delivery program

- Blueprint: [2026-08-13_factgraph-query-scenario-program.md](./2026-08-13_factgraph-query-scenario-program.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | scoped | Program scope frozen | User authorized project-level continuous delivery. Q14 is the baseline; work is grouped by semantic package rather than micro-slice lifecycle. |
| 2026-08-13 | scoped | P1 design audit complete | F4 already provides exact capture, isolated verification and detached evidence. A new sealed outer Query-run artifact is required because Q9 correctly keeps ordinary expectation and capture separate. |
| 2026-08-13 | scoped | P2 design audit complete | Existing Scenario replacement relations are Query-dependency scoped, and old Scenario digests include result diff. A future identity must be parallel/adaptive, not a silent v0 rewrite. |
| 2026-08-13 | implementing | P1 implementation entered verification | Added a separate captured Query outer artifact. Independent review found and the implementation closed two fail-closed gaps: captured expectations must match sealed selection alias/type, and the capture-only inventory cap must not narrow ordinary `evaluate()`. |
| 2026-08-13 | implementing | P1 implementation verified | Application suite 129/129, SDK suite 197/197, focused adversarial suite 7/7 and changed-file Ruff passed. A second review found the outer codec could exceed its cap after capture; build now proves codec fit before returning. |
| 2026-08-13 | implementing | Q16/P2 identity frozen | `QueryEffectiveSnapshotV1` is limited to the trusted materialized Query dependency relation. It excludes result rows and preserves Q7/Q11 public scenario/witness/digest contracts through an adapter. Two independent read-only reviews found no blocker and required explicit TOCTOU, keyset and relation-delta guards. |
| 2026-08-13 | implemented | P2 implementation and final verification complete | Added the parallel Query-dependency EffectiveSnapshot identity and routed Q7/Q11 resolvers through it without changing legacy relation-digest domain, witness labels, DTOs or ScenarioRun behavior. Final review found and closed two integrity defects before release: a self-consistent legacy DTO splice and a post-projection live-Store read. Final scope review also narrowed active-identity capture to the submitted Scenario. Application + SDK suite: 588 passed / 172 subtests; changed-file Ruff, targeted mypy and diff check passed. |

## Decision notes

- P1 preserves `EvaluationRunBundleV0` and `EvaluateResult`; it does not add
  expectations to either historical contract.
- P2 must be called a query-scoped effective snapshot, never a global ledger or
  historical snapshot.
- M0 is not part of this program until separately rebased and revalidated; its
  synthetic shadow fixture is not Meander product integration.
