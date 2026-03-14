# Status Header Rollout

## Goal

Add document status headers in a controlled order so high-visibility and high-confusion docs are labeled first.

This file is the rollout checklist and metadata record for the first pass.

Headers were applied on `2026-03-14`. The paths below reflect the current live locations after the structural migration.

## Rollout Order

### Phase 1: P0

Status: completed on `2026-03-14`

Highest-visibility or highest-confusion docs.

- `docs/reference/` and `docs/architecture/specs/` files that are easy to misread as “current implementation” without a header
- high-visibility entry docs now living under `docs/reference/` and `docs/architecture/blueprints/`

### Phase 2: P1

Status: completed on `2026-03-14`

Current service contract docs and remaining important spec-adjacent files.

### Phase 3: P2

Guides and execution docs.

- `docs/guides/tutorials/`
- `docs/plans/`

## Header Schema

Use this shape:

```yaml
---
doc_type: reference | spec | blueprint | plan | guide | history
status: authoritative | draft | partial | archived
source_of_truth: code | contract | design | historical
implementation_state: implemented | partial | pending | legacy
owner: <team-or-module>
last_verified: 2026-03-14
---
```

Rollout conventions:

- `owner` uses module/domain names for now
- `last_verified` is the review date for this cleanup pass
- `partial` means “contains trustworthy content, but not all sections should be read as fully current”
- for `partial` docs, add one short prose note after the header if the scope boundary needs to be explicit

## Phase 1: P0 Targets

| Path | Proposed Header | Notes |
| --- | --- | --- |
| `docs/reference/application/application_protocol_spec.md` | `doc_type: reference` `status: partial` `source_of_truth: contract` `implementation_state: implemented` `owner: application/protocol` `last_verified: 2026-03-14` | Phase 0 contract is implemented, but the document is intentionally not the full application protocol surface |
| `docs/architecture/blueprints/application/application_projection_blueprint.md` | `doc_type: blueprint` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: application` `last_verified: 2026-03-14` | Contains both completed and pending sections |
| `docs/architecture/blueprints/frontend/frontend_entity_ui_design.md` | `doc_type: blueprint` `status: draft` `source_of_truth: design` `implementation_state: pending` `owner: frontend` `last_verified: 2026-03-14` | Design intent, not current frontend implementation reference |
| `docs/reference/core/candidate_protocol_v2.md` | `doc_type: reference` `status: authoritative` `source_of_truth: code` `implementation_state: implemented` `owner: core/derivation` `last_verified: 2026-03-14` | Title already says current implementation spec |
| `docs/reference/service/service.md` | `doc_type: reference` `status: authoritative` `source_of_truth: contract` `implementation_state: implemented` `owner: service` `last_verified: 2026-03-14` | Current service v1 boundary/reference doc |
| `docs/architecture/specs/schema/规范.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: core/schema` `last_verified: 2026-03-14` | Canonical schema semantics, but should be labeled conservatively until fully re-verified |
| `docs/architecture/specs/core/断言层 证据层.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: core/evidence` `last_verified: 2026-03-14` | Normative semantics with likely mixed implementation maturity |
| `docs/architecture/specs/core/视图层.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: core/view` `last_verified: 2026-03-14` | Canonical view semantics, but should not imply every section is fully code-verified |
| `docs/architecture/specs/authoring/Authoring 层契约.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: authoring` `last_verified: 2026-03-14` | Important contract doc, but broader than fully verified current behavior |

## Phase 2: P1 Targets

| Path | Proposed Header | Notes |
| --- | --- | --- |
| `docs/architecture/specs/runtime/导出与运行.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: runtime/export` `last_verified: 2026-03-14` | Normative target semantics; verify exact current package/export surface over time |
| `docs/architecture/specs/authoring/Authoring 层契约 fixtures.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: authoring` `last_verified: 2026-03-14` | Fixture bank is useful, but includes historical fixture content |
| `docs/architecture/specs/sdk/sdk_accept_ingest_provenance_spec.md` | `doc_type: spec` `status: partial` `source_of_truth: design` `implementation_state: partial` `owner: sdk` `last_verified: 2026-03-14` | Good candidate for metadata labeling before deeper content tightening |
| `docs/reference/service/api/README.md` | `doc_type: reference` `status: authoritative` `source_of_truth: contract` `implementation_state: implemented` `owner: service/api` `last_verified: 2026-03-14` | Current service API index |
| `docs/reference/service/api/runtime-session.md` | `doc_type: reference` `status: authoritative` `source_of_truth: contract` `implementation_state: implemented` `owner: service/runtime` `last_verified: 2026-03-14` | Current session/write contract |
| `docs/reference/service/api/runtime-queries.md` | `doc_type: reference` `status: authoritative` `source_of_truth: contract` `implementation_state: implemented` `owner: service/runtime` `last_verified: 2026-03-14` | Current runtime query/derivation/query DTO contract |
| `docs/reference/service/api/rules-registry.md` | `doc_type: reference` `status: authoritative` `source_of_truth: contract` `implementation_state: implemented` `owner: service/rules-registry` `last_verified: 2026-03-14` | Current rules/registry DTO contract |

## Phase 3: P2 Backlog

These do not need immediate metadata labeling to reduce the current confusion risk, but should be covered later:

- `docs/guides/tutorials/*`
  - default target: `doc_type: guide`
- `docs/plans/*`
  - default target: `doc_type: plan`

For history files, add headers when they are actually moved or actively touched, rather than bulk-editing them immediately.

## Proposed Execution Rule

When applying headers:

1. do not change document body semantics in the same patch unless the header would otherwise be misleading
2. if a document is `partial`, add a one-sentence note after the header clarifying the trustworthy scope
3. if a document is `draft` or `archived`, make that explicit before the main title
4. update this checklist after each completed batch

## Exit Criteria

Phase 1 is complete when:

- all P0 targets have headers
- no high-visibility entry doc remains unlabeled
- no high-visibility `docs/reference/` or `docs/architecture/specs/` doc remains unlabeled

Phase 2 is complete when:

- all `docs/reference/service/api/` docs have headers
- the remaining spec-adjacent P1 docs have headers
