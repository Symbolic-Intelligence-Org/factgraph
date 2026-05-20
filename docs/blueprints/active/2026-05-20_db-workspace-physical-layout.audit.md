# Task Blueprint Audit: DB Workspace Physical Layout

- Blueprint: [2026-05-20_db-workspace-physical-layout.md](./2026-05-20_db-workspace-physical-layout.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-20 | draft | Blueprint created | Scope derived from post-Q synthesis slice 2: workspace physical layout and schema object migration. |

## Decision Notes

### 2026-05-20 — Scope limited to workspace physical layout

This blueprint intentionally covers the second synthesis slice:

- `db/objects/tx/`
- `db/objects/schema/`
- `db/refs/head.txt`
- `db/assertions.db`
- manifest target shape and registry transition boundary
- schema snapshot migration from registry path to Database object path

It excludes view object implementation, `FactGraph.attach(...)`, public `view=` APIs, SavedRule removal execution, evidence metadata, and rule-expression seams.

### 2026-05-20 — Upstream decisions consumed

The draft consumes:

- Q1 (`13dde310`): `Database` is a new boundary above `Ledger`.
- Q3 (`4ba11428`): `tx_id`, `data_digest`, and schema/assertion identity sources are Database-owned identity inputs.
- Q4 (`b2a16bb3`): view identity exists, but this slice does not implement view persistence.
- Q6 (`917ada19`): registry exits in phases;`components.registry` cannot disappear before Q8/Q6 conditions are satisfied.
- Q8 (`8be96760`): SavedRule persistence exits gradually;schema persistence is migrated, not removed.
- DB identity substrate implementation (`6e4642d7`) and closure (`f3c4375f`): `Database` and identity primitives now exist as the substrate for this layout work.

### 2026-05-20 — Current shipped drift verified before drafting

Source reread before drafting verified:

- current workspace constants are root-level `ledger.db` + `registry/` at `src/factgraph/application/workspace_runtime.py:15-19`;
- current manifest writes top-level `schema_digest` and `components.ledger` / `components.registry` at `workspace_runtime.py:46-65`;
- manifest validation requires both legacy components at `workspace_runtime.py:87-116`;
- save/load still copy `Ledger` and `FileAuthoringRegistry` paths at `workspace_runtime.py:160-187`;
- `SDKStore.load(...)` and `SDKStore.save(...)` remain coupled to `app_load_workspace(...)` / `app_save_workspace(...)` at `src/factgraph/sdk/store.py:860-895` and `:2063-2090`;
- `FileAuthoringRegistry.upsert_schema_ir(...)` stores schema at `registry/schema/schema_ir.json` and records the entry in `registry_manifest.json` at `src/factgraph/authoring/registry_fs.py:47-67`.

### 2026-05-20 — Manifest target vs Q6 transition

The design target removes `components.registry`, but Q6 selected phased registry exit.

This blueprint therefore records both:

- final A19 target manifest: `components.{db, views}` only, with no top-level `db_id`, `schema_digest`, `data_digest`, or `tx_id`;
- transition constraint: `components.registry` may remain during Q8 Phase 1 and the schema-only transition, and must not be hard-removed before A20(E) schema migration and Q8 Phase 2 conditions are satisfied.

This prevents the slice from accidentally turning workspace layout work into a premature SavedRule/registry removal branch.

### 2026-05-20 — Filename encoding intentionally left for preflight

The design text uses semantic placeholders like `db/objects/tx/<tx_id>.json` and `db/objects/schema/<schema_digest>.json`.

This draft does not yet choose whether physical filenames contain full tokens such as `tx:<hex>` / `sha256:<hex>` or filesystem-safe derived hex segments. It only locks that object content must carry the full token form. Filename encoding is a preflight decision before moving to `scoped`.
