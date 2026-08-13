# Task Blueprint Audit: FactGraph D09 native absence/closure observation

- Status: scoped
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: paired blueprint audit log; records scope and evidence, but does
  not define public semantic behavior.
- Inputs:
  - [D09 native absence/closure observation blueprint](./2026-08-13_factgraph-d09-native-absence-closure-observation.md)
  - [Q17 observation decision](../../design/decisions/active/2026-08-13_q17-d09-native-absence-closure-observation-decision.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [Archived Query/Scenario program](../archive/2026-08-13_factgraph-query-scenario-program.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Observation task recorded | The task asks only what current native paths observe; it cannot turn equivalent bindings into equivalent factual states. |
| 2026-08-13 | scoped | Q17 matrix frozen | O1–O7 cover present, empty, assertion-specific removal, remaining multi-value blocker, premise filter, ordinary named negative predicate, and replacement. No standalone preflight is required because source/public scope remains zero; the continuous-delivery authority permits this lightweight scoped anchor. |

## Decision notes

- The probe is intentionally native-only. Adapter output is not evidence for
  a cross-engine absence/closure contract.
- The `not` body must stay correlated with an outer `Person:exists` binding;
  the shipped validator rejects an unbound negation body.
- A passed `not` result can only mean "no matching inner row in this evaluated
  relation". It must not be labeled a real-world negative fact or closure.
