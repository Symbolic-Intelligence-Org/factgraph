# Task Blueprint Audit: FactGraph Query field-navigation continuous delivery

- Blueprint: [2026-08-13_factgraph-query-field-navigation-continuous.md](./2026-08-13_factgraph-query-field-navigation-continuous.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Scope derived from Q12/Q13 boundary | Q12 intentionally deferred Query-level navigation; Q13 made the shared captured Scenario path available. |
| 2026-08-13 | preflight | Independent source audit complete | Query contract and F4 evidence audits independently confirmed the slice is feasible, but require a Query-owned DTO, a parallel run-selection DTO and an explicit lookup atom partition. |
| 2026-08-13 | scoped | Continuous-delivery scope locked | Only select-side, one-hop scalar navigation is admitted. All broader Query, Policy, Scenario, authorization and Meander surfaces remain out of scope. |

## Decision notes

- Query-owned navigation must not reuse `PolicyFieldNavigation`; their evidence
  and identity contracts differ despite structural similarity.
- The generated lookup is an inner relation. Missing source facts deliberately
  produce no row rather than a nullable value.
- F4 selection compatibility requires a parallel DTO union instead of changing
  historic direct-selection dataclasses.
