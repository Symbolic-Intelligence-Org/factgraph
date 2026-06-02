# Data model: claims, meta, and the append-only ledger

This chapter describes what's actually stored when a FactGraph writes a fact. It complements [`schema_definition.md`](schema_definition.md) (which declares the *types*) by documenting how *instances* live in the ledger.

## 1. Claim — the atomic unit

A claim is one immutable assertion. Every successful write produces at least one claim, identified by a content-addressed `asrt_id`.

The on-disk representation (`factgraph.core.store.ledger.Claim`):

```python
@dataclass(frozen=True)
class Claim:
    asrt_id: str                            # content-addressed assertion id
    pred_id: str                            # predicate identifier
    e_ref: str                              # entity reference (idref_v1)
    rest_terms: list[tuple[str, Any]]       # value terms as (tag, value) pairs
```

A concrete claim produced by `fg.fields.set(User.name, alice, "Alice")`:

```python
Claim(
    asrt_id="asrt:9f3a...e1",
    pred_id="User.name",
    e_ref="idref_v1:User:7c12...3a",
    rest_terms=[
        ("entity_ref", "idref_v1:User:7c12...3a"),
        ("string", "Alice"),
    ],
)
```

The first element of `rest_terms` is conventionally the entity reference; the remaining elements are the typed value(s).

### 1.1 Three user-facing claim categories

The `pred_id` pattern tells you what role a claim plays:

| Category | `pred_id` shape | Created by | Retractable? |
|---|---|---|---|
| **Identity Claim** | `<EntityType>.<identity_field>` (e.g., `User.user_id`) | `fg.entities.create` | only via `fg.entities.delete` (whole entity) — direct retract raises `INV_7C_IDENTITY_PROTECTED` |
| **Field Claim** | `<EntityType>.<field>` (e.g., `User.name`) | `fg.fields.set` / `fg.fields.add` | yes — `fg.assertions.retract(asrt_id)` or `fg.fields.retract` |
| **`:exists` Claim** | `<EntityType>:exists` (e.g., `User:exists`) | auto-emitted on first `fg.entities.create` | only via `fg.entities.delete` — direct retract raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` |

Identity values are part of the entity reference's content-derived hash, so they cannot be mutated without changing the entity's `e_ref`. That's why direct identity retraction is protected.

## 2. MetaRow — annotation attached to a claim

Each claim can carry one or more meta key-value rows. The on-disk representation (`factgraph.core.store.ledger.MetaRow`):

```python
@dataclass(frozen=True)
class MetaRow:
    asrt_id: str                            # links to the Claim
    key: str                                # the meta key
    kind: str                               # one of META_KINDS
    value: Any                              # the meta value
```

`META_KINDS = {"str", "int", "float", "bool", "time", "json"}`. The `kind` column records how the value should be decoded.

A concrete MetaRow attached to the claim above, if the caller passed `meta={"source": "import"}`:

```python
MetaRow(
    asrt_id="asrt:9f3a...e1",
    key="source",
    kind="str",
    value="import",
)
```

Write meta with the `meta={...}` parameter on any write method:

```python
fg.fields.set(User.name, alice, "Alice", meta={"source": "import", "trace_id": "batch-001"})
```

Each pair becomes one MetaRow attached to the new Claim.

### 2.1 Built-in meta keys

A handful of meta keys are *canonical* — they're surfaced as typed slots on `AssertionMeta` (the read-side projection of MetaRows for one claim) and several drive special runtime mechanisms.

| Key | What it does |
|---|---|
| `source` | provenance label;typed slot on `AssertionMeta.source` |
| `trace_id` | batch / request id for audit;typed slot on `AssertionMeta.trace_id` |
| `approved_by` | approval signal;typed slot on `AssertionMeta.approved_by` |
| `note` | free-form note;typed slot on `AssertionMeta.note` |
| `ingested_at` | nanosecond timestamp consumed by snapshot projection policies (e.g., active-view freshness) |
| `version` | version label used by record-set filters (`_meta={"version": v}`) |
| `valid_from`, `valid_to` | ISO-8601 business-time markers used by record-set business-time selection (`.at(t)`) |
| `raw_kind` + `bound` | reasoning input — `ProbLog` and `PyReason` adapters consume these as uncertainty carriers (see [`assertions.md`](../official/kernel/quickstart/assertions.md) and `semantics.md`). Strict pairing: see §2.2. |
| `derived_rule_id`, `derived_rule_version` | identifies the rule and version that derived this assertion (set automatically when an inference engine writes back) |
| `candidate_id`, `candidate_key`, `candidate_kind` | links a derived claim to its candidate origin (audit / explanation surface) |

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

## 3. Append-only retract

The ledger never modifies a row in place. To "remove" a claim, the runtime appends a new record that marks it revoked. The on-disk representation (`factgraph.core.store.ledger.Revokes`):

```python
@dataclass(frozen=True)
class Revokes:
    revoker_asrt_id: str
    revoked_asrt_id: str
```

`fg.assertions.retract(asrt_id, meta={...})` produces two writes in one transaction:

- a new Claim (the revoker), which can carry its own MetaRows
- a Revokes row pointing from the revoker to the revoked

The original Claim row is **untouched**. Two consequences:

- **active** means *not revoked*. A claim is active iff no Revokes row targets its `asrt_id`.
- **all** includes both active and revoked claims — useful for history and audit replay.

For single-cardinality fields, multiple `fg.fields.set(...)` calls produce multiple active Claims (no automatic revoke). Snapshot reads project a single value by picking the latest; the assertion view shows all of them. Use `fg.fields.retract(field, ref, value)` to explicitly revoke a specific older value, or `fg.fields.delete(field, ref)` to revoke every active value for the cell.

## 4. Physical storage — SQLite tables

The ledger is a single SQLite database file. The path depends on which workspace mode you use (see [`load_and_save.md`](load_and_save.md)). The current schema has seven tables:

| Table | What it stores | Append-only? |
|---|---|---|
| `claims` | one row per Claim (`asrt_id`, `pred_id`, `e_ref`, `rest_terms`) | ✓ |
| `claim_args` | `rest_terms` exploded for index lookup (one row per `(asrt_id, idx)`) | ✓ |
| `meta_rows` | one row per MetaRow | ✓ |
| `revokes` | one row per Revokes record | ✓ |
| `annotation_rows` | separate internal annotation channel (not covered in this chapter) | ✓ |
| `ingest_keys` | idempotency keys for bulk-ingest dedup | ✓ |
| `ledger_meta` | mutable head pointers (`db_id`, `schema_digest`, `head_tx_id`, `head_data_digest`) | ✗ |

Only `ledger_meta` is mutable — it holds the head pointers (analogous to git's `HEAD` ref). Every other table is strictly INSERT-only.

The `claims` schema:

```sql
CREATE TABLE IF NOT EXISTS claims (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    asrt_id    TEXT NOT NULL UNIQUE,
    pred_id    TEXT NOT NULL,
    e_ref      TEXT NOT NULL,
    rest_terms TEXT NOT NULL
);
```

### 4.1 The append-only invariant

Six of the seven tables never UPDATE or DELETE a row. Retract is two INSERTs (one new Claim for the revoker, one Revokes row); schema mutation is INSERTs into a new schema object; even errors that "remove" a fact are recorded as new revoke records. The only mutable state is `ledger_meta`, which holds the few pointers (head transaction id, head data digest, current schema digest) needed to navigate the immutable record stream.

### 4.2 Comparison with similar designs

| System | Storage primitive | Append-only? | Mutability boundary |
|---|---|---|---|
| **FactGraph** | `Claim` 4-tuple + `MetaRow` k/v + `Revokes` link | yes (6 of 7 tables) | `ledger_meta` head pointers |
| Datomic | datom 5-tuple `(E, A, V, T, Op)` | yes; retract is `Op=:db/retract` | transaction layer is content-addressed |
| Event sourcing | immutable event record | yes | derived aggregate state may be cached/replayed |
| Git | content-addressed blob / tree / commit | yes for objects | refs (HEAD, branches) are mutable pointers |
| Conventional SQL OLTP | row | no — UPDATE / DELETE allowed | every row is mutable |

FactGraph sits closest to Datomic (immutable assertion + retract-as-record) and shares the git-style "immutable content + mutable pointer" split via the `ledger_meta` table.

### 4.3 In-flight design note

The shipped 7-table layout is the current scope. An active design — [`ledger-schema-specification.zh.md`](../../workflow/design/design-points/active/ledger-schema-specification.zh.md) — targets a simpler shape with two data tables (`claims` + `claim_meta`) plus `ledger_meta`, with revokes collapsed into a `__system__.revokes` Claim category and `claim_args` / `annotation_rows` / `ingest_keys` removed. Five related ADRs are adopted (`q-ic` / `q-api` / `q-sys-a` / `q-sys-b` / `q-inv-9`), but the implementation slice (`slice-3b-ledger-migration`) has not been scheduled yet; `core/store/ledger.py` is currently Q-PR1 sacred (no diffs allowed in v0.2.0 cycles). This chapter will be updated when the migration slice lands.

## 5. Reference

### 5.1 Types

`factgraph.core.store.ledger`:

```python
@dataclass(frozen=True)
class Claim:
    asrt_id: str
    pred_id: str
    e_ref: str
    rest_terms: list[tuple[str, Any]]

@dataclass(frozen=True)
class MetaRow:
    asrt_id: str
    key: str
    kind: str                # one of: str, int, float, bool, time, json
    value: Any

@dataclass(frozen=True)
class Revokes:
    revoker_asrt_id: str
    revoked_asrt_id: str

META_KINDS = {"str", "int", "float", "bool", "time", "json"}
```

`factgraph.sdk.AssertionMeta` is the read-side projection of a claim's MetaRows. It exposes typed slots for canonical keys (`source`, `trace_id`, `ingested_at`, `approved_by`, `note`, `derived_rule_id`, `derived_rule_version`, `candidate_id`, `candidate_key`, `candidate_kind`) plus `raw: dict[str, Any]` for any other keys.

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
