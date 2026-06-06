# Task Blueprint Audit: Schema Digest Stability

- Blueprint: [2026-06-06_schema-digest-stability.md](./2026-06-06_schema-digest-stability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-06 | draft | Blueprint created | User-reported `generated_at` / schema digest instability reproduced; Stage 1 audit and Step 4.1 blueprint draft created. |
| 2026-06-06 | draft | Step 4.2 review + tightening | Added P1 legacy volatile-digest workspace boundary, P2 schema object identity-validation precision, and P3 deterministic timestamp test strategy. |
| 2026-06-06 | draft | Step 4.4 preflight amendment | Folded PF-R1/PF-R2 parsed schema object validation, PF-R3 legacy ledger boundary, and PF-r1/PF-r2 test locks. |
| 2026-06-06 | scoped | Step 4.6 scope freeze | Step 4.5 self-check passed; PF-R1/PF-R2/PF-R3 + PF-r1/PF-r2 covered by `b785313e`. |
| 2026-06-06 | scoped | Step 4.6.5 pre-impl grep amendment | Re-ran full-object digest / schema object validation / docs wording grep. No new production scope beyond PF-R1/PF-R2/PF-R3; N-1 bridge docs cascade folded. Status remains scoped; no implementation started. |
| 2026-06-06 | scoped | Step 4.7 implementation | Implemented stable schema identity digest excluding only top-level `generated_at`; updated schema object validation, regression tests, and scoped docs. Status remains scoped until Step 4.8 closure. |
| 2026-06-06 | implemented | Step 4.8 closure | Status changed scoped → implemented; §10 Outcome / Verification / Deviations filled. |
| 2026-06-06 | implemented | Step 4.9 archive | Moved blueprint pair and audit artifacts from active to archive; updated archive inventory. |

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

### Step 4.6.5 Pre-Impl Grep Amendment

- **Code grep result**: old schema object full-byte assumptions are confined to the already-scoped `database.py` helper rewrite (`expected_bytes`, `sha256_token(schema_bytes)`, `sha256_token(actual)`, and full byte compare). No additional production consumer requires scope expansion.
- **N-1 docs cascade**: `docs/references/bridges/symir-blueprint-extraction.md` contains current-behavior rows that say `schema_digest` hashes the whole schema IR including `generated_at`. Step 4.7 must update those rows to the new policy while preserving the slice boundary that `description` / `tags` remain included.
- **Dirty docs caution**: `docs/quickstart/load_and_save.md` is already dirty from unrelated edits. Step 4.7 must avoid staging unrelated hunks when adding the schema-digest documentation update.

### Step 4.7 Implementation Notes

- `schema_digest(...)` now hashes `canonicalize_schema_ir_identity_jcs(...)`, which excludes only top-level `generated_at`.
- Schema object files still store full canonical schema IR bytes, but write / validate parse the object and compare schema identity rather than full-object byte hashes.
- `FactGraph.load_workspace(...)` and `FactGraph.attach(...)` now tolerate recompiled identical schema classes with a different generated timestamp.
- Pytest currently segfaults in local pytest capture initialization before test collection; focused verification used `unittest` for the same test modules.

### Step 4.8 Closure

- Closure commit records implementation `52425c3f`, focused `unittest` verification, py_compile, direct save/load and attach reproductions, Q-PR1 0-diff, and sacred master preservation.
- Dirty-doc handling is explicitly recorded: only schema-digest hunks from `docs/quickstart/load_and_save.md` were staged; unrelated pre-existing hunks remain unstaged.

### Step 4.9 Archive

- Archived blueprint pair under `workflow/blueprints/archive/`.
- Archived Stage 1 audit and Step 4.3 preflight artifact under `workflow/audit/archive/`.
- Updated `workflow/blueprints/archive/INVENTORY.md` with schema-digest-stability summary.
