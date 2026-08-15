# Task Blueprint Audit: FactGraph EvaluationQuery native execution

- Status: archived
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
| 2026-08-12 | review | Implementation and internal independent review completed | Implementation `c94c5bf9`; three reviews returned CLEAR, the full application/SDK cohort passed 458 tests plus 96 subtests, and production growth is 317/320 lines. User-side read-only review remains pending. |
| 2026-08-12 | review | User-side independent review cleared F3B | The read-only review repeated 458 tests and static checks, added 33 passing adversarial probes, and reported zero P0/P1/P2. It clarified the existing close-versus-explain stale-error envelope without finding a semantic defect. |
| 2026-08-12 | implemented | Scoped native Query execution landed | Implementation `c94c5bf9` plus current-truth documentation `9f465628`; all acceptance criteria passed without crossing the F4 boundary. |
| 2026-08-12 | archived | Blueprint pair archived | Outcome is complete; current behavior is owned by the application and SDK module docs. |

## Decision Notes

- Returning `CandidateSet` looked mechanically smaller but violates the shipped
  single-result-model direction and invites callers to rebuild rows and Explain.
- F3B therefore reuses `EvaluateResult`, but this is not F4: it captures no
  immutable evaluation bundle and makes no historical replay claim.
- Native-only execution is deliberate. Adapter parity and config ownership are
  deferred rather than inferred from shared lowering machinery.
- Candidate IDs remain evaluator-internal identities. F4 must anchor immutable
  bundles and replay to the transitive Query/result fingerprints instead.
- The pinned `factpy` environment is the verified test environment; the base
  interpreter's broad pytest startup still exits 139 and is not treated as a
  passing environment.
