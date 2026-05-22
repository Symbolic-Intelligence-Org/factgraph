# Task Blueprint Audit: PyReason Graph-Fact Materialization Fix

- Blueprint: [2026-03-28_pyreason-graph-fact-materialization-fix.md](./2026-03-28_pyreason-graph-fact-materialization-fix.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Root cause verified from E2E experiments | Real PyReason runs showed graph attributes do not trigger rule propagation, while `add_fact(...)` does; mixed mode on the same label conflicts. |
| 2026-03-28 | scoped | Blueprint activated for implementation | Scope frozen to adapter-local graph/fact materialization only. |
| 2026-03-28 | implemented | Runner/docs/tests updated | Graph build switched to structure-only; session facts now lower to explicit `Fact(...)` registrations. Targeted PyReason adapter tests passed. |
| 2026-03-28 | archived | Blueprint archived after validation | Unit coverage passed. Real-engine smoke in the current shell remained blocked by the existing numba cache issue and was recorded as an environment limitation, not a code blocker. |

## Decision Notes

- The correct fix is not “exclude IDB predicates from graph build”. Seed facts may use the same predicate as a rule head. The stable boundary is structural graph input vs. explicit initial label facts.
- Session fact timing now maps `active_to=None` to the current run horizon (`config.timesteps`) when lowering to `Fact(...)`, which preserves the previous “present for the whole run” behavior without relying on PyReason static graph attributes.
