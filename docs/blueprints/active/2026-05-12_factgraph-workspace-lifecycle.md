# Task Blueprint: FactGraph Workspace Lifecycle

- Status: scoped
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/store.py`
  - `src/kernel/core/store/ledger.py`
  - `src/kernel/authoring/registry_fs.py`
  - `src/kernel/application/`
  - `src/kernel/core/store/_artifact_sidecar.py`
- Related Docs:
  - [docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md](../../references/working/design-points/factgraph-lifecycle-and-assets.zh.md)
  - [docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md](../archive/2026-05-12_public-inference-factgraph-create.md)
  - [docs/blueprints/archive/2026-05-12_inference-wire-registry-vocabulary.md](../archive/2026-05-12_inference-wire-registry-vocabulary.md)
  - [docs/blueprints/archive/2026-05-12_authoring-asset-persistence-facade.md](../archive/2026-05-12_authoring-asset-persistence-facade.md)
- Audit Log:
  - [2026-05-12_factgraph-workspace-lifecycle.audit.md](./2026-05-12_factgraph-workspace-lifecycle.audit.md)

## 1. Problem

The lifecycle/assets sequence has landed three prerequisite slices:

```text
[x] Blueprint 1  Public Inference + FactGraph.create        @ 20bcc7e8
[x] §13.4        Service/registry wire vocabulary rename    @ 8ff5c7fb
[x] Blueprint 2  Authoring asset persistence facade          @ cfd8c35a
[ ] Blueprint 3  FactGraph workspace lifecycle
```

Users can now create a `FactGraph`, bind an authoring registry, save/load rules
and inferences through graph namespaces, and use a consistent public
`Inference` vocabulary. What remains missing is the graph-level lifecycle:

```python
fg = FactGraph.create(schema_classes=[User], path="./workspace")
fg.rules.save(rule)
fg.inferences.save(inference)
fg.save()

fg2 = FactGraph.load("./workspace", schema_classes=[User])
```

Today users must still manually coordinate `ledger_path=...`,
`registry_root=...`, and optional artifact roots. This makes graph state feel
like a set of loose mechanisms rather than one workspace.

Blueprint 3 should add a conservative workspace save/load layer without
accidentally absorbing package export, artifact sidecars, views, audit/evidence
round files, query persistence, or dynamic schema loading.

## 2. Goals

- Lock a first durable FactGraph workspace directory layout.
- Add graph-level workspace construction and persistence:
  - `FactGraph.create(..., path=...)`;
  - `fg.save(path=None)`;
  - `FactGraph.load(path, schema_classes=[...])`.
- Save and load the Level 4 workspace subset:
  - ledger;
  - schema IR / schema digest;
  - registry manifest;
  - saved rules;
  - saved inferences.
- Keep `fg.package.export_package(...)` distinct from workspace save/load.
- Keep `fg.views`, artifact sidecars, audit/evidence files, and query
  persistence outside this first workspace lifecycle slice.
- Preserve Blueprint 2 authoring persistence behavior and direct runtime use.

## 3. Non-goals

- No class-less / dynamic entity facade load.
- No schema mutation, migration, destructive delete, or class generation.
- No query persistence or `fg.queries.*` namespace.
- No view persistence.
- No artifact sidecar save/load.
- No audit/evidence round archive.
- No package export convergence.
- No release packaging or rc cut.
- No changes to `_SDKBatchTx.save(...)`; its transaction meaning remains
  separate from graph/workspace `fg.save(...)`.

## 4. Source Audit

### 4.1 Current Creation Surface

`FactGraph` is still a public alias of `SDKStore`. After Blueprint 2:

- `FactGraph.create(schema_classes=[...], ledger_path=..., registry_root=...)`
  wraps `from_schema_classes(...)`.
- `from_schema_classes(...)` accepts `ledger`, `ledger_path`,
  `artifact_store_root`, `registry_root`, and `registry`.
- `SDKStore.__init__(...)` accepts `artifact_store_root`, `registry_root`, and
  `registry`, but does not know a single workspace root.

Implication: Blueprint 3 can add `path=` as a graph-level umbrella without
removing lower-level explicit knobs.

### 4.2 Ledger Reality

`Ledger(path="./data/ledger.db")` is file-backed SQLite. `Ledger()` is
in-memory. `from_schema_classes(...)` stores `schema_digest` in ledger metadata
when a file-backed ledger is opened or created and rejects schema mismatches on
reopen.

Ledger metadata does not store:

- workspace root;
- registry root;
- artifact sidecar root;
- schema class import paths;
- view definitions;
- package/export metadata.

The ledger has internal SQLite connection state and a private `_path`, but no
public workspace save/copy API.

### 4.3 Registry Reality

`FileAuthoringRegistry(root_dir)` already owns:

```text
registry_manifest.json
schema/schema_ir.json
rules/{rule_id}/{version}.json
inferences/{inference_id}/{version}.json
authoring_apply_events.jsonl
```

Blueprint 2 made this the backend for:

- `fg.rules.save/load/list/get`;
- `fg.inferences.save/load/list/get`;
- schema auto-upsert and digest mismatch rejection.

Implication: a Level 4 workspace can include `registry/` as an existing
mechanism; it should not invent a second registry format.

### 4.4 Artifact Sidecar Reality

`FileArtifactSidecar(root)` stores support artifacts and rule trace artifacts
under sidecar-managed directories (`support/...`, `rule_trace/...`). It also
has retention metadata and garbage-collection behavior.

Including this in workspace save/load would require a separate lifecycle policy:

- whether sidecar files are copied;
- whether GC metadata is preserved;
- whether missing payload/meta pairs are repaired or rejected.

This should be out of scope for Blueprint 3 unless G0 explicitly expands it.

### 4.5 View Reality

`fg.views` is an in-memory `_SDKViewsManager` with
`create/update/delete/get/list`. Views are frozen assertion-id selections, but
they are not registry-backed and not package-backed.

Implication: workspace save/load must explicitly exclude views in this slice or
add a real view persistence format. The conservative choice is exclusion.

### 4.6 Package Export Reality

`fg.package.export_package(...)` delegates to Souffle package export. Package
export is already a separate user-facing concept from graph workspace save/load.
It packages executable/distribution-oriented artifacts, not a continued editing
workspace.

Implication: `fg.save(...)` must not be implemented as an alias or thin wrapper
over package export.

### 4.7 Save Verb Collision

`_SDKBatchTx.save(obj, *, include_deps=True, meta=None)` already exists. It
means "stage this object into the current batch transaction." Graph-level
`fg.save(...)` would mean "persist this FactGraph workspace."

The receiver object disambiguates the verb, but docs and errors must be clear.

### 4.8 Application-Layer Gap

Blueprint 2 introduced `kernel.application.authoring_runtime` for asset
persistence. There is still no `kernel.application.workspace_runtime` or
equivalent orchestration layer for a full workspace.

Given the application-first rule, Blueprint 3 should add a small application
workspace runtime rather than performing filesystem layout directly inside SDK
manager methods.

### 4.9 Load Constraint

Current typed SDK behavior needs Python `Entity` classes. Registry schema IR and
ledger schema digest are not enough to reconstruct SDK entity classes.

Implication: first-slice `FactGraph.load(...)` should require
`schema_classes=[...]`. Class-less load is a separate dynamic-facade design.

## 5. G0 Questions

### 5.1 Q1 — Workspace Root Parameter

Options:

- **W1a — `path=` for graph workspace root.** Use
  `FactGraph.create(..., path="./workspace")`, `fg.save(path=None)`, and
  `FactGraph.load(path, ...)`.
- **W1b — `workspace_root=` everywhere.** More explicit, longer public API.
- **W1c — no create-time workspace root; save/load only.** Users still bind
  ledger/registry separately until first save.

Recommendation: **W1a**. `path=` is short, reads naturally for save/load, and
stays distinct from lower-level `ledger_path=` / `registry_root=`.

G0 decision (2026-05-12): **W1a locked**. `path=` is the graph-level lifecycle root across create/save/load.

### 5.2 Q2 — Workspace Save Scope

Options:

- **W2a — Level 3:** ledger + schema IR only.
- **W2b — Level 4:** ledger + schema IR + registry manifest/rules/inferences.
- **W2c — Level 5:** ledger + schema + registry + artifacts + views + package
  metadata.

Recommendation: **W2b**. Blueprint 2 made registry-backed authoring assets the
product facade, so a workspace that omits them is incomplete. Artifacts, views,
and package metadata have separate lifecycles and should remain out of scope.

G0 decision (2026-05-12): **W2b locked**. Level 4 is the first workspace scope: ledger + schema IR + registry rules/inferences.

### 5.3 Q3 — Directory Layout

Options:

- **W3a — compact v1 layout:**
  ```text
  workspace/
    factgraph_workspace.json
    ledger.db
    registry/
      registry_manifest.json
      schema/schema_ir.json
      rules/...
      inferences/...
  ```
- **W3b — data-subdir layout:**
  ```text
  workspace/
    factgraph_workspace.json
    data/ledger.db
    registry/...
  ```
- **W3c — mirror explicit constructor names:**
  ```text
  workspace/
    ledger/ledger.db
    authoring_registry/...
  ```

Recommendation: **W3a**. It is predictable and small. The registry subtree keeps
its existing format; `ledger.db` is obvious at the root.

G0 decision (2026-05-12): **W3a locked**. The v1 workspace uses root `ledger.db`, root `factgraph_workspace.json`, and a `registry/` subtree.

### 5.4 Q4 — Workspace Manifest

Options:

- **W4a — add `factgraph_workspace.json` with explicit v1 manifest fields.**
  Minimum shape:
  ```json
  {
    "factgraph_workspace_version": "1",
    "save_scope": "level_4",
    "schema_digest": "<digest>",
    "components": {
      "ledger": "ledger.db",
      "registry": "registry/"
    },
    "created_at": "<iso-8601>",
    "last_saved_at": "<iso-8601>"
  }
  ```
- **W4b — no workspace manifest; infer from fixed paths.**
- **W4c — store workspace metadata only in ledger meta.**

Recommendation: **W4a**. A manifest gives `FactGraph.load(...)` one validation
anchor without overloading ledger meta. `save_scope` is intentionally explicit
so future Level 5 work can detect whether artifacts/views are part of a
workspace.

G0 decision (2026-05-12): **W4a locked**. The v1 manifest is required and
records version, save scope, schema digest, component paths, and timestamps.

### 5.5 Q5 — Create-Time `path=` Behavior

Options:

- **W5a — `FactGraph.create(..., path=...)` binds ledger and registry to the
  workspace default paths.**
- **W5b — `path=` only stores a future save target; ledger remains in-memory
  until save.**
- **W5c — reject `path=` on create; only load/save understand path.**

Recommendation: **W5a**. Users expect a path-created graph to be file-backed
from the start. It also avoids copying an in-memory ledger on every save.

G0 decision (2026-05-12): **W5a locked**. `FactGraph.create(..., path=...)` binds both ledger and registry to the workspace defaults.

### 5.6 Q6 — Explicit Path Override Interaction

Options:

- **W6a — allow `path=` with explicit `ledger_path=` / `registry_root=` only
  when they match the workspace defaults; otherwise reject.**
- **W6b — explicit paths override workspace defaults.**
- **W6c — forbid combining `path=` with any lower-level path knobs.**

Recommendation: **W6a**. It mirrors Blueprint 2's registry conflict pattern and
prevents ambiguous workspaces.

G0 decision (2026-05-12): **W6a locked**. Explicit lower-level paths may accompany `path=` only when they match workspace defaults.

### 5.7 Q7 — `fg.save(path=None)` Semantics

Options:

- **W7a — no-arg save requires a bound workspace path; `fg.save(path)` saves and
  binds future saves to that path.**
- **W7b — no-arg save writes only if ledger is file-backed, even without a
  workspace manifest.**
- **W7c — always require `path` for save.**

Recommendation: **W7a**. This supports ergonomic `create(path=...)` / `save()`
while keeping unbound in-memory graphs explicit. G2 should lock the unbound
error anchor: `"workspace path not bound; pass fg.save(path=...) or create with FactGraph.create(path=...)"`.

G0 decision (2026-05-12): **W7a locked**. No-arg save requires a bound workspace path; `fg.save(path)` saves and binds future saves.

### 5.8 Q8 — Ledger Save Mechanics

Options:

- **W8a — save to the workspace ledger path using SQLite backup/copy semantics,
  preserving the source graph in memory.**
- **W8b — require the graph already be file-backed at the target path.**
- **W8c — reconstruct the ledger through public append APIs.**

Recommendation: **W8a**. It allows `FactGraph.create(..., path=...)` and
in-memory graphs to converge on the same persisted layout. G2 should implement
this through a helper, not by ad hoc row replays. If the bound ledger is already
the workspace target `ledger.db`, save should only flush/checkpoint as needed;
SQLite backup/copy applies when the source ledger and target workspace ledger
paths differ, such as `fg.save(other_path)`.

G0 decision (2026-05-12): **W8a locked**. Ledger persistence uses helper-mediated SQLite backup/copy only when source and target differ.

### 5.9 Q9 — Registry Save Mechanics

Options:

- **W9a — copy/sync the bound registry subtree into `workspace/registry`, with
  schema digest validation.**
- **W9b — require the graph already be bound to `workspace/registry`.**
- **W9c — rebuild registry assets from in-memory SDK objects only.**

Recommendation: **W9a**. It supports saving graphs that were created with a
separate `registry_root=` while preserving Blueprint 2's registry as the source
of persisted rules/inferences.

G0 decision (2026-05-12): **W9a locked**. Registry persistence syncs/copies the bound registry subtree into `workspace/registry` with schema validation.

### 5.10 Q10 — Registry-Less Save

Options:

- **W10a — allow save without an authoring registry; create an empty
  `registry/` containing schema IR only.**
- **W10b — reject save unless the graph is bound to a registry.**
- **W10c — save ledger only when no registry exists.**

Recommendation: **W10a**. A graph can legitimately have no saved rules or
inferences yet. The workspace should still be complete enough to load and later
save assets.

G0 decision (2026-05-12): **W10a locked**. Registry-less graphs can save a complete empty registry with schema IR.

### 5.11 Q11 — Load Shape

Options:

- **W11a — `FactGraph.load(path, schema_classes=[...])` required in first
  slice.**
- **W11b — `FactGraph.load(path)` class-less dynamic mode.**
- **W11c — `FactGraph.load(path, schema_ir=...)` but no Python classes.**

Recommendation: **W11a**. Current SDK object hydration is class-based. Dynamic
or schema-IR-only loading should be a later blueprint.

G0 decision (2026-05-12): **W11a locked**. First-slice `FactGraph.load(...)` requires `schema_classes=[...]`.

### 5.12 Q12 — Load Validation

Options:

- **W12a — validate workspace manifest, ledger schema digest, registry schema
  digest, and provided class schema digest all match.**
- **W12b — validate only ledger schema digest against provided classes.**
- **W12c — best-effort load with warnings.**

Recommendation: **W12a**. Workspace load should fail loudly if its three schema
anchors disagree.

G0 decision (2026-05-12): **W12a locked**. Load validates manifest, ledger digest, registry digest, and class schema digest as one schema anchor set.

### 5.13 Q13 — Artifact Sidecars

Options:

- **W13a — exclude artifact sidecars in Blueprint 3.**
- **W13b — include sidecars by copying the artifact root into workspace.**
- **W13c — include only support artifacts, not rule traces.**

Recommendation: **W13a**. Sidecar retention and repair semantics need their own
scope. Excluding them keeps workspace save/load focused.

G0 decision (2026-05-12): **W13a locked**. Artifact sidecars are excluded from Blueprint 3.

### 5.14 Q14 — Views

Options:

- **W14a — exclude `fg.views` from Blueprint 3 workspace persistence.**
- **W14b — persist views in `workspace/views.json`.**
- **W14c — persist views only when explicitly requested.**

Recommendation: **W14a**. Views are currently in-memory only. Persisting them
requires a separate format and compatibility promise.

G0 decision (2026-05-12): **W14a locked**. `fg.views` remains in-memory and is excluded from workspace persistence.

### 5.15 Q15 — Audit / Evidence Round Files

Options:

- **W15a — exclude audit/evidence files in Blueprint 3.**
- **W15b — include all file-backed evidence/audit artifacts.**
- **W15c — include only package-exportable audit files.**

Recommendation: **W15a**. Explain/evidence is a separate future thread and
should not be folded into workspace lifecycle by accident.

G0 decision (2026-05-12): **W15a locked**. Audit/evidence files are excluded from Blueprint 3.

### 5.16 Q16 — Package Export Boundary

Options:

- **W16a — document `fg.save/load` as workspace persistence, distinct from
  `fg.package.export_package(...)`.**
- **W16b — make package export consume workspace manifests.**
- **W16c — implement workspace save as package export.**

Recommendation: **W16a**. Package export is distribution/reproduction; workspace
save/load is continued editing/running.

G0 decision (2026-05-12): **W16a locked**. Workspace save/load is documented as distinct from package export.

### 5.17 Q17 — Application-Layer Ownership

Options:

- **W17a — add `kernel.application.workspace_runtime` for manifest/layout
  validation and save/load path resolution.**
- **W17b — implement directly in `SDKStore.save/load`.**
- **W17c — implement under `kernel.authoring` only.**

Recommendation: **W17a**. It follows the application-first runtime authority
pattern and keeps the SDK shell ergonomic.

G0 decision (2026-05-12): **W17a locked**. Workspace layout and validation belong in `kernel.application.workspace_runtime`.

### 5.18 Q18 — Static/Class Save Helper

Options:

- **W18a — instance method only: `fg.save(path=None)`.**
- **W18b — add both `fg.save(...)` and `FactGraph.save(fg, ...)`.**
- **W18c — class/static helper only.**

Recommendation: **W18a**. Python users expect instance lifecycle methods. A
static helper adds surface without a clear use case.

G0 decision (2026-05-12): **W18a locked**. Only instance `fg.save(path=None)` is added; no `FactGraph.save(fg, ...)` helper.

### 5.19 Q19 — `from_schema_classes(...)` Path Parity

Options:

- **W19a — add `path=` to `from_schema_classes(...)` as full parity with
  `FactGraph.create(...)`.**
- **W19b — keep `path=` on `FactGraph.create(...)` only; leave
  `from_schema_classes(...)` as the lower-level explicit constructor.**
- **W19c — remove public `from_schema_classes(...)` in this slice.**

Recommendation: **W19b**. `FactGraph.create(...)` is the product lifecycle
constructor. Extending `from_schema_classes(...)` would expand an older
class-first surface exactly as the lifecycle API is becoming canonical.

G0 decision (2026-05-12): **W19b locked**. `path=` stays on `FactGraph.create(...)`; `from_schema_classes(...)` is not expanded.

## 6. Boundaries And Invariants

- `fg.save(...)` is graph/workspace persistence, not batch transaction staging.
- `_SDKBatchTx.save(...)` remains unchanged.
- `fg.package.export_package(...)` remains package/export behavior, not
  workspace save.
- `FactGraph.load(...)` requires Python schema classes in this slice.
- Saved workspace schema anchors must agree: manifest, ledger, registry, and
  provided classes.
- Workspace save/load includes authoring registry assets but excludes views,
  artifacts, audit/evidence files, queries, and package metadata.
- `fg.rules.save/load/list/get` and `fg.inferences.save/load/list/get` continue
  to work exactly as Blueprint 2 defined them.
- `SavedRuleRef` / `SavedInferenceRef` remain load handles, not runtime
  selectors.
- Direct runtime value-object use remains registry-free.
- Public service/registry inference vocabulary remains unchanged.
- `fg.save()` on an unchanged bound workspace is idempotent: it may update
  `last_saved_at` in the workspace manifest, but it must not corrupt or
  unnecessarily rewrite ledger/registry payloads.
- `FactGraph.create(..., path=...)` owns the new graph-level path API;
  `from_schema_classes(...)` remains the explicit lower-level constructor in
  this slice.

## 7. Acceptance

- [x] G0 locks workspace path parameter and directory layout.
- [x] G0 locks save scope.
- [x] G0 locks create/save/load behavior for bound and unbound graphs.
- [x] G0 locks schema validation anchors.
- [x] G0 locks artifacts/views/audit/package exclusions.
- [x] G0 locks application-layer ownership.
- [ ] G1 adds red tests for `FactGraph.create(..., path=...)`.
- [ ] G1 adds red tests for `fg.save(...)`.
- [ ] G1 adds red tests for `FactGraph.load(...)`.
- [ ] G1 adds guard tests for Blueprint 2 authoring persistence.
- [ ] G1 adds guard tests for package/export and batch save boundaries.
- [ ] G2 implements only locked workspace lifecycle behavior.
- [ ] G3 updates SDK, authoring, package, and lifecycle docs.
- [ ] G4 fills §10, marks implemented, and archives this blueprint pair.

## 8. Implementation Plan

Draft sequence, subject to G0:

1. G1 red baseline:
   - workspace layout assertions;
   - create/save/load public behavior;
   - schema mismatch errors;
   - exclusion guards for views/artifacts/audit/package;
   - Blueprint 2 persistence guards.
2. G2 application workspace runtime:
   - define workspace manifest DTO/shape;
   - add path resolution and schema-anchor validation helpers;
   - add ledger copy/backup helper;
   - add registry copy/sync helper.
3. G2 SDK binding:
   - add `path=` to `FactGraph.create(...)`;
   - leave `from_schema_classes(...)` as the lower-level explicit constructor
     unless G0 changes Q19;
   - add `fg.save(path=None)`;
   - add `FactGraph.load(path, schema_classes=[...])`;
   - store bound workspace path on `SDKStore`.
4. G2 guards and cleanup:
   - ensure lower-level `ledger_path=` / `registry_root=` paths remain valid;
   - ensure `fg.rules.*` / `fg.inferences.*` keep using the bound registry;
   - ensure batch `tx.save(...)` remains unchanged.
5. G3 docs sync:
   - SDK user guide;
   - API surface;
   - read/write and ingest docs;
   - authoring docs;
   - package/export docs;
   - lifecycle design-point.
6. G4 close-out and archive.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/authoring/docs/01_overview.md`
- package/export docs if they mention persistence or portability boundaries
- `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`
- `docs/README.md` if a durable docs entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Validation:
- Commit lineage:
- Deviations:
- Archive notes:
