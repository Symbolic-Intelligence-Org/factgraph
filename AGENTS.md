# Repository Workflow

## Document Roles

- `docs/architecture_principles.md`
  - Stable project philosophy, long-term boundaries, and durable design rules.
- `docs/blueprints/active/*.md` + `*.audit.md`
  - Task-scoped blueprints and their audit trails.
- `src/factpy_kernel/*/docs/`
  - Current implementation truth for each module.
- `docs/blueprints/archive/` and `docs/blueprint_history/`
  - Archived blueprints and legacy historical material.

## Required Workflow

- For any non-trivial feature, refactor, protocol change, cross-module change, or architecture-facing task, create or reuse a task blueprint before editing code.
- Use `docs/blueprints/templates/task_blueprint.md` and `docs/blueprints/templates/task_blueprint.audit.md`.
- Keep the blueprint in `draft` while exploring. Move it to `scoped` before multi-file implementation starts.
- If implementation needs to expand or change scope, update the blueprint and audit first, then continue coding.
- After implementation, update the affected module docs under `src/factpy_kernel/*/docs/`.
- If a new module is introduced, create its `docs/README.md` in the same change.
- When adding a new durable docs entry, update `docs/README.md`.
- When code and module docs are aligned, complete the blueprint's `Outcome / Deviations` section, mark it `implemented`, then archive it.
- Historical files under `docs/blueprint_history/` may only be bridged into `docs/blueprints/archive/` as explicitly marked reconstructed archive entries.
- Reconstructed archive entries must preserve provenance (`Historical Source`, `Git First Seen`) and must not imply they actually ran through the modern active blueprint workflow.

## Exceptions

- Tiny typo fixes, comment-only edits, and clearly local test fixes may skip a blueprint.
- Even for small tasks, update module docs when public behavior or operator-facing behavior changes.

## Naming

- Active blueprint: `docs/blueprints/active/YYYY-MM-DD_slug.md`
- Audit log: `docs/blueprints/active/YYYY-MM-DD_slug.audit.md`
- Archive keeps the same basename under `docs/blueprints/archive/`

## Legacy Material

- `docs/blueprint_history/` is a legacy historical archive.
- Do not rewrite legacy blueprints into "current truth" documents.
- If a legacy blueprint is still useful, reference it as rationale and keep current behavior in module docs.
