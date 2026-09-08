# Core Store Docs

- Applicable scope: `src/factgraph/core/store`
- Last updated: 2026-08-03
- Audience: maintainers of the Ledger, Database commit protocol, and durable
  workspace lifecycle

This document records the current implementation contract for the low-level
append-only Ledger substrate and the Database identity boundary above it.

## Scope

The module owns SQLite row persistence, atomic Database commits, durable
workspace identity, state/history commitments, writer locking, integrity
validation, repair, migration, and frozen assertion-set objects.

## Current Responsibilities

- Persist append-only claims and claim-scoped metadata events in the three-table
  `claims` / `claim_meta` / `ledger_meta` layout. Revocations are ordinary
  internal claims with `pred_id="__system__.revokes"`; argument and annotation
  compatibility reads are projections, not separate tables.
- Commit one logical change batch through `Database.commit_changes(...)` as one
  SQLite transaction, including the factual rows, metadata rows, CAS-protected
  head, schema anchor, and state digest.
- Maintain two commitments: an order-independent active-state `state_digest`
  and an order-sensitive transaction chain rooted at `tx_id`.
- Open durable workspaces fail-closed by replaying the transaction chain and
  comparing it with the SQLite active set and assertion content digests.
- Create, open, repair, migrate, lock, and close durable Database workspaces.

## Database Commit Protocol

`DatabaseValue` is the immutable current head identity: `db_id`, `tx_id`,
`schema_digest`, `state_digest`, `digest_scheme`, and `tx_seq`. The
`data_digest` property is a compatibility alias for `state_digest`.

`Database.commit_changes(...)` accepts assertions, revocations, metadata
appends, batch metadata defaults, or one isolated schema transition. Assertion
ids are server-generated UUID4 tokens. A transaction object commits only the
normalized delta for that batch plus its parent, sequence, schema digest,
`digest_scheme`, and optional canonical `meta_defaults`; it does not hash the
whole ledger.

The low-level `SchemaTransitionInput` path is deliberately policy-free: it
commits and validates an already-authorized transition but does not decide
whether the IR change is additive. It is not exported from `factgraph.sdk`.
SDK users must go through `fg.schema.register/extend/apply`, whose application
runtime enforces the current additive-only policy. A future schema-evolution
blueprint owns diff generation and richer policy filtering.

The current state scheme is `lthash16-v2`. Each multiset element binds both
`asrt_id` and `assertion_digest`, so factual-content tampering is detected on
open. Metadata appended after assertion creation is event history and does not
change `state_digest`. A schema-transition transaction stores only the old and
new schema digests; both canonical, content-addressed schema objects are
required for replay, which validates transition continuity.

`claim_meta` rows are immutable events ordered by `(tx_seq, op_ordinal)`.
Effective reads choose the greatest event per `(asrt_id, key)`; a dual-NULL
`kind`/`value` event is an internal UNSET tombstone. `Ledger.latest_event_sequence()`
returns the inclusive current ledger boundary used by evidence envelopes. It
does not alter `state_digest`, support digests, or view-snapshot digests.

## Three-table Shape and Metadata Tiering

The durable SQLite schema contains exactly three non-internal tables:

```text
claims(seq, asrt_id, pred_id, e_ref, rest_terms, value, value_tag, tx_ref)
claim_meta(asrt_id, key, kind, value, tx_seq, op_ordinal)
ledger_meta(key, value)
```

`claims.tx_ref` is the producing transaction's integer `tx_seq`. The retained
nullable `rest_terms` column is a narrow legacy PyReason carrier; new
application and SDK writes use `value` / `value_tag` and write `[]`. Dropping
`rest_terms`, rewriting the adapter, and enforcing strict unary INV-9 are one
Slice 5 change, not independent cleanups.

Schema IR may declare a canonical-minimal `meta_keys` mapping. Each key has five
orthogonal properties: `reader_class`, `premise_eligible`, `load_policy`,
`storage_scope`, and `query_indexed`. Omitted properties mean the Phase 2
defaults (`runtime`, `false`, `eager`, `claim`, `false`); default-valued
properties and an empty mapping are omitted from canonical schema bytes.
`query_indexed` is declarative in v0.3 and does not yet create a dedicated
physical index.

Keys declared `load_policy="lazy"` remain queryable from `claim_meta` but do
not occupy the eager event/meta/annotation indexes. Keys declared
`storage_scope="tx_liftable"` may be supplied once in
`Database.commit_changes(meta_defaults=...)`. The sorted defaults are committed
in the tx object's canonical bytes and inherited by every assertion and
revoker in that batch. A claim event wins over its tx default; an internal
claim-level UNSET removes inheritance. Tx defaults never use UNSET and no
fourth table or ledger-meta mirror is created.

Premise configuration is closed against the schema. Only the pinned built-ins
`provenance_class` and `origin_binding`, or explicitly declared keys with
`premise_eligible=true`, can control evaluation visibility. See
`core/policy/README.md` and `premise_filter.py` for the evaluation boundary.

`assertion_digest`, `schema_digest`, and `tx_id` are Database-owned assertion
metadata keys. Assertion, revocation, and later meta-append inputs reject the
same complete set for both factual assertion ids and revoker ids.

`Ledger.commit_batch(...)` is the single SQLite transaction boundary. Head CAS
and the persisted state are updated in the same transaction as the rows. A
lost CAS raises `HeadConflictError`; an unsupported digest scheme or any
history/data mismatch fails closed. `Database.repair(...)` is an explicit,
auditable state rebuild and is not invoked automatically.

## Database Workspace Layout

For durable `Database.create(path=...)` and `Database.open(path=...)`, `path`
is the workspace root:

```text
workspace/
  factgraph_workspace.json
  db/
    assertions.db
    meta.json
    writer.lock
    objects/
      schema/<64hex>.json
      tx/<64hex>.json
    refs/                    # reserved; empty in v0.3 (head is in ledger_meta)
  views/                     # created lazily by Database.create_view(...)
    objects/<64hex>.json
```

`ledger_meta` inside `db/assertions.db` is authoritative for the current head,
state digest, schema digest, sequence, scheme, and Database id. Immutable tx
objects make the history replayable. Canonical schema objects and tx objects
are write-once; repeated identical schema writes keep the first object's bytes.

Every durable `Database.create/open` acquires a non-blocking exclusive
`flock` for the lifetime of the object. There is no read-only durable open path
in v0.3: a second open, including one intended only for reading, fails
explicitly. `Database.close()` and its context-manager exit release the Ledger
connection and lock idempotently.

`FactGraph.save_workspace()` no longer persists factual data. Canonical SDK
writes are already durable; save only updates `last_saved_at_epoch_ns` in
`db/meta.json` and must not advance the Database head.

## Legacy Migration

`python -m factgraph migrate-workspace <path>` is the opt-in route from a
closed v0.2 `ledger.db` workspace. It builds and verifies a staging v0.3
workspace, preserves legacy assertion/revocation rows and ids, and writes one
explicit genesis import transaction made from ordinary assertion, revocation,
and append-meta operations because the old per-commit history cannot be
reconstructed. The default keeps the complete old
workspace under `workspace.legacy.<UTC timestamp>/`; `--no-archive` discards
that backup only after verified replacement. Migration is never automatic.

During the two-rename replacement window, the complete source is held in a
visible sibling named `<workspace-name>.legacy-<UTC timestamp>`. If the process
stops there, rerunning the CLI returns `workspace_recovery_required` and lists
the candidate. When the requested workspace is absent, verify the sibling and
rename it back before rerunning migration. When both the verified replacement
and sibling exist, verify the replacement, then explicitly archive the sibling
inside the workspace or remove it. The CLI does not guess which copy to keep.
Torn-create and registry-only directories report `workspace_incomplete` with
recreate guidance; only a complete v0.2 `ledger.db` source is migratable.

## Frozen Assertion View Persistence

`Database.create_view(name, asrt_ids, *, base=None)` writes a content-addressed
`FrozenAssertionSet` under `views/objects/`. Creation is current-head-only.
Membership requires an existing claim but may include revoked assertions.
Memory-mode Databases reject `create_view(...)` because view objects require a
durable workspace. `FactGraph.attach(db, view=view)` is read-only; base attach
is writable and routes canonical SDK writes through the caller-owned Database.

## Non-responsibilities

- Schema authoring and additive compatibility policy belong to authoring and
  application layers; this policy-free mechanism commits an already-approved
  transition and must not be exposed as a product policy bypass.
- SDK entity/field planning and ingest normalization belong to the application
  and SDK layers.
- Engine projection, premise filtering, evidence, and service routing consume
  Ledger read APIs but do not belong to this module.

## Limitations and Compatibility

- Durable workspaces have one exclusive writer and no read-only open channel.
- A missing authoritative tx object cannot yet be re-anchored even when SQLite
  is intact; repair requires a valid tx-object head anchor.
- Portable `fsync` is explicit, but macOS `F_FULLFSYNC` is not requested.
- Legacy migration preserves rows and active state, not unrecoverable v0.2
  transaction history.
- Bare 32/64-character legacy UUID assertion ids remain accepted so migrated
  workspaces can be updated; new Database writes generate `asrt:<uuidhex>`.

## Test Entry Points

- `tests/test_storage_hardening_phase1.py`
- `tests/test_dbtx_v2_golden.py`
- `tests/test_slice3b_phase1_read_equivalence.py`
- `tests/test_slice3b_phase2_meta_events.py`
- `tests/test_slice3b_phase3_meta_policy.py`
- `tests/test_slice3b_phase3_tx_lift.py`
- `tests/test_slice3b_phase3_lazy_meta.py`
- `tests/test_slice3b_phase3_chosen_seq.py`
- `tests/test_application_entity_write.py`
- `tests/test_sdk_batch_application_delegate.py`
- `tests/test_db_identity_substrate.py`
- `tests/test_db_attach_lifecycle.py`
- `tests/test_factgraph_workspace_lifecycle.py`
- `tests/test_a20e_registry_final_removal.py`
