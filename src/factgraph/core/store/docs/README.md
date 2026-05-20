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
universe. View-scoped data-digest semantics, workspace physical layout,
`FactGraph.attach(...)`, and public `view=` read/evaluate APIs are separate
future slices.

Canonical assertion metadata is based on normalized `MetaRow` semantics. Raw
user metadata dictionaries are write-normalization inputs, not identity inputs.

Engine projection tuples such as `build_args_for_claim(...)` and
`ProjectedFact.fact_tuple` are not assertion identity payloads.
