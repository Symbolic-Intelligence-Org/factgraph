# Docs Map

`docs/` should be organized by document role first, not by topic first.

The primary question for any document is:

`Is this file describing current truth, target design, execution plan, how-to usage, or historical context?`

That answer determines where the file belongs.

## Target Roles

### `reference/`

Use this for code-aligned facts that can be cited during development.

Typical contents:

- current API contracts
- current protocol DTOs
- current implementation behavior
- stable implementation references

Hard rule:

- files in `reference/` must track current code or current externally exposed contract
- behavior changes should update these docs in the same PR

### `architecture/specs/`

Use this for long-lived semantic specifications that define canonical concepts even when multiple implementations exist.

Typical contents:

- schema semantics
- assertion/evidence semantics
- view semantics
- exporter/runner semantics
- authoring contract

Hard rule:

- these are normative semantic documents, not step-by-step plans
- if implementation is incomplete, the document must say so explicitly

### `architecture/blueprints/`

Use this for target-state designs, partial designs, and migration-oriented architecture documents.

Typical contents:

- new layer boundaries
- future frontend interaction model
- partial migration blueprints
- subsystem redesign proposals

Hard rule:

- blueprints may contain `implemented`, `partial`, and `pending` sections
- they are not the default source of truth for current behavior unless they explicitly say the relevant part is implemented

### `plans/`

Use this for execution plans and staged work that is not yet complete.

Typical contents:

- phase plans
- migration checklists
- task breakdowns
- proposed rollout order

Hard rule:

- files in `plans/` are not implementation reference
- once the work is complete, either delete the plan or link it to the resulting reference/spec doc

### `guides/`

Use this for instructional material.

Typical contents:

- tutorials
- onboarding
- CLI recipes
- troubleshooting
- operations handbooks

Hard rule:

- guides explain how to use the system
- guides should not silently redefine canonical semantics

### `history/`

Use this for historical material that explains evolution but should not drive new implementation directly.

Typical contents:

- design logs
- discarded designs
- transition snapshots
- legacy docs

Hard rule:

- history is useful context, not authoritative behavior
- files here should usually carry an explicit note that they are historical

## Review Decision Order

When reviewing a document, classify it in this order:

1. Does it describe current implementation or an externally exposed current contract?
   - put it in `reference/`
2. Does it define long-lived canonical semantics across layers?
   - put it in `architecture/specs/`
3. Does it describe a target design or a partially implemented future architecture?
   - put it in `architecture/blueprints/`
4. Does it describe unfinished execution work?
   - put it in `plans/`
5. Is it primarily teaching or operational guidance?
   - put it in `guides/`
6. Is it mainly historical or superseded context?
   - put it in `history/`

## Current High-Level Layout

The primary structural migration has landed.

- `docs/reference/`
  - current reference docs, including `application/`, `core/`, `service/`, and `service/api/`
- `docs/architecture/specs/`
  - long-lived semantic specs for schema, core semantics, runtime, authoring, and SDK contracts
- `docs/architecture/blueprints/`
  - target-state application, frontend, core, and runtime design docs
- `docs/plans/`
  - execution plans and governance records
- `docs/guides/tutorials/`
  - instructional and onboarding material
- `docs/history/`
  - logs, design evolution, migrations, and legacy snapshots
- `docs/blueprint/`
  - temporary holding area for deferred draft docs that still need cleanup before promotion

The root-level role-specific docs have already moved into their role-based homes:

- `docs/reference/application/application_protocol_spec.md`
- `docs/architecture/blueprints/application/application_projection_blueprint.md`
- `docs/architecture/blueprints/frontend/frontend_entity_ui_design.md`

## Document Status Labels

Every important document should eventually state at least these fields near the top:

```md
---
doc_type: reference | spec | blueprint | plan | guide | history
status: authoritative | draft | partial | archived
source_of_truth: code | contract | design | historical
implementation_state: implemented | partial | pending | legacy
owner: <team-or-module>
last_verified: YYYY-MM-DD
---
```

Recommended interpretation:

- `authoritative`
  - default reference for current work in that scope
- `partial`
  - some sections are reliable, others are pending or need verification
- `draft`
  - design intent, not yet stable
- `archived`
  - preserved for context only

## Archive Cross-Reference Rule

When a file is archived into `history/`:

1. add a short header note pointing to the current authoritative source
2. if useful, add a backlink from the current authoritative doc to the archived file for design-evolution context
3. do not archive a file silently when the archived file and the current file still share the same subject area

Purpose:

- archived docs should remain traceable
- current docs should remain discoverable
- history should explain evolution instead of becoming a dead end

## Structural Migration Status

Completed on `2026-03-14`:

1. archived legacy SDK docs under `docs/history/legacy/sdk/`
2. moved classified root-level docs into `reference/` and `architecture/blueprints/`
3. moved classified `docs/blueprint/` docs into `reference/`, `architecture/specs/`, `architecture/blueprints/`, and `history/`
4. moved service API docs into `docs/reference/service/api/`
5. moved tutorials into `docs/guides/tutorials/`
6. moved design logs into `docs/history/logs/`

Still deferred:

- `docs/blueprint/语法.md`
  - rewrite required before promotion to `docs/architecture/specs/rules/`
- `docs/blueprint/审计.md`
  - cleanup required before promotion to `docs/architecture/blueprints/audit/`

For the detailed migration record, see [docs/plans/docs_structure_migration_checklist.md](./plans/docs_structure_migration_checklist.md).
