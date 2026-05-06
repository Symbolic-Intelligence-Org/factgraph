# Task Blueprint Audit: Round Story Demo Refresh

- Blueprint: [2026-05-06_round-story-demo-refresh.md](./2026-05-06_round-story-demo-refresh.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial scope recorded for canonical round story demo refresh. |
| 2026-05-06 | scoped | Scope frozen | User selected script + notebook,current examples archived under `examples/archive/`,and full round-story coverage. |

## Decision Notes

### 2026-05-06 — Demo Shape

The Python script is the source of truth because it can be imported by tests and run as a deterministic smoke target. The notebook is a reader-facing wrapper and must not fork behavior.

### 2026-05-06 — Archive Existing Examples

All existing root examples move to `examples/archive/`. This keeps historical/sectional examples available while making the root directory unambiguous for new users.
