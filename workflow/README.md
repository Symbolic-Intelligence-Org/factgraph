# Workflow

The `workflow/` directory holds the canonical work-mode governance for this repository: design, audit, decision, blueprint lifecycle, operational memory, and heritage archive.

## Quick Pointers

- **[AGENTS.md](./AGENTS.md)** — workflow pillar map + primary work-mode lock-in + conflict priority.
- **[CADENCE.md](./CADENCE.md)** — Audit-to-Archive Cadence (the canonical methodology for large-scope work).

## Pillar Layout

| Subdirectory | Role |
|---|---|
| `foundations/` | Stable architecture principles + module docs convention |
| `templates/` | Centralized document template inventory (blueprints + design + audit subtrees) |
| `design/` | Design-points (essays) + Decisions (ADR-style discrete records) |
| `audit/` | Drift / anti-drift records (vs-shipped / preflight / synthesis sub-types) |
| `blueprints/` | Task-scoped implementation blueprints (8-state lifecycle) |
| `memory/` | Operational memory, session continuity, handoff archive |
| `working/` | Temporary work area (gitignored) |
| `heritage/` | Closed / legacy archive |

Each pillar holds its own `README.md` (and where applicable `AGENTS.md`) describing its scope and state machine. As of the initial skeleton (2026-05-22) most subdirectories are empty placeholders; their content lands in subsequent stages of the implementing blueprint.

## Provenance

This `workflow/` structure was introduced via the workflow-governance-promotion slice on 2026-05-22. It promotes the Audit-to-Archive Cadence — previously sitting only in Claude auto-memory — into canonical, team-visible, git-tracked governance. The implementing blueprint will live at `blueprints/active/2026-05-22_workflow-governance-promotion.md` until archive completion.

Pre-existing governance documents under `docs/` (architecture principles, blueprints, decisions, audit, memory) are migrated into this tree via the same slice. See the audit doc at `audit/active/2026-05-22_workflow-governance-vs-shipped.md` for the full migration map.
