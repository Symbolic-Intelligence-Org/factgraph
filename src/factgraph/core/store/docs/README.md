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
  reserves `views/`. Existing `registry/` data is preserved as inert historical
  data when present, but new clean Database and SDK workspaces do not create
  live registry content or use `registry/schema/schema_ir.json` as the schema
  anchor.

Object and head writes use sibling temporary files followed by `os.replace(...)`
for per-file atomic replacement. Cross-file atomicity across object, ref, and
SQLite writes remains a future storage-hardening concern.

## Frozen Assertion View Persistence

`Database.create_view(name, asrt_ids, *, base=None)` creates anonymous,
content-addressed `FrozenAssertionView` objects for new-layout workspaces only.
Memory-mode and legacy-ledger-mode Databases reject durable view persistence.

The canonical view record has six fields: `name`, `db_id`, `base_tx_id`,
`schema_digest`, sorted `asrt_ids`, and `view_digest`. The `view_digest` is a
`sha256:<hex>` digest over `VIEW_V1_PREFIX = b"factpy\x00subset_view_v1\x00"`,
the Database identity anchors, and the sorted assertion-id set. The `name`
field is a label and is not part of the digest input.

View objects are written under `views/objects/<64hex>.json`. The filename uses
the raw hex suffix of `view_digest`; object content keeps the full token and is
write-once. Creation is current-head-only: callers may omit `base` or pass the
current `Database.head()` value. Historical-base validation is deferred to a
future snapshot/attach slice.

Membership validation checks that each `asrt_id` exists as a ledger claim. It
does not require assertions to be active; revoked assertions may remain in a
frozen view scope per Q5. SDK in-memory `_SDKViewsManager` views and
`fg.save(...)` compatibility behavior remain separate and unchanged.

## Attach Lifecycle

`FactGraph.attach(db, schema_classes=...)` binds the SDK runtime to an existing
`Database` instance for the base writable attach form. The attached runtime
shares the Database-owned Ledger substrate for reads, but Database-owned writes
route through `fg.commit_assertions(...)`, which delegates to
`Database.commit_assertions(...)` and returns `CommitResult` unchanged.

Attached runtimes reject the shipped SDK mutation surfaces (`fg.set`,
`fg.add`, `fg.retract`, `fg.edit`, `fg.ingest`, `fg.add_schema_classes`,
`fg.save_rule`, `fg.save_inference`, `fg.accept`, `fg.accept_many`,
`fg.batch`, `fg.save`, and the corresponding manager delegates) because those
paths bypass the Database boundary. Non-attached `FactGraph.create`,
`FactGraph.from_schema_classes`, and `FactGraph.load` runtimes keep the shipped
behavior.

Snapshot attach (`db.as_of(...)`), view-scoped attach, `ReadOnlyAttachmentError`,
and public `view=` read/evaluate APIs remain future slices.
