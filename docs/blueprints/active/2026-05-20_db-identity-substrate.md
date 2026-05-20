# Task Blueprint: DB Identity Substrate

- Status: draft
- Created: 2026-05-20
- Last Updated: 2026-05-20
- Related Modules:
  - `src/factgraph/core/store/ledger.py`
  - `src/factgraph/core/evidence/write_protocol.py`
  - `src/factgraph/core/protocol/digests.py`
  - `src/factgraph/core/protocol/tup_v1.py`
  - `src/factgraph/core/schema/schema_ir.py`
  - `src/factgraph/core/store/_support.py`
  - `src/factgraph/core/view/projector.py`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](../../audit/2026-05-20_database-view-design-vs-shipped-runtime.md)
  - [docs/audit/2026-05-20_post-q-db-view-synthesis.md](../../audit/2026-05-20_post-q-db-view-synthesis.md)
  - [docs/decisions/2026-05-20_q1-database-class-boundary-decision.md](../../decisions/2026-05-20_q1-database-class-boundary-decision.md)
  - [docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md](../../decisions/2026-05-20_q3-tx-identity-primitives-decision.md)
  - [docs/decisions/2026-05-20_q5-view-revocation-composition-decision.md](../../decisions/2026-05-20_q5-view-revocation-composition-decision.md)
  - [docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md](../../decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md)
  - [docs/references/working/design-points/database-view-fg-layered-architecture.zh.md](../../references/working/design-points/database-view-fg-layered-architecture.zh.md)
- Audit Log:
  - [2026-05-20_db-identity-substrate.audit.md](./2026-05-20_db-identity-substrate.audit.md)

## 1. Problem

The DB/view audit found that the shipped runtime has a `Ledger`-centered storage substrate, UUID-style assertion ids, no `Database` boundary, no `DatabaseValue`, no `tx_id`, and no canonical durable 7-field `AssertionRecord`.

Q1, Q3, Q5, and Q7 closed the load-bearing design questions for this slice:

- Q1: `Database` is a new boundary above shipped `Ledger`.
- Q3: `Database` owns transaction and data identity protocols (`tx_id`, `data_digest`, assertion id envelope).
- Q5: no-view `DatabaseValue.data_digest` uses the active-only assertion universe for the snapshot.
- Q7: the canonical durable assertion record is the design 7-field shape, with shipped `Claim` / application DTO / SDK record treated as projections or adapters.

This blueprint scopes the first implementable DB/view slice: the identity substrate that later workspace layout, view persistence, and attach lifecycle work depend on.

## 2. Goals

- Introduce a `Database` boundary above `Ledger` without renaming `Ledger` or pretending `Ledger` already satisfies the design.
- Define and implement durable identity primitives required by the DB/view design:
  - `db_id`
  - `tx_id`
  - `data_digest`
  - `assertion_digest`
  - content-addressed `asrt_id`
- Define and implement a canonical durable 7-field `AssertionRecord` shape:
  - `asrt_id`
  - `pred_id`
  - `fact_tuple`
  - `schema_digest`
  - `assertion_digest`
  - `tx_id`
  - `meta`
- Provide a minimal append-only `Database.commit_assertions(...)` boundary for new Database-owned writes.
- Preserve shipped `Ledger` as storage/index substrate and preserve shipped SDK/write-protocol compatibility paths unless a later scoped migration explicitly changes them.
- Add focused tests that prove cross-process deterministic identity for the new Database-owned identities.

## 3. Non-goals

- Do not implement workspace physical layout (`db/objects/`, `db/refs/`, `db/assertions.db`, manifest reshape). That is a later slice.
- Do not implement `FactGraph.attach(...)`, snapshot attach, or view-scoped attach. Those belong to the attach lifecycle slice.
- Do not implement `FrozenAssertionView`, `view_digest`, view persistence, or view scope filtering. Those belong to the view slice.
- Do not implement public `fg.read.find(view=...)` or `fg.eval.evaluate(view=...)` semantics. Those remain cross-doc blocked.
- Do not implement `EvaluateResult`, `EvidenceGraph.metadata`, evidence failure envelopes, or `rule_set_digest`.
- Do not implement SavedRule / registry migration. That belongs to the Q8/Q6 migration slice.
- Do not lock concrete `path=` filesystem layout for `Database.create(...)` / `Database.open(...)`;treat `path` as an opaque storage handle whose concrete layout is the workspace slice's responsibility.
- Do not remove shipped `fg.retract`, `retract_by_asrt`, `replace_field`, UUID-style legacy assertion rows, or low-level `Ledger` methods in this slice.
- Do not expose retract/update/schema-migration methods on `Database` v1.
- Do not introduce a broad user-facing `canonical_meta(...)` API or any meta encoding framework detached from shipped `MetaRow` semantics.

## 4. Current Context

- Current storage substrate:
  - `Ledger` owns SQLite tables and exposes `append_assertion(...)`, `append_revocation(...)`, low-level deprecated append methods, annotation writes, and lifecycle metadata writes.
  - Shipped assertion ids are UUID-style (`_new_asrt_id()` / `new_assertion_id()`).
- Current write path:
  - SDK mutation paths route through application write protocol and then `Ledger.append_assertion(...)`.
  - Retract / replace paths exist as compatibility behavior but are not part of the new Database v1 boundary.
- Current canonical primitives:
  - `sha256_hex(...)` / `sha256_token(...)` exist.
  - `canonical_bytes_tup_v1(...)` exists for tagged fact tuples.
  - `schema_digest(...)` exists and must be reused.
- Current shape conflict:
  - `Claim(asrt_id, pred_id, e_ref, rest_terms)` is storage shape.
  - `AssertionRecordDTO(assertion_id, value, active, meta)` is application read DTO.
  - SDK `AssertionRecord(...)` is public read surface.
  - None of those is the canonical durable 7-field Database assertion record.

## 5. Proposed Shape

### 5.1 Module placement

This slice should introduce a new DB identity substrate under `src/factgraph/core/store/` or a closely adjacent core package. The exact file split is implementation detail, but ownership should stay below SDK and above raw `Ledger`.

Expected module responsibilities:

- `Database`
  - owns `db_id`;
  - owns current head identity;
  - exposes `create(...)`, `open(...)`, `head()` and `commit_assertions(...)` shape for this slice;
  - uses `Ledger` as storage/index substrate or compatibility backing.
  - treats `create(path=...)` / `open(path=...)` path values as opaque storage handles in this slice;concrete `db/objects/` / `db/refs/` filesystem layout belongs to the workspace physical layout slice.
- `DatabaseValue`
  - immutable snapshot identity with at least `db_id`, `tx_id`, `schema_digest`, and `data_digest`;
  - no runtime attachment behavior.
- `AssertionRecord`
  - canonical durable 7-field Database-owned record;
  - not the same as shipped storage/application/SDK read shapes.
- identity helpers:
  - `canonical_bytes_dbtx_v1(...)`;
  - `canonical_bytes_dbdata_v1(...)`;
  - `canonical_bytes_assertion_v1(...)`;
  - helpers for `tx:<hex>`, `asrt:<hex>`, and `sha256:<hex>` tokens.

### 5.2 Identity rules

This slice must follow Q3:

- `tx_id = "tx:" + sha256_hex(canonical_bytes_dbtx_v1(tx_payload))`
- `data_digest = "sha256:" + sha256_hex(canonical_bytes_dbdata_v1(data_payload))`
- `assertion_digest = "sha256:" + sha256_hex(canonical_bytes_assertion_v1(assertion_payload))`
- `asrt_id = "asrt:" + sha256_hex(canonical_bytes_assertion_v1(assertion_payload))`

`canonical_bytes_dbtx_v1(...)` must use the `factpy\0dbtx_v1\0` namespace.

`canonical_bytes_dbdata_v1(...)` must use the `factpy\0dbdata_v1\0` namespace.

`canonical_bytes_assertion_v1(...)` must use the `factpy\0assertion_v1\0` namespace.

For this identity slice, `DatabaseValue.data_digest` is defined for the default no-view snapshot universe. Per Q5, that universe is active-only at the snapshot tx: assertions with an active revocation are excluded from the member set used by `canonical_bytes_dbdata_v1(...)`. View-scoped data-digest semantics are not implemented in this slice.

### 5.3 Assertion record rules

The canonical durable `AssertionRecord` must keep the Q7 field semantics:

- `fact_tuple = (("entity_ref", e_ref), *rest_terms)`
- canonical fact bytes use `canonical_bytes_tup_v1(fact_tuple)`
- assertion identity payload includes:
  - `pred_id`
  - canonical `fact_tuple` bytes
  - `schema_digest`
  - canonical assertion `meta`
- assertion identity payload excludes:
  - `asrt_id`
  - `assertion_digest`
  - `tx_id`
  - SQLite row ids
  - UUID-style shipped assertion ids
  - local path / process / host data

`tx_id` is required on the durable record as transaction membership / provenance, but it is not part of assertion identity.

Canonical assertion `meta` encoding must be based on shipped `MetaRow` semantics:

- `META_KINDS = {"str", "int", "float", "bool", "time", "json"}`
- ledger JSONable value domain from shipped `core/store/ledger.py`
- raw user meta dictionaries are write-normalization inputs, not identity inputs;
- assertion identity canonicalizes the normalized `MetaRow` sequence for the assertion, ordered deterministically by `(key, kind, canonical value bytes)`.

This slice may introduce a Database-owned assertion-meta encoder, but it must not introduce a broad user-facing `canonical_meta(...)` API.

### 5.4 Database v1 write boundary

`Database.commit_assertions(...)` is the only new Database v1 write boundary in this slice.

This blueprint intentionally leaves the exact Python signature open until implementation audit, but the behavior must obey:

- append assertions only;
- no retract/update/schema-migration Database methods;
- content-addressed assertion identity;
- transaction identity independent of wall-clock time, process, path, SQLite sequence ids, UUIDs, and authoring registry material;
- deterministic output across processes for equivalent logical inputs.

Transactional atomicity and batching semantics for `commit_assertions(...)` are implementation preflight decisions. This draft locks the boundary and identity invariants, not whether the final implementation is single-call all-or-nothing, streaming, or staged through another transaction helper.

### 5.5 Legacy compatibility

Existing shipped write paths remain compatibility surfaces during this slice:

- `Ledger.append_assertion(...)`
- `Ledger.append_revocation(...)`
- low-level deprecated Ledger append methods
- SDK `set/add/retract`
- `write_protocol.set_field(...)`
- `write_protocol.retract_by_asrt(...)`
- `write_protocol.replace_field(...)`

This slice may add adapters so new Database-owned writes project into `Ledger`, but it must not remove or silently rewrite legacy paths without a separate migration blueprint.

## 6. Boundaries And Invariants

- `Database` is a new boundary above `Ledger`;`Ledger` is not renamed to `Database`.
- `Ledger` remains a low-level storage/index substrate and compatibility layer.
- `Database` owns new durable identities;`Ledger` does not own `tx_id`, `data_digest`, or canonical content-addressed `asrt_id`.
- `Database` v1 exposes only append-assertion semantics for new Database-owned writes.
- `schema_digest(...)` must be reused;no parallel schema digest algorithm.
- `_compute_ingest_key(...)` must not be reused as `tx_id` or as transaction payload template.
- `canonical_bytes_tup_v1(...)` may be used inside `assertion_v1`, but not as the whole transaction payload.
- `data_digest` is path-independent over the chosen assertion universe;for this no-view identity slice, that universe is the Q5 active-only snapshot universe.
- `tx_id` is path-sensitive over parent tx, added assertion digests, schema digest, and data digest.
- `AssertionRecord` 7-field canonical durable shape is not a public SDK read DTO by default.
- Canonical assertion `meta` encoding must be based on shipped `MetaRow` semantics;no parallel broad meta canonicalization framework.
- Engine projection `build_args_for_claim(...)` is not assertion identity payload;only `canonical_bytes_tup_v1(fact_tuple)` is the fact-argument identity input.
- Shipped `ProjectedFact.fact_tuple` is an untagged engine-projection tuple and is not the canonical tagged identity `fact_tuple`.
- No cross-doc evidence/evaluate metadata carrier is introduced in this slice.

## 7. Acceptance

- [ ] `Database` exists as a distinct boundary above `Ledger`;tests prove `Ledger` was not treated as already satisfying `Database`.
- [ ] `DatabaseValue` or equivalent immutable snapshot identity exists with `db_id`, `tx_id`, `schema_digest`, and `data_digest`.
- [ ] `tx_id` uses a deterministic `factpy\0dbtx_v1\0` canonical byte protocol and `tx:<hex>` token form.
- [ ] `data_digest` uses a deterministic `factpy\0dbdata_v1\0` canonical byte protocol and `sha256:<hex>` token form.
- [ ] `data_digest` tests prove the no-view member set is active-only per Q5 and path-independent for equivalent active assertion universes.
- [ ] `AssertionRecord` canonical durable 7-field shape exists and is separate from shipped `Claim`, application DTO, and SDK read record.
- [ ] `asrt_id` / `assertion_digest` derive from `factpy\0assertion_v1\0` canonical bytes and are deterministic across processes.
- [ ] `assertion_v1` canonical bytes include `pred_id`, canonical `fact_tuple`, `schema_digest`, and canonical assertion `meta`;they exclude `asrt_id`, `assertion_digest`, and `tx_id`.
- [ ] Canonical assertion `meta` tests cover normalized `MetaRow` sequences rather than raw user meta dict identity.
- [ ] Existing shipped retract/update compatibility paths are not folded into Database v1.
- [ ] No workspace layout, view, attach, registry, evidence, or rule-expression surface is introduced.
- [ ] A source-grep check confirms no new `evaluate(view=...)`, `read.find(view=...)`, `EvidenceGraph.metadata`, or `rule_set_digest` implementation was added by this slice.
- [ ] A source-grep check confirms identity code does not import `ProjectedFact` or use `build_args_for_claim(...)`.
- [ ] Affected module docs are updated.
- [ ] If this blueprint or new decision artifacts add durable docs entries, `docs/README.md` is updated.

## 8. Implementation Plan

This section is intentionally a draft until implementation preflight completes. Before moving to `scoped`, perform a fresh source audit of the shipped `Ledger`, write protocol, protocol canonicalization helpers, schema digest, and SDK write paths.

1. Define Database identity protocols and helpers.
   - Add `dbtx_v1`, `dbdata_v1`, and `assertion_v1` canonical byte encoders.
   - Reuse shipped digest helpers and `canonical_bytes_tup_v1(...)`.
   - Add deterministic unit tests, including process-independent fixtures.
2. Define canonical DTOs.
   - Add `DatabaseValue`.
   - Add canonical durable `AssertionRecord`.
   - Define any assertion input shape needed to construct the durable record without leaking SDK DTO semantics.
3. Define `Database` boundary.
   - Add `create(...)`, `open(...)`, `head()`, and minimal `commit_assertions(...)` behavior.
   - Decide composition with `Ledger` during implementation preflight, while preserving Q1's boundary invariant.
4. Project Database records into shipped storage.
   - Map canonical `AssertionRecord` into `Ledger` storage rows.
   - Keep shipped `Claim` / `ClaimArg` / `MetaRow` as storage projections.
5. Add compatibility and non-regression tests.
   - Verify shipped SDK/read DTO paths are not accidentally broken.
   - Verify legacy retract/update paths are not folded into Database v1.
6. Update module docs.
   - Document the new Database identity substrate in core docs.
   - Document compatibility boundaries if SDK docs are affected.

## 9. Docs To Update

- `src/factgraph/core/docs/README.md` or an adjacent core/store module doc describing the Database identity substrate.
- `src/factgraph/sdk/docs/README.md` only if public SDK compatibility semantics are mentioned or affected.
- `docs/README.md` if a new durable docs entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- final landed modules and public/internal boundaries;
- any implementation deviations from Q1/Q3/Q7;
- any compatibility paths left intentionally legacy;
- archive / follow-up notes for workspace layout, view, attach, registry, or cross-doc redraft work.
