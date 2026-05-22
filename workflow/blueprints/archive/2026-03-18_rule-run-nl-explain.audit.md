# Task Blueprint Audit: Rule-Run NL Explain

- Blueprint: [2026-03-18_rule-run-nl-explain.md](./2026-03-18_rule-run-nl-explain.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | NL explain was split out as a runtime-first delivery layer above the frozen raw/summary/narrative contracts. |
| 2026-03-18 | scoped | Scope frozen | First-round NL explain keeps a dedicated runtime endpoint and freezes its DTO to `headline + paragraphs`, with drill-down guidance folded into prose rather than exposed as a separate field. |
| 2026-03-18 | implemented | Runtime NL explain landed | `core.rules._trace_nl` now owns the deterministic prose renderer and runtime exposes a dedicated `explain-nl` endpoint for `rule_run`. |
| 2026-03-18 | verified | Tests and docs synced | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 64 tests; service and core docs were updated to reflect the frozen NL explain contract. |
| 2026-03-18 | archived | Blueprint archived | Implementation matched the scoped runtime-first boundary; blueprint and audit log moved to `docs/blueprints/archive/`. |

## Decision Notes

- 2026-03-18
  - Initial scope: first-round NL explain should remain deterministic and runtime-first, not an LLM integration slice.
- 2026-03-18
  - Input boundary: NL explain should consume `rule_run_summary` and `rule_run_narrative`, not raw trace payloads or runtime-only hidden state.
- 2026-03-18
  - Delivery boundary: runtime gets the first public NL surface; audit/static parity is deferred until the runtime contract proves useful.
- 2026-03-18
  - Output narrowing: NL explain should not carry forward narrative's structured `drilldown_lines`; it freezes as a prose-only DTO (`headline`, `paragraphs`) so consumers use `explain-narrative` when they need structured drill-down affordances.
