# Task Blueprint Audit: PyReason Threshold-Aware Clause Bounds

- Blueprint: [2026-03-28_pyreason-threshold-aware-clause-bounds.md](./2026-03-28_pyreason-threshold-aware-clause-bounds.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Scope captured after real-engine reproduction showed explicit body thresholds admit bounded seeds into rule matching. |
| 2026-03-28 | scoped | Scope frozen for implementation | Limit change to engine-specific clause-bound support, warning revision, tests, and docs updates. |
| 2026-03-28 | implemented | Code and docs landed | Added `body_predicate_bounds`, updated compiler/warning behavior, and verified `513` tests green. |
| 2026-03-28 | archived | Blueprint archived | Active blueprint queue returned to decision/reference-only state. |

## Decision Notes

- Real-engine evidence now distinguishes "bounded seeds cannot propagate under current adapter-generated default thresholds" from "PyReason engine cannot use bounded seeds at all".
- The validated boundary is now: explicit clause intervals can admit bounded seeds into body matching, but current observed derived-head behavior still should not be described as interval transport.
