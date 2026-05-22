# Workflow Governance

This document is the umbrella governance for the `workflow/` directory. It defines the pillar map, the primary work mode, conflict priority, and pointers to per-pillar AGENTS files.

For the canonical methodology see [CADENCE.md](./CADENCE.md). For the high-level layout see [README.md](./README.md).

## Pillar Map

| Pillar | Purpose | State machine source |
|---|---|---|
| `foundations/` | Stable architecture principles + module docs convention | (Stable, no state machine) |
| `templates/` | Centralized document template inventory | (Static, replaced via blueprint) |
| `design/design-points/` | Conceptual design essays (iterative, non-authoritative) | `design/AGENTS.md` (TBD Phase 1.5) |
| `design/decisions/` | ADR-style decision records | `design/AGENTS.md` (TBD Phase 1.5) — ADR 4-state |
| `audit/` | Drift / anti-drift records | `audit/AGENTS.md` (TBD Phase 1.5) — 3 sub-types |
| `blueprints/` | Task-scoped implementation blueprints | `blueprints/AGENTS.md` (inherited on Phase 3 mv) — 8-state |
| `memory/` | Operational memory + session handoff archive | `memory/README.md` (light) |
| `working/` | Temporary work area | gitignored, no state machine |
| `heritage/` | Closed / legacy archive | (Append-only, no state machine) |

## Primary Work Mode

> Primary work mode for large-scope workflow, architecture, migration, and audit-first implementation work is the Audit-to-Archive Cadence. See `workflow/CADENCE.md`. Tiny local fixes may use the lightweight exception path, but must not bypass blueprint requirements when the task changes workflow, architecture, protocol, or cross-module behavior.

This is the project-canonical lock-in statement. The lightweight exception path lives in `blueprints/AGENTS.md` (after Phase 3 mv) and in the per-pillar AGENTS files where state machines define when a stage is required vs optional.

## Conflict Priority

When governance documents disagree:

1. `workflow/CADENCE.md` is authoritative for stage transitions, branch naming, verification rituals, and commit discipline.
2. Per-pillar `AGENTS.md` (when present) is authoritative for that pillar's state machine, naming convention, and structural rules.
3. `README.md` at any level is descriptive, not prescriptive — if a README contradicts AGENTS or CADENCE, the README is the one to update.
4. Repo-root `AGENTS.md` (legacy `docs/`-pointer rules) and `docs/blueprints/README.md` are being migrated; until migration completes, this `workflow/AGENTS.md` and `workflow/CADENCE.md` take precedence for any workflow concern.

## Companion Rules (Auto-memory, promotion pending)

CADENCE.md references six companion rules currently in Claude auto-memory:

- `feedback_preflight_code_audit_required.md` (preflight discipline)
- `feedback_audit_execution_discipline.md` (Rule 1 line-cite re-read + Rule 2 design strictness)
- `feedback_push_master_gate.md` (never auto-push master)
- `feedback_blueprint_workflow.md` (no plan mode, direct active/ creation)
- `feedback_milestone_branch_refs.md` (milestone refs are branches, not git tags)
- `feedback_smaller_batch_design_blueprints.md` (single-PR cadence for rule-touching blueprints)

These remain authoritative for Claude session behavior. Their canonical promotion plan is captured in `design/decisions/active/2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md` (to be written in Step 0.2 of the workflow-governance-promotion slice).

## Per-Pillar AGENTS Files

| File | Status |
|---|---|
| `blueprints/AGENTS.md` | Inherited from `docs/blueprints/AGENTS.md` on Phase 3 mv (existing 70-line 8-state machine) |
| `design/AGENTS.md` | To be authored in Phase 1.5 (ADR semantics + design-point authority boundary) |
| `audit/AGENTS.md` | To be authored in Phase 1.5 (3 sub-types + Rule 1/Rule 2 + preflight trigger conditions) |
| `memory/AGENTS.md` | Deferred — content cleanup is its own future workstream |

## Branch Naming Convention

- Audit: `v<version>-<topic>-audit-<date>`
- Decision (single-Q): `v<version>-<topic>-q<N>-decision-<date>` (multi-Q slices may consolidate on the blueprint branch — see `CADENCE.md` deviations section)
- Blueprint: `v<version>-blueprint-<topic>-<date>`
- Preflight (independent artifact): `v<version>-<topic>-preflight-<date>`
- Implementation: `v<version>-impl-<topic>-<date>`

`<version>` reflects the active release line; `<topic>` is a short slug; `<date>` is `YYYY-MM-DD`. See `CADENCE.md` for detailed branch lifecycle and exceptions.

## Sacred Branches

Per CADENCE Sacred-branch isolation rule:

- `master` is **sacred** — never auto-push, never auto-merge, never modify without explicit user authorization.
- `v0.1-oss-prep` is **sacred** — same rules apply.
- All work goes on `v<version>-<topic>-<date>` style branches.

Verify sacred state after every commit:

```
git rev-parse master   # expect unchanged hash
git status             # expect unrelated dirty unchanged
git branch --show-current  # expect non-sacred branch
```

## Scope Outside `workflow/`

The `workflow/` directory does not govern:

- Module implementation truth — that lives in `src/factgraph/*/docs/` and is governed by `src/factgraph/AGENTS.md`.
- Public-facing docs — `docs/official/kernel/` and similar.
- Security policy — `docs/SECURITY.md` and `docs/SECURITY_monorepo.md`.
- API specs — `docs/api/openapi.yaml`.

These remain in `docs/` after the workflow-governance-promotion slice. The split is intentional: `workflow/` holds governance; `docs/` holds non-workflow project content.
