# Task Blueprint Audit: Live Evidence URL — Runtime Permalink

- Blueprint: [2026-03-20_live-evidence-url-runtime-permalink.md](./2026-03-20_live-evidence-url-runtime-permalink.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Live evidence permalink problem scoped around runtime GET routes and static reuse. |
| 2026-03-20 | scoped | Freeze confirmed | Four positions frozen: (1) candidate_id + rule_run_id only; (2) runtime GET returns HTML directly; (3) session-bound ephemeral, not durable; (4) reuse static renderers + data shapes, not AuditQuery adapter. |

## Decision Notes

- First-round discussion is intentionally narrow: candidate/rule-run proof-entry only, not full object permalink coverage.
- The key decision boundary is delivery shape and runtime/static reuse, not proof carrier redesign.
- Rainbird comparison is used only as consumer-gap motivation; no external URL or hosting model is imported as contract.
- 2026-03-20: **Freeze: object scope** — `candidate_id` + `rule_run_id` only. assertion/run/decision deferred.
- 2026-03-20: **Freeze: delivery shape** — runtime GET route returns HTML directly. No redirect to static site.
- 2026-03-20: **Freeze: session lifecycle** — ephemeral, session-scoped permalink. Not durable. Static audit export remains the durable proof-entry surface.
- 2026-03-20: **Freeze: reuse boundary** — reuse static page renderers and existing data shapes. Runtime does NOT wrap itself as AuditQuery. Only thin data adapters if needed for specific render function inputs.
