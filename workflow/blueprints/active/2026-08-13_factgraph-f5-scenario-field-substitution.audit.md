# Task Blueprint Audit: FactGraph F5A Scenario field substitution

- Blueprint: [`2026-08-13_factgraph-f5-scenario-field-substitution.md`](./2026-08-13_factgraph-f5-scenario-field-substitution.md)

## Event log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-13 | draft | Blueprint created | User requested autonomous completion of the implementable F5 work. |
| 2026-08-13 | scoped | Compact source audit completed | Query/native evaluator has one safe private relation-injection seam; FactOverlay and F4 bundles are rejected as public Scenario contracts. |
| 2026-08-13 | implementing | Q7 adopted and implementation started | Scope is replacement-only ScenarioFieldSubstitutionV0; Explain/capture/replay are hard non-goals. |
| 2026-08-13 | implemented | Final three-way review CLEAR | Contract, runtime and combined F4/F5 reviewers verified the focused and integrated suites. Three discovered P1s were fixed before closure: non-Query `scenario=` presence rejection, Scenario/result cross-binding, and no-provenance enforcement at both effective-relation seams. |

## Decision notes

- This is a deliberately compressed lifecycle under the user's instruction not
  to consume time on repetitive authorization/document transitions.  It does
  not claim a generic Scenario design was resolved.
- F5A must fail closed rather than infer missing/add, target navigation,
  multi-value or virtual-provenance semantics.
- This records implementation completion only. Archive remains a separate
  lifecycle action after the user's final verification of the combined F4/F5
  handoff.
