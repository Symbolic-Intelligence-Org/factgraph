# Task Blueprint Audit: Candidate Evidence Tree NL Explain

- Blueprint: [2026-03-20_candidate-evidence-tree-nl-explain.md](./2026-03-20_candidate-evidence-tree-nl-explain.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Tree NL explain as consumer-facing layer on top of stable candidate_evidence_tree carrier. Reuses rule_run 4-layer pattern: raw → summary → narrative → NL. |
| 2026-03-20 | draft | Scoping review | Summary narrowed to role-first core fields (deferred: node_count_by_kind, witness_predicate_ids, constraint_check_kinds). Audit NL not first-round. Integration test step added. |
| 2026-03-20 | scoped | Freeze confirmed | Three substantive freezes: (1) summary = role-first 12-field core set, 3 fields deferred; (2) delivery matrix = three channels sync to narrative, NL runtime-only first-round; (3) implementation plan requires targeted integration tests before docs. |
| 2026-03-20 | implemented | Implementation completed | Added candidate summary/narrative/NL pure helpers, extended runtime/audit/static surfaces, passed targeted unit + cross-channel integration tests, and synced module docs. |

## Decision Notes

- 2026-03-20: This slice deliberately does NOT modify the raw tree carrier (`_candidate_evidence_tree.py`), which is frozen.
- 2026-03-20: The provenance-role taxonomy (structural/witness/constraint/rule_chain/terminal/degraded) is used as the organizing principle for summary grouping and narrative sections.
- 2026-03-20: Deterministic prose only; no LLM generation.
- 2026-03-20: Engine degraded tree must produce valid (non-empty) NL output, not just skip or error.
- 2026-03-20: **Freeze: summary field set** — 12 core stable fields (role-first); `node_count_by_kind`, `witness_predicate_ids`, `constraint_check_kinds` explicitly deferred as they repeat raw tree detail or are not narrative/NL minimum dependencies.
- 2026-03-20: **Freeze: delivery matrix** — runtime delivers summary + narrative + NL; audit delivers summary + narrative only; static delivers narrative block only. Audit/static NL is not first-round scope.
- 2026-03-20: **Freeze: integration tests** — implementation plan requires targeted cross-channel integration tests (step 8) before docs update, not just unit tests on pure functions.
