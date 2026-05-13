# Task Blueprint: Official Kernel Docstrings And Tutorials

- Status: draft
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `kernel.sdk`
  - `kernel.application`
  - `kernel.audit`
  - `kernel.authoring`
  - `kernel.adapters`
- Related Docs:
  - [README.md](../../../README.md)
  - [docs/README.md](../../README.md)
  - [src/kernel/sdk/docs/README.md](../../../src/kernel/sdk/docs/README.md)
  - [src/kernel/sdk/docs/00_user_guide.en.md](../../../src/kernel/sdk/docs/00_user_guide.en.md)
  - [src/kernel/sdk/docs/04_api_surface.en.md](../../../src/kernel/sdk/docs/04_api_surface.en.md)
  - [src/kernel/core/docs/01_architecture.en.md](../../../src/kernel/core/docs/01_architecture.en.md)
  - [src/kernel/authoring/docs/01_overview.md](../../../src/kernel/authoring/docs/01_overview.md)
  - [docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md](../archive/2026-05-12_public-inference-factgraph-create.md)
  - [docs/blueprints/archive/2026-05-12_factgraph-workspace-lifecycle.md](../archive/2026-05-12_factgraph-workspace-lifecycle.md)
  - [docs/blueprints/archive/2026-05-13_schema-mutation-lifecycle.md](../archive/2026-05-13_schema-mutation-lifecycle.md)
  - [docs/blueprints/archive/2026-05-13_schema-field-add-lifecycle.md](../archive/2026-05-13_schema-field-add-lifecycle.md)
- Audit Log:
  - [2026-05-13_official-kernel-docstrings-and-tutorials.audit.md](./2026-05-13_official-kernel-docstrings-and-tutorials.audit.md)

## 1. Problem

The upcoming official documentation should replace the older public tutorial
site with current kernel behavior. It should not preserve old documentation
compatibility; the old site is only a style / structure reference.

Before writing long-form tutorials, the public Python API also needs usable
docstrings. Today, many `kernel.sdk` public exports have no `inspect.getdoc(...)`
text, so IDE hover help does not explain what core entrypoints do. That makes
the SDK feel incomplete even if the Markdown tutorials are correct.

This task therefore has two layers:

1. **Docstring layer** — concise hover documentation for public SDK exports and
   selected `FactGraph` namespace methods.
2. **Official Markdown tutorial layer** — a new kernel-only documentation tree
   that teaches current APIs and design concepts in a Pydantic-like structure.

## 2. Goals

- Define the official kernel docs structure under a new durable path.
- Add concise, stable docstrings for the public SDK surface.
- Create enough Markdown tutorial structure that the future website can use it
  directly as the canonical source.
- Keep official docs kernel-only: no service, agent, extraction, or domain
  bundle tutorials.
- Teach current APIs:
  - `FactGraph.create(...)`
  - `FactGraph.create(path=...)`, `fg.save(...)`, `FactGraph.load(...)`
  - `Entity`, `Field`, `Identity`
  - `Rule`, `Query`, `Inference`
  - `fg.rules.*`, `fg.inferences.*`
  - `fg.schema.add(...)`
  - `ProbLogSemantics`, `PyReasonSemantics`
- Keep implementation/module docs as current truth, but make the official docs
  the user-facing tutorial path.

## 3. Non-goals

- No service / HTTP documentation.
- No agent, extraction, or domain-bundle documentation.
- No compatibility with old public docs.
- No generated notebook rewrite.
- No code behavior changes.
- No new public API.
- No migration guide required solely for old unpublished docs.
- No exhaustive low-level implementation internals.

## 4. Current Context

### 4.1 Public SDK Export Audit

Current `kernel.sdk.__all__` has 41 names:

```text
SDKSchemaError, SDKStoreError, SDKRegistryError, EntityNotFoundError,
FrozenSnapshotError, CardinalityError, EditorClosedError,
INVALID_ROW_FORMAT, QUERY_MISSING_REF, QUERY_TYPE_MISMATCH,
QUERY_ALIAS_CONFLICT, QUERY_UNBOUND_VAR, QUERY_INVALID_ROW_FORMAT,
QUERY_NOT_IMPLEMENTED, IngestResult, ValidationReport, SDKDSLError,
Branch, Entity, Field, Identity, Relationship, ReadPolicy, SemanticsProfile,
ProbLogSemantics, PyReasonSemantics, SavedRuleRef, SavedInferenceRef,
SchemaAddResult, Rule, RuleRef, Inference, Query, Pred, Not, vars,
FactGraph, SDKStore, build_authoring_schema_from_classes,
compile_schema_from_classes, schema_preflight_from_classes
```

Initial AST audit showed that most public SDK classes/functions lack
docstrings. Notable missing areas:

- `Entity`, `Field`, `Identity`
- `FactGraph` / `SDKStore`
- `Rule`, `Inference`, `Query`, `Branch`, `RuleRef`
- `ProbLogSemantics`, `PyReasonSemantics`
- schema compile helpers
- ingest / validation DTOs
- SDK facade DTOs and editors
- SDK error classes

Some internal shell helpers already have docstrings, but those are not the main
user-facing hover surface.

### 4.1.1 Initial Docstring Coverage Snapshot

Initial AST audit found:

- Existing user-adjacent docstrings:
  - `Relationship`
  - SDK shell implementation helpers under `src/kernel/sdk/shells/*`
- Missing docstrings in the planned public hover surface:
  - all 41 `kernel.sdk.__all__` exports listed above;
  - `FactGraph` / `SDKStore` class-level docs;
  - the selected namespace methods enumerated in §5.1.1.

The baseline test should verify the final intended coverage, not merely the
initial missing set. If a symbol already has a docstring, it still belongs in
the gate when it is part of the locked public hover surface.

### 4.2 Official Docs Boundary

The official release docs must be kernel-only:

- include: `kernel.sdk`, conceptual `kernel.application` / `kernel.audit`
  advanced importable boundaries, adapter semantics as used from SDK;
- exclude: `src/service`, HTTP routes, `agent`, document extraction, domains,
  and internal workflow docs.

### 4.3 Existing Documentation Sources

Useful current sources:

- `src/kernel/sdk/docs/*` — current SDK implementation docs.
- `src/kernel/core/docs/*` — substrate and architecture background.
- `src/kernel/authoring/docs/*` — authoring registry and schema behavior.
- `src/kernel/adapters/docs/*` — adapter semantics.
- archived blueprints from 2026-05-12 and 2026-05-13 — decision rationale for
  Inference, lifecycle/assets, semantics, and schema mutation.

Non-authoritative sources:

- old official/tutorial docs;
- `archive/docs_old/tutorials/*`;
- `archive/factpy_archive/docs/*`;
- `docs/references/*` unless conclusions have migrated into module docs or
  current archived blueprints.

## 5. Proposed Shape

Create a documentation slice with two implementation tracks.

### 5.1 Track A — Public SDK Docstrings

Add concise docstrings to:

- every exported public value in `kernel.sdk.__all__`;
- selected `FactGraph` / `SDKStore` public methods;
- selected namespace manager methods that users call through:
  - see §5.1.1.

#### 5.1.1 Selected Method Checklist

The docstring gate should cover these user-facing `FactGraph` / namespace
methods:

| Namespace | Methods |
| --- | --- |
| `FactGraph` / `SDKStore` | `create`, `load`, `save` |
| `fg.schema` | `add` |
| `fg.read` | `get`, `find`, `ref` |
| `fg.write` | `set`, `add`, `retract` |
| `fg.rules` | `inspect`, `save`, `load`, `list`, `get` |
| `fg.inferences` | `save`, `load`, `list`, `get` |
| `fg.eval` | `run`, `evaluate`, `accept`, `accept_many`, `inspect_semantics` |
| `fg.what_if` | `check`, `diagnose`, `why_not` |
| `fg.what_if.fact_overlay` | `check`, `recheck_proof_frame` |
| `fg.what_if.rule` | `disable`, `literal_replace`, `add_condition` |
| `fg.audit` | `explain_fact`, `conflicts`, `diff_proof_frames` |
| `fg.package` | `export_package`, `run_package` |
| `fg.views` | `create`, `update`, `delete`, `get`, `list` |

Docstrings should answer:

- what the object/function is for;
- when to use it;
- important parameters;
- return value;
- notable errors or boundaries.

They should not become long tutorials.

### 5.2 Track B — Official Kernel Markdown Docs

Create a new canonical tutorial tree:

```text
docs/official/kernel/
  index.md
  quickstart/
    index.md
    first-factgraph.md
    schema.md
    read-write.md
    rules-and-inferences.md
    semantics.md
    persistence.md
  concepts/
    factgraph.md
    schema-ledger-assertions.md
    rules-queries-inferences.md
    semantics.md
    persistence.md
    public-vs-advanced.md
  how-to/
    define-schema.md
    mutate-schema.md
    save-load-workspace.md
    save-rules-inferences.md
    use-problog.md
    use-pyreason.md
    inspect-rules.md
  reference/
    sdk-surface.md
    namespace-map.md
    errors.md
```

This tree should use plain Markdown and a calm tutorial style: direct examples,
short explanations, and clear cross-links. It should not duplicate low-level
module internals.

## 6. G0 Questions

These are draft questions. They are not locked until G0 scope freeze.

| ID | Question | Options | Recommendation |
| --- | --- | --- | --- |
| D1 | Docstring coverage | D1a: `kernel.sdk.__all__` only; D1b: `__all__` plus selected `FactGraph` namespace methods; D1c: all public classes/functions in `src/kernel/sdk` | D1b |
| D2 | Docstring style | D2a: compact prose only; D2b: Google-style sections (`Args`, `Returns`, `Raises`) when helpful; D2c: long examples in docstrings | D2b |
| D3 | Docstring examples | D3a: avoid examples except tiny one-liners; D3b: include runnable examples in every docstring | D3a |
| D4 | Docstring test gate | D4a: `inspect.getdoc(...)` non-empty for exported names and selected methods; D4b: no test gate; D4c: pydocstyle-style strict lint | D4a |
| D5 | Official docs path | D5a: `docs/official/kernel/`; D5b: `docs/tutorials/kernel/`; D5c: replace current `tutorials/` | D5a |
| D6 | Official docs language | D6a: English first; D6b: Chinese first; D6c: bilingual in one tree | D6a |
| D7 | Docs structure | D7a: tutorials / concepts / how-to / reference; D7b: flat quickstart-only tree; D7c: mirror old docs | D7a |
| D8 | Kernel-only boundary | D8a: strict kernel-only; D8b: include service/agent appendices | D8a |
| D9 | Runnable snippet policy | D9a: snippets should be runnable or explicitly marked conceptual; D9b: examples may be illustrative only | D9a |
| D10 | Source hierarchy | D10a: current code + module docs + archived blueprints; D10b: old official docs as truth | D10a |
| D11 | Implementation phasing | D11a: docstrings first, Markdown second; D11b: Markdown first; D11c: one large combined pass | D11a |
| D12 | README / docs index | D12a: add durable entry to `docs/README.md`; D12b: leave official tree unindexed until website import | D12a |
| D13 | Advanced importables | D13a: explain as advanced boundaries, not first-contact tutorial path; D13b: teach application/audit alongside SDK from page one | D13a |
| D14 | Old docs compatibility | D14a: no compatibility requirement; D14b: migration chapter for old unpublished docs | D14a |
| D15 | Per-page preparation | D15a: every substantive official MD page starts with a lightweight Page Brief recorded in the audit log; D15b: one global research pass only; D15c: no per-page research record | D15a |
| D16 | External style references | D16a: use Pydantic-like projects only for structure/tone, never as a fact source; D16b: do not reference external docs; D16c: mirror one external project's information architecture closely | D16a |

## 7. Boundaries And Invariants

- Official docs are kernel-only.
- The `inspect.getdoc(...)` test gate covers all 41 `kernel.sdk.__all__`
  exports plus the explicit method enumeration in §5.1.1.
- Private `_*` helpers are not in the docstring test scope even when they
  already have docstrings.
- Public tutorial examples lead with `kernel.sdk` and `FactGraph`.
- Do not teach `FactGraph.from_schema_classes(...)` as first-contact API.
- Do not reintroduce public `Derivation` value-object vocabulary.
- Do not present service / agent / extraction as part of `factpy-kernel` public
  release docs.
- Docstrings must be short enough to work in IDE hover.
- Markdown tutorials may be longer and include runnable examples.
- If a snippet depends on optional adapters, say so explicitly.
- No doctest harness for Markdown code blocks is in scope for this slice.
  Runnability is verified by using current APIs and marking conceptual snippets
  explicitly; a future slice may add executable Markdown validation.
- Existing module docs remain implementation truth; official docs are the
  tutorial/readme layer.
- The Markdown tree uses a Diátaxis-style boundary:
  - Tutorial pages are sequential learning paths and should be runnable from
    a clean start.
  - Concepts pages explain mental models and design rationale, not API lists.
  - How-to pages are task-oriented recipes.
  - Reference pages enumerate the surface and link back to implementation docs.
- Multi-session completion is expected. This blueprint must not archive to
  `implemented` until the locked docstring batches and all Markdown pages from
  §5.2 are landed. Between sessions, `memory/current.md` or a handoff must
  record the remaining page checklist.
- Per-page research is required before writing substantive Markdown pages.
  Record each Page Brief in the audit log before implementation.
- External docs such as Pydantic may inform organization, tone, and navigation,
  but never override local code, module docs, or archived blueprint decisions.

## 8. Acceptance

- [ ] G0 locks docstring coverage, style, and test gate.
- [ ] G0 locks official docs path, structure, language, and kernel-only scope.
- [ ] G0 locks Page Brief and external-style-reference rules.
- [ ] Public SDK docstring baseline exists and fails before implementation.
- [ ] Docstring implementation passes the baseline.
- [ ] Official Markdown tree exists under the locked path.
- [ ] Official docs tree structure baseline exists and fails before implementation.
- [ ] Audit log contains the Page Brief template before the first Markdown page.
- [ ] `docs/README.md` indexes the official docs entry.
- [ ] Tutorial docs use current API names and avoid old public surface.
- [ ] No code behavior changes.

## 9. Implementation Plan

1. Complete source audit:
   - enumerate `kernel.sdk.__all__`;
   - enumerate selected `FactGraph` / namespace manager methods;
   - classify which already have docstrings.
2. Scope-freeze G0 decisions.
3. Add G1 baselines:
   - `inspect.getdoc(...)` gate for all 41 `kernel.sdk.__all__` exports plus
     §5.1.1 selected methods;
   - official docs tree structure gate for `docs/official/kernel/`, root
     `index.md`, `quickstart/`, `concepts/`, `how-to/`, `reference/`, and each
     subdirectory `index.md`;
   - audit-log Page Brief template gate.
4. Add docstrings in focused groups:
   - schema/value objects;
   - `FactGraph` / namespace methods;
   - rules/inferences/semantics;
   - persistence and errors.
5. Use per-document cadence for Markdown pages:
   - research source code, module docs, archived blueprints, and external style
     references if useful;
   - record a Page Brief in the audit log;
   - write the page;
   - review against current code and Diátaxis boundary;
   - commit the page or allowed small batch.
6. Create `docs/official/kernel/` skeleton and initial tutorial pages.
7. Add docs index entry.
8. Run focused grep gates and docstring/docs-tree tests.
9. Fill Outcome / Deviations and archive only after all locked docstring batches
   and Markdown pages are complete.

### 9.1 Per-Document Cadence

- Substantive page (roughly >=200 lines or covers >=2 distinct user concepts):
  one page per commit, one Page Brief per page.
- Index / landing page (navigation only): may batch with sibling index pages.
- Reference pages may batch when mechanically similar; otherwise one page per
  commit.
- Docstring changes may batch by logical group:
  - schema/value objects;
  - `FactGraph` entrypoints and namespace methods;
  - rules/inferences/semantics;
  - persistence references and errors.

### 9.2 Page Brief Template

Each substantive Markdown page should record this brief in the audit log before
implementation:

```text
Page Brief — <path>
- Reader goal:
- APIs covered:
- Non-goals:
- Source files checked:
- Module docs checked:
- Archived blueprints checked:
- Example snippets planned:
- Validation method:
- External style reference:
```

## 10. Docs To Update

- `docs/official/kernel/**`
- `docs/README.md`
- `src/kernel/sdk/docs/README.md` if it should point to the official docs
- public SDK docstrings in `src/kernel/sdk/**`

## 11. Outcome / Deviations

Task completion notes will be filled after implementation and verification.
