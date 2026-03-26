# Task Blueprint Audit: Annotation Store V0 Schema And Ledger

- Blueprint: [2026-03-26_annotation-store-v0-schema-and-ledger.md](./2026-03-26_annotation-store-v0-schema-and-ledger.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-26 | draft | Blueprint created | Initial implementation slice opened under the scoped Assertion Annotation Store decision blueprint. Scope frozen to `annotation_rows` durable shape, assertion-level write/read, and explicit legacy projection strategy. |
| 2026-03-26 | scoped | Promoted to scoped | Reviewed: scope aligns with parent decision blueprint, no expansion/contraction needed. Ready for Step 1 implementation (ledger durable shape). |
| 2026-03-26 | implementing | Step 1 complete | `annotation_rows` DDL + `AnnotationRow` dataclass + in-memory indexes (with upsert via `_anno_by_identity`) + `append_assertion(..., annotation_rows=...)` + `append_annotations()` + `find_annotations()` (arbitrary filter combo) + `annotation_rows` property + validation + persistence round-trip. 35 new tests (`test_annotation_store.py`), 16 regression tests green. Minor compat fix: `append_assertion` now allows placeholder empty `asrt_id` in input `meta_rows`/`annotation_rows`. |
| 2026-03-26 | implementing | Step 2 complete | `write_protocol.py`: shared annotation whitelist projection. `set_field`/`add_field`/`replace_field` now dual-write to both `meta_rows` (legacy) and `annotation_rows` (canonical). Whitelist: `shared/source` (source, source_loc, trace_id, approved_by, note) + `shared/derived` (confidence). Non-whitelisted custom meta stays in `meta_rows` only. Retraction does not produce annotations. 16 new tests (`test_write_protocol_annotations.py`), 46 total tests green. |
| 2026-03-26 | implemented | Steps 3-5 complete, blueprint closed | Step 3 (read path) already done via `find_annotations()` in Step 1. Step 4 (legacy projection) already done via dual-write in Step 2. Step 5: `01_architecture.md` updated (§4 four-layer architecture, §5.1 dual-write chain). Blueprint Outcome section filled. Total: 51 new tests, all green. Ready for archive. |

## Decision Notes

- Scope intentionally excludes provenance, rule builder, and static/audit consumer migration.
- Initial subject scope remains `assertion` only; no candidate/provenance annotation in this slice.
- `meta_rows` remains a compatibility layer in this task; no historical migration is in scope.
