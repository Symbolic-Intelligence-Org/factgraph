# Task Blueprint Audit: Runtime Rule-Run Explain Summary API

- Blueprint: [2026-03-18_runtime-rule-run-explain-summary-api.md](./2026-03-18_runtime-rule-run-explain-summary-api.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Summary API split out as a derived consumer-facing DTO slice on top of the frozen raw `rule_run` explain contract. |
| 2026-03-18 | scoped | Scope frozen | Endpoint shape, pure-derivation invariant, 7-field summary DTO, and flat semantic-key grouping with back-links are now fixed for implementation. |
| 2026-03-18 | implemented | Summary endpoint added | Added `POST /v1/runtime/sessions/{session_id}/queries/explain-summary`, deriving `rule_run_summary` from canonical `explain_ref(kind="rule_run")` without changing the raw carrier contract. |
| 2026-03-18 | implemented | Docs synced | Updated `src/factpy_kernel/service/docs/03_runtime_queries_views.md` to freeze the summary endpoint request/response shape and its stable derivation rules. |
| 2026-03-18 | verified | Test suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 61 tests, including direct parity and HTTP route checks for `rule_run_summary`. |
| 2026-03-18 | archived | Blueprint archived | Code, tests, docs, and blueprint outcome were aligned; archive copy now records the implemented contract. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: keep summary as a separate endpoint, not a `format=summary` switch on the raw explain endpoint.
- 2026-03-18
  - Initial invariant: summary must be a pure derivation from canonical raw `rule_run` explain payload.
- 2026-03-18
  - Adopted draft direction: summary groups use flat semantic key + minimal back-links. `predicate_witness_groups` aggregate by derived `pred_id`; `non_fact_step_groups` aggregate by `kind`; neither uses `invocation_id` as the primary grouping dimension.
