# Task Blueprint Audit: Round Story Demo Refresh

- Blueprint: [2026-05-06_round-story-demo-refresh.md](./2026-05-06_round-story-demo-refresh.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-06 | draft | Blueprint created | Initial scope recorded for canonical round story demo refresh. |
| 2026-05-06 | scoped | Scope frozen | User selected script + notebook,current examples archived under `examples/archive/`,and full round-story coverage. |
| 2026-05-06 | implemented | Canonical demo shipped | Added assertion-bearing `examples/round_story_full_demo.py`,notebook wrapper,archive README,rewritten examples README,and smoke test;verified script,focused test,ruff,diff check,and stale-link grep. |

## Decision Notes

### 2026-05-06 — Demo Shape

The Python script is the source of truth because it can be imported by tests and run as a deterministic smoke target. The notebook is a reader-facing wrapper and must not fork behavior.

### 2026-05-06 — Archive Existing Examples

All existing root examples move to `examples/archive/`. This keeps historical/sectional examples available while making the root directory unambiguous for new users.

### 2026-05-06 — Notebook Parity

The notebook imports `round_story_full_demo.py` and asserts the script's
`EXPECTED_PHASE_SUMMARY`. The Python script is therefore the only behavior
source and the notebook is presentation-only.
