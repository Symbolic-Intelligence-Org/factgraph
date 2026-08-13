# Task Blueprint Audit: FactGraph F5B2 Scenario field substitution set

- Blueprint: [2026-08-13_factgraph-f5b2-scenario-substitution-set.md](./2026-08-13_factgraph-f5b2-scenario-substitution-set.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- |
| 2026-08-13 | draft | Blueprint created | Multiple direct substitutions require one atomic relation, not repeated Q7 calls. |

## Decision Notes

- Q7's single-substitution wire/digest shape is preserved rather than widened.
- Q9 expectation plus all Scenario forms remains an explicit rejection.
