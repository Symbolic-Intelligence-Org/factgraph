# Task Blueprint Audit: Official Kernel Docstrings And Tutorials

- Blueprint: [2026-05-13_official-kernel-docstrings-and-tutorials.md](./2026-05-13_official-kernel-docstrings-and-tutorials.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Initial draft for official kernel documentation slice: public SDK docstrings first, then canonical Markdown tutorial tree under `docs/official/kernel/`. |
| 2026-05-13 | draft | Draft clarified | Added explicit selected-method docstring checklist, docstring gate scope, initial coverage snapshot, Diátaxis section boundaries, and deferred Markdown doctest harness. |
| 2026-05-13 | draft | Per-document cadence added | Added D15/D16, G1 gate specifics, Page Brief template, per-document commit cadence, and multi-session completion boundary. |
| 2026-05-13 | scoped | G0 scope frozen | Locked 16 decisions: docstring coverage/style/gate, `docs/official/kernel/`, English-first Diátaxis tree, strict kernel-only boundary, per-page Page Briefs, external style references as non-factual, and multi-session completion. |
| 2026-05-13 | scoped | G2.1 docstring batch started | Added first hover-doc batch for `Entity`, `Field`, `Identity`, `FactGraph`/`SDKStore`, `FactGraph.create`, `fg.read.get/ref`, and `fg.write.set/add`. |
| 2026-05-13 | scoped | G2.2 quickstart page started | Added the first official tutorial page brief and drafted `quickstart/first-factgraph.md` from current SDK behavior. |
| 2026-05-13 | scoped | G2.3 schema quickstart page started | Added a schema-focused tutorial page brief and drafted `quickstart/schema.md` from current schema, read/write, and schema mutation behavior. |
| 2026-05-13 | scoped | G2.4 schema/read-write docstring anchors started | Added hover docs for `SchemaAddResult`, `fg.schema.add`, `fg.read.find`, and `fg.write.retract` to anchor schema and read/write tutorials. |

## Decision Notes

- 2026-05-13: Old public docs are not compatibility constraints because the
  product has not shipped yet. They may inform style, but current code and
  module docs are the source of truth.
- 2026-05-13: The release artifact is kernel-only. Official tutorial docs
  should not teach service, agent, extraction, domains, or HTTP routes as part
  of the `factpy-kernel` public release surface.
- 2026-05-13: Public API docstrings are treated as part of the user
  documentation layer because IDE hover text is a first-contact learning path.
- 2026-05-13: Documentation-slice cadence is scoped differently from
  capability and cleanup slices: G1 has docstring/tree/audit-template gates;
  G2 proceeds by logical docstring batches and per-page Markdown briefs.

## Page Briefs

### `quickstart/first-factgraph.md`

- Reader goal: Build the smallest useful `FactGraph`, write facts, and read them back without learning registry, workspace, rules, inference, or service concepts yet.
- APIs covered: `Entity`, `Identity`, `Field`, `FactGraph.create`, `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`.
- Non-goals: Rules, inferences, semantics profiles, schema mutation, saved registries, workspace persistence, views, audit, package export, service routes, and advanced adapter behavior.
- Source files checked: `src/kernel/sdk/schema.py`, `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/tests/test_sdk_assertion_record_set.py`, `src/kernel/tests/test_schema_field_add_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`.
- Example snippets planned: Define a `User` entity, create an in-memory graph, build an `idref_v1` handle, write one single field and one multi field, then read the snapshot.
- Validation method: Extracted the main snippet and ran it with `PYTHONPATH=src python`, verifying `snap.name == "Alice"` and `tuple(snap.tags) == ("engineer",)`.
- External style reference: Pydantic-style plain-language quickstart structure only; all API facts come from local source, module docs, tests, and archived blueprints.

### `quickstart/schema.md`

- Reader goal: Learn how to choose identity fields, single fields, multi fields, and entity-reference fields before writing larger schemas.
- APIs covered: `Entity`, `Identity`, `Field`, `FactGraph.create`, `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`, `fg.schema.add`, `SchemaAddResult.added_fields`.
- Non-goals: Relationship classes, rule/inference authoring, semantic adapters, workspace persistence, schema delete/update/migrate, low-level schema IR, and service routes.
- Source files checked: `src/kernel/sdk/schema.py`, `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/tests/test_schema_mutation_lifecycle.py`, `src/kernel/tests/test_schema_field_add_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/01_concepts.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`.
- Example snippets planned: Define `Team` and `User`, store a reference from `User.team` to `Team`, read single/multi/reference fields, then add a non-identity `nickname` field with a replacement `User` class.
- Validation method: Extracted all Python blocks and ran them in order with `PYTHONPATH=src python`, verifying reference writes, missing added-field reads, and `SchemaAddResult.added_fields`.
- External style reference: Pydantic-style progressive schema teaching only; current local code, tests, module docs, and archived blueprints define behavior.
