# Task Blueprint Audit: DB Identity Substrate

- Blueprint: [2026-05-20_db-identity-substrate.md](./2026-05-20_db-identity-substrate.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-20 | draft | Blueprint created | Scope derived from post-Q synthesis slice 1: Q1/Q3/Q7 rows only. |
| 2026-05-20 | draft | Review polish applied | Added meta canonicalization boundary, opaque `path=` boundary, `commit_assertions` atomicity deferral, and engine projection non-identity invariant. |
| 2026-05-20 | draft | Preflight amendment applied | Consumed preflight findings PF-1/PF-2/PF-3 before any `scoped` decision. |

## Decision Notes

### 2026-05-20 — Scope limited to identity substrate

This blueprint intentionally covers only the first synthesis slice:

- `Database` boundary above `Ledger`
- `DatabaseValue`
- transaction/data/assertion identity protocols
- canonical durable 7-field `AssertionRecord`
- minimal append-only `Database.commit_assertions(...)` boundary

It explicitly excludes workspace layout, view shape/persistence, attach lifecycle, registry/SavedRule migration, and cross-doc evidence/rule-expression seams.

### 2026-05-20 — Q decisions consumed

The draft consumes:

- Q1 (`13dde310`): `Database` is a new boundary above `Ledger`.
- Q3 (`4ba11428`): dedicated `factpy\0dbtx_v1\0` / `factpy\0dbdata_v1\0` identity protocols and assertion identity envelope.
- Q5 (`b932e675`): no-view snapshot universe is active-only;view-scoped universe is exact `view.asrt_ids` and remains out of this slice.
- Q7 (`ed1fd3d9`): canonical durable 7-field assertion record with shipped adapters.

No new Q is opened by this blueprint draft.

### 2026-05-20 — Draft review boundary clarifications

Review identified four precision updates before commit:

- canonical assertion `meta` must stay tied to shipped `MetaRow` semantics and must not introduce a broad user-facing `canonical_meta(...)` API;
- `Database.create(...)` / `Database.open(...)` may exist in this slice, but any `path=` is an opaque storage handle until the workspace physical layout slice defines concrete files/directories;
- `commit_assertions(...)` atomicity / batching semantics remain implementation-preflight decisions;
- `build_args_for_claim(...)` engine projection is not assertion identity payload.

### 2026-05-20 — Preflight PF-1: `data_digest` consumes Q5

Preflight `1188396b` found that the blueprint could not move to `scoped` while `DatabaseValue.data_digest` still referenced Q3's "chosen assertion universe" without consuming Q5.

Amendment:

- add Q5 as a related decision and consumed design input;
- define this slice's `DatabaseValue.data_digest` over the default no-view active-only snapshot universe;
- leave view-scoped data-digest semantics out of scope;
- add acceptance that tests prove active-only membership and path independence.

### 2026-05-20 — Preflight PF-2: canonical `meta` uses normalized `MetaRow`

Preflight found that "canonical assertion meta" was still ambiguous between raw user meta dictionaries and shipped storage semantics.

Amendment:

- raw user meta dictionaries are explicitly write-normalization inputs, not identity inputs;
- assertion identity canonicalizes the normalized `MetaRow` sequence for the assertion;
- deterministic ordering is by `(key, kind, canonical value bytes)`;
- acceptance requires tests against normalized `MetaRow` sequences.

### 2026-05-20 — Preflight PF-3: projected fact tuple name collision

Preflight found a second engine-projection collision beyond `build_args_for_claim(...)`: shipped `ProjectedFact.fact_tuple` uses the same field name but carries an untagged engine projection, not Q7's tagged identity tuple.

Amendment:

- add `src/factgraph/core/store/_support.py` and `src/factgraph/core/view/projector.py` to the related module surface;
- state that `ProjectedFact.fact_tuple` is not the canonical tagged identity `fact_tuple`;
- add acceptance that identity code must not import `ProjectedFact` or use `build_args_for_claim(...)`.
