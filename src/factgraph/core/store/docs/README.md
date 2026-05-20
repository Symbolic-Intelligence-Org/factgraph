# Core Store Docs

`factgraph.core.store` contains the low-level ledger substrate and the
Database identity boundary built above it.

## Database Identity Substrate

`factgraph.core.store.database` defines the first DB/view identity slice:

- `Database` is a new boundary above `Ledger`; `Ledger` remains the storage
  and compatibility substrate.
- `DatabaseValue` is the immutable head identity (`db_id`, `tx_id`,
  `schema_digest`, `data_digest`).
- `AssertionRecord` is the canonical durable Database-owned assertion record.
  It is not the SDK read DTO and not the raw `Ledger.Claim` storage shape.
- `canonical_bytes_dbtx_v1`, `canonical_bytes_dbdata_v1`, and
  `canonical_bytes_assertion_v1` provide the domain-separated byte protocols
  used to derive `tx_id`, `data_digest`, `assertion_digest`, and `asrt_id`.

The no-view `DatabaseValue.data_digest` uses the Q5 active-only snapshot
universe. View-scoped data-digest semantics, `FactGraph.attach(...)`, and public
`view=` read/evaluate APIs are separate future slices.

Canonical assertion metadata is based on normalized `MetaRow` semantics. Raw
user metadata dictionaries are write-normalization inputs, not identity inputs.

Engine projection tuples such as `build_args_for_claim(...)` and
`ProjectedFact.fact_tuple` are not assertion identity payloads.

## Database Workspace Layout

For durable, non-memory `Database.create(path=...)` and
`Database.open(path=...)`, `path` is the workspace root. The Database-owned
layout lives under `db/`:

- `db/objects/tx/<64hex>.json` stores immutable transaction objects. The
  filename uses the raw hex suffix of the `tx:<hex>` token; object content keeps
  and validates the full token.
- `db/objects/schema/<64hex>.json` stores exact `canonicalize_schema_ir_jcs(...)`
  bytes. It does not reuse the authoring-registry presentation newline or
  manifest envelope.
- `db/refs/head.txt` stores the current head `tx_id`. `Database.head()` resolves
  `head.txt -> tx object -> DatabaseValue`; ledger metadata is only a
  compatibility cache for this head identity.
- `db/assertions.db` remains the SQLite `Ledger` storage substrate and mutable
  assertion index.
- `factgraph_workspace.json` points to the Database-owned `db/` component and
  reserves `views/`. Existing `registry/` data is preserved and kept in the
  manifest during the transition window, but new clean Database workspaces do
  not create registry content.

Object and head writes use sibling temporary files followed by `os.replace(...)`
for per-file atomic replacement. Cross-file atomicity across object, ref, and
SQLite writes remains a future storage-hardening concern.
