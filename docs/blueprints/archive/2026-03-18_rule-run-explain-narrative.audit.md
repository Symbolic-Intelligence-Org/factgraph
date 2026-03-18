# Task Blueprint Audit: Rule-Run Explain Narrative

- Blueprint: [2026-03-18_rule-run-explain-narrative.md](./2026-03-18_rule-run-explain-narrative.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Narrative was split out as a deterministic presentation layer on top of frozen `rule_run_summary`, with audit/static proof-entry as the first-round surface. |
| 2026-03-18 | scoped | Scope frozen | Output shape is fixed to 5 presentation fields, shared renderer ownership is fixed to `core.rules._trace_narrative`, and first-round remains audit/static only with a reserved `locale=\"en\"` signature. |
| 2026-03-18 | implemented | Shared narrative renderer added | Added `core.rules._trace_narrative.render_rule_run_narrative(...)` as the canonical deterministic renderer over `rule_run_summary`. |
| 2026-03-18 | implemented | Static proof-entry page updated | `rule_traces/{rule_run_id}.html` now renders a narrative block above the existing summary/raw trace detail. |
| 2026-03-18 | implemented | Docs synced | Core and audit module docs now record the shared narrative owner and the proof-entry page behavior. |
| 2026-03-18 | verified | Test suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 63 tests, including narrative unit and static delivery assertions. |
| 2026-03-18 | archived | Blueprint archived | Code, tests, docs, and blueprint outcome were aligned; archive copy now records the implemented narrative layer. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: narrative remains deterministic and template-driven; no LLM is introduced in first round.
- 2026-03-18
  - Initial surface choice: first-round consumer surface is audit/static proof-entry, not runtime API.
- 2026-03-18
  - Initial layering direction: narrative should derive from `rule_run_summary`, not downscope into raw trace carrier fields.
- 2026-03-18
  - Adopted owner: canonical narrative rendering lives in `factpy_kernel.core.rules._trace_narrative`, not in `audit.static_ui` and not back inside `_trace.py`.
