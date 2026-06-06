# Task Blueprint Audit: Schema Digest Stability

- Blueprint: [2026-06-06_schema-digest-stability.md](./2026-06-06_schema-digest-stability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-06 | draft | Blueprint created | User-reported `generated_at` / schema digest instability reproduced; Stage 1 audit and Step 4.1 blueprint draft created. |

## Decision Notes

### Step 4.1 Draft Decisions

- Scope is narrow by design: exclude only top-level `generated_at` from schema identity digest.
- Keep `generated_at` as required schema object metadata.
- Keep `description`, `tags`, and `version` in digest for this slice; future metadata-policy work can revisit them.
- Keep `pattern` and `enum_values` in digest because runtime value validation consumes them.
- Schema object helpers must be updated together with `schema_digest`; a one-line `schema_digest` change would break current filename/content digest assumptions.
