# Core Store Docs

- Applicable scope: `src/factgraph/core/store`
- Last updated: 2026-08-01
- Audience: maintainers of the Ledger, Database commit protocol, and durable
  workspace lifecycle

This document records the current implementation contract for the low-level
append-only Ledger substrate and the Database identity boundary above it.

## Scope

The module owns SQLite row persistence, atomic Database commits, durable
workspace identity, state/history commitments, writer locking, integrity
validation, repair, migration, and frozen assertion-set objects.

## Current Responsibilities

- Persist append-only claim, argument, metadata, annotation, and revocation
  rows through `Ledger`.
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
appends, or one isolated schema transition. Assertion ids are server-generated
UUID4 tokens. A transaction object commits only the normalized delta for that
batch plus its parent, sequence, schema digest, and `digest_scheme`; it does
not hash the whole ledger.

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
  views/
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
explicit genesis repair anchor over the imported active set because the old
per-commit history cannot be reconstructed. The default keeps the complete old
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
Memory-mode Databases do not persist views. `FactGraph.attach(db, view=view)`
is read-only; base attach is writable and routes canonical SDK writes through
the caller-owned Database.

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
- `tests/test_application_entity_write.py`
- `tests/test_sdk_batch_application_delegate.py`
- `tests/test_db_identity_substrate.py`
- `tests/test_db_attach_lifecycle.py`
- `tests/test_factgraph_workspace_lifecycle.py`
- `tests/test_a20e_registry_final_removal.py`

## Related Historical Blueprints

- `workflow/blueprints/active/2026-07-31_stage-a-lifecycle-convergence.md`
  — current Stage A lifecycle and storage-hardening implementation contract.
- `workflow/design/decisions/active/2026-07-31_q-sae-7-data-digest-contract-decision.md`
  — dual commitment, fail-closed, and digest ownership rationale.
- `workflow/design/decisions/active/2026-07-31_q-sae-9-meta-tiering-tx-reification-decision.md`
  — transaction reification and metadata-tiering rationale.
