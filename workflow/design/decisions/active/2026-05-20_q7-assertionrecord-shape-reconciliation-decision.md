# Q7 Decision: AssertionRecord Shape Reconciliation

- Status: closed
- Created: 2026-05-20
- Branch: `v0.1-q7-assertionrecord-shape-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_preflight_code_audit_required.md`
  - `feedback_audit_execution_discipline.md`
- Scope: reconcile design A13's 7-field `AssertionRecord` commitment with shipped storage / application / SDK assertion shapes, and close the assertion-payload shape deferred by Q3.
- Non-scope: Q1 `Database` boundary, Q3 transaction/data identity primitives, Q8 SavedRule governance, Q2 attach lifecycle, Q4 `FrozenAssertionView`, Q5 view active-set semantics, evidence/evaluate metadata carriers.

## 1. Decision

Q7 chooses a **canonical durable assertion record with shipped adapters**.

The design A13 7-field shape is retained as the canonical Database-owned durable assertion record:

```text
AssertionRecord(
  asrt_id: str,
  pred_id: str,
  fact_tuple: tuple[tuple[str, Any], ...],
  schema_digest: str,
  assertion_digest: str,
  tx_id: str,
  meta: Mapping[str, Any],
)
```

This record is the durable shape for new Database-owned assertion writes after the Database migration starts. It is not a cosmetic rename of any shipped shape.

Shipped shapes remain as adapters / projections during migration:

- `core.store.ledger.Claim(asrt_id, pred_id, e_ref, rest_terms)` remains the low-level SQLite storage/index row under Q1's "Database above Ledger" boundary.
- `application.protocol.entity_read.AssertionRecordDTO(assertion_id, value, active, meta)` remains an application read DTO.
- `sdk.facade.AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta)` remains a public SDK read surface during compatibility.

The shipped shapes do **not** satisfy A13 by themselves. They are compatibility/projection layers around the canonical durable record.

## 2. Canonical Field Semantics

### 2.1 `asrt_id` and `assertion_digest`

`assertion_digest` is a generic digest token:

```text
assertion_digest = "sha256:<hex>"
```

`asrt_id` is the typed assertion identifier derived from the same hash:

```text
asrt_id = "asrt:<hex>"
```

Per Q3, `asrt_id` and `assertion_digest` are the assertion identity envelope. Q7 closes the assertion payload shape they are derived from.

### 2.2 Non-circular assertion payload

`assertion_v1` identity is non-circular.

The canonical identity payload includes:

- format/domain marker: `factpy\0assertion_v1\0`
- `pred_id`
- canonical `fact_tuple` bytes
- `schema_digest`
- canonical assertion `meta`

The canonical identity payload MUST NOT include:

- `asrt_id` (derived from payload)
- `assertion_digest` (derived from payload)
- `tx_id` (transaction membership / provenance, not assertion content)
- SQLite row ids / sequence ids
- UUID-style shipped assertion ids
- local path / process / host information

Consequence: the same logical assertion in the same schema with the same assertion meta has the same `asrt_id` even if it appears in different transactions. `tx_id` records the transaction that added or carried the assertion; it is not part of assertion content identity.

### 2.3 `fact_tuple`

`fact_tuple` is the canonical tagged fact-argument tuple, not a new untyped fact API.

It is defined as:

```text
fact_tuple = (("entity_ref", e_ref), *rest_terms)
```

where shipped `rest_terms` already use `(tag, value)` pairs.

This preserves the shipped fact model:

- shipped storage splits the entity ref and rest terms as `Claim.e_ref` + `Claim.rest_terms` (`src/factgraph/core/store/ledger.py:21-26`);
- shipped write protocol accepts `pred_id`, `e_ref`, and `rest_terms` (`src/factgraph/core/evidence/write_protocol.py:128-157`);
- shipped `tup_v1` defines canonical tags and byte encoding (`src/factgraph/core/protocol/tup_v1.py:10-23`, `:133-168`);
- shipped SQLite claim-arg storage has a separate row encoding via `claim_args_from_rest_terms(...)` (`src/factgraph/core/protocol/tup_v1.py:196-210`).

Q7 chooses `canonical_bytes_tup_v1(fact_tuple)` as the canonical fact-argument bytes inside `assertion_v1`.

The untagged engine projection tuple returned by `build_args_for_claim(...)` (`src/factgraph/core/view/projector.py:90-114`) is **not** the assertion identity tuple. It is a runtime engine fact projection.

### 2.4 `schema_digest`

`schema_digest` is the existing digest token from `schema_digest(...)`, reused per Q3. It participates in assertion identity so the same predicate / fact tuple in different compiled schemas can produce different assertion identities.

### 2.5 `tx_id`

`tx_id` is a required field on the durable `AssertionRecord`, but it is not part of the assertion identity payload.

Rationale: `tx_id` says which Database transaction added / carried the assertion. It is transaction provenance and snapshot membership, not assertion content. Including it in assertion identity would make identical assertion content produce different `asrt_id` values across transactions, contradicting content-addressed assertion identity.

### 2.6 `meta`

`meta` is part of the durable assertion record and assertion identity, but Q7 does **not** introduce a broad standalone `canonical_meta(...)` API.

The canonical assertion meta input is the assertion-scoped meta represented by shipped `MetaRow` semantics:

- `MetaRow(asrt_id, key, kind, value)` (`src/factgraph/core/store/ledger.py:37-42`);
- `META_KINDS = {"str", "int", "float", "bool", "time", "json"}` (`src/factgraph/core/store/ledger.py:15`);
- values use the shipped ledger JSONable value domain (`src/factgraph/core/store/ledger.py:204-217`).

Future blueprints must specify the exact `assertion_v1` meta byte encoding by auditing this shipped meta row model. They may add a Database-owned assertion-meta encoder, but must not reintroduce the failed Phase C pattern of a broad user-facing `canonical_meta` helper detached from shipped `MetaRow` semantics.

## 3. Rejected Alternatives

### 3.1 Option (a) — Replace all shipped layers with the 7-field shape immediately

Rejected as the immediate migration path.

Reason: it treats storage rows, application read DTOs, and public SDK read surfaces as if they were the same layer. Shipped has distinct responsibilities:

- `Claim(asrt_id, pred_id, e_ref, rest_terms)` is storage/index shape (`src/factgraph/core/store/ledger.py:21-26`);
- `AssertionRecordDTO(assertion_id, value, active, meta)` is application read DTO (`src/factgraph/application/protocol/entity_read.py:60-72`);
- SDK `AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta)` is public read surface (`src/factgraph/sdk/facade.py:87-96`).

Replacing all three in one step would be a large public/API/storage break and would conflate layers Q1 intentionally separated.

Q7 still preserves the design 7-field record as canonical durable shape. It rejects only "replace every shipped layer immediately".

### 3.2 Option (b) — Keep shipped 3-layer separation and revise away A13

Rejected.

Reason: this softens design strictness to fit shipped reality. A13 explicitly locks `asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta`; the audit classifies shipped shape coexistence as a problem, not a feature.

Keeping the shipped layers as adapters is acceptable. Treating them as the design-complete answer is not.

### 3.3 Option (c) — Add an unbounded fourth public AssertionRecord layer

Rejected in its naive form.

Reason: adding a fourth user-facing shape would reproduce the Phase C failure mode: parallel concepts with overlapping responsibilities (`Claim` / DTO / SDK record / design record) and no clear ownership boundary.

Q7's chosen path is narrower: the 7-field shape is the **Database-owned canonical durable record**, not a new public read DTO. Existing shipped shapes are projections/adapters around it until their own migration blueprints decide otherwise.

## 4. Shipped Shape Mapping

| Shipped shape | Role after Q7 | Relationship to canonical durable record |
|---|---|---|
| `Claim(asrt_id, pred_id, e_ref, rest_terms)` | Low-level storage/index row | Projection from canonical record into Ledger storage. `e_ref + rest_terms` map to canonical `fact_tuple`. |
| `ClaimArg(asrt_id, idx, val_atom, tag)` | SQLite argument index row | Storage projection from tagged `fact_tuple` via shipped `claim_args_from_rest_terms(...)` semantics. |
| `MetaRow(asrt_id, key, kind, value)` | SQLite meta row | Storage projection from canonical assertion `meta`; exact identity bytes specified by future assertion_v1 blueprint under Q7 constraints. |
| `AssertionRecordDTO(assertion_id, value, active, meta)` | Application read DTO | Read projection, not durable identity record. `active` is read-time state, not part of canonical assertion content. |
| SDK `AssertionRecord(asrt_id, value, is_active, entity_type, field_name, pred_id, e_ref, meta)` | Public SDK read surface | Public projection. It may later gain anchors, but Q7 does not require immediate SDK break. |

## 5. Consequences

### 5.1 Q3 assertion payload deferral closes

Q3 deferred assertion-payload field list, names, ordering, and encoding to Q7. Q7 closes the field-level decision:

- durable record fields are exactly A13's 7 fields;
- assertion identity payload includes `pred_id`, `fact_tuple`, `schema_digest`, and `meta`;
- assertion identity payload excludes derived fields (`asrt_id`, `assertion_digest`) and transaction membership (`tx_id`).

Exact byte serialization for assertion meta is blueprint-level work constrained by §2.6.

### 5.2 Q1 Database boundary is preserved

Q1 established Database above Ledger. Q7 follows that boundary:

- Database owns canonical durable assertion record and assertion identity.
- Ledger remains storage/index implementation detail.
- Database writes may project records into Ledger rows.
- Legacy Ledger UUID assertion ids remain compatibility ids until migrated.

### 5.3 Q2 / Q4 / Q5 unaffected

Q7 does not decide attach lifecycle, view shape, or view active-set semantics.

The only cross-link is that `fact_tuple` and `asrt_id` become stable enough for future Database / view commitments to reference.

### 5.4 SDK compatibility path remains open

Q7 does not force an immediate public SDK `AssertionRecord` breaking change.

Future SDK-facing blueprints may choose one of:

- keep SDK `AssertionRecord` as a read projection indefinitely;
- add optional identity anchor fields to SDK `AssertionRecord`;
- introduce a separate advanced Database assertion-inspection surface.

Those are SDK API decisions, not Q7's durable-record decision.

### 5.5 Q8 unaffected

Q8 governs SavedRule persistence and the rule/inference registry layer. Q7 governs assertion record shape. They are mutually orthogonal;Q7 does not reopen or modify Q8.

## 6. Acceptance Criteria For This Decision

Future Q7-dependent blueprints must obey:

1. Do treat A13's 7-field shape as the canonical Database-owned durable assertion record.
2. Do NOT claim shipped `Claim`, `AssertionRecordDTO`, or SDK `AssertionRecord` already satisfies A13.
3. Do NOT replace all shipped layers in one unscoped breaking change.
4. Do construct canonical `fact_tuple` from shipped fact model as `(("entity_ref", e_ref), *rest_terms)`.
5. Do use `canonical_bytes_tup_v1(fact_tuple)` for canonical fact-argument bytes inside `assertion_v1`.
6. Do NOT use `build_args_for_claim(...)` engine projection as assertion identity payload.
7. Do NOT include `asrt_id`, `assertion_digest`, or `tx_id` in the assertion identity payload.
8. Do include `tx_id` as a required durable record field, but treat it as transaction provenance / membership.
9. Do derive `asrt_id` from `assertion_digest` using Q3's `asrt:<hex>` convention.
10. Do base canonical assertion meta on shipped `MetaRow` semantics; do NOT introduce a broad user-facing `canonical_meta(...)` API without a separate shipped-meta audit.
11. Do keep Ledger storage rows as projections/adapters under the Q1 Database boundary.
12. Do keep SDK read surface migration separate from canonical durable record adoption.

## 7. Decision Record

Q7 resolution: **canonical durable assertion record with shipped adapters**.

The canonical Database-owned durable record uses A13's 7 fields:

```text
asrt_id / pred_id / fact_tuple / schema_digest / assertion_digest / tx_id / meta
```

`fact_tuple` is the tagged canonical tuple `(("entity_ref", e_ref), *rest_terms)` and uses shipped `canonical_bytes_tup_v1(...)` for fact-argument bytes. `assertion_v1` identity excludes `asrt_id`, `assertion_digest`, and `tx_id`; `tx_id` remains a required record field as transaction provenance.

Shipped `Claim`, `AssertionRecordDTO`, and SDK `AssertionRecord` are adapters/projections, not the canonical durable record. They may survive migration as compatibility/read surfaces, but they do not satisfy A13 by themselves.
