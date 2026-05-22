# Task Blueprint Audit: ProbLog import cycle hygiene

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_problog-import-cycle-hygiene.md](./2026-05-23_problog-import-cycle-hygiene.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [2026-05-22_t2-1-ne-adapter-dispatch.audit.md](../archive/2026-05-22_t2-1-ne-adapter-dispatch.audit.md)
- Blueprint: [2026-05-23_problog-import-cycle-hygiene.md](./2026-05-23_problog-import-cycle-hygiene.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | Scope locked to import-cycle hygiene follow-up from T2.1 closure. |
| 2026-05-23 | review | Step 4.2 tightening applied | P1 narrows preferred fix to lazy `round_events` only; P2 adds precondition check; P3 tightens acceptance wording. |

## Decision Notes

### 2026-05-23 — Initial Scope Lock

- This slice is not part of the five-track rule-expression implementation plan. It is a hygiene follow-up explicitly surfaced by T2.1 closure.
- The motivating failure is `tests.test_problog_export` failing during import, before any T2.1 `ne` assertions run.
- The fix must restore the normal ProbLog test gate so T2.2 ArithExpr does not inherit the same baseline workaround.
- The implementation must not broaden into ProbLog semantics, provenance parsing, audit model, or application capability-helper behavior changes.

### 2026-05-23 — Import Chain Captured

Reproduced chain:

1. `tests/test_problog_export.py:9` imports `factgraph.adapters.problog.problog_export`.
2. `factgraph.adapters.problog.__init__` eagerly imports `engine_eval`.
3. `engine_eval` imports `provenance`.
4. `provenance` imports `factgraph.audit.evidence_graph`, triggering `factgraph.audit.__init__`.
5. `factgraph.audit.__init__` eagerly imports `round_events`.
6. `audit.round_events` imports `factgraph.application.protocol.common`, triggering `factgraph.application.__init__`.
7. `factgraph.application.__init__` eagerly imports `capability_helpers`.
8. `application.capability_helpers.round_events` imports projector functions from partially initialized `factgraph.audit.round_events`.

### 2026-05-23 — Preferred Boundary

- Preferred boundary is `factgraph.audit.__init__`: importing `factgraph.audit.evidence_graph` for ProbLog provenance should not initialize `audit.round_events`.
- Step 4.2 review narrowed this further: only the eager `round_events` import is in scope for lazy export. Other eager audit submodules remain unchanged unless implementation-time verification proves they share the same cycle path.
- Fallback boundary is `factgraph.application.__init__`: importing `application.protocol.common` should not initialize capability helpers.
- ProbLog package registration workaround is not preferred because existing tests require `get_engine_evaluator("problog") is evaluate_problog` after `import factgraph.adapters.problog`.

### 2026-05-23 — Step 4.2 Review Findings Applied

- P1 required: changed the implementation boundary from broad "cycle-heavy audit submodules" wording to the specific `audit.__init__` eager `round_events` import.
- P2 minor: added a pre-edit implementation step to verify `import factgraph.audit.evidence_graph` does not itself trigger the application/capability-helper chain.
- P3 minor: rewrote the combined ProbLog gate acceptance so any unrelated baseline failure must be documented explicitly in closure §10.

### Carry-Forward Checks For Review

- Verify the selected implementation boundary is the smallest one that breaks the cycle.
- Verify public facade identities, especially `application.build_round_event_payload`.
- Verify normal ProbLog unittest gates run without isolated module loading.
- Verify unrelated dirty files remain untouched.
