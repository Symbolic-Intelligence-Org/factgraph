# Audit Pillar

Drift / anti-drift records: design-doc-vs-shipped triage, pre-implementation safety checks, and post-Q re-bucketing syntheses.

See [`AGENTS.md`](./AGENTS.md) for the full governance — including the **two distinct "audit" concepts** (standalone audit record here vs paired blueprint audit log in `workflow/blueprints/`), the 3 sub-type taxonomy, preflight + synthesis trigger conditions, and cross-branch visibility rules. Governance was locked by Q3 (commit `ae375ce5`).

## Three sub-types

| Sub-type | Filename | Purpose |
|---|---|---|
| `vs-shipped` | `YYYY-MM-DD_<topic>-vs-shipped.md` | Stage 1 drift triage (design doc vs shipped code) |
| `preflight` | `YYYY-MM-DD_<topic>-preflight.md` | Step 4.3 safety check before scoped anchor |
| `synthesis` | `YYYY-MM-DD_post-q-<topic>-synthesis.md` | Stage 3 post-Q re-bucketing |

## Lifecycle

`active/` while the consuming blueprint is in `workflow/blueprints/active/`; moves to `archive/` in the same commit batch as the blueprint's Step 4.9 archive.

## Templates

`workflow/templates/audit/{vs-shipped,preflight,synthesis}.md`.
