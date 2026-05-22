# Repository Workflow

Thin entry pointer. Canonical governance lives in dedicated files; this file routes you there.

## Canonical Sources

| Concern | Authoritative file |
|---|---|
| **Workflow governance** (cadence, pillar map, lock-in, conflict priority, branch naming, sacred branches) | [`workflow/AGENTS.md`](workflow/AGENTS.md) |
| **Methodology** (9-stage Audit-to-Archive Cadence for large-scope audit-first work) | [`workflow/CADENCE.md`](workflow/CADENCE.md) |
| **Module docs convention** (`src/factgraph/*/docs/README.md` minimum structure) | [`src/factgraph/AGENTS.md`](src/factgraph/AGENTS.md) + [`workflow/foundations/module_docs_convention.md`](workflow/foundations/module_docs_convention.md) |
| **Architecture principles** (stable design philosophy, layer authority, release surface governance) | [`workflow/foundations/architecture_principles.md`](workflow/foundations/architecture_principles.md) |

## Document Roles

- [`workflow/foundations/`](workflow/foundations/) — Stable architecture principles + module docs convention.
- [`workflow/design/`](workflow/design/) — Design-points (conceptual essays) + decisions (ADR-style discrete records).
- [`workflow/audit/`](workflow/audit/) — Drift / anti-drift records (`vs-shipped` / `preflight` / `synthesis` sub-types).
- [`workflow/blueprints/active/`](workflow/blueprints/active/) — Live task blueprints and paired audit logs.
- [`workflow/blueprints/archive/`](workflow/blueprints/archive/) — Archived blueprints + reconstructed legacy archive entries. See `INVENTORY.md` for the date-sorted index.
- [`workflow/memory/`](workflow/memory/) — Operational memory, session continuity, and handoff archives; **not** current implementation truth.
- [`workflow/heritage/blueprint_history/`](workflow/heritage/blueprint_history/) — Legacy historical material (pre-modern-workflow blueprints).
- `src/factgraph/*/docs/` — **Current implementation truth** for each module.
- [`docs/`](docs/) — Non-workflow content only: `SECURITY.md`, `api/openapi.yaml`, `official/kernel/` (public quickstart docs).

## Required Workflow

For any non-trivial feature, refactor, protocol change, cross-module change, or architecture-facing task, **create or reuse a task blueprint before editing code**.

- Use templates from [`workflow/templates/blueprints/`](workflow/templates/blueprints/).
- Keep the blueprint in `draft` while exploring; move it to `scoped` before multi-file implementation starts.
- If scope expands or changes, update the blueprint and its sibling audit first, then continue coding.
- Cite reference material from the active blueprint and record adopted conclusions in the audit log.
- After implementation, update affected module docs under `src/factgraph/*/docs/`.
- When adding a new durable docs entry, update [`docs/README.md`](docs/README.md).
- When code and module docs are aligned, complete the blueprint's `Outcome / Deviations`, mark it `implemented`, then archive it.

For the full 8-state lifecycle, transition rules, and reconstructed archive conventions see [`workflow/blueprints/README.md`](workflow/blueprints/README.md). For the 9-stage cadence for large-scope work see [`workflow/CADENCE.md`](workflow/CADENCE.md).

## Exceptions

- Tiny typo fixes, comment-only edits, and clearly local test fixes may skip a blueprint.
- Even for small tasks, update module docs when public behavior or operator-facing behavior changes.

## Naming

- Active blueprint: `workflow/blueprints/active/YYYY-MM-DD_slug.md`
- Paired audit log: `workflow/blueprints/active/YYYY-MM-DD_slug.audit.md`
- Archive keeps the same basename under `workflow/blueprints/archive/`.

## Legacy Material

- [`workflow/heritage/blueprint_history/`](workflow/heritage/blueprint_history/) is a legacy historical archive.
- Do not rewrite legacy blueprints into "current truth" documents.
- If a legacy blueprint is still useful, reference it as rationale and keep current behavior in module docs.
- Reconstructed archive entries must preserve provenance (`Archive Mode: reconstructed`, `Historical Source`, `Git First Seen`, `Migration Date`) per [`workflow/blueprints/README.md`](workflow/blueprints/README.md) §Reconstructed 归档规则.
