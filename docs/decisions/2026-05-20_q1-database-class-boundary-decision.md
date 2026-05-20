# Q1 Decision: Database Class Boundary

- Status: proposed for user review
- Created: 2026-05-20
- Branch: `v0.1-q1-database-class-decision-2026-05-20`
- Inputs:
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_audit_execution_discipline.md` (strict design wording must not be softened to match shipped reality)
- Scope: decide what the design term `Database` means relative to shipped `Ledger`.
- Non-scope: `tx_id` formula (Q3), `attach(...)` lifecycle (Q2), `FrozenAssertionView` shape (Q4), `AssertionRecord` reconciliation (Q7), SavedRule governance (Q8).

## 1. Decision

`Database` is a **new application/storage boundary above shipped `Ledger`**.

`Ledger` remains the low-level SQLite storage/index primitive. It is not renamed to `Database`, and the design term `Database` is not dropped.

The minimum architecture becomes:

```text
Database
  owns durable database identity, transaction head, transaction objects,
  and the public commit/head/as_of boundary

Ledger
  remains the low-level SQLite assertion/revocation/meta/index substrate
  used by Database and existing compatibility paths during migration
```

This means the design statement "`Database` 是唯一持久写入点" is interpreted as:

- **Normative target**: new db/view architecture writes enter through `Database`.
- **Compatibility reality**: existing shipped SDK/Ledger write paths remain until explicitly migrated, routed through `Database`, or deprecated.
- **Not allowed**: pretending shipped `Ledger` already satisfies the `Database` boundary.

Q1 does **not** pin the implementation composition between `Database` and `Ledger`. Future blueprints may choose whether `Database` wraps a `Ledger` instance, uses `Ledger` as one replaceable storage substrate, or stages another composition pattern during migration. The invariant from Q1 is only that the public db/view boundary is `Database`, while `Ledger` stays below it as storage substrate / compatibility machinery.

## 2. Rejected Alternatives

### 2.1 Map `Database` directly to existing `Ledger`

Rejected.

Reason: shipped `Ledger` is a storage primitive with several write surfaces, not the design boundary. It has high-level assertion and revocation writes (`append_assertion`, `append_revocation`) plus deprecated low-level row writes (`append_claim`, `append_claim_args`, `append_meta`, `append_revokes`), annotation writes, and lifecycle metadata writes (`set_ledger_meta`, `replace_ledger_meta`). It also has no `db_id`, no `tx_id`, no `head()`, no `as_of(tx_id)`, and no `commit_assertions(...)`.

Mapping `Database` to `Ledger` would weaken the design into a vocabulary alias while leaving the load-bearing identity and transaction questions unresolved.

### 2.2 Drop `Database` from the design

Rejected.

Reason: dropping `Database` would collapse the design's four-concept boundary (`Database` / `DatabaseValue` / `SubsetView` / `FactGraph runtime`) and leave no owner for `db_id`, durable `head`, transaction objects, `DatabaseValue`, or cross-doc metadata sources.

The audit already shows Q3/Q4/Q10-style fields depend on a database-level identity source; removing `Database` would push that responsibility back into `FactGraph` or scattered ledger metadata, recreating the original conflation the design is trying to correct.

## 3. Supporting Evidence

### 3.1 Design requires a boundary above raw storage

The DB/view design defines `Database` as the owner of assertion records, append-only transaction log, current head tx, `head()` / `as_of(tx_id)`, and schema/data digests (`database-view-fg-layered-architecture.zh.md:80-91`).

It separately defines `DatabaseValue` as an immutable snapshot identified by `db_id + tx_id` (`database-view-fg-layered-architecture.zh.md:97-108`), and locks I1/I2 as invariants (`database-view-fg-layered-architecture.zh.md:149-150`).

This is broader than the shipped `Ledger` abstraction.

### 3.2 Shipped `Ledger` is the current storage substrate, but not the target boundary

Shipped `Ledger.append_assertion(...)` writes claim, args, meta, optional annotations, and idempotency rows into SQLite (`src/factgraph/core/store/ledger.py:363-451`).

Shipped `Ledger.append_revocation(...)` is a separate high-level revocation write (`src/factgraph/core/store/ledger.py:453-510`).

Shipped `Ledger` also retains deprecated low-level row write methods:

- `append_claim` (`src/factgraph/core/store/ledger.py:512-529`)
- `append_claim_args` (`src/factgraph/core/store/ledger.py:531-551`)
- `append_meta` (`src/factgraph/core/store/ledger.py:553-574`)
- `append_revokes` (`src/factgraph/core/store/ledger.py:598-610`)

It exposes annotation-only writes (`src/factgraph/core/store/ledger.py:576-596`) and lifecycle metadata writes (`src/factgraph/core/store/ledger.py:780-792`).

Therefore, `Ledger` is not a single `Database.commit_assertions(...)` boundary.

### 3.3 Shipped SDK write paths already route through Ledger

The SDK field mutation path builds an application write command, applies it, and returns the resulting assertion id (`src/factgraph/sdk/store.py:1782-1839`).

The core write protocol creates UUID-style assertion ids, computes an ingest idempotency key, and writes through `Ledger.append_assertion(...)` (`src/factgraph/core/evidence/write_protocol.py:120-157`).

Retraction and replacement already exist at the write-protocol level:

- `retract_by_asrt(...)` (`src/factgraph/core/evidence/write_protocol.py:170-208`)
- `replace_field(...)` (`src/factgraph/core/evidence/write_protocol.py:211-228`)
- SDK `retract(...)` (`src/factgraph/sdk/store.py:1886-1909`)

This supports keeping `Ledger` as the storage substrate while introducing a clearer `Database` boundary above it.

## 4. Consequences

### 4.1 Q3 can proceed with a real owner

Q3 should define `tx_id`, `data_digest`, and transaction canonicalization as `Database` responsibilities, not as direct `Ledger` responsibilities.

`Ledger` may store or index rows needed by `Database`, but it does not become the canonical transaction identity owner.

### 4.2 Q2 attach lifecycle remains a runtime question

Q1 does not decide `FactGraph.attach(...)`.

It only establishes that if `attach(db)` is introduced, `db` means the new `Database` boundary, not raw `Ledger`.

### 4.3 Q4 view shape depends on Q3 outputs

`FrozenAssertionView` anchor fields (`db_id`, `base_tx_id`, `schema_digest`, `view_digest`) should consume `Database` / `DatabaseValue` identity once Q3 closes.

### 4.4 Existing shipped write APIs become migration surface

Existing `SDKStore.set/add/retract`, `write_protocol.set_field/retract_by_asrt/replace_field`, and low-level `Ledger` append methods are not automatically removed by Q1.

They are classified into three migration categories:

| Surface | Q1 meaning |
|---|---|
| `Ledger.append_assertion` / `append_revocation` | low-level storage primitive used by Database or compatibility paths |
| deprecated `append_claim*` / `append_meta` / `append_revokes` | legacy escape hatches; not part of Database target boundary |
| SDK `set/add` | public compatibility paths; later migration may route them through Database v1 `commit_assertions(...)` |
| SDK `retract` / `write_protocol.retract_by_asrt` / `replace_field` | public / application compatibility paths that **cannot** route through Database v1 because Database v1 intentionally has no retract/update method |
| `set_ledger_meta` / `replace_ledger_meta` | lifecycle metadata primitive; not assertion transaction boundary |

## 5. A2 / D4 Reading

Q1 adopts the **strict API reading** for the design phrase "最小版本只 append assertions":

- The new `Database` v1 API exposes `commit_assertions(...)` only.
- The new `Database` v1 API does **not** expose retract/update/schema-migration transaction methods.
- Existing shipped `fg.retract`, `retract_by_asrt`, and `replace_field` are compatibility-layer behavior, not evidence that Database v1 should include retract/update.

This does not require immediate deletion of shipped retract/update APIs. It only prevents them from being folded into the new `Database` v1 boundary.

`commit_assertions(...)` is a boundary name in Q1, not a full API signature. Its payload shape, `tx_id` formula, `data_digest`, duplicate behavior, and transaction-object canonicalization belong to Q3 and later blueprints.

## 6. Required Follow-up Decisions

Q1 closes the boundary question but deliberately leaves these open:

1. **Q3**: define `tx_id` / `data_digest` / transaction payload canonicalization.
2. **Q2**: decide `FactGraph.attach(...)` lifecycle on top of `Database`.
3. **Q4**: decide `FrozenAssertionView` shape after Q3 provides identity sources.
4. **Q5**: decide how view scope composes with `is_active` after Q4.
5. **Q8**: decide SavedRule existence governance separately; Q1 does not touch rules persistence.
6. **Q6**: decide registry-in-workspace migration only if Q8 keeps a registry-like surface.
7. **Q7**: reconcile shipped assertion record shapes with the design `AssertionRecord`.

## 7. Acceptance Criteria For This Decision

Future DB/view blueprints must obey:

1. Do not treat `Ledger` as already satisfying `Database`.
2. Do not rename `Ledger` to `Database` as a cosmetic change.
3. Do not remove `Database` from the DB/view design without reopening Q1.
4. New durable db/view identity fields must be owned by `Database` or `DatabaseValue`, not by `FactGraph` alone.
5. New `Database` v1 write API must not expose retract/update until a later tx-model decision explicitly adds it.
6. Existing shipped write paths may remain during migration, but any compliant new db/view implementation must identify whether each path is still compatibility-only or routes through `Database`.

## 8. Decision Record

Q1 resolution: **new `Database` boundary above `Ledger`**.

This is the only Q1 outcome that preserves the design's separation of storage identity, immutable snapshots, view scope, and runtime attachment while respecting shipped code reality.
