# Task Blueprint Audit: Schema Digest Stability

- Blueprint: [2026-06-06_schema-digest-stability.md](./2026-06-06_schema-digest-stability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-06 | draft | Blueprint created | User-reported `generated_at` / schema digest instability reproduced; Stage 1 audit and Step 4.1 blueprint draft created. |
| 2026-06-06 | draft | Step 4.2 review + tightening | Added P1 legacy volatile-digest workspace boundary, P2 schema object identity-validation precision, and P3 deterministic timestamp test strategy. |
| 2026-06-06 | draft | Step 4.4 preflight amendment | Folded PF-R1/PF-R2 parsed schema object validation, PF-R3 legacy ledger boundary, and PF-r1/PF-r2 test locks. |
| 2026-06-06 | scoped | Step 4.6 scope freeze | Step 4.5 self-check passed; PF-R1/PF-R2/PF-R3 + PF-r1/PF-r2 covered by `b785313e`. |

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

### Step 4.4 Preflight Amendment

- **PF-R1 / PF-R2**: schema object helpers must parse canonical object bytes, validate schema IR, and compare identity canonical bytes. Public validation must pass `expected_schema_ir`, not full expected bytes.
- **PF-R3**: legacy boundary includes old ledger-only files and Database legacy open paths, not only workspace schema objects.
- **PF-r1**: tests must verify schema object path uses stable identity digest and stored bytes still include full metadata such as `generated_at`.
- **PF-r2**: tests must guard narrow policy by proving `description` or `version` still changes digest in this slice.
