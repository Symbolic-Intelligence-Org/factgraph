# Q3 Decision: Transaction Identity Primitives

- Status: closed
- Created: 2026-05-20
- Branch: `v0.1-q3-tx-identity-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_audit_execution_discipline.md`
- Scope: decide the canonical primitives for `tx_id`, `data_digest`, and the digest envelope for assertion identity.
- Non-scope: `Database` boundary (Q1 closed), `FactGraph.attach(...)` lifecycle (Q2), `FrozenAssertionView` shape (Q4), `AssertionRecord` shape / `fact_tuple` reconciliation (Q7), SavedRule governance (Q8).

## 1. Decision

Q3 chooses a **dedicated Database identity canonicalization family**, not reuse of `tup_v1` as the whole transaction payload.

The decision is:

```text
tx_id          = "tx:" + sha256_hex(canonical_bytes_dbtx_v1(tx_payload))
data_digest    = "sha256:" + sha256_hex(canonical_bytes_dbdata_v1(data_payload))
assertion_digest = "sha256:" + sha256_hex(canonical_bytes_assertion_v1(assertion_payload))
asrt_id        = "asrt:" + sha256_hex(canonical_bytes_assertion_v1(assertion_payload))
```

Ownership:

- `Database` owns `tx_id`, `data_digest`, transaction payload canonicalization, and resulting head identity.
- `Database` or a Database-owned helper owns `assertion_digest` / content-addressed `asrt_id` once Q7 resolves the assertion record shape.
- `Ledger` does **not** own these durable identities. It may store/index rows for `Database`.

## 2. Canonical Payloads

### 2.1 `dbtx_v1`

`canonical_bytes_dbtx_v1(...)` is a new byte protocol for transaction identity.

It MUST include exactly:

- format/domain marker: `factpy\0dbtx_v1\0`
- `parent_tx_id: str | None`
- `schema_digest: str`
- `added_assertion_digests: tuple[str, ...]` sorted ascending
- `data_digest: str`

It MUST NOT include:

- `created_at`
- local path
- process id
- host info
- SQLite sequence ids
- UUIDs
- authoring registry / rule material

The `tx_id` prefix is `tx:`. It is not `sha256:<hex>` because `tx_id` is a typed durable identifier, not a generic digest token.

The byte-prefix namespace intentionally remains `factpy\0`, matching shipped `tup_v1` and `idref_v1`. The package/runtime vocabulary may say `factgraph`, but byte-level identity protocols keep the shipped prefix family for digest stability.

### 2.2 `dbdata_v1`

`canonical_bytes_dbdata_v1(...)` is a new byte protocol for the assertion universe represented by a `DatabaseValue`.

It MUST include exactly:

- format/domain marker: `factpy\0dbdata_v1\0`
- sorted resulting `asrt_id` set for the snapshot, using the universe semantics chosen by Q5

`data_digest` uses the generic digest token form `sha256:<hex>`.

Rationale: the same final assertion universe should produce the same `data_digest` even if reached by different transaction paths. The `tx_id` still differs when `parent_tx_id` or added assertions differ.

Q3 does **not** decide what counts as the resulting assertion universe. In particular, all-asserted vs currently-active semantics are Q5 territory because they depend on how view scope composes with `is_active` / revocation. Q3 commits only to canonicalizing the chosen set as sorted ascending assertion ids.

### 2.3 `assertion_v1`

`canonical_bytes_assertion_v1(...)` is the assertion identity envelope.

Q3 locks only the digest envelope and prefix convention:

- `assertion_digest = "sha256:<hex>"`
- `asrt_id = "asrt:<hex>"`

Q3 does **not** lock the `assertion_payload` field list, field names, ordering, or encoding. All of that is Q7 territory. Q3 commits only to the digest envelope (`sha256:<hex>`) and typed-id prefix (`asrt:<hex>`).

Once Q7 closes, `assertion_v1` may reuse existing fact-term canonicalization primitives internally, especially `canonical_bytes_tup_v1(...)`, but Q3 does not decide that shape.

## 3. Rejected Alternatives

### 3.1 Use UUIDs or SQLite AUTOINCREMENT for durable identity

Rejected.

Design A3 explicitly says `tx_id` must not be UUID or autoincrement durable identity. Shipped SQLite tables use `AUTOINCREMENT` columns for row storage (`src/factgraph/core/store/ledger.py:83-120`) and shipped assertion ids use UUID-style hex (`src/factgraph/core/store/ledger.py:1066-1067`, `src/factgraph/core/evidence/write_protocol.py:120-121`), but those shipped mechanisms are not acceptable templates for `tx_id`.

### 3.2 Reuse `_compute_ingest_key(...)` as the transaction template

Rejected.

`_compute_ingest_key(...)` is an ingest idempotency key over `pred_id`, `e_ref`, fact rest terms, source metadata, and temporal metadata (`src/factgraph/core/evidence/write_protocol.py:318-370`).

That payload is deliberately about write idempotency, not database snapshot identity. Reusing it for `tx_id` would conflate ingestion dedup with transaction identity.

### 3.3 Use `canonical_bytes_tup_v1(...)` as the whole transaction payload

Rejected.

`canonical_bytes_tup_v1(...)` is the shipped canonical tuple protocol for fact terms. It validates a flat list of `(tag, value)` terms and writes the `factpy\0tup_v1\0` prefix (`src/factgraph/core/protocol/tup_v1.py:10-23`, `src/factgraph/core/protocol/tup_v1.py:156-168`).

A transaction payload is not a fact tuple. It contains named fields, an optional parent, a schema digest, a sorted list of assertion digests, and a resulting data digest.

Using `tup_v1` as the entire transaction protocol would force transaction field semantics into a flat positional fact-term protocol. Shipped `_compute_ingest_key(...)` already uses a sentinel-prefixed `tup_v1` tuple for ingest idempotency, but Q3 deliberately does not extend that pattern to transaction identity: transaction identity has durable named fields (`parent_tx_id`, `schema_digest`, `added_assertion_digests`, `data_digest`) and should not couple its stability to fact-tuple positional conventions.

### 3.4 Make `data_digest` path-dependent

Rejected.

`data_digest` represents the resulting assertion universe, not how the universe was reached. `tx_id` is the path-sensitive identity because it includes `parent_tx_id` and added assertion digests. `data_digest` must stay path-independent.

## 4. Shipped Primitives To Reuse

Q3 reuses shipped primitives at the correct layer:

| Shipped primitive | Use in Q3 |
|---|---|
| `sha256_hex(data)` / `sha256_token(data)` (`src/factgraph/core/protocol/digests.py:7-12`) | hashing and generic digest token formatting |
| `canonical_bytes_tup_v1(...)` (`src/factgraph/core/protocol/tup_v1.py:156-168`) | fact-term canonicalization inside future `assertion_v1`, after Q7 closes |
| `encode_value_bytes(...)` (`src/factgraph/core/protocol/tup_v1.py:133-153`) | per-tag strict value encoding, via assertion/fact canonicalization, not transaction-level named-field encoding |
| `schema_digest(...)` (`src/factgraph/core/schema/schema_ir.py:76-78`) | existing compiled schema digest; do not duplicate |

Q3 introduces new byte protocols only for the domains that do not already exist: Database transaction identity and DatabaseValue data identity.

## 5. Prefixes And Token Forms

| Value | Form | Reason |
|---|---|---|
| `db_id` | `db:<uuid4>` | Q3 does not change Q1/design `db_id`; durable database identity is not content-addressed |
| in-memory db id | `mem:<uuid4>` | non-durable identity per design A12 |
| `tx_id` | `tx:<hex>` | typed durable transaction identity |
| `asrt_id` | `asrt:<hex>` | typed durable assertion identity |
| `schema_digest` | `sha256:<hex>` | existing shipped digest token from `schema_digest(...)` |
| `data_digest` | `sha256:<hex>` | generic digest of resulting assertion universe |
| `assertion_digest` | `sha256:<hex>` | generic digest token used to derive typed `asrt_id` |

Typed IDs use domain prefixes (`tx:`, `asrt:`). Digest values use `sha256:<hex>`.

## 6. Consequences

### 6.1 Q2 can treat `DatabaseValue` identity as stable

After Q3, `DatabaseValue(db_id, tx_id, schema_digest, data_digest, ...)` has concrete identity sources. Q2 can decide attach lifecycle without inventing identity semantics.

### 6.2 Q4 can consume `base_tx_id` and `schema_digest`

Q4 should treat `FrozenAssertionView.base_tx_id` as a `tx:<hex>` value and `FrozenAssertionView.schema_digest` as the existing `sha256:<hex>` schema digest token.

### 6.3 Q7 remains necessary

Q3 does not resolve the four-shape `AssertionRecord` conflict.

Q7 must decide whether assertion canonicalization consumes:

- shipped `Claim(e_ref, rest_terms)`,
- a design `fact_tuple`,
- a layered logical assertion record, or
- another reconciled shape.

Only after Q7 closes can `canonical_bytes_assertion_v1(...)` be fully specified.

### 6.4 Existing shipped IDs become compatibility identities

Shipped UUID-style assertion ids and SQLite autoincrement ids remain compatibility/storage details until migrated.

They are not valid durable `tx_id` templates, and they are not valid content-addressed `asrt_id` outputs for new Database-owned writes.

## 7. Acceptance Criteria For This Decision

Future Q3-dependent blueprints must obey:

1. Do not use `_compute_ingest_key(...)` as `tx_id` or as the transaction payload template.
2. Do not use SQLite autoincrement ids or UUIDs for durable `tx_id`.
3. Do not use `canonical_bytes_tup_v1(...)` as the whole transaction payload.
4. Do introduce a domain-separated transaction canonical byte protocol (`dbtx_v1` or equivalent name) before implementing `tx_id`.
5. Do introduce a domain-separated data canonical byte protocol (`dbdata_v1` or equivalent name) before implementing `data_digest`.
6. Do keep `data_digest` path-independent and `tx_id` path-sensitive.
7. Do leave assertion payload shape open until Q7 closes.
8. Do reuse existing `schema_digest(...)`; do not introduce a parallel schema digest algorithm.

## 8. Decision Record

Q3 resolution: **dedicated Database identity protocols for transaction and data identity**.

`Database` owns `tx_id` and `data_digest`. `tx_id` is `tx:<hex>` over `dbtx_v1`; `data_digest` is `sha256:<hex>` over `dbdata_v1`. Assertion identity uses an `assertion_v1` envelope but remains shape-incomplete until Q7 closes.
