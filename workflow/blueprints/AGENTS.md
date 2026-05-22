# Blueprint Workflow

## Role

- `active/` contains live task blueprints and audit logs.
- `archive/` contains completed blueprints that still matter as rationale, plus explicitly marked reconstructed legacy archive entries.
- `templates/` contains the only approved starting points for new blueprint files.

## Required Practice

- Create both the blueprint file and the sibling audit file together.
- Use the same basename for the pair.
- Keep status in one of: `draft`, `scoped`, `implementing`, `implemented`, `blocked`, `abandoned`, `archived`, `superseded`.
- Blueprints describe problem, scope, constraints, acceptance, docs impact, and deviations.
- Audit files record decision events, scope changes, and implementation checkpoints in chronological order.
- Reconstructed legacy archive entries must use the dedicated legacy templates and must state their provenance explicitly.

## State Rules

- `draft`: exploration and open questions are still allowed.
- `scoped`: boundaries are frozen enough for implementation to begin.
- `implementing`: code generation or refactoring is in progress.
- `implemented`: code and module docs are updated; archive is still pending.
- `archived`: blueprint moved to `archive/` with final outcome recorded.
- `blocked`: stalled on an external dependency; record reason in audit, resume to `implementing` when unblocked.
- `abandoned`: explicitly cancelled; record reason in audit, move to `archive/`.
- `superseded`: replaced by a newer blueprint; record the successor link in audit, move to `archive/`.

## Valid State Transitions

Forward path:
- `draft` → `scoped` → `implementing` → `implemented` → `archived`

Allowed deviations:
- `implementing` → `scoped`: scope needs re-freezing; update blueprint and audit before resuming.
- `implementing` ↔ `blocked`: pause on external dependency; resume to `implementing` when resolved.
- any active state → `abandoned`: decision to cancel; must record reason in audit before archiving.
- any active state → `superseded`: replaced by a new blueprint; record successor link in audit before archiving.

Not allowed:
- Skipping `implementing` between `scoped` and `implemented`.
- Transitioning out of `archived` back to any active state (open a new blueprint instead).

Exception:
- A legacy reconstructed archive entry may be created directly in `archive/` only when its source document already lives in `../blueprint_history/` and the entry is explicitly marked `Archive Mode: reconstructed`.

## Archive Rules

- Do not archive until affected module docs are updated.
- Do not archive until `docs/README.md` is updated when a new durable docs entry was introduced.
- Before archiving, complete the blueprint's `Outcome / Deviations` section.
- Archive by moving both files from `active/` to `archive/` without changing the basename.

## Reconstructed Archive Rules

- Use [legacy_reconstructed_archive.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.md) and [legacy_reconstructed_archive.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.audit.md).
- Required metadata fields:
  - `Archive Mode: reconstructed`
  - `Migration Date`
  - `Git First Seen`
  - `Historical Source`
- Reconstructed entries may mirror the standard 10-section shape, but they must describe historical context honestly.
- Do not invent a fake `draft -> scoped -> implementing -> implemented` chain for the past.
- In the audit file, separate reconstructed historical notes from verified migration events.
- If current module docs or current code cannot verify an intended outcome, leave the acceptance item unchecked or explain the uncertainty in `Outcome / Deviations`.

## Legacy Boundary

- `../blueprint_history/` is not the active blueprint area.
- Legacy files may be cited as rationale, but new tasks should not be opened there.

## Templates (per Q4 §4.4)

Authoritative starting points for new blueprints live in `workflow/templates/blueprints/`:

- `task_blueprint.md` — standard task blueprint (8-state lifecycle)
- `task_blueprint.audit.md` — sibling paired audit log
- `legacy_reconstructed_archive.md` — reconstructed legacy archive
- `legacy_reconstructed_archive.audit.md` — reconstructed legacy audit log

Manual drafting (not from template) is discouraged; see `workflow/templates/README.md` §customization policy.

## Paired vs standalone audit (per Q3 §4.2)

The word "audit" in this repo refers to two distinct concepts:

- **Paired blueprint audit log** (`<basename>.audit.md` sibling, governed by this file) — per-blueprint event log of state transitions + decision notes. Authority: `paired blueprint audit log`. Lives next to the blueprint it pairs with.
- **Standalone audit record** (in `workflow/audit/`, governed by `workflow/audit/AGENTS.md`) — cross-cutting drift triage (`vs-shipped`), pre-implementation safety check (`preflight`), or post-Q re-bucketing (`synthesis`). Authority: `working triage document`.

These are NOT interchangeable. See `workflow/audit/AGENTS.md` for the standalone-audit conventions.
