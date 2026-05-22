# Workflow Governance

This document is the umbrella governance for the `workflow/` directory. It defines the pillar map, the primary work mode, conflict priority, and pointers to per-pillar AGENTS files.

For the canonical methodology see [CADENCE.md](./CADENCE.md). For the high-level layout see [README.md](./README.md).

## Pillar Map

| Pillar | Purpose | State machine source |
|---|---|---|
| `foundations/` | Stable architecture principles + module docs convention | (Stable, no state machine) |
| `templates/` | Centralized document template inventory | (Static, replaced via blueprint) |
| `design/design-points/` | Conceptual design essays (iterative, non-authoritative) | [`design/README.md`](./design/README.md) — 3-condition archive |
| `design/decisions/` | ADR-style decision records | [`design/README.md`](./design/README.md) — ADR 4-state |
| `audit/` | Drift / anti-drift records | [`audit/README.md`](./audit/README.md) — 3 sub-types |
| `blueprints/` | Task-scoped implementation blueprints | [`blueprints/README.md`](./blueprints/README.md) — 8-state |
| `memory/` | Operational memory + session handoff archive | [`memory/README.md`](./memory/README.md) (light) |
| `working/` | Temporary work area | gitignored, no state machine |
| `heritage/` | Closed / legacy archive | (Append-only, no state machine) |

## Primary Work Mode

> Primary work mode for large-scope workflow, architecture, migration, and audit-first implementation work is the Audit-to-Archive Cadence. See `workflow/CADENCE.md`. Tiny local fixes may use the lightweight exception path, but must not bypass blueprint requirements when the task changes workflow, architecture, protocol, or cross-module behavior.

This is the project-canonical lock-in statement. The lightweight exception path lives in [`blueprints/README.md`](./blueprints/README.md) §可以跳过蓝图的情况 + §State Rules, and in the per-pillar README files where state machines define when a stage is required vs optional.

## Conflict Priority

When governance documents disagree:

1. [`workflow/CADENCE.md`](./CADENCE.md) is authoritative for stage transitions, branch naming, verification rituals, and commit discipline.
2. This `workflow/AGENTS.md` (umbrella) is authoritative for the pillar map, primary work mode lock-in, conflict priority itself, and cross-pillar concerns.
3. Per-pillar `README.md` (one per pillar: blueprints / design / audit / memory / foundations / heritage / templates / working) is authoritative for that pillar's state machine, naming convention, and structural rules. (Phase 1.5 / SC-1 merge folded the pillar AGENTS.md content into these READMEs.)
4. Repo-root `/AGENTS.md` (legacy) is being updated to point at this `workflow/AGENTS.md` as canonical workflow entry; until that update completes, `workflow/AGENTS.md` + `workflow/CADENCE.md` take precedence for any workflow concern.

## Companion Rules (Auto-memory, promotion pending)

CADENCE.md references six companion rules currently in Claude auto-memory:

- `feedback_preflight_code_audit_required.md` (preflight discipline)
- `feedback_audit_execution_discipline.md` (Rule 1 line-cite re-read + Rule 2 design strictness)
- `feedback_push_master_gate.md` (never auto-push master)
- `feedback_blueprint_workflow.md` (no plan mode, direct active/ creation)
- `feedback_milestone_branch_refs.md` (milestone refs are branches, not git tags)
- `feedback_smaller_batch_design_blueprints.md` (single-PR cadence for rule-touching blueprints)

These remain authoritative for Claude session behavior. Their canonical promotion plan is captured in `design/decisions/active/2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md` (to be written in Step 0.2 of the workflow-governance-promotion slice).

## Per-Pillar Governance Files

Per-pillar state machines and structural rules live in each pillar's `README.md`. There are no per-pillar `AGENTS.md` files — the original Phase 1.5 plan called for them, but the SC-1 merge folded their content into the pillar READMEs to reduce file proliferation (the umbrella `AGENTS.md` you are reading stays separate to host the project-canonical lock-in + conflict priority + cross-pillar concerns).

| Pillar | Governance file |
|---|---|
| `blueprints/` | [`blueprints/README.md`](./blueprints/README.md) — 8-state machine + paired audit log convention |
| `design/` | [`design/README.md`](./design/README.md) — design-points 3-condition archive + decisions ADR 4-state |
| `audit/` | [`audit/README.md`](./audit/README.md) — 3 sub-types + preflight/synthesis triggers + cross-branch visibility |
| `foundations/` | [`foundations/README.md`](./foundations/README.md) — light (stable content) |
| `templates/` | [`templates/README.md`](./templates/README.md) — 9-template inventory + 7-field schema + customization policy |
| `memory/` | [`memory/README.md`](./memory/README.md) — light; content cleanup is its own future workstream |
| `working/` | [`working/README.md`](./working/README.md) — gitignored temp area conventions |
| `heritage/` | [`heritage/README.md`](./heritage/README.md) — append-only legacy archive |

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
