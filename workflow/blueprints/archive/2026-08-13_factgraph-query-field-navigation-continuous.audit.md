# Task Blueprint Audit: FactGraph Query field-navigation continuous delivery

- Blueprint: [2026-08-13_factgraph-query-field-navigation-continuous.md](./2026-08-13_factgraph-query-field-navigation-continuous.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Scope derived from Q12/Q13 boundary | Q12 intentionally deferred Query-level navigation; Q13 made the shared captured Scenario path available. |
| 2026-08-13 | preflight | Independent source audit complete | Query contract and F4 evidence audits independently confirmed the slice is feasible, but require a Query-owned DTO, a parallel run-selection DTO and an explicit lookup atom partition. |
| 2026-08-13 | scoped | Continuous-delivery scope locked | Only select-side, one-hop scalar navigation is admitted. All broader Query, Policy, Scenario, authorization and Meander surfaces remain out of scope. |
| 2026-08-13 | implementing | Query-owned lowering boundary implemented | Added parallel Query/Run selection unions, branch-total lookup lowering, and an explicit trace partition so navigation never becomes a Rule-body or Policy-condition atom. |
| 2026-08-13 | implementing | F4 and Scenario propagation completed | Anchor, strict bundle codec, detached evidence, isolated verification, expectations, and captured ScenarioRun now consume the same sealed navigation intent. Live Explain requires the exact native receipt binding inventory. |
| 2026-08-13 | implemented | Concentrated regression verification complete | Focused Query tests: 36 passed; full application discovery: 129 passed; full SDK discovery: 190 passed; targeted ruff and diff check clean. |
| 2026-08-13 | implemented | Independent adversarial reviews: CLEAR | Three read-only reviews found no P0/P1. Their test-coverage recommendations were incorporated: direct-Policy navigation, identity-only authored Rule navigation, and missing-field zero-row semantics. |

## Decision notes

- Query-owned navigation must not reuse `PolicyFieldNavigation`; their evidence
  and identity contracts differ despite structural similarity.
- The generated lookup is an inner relation. Missing source facts deliberately
  produce no row rather than a nullable value.
- F4 selection compatibility requires a parallel DTO union instead of changing
  historic direct-selection dataclasses.
- The generated Query lookup is integrity-sealed but is not authentication; it
  remains inside the existing trusted in-process compiler/runtime boundary.
- Repository-wide mypy remains non-gating for this slice: a targeted invocation
  surfaced 571 pre-existing errors across 74 files. Runtime tests and ruff are
  the completed local verification gates for Q14.
