# Audit Log: fact-confidence-to-evidence-tree

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-21 | scoped | Blueprint created | 3 wiring breakpoints identified: assertion detail → assertion_fact node → predicate_witness_group condition_confidence. Write and consumption sides already ready. |
| 2026-03-21 | scoped | Fix: max not min | predicate_witness_group aggregation corrected to max(children) per talk.md — tree is carrier (local evidence strength), not scorer (global bottleneck). min stays in summary layer. |
| 2026-03-21 | implementing | Phase 1 start | 3 breakpoints: assertion detail → assertion_fact node → predicate_witness_group condition_confidence. |
| 2026-03-21 | implementing | Phase 1 complete | 3 wiring points fixed. 225 tests green. |
| 2026-03-21 | implementing | Phase 2 complete | 2 new tests: carrier shape + e2e propagation. 227 tests green. |
| 2026-03-21 | implemented | Phase 3 complete | Notebook updated with real confidence values. Docs known gap recorded. Blueprint archived. |
