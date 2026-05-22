# Decision Blueprint Audit: Engine Options Runtime Dispatch v1

- Blueprint: [2026-03-27_engine-options-runtime-dispatch-decision.md](./2026-03-27_engine-options-runtime-dispatch-decision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | Opened engine_options as a future design branch after L3b closeout. Scope limited to evaluate dispatch, not implementation. |
| 2026-03-27 | scoped | 6 decisions frozen | Clarified naming drift first: mainline L4 remains ProbLog semantic-delivery parity; engine_options gets its own decision branch. Frozen decisions cover shared carrier, runtime-only boundary, adapter-owned validation, PyReason v1 option subset, `PyReasonRunConfig` boundary, and narrow implementation scope. |

## Decision Notes

- D-EO1 through D-EO6 are decision-only. No implementation files changed under `src/` in this blueprint-opening step.
- PyReason v1 shared-surface runtime subset is intentionally narrower than the current dataclass fields: only `timesteps` is both wired and user-visible.
