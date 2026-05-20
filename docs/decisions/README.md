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
- [2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md)
  - Resolves Q7 from the DB/view audit: canonical Database-owned durable assertion record with shipped storage/application/SDK adapters.
- [2026-05-20_q2-attach-lifecycle-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q2-attach-lifecycle-decision.md)
  - Resolves Q2 from the DB/view audit: `FactGraph.attach(...)` is a new class-method-style constructor distinct from shipped constructors;`attach(db)` is writable against current head, while snapshot/view-scoped forms are read-only;no `rules=` per A15-D.
- [2026-05-20_q4-frozenassertionview-shape-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md)
  - Resolves Q4 from the DB/view audit: design-target `FrozenAssertionView` keeps the existing name and upgrades to the anchored 6-field shape; shipped 2-field views become compatibility artifacts.
- [2026-05-20_q5-view-revocation-composition-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q5-view-revocation-composition-decision.md)
  - Resolves Q5 from the DB/view audit: View-replaces-active (option (b));`view=` specified scope universe is exactly `view.asrt_ids` with no `is_active` re-filter;`view=` omitted preserves shipped active-only universe;post-scope projection and evidence annotation are separate work.
