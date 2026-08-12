# Task Blueprint Audit: FactGraph EvaluationQuery projection

- Status: scoped
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-evaluation-query-projection.md`](./2026-08-12_factgraph-evaluation-query-projection.md)
- Outputs / Downstream:
  - (none)
- Blueprint: [`2026-08-12_factgraph-evaluation-query-projection.md`](./2026-08-12_factgraph-evaluation-query-projection.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | F3A blueprint created | Scope is exact Policy bind/select lowering only. |
| 2026-08-12 | scoped | Runtime and compatibility audits converged | Old Query cannot be redefined; explicit per-branch links and later reuse of existing EvaluateResult are required. |
| 2026-08-12 | implementing | User authorized the next isolated item | Implementation may proceed inside the 550-line and no-execution stops. |

## Decision Notes

- The larger unified Query remains a hypothesis. F3A proves only one narrow
  seam: Policy-owned typed bindings and explicit projections can share the
  shipped RuleExpr lowering substrate.
- Lazy Explain is not implemented here. The explicit mapping is nevertheless
  wired into probe seed discovery now so a later execution slice cannot fall
  back to unqualified port-name inference.
