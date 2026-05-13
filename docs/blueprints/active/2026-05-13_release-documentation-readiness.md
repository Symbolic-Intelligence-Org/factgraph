# Task Blueprint: Release Documentation Readiness

- Status: scoped
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `kernel.sdk`
  - `kernel.application`
  - `kernel.audit`
  - `src/service`
- Related Docs:
  - [README.md](../../../README.md)
  - [docs/README.md](../../README.md)
  - [src/kernel/sdk/docs/00_user_guide.en.md](../../../src/kernel/sdk/docs/00_user_guide.en.md)
  - [src/kernel/sdk/docs/03_rules_and_inferences.en.md](../../../src/kernel/sdk/docs/03_rules_and_inferences.en.md)
  - [src/kernel/sdk/docs/04_api_surface.en.md](../../../src/kernel/sdk/docs/04_api_surface.en.md)
  - [src/service/docs/01_overview.md](../../../src/service/docs/01_overview.md)
  - [src/service/docs/03_runtime_queries_policy.md](../../../src/service/docs/03_runtime_queries_policy.md)
  - [docs/api/openapi.yaml](../../api/openapi.yaml)
- Audit Log:
  - [2026-05-13_release-documentation-readiness.audit.md](./2026-05-13_release-documentation-readiness.audit.md)

## 1. Problem

After `v0.1.0-rc.3`, schema mutation, schema field-add, and the confidence /
evidence cleanup, several release-facing documents still reflect older public
surface assumptions:

- root README still teaches `FactGraph.from_schema_classes(...)`, `Derivation`,
  and "8 taxonomy namespaces";
- examples README still says v0.1 ships no SDK shells and that application /
  audit advanced imports are the main Q1-Q5 path;
- service overview accept examples still expose legacy confidence fields in
  candidate DTOs;
- OpenAPI still mixes kernel service and extraction wording while docs already
  say extraction moved to `agent.service`;
- some current implementation docs use substrate `derivation` wording in places
  where public `Inference` wording should lead.

This is release documentation readiness work, not a product redesign. The task
is to align release-facing docs with already-published behavior and clearly
separate public surface, advanced importable surface, service scope, and
substrate vocabulary.

## 2. Goals

- Make the root README accurate for the current `kernel.sdk` public surface.
- Make SDK docs consistent on `FactGraph.create(...)`, `Inference`,
  `fg.rules.*` / `fg.inferences.*`, `fg.schema.add(...)`, and workspace
  lifecycle.
- Make examples README reflect current SDK shells and lifecycle APIs.
- Make service docs and OpenAPI accurately describe current service scope and
  confidence cleanup boundaries.
- Preserve module docs as current implementation truth.
- Keep reference/design-point docs explicitly non-authoritative.

## 3. Non-goals

- No Python code changes.
- No public API changes.
- No release tag or release branch movement.
- No generated notebook rewrite.
- No broad rewrite of `docs/blueprint_history/`.
- No full OpenAPI field-schema completion; existing generic payload schemas may
  remain if explicitly documented.
- No extraction / agent service redesign.

## 4. Current Context

### 4.1 Source Audit Findings

Initial grep/read audit found these concrete stale or ambiguous surfaces:

1. Root README:
   - teaches `FactGraph.from_schema_classes([User])` instead of
     `FactGraph.create(schema_classes=[...])`;
   - says "8 taxonomy namespaces" and omits `rules` / `inferences`;
   - lists `Query / Derivation` user entrypoints instead of
     `Query / Inference`;
   - links `src/kernel/core/docs/01_architecture.md`, while current docs are
     `01_architecture.en.md`.
2. `examples/README.md`:
   - still says v0.1 ships no SDK shells or wrapped surface for Batch 3-7,
     which predates the L-direction / post-L SDK surface and lifecycle work.
3. `src/service/docs/01_overview.md`:
   - accept candidate example still includes legacy `confidence` /
     `confidence_kind` fields after the release cleanup;
   - still uses public `derivation` wording in some explanatory prose, while
     substrate `derivation_id` fields intentionally remain only inside
     candidate payloads.
4. `src/service/docs/03_runtime_queries_policy.md`:
   - mostly reflects the confidence cleanup already, but the title still says
     "Derivation DTO" and substrate wording needs review for public-vs-internal
     clarity.
5. `docs/api/openapi.yaml`:
   - top description and tags still include extraction as part of this service
     spec even though docs say extraction moved to `agent.service`;
   - uses stale `src/factpy_kernel/...` doc paths;
   - still documents generic object payload precision boundary, which may stay
     but must be framed as deliberate incomplete field-schema coverage.
6. SDK docs:
   - current API surface already contains the latest `Saved*Ref`,
     `SchemaAddResult`, workspace lifecycle, and schema add behavior;
   - audit should focus on remaining top-level wording drift rather than
     rewriting stable API sections.
7. Runtime verification:
   - `kernel.sdk.__all__` currently has 41 names.
   - `FactGraph` exposes these 10 top-level namespaces:
     `schema`, `read`, `write`, `rules`, `inferences`, `eval`, `what_if`,
     `audit`, `package`, `views`.
   - `FactGraph.create(schema_classes=[])` is invalid; examples need at least
     one `Entity` class.

### 4.2 Existing Constraints

- `src/kernel/*/docs/` and `src/service/docs/` are current implementation
  truth.
- `docs/references/` and `memory/` are not current truth.
- Service remains a monorepo HTTP facade; `factpy-kernel` PyPI release remains
  kernel-only.
- Substrate `derivation_id` / `Derivation*` names still exist intentionally in
  internal DTOs and candidate payloads.

## 5. Proposed Shape

Treat this as a release-docs cleanup slice:

- update the user-facing README to present the current SDK path:
  `FactGraph.create(...)`, `Inference`, authoring facades, schema mutation,
  workspace lifecycle, and current namespace count;
- update examples README so it no longer describes the pre-L public surface;
- update service docs to remove stale confidence DTO examples and clarify
  public inference route vocabulary vs substrate candidate fields;
- update OpenAPI description/tags/doc links for current service scope without
  attempting full schema completion;
- run focused stale-grep gates for the old terms and links.

## 6. Boundaries And Invariants

- Release docs must not claim `Derivation` is a public SDK value object.
- Release docs must not teach `FactGraph.from_schema_classes(...)` as the
  default first-contact constructor.
- Root README and SDK docs should lead with `FactGraph.create(...)`.
- Public docs may mention substrate `derivation_id` only when explicitly
  describing candidate/internal protocol payloads.
- Service docs must not show default candidate DTOs with legacy confidence
  fields after the confidence cleanup.
- OpenAPI may keep generic object schemas, but must not imply extraction is in
  the kernel service when the current service docs say it moved to
  `agent.service`.
- Notebook execution / regeneration is out of scope unless a stale notebook is
  deliberately promoted as a release-facing example.

## 7. Acceptance

- [ ] Root README current with public SDK names and entrypoints.
- [ ] Examples README current with current SDK shell / advanced importable
  boundary.
- [ ] SDK docs checked for release-facing stale terms.
- [ ] Service docs checked for confidence DTO and inference vocabulary drift.
- [ ] OpenAPI description/tags/doc paths synchronized with current service
  scope.
- [ ] Focused stale-grep gates pass or remaining hits are explicitly internal /
  substrate / historical.
- [ ] No code behavior changes.

## 7.1 G0 Candidate Gates

Before implementation, lock the exact file list and grep gates:

- `README.md`
- `examples/README.md`
- `src/service/docs/01_overview.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `docs/api/openapi.yaml`
- optional SDK docs touch only when the stale-grep result is release-facing,
  not merely substrate/internal vocabulary.

Candidate stale-grep gates:

```bash
rg -n "FactGraph\\.from_schema_classes|Query / Derivation|8 taxonomy|eight namespaces|no SDK shells|no \"wrapped\"|src/factpy_kernel|01_architecture\\.md|\"confidence\": null|/v1/extraction/documents|LLM document extraction|05_extraction" \
  README.md examples/README.md src/service/docs/01_overview.md \
  src/service/docs/03_runtime_queries_policy.md docs/api/openapi.yaml
```

Remaining `derivation_id` / `derivation_version` hits are allowed only when
framed as candidate/internal substrate fields.

## 8. Implementation Plan

1. Complete source audit across README, SDK docs, service docs, OpenAPI, and
   examples README; record any additional drift in the audit log.
2. Scope-freeze the exact file list and stale-grep gates.
3. Apply docs updates in small thematic commits:
   - root README + docs index;
   - SDK / examples docs;
   - service docs + OpenAPI.
4. Run `git diff --check` and focused stale-grep gates.
5. Fill Outcome / Deviations and archive this blueprint.

## 9. Docs To Update

- `README.md`
- `docs/README.md`
- `examples/README.md`
- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/service/docs/01_overview.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `docs/api/openapi.yaml`

## 10. Outcome / Deviations

Task completion notes will be filled after implementation and verification.
