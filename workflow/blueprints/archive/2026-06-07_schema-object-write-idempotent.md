# Task Blueprint: Schema Object Write Idempotency (generated_at)

- Status: implemented
- Created: 2026-06-07
- Last Updated: 2026-06-07 (Step 4.8 closure)
- Related Modules:
  - `src/factgraph/core/store/database.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/core/store/docs/README.md`
- Related Docs:
  - [workflow/blueprints/archive/2026-06-06_schema-digest-stability.md](../archive/2026-06-06_schema-digest-stability.md) (parent slice; regression source)
  - [docs/quickstart/load_and_save.md](../../../docs/quickstart/load_and_save.md)
- Audit Log:
  - [2026-06-07_schema-object-write-idempotent.audit.md](./2026-06-07_schema-object-write-idempotent.audit.md)

## 1. Problem

The just-shipped slice `52425c3f fix(schema): stabilize digest across generated timestamps` introduced a regression in the schema object **write** path.

That slice made `schema_digest(...)` a **schema identity digest** (excludes top-level `generated_at`), so the schema object **filename** is now stable across recompiles. But the schema object **content** is still the full canonical bytes (`canonicalize_schema_ir_jcs(...)`, which includes `generated_at`). Filename and content are now decoupled, while the write still goes through the byte-level write-once primitive `_write_once_bytes`, whose invariant is "filename derives from a hash of the content, so same filename ⟹ same bytes."

Observed failure (reported from `meander` consuming `factgraph`):

```
DatabaseError: object already exists with different bytes:
  data/factgraph/dev-workspace/db/objects/schema/f1a88c25….json
  <- _write_once_bytes (database.py:890)
  <- _write_schema_object (database.py:648)
  <- write_schema_object_for_workspace (database.py:583)
  <- SDKStore.save_workspace (store.py:2334)  [meander on_shutdown]
```

Mechanism:

1. First run writes the schema object at the **identity-digest** path with `generated_at = T1` full bytes.
2. A later run calls `FactGraph.load_workspace(schema_classes=[...])`, which **recompiles** the classes → fresh `generated_at = T2`. Load now tolerates this (the parent slice's identity-based validation), so `fg.schema_ir["generated_at"] = T2`.
3. On shutdown, `save_workspace()` → `write_schema_object_for_workspace(path, self.schema_ir)` writes **T2** full bytes under the **same identity filename**. `_write_once_bytes` sees same path / different bytes → raises.

Net effect: **every second `save_workspace()` on an existing (post-fix) workspace fails.** The app works on first run, then crashes on shutdown of every subsequent run.

Why the parent slice tests missed it: the regression test `test_load_workspace_accepts_same_schema_with_new_generated_at` saves **once**, then loads. Load was upgraded to identity-aware validation, so it passes. The test never calls `save_workspace()` a **second** time after a recompile, so the write-once collision path is never exercised. (Notably, that test already establishes the exact precondition — `loaded.schema_ir["generated_at"]` differs from the on-disk object — so adding a trailing `loaded.save_workspace()` reproduces the crash.)

## 2. Goals

- Make the schema object **write** idempotent at the **schema-identity** level: a repeated `save_workspace()` on an existing workspace whose in-memory `schema_ir` only differs by `generated_at` must succeed.
- Preserve the parent slice's stored-object invariant: the schema object file keeps **full canonical bytes including the first writer's `generated_at`**; idempotent saves do not rewrite it.
- Cover both write paths (workspace save **and** `Database.create`) with a single change point.
- Keep genuine corruption detection: a stored object whose identity digest does not match its filename must still raise.
- Add regression coverage for the save → recompile (new `generated_at`) → save path.

## 3. Non-goals

- **Do not** drop `generated_at` from the stored schema object bytes (the "store identity bytes" option). Rejected for this bugfix because:
  - `generated_at` is a `REQUIRED_TOP_LEVEL_KEYS` field (`schema_ir.py:27`); the write/validate path parses stored bytes back through `ensure_schema_ir` (`_schema_ir_from_canonical_bytes`), so identity-only bytes would fail read-back unless the schema IR contract is also relaxed — scope creep.
  - It contradicts the parent slice's stated invariant (§5.3: object stores full bytes incl. `generated_at`).
  - It does **not** fix existing post-fix workspaces on its own: the on-disk object already holds full bytes, so writing shorter identity bytes under the same filename with `_write_once_bytes` unchanged still raises. It would have to be combined with skip/overwrite anyway.
  - The deeper design question ("should a content-addressed object embed address-excluded metadata at all?") is legitimate but is a format redesign with its own migration story → capture as a separate design-point, not this fix.
- **Do not** change `schema_digest(...)` identity semantics shipped in `52425c3f`.
- **Do not** modify `_write_once_bytes`. Tx objects and view objects are addressed by full-byte hash (true content addressing) and must keep byte-level write-once.
- **Do not** change `generated_at` validation or `REQUIRED_TOP_LEVEL_KEYS`.
- **Do not** migrate pre-fix volatile-digest workspaces (parent §5.4 boundary still applies).
- No sacred Q-PR1 path changes; `master` / `v0.1-oss-prep` untouched.

## 4. Current Context

- `write_schema_object_for_workspace(path, schema_ir)` — `database.py:578`: computes `schema_bytes = canonicalize_schema_ir_jcs(schema_ir)` (full, volatile `generated_at`, `:581`) and `schema_token = compute_schema_digest(schema_ir)` (identity, stable, `:582`), then calls `_write_schema_object`.
- `_write_schema_object(paths, *, schema_digest, schema_bytes)` — `database.py:635`: validates incoming bytes round-trip + digest match (`:642`–`:647`), then `_write_once_bytes(schema_path, schema_bytes)` (`:648`). **This tail is the bug.**
- `_write_once_bytes(path, data)` — `database.py:887`: byte-level write-once; raises "object already exists with different bytes" at `:890`. Used by schema, tx, and view objects.
- `Database.create` write path — `database.py:293`/`:309`: same `canonicalize_schema_ir_jcs` full bytes + `_write_schema_object`. One-shot, so it does not currently fire, but it shares the flaw.
- Other workspace-save callers: `store.py:1681`, `store.py:3111`, `cli.py:270` — all route through `write_schema_object_for_workspace`.
- `_validate_schema_object(...)` — `database.py:674`: the **read** path was already upgraded to identity-aware comparison (parses stored object, compares `compute_schema_digest`). The write path was left byte-level — this fix restores symmetry.
- `_schema_ir_from_canonical_bytes(...)` — `database.py:~706`: parse UTF-8 JSON → `ensure_schema_ir(...)`; raises `DatabaseError` on bad bytes. Reusable in the write existence branch.
- `_atomic_write_bytes(...)` — `database.py:895`: atomic write primitive used by `_write_once_bytes`.
- Reproduction signal: the colliding object lives at the **identity-digest** path, which proves both writes came from post-fix code (pre-fix code would compute a different filename). So this is purely the post-fix write regression, not a parent §5.4 legacy-boundary case.

## 5. Proposed Shape

### 5.1 Identity-idempotent schema object write

In `_write_schema_object`, keep the existing incoming-bytes validation (`database.py:642`–`:647`) and replace **only** the final `_write_once_bytes(schema_path, schema_bytes)` (`:648`) with an identity-aware existence branch:

```python
# database.py: _write_schema_object tail (replaces line 648 only)
if schema_path.exists():
    stored_schema_ir = _schema_ir_from_canonical_bytes(schema_path.read_bytes())
    if compute_schema_digest(stored_schema_ir) != schema_digest:
        raise DatabaseError("schema object filename/content digest mismatch")
    return  # identity already persisted; keep first writer's full bytes (incl. generated_at)
_atomic_write_bytes(schema_path, schema_bytes)
```

Rationale: the schema object is content-addressed **by identity** (filename = identity digest). Existence at that path means the schema identity is already persisted; a second write with a different `generated_at` is a no-op, not a conflict. The retained `:642`–`:647` validation still rejects malformed incoming bytes and digest/filename mismatches for fresh writes; the existence branch re-checks stored identity so corruption is still caught.

### 5.2 Single change point covers all callers

Because the change is inside `_write_schema_object`, it covers both `write_schema_object_for_workspace` (workspace save: `store.py:2334`/`:1681`/`:3111`, `cli.py:270`) **and** the `Database.create` path (`database.py:309`). No caller-site edits.

### 5.3 Leave byte-level write-once for tx/view objects

`_write_once_bytes` is unchanged and continues to guard tx objects and view objects, which are addressed by full-byte hash. Only schema objects have the identity/content split, so only the schema object write changes.

### 5.4 Tests

- **SDK / meander reproduction**: a test that seeds a workspace, `save_workspace()`, then `load_workspace(schema_classes=[...])` under a patched compiler timestamp (so the loaded `schema_ir["generated_at"]` differs), then `loaded.save_workspace()` again — asserts no raise, the on-disk schema object bytes are **unchanged** (first `generated_at` retained), the manifest `schema_digest` is stable, and data still loads. (Lives alongside `test_load_workspace_accepts_same_schema_with_new_generated_at` in `tests/test_factgraph_workspace_lifecycle.py`.)
- **Core helper idempotency**: `write_schema_object_for_workspace(path, ir_T1)` then `write_schema_object_for_workspace(path, ir_T2)` where the two IRs differ only by `generated_at` — second returns the same token, does not raise, and the file bytes equal the first write. (`tests/test_db_identity_substrate.py`.)
- **Corruption guard**: overwrite the stored object so its identity digest no longer matches the filename, then write again → raises `"... digest mismatch"`.
- All parent-slice tests stay green.

### 5.5 Docs

- `src/factgraph/core/store/docs/README.md:39` documents that the schema object stores exact `canonicalize_schema_ir_jcs(...)`. Add that the write is **identity-idempotent**: a repeated write at the same identity digest is a no-op and retains the first writer's `generated_at`.
- `docs/quickstart/load_and_save.md`: optional one-line note that repeated `save_workspace()` is safe across recompiles. Decide at Step 4.7 to keep scope tight (and `load_and_save.md` is already dirty — partial-stage like the parent slice).

## 6. Boundaries And Invariants

- `master` and `v0.1-oss-prep` untouched. Q-PR1 sacred paths 0-diff.
- `schema_digest` identity semantics unchanged from `52425c3f`.
- Schema object file still stores full canonical bytes including the **first writer's** `generated_at`; idempotent saves never rewrite it.
- `_write_once_bytes` unchanged; tx/view byte-level write-once preserved.
- Genuine structural mismatch / object corruption still raises.
- `generated_at` remains a required schema IR field.
- Pre-fix volatile-digest workspaces / ledgers remain out of scope.
- Existing unrelated dirty files remain unstaged.

## 7. Acceptance

- [x] Repeated `save_workspace()` on an existing post-fix workspace with a recompiled `schema_ir` (new `generated_at`) succeeds.
- [x] On-disk schema object bytes are not rewritten on an idempotent save (first `generated_at` retained).
- [x] `Database.create` write path is also idempotent (single change point).
- [x] Stored-object corruption (identity digest != filename) still raises.
- [x] Tx / view object write-once behavior unchanged.
- [x] `schema_digest` values unchanged from `52425c3f`.
- [x] Regression test reproduces the meander save → recompile → save path and passes.
- [x] Parent-slice tests remain green.
- [x] `src/factgraph/core/store/docs/README.md` reflects the idempotent write.
- [x] No sacred Q-PR1 path changes; `master` pointer unchanged.

## 8. Implementation Plan

1. `database.py` `_write_schema_object`: replace the trailing `_write_once_bytes(...)` (`:648`) with the identity-idempotent existence branch from §5.1; keep `:642`–`:647` validation ahead of it.
2. Add the core helper idempotency test to `tests/test_db_identity_substrate.py`.
3. Add the SDK load→save regression test to `tests/test_factgraph_workspace_lifecycle.py`.
4. Add the corruption-guard assertion.
5. Update `src/factgraph/core/store/docs/README.md` (and optionally `docs/quickstart/load_and_save.md` at 4.7).
6. Run focused tests; if local `pytest` segfaults (parent-slice deviation), fall back to `unittest` for the same modules:
   - `PYTHONPATH=src python -m unittest tests.test_db_identity_substrate tests.test_factgraph_workspace_lifecycle tests.test_db_attach_lifecycle tests.test_schema_mutation_lifecycle`
7. Sacred Q-PR1 0-diff + `master` pointer preservation checks.

## 9. Docs To Update

- `src/factgraph/core/store/docs/README.md`
- (optional, decide at 4.7) `docs/quickstart/load_and_save.md`

No new durable docs entry expected, so `docs/README.md` should not need an update.

## 10. Outcome / Deviations

Implemented in Step 4.7 on the parent schema-digest-stability implementation
branch.

- `_write_schema_object(...)` now validates incoming full canonical bytes first,
  then treats an existing schema object path as an identity-idempotent no-op when
  the stored object's recomputed schema identity digest matches the filename.
- The first writer's full canonical schema bytes are retained, including
  `generated_at`; subsequent recompiles with a new `generated_at` no longer
  rewrite the object or trip `_write_once_bytes`.
- `_write_once_bytes(...)` remains unchanged for transaction and view objects.
- Regression coverage now includes both the core helper write-T1/write-T2 path
  and the SDK save → load/recompile → save path that matched the `meander`
  shutdown failure.
- `src/factgraph/core/store/docs/README.md` documents identity-idempotent schema
  object writes.

Verification:

- `PYTHONPATH=src python -m py_compile src/factgraph/core/store/database.py`
- `PYTHONPATH=src python -m unittest tests.test_db_identity_substrate tests.test_factgraph_workspace_lifecycle tests.test_db_attach_lifecycle tests.test_schema_mutation_lifecycle`
  → 99 tests OK / 6 skipped.
- Direct smoke confirmed a recompiled loaded workspace saves successfully while
  retaining the first schema-object bytes.

Deviations:

- `docs/quickstart/load_and_save.md` was left untouched because it already has
  unrelated dirty changes in the working tree; the core-store durable-layout doc
  carries the persistence invariant for this bugfix.
