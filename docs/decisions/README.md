# Decisions

This directory holds small decision records that close load-bearing design questions before blueprint or implementation work starts.

Decision records are not implementation blueprints. They resolve a specific question, cite the source design and shipped-code audit evidence used, and define downstream constraints for future blueprints.

Current records:

- [2026-05-20_q1-database-class-boundary-decision.md](/Users/zhenzhili/hnsm-backend/docs/decisions/2026-05-20_q1-database-class-boundary-decision.md)
  - Resolves Q1 from the DB/view audit: `Database` is a new application/storage boundary above shipped `Ledger`.
