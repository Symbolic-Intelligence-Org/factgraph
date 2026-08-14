# Task Blueprint Audit: FactGraph product interface

- Blueprint: [2026-08-14_factgraph-product-interface.md](2026-08-14_factgraph-product-interface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | draft | Blueprint created | Q20 user-locked scope recorded from the completed versus-shipped audit. |
| 2026-08-14 | preflight | Independent readback complete | PF-1 through PF-9 required amendments applied before scope anchoring. |

## Decision Notes

- The user authorized a continuous implementation and final review for this
  bounded Q20 contract. This is the explicit phase authorization required by
  CADENCE; it does not expand into Meander/Agent product authority.
- Q20 uses parallel V2 protocol values for Scenario/profile/result presentation
  rather than widening Q18 V1 sealed records.
- Deterministic portable parity and ProbLog-only probability are separate
  support matrices and must be documented/tested independently.
- PF-1 through PF-9 froze the Rule product wrapper, asset association seal,
  choice model, V2 Scenario/run/profile, product Explain and Agent bridge
  boundaries. See the standalone preflight record.
