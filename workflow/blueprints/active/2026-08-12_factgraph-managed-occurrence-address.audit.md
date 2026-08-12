# Task Blueprint Audit: FactGraph managed occurrence address

- Status: draft
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-managed-occurrence-address.md`](./2026-08-12_factgraph-managed-occurrence-address.md)
- Outputs / Downstream:
  - (none)
- Blueprint: [`2026-08-12_factgraph-managed-occurrence-address.md`](./2026-08-12_factgraph-managed-occurrence-address.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | Blueprint created | F2A is split from the broader F2 compiler idea so unresolved Policy semantics cannot leak into the occurrence/address substrate. |
| 2026-08-12 | draft | Independent contract review amended the draft | Required exact occurrence/contract consistency, internally derived execution refs, copy/freeze plus typed digest, value-unique aliases and distinct resolution failures. Convenience sugar was removed. |

## Decision Notes

- Q4A reuses shipped occurrence identity and F1-lite contracts.
- F2B Policy AST/compiler remains a separate decision and blueprint.
- Independent review returned AMEND with three bounded Required items; all were
  incorporated without expanding F2A into Policy or Query behavior.
