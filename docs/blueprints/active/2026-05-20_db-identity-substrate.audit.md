# Task Blueprint Audit: DB Identity Substrate

- Blueprint: [2026-05-20_db-identity-substrate.md](./2026-05-20_db-identity-substrate.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-20 | draft | Blueprint created | Scope derived from post-Q synthesis slice 1: Q1/Q3/Q7 rows only. |
| 2026-05-20 | draft | Review polish applied | Added meta canonicalization boundary, opaque `path=` boundary, `commit_assertions` atomicity deferral, and engine projection non-identity invariant. |

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
- Q7 (`ed1fd3d9`): canonical durable 7-field assertion record with shipped adapters.

No new Q is opened by this blueprint draft.

### 2026-05-20 — Draft review boundary clarifications

Review identified four precision updates before commit:

- canonical assertion `meta` must stay tied to shipped `MetaRow` semantics and must not introduce a broad user-facing `canonical_meta(...)` API;
- `Database.create(...)` / `Database.open(...)` may exist in this slice, but any `path=` is an opaque storage handle until the workspace physical layout slice defines concrete files/directories;
- `commit_assertions(...)` atomicity / batching semantics remain implementation-preflight decisions;
- `build_args_for_claim(...)` engine projection is not assertion identity payload.
