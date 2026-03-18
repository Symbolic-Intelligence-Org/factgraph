# Task Blueprint Audit: Rule-Run Explain Narrative Parity

- Blueprint: [2026-03-18_rule-run-explain-narrative-parity.md](./2026-03-18_rule-run-explain-narrative-parity.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Narrative parity was split out as a consumer-contract slice on top of the already implemented shared narrative renderer and static proof-entry behavior. |
| 2026-03-18 | scoped | Scope frozen | Runtime keeps a dedicated `explain-narrative` endpoint, audit keeps per-rule-run narrative query/DTO surfaces, and bundled `include_narrative=true` delivery is explicitly deferred. |
| 2026-03-18 | implemented | Runtime + audit narrative parity landed | Runtime now exposes `explain_runtime_narrative`, audit exposes `get_rule_trace_narrative` / DTO builders, and static UI consumes the audit narrative DTO instead of calling the renderer directly. |
| 2026-03-18 | verified | Tests and docs synced | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 63 tests; service, audit, and core docs were updated to reflect the frozen narrative contract. |
| 2026-03-18 | archived | Blueprint archived | Implementation matched scoped decisions; blueprint and audit log moved to `docs/blueprints/archive/`. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: narrative parity should promote the existing deterministic renderer into runtime/audit public surfaces, not redesign the renderer itself.
- 2026-03-18
  - Initial runtime direction: use a dedicated `explain-narrative` endpoint rather than overloading raw or summary endpoints.
- 2026-03-18
  - Initial audit direction: first-round narrative surface should be per-rule-run (`get_rule_trace_narrative` / DTO), not a new narrative index/list contract.
- 2026-03-18
  - Bundled delivery deferred: `include_narrative=true` on `explain-summary` is intentionally out of first-round scope so that narrative remains an explicit standalone contract on both runtime and audit sides.
- 2026-03-18
  - Delivery alignment: static proof-entry pages should render narrative from the audit DTO surface rather than owning a separate renderer integration path.
