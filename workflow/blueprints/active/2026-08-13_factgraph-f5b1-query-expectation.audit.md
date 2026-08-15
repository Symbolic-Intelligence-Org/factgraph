# Task Blueprint Audit: FactGraph F5B1 Query expectation

- Blueprint: [2026-08-13_factgraph-f5b1-query-expectation.md](./2026-08-13_factgraph-f5b1-query-expectation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Blueprint created | Narrow `contains_row` observation selected rather than a generic expectation grammar. |
| 2026-08-13 | preflight | Independent source audit complete | Native stored-plan enumeration is locally complete on successful public execution; F4 summary remains identity-only and Scenario/capture require explicit rejection. |
| 2026-08-13 | scoped | Boundary frozen | Only unified targeted Query gets `contains_row`; no Query mode, generic false claim, bundle/Scenario expectation, Agent or Meander surface. |
| 2026-08-13 | implementing | Implementation started | Protocol-first addition will reuse the existing compiler and sole native evaluator. |
| 2026-08-13 | review | Independent review requested a repair | `dataclasses.replace()` could otherwise splice an expectation artifact onto a bundle or Scenario result even though normal execution rejects both combinations. |
| 2026-08-13 | implemented | Review repair and final verification complete | `EvaluateResult` now rejects that coexistence itself; bundle/Scenario regressions, 540 application+SDK tests, ruff and diff checks pass. Final independent verdict: CLEAR. |

## Decision Notes

- `complete_native_enumeration_v0` is a result-local execution basis.  It is
  not a source-truth, historical-snapshot, replay or cross-engine assertion.
- `ExpectationResultV0` binds matching existing row ids; it creates no
  negative EvidenceGraph and has no `explain()` method in this slice.
- F4 summary semantics and F5A Scenario evidence restrictions are hard
  compatibility boundaries, not deferred cleanup.
