# Task Blueprint Audit: ProbLog Adapter Batch Fix

- Blueprint: [2026-03-29_problog-adapter-batch.md](./2026-03-29_problog-adapter-batch.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | 5 findings batched: F-PL-1~5 |
| 2026-03-29 | scoped | Scope frozen | All 5 in-scope |
| 2026-03-29 | implemented | All fixes applied | 604 tests green; 4 new tests; _parsing.py created |

## Decision Notes

- F-PL-1: deepcopy per candidate envelope (import copy at module level)
- F-PL-2: colon path already has float-match guard; add inline comment documenting rsplit safety
- F-PL-3: same pattern as F-PR-5 fix
- F-PL-4: replace raise with return 1.0 for bool-only meta.confidence
- F-PL-5: new _parsing.py with canonical _split_top_level_args
