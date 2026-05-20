# Decisions

This directory holds small decision records that close load-bearing design questions before blueprint or implementation work starts.

Decision records are not implementation blueprints. They resolve a specific question, cite the source design and shipped-code audit evidence used, and define downstream constraints for future blueprints.

Current records:

- [2026-05-20_q1-database-class-boundary-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q1-database-class-boundary-decision.md)
  - Resolves Q1 from the DB/view audit: `Database` is a new application/storage boundary above shipped `Ledger`.
- [2026-05-20_q3-tx-identity-primitives-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md)
  - Resolves Q3 from the DB/view audit: dedicated Database identity protocols for `tx_id`, `data_digest`, and assertion digest envelope.
- [2026-05-20_q8-savedrule-existence-governance-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md)
  - Resolves Q8 from the DB/view audit: gradual deprecation of the shipped SavedRule / `FileAuthoringRegistry` rule+inference persistence layer (option (c)); schema persistence stays out of scope per A16(B) / A20(E).
