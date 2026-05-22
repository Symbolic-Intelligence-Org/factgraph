# Task Blueprint Audit: Runtime Service Explain Readback

- Blueprint: [2026-03-17_runtime-service-explain-readback.md](./2026-03-17_runtime-service-explain-readback.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a dedicated service-layer child blueprint after core derivation support and core rule-trace readback were both already available. |
| 2026-03-17 | scoped | Service shape locked | Confirmed the service should follow existing runtime query conventions: `POST /queries/...`, optional `capture_trace` on `/rules/run`, `result.trace.rule_run_id` when enabled, and session-scoped/in-process limitations kept explicit. |
| 2026-03-17 | implemented | Runtime service explain endpoints landed | Added `explain-support`, `explain-rule-trace`, and `/rules/run` trace capture wiring on top of the existing core readback helpers. |
| 2026-03-17 | validated | Contract tests passed | Added a focused runtime service test covering `explain_support`, `capture_trace`, `explain_rule_trace`, and `runtime_explain_not_found`; re-ran it together with the core `run_rule_with_trace` regression under `unittest`. |

## Decision Notes

- 2026-03-17: Service explain endpoints should follow the existing runtime query style (`POST /v1/runtime/sessions/{session_id}/queries/...`) rather than introducing new GET/REST patterns mid-surface.
- 2026-03-17: `/rules/run` should gain an optional `capture_trace` flag rather than changing its default execution path; backward compatibility of the current rows-only response remains a hard constraint.
- 2026-03-17: When trace capture is enabled, the returned handle should live under `result.trace.rule_run_id` rather than being flattened into the existing result object.
- 2026-03-17: Service explain should stay session-scoped and in-process for the first slice; cross-session, cross-instance, and durable lookup remain explicit non-goals.
- 2026-03-17: Artifact misses should not be reported as generic `shape` errors; the blueprint currently prefers a dedicated explain-specific kind such as `runtime_explain_not_found`.
- 2026-03-17: The first slice should expose the two existing core readback helpers directly instead of introducing a generic explain multiplexer; keeping `explain-support` and `explain-rule-trace` separate preserves the already-distinct handle types.
