# Task Blueprint: DB Workspace Physical Layout

- Status: draft
- Created: 2026-05-20
- Last Updated: 2026-05-20
- Related Modules:
  - `src/factgraph/application/workspace_runtime.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/authoring/registry_fs.py`
  - `src/factgraph/core/store/database.py`
  - `src/factgraph/core/store/ledger.py`
  - `src/factgraph/core/schema/schema_ir.py`
- Related Docs:
  - [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](../../audit/2026-05-20_database-view-design-vs-shipped-runtime.md)
  - [docs/audit/2026-05-20_post-q-db-view-synthesis.md](../../audit/2026-05-20_post-q-db-view-synthesis.md)
  - [docs/blueprints/active/2026-05-20_db-identity-substrate.md](./2026-05-20_db-identity-substrate.md)
  - [docs/decisions/2026-05-20_q1-database-class-boundary-decision.md](../../decisions/2026-05-20_q1-database-class-boundary-decision.md)
  - [docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md](../../decisions/2026-05-20_q3-tx-identity-primitives-decision.md)
  - [docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md](../../decisions/2026-05-20_q4-frozenassertionview-shape-decision.md)
  - [docs/decisions/2026-05-20_q6-registry-workspace-migration-decision.md](../../decisions/2026-05-20_q6-registry-workspace-migration-decision.md)
  - [docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md](../../decisions/2026-05-20_q8-savedrule-existence-governance-decision.md)
  - [docs/references/working/design-points/database-view-fg-layered-architecture.zh.md](../../references/working/design-points/database-view-fg-layered-architecture.zh.md)
- Audit Log:
  - [2026-05-20_db-workspace-physical-layout.audit.md](./2026-05-20_db-workspace-physical-layout.audit.md)

## 1. Problem

The DB identity substrate slice implemented `Database`, `DatabaseValue`, transaction/data/assertion identity protocols, and canonical durable assertion records, but it intentionally left workspace physical layout out of scope.

Shipped workspace persistence is still the legacy level-4 layout:

- root-level `ledger.db`;
- root-level `registry/`;
- `factgraph_workspace.json` with top-level `schema_digest`;
- `components.ledger` and `components.registry` as required manifest entries;
- compiled schema snapshot stored as `registry/schema/schema_ir.json`.

The design target is a Database-owned Git-style layout where transaction objects and schema snapshots live under `db/objects/`, the current head is a mutable ref under `db/refs/`, and SQLite is a rebuildable index under `db/assertions.db`.

This blueprint scopes the second implementable DB/view slice: workspace physical layout and schema snapshot migration, built on the already implemented DB identity substrate.

## 2. Goals

- Define the target Database subtree:
  - `db/meta.json`
  - `db/objects/tx/`
  - `db/objects/schema/`
  - `db/refs/head.txt`
  - `db/assertions.db`
- Persist compiled schema snapshots as content-addressed Database objects.
- Persist transaction objects as content-addressed Database objects.
- Move the mutable head pointer into `db/refs/head.txt`.
- Treat `db/assertions.db` as the mutable SQLite index layer, not as cross-process identity.
- Define the target `factgraph_workspace.json` shape and the transition rules for `components.registry`.
- Preserve existing user workspaces during migration;do not silently delete registry data or legacy `ledger.db`.
- Keep this slice limited to physical layout and schema persistence. Later slices own views, attach lifecycle, registry deprecation execution, and cross-doc evidence/rule-expression seams.

## 3. Non-goals

- Do not implement `FrozenAssertionView`, view object persistence, named view registry, or view-scoped runtime behavior. This slice may reserve `views/` / `components.views` as a target layout concept, but it must not implement `views/objects/<view_digest>.json`.
- Do not implement `FactGraph.attach(...)`, snapshot attach, or view-scoped attach.
- Do not implement public `fg.read.find(view=...)` or `fg.eval.evaluate(view=...)` semantics.
- Do not implement `EvaluateResult`, `EvidenceGraph.metadata`, stale/out-of-scope failure envelopes, or `rule_set_digest`.
- Do not implement Q8 Phase 2 SavedRule removal. This slice must not remove live rule/inference registry write surfaces.
- Do not silently remove `registry/`, `registry_manifest.json`, or `authoring_apply_events.jsonl` before the Q6 phase conditions are met.
- Do not introduce Database retract/update/schema-migration public methods.
- Do not change the DB identity protocols from the implemented DB identity substrate slice.
- Do not claim full rebuild-from-objects tooling unless the implementation actually provides replay coverage.

## 4. Current Context

### 4.1 Shipped workspace layout

`workspace_runtime.py` currently defines:

- `WORKSPACE_LEDGER = "ledger.db"` and `WORKSPACE_REGISTRY = "registry/"` at `src/factgraph/application/workspace_runtime.py:18-19`.
- `WorkspacePaths` with `manifest`, `ledger`, and `registry` fields at `workspace_runtime.py:26-32`.
- `resolve_workspace_paths(...)` mapping workspace roots to root-level `ledger.db` and `registry/` at `workspace_runtime.py:34-43`.
- `workspace_manifest_payload(...)` writing top-level `schema_digest` plus `components.ledger` and `components.registry` at `workspace_runtime.py:46-65`.
- `validate_workspace_manifest(...)` requiring `components.ledger == "ledger.db"` and `components.registry == "registry/"` at `workspace_runtime.py:87-116`.
- `save_workspace(...)` copying a ledger to root-level `ledger.db`, syncing a `FileAuthoringRegistry`, and writing the legacy manifest at `workspace_runtime.py:160-177`.
- `load_workspace(...)` requiring both root-level ledger and registry paths at `workspace_runtime.py:180-187`.

### 4.2 Shipped SDK coupling

`SDKStore.load(...)` currently calls `app_load_workspace(...)`, validates registry schema, and opens `Ledger(path=paths.ledger)` at `src/factgraph/sdk/store.py:860-895`.

`SDKStore.save(...)` calls `app_save_workspace(...)`, passes `schema_ir`, then rebinds `_authoring_registry = FileAuthoringRegistry(paths.registry)` at `src/factgraph/sdk/store.py:2063-2090`.

This means the shipped SDK treats workspace save/load as ledger + registry persistence, not as Database object/ref persistence.

### 4.3 Shipped schema snapshot location

`FileAuthoringRegistry.upsert_schema_ir(...)` canonicalizes schema IR, computes `schema_digest`, writes fixed path `schema/schema_ir.json`, and records that path in `registry_manifest.json` at `src/factgraph/authoring/registry_fs.py:47-67`.

This is exactly the A20(E) migration target: the compiled schema snapshot must move from `registry/schema/schema_ir.json` to `db/objects/schema/<schema_digest>.json`.

### 4.4 Design target

The design's workspace layout target is:

- `db/objects/` content-addressed write-once objects;
- `db/objects/tx/<tx_id>.json` transaction objects;
- `db/objects/schema/<schema_digest>.json` compiled schema snapshots;
- `db/refs/head.txt` as the only mutable Database ref file;
- `db/assertions.db` as mutable SQLite index layer;
- minimal `factgraph_workspace.json` with `components.{db, views}` and timestamps;
- registry removed from the final workspace layout after schema migrates and Q8/Q6 phases complete.

The post-Q synthesis classifies I13, A16(B), A17, A19, and A20(E) as blueprint-eligible physical-layout work, while warning that A19's `components.registry` removal depends on Q6/Q8 timing.

## 5. Proposed Shape

### 5.1 Target layout

The target Database workspace subtree is:

```text
<workspace>/
├── factgraph_workspace.json
├── db/
│   ├── meta.json
│   ├── refs/
│   │   └── head.txt
│   ├── objects/
│   │   ├── tx/
│   │   └── schema/
│   └── assertions.db
└── views/
```

This slice owns `db/` and the manifest relationship to `db/`. It may create or reserve the `views/` component path only as a manifest/layout placeholder. Actual view object persistence belongs to the view slice.

### 5.2 `db/meta.json`

`db/meta.json` should carry Database-local identity and creation metadata that must not be duplicated in the top-level manifest:

- `db_id`
- workspace/database format version
- creation timestamp or equivalent non-identity metadata

`db_id` remains the durable Database identity established by the DB identity substrate;the top-level manifest must not duplicate it.

### 5.3 `db/objects/tx/`

`db/objects/tx/` stores immutable transaction objects. Each object must be content-addressed by the `tx_id` from the DB identity substrate.

Each transaction object must carry enough Database-owned data to replay or validate the head chain at the DB layout layer:

- `tx_id`
- `parent_tx_id`
- `schema_digest`
- `data_digest`
- added assertion digests / assertion ids sufficient to reconstruct the tx's effect

Exact JSON schema, filename encoding, and whether filenames use full tokens (`tx:<hex>`) or raw hex segments are implementation-preflight decisions. The object content must carry the full token form even if filenames use a filesystem-safe derived segment.

### 5.4 `db/objects/schema/`

`db/objects/schema/` stores immutable compiled schema snapshots. The source bytes must be the canonical compiled schema IR bytes used by `schema_digest(...)`.

This path replaces the live workspace role currently played by `registry/schema/schema_ir.json`.

Rules:

- Write the schema object when a tx first references a `schema_digest`.
- If the schema object already exists, do not overwrite it.
- Do not store authoring Python source in Database objects.
- Do not invent a parallel schema digest algorithm.

Exact JSON/byte envelope and filename encoding are implementation-preflight decisions, but the stored content must round-trip the compiled schema snapshot required for Database replay and validation.

### 5.5 `db/refs/head.txt`

`db/refs/head.txt` is the mutable Database head pointer.

Rules:

- Its content is the current head `tx_id`.
- It is the only mutable Database ref file in this slice.
- Updates must be atomic at the file-write level.
- If implementation cannot guarantee atomic writes on a target filesystem, that limitation must be recorded before moving to `scoped`.

### 5.6 `db/assertions.db`

`db/assertions.db` is the mutable SQLite index layer.

Rules:

- It replaces root-level `ledger.db` for the new layout.
- It does not participate in cross-process identity.
- It must remain logically rebuildable from `db/objects/tx/` and schema objects, even if full replay tooling is deferred.
- Legacy `Ledger` may remain the SQLite implementation substrate.
- Legacy root-level `ledger.db` must not be silently deleted during migration.

### 5.7 Manifest shape and registry transition

The target final manifest is:

```json
{
  "workspace_version": "...",
  "components": {
    "db": "db/",
    "views": "views/"
  },
  "created_at": "...",
  "last_saved_at": "..."
}
```

It must not duplicate:

- `db_id`
- `schema_digest`
- `data_digest`
- current `tx_id`

However, Q6 requires a phased transition:

- During Q8 Phase 1, `components.registry` may remain because rule/inference persistence is still in its deprecation window.
- During the schema-only transition, `components.registry` may remain only while schema persistence still depends on `registry/schema/schema_ir.json`.
- After A20(E) schema migration and Q8 Phase 2 rule/inference removal, `components.registry` exits the manifest.

This blueprint can define the target manifest and the migration boundary, but it must not hard-remove `components.registry` unless the implementation scope also satisfies the Q6 phase prerequisites.

### 5.8 Legacy compatibility

This slice must preserve existing workspaces unless a migration step explicitly handles them.

Compatibility expectations:

- Existing `factgraph_workspace.json` + `ledger.db` + `registry/` workspaces remain loadable or fail with a clear migration error.
- New-layout workspaces must not be mistaken for legacy level-4 workspaces.
- Migration must not silently discard `registry/rules/`, `registry/inferences/`, `registry_manifest.json`, or `authoring_apply_events.jsonl`.
- If dual-format load/save is implemented, the format detection rules must be explicit and tested.

## 6. Boundaries And Invariants

- `db/objects/` files are content-addressed write-once;do not overwrite or delete them in this slice.
- `db/refs/head.txt` is the only mutable Database ref file.
- `db/assertions.db` is mutable index state and is not an identity source.
- Compiled schema snapshots move to Database objects;authoring source remains user code.
- Final manifest does not duplicate Database identity or snapshot identity.
- `components.registry` removal is governed by Q6/Q8 phases;do not remove it early.
- View persistence is out of scope except for reserving the target `views/` component concept.
- No public `view=` APIs, evidence metadata carriers, or rule-expression carriers are introduced.
- Legacy `Ledger` can remain the SQLite implementation substrate, but root-level `ledger.db` is not the target layout.
- If implementation keeps same-path save idempotence or SQLite checkpoint behavior, those are compatibility details, not identity semantics.

## 7. Acceptance

- [ ] Target workspace layout is defined in code or documented implementation constants:
  - `db/objects/tx/`
  - `db/objects/schema/`
  - `db/refs/head.txt`
  - `db/assertions.db`
- [ ] Compiled schema snapshots persist under Database-owned schema object paths, not only under `registry/schema/schema_ir.json`.
- [ ] Transaction objects persist under Database-owned tx object paths and carry the full `tx_id`.
- [ ] Object writes are content-addressed and write-once;tests cover existing-object idempotence and conflict behavior.
- [ ] `db/refs/head.txt` is updated atomically or the implementation records why atomicity is not yet satisfied.
- [ ] `db/assertions.db` is treated as rebuildable mutable index, not identity source.
- [ ] Final manifest target shape excludes top-level `db_id`, `schema_digest`, `data_digest`, and `tx_id`.
- [ ] Manifest transition behavior around `components.registry` follows Q6 and does not hard-remove registry during Q8 Phase 1.
- [ ] Legacy workspaces either remain loadable or fail with an explicit migration-required error.
- [ ] No view persistence, attach lifecycle, SavedRule removal, evidence metadata, or rule-expression API is introduced.
- [ ] Affected module docs are updated.
- [ ] `docs/README.md` is updated if this blueprint creates a new durable docs entry beyond the active blueprint pair.

## 8. Implementation Plan

This section is draft until implementation preflight completes. Before moving to `scoped`, perform a fresh source audit of `workspace_runtime.py`, `SDKStore.save/load`, `FileAuthoringRegistry.upsert_schema_ir(...)`, DB identity substrate APIs, and any migration helpers touched.

1. Define target workspace path model.
   - Add or revise path DTOs/constants for `db/`, object dirs, refs, assertions index, and manifest.
   - Keep legacy path constants available for migration/compatibility.
2. Define Database object writers/readers.
   - Add write-once helpers for schema objects and tx objects.
   - Decide filename encoding during preflight.
   - Keep full token forms inside object content.
3. Define head ref handling.
   - Add read/write helpers for `db/refs/head.txt`.
   - Decide atomic write strategy during preflight.
4. Define manifest target and transition logic.
   - Add final manifest shape.
   - Add explicit legacy vs target manifest detection.
   - Preserve Q6 registry phase boundaries.
5. Integrate SQLite index placement.
   - Place new-layout Ledger/SQLite index at `db/assertions.db`.
   - Keep root-level `ledger.db` compatibility separate.
6. Add migration/compatibility tests.
   - New-layout save/load.
   - Legacy workspace detection.
   - Registry transition behavior.
   - Schema object idempotence/conflict behavior.
7. Update module docs.
   - Update workspace/application docs.
   - Update core/store docs if Database open/create behavior changes.

## 9. Docs To Update

- `src/factgraph/application/docs/README.md` or a new workspace runtime module doc.
- `src/factgraph/core/store/docs/README.md` if `Database.create/open` semantics change.
- `src/factgraph/sdk/docs/README.md` if public `fg.save(...)` / `FactGraph.load(...)` behavior changes.
- `docs/README.md` if a new durable docs entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- final landed layout;
- migration behavior;
- compatibility behavior;
- any deviations from target A16/A17/A19/A20(E);
- remaining follow-up slices.
