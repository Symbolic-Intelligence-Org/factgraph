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

This slice owns `db/` and the manifest relationship to `db/`. It may create or reserve the `views/` component path only as a manifest/layout placeholder. Concrete creation of an empty `views/` directory versus reserving only the manifest entry is an implementation-preflight decision; actual view object persistence belongs to the view slice.

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

Transaction object filenames use filesystem-safe raw lowercase hex segments:

- path: `db/objects/tx/<64hex>.json`
- `<64hex> = tx_id.removeprefix("tx:")`
- object content carries and validates the full `tx:<hex>` token
- filename/content mismatch is an error

Exact transaction object JSON schema remains a scoped implementation decision, but the filename convention and full-token-in-content rule are locked by this blueprint.

### 5.4 `db/objects/schema/`

`db/objects/schema/` stores immutable compiled schema snapshots. The source bytes must be the canonical compiled schema IR bytes used by `schema_digest(...)`.

This path replaces the live workspace role currently played by `registry/schema/schema_ir.json`.

Rules:

- Write the schema object when a tx first references a `schema_digest`.
- If the schema object already exists, do not overwrite it.
- Do not store authoring Python source in Database objects.
- Do not invent a parallel schema digest algorithm.

Schema object filenames use filesystem-safe raw lowercase hex segments:

- path: `db/objects/schema/<64hex>.json`
- `<64hex> = schema_digest.removeprefix("sha256:")`
- object content is exactly `canonicalize_schema_ir_jcs(schema_ir)` bytes
- object content must validate back to the full `sha256:<hex>` schema digest
- filename/content mismatch is an error

This explicitly does not reuse the registry presentation format (`data + b"\n"`) or `registry_manifest.json` envelope.

### 5.5 `db/refs/head.txt`

`db/refs/head.txt` is the mutable Database head pointer.

Rules:

- Its content is the current head `tx_id`.
- It is the only mutable Database ref file in this slice.
- Updates must be atomic at the file-write level.
- Implement using a sibling temp file followed by `os.replace(...)`;best-effort fsync should be used where available and documented where not available.
- Update `head.txt` only after the referenced tx object exists and validates.

Slice 2 implementation must adapt the DB identity substrate's `Database.create(...)`, `Database.open(...)`, `Database.head()`, and `Database.commit_assertions(...)` storage placement so the durable head pointer is read from and written to `db/refs/head.txt` rather than `ledger_meta`. The identity computation formulas from slice 1 (`canonical_bytes_dbtx_v1(...)`, `canonical_bytes_dbdata_v1(...)`, and `canonical_bytes_assertion_v1(...)`) are not changed.

`Database.head()` resolution under the new layout is:

1. read `db/refs/head.txt` to obtain the full `tx:<hex>` token;
2. read `db/objects/tx/<64hex>.json`, using the raw hex suffix as the filename segment;
3. validate the tx object carries the same `tx_id`;
4. read `data_digest` and `schema_digest` from the tx object;
5. validate schema context and return `DatabaseValue(db_id, tx_id, schema_digest, data_digest)`.

Ledger metadata may be retained as a legacy compatibility cache only. It must not be the durable source of head identity for new-layout workspaces.

Cross-file atomicity across transaction object write, `head.txt` update, and `db/assertions.db` mutation is an implementation-preflight question. This blueprint locks per-file atomic head-write rules and records that the slice inherits the DB identity substrate's current `commit_assertions(...)` atomicity limitation until a storage-hardening decision changes it.

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
- New-layout `Database.create(path=...)` / `Database.open(path=...)` take the workspace root path. They resolve `db/`, `db/assertions.db`, object paths, and refs internally. Direct `db/` subdirectory paths and direct SQLite paths are internal helper concerns, not the public new-layout convention.
- Migration must not silently discard `registry/rules/`, `registry/inferences/`, `registry_manifest.json`, or `authoring_apply_events.jsonl`.
- New-layout save must not call `sync_registry_to_workspace(...)` as-is for registry copy/delete semantics. It must either leave legacy registry data untouched, use a non-destructive schema-only migration helper, raise an explicit migration-required error, or require an archive/export step before destructive movement.
- If dual-format load/save is implemented, the format detection rules must be explicit and tested.

## 6. Boundaries And Invariants

- `db/objects/` files are content-addressed write-once;do not overwrite or delete them in this slice.
- `db/refs/head.txt` is the only mutable Database ref file.
- `Database.head()` resolves `head.txt -> tx object -> DatabaseValue`;ledger metadata is not the durable head source.
- `db/assertions.db` is mutable index state and is not an identity source.
- Compiled schema snapshots move to Database objects;object bytes are exactly `canonicalize_schema_ir_jcs(schema_ir)`, and authoring source remains user code.
- Final manifest does not duplicate Database identity or snapshot identity.
- DB identity formulas remain unchanged while head storage moves from `ledger_meta` to `db/refs/head.txt`.
- New-layout `Database.create(...)` / `Database.open(...)` public path semantics are workspace-root semantics.
- Tx and schema object filenames use raw 64-hex segments;object content carries and validates the full token.
- `components.registry` removal is governed by Q6/Q8 phases;do not remove it early.
- New-layout save must not reuse destructive registry deletion/copy semantics from `sync_registry_to_workspace(...)`.
- View persistence is out of scope except for reserving the target `views/` component concept.
- No public `view=` APIs, evidence metadata carriers, or rule-expression carriers are introduced.
- Legacy `Ledger` can remain the SQLite implementation substrate, but root-level `ledger.db` is not the target layout.
- Per-file writes for objects and head refs use temp sibling paths plus atomic replace;cross-file atomicity across object/ref/index writes remains a future storage-hardening concern.
- If implementation keeps same-path save idempotence or SQLite checkpoint behavior, those are compatibility details, not identity semantics.

## 7. Acceptance

- [ ] Target workspace layout is defined in code or documented implementation constants:
  - `db/objects/tx/`
  - `db/objects/schema/`
  - `db/refs/head.txt`
  - `db/assertions.db`
- [ ] Compiled schema snapshots persist under Database-owned schema object paths, not only under `registry/schema/schema_ir.json`.
- [ ] Transaction objects persist under `db/objects/tx/<64hex>.json`, carry the full `tx_id`, and validate filename/content match.
- [ ] Object writes are content-addressed and write-once;tests cover existing-object idempotence and conflict behavior.
- [ ] Schema objects persist under `db/objects/schema/<64hex>.json` with exact `canonicalize_schema_ir_jcs(schema_ir)` payload bytes and validate filename/content match.
- [ ] `db/refs/head.txt` is updated via temp sibling path plus atomic replace and only after the referenced tx object exists.
- [ ] `Database.head()` resolves `head.txt -> tx object -> DatabaseValue`, rather than reading durable head identity from ledger metadata.
- [ ] New-layout `Database.create(...)` / `Database.open(...)` use workspace-root path semantics and are tested.
- [ ] `db/assertions.db` is treated as rebuildable mutable index, not identity source.
- [ ] Final manifest target shape excludes top-level `db_id`, `schema_digest`, `data_digest`, and `tx_id`.
- [ ] Manifest transition behavior around `components.registry` follows Q6 and does not hard-remove registry during Q8 Phase 1.
- [ ] New-layout save/load does not reuse destructive `sync_registry_to_workspace(...)` registry deletion/copy semantics.
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
