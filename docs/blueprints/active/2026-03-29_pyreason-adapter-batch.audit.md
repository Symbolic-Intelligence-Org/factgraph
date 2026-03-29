# Task Blueprint Audit: PyReason Adapter Batch Fix

- Blueprint: [2026-03-29_pyreason-adapter-batch.md](./2026-03-29_pyreason-adapter-batch.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | 5 findings batched: F-PR-2~6 |
| 2026-03-29 | scoped | Scope frozen | All 5 in-scope |
| 2026-03-29 | implemented | All fixes applied | 600 tests green; 4 new tests added; _helpers.py created |

## Decision Notes

- F-PR-3: change `0.0 <` to `0.0 <=` to align auto-derive and explicit-meta paths
- F-PR-5: build claim_key → asrt_id mapping from written, match templates by claim_key
- F-PR-6: new `_helpers.py` with canonical definitions; other modules import from it
