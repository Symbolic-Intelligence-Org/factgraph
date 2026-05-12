# Task Blueprint Audit: Schema Field Add Lifecycle

- Blueprint: [2026-05-13_schema-field-add-lifecycle.md](./2026-05-13_schema-field-add-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Audit-first draft after schema mutation lifecycle publish. |
| 2026-05-13 | draft | Draft polish | Added superseded-class detection invariant, DSL prefix boundary, and G1 baseline sizing note. |
| 2026-05-13 | scoped | G0 scope freeze | Locked 17 field-add decisions: reuse `fg.schema.add`, same-entity replacement class, superseded class rejection, `SchemaAddResult.added_fields`, non-identity only, no defaults/backfill, additive validator extension, digest/workspace reuse, saved asset compatibility, and docs sync. |
| 2026-05-13 | scoped | G1 red baseline | Added 33-test field-add baseline: 8 failures + 11 errors + 14 guards/pass. Preservation suite remains 184/184 OK. |

## Decision Notes

- Draft source audit confirmed field-add is a same-entity class replacement
  problem, not dynamic class mutation.
- Draft recommendations preserve additive-only schema mutation, digest anchors,
  and workspace save-time behavior from the previous slice.
