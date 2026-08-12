# Task Blueprint Audit: FactGraph managed Policy compiler and lineage

- Status: draft
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-managed-policy-compiler-lineage.md`](./2026-08-12_factgraph-managed-policy-compiler-lineage.md)
- Outputs / Downstream:
  - (none)
- Blueprint: [`2026-08-12_factgraph-managed-policy-compiler-lineage.md`](./2026-08-12_factgraph-managed-policy-compiler-lineage.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | Blueprint created | F2B is limited to managed Policy structure, equality Unify, exact RuleExpr body reuse and total lineage. |
| 2026-08-12 | draft | Three independent implementation analyses converged | Reject-on-partial, conservative Rule admission and head-independent lineage are required; Compare is split rather than forcing a new lowering substrate. |

## Decision Notes

- Q4B is a new conservative v0 product choice; the vertical probe is supporting
  feasibility evidence, not authority for the production semantics.
- AC-21 is only partially consumed: actual projection-head collision behavior
  remains in the future Query slice because F2B creates no head.
- Final Step 4.7 review will be performed by the user's independent Agent using
  a bounded instruction packet supplied after local implementation checks.
