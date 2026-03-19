# Task Blueprint Audit: Blueprint Workflow Active/Archive Cleanup

- Blueprint: [2026-03-19_blueprint-workflow-active-archive-cleanup.md](./2026-03-19_blueprint-workflow-active-archive-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Recorded the active/archive cleanup problem: implemented blueprints still lived in `active/`, one decision blueprint was missing archive counterparts, and the canonical handoff still pointed at stale active paths. |
| 2026-03-19 | scoped | Scope freeze completed | Kept the slice narrow: clean `active/`, backfill missing archive files, and patch only the handoff references directly affected by the move. |
| 2026-03-19 | implemented | Cleanup landed | Implemented 2026-03-19 blueprints were removed from `active/`, the missing decision archive pair was backfilled, and the canonical handoff was refreshed to the new baseline. |
| 2026-03-19 | implemented | Archive-link repair added | A narrow follow-up fix corrected archive relative links that became invalid as an immediate side effect of moving the newly archived files. |

## Decision Notes

- 2026-03-19: This cleanup is a workflow-fidelity slice, not a module-doc or implementation slice.
- 2026-03-19: The cleanup should not trigger a mass rewrite of archive-file `Status` fields; first-round scope is limited to directory hygiene and entry references.
- 2026-03-19: The canonical handoff is in scope only because it is a live workflow entry and currently points at stale active paths.
- 2026-03-19: Broader archive-link normalization remains out of scope; only links broken by this move were repaired.
