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
| 2026-05-13 | scoped | G2.13 persistence round-trip bug fixed | While validating the persistence tutorial examples, found saved `Rule`/`Inference` load returned SDK value objects whose already-lowered `where` IR failed when executed again. Preserved/restored authoring IR in DSL payload generation and added a focused regression test. |
| 2026-05-13 | scoped | G2.14 persistence quickstart page started | Added a Page Brief and drafted `quickstart/persistence.md` around saved authoring handles, load-before-run, workspace save/load, and the per-asset vs whole-workspace distinction. |
| 2026-05-13 | scoped | G2.15 semantics docstring anchors | Added hover docs for public semantics wrappers, canonical `SemanticsProfile`, and `fg.eval.inspect_semantics` before drafting the semantics quickstart page. |
| 2026-05-13 | scoped | G2.16 semantics quickstart page started | Added a Page Brief and drafted `quickstart/semantics.md` around evaluate-time engine configuration, public wrappers, canonical profiles, branch ids, and the unchanged CandidateSet-to-accept lifecycle. |
| 2026-05-13 | scoped | G2.17 docstring gate closed | Added the remaining hover docs for schema compile helpers, bulk accept, what-if, audit, package, and views; `test_official_kernel_docs_baseline.py` now passes. |
| 2026-05-13 | scoped | G2.18 schema identity concept page started | Added a Page Brief and drafted `concepts/schema-and-identity.md` to deepen the coordinate / primary-anchor / Field fact model introduced in quickstart/schema.md. |
| 2026-05-13 | scoped | G2.19 SDK surface reference page started | Added a Page Brief and drafted `reference/sdk-surface.md` as a scan-friendly map of public `kernel.sdk` exports and `FactGraph` namespaces. |

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
- 2026-05-13: Docs-as-validation is part of this slice. The persistence
  tutorial draft exposed a real authoring round-trip bug where loaded
  `Rule`/`Inference` value objects could not be executed because already
  lowered `where` IR was lowered again. The fix and regression test landed
  before the tutorial page was committed.

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

### `quickstart/persistence.md`

- Reader goal: Persist reusable rules and inferences as authoring assets, then save and load a complete workspace containing schema, ledger, and registry state.
- Core mental model: Persistence has two tiers: per-asset registry persistence (`fg.rules.save/load`, `fg.inferences.save/load`) and whole-workspace persistence (`fg.save`, `FactGraph.load`). Saved refs are handles; loaded value objects are what runtime methods consume.
- Common misconception to prevent: `fg.rules.get(...)` returns the latest `SavedRuleRef`, not a `Rule`; `SavedRuleRef` is not a runtime selector; `FactGraph.load(path)` requires `schema_classes=[...]`.
- APIs covered: `SavedRuleRef`, `SavedInferenceRef`, `fg.rules.save`, `fg.rules.list`, `fg.rules.get`, `fg.rules.load`, `fg.inferences.save`, `fg.inferences.list`, `fg.inferences.get`, `fg.inferences.load`, `FactGraph.create(path=...)`, `fg.save`, `FactGraph.load`.
- Non-goals: Class-less dynamic load, schema migration across workspaces, package export, service routes, conflict-resolution UI, advanced registry versioning, and semantic engine persistence.
- Source files checked: `src/kernel/application/authoring_runtime.py`, `src/kernel/application/workspace_runtime.py`, `src/kernel/authoring/registry_fs.py`, `src/kernel/sdk/store.py`, `src/kernel/tests/test_authoring_asset_persistence_facade.py`, `src/kernel/tests/test_factgraph_workspace_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/03_rules_and_inferences.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`, `src/kernel/authoring/docs/01_overview.md`.
- Design references checked: `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_authoring-asset-persistence-facade.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`, `docs/blueprints/archive/2026-05-12_inference-wire-registry-vocabulary.md`, `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`.
- Example snippets planned: Create a path-backed graph, save/load a rule and inference, show `get(...)` returning latest saved refs, run/evaluate loaded value objects, save the workspace, inspect Level-4 layout files, and load the workspace with schema classes.
- Validation method: Extract all Python blocks and run them in order with `PYTHONPATH=src python`, verifying saved-ref shapes, load-before-run, accepted inference facts, workspace files, and `FactGraph.load(..., schema_classes=[...])`.
- External style reference: Pydantic-style tutorial progression and short recap only; all persistence behavior comes from local source, module docs, tests, and archived blueprints.

### `quickstart/semantics.md`

- Reader goal: Understand how to choose and inspect evaluate-time semantics configuration without changing the rule/inference lifecycle learned in the previous pages.
- Core mental model: `Inference` describes what could be derived; `ProbLogSemantics`, `PyReasonSemantics`, or `SemanticsProfile` describe how a runtime engine should evaluate that inference at call time.
- Common misconception to prevent: Semantics wrappers do not write to the ledger, do not belong inside the `Inference` template, and do not replace the `evaluate -> CandidateSet -> accept` lifecycle.
- APIs covered: `ProbLogSemantics`, `PyReasonSemantics`, `SemanticsProfile`, `fg.eval.inspect_semantics`, `fg.eval.evaluate` as the call-site concept, `Branch(id=...)` as the stable branch-key source.
- Non-goals: ProbLog or PyReason mathematical semantics, service JSON semantics payloads, compiled-plan internals, direct adapter carriers, atom-level PyReason bounds, and advanced custom `SemanticsProfile` authoring.
- Source files checked: `src/kernel/sdk/semantics.py`, `src/kernel/core/semantics/profile.py`, `src/kernel/sdk/store.py`, `src/kernel/tests/test_public_semantics_api_redesign.py`, `src/kernel/tests/test_pyreason_branch_bounds_carrier.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/03_rules_and_inferences.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`, `src/kernel/core/semantics/docs/README.md`, `src/kernel/adapters/docs/02_problog_adapter.md`, `src/kernel/adapters/docs/03_pyreason_adapter.md`.
- Design references checked: `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-semantics-api-redesign.md`, `docs/blueprints/archive/2026-05-12_pyreason-branch-bounds-carrier.md`, `docs/blueprints/archive/2026-05-12_sdk-service-semantics-callsite.md`, `docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md`.
- Example snippets planned: Define one inference with an explicit branch id, inspect ProbLog and PyReason wrapper previews, show PyReason branch-bound profile entries, inspect an advanced `SemanticsProfile`, and keep the accepted-fact lifecycle separate.
- Validation method: Extract all Python blocks and run them in order with `PYTHONPATH=src python`, verifying wrapper engines, inspect output, PyReason lowered profile entries, explicit branch ids, and the unchanged read-before-accept state.
- External style reference: Pydantic-style tutorial progression and short recap only; all semantics behavior comes from local source, tests, module docs, and archived blueprints.

### `concepts/schema-and-identity.md`

- Reader goal: Build a stable mental model for `Identity(primary_key=True)`, non-primary `Identity()`, `Field(...)`, full-coordinate refs, and primary-anchor reads/writes before using larger schemas.
- Core mental model: All `Identity` fields define the complete entity coordinate and encode into `idref_v1`; `primary_key=True` marks the logical anchor used by SDK ergonomics and authoring, while `Field(...)` values are mutable facts under one complete coordinate.
- Common misconception to prevent: A primary key is not the only identity field, non-primary identity is not a normal mutable field, and `fg.read.find(...)` does not return a primary-only entity object.
- APIs covered: `Entity`, `Identity`, `Field`, `FactGraph.create`, `fg.read.ref`, `fg.read.get`, `fg.read.find`, `fg.write.set`, `fg.batch`, `tx.entity`, `handle.bind`, `fg.schema.add`, `SchemaAddResult.added_fields`.
- Non-goals: Relationship schema modeling, rule authoring identity lowering, identity migration, schema delete/update/migrate, field defaults/backfill, primary-only ref tokens, and storage internals beyond the user-visible `idref_v1` boundary.
- Source files checked: `src/kernel/sdk/schema.py`, `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/application/schema_runtime.py`, `src/kernel/application/schema_mutation_runtime.py`, `src/kernel/tests/test_sdk_batch_primary_identity.py`, `src/kernel/tests/test_sdk_find_partial_identity.py`, `src/kernel/tests/test_schema_field_add_lifecycle.py`.
- Module docs checked: `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/01_concepts.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/identity-primary-key-coordinate-semantics.md`, `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`, `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`, `docs/blueprint_history/从dims到n元Identity的设计演进.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-10_primary-identity-domain-semantics.md`, `docs/blueprints/archive/2026-05-10_primary-anchor-domain-read.md`, `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`.
- Example snippets planned: Show same primary / different non-primary identity refs, attach Field facts under coordinates, compare `get` and `find`, demonstrate primary-first batch binding, and add a non-identity field with a replacement class.
- Validation method: Extract all Python blocks and run them in order with `PYTHONPATH=src python`, verifying distinct refs, full-coordinate reads, partial-identity find results, batch primary-first binding, and field-add missing-value semantics.
- External style reference: Pydantic-style concepts page pacing only; all schema and identity behavior comes from local source, tests, module docs, design notes, and archived blueprints.

### `reference/sdk-surface.md`

- Reader goal: Provide a scan-friendly public surface map so users can find the right SDK object or namespace after learning from the quickstart.
- Core mental model: `kernel.sdk` is the public import surface; `FactGraph` is the facade object; namespaces group workflows rather than implementation modules.
- Common misconception to prevent: Advanced helpers such as schema compiler functions are public escape hatches, not the starting path; namespace methods are preferred over flat/root call-throughs.
- APIs covered: all 41 `kernel.sdk.__all__` exports and the selected `FactGraph` namespace methods from blueprint §5.1.1.
- Non-goals: Full parameter-by-parameter API reference, service routes, internals, adapter implementation APIs, and examples for every method.
- Source files checked: `src/kernel/sdk/__init__.py`, `src/kernel/sdk/compile.py`, `src/kernel/sdk/store.py`, `src/kernel/tests/test_official_kernel_docs_baseline.py`.
- Module docs checked: `src/kernel/sdk/docs/04_api_surface.en.md`, `src/kernel/sdk/docs/00_user_guide.en.md`, `src/kernel/sdk/docs/03_rules_and_inferences.en.md`.
- Design references checked: `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`, `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`, `docs/blueprints/archive/2026-05-12_authoring-asset-persistence-facade.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md`, `docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md`.
- Example snippets planned: None; this is a reference table page. It links users back to quickstart/concepts pages for runnable examples.
- Validation method: Compare the export count and names with `kernel.sdk.__all__`, run the official docs baseline, and keep `git diff --check` clean.
- External style reference: Pydantic-style reference navigation only; all API names and groupings come from local source, tests, and module docs.

### `concepts/factgraph.md`

- Reader goal: Understand what a `FactGraph` is: a schema-bound facade over an append-only assertion ledger, not a mutable object table.
- Core mental model: Writes append assertions to the ledger; reads resolve current snapshots from active assertion history; views name frozen assertion-id sets, not read policies.
- Common misconception to prevent: `fg.write.set(...)` is not in-place mutation, `single` fields do not erase earlier assertions, and `fg.write.retract(...)` takes an assertion id rather than an entity ref or value.
- APIs covered: `FactGraph`, `fg.read.ref`, `fg.write.set`, `fg.write.add`, `fg.read.get`, `EntitySnapshot.field(...)`, `AssertionRecordSet.active`, `AssertionRecordSet.history`, `fg.write.retract`, `fg.views.create/get/list`, `fg.assertions.by_ids`, `ReadPolicy`.
- Non-goals: Rules/inferences, semantics engines, workspace persistence, service routes, proof/evidence internals, package export, and full confidence/certainty design.
- Source files checked: `src/kernel/sdk/store.py`, `src/kernel/sdk/facade.py`, `src/kernel/core/evidence/write_protocol.py`, `src/kernel/tests/test_sdk_assertion_record_set.py`, `src/kernel/tests/test_sdk_read_policy.py`, `src/kernel/tests/test_sdk_frozen_assertion_view.py`.
- Module docs checked: `src/kernel/sdk/docs/01_concepts.en.md`, `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-11_frozen-assertion-view-model.md`, `docs/blueprints/archive/2026-05-10_assertion-selection-crud-ergonomics.md`, `docs/blueprints/archive/2026-05-13_confidence-evidence-meta-release-cleanup.md`.
- Example snippets planned: Write two single-field assertions, inspect snapshot history, retract one multi-field assertion, create a frozen assertion view, read assertion records by id, and show `ReadPolicy` as a call-site object.
- Validation method: Extract Python blocks and run them with `PYTHONPATH=src python`, verifying append-only history, current snapshot resolution, retraction active/history split, frozen view membership, and `ReadPolicy` construction.
- External style reference: Pydantic-style concepts page pacing only; all FactGraph, ledger, snapshot, and view behavior comes from local source, tests, module docs, and archived blueprints.

### `concepts/rules-and-inferences.md`

- Reader goal: Understand the conceptual boundary between `Rule`, `Inference`, `CandidateSet`, `accept`, `RuleRef`, and saved authoring refs before using larger rule systems.
- Core mental model: Rules read current snapshots; inferences propose candidate assertions; acceptance is the only step that appends inferred facts to the ledger.
- Common misconception to prevent: `fg.eval.evaluate(...)` does not write, `RuleRef` is not a persisted rule handle, and engine-specific semantics are call-site evaluation configuration rather than part of the rule template.
- APIs covered: `Rule`, `Inference`, `Branch`, `Pred`, `vars`, `fg.eval.run`, `fg.eval.evaluate`, `fg.eval.accept`, `fg.rules.inspect`, `RuleRef`, `SavedRuleRef`, `SavedInferenceRef`.
- Non-goals: Advanced `RuleRef` composition examples, query persistence, proof/evidence internals, service routes, ProbLog/PyReason mathematics, and policy/theory verification.
- Source files checked: `src/kernel/sdk/dsl/rule.py`, `src/kernel/sdk/dsl/branch.py`, `src/kernel/sdk/dsl/expr.py`, `src/kernel/sdk/store.py`, `src/kernel/application/derivation_runtime.py`.
- Module docs checked: `src/kernel/sdk/docs/03_rules_and_inferences.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`, `src/kernel/core/semantics/docs/README.md`.
- Design references checked: `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`, `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md`, `docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md`, `docs/blueprints/archive/2026-05-12_public-semantics-api-redesign.md`, `docs/blueprints/archive/2026-05-12_authoring-asset-persistence-facade.md`.
- Example snippets planned: Run a rule, evaluate an inference, prove no write before accept, accept the candidate, inspect branch structure, and distinguish `RuleRef` from saved refs.
- Validation method: Extract Python blocks and run them with `PYTHONPATH=src python`, verifying rule rows, read-before-accept state, accepted candidate writes, and inspect metadata.
- External style reference: Pydantic-style concepts page pacing only; all rule, inference, candidate, and saved-ref boundaries come from local source, tests, module docs, design notes, and archived blueprints.

### `concepts/persistence-and-workspaces.md`

- Reader goal: Understand the difference between saving authoring assets and saving a complete FactGraph workspace.
- Core mental model: The registry stores reusable rule/inference definitions; the workspace stores the Level-4 graph state: schema metadata, ledger database, registry, and workspace manifest.
- Common misconception to prevent: `SavedRuleRef` / `SavedInferenceRef` are not runtime objects, `fg.rules.get(...)` returns a handle rather than a `Rule`, and `fg.save()` is not the same operation as `fg.rules.save(...)`.
- APIs covered: `SavedRuleRef`, `SavedInferenceRef`, `fg.rules.save/load/list/get`, `fg.inferences.save/load/list/get`, `FactGraph.create(path=...)`, `fg.save`, `FactGraph.load`.
- Non-goals: Class-less load, package export, service routes, artifact sidecar persistence, view persistence, query persistence, and schema migration.
- Source files checked: `src/kernel/application/authoring_runtime.py`, `src/kernel/application/workspace_runtime.py`, `src/kernel/authoring/registry_fs.py`, `src/kernel/sdk/store.py`, `src/kernel/tests/test_authoring_asset_persistence_facade.py`, `src/kernel/tests/test_factgraph_workspace_lifecycle.py`.
- Module docs checked: `src/kernel/authoring/docs/01_overview.md`, `src/kernel/sdk/docs/03_rules_and_inferences.en.md`, `src/kernel/sdk/docs/04_api_surface.en.md`.
- Design references checked: `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`.
- Archived blueprints checked: `docs/blueprints/archive/2026-05-12_authoring-asset-persistence-facade.md`, `docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md`, `docs/blueprints/archive/2026-05-12_inference-wire-registry-vocabulary.md`.
- Example snippets planned: Save and load a rule handle, save and load an inference handle, save a path-bound workspace, inspect workspace layout files, and load the workspace with schema classes.
- Validation method: Extract Python blocks and run them with `PYTHONPATH=src python`, verifying saved-ref shapes, load-before-runtime, workspace layout files, and loaded graph round-trip behavior.
- External style reference: Pydantic-style concepts page pacing only; all persistence and workspace behavior comes from local source, tests, module docs, design notes, and archived blueprints.
