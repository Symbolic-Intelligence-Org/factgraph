# Data model: claims, meta, and the append-only ledger

This chapter describes what's actually stored when a FactGraph writes a fact. It complements [`schema_definition.md`](schema_definition.md) (which declares the *types*) by documenting how *instances* live in the ledger.

> **v0.3 note.** The ledger converged from seven tables to three (`claims` + `claim_meta` + `ledger_meta`), meta became an immutable event stream, and retract became a `__system__.revokes` claim. This chapter reflects the shipped Slice 3b layout. The Python `Claim` / `MetaRow` / `Revokes` dataclasses still exist as **logical / write-side input types** — they are no longer 1:1 with the on-disk rows.

## 1. Claim — the atomic unit

A claim is one immutable assertion. Every successful write produces at least one claim, identified by a **server-assigned** `asrt_id` (`asrt:<uuid4hex>`, allocated at commit — not content-addressed).

The in-memory `Claim` type (`factgraph.core.store.ledger.Claim`):

```python
@dataclass(frozen=True)
class Claim:
    asrt_id: str                            # server-assigned assertion id (UUID4)
    pred_id: str                            # predicate identifier
    e_ref: str                              # entity reference (idref_v1) — the subject
    rest_terms: list[tuple[str, Any]]       # at most one value term as (tag, value)
```

A concrete claim produced by `fg.fields.set(User.name, alice, "Alice")`:

```python
Claim(
    asrt_id="asrt:9f3a1c...e1",             # 32-hex UUID4, not a content hash
    pred_id="user:name",
    e_ref="idref_v1:User:7c12...3a",
    rest_terms=[("string", "Alice")],       # a single value term; the subject is e_ref, not repeated here
)
```

Every v0.3 claim is a **unary fact** (INV-9): the subject lives in the `e_ref` column and the fact carries at most one value term. On disk that value is stored in dedicated `value` / `value_tag` columns (see §4), so the row above persists as `value="Alice"`, `value_tag="string"`, and `rest_terms="[]"`. The `rest_terms` column is a **retained legacy carrier** for the not-yet-rewritten PyReason n-ary adapter path only; new writes always leave it `[]`.

This unary statement covers canonical v0.3 Database and SDK/application field
writes. `Relationship` declarations are currently compile-level schema only;
the SDK has no relationship CRUD surface. The advanced application
`PublishedRelationQueryV1` executor can read stored ternary relationship facts
from an unmanaged in-memory `Store` or compatible legacy/imported relation
data, but that does not widen the canonical durable write contract. See the
[published relation query contract](../../src/factgraph/application/docs/relation_query.md#5-store-and-durability-boundary).

### 1.1 User-facing claims and the virtual entity domain

The `pred_id` pattern tells you what role a claim plays:

| Category | `pred_id` shape | Created by | Retractable? |
|---|---|---|---|
| **Identity Claim** | `<owner>:<identity_field>` — snake_case owner, e.g. `user:user_id` | `fg.entities.create` | only via `fg.entities.delete` (whole entity) — direct retract raises `INV_7C_IDENTITY_PROTECTED` |
| **Field Claim** | `<owner>:<field>` — snake_case owner, e.g. `user:name` | `fg.fields.set` / `fg.fields.add` | yes — `fg.assertions.retract(asrt_id)` or `fg.fields.retract` |
| **Legacy `:exists` Claim** | `<EntityType>:exists` — raw type name, e.g. `User:exists` | older ledgers and compatibility/internal derivation paths; new SDK entity materialization does not emit it | only via `fg.entities.delete` — direct retract raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` |

Field and Identity predicates use the **lowercased snake_case** owner prefix
(`user:name`), while the generated entity-domain predicate uses the **raw
entity-type name** (`User:exists`). The latter remains usable in rule bodies,
but its rows are now a view projection rather than a second persisted truth
carrier.

`fg.entities.create(...)` persists the complete Identity Claim bundle. During
view projection, FactGraph emits one virtual `<EntityType>:exists(e_ref)` row
only when every Identity field has a current chosen value and those typed
values reconstruct exactly that content-derived `e_ref`. Partial or revoked
bundles and bundles stored under a mismatched `e_ref` produce no domain row.
Each projected row has a deterministic virtual witness derived from all
supporting Identity assertion ids. A persisted legacy `:exists` marker alone
is deliberately ignored and cannot create or duplicate an entity-domain row.

Identity values are part of the entity reference's content-derived hash, so they cannot be mutated without changing the entity's `e_ref`. That's why direct identity retraction is protected.

## 2. Meta — an immutable event stream on a claim

Each claim can carry meta key/value pairs (provenance, uncertainty, audit tags). Write them with the `meta={...}` parameter on any write method:

```python
fg.fields.set(User.name, alice, "Alice", meta={"source": "import", "trace_id": "batch-001"})
```

The write-side input type is `factgraph.core.store.ledger.MetaRow` (`asrt_id`, `key`, `kind`, `value`), where `kind ∈ META_KINDS = {"str", "int", "float", "bool", "time", "json"}`. But meta is **not** stored as a flat overwrite row. Each pair becomes one immutable **event** in the `claim_meta` table, tagged with its transaction coordinate `(tx_seq, op_ordinal)`:

| Column | Meaning |
|---|---|
| `asrt_id` | the claim (or revoker) this event belongs to |
| `key` | the meta key (`source`, `trace_id`, …) |
| `kind` | the value kind; `NULL` only for an UNSET tombstone |
| `value` | canonical text of the value; `NULL` only for an UNSET tombstone |
| `tx_seq` | the Database commit sequence that produced the event |
| `op_ordinal` | position within that commit (input order) |

The event **primary key is `(asrt_id, key, tx_seq, op_ordinal)`** — the same `(asrt_id, key)` may accumulate many events over time, and each row is append-only (never UPDATE/DELETE).

**Effective value = last-wins by `max(tx_seq, op_ordinal)`.** Re-setting a key appends a new event; it does not overwrite the old one. For example, two successive `fg.assertions.append_meta(aid, "reviewer", …)` calls leave two rows:

```text
(asrt_id, "reviewer", "str", "alice", tx_seq=3, op_ordinal=0)   # earlier
(asrt_id, "reviewer", "str", "bob",   tx_seq=4, op_ordinal=0)   # effective (latest)
```

Three consequences worth knowing:

- **Unique keys per operation (breaking).** A single commit operation may not carry the same meta key twice; successive values for one key must be separate `append_meta` operations, so `(tx_seq, op_ordinal)` defines an unambiguous event order. (Through the `meta={...}` dict API this is automatic — dict keys are already unique; the rule bites only when authoring Database-level batches directly.)
- **UNSET tombstone.** An UNSET event sets both `kind` and `value` to SQL `NULL` (dual-NULL); a key whose latest event is UNSET reads as absent. Ordinary user events must have both columns non-NULL.
- **As-of replay.** The full ordered history — including tombstones — is readable through the narrow audit interface `factgraph.audit.meta_history` (`read_meta_history` / `effective_meta_at` / export / import). Regular reads always resolve the latest-effective value; as-of replay is an audit/explain surface, not a general SDK history API.

### 2.1 Built-in meta keys

A handful of meta keys are *canonical* — they're surfaced as typed slots on `AssertionMeta` (the read-side projection of a claim's **effective** meta events) and several drive special runtime mechanisms.

| Key | What it does |
|---|---|
| `source` | provenance label;typed slot on `AssertionMeta.source` |
| `trace_id` | batch / request id for audit;typed slot on `AssertionMeta.trace_id` |
| `approved_by` | approval signal;typed slot on `AssertionMeta.approved_by` |
| `note` | free-form note;typed slot on `AssertionMeta.note` |
| `ingested_at` | system-injected nanosecond ingest timestamp. **Lifecycle-managed (S-class): override-protected — append/UNSET of this key fails closed.** To record your own source time, use the ordinary `event_time` time-key instead. |
| `version` | version label used by record-set filters (`_meta={"version": v}`) |
| `valid_from`, `valid_to` | ISO-8601 business-time markers used by record-set business-time selection (`.at(t)`) |
| `raw_kind` + `bound` | reasoning input — `ProbLog` and `PyReason` adapters consume these as uncertainty carriers. Strict pairing: see §2.2. |
| `derived_rule_id`, `derived_rule_version` | identifies the rule and version that derived this assertion (set automatically when an inference engine writes back) |
| `candidate_id`, `candidate_key`, `candidate_kind` | links a derived claim to its candidate origin (audit / explanation surface) |

> **Meta-key tiering (advanced).** A schema may declare per-key policy — `reader_class`, `premise_eligible`, `load_policy`, `storage_scope`, `query_indexed` — via schema-global `meta_keys`, controlling premise-eligibility, lazy loading, and batch `tx_liftable` defaults. See [`schema_definition.md`](schema_definition.md) §2.

### 2.2 Uncertainty pairing: `raw_kind` + `bound`

When you want to record numeric uncertainty on a write, both keys must appear together:

- `raw_kind` ∈ `{"probabilistic", "possibilistic"}`
- `bound` is a two-element list `[lower, upper]` of finite floats with `0 <= lower <= upper <= 1`

Examples of rejected forms (all raise `WriteProtocolError` at write time):

- providing one of `raw_kind` / `bound` without the other → `meta[raw_kind] and meta[bound] must be provided together`
- `raw_kind` outside the allowed set → `meta[raw_kind] must be one of: ...`
- `bound` not a two-element list → `meta[bound] must be a two-element JSON list`
- legacy `confidence` or `confidence_source` keys → `meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.`

### 2.3 Adding your own meta keys

Anything not listed in §2.1 is preserved as-is in `AssertionMeta.raw` (a plain `dict`). The runtime does not interpret unknown keys — feel free to add tenant ids, workflow tags, custom audit fields, anything that's serialisable into one of the `META_KINDS`. The only constraint is that the `kind` is one of the six accepted values.

### 2.4 Ledger `meta` and Product V2 Scenario `meta` are different contracts

Product V2 deliberately gives Scenario operations a familiar write-like form:

```python
scenario = (
    fg.scenario()
      .set(
          User.risk_flag,
          user_ref,
          True,
          meta={
              "raw_kind": "probabilistic",
              "bound": [0.8, 0.8],
              "source": {
                  "ref": "model:risk-v3",
                  "locator": {"kind": "opaque", "opaque_ref": "prediction-7"},
                  "origin_role": "imported_record",
              },
              "note": "run-local hypothesis",
          },
      )
      .build()
)
```

The spelling is similar, but Scenario does **not** append a Claim or a
`claim_meta` event. Its strict `meta` input is immediately separated into:

- evaluator-visible fact semantics (`raw_kind` and `bound`);
- safe opaque provenance references (`source` / `sources`); and
- display/audit annotations (`note` / `labels`).

Those lanes receive separate semantic-world and resolution-evidence digests.
Changing only a source reference does not change the evaluator-visible world,
but it still changes the sealed run and its structured Explain data. Scenario
facts are marked as run-local synthetic premises; caller metadata cannot turn
them into ledger assertions or authoritative sources.

Probabilistic Scenario facts currently execute only under a Product V2
ProbLog point profile. Native and Soufflé return typed unsupported frames
rather than ignoring the metadata. See the
[complete Product V2 workflow](product_workflow_v2.md#9-probabilistic-scenario-facts).

## 3. Append-only retract

The ledger never modifies a row in place. To "remove" a claim, the runtime appends a **revoke claim** — an ordinary `claims` row in the reserved `__system__.revokes` predicate. The in-memory logical type is `factgraph.core.store.ledger.Revokes` (`revoker_asrt_id`, `revoked_asrt_id`), but there is no separate `revokes` table.

`fg.assertions.retract(asrt_id, meta={...})` writes **one** new claim row:

```text
pred_id   = "__system__.revokes"
e_ref     = <e_ref of the revoked fact>
value     = <revoked asrt_id>        # value_tag = "string"
```

The revoker claim can carry its own meta events. The original claim row is **untouched**. Two consequences:

- **active** means *not revoked*. A claim is active iff no active `__system__.revokes` claim carries its `asrt_id` as `value` (INV-13).
- **all** includes both active and revoked claims — useful for history and audit replay.

For single-cardinality fields, multiple `fg.fields.set(...)` calls produce multiple active Claims (no automatic revoke). Snapshot reads project a single value by picking the **active claim with the highest `claims.seq`** — i.e. the most recent durable commit order.

> **Breaking (v0.2 → v0.3).** Single-cardinality winner selection now follows durable `claims.seq`, regardless of the sampled `ingested_at` or the assertion id. This intentionally changes time-inversion, equal-time, and imported histories; the `core/policy` module contract documents the selection rule.

Use `fg.fields.retract(field, ref, value)` to explicitly revoke a specific older value, or `fg.fields.delete(field, ref)` to revoke every active value for the cell.

## 4. Physical storage — SQLite tables

The ledger is a single SQLite database file. A durable v0.3 workspace stores it at `db/assertions.db`; a pathless graph uses an in-memory Database. The lower-level `FactGraph.from_schema_classes(...)` unmanaged-Ledger compatibility lifecycle remains separate (see [`load_and_save.md`](load_and_save.md)). The schema is **three tables**:

| Table | What it stores | Append-only? |
|---|---|---|
| `claims` | one row per claim: `(seq, asrt_id, pred_id, e_ref, rest_terms, value, value_tag, tx_ref)` | ✓ |
| `claim_meta` | one row per meta **event**: `(asrt_id, key, kind, value, tx_seq, op_ordinal)` | ✓ |
| `ledger_meta` | mutable head metadata: `head_tx_id`, `head_tx_seq`, `head_state_digest`, `digest_scheme`, `schema_digest`, `db_id`, `ledger_format_version` | ✗ |

Only `ledger_meta` is mutable — it holds the head pointers (analogous to git's `HEAD` ref). Both data tables are strictly INSERT-only.

The `claims` and `claim_meta` schemas (`factgraph.core.store.ledger._DDL`):

```sql
CREATE TABLE IF NOT EXISTS claims (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id    TEXT NOT NULL UNIQUE,
    pred_id    TEXT NOT NULL,
    e_ref      TEXT NOT NULL,
    rest_terms TEXT,                 -- legacy n-ary carrier; new writes store "[]"
    value      TEXT,                 -- unary fact value (with value_tag)
    value_tag  TEXT,
    tx_ref     INTEGER NOT NULL,     -- the commit (tx_seq) that wrote this claim
    CHECK ((value IS NULL) = (value_tag IS NULL))
);

CREATE TABLE IF NOT EXISTS claim_meta (
    asrt_id     TEXT NOT NULL,
    key         TEXT NOT NULL,
    kind        TEXT,                -- NULL only for an UNSET tombstone
    value       TEXT,                -- NULL only for an UNSET tombstone
    tx_seq      INTEGER NOT NULL,
    op_ordinal  INTEGER NOT NULL,
    PRIMARY KEY (asrt_id, key, tx_seq, op_ordinal),
    CHECK ((kind IS NULL) = (value IS NULL))
);
```

Revoke is not a table: a partial index `idx_claims_revokes ON claims(value) WHERE pred_id = '__system__.revokes'` gives revoke lookups the same speed a dedicated table would.

### 4.1 The append-only invariant

Both data tables (`claims` and `claim_meta`) never UPDATE or DELETE a row. Retract is **one** INSERT (the `__system__.revokes` claim); re-setting a meta key is one INSERT (a new event); schema mutation is INSERTs into a new content-addressed schema object. The only mutable state is `ledger_meta`, which holds the head transaction id, transaction sequence, state digest, digest scheme, current schema digest, and Database id needed to navigate and verify the immutable record stream.

### 4.2 Comparison with similar designs

| System | Storage primitive | Append-only? | Mutability boundary |
|---|---|---|---|
| **FactGraph** | unary `Claim` row (`value` / `value_tag`) + `claim_meta` event stream + revoke-as-Claim | yes (`claims` + `claim_meta`) | `ledger_meta` head pointers |
| Datomic | datom 5-tuple `(E, A, V, T, Op)` | yes; retract is `Op=:db/retract` | transaction layer is content-addressed |
| Event sourcing | immutable event record | yes | derived aggregate state may be cached/replayed |
| Git | content-addressed blob / tree / commit | yes for objects | refs (HEAD, branches) are mutable pointers |
| Conventional SQL OLTP | row | no — UPDATE / DELETE allowed | every row is mutable |

FactGraph sits closest to Datomic (immutable assertion + retract-as-record) and shares the git-style "immutable content + mutable pointer" split via the `ledger_meta` table. The eventized `claim_meta` also gives meta the classic event-sourcing property: latest-effective by default, full history replayable.

### 4.3 Migration and remaining legacy shape

The three-table claim-first layout **shipped** in Slice 3b (`CHANGELOG.md` → *"Ledger persistence converges from seven tables to three"*). Two real caveats carry forward:

- **`rest_terms` column retained.** It stays as a compatibility carrier for the PyReason n-ary adapter until that adapter is rewritten. Dropping the column, strict unary INV-9 enforcement, and the adapter rewrite are bundled into a later slice (Slice 5). New writes already store `[]`.
- **Migrating older workspaces.** A v0.2 workspace (`ledger.db`) migrates once via `python -m factgraph migrate-workspace <path>`; the CLI stages, verifies, and archives the source. Unreleased v0.3 **development** workspaces that carry the intermediate seven-table layout have **no upgrade path** and fail closed on open — rebuild them, or remigrate from the original v0.2 source.

The authoritative table/column/digest definitions live in the ledger schema specification (§2–§6) and the `core/store` module contract.

## 5. Reference

### 5.1 Types

`factgraph.core.store.ledger` — these are **logical / write-side input types**; the on-disk shape is the three tables in §4, not these dataclasses one-for-one:

```python
@dataclass(frozen=True)
class Claim:                          # on disk: claims row (+ value / value_tag / tx_ref columns)
    asrt_id: str
    pred_id: str
    e_ref: str
    rest_terms: list[tuple[str, Any]]

@dataclass(frozen=True)
class MetaRow:                        # on disk: one claim_meta event (asrt_id, key, kind, value, tx_seq, op_ordinal)
    asrt_id: str
    key: str
    kind: str                         # one of: str, int, float, bool, time, json
    value: Any

@dataclass(frozen=True)
class Revokes:                        # on disk: a __system__.revokes claims row (no revokes table)
    revoker_asrt_id: str
    revoked_asrt_id: str

META_KINDS = {"str", "int", "float", "bool", "time", "json"}
```

`factgraph.sdk.AssertionMeta` is the read-side projection of a claim's effective meta events. It exposes typed slots for canonical keys (`source`, `trace_id`, `ingested_at`, `approved_by`, `note`, `derived_rule_id`, `derived_rule_version`, `candidate_id`, `candidate_key`, `candidate_kind`) plus `raw: dict[str, Any]` for any other keys.

### 5.2 Errors

| Raised by | Type | Message |
|---|---|---|
| direct retract of Identity Claim | `SDKStoreError` (`code="INV_7C_IDENTITY_PROTECTED"`) | identity claims must be revoked via `fg.entities.delete(...)` |
| direct retract of `:exists` Claim | `SDKStoreError` (`code="EXISTENCE_CLAIM_TRANSITIONAL_GUARD"`) | use `fg.entities.delete(...)` for whole-entity removal |
| meta pairing violation | `WriteProtocolError` | `meta[raw_kind] and meta[bound] must be provided together` |
| `raw_kind` value invalid | `WriteProtocolError` | `meta[raw_kind] must be one of: ...` |
| `bound` shape invalid | `WriteProtocolError` | `meta[bound] must be a two-element JSON list` |
| legacy `confidence` key | `WriteProtocolError` | `meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.` |
| unknown `kind` value | `WriteProtocolError` | meta value kind must be one of: str, int, float, bool, time, json |
| append / UNSET of an S-class key (`ingested_at` / `ingest_key` / `revoked_asrt_id`) | `SDKStoreError` | `meta append cannot override system-managed key(s): ...` — use `event_time` for source timestamps |
