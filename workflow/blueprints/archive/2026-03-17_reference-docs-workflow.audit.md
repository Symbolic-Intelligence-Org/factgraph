# Task Blueprint Audit: Reference Docs Workflow

- Blueprint: [2026-03-17_reference-docs-workflow.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-17_reference-docs-workflow.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Recorded the missing role for external, bridge, and working reference materials that are already being cited by active blueprints. |
| 2026-03-17 | scoped | Scope frozen | Chose `docs/references/{external,bridges,working,templates}` as the minimal durable structure and limited migration to the three currently scattered root-level files plus their links. |
| 2026-03-17 | implementing | Documentation migration started | Began writing the `docs/references/` rules, moving the three root-level files, and updating workflow/index references to the new paths. |
| 2026-03-17 | implementing | Reference rules landed | Updated `AGENTS.md`, `docs/README.md`, and `docs/blueprints/README.md` so `docs/references/` becomes a formal repository workflow role rather than a one-off cleanup. |
| 2026-03-17 | implementing | Reference files migrated | Moved the three root-level notes into categorized `docs/references/` subdirectories, added minimal metadata headers, and repaired active blueprint links. |
| 2026-03-17 | implemented | Docs workflow extension completed | Verified the new structure, confirmed the old root-level files are gone, and checked the patch with `git diff --check`. |
| 2026-03-17 | archived | Blueprint archived | Moved this completed workflow task into `docs/blueprints/archive/` as a durable example of how reference materials enter the documentation system. |

## Decision Notes

- 2026-03-17: Reference materials need a formal home, but they should remain outside the blueprint status machine and outside module-doc truth.
- 2026-03-17: `working/` references remain intentionally non-authoritative, but they still need a controlled path and explicit metadata if active blueprints are going to cite them.
