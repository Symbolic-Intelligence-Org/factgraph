# Task Blueprint Audit: Audit Rule-Run Explain Summary Export

- Blueprint: [2026-03-18_audit-rule-run-explain-summary-export.md](./2026-03-18_audit-rule-run-explain-summary-export.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Audit-side `rule_run_summary` parity was split out as a derived DTO/export slice on top of existing raw `rule_trace_artifacts.jsonl`. |
| 2026-03-18 | scoped | Scope frozen | Shared summarizer ownership is fixed to `factpy_kernel.core.rules._trace`; audit summary remains a derived surface over existing `rule_trace_artifacts.jsonl` with no new durable artifact. |
| 2026-03-18 | implemented | Shared summarizer migrated | Canonical `rule_run_summary` derivation moved into `core.rules._trace`, and `service.runtime_v1` now delegates to the shared helper. |
| 2026-03-18 | implemented | Audit summary surface added | `AuditQuery` and `audit.dto` now expose machine-readable `rule_run_summary` / summary-list surfaces derived from raw trace rows. |
| 2026-03-18 | implemented | Docs synced | `src/factpy_kernel/audit/docs/01_overview.md` now documents audit-side rule trace summaries as derived query/DTO surfaces, not new package artifacts. |
| 2026-03-18 | verified | Test suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 62 tests, including runtime/audit summary parity coverage. |
| 2026-03-18 | archived | Blueprint archived | Code, tests, docs, and blueprint outcome were aligned; archive copy now records the implemented audit summary contract. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: do not add a new audit summary artifact file; derive from existing `rule_trace_artifacts.jsonl`.
- 2026-03-18
  - Initial parity target: audit summary should match the runtime `rule_run_summary` contract rather than invent an audit-specific variant.
- 2026-03-18
  - Adopted owner: canonical `rule_run_summary` derivation moves into `factpy_kernel.core.rules._trace`, so both runtime and audit consume the same shared helper instead of duplicating grouping logic.
