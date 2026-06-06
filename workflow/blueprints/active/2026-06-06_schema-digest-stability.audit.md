# Task Blueprint Audit: Schema Digest Stability

- Blueprint: [2026-06-06_schema-digest-stability.md](./2026-06-06_schema-digest-stability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-06 | draft | Blueprint created | User-reported `generated_at` / schema digest instability reproduced; Stage 1 audit and Step 4.1 blueprint draft created. |
| 2026-06-06 | draft | Step 4.2 review + tightening | Added P1 legacy volatile-digest workspace boundary, P2 schema object identity-validation precision, and P3 deterministic timestamp test strategy. |

## Decision Notes

### Step 4.1 Draft Decisions

- Scope is narrow by design: exclude only top-level `generated_at` from schema identity digest.
- Keep `generated_at` as required schema object metadata.
- Keep `description`, `tags`, and `version` in digest for this slice; future metadata-policy work can revisit them.
- Keep `pattern` and `enum_values` in digest because runtime value validation consumes them.
- Schema object helpers must be updated together with `schema_digest`; a one-line `schema_digest` change would break current filename/content digest assumptions.

### Step 4.2 Review Tightening

- **P1 legacy volatile-digest boundary**: pre-fix workspaces have old full-object digests embedded in manifest, ledger meta, tx objects, assertion digests, and schema object filenames. A load-time fallback alone cannot safely convert those identities. This slice fixes new save/load and attach flows; old workspace migration is deferred.
- **P2 schema object validation precision**: database schema object helpers must validate parsed schema identity digest, not hash full object bytes. The saved object may keep `generated_at`; the identity digest must ignore it.
- **P3 deterministic tests**: prefer explicit `generated_at` values or timestamp-source mocking over wall-clock sleep. Wall-clock tests are slow and can be flaky.
