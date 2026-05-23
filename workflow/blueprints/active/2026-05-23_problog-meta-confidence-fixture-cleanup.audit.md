# Task Blueprint Audit: ProbLog meta-confidence fixture cleanup

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_problog-meta-confidence-fixture-cleanup.md](./2026-05-23_problog-meta-confidence-fixture-cleanup.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [2026-05-23_problog-import-cycle-hygiene.md](../archive/2026-05-23_problog-import-cycle-hygiene.md)
  - [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md)
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
- Blueprint: [2026-05-23_problog-meta-confidence-fixture-cleanup.md](./2026-05-23_problog-meta-confidence-fixture-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | S-class hygiene slice to remove stale ProbLog `meta[confidence]` fixture inputs repeatedly acknowledged in prior closures. |

## Decision Notes

### 2026-05-23 — Initial scope lock

- This is a test-only hygiene slice.
- The source of truth is `write_protocol.py`, not a parent design essay commitment.
- The cleanup is justified by repeated closure acknowledgments in ProbLog hygiene and T2.2.
- Implementation must not relax write protocol validation or change adapter semantics.

### 2026-05-23 — G1-G7 mapping for hygiene slice

- G1: Canonical source chain is `write_protocol.py` removed-key enforcement + prior closure acknowledgments, not parent essay C-number commitments.
- G2: Blueprint §4 records shipped source reads across `write_protocol.py`, `tests/test_problog_export.py`, `tests/test_problog_engine_eval.py`, and canonical raw uncertainty tests.
- G3: Blueprint §4 uses file:line citations for all enforcement and fixture claims.
- G4: Blueprint §2 goals map to the hygiene driver: eliminate repeated closure baseline noise without design change.
- G5: Expected deviation count is zero; new unrelated baselines must be documented in §10 rather than fixed opportunistically.
- G6: Reviewer should independently verify removed fixture site completeness and `write_protocol.py` enforcement truth.
- G7: Blueprint §5.4 defines pre-impl precondition checks that must run before fixture edits.
