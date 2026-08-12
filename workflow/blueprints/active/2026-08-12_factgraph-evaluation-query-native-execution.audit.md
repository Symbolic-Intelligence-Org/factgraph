# Task Blueprint Audit: FactGraph EvaluationQuery native execution

- Status: implementing
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-evaluation-query-native-execution.md`](./2026-08-12_factgraph-evaluation-query-native-execution.md)
- Outputs / Downstream:
  - (none)
- Blueprint: [`2026-08-12_factgraph-evaluation-query-native-execution.md`](./2026-08-12_factgraph-evaluation-query-native-execution.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | F3B blueprint created | Initial question was whether execution should expose a CandidateSet bridge or an existing result envelope. |
| 2026-08-12 | scoped | Runtime, result, Explain and compatibility audits converged | CandidateSet remains internal; exact native execution returns EvaluateResult with Query anchors and unchanged-live-view guards. |
| 2026-08-12 | implementing | User authorized continuing F3B | Work is confined to the isolated F3B branch and the 320-line/no-F4 stops. |

## Decision Notes

- Returning `CandidateSet` looked mechanically smaller but violates the shipped
  single-result-model direction and invites callers to rebuild rows and Explain.
- F3B therefore reuses `EvaluateResult`, but this is not F4: it captures no
  immutable evaluation bundle and makes no historical replay claim.
- Native-only execution is deliberate. Adapter parity and config ownership are
  deferred rather than inferred from shared lowering machinery.
