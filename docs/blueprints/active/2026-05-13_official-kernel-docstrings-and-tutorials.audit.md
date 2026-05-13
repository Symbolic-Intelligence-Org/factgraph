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
| 2026-05-13 | scoped | G2.5 tutorial mental-model pass started | Strengthened the Page Brief contract and revised the first two quickstart pages to explain FactGraph/fact/assertion/ref/snapshot/schema concepts before syntax. |
| 2026-05-13 | scoped | G2.6 Page Brief gate updated | Extended the official docs baseline to require Page Brief fields for core mental model, common misconception, and design references. |
| 2026-05-13 | scoped | G2.7 read/write quickstart page started | Added a read/write tutorial brief and drafted `quickstart/read-write.md` from current assertion, snapshot, ref, find, and retract behavior. |
| 2026-05-13 | scoped | G2.8 schema quickstart identity-coordinate pass | Reworked `quickstart/schema.md` around Identity coordinate semantics, primary-key logical anchors, Field fact content, and n-ary identity guidance from design references. |
| 2026-05-13 | scoped | G2.9 primary-anchor batch note added | Expanded `quickstart/schema.md` with the primary-first batch handle / non-primary `bind(...)` mechanism so `primary_key=True` has a concrete user-facing meaning. |
| 2026-05-13 | scoped | G2.9 schema quickstart batch identity note | Added a concise forward pointer clarifying that batch handles start from primary identity and may bind non-primary identity dimensions later. |
| 2026-05-13 | scoped | G2.10 rules/inferences docstring anchors | Added hover docs for rule/inference/query DSL objects plus `fg.eval.run`, `fg.eval.evaluate`, `fg.eval.accept`, and `fg.rules.inspect` before drafting the rules tutorial page. |
| 2026-05-13 | scoped | G2.11 rules/inferences quickstart page started | Added a Page Brief and drafted `quickstart/rules-and-inferences.md` around Rule read-only queries, Inference candidate generation, explicit accept, and branch inspection. |
| 2026-05-13 | scoped | G2.12 official docs index skeleton | Added five lightweight index pages for the official kernel docs root plus quickstart, concepts, how-to, and reference sections. |
| 2026-05-13 | scoped | G2.13 persistence/workspace docstring anchors | Added hover docs for `SavedRuleRef`, `SavedInferenceRef`, `fg.rules.*`, `fg.inferences.*`, `fg.save`, and `FactGraph.load` before drafting the persistence quickstart page. |

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
- 2026-05-13: Substantive official pages must not be API transcripts. Each
  page should establish a concise mental model, identify a likely
  misconception, and then teach the current API path.

## Page Briefs

### `quickstart/first-factgraph.md`

- Reader goal: Build the smallest useful `FactGraph`, write facts, and read them back without learning registry, workspace, rules, inference, or service concepts yet.
- Core mental model: A `FactGraph` is a schema-bound fact workspace; writes append assertions about entity identities, and reads return current snapshots over those assertions.
- Common misconception to prevent: `fg.write.set(...)` does not mutate a Python `User` object, and `fg.read.ref(...)` is not a string format users should parse.
- APIs covered: `Entity`, `Identity`, `Field`, `FactGraph.create`, `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`.
- Non-goals: Rules, inferences, semantics profiles, schema mutation, saved registries, workspace persistence, views, audit, package export, service routes, and advanced adapter behavior.
- Source files checked: `src/kernel/sdk/schema.py`, `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/tests/test_sdk_assertion_record_set.py`, `src/kernel/tests/test_schema_field_add_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`.
- Example snippets planned: Define a `User` entity, create an in-memory graph, build an `idref_v1` handle, write one single field and one multi field, then read the snapshot.
- Validation method: Extracted the main snippet and ran it with `PYTHONPATH=src python`, verifying `snap.name == "Alice"` and `tuple(snap.tags) == ("engineer",)`.
- External style reference: Pydantic-style plain-language quickstart structure only; all API facts come from local source, module docs, tests, and archived blueprints.

### `quickstart/schema.md`

- Reader goal: Learn how to choose primary identity anchors, non-primary identity dimensions, single fields, multi fields, and entity-reference fields before writing larger schemas.
- Core mental model: The schema is both vocabulary and coordinate system: all `Identity` fields define the complete entity coordinate, `primary_key=True` marks a logical anchor, and `Field(...)` values are mutable facts attached to that coordinate.
- Common misconception to prevent: `primary_key=True` is not a database-style sole identity determinant; non-primary `Identity()` fields still participate in `idref_v1`, while `Field(...)` values do not.
- APIs covered: `Entity`, `Identity`, `Field`, `FactGraph.create`, `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`, `fg.read.find`, `fg.batch`, `tx.entity`, `handle.bind`, `fg.schema.add`, `SchemaAddResult.added_fields`.
- Non-goals: Relationship classes, rule/inference authoring, semantic adapters, workspace persistence, schema delete/update/migrate, low-level schema IR, and service routes.
- Source files checked: `src/kernel/sdk/schema.py`, `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/tests/test_schema_mutation_lifecycle.py`, `src/kernel/tests/test_schema_field_add_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/01_concepts.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/identity-primary-key-coordinate-semantics.md`, `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`, `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`, `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/blueprint_history/从dims到n元Identity的设计演进.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-10_primary-identity-domain-semantics.md`, `docs/blueprints/archive/2026-05-10_primary-anchor-domain-read.md`, `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`.
- Example snippets planned: Define `Team` and `User` with primary and non-primary identities, show distinct complete-coordinate refs, write a managed entity-ref field, read one full coordinate with `get`, enumerate primary-anchor coordinates with `find`, show primary-first batch handle binding, then add non-identity fields with a replacement `User` class.
- Validation method: Extracted all Python blocks and ran them in order with `PYTHONPATH=src python`, verifying full-coordinate refs, partial identity `find`, reference writes, primary-first batch `bind(...)`, missing added-field reads, and `SchemaAddResult.added_fields`.
- External style reference: Pydantic-style progressive schema teaching only; current local code, tests, module docs, and archived blueprints define behavior.

### `quickstart/read-write.md`

- Reader goal: Understand how ordinary writes become append-only assertions, how reads resolve those assertions into snapshots, and how to inspect or retract individual assertions.
- Core mental model: The ledger stores assertion records; `fg.read.get(...)` and `fg.read.find(...)` build current snapshots from active assertions rather than returning mutable database rows.
- Common misconception to prevent: `fg.write.set(...)` is not an in-place update, `fg.write.retract(...)` takes an assertion id rather than an entity ref, and `fg.read.ref(...)` should be treated as opaque.
- APIs covered: `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`, `fg.read.find`, `fg.write.retract`, `EntitySnapshot.field(...)`, `AssertionRecordSet.active`, `AssertionRecordSet.history`.
- Non-goals: Batch transactions, edit context managers, ingest, read policies, views, audit/explain APIs, rules, inferences, workspace persistence, and service routes.
- Source files checked: `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/tests/test_sdk_set_add_application_delegate.py`, `src/kernel/tests/test_sdk_assertion_record_set.py`, `src/kernel/tests/test_sdk_find_partial_identity.py`, `src/kernel/tests/test_sdk_read_policy.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/01_concepts.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`, `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/references/working/design-points/identity-primary-key-coordinate-semantics.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-13_confidence-evidence-meta-release-cleanup.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`.
- Example snippets planned: Write a single field twice, add multi-field values, read a current snapshot, inspect assertion history, find entities by field filters, and retract one assertion by id.
- Validation method: Extract the complete example and run it with `PYTHONPATH=src python`, verifying latest single-field resolution, multi-field containment, assertion history, find filters, and retraction behavior.
- External style reference: Pydantic-style tutorial progression and recap only; all semantics come from local source, module docs, tests, and archived blueprints.

### `quickstart/rules-and-inferences.md`

- Reader goal: Learn the difference between a read-only `Rule` and an `Inference` that proposes new facts, then run, inspect, evaluate, and accept a minimal example.
- Core mental model: Rules ask the graph what is already true in the current snapshot; inferences propose candidate assertions from existing facts, and only `fg.eval.accept(...)` appends accepted candidates to the ledger.
- Common misconception to prevent: `fg.eval.evaluate(...)` does not write to the graph, `RuleRef` is not a saved-rule handle, and semantic engines are evaluate-time configuration rather than the first thing to learn.
- APIs covered: `Rule`, `Inference`, `Branch`, `Pred`, `vars`, `fg.eval.run`, `fg.eval.evaluate`, `fg.eval.accept`, `fg.rules.inspect`.
- Non-goals: Persistence with `SavedRuleRef` / `SavedInferenceRef`, advanced `RuleRef` composition, ProbLog/PyReason semantics, public `SemanticsProfile`, query persistence, what-if shells, and service routes.
- Source files checked: `src/kernel/sdk/dsl/rule.py`, `src/kernel/sdk/dsl/branch.py`, `src/kernel/sdk/dsl/expr.py`, `src/kernel/sdk/dsl/vars.py`, `src/kernel/sdk/store.py`, `src/kernel/tests/test_schema_mutation_lifecycle.py`, `src/kernel/tests/test_factgraph_workspace_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/03_rules_and_inferences.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`, `src/kernel/adapters/docs/02_problog_adapter.md`, `src/kernel/adapters/docs/03_pyreason_adapter.md`.
- Design references checked: `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`, `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`, `docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md`, `docs/blueprints/archive/2026-05-12_public-semantics-api-redesign.md`, `docs/blueprints/archive/2026-05-12_pyreason-branch-bounds-carrier.md`, `docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md`.
- Example snippets planned: Seed a fact, define a `Rule` over that fact, run it, define an `Inference` with the same body and a target predicate, evaluate to a `CandidateSet`, accept the candidate, read the written field, and inspect branch metadata.
- Validation method: Extract all Python blocks and run them in order with `PYTHONPATH=src python`, verifying rule rows, no write before accept, accepted candidate facts, and explicit branch ids in `fg.rules.inspect(...)`.
- External style reference: Pydantic-style tutorial progression and short recap only; all rule/inference behavior comes from local source, tests, module docs, and archived blueprints.
