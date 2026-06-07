# Task Blueprint Audit: Schema Object Write Idempotency (generated_at)

- Blueprint: [2026-06-07_schema-object-write-idempotent.md](./2026-06-07_schema-object-write-idempotent.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-07 | draft | Blueprint created | Regression in parent slice `52425c3f` reproduced from `meander` shutdown save. Stage 1 root cause confirmed against shipped code; Step 4.1 draft scoped to identity-idempotent schema object write + missing save→recompile→save regression test. |
| 2026-06-07 | implemented | Step 4.2 review + Step 4.7 implementation | Codex re-confirmed root cause and fix altitude: `_write_schema_object` is the correct single change point; validation must remain before the existence branch; `_write_once_bytes` remains unchanged for tx/view objects. Implemented identity-idempotent schema-object writes, focused regression tests, and core-store docs. |
| 2026-06-07 | implemented | Step 4.8 closure | Verification passed: py_compile clean; focused unittest cohort 99 OK / 6 skipped; direct save → load/recompile → save smoke retained first schema-object bytes and no longer raised. |

## Decision Notes

### Step 4.1 Draft Decisions

- **Root cause (confirmed against shipped code)**: `52425c3f` decoupled the schema object filename (identity digest, stable) from its content (full canonical bytes incl. `generated_at`, volatile) but left `_write_schema_object` writing through byte-level `_write_once_bytes`. Second save with a fresh `generated_at` collides under the same identity filename.
- **Fix choice = identity-idempotent write (the "skip when digest exists" option), not "drop generated_at"**:
  - The "drop `generated_at` from object bytes" option was rejected as a non-goal. Three reasons: (1) `generated_at` is a `REQUIRED_TOP_LEVEL_KEYS` field and the object is parsed back through `ensure_schema_ir`, so identity-only bytes break read-back unless the schema IR contract is also relaxed; (2) it contradicts parent §5.3 (object stores full bytes incl. `generated_at`); (3) it does not fix existing post-fix workspaces on its own (old full-bytes object + unchanged `_write_once_bytes` still collides), so it would need skip/overwrite anyway.
  - The cleaner "should the schema object carry `generated_at` at all" question is a content-addressing design concern → deferred to a separate design-point, out of this bugfix.
- **Change placement**: inside `_write_schema_object` (not only the workspace helper) so both `write_schema_object_for_workspace` and the `Database.create` path become idempotent from a single edit.
- **Preserve `_write_once_bytes`**: tx objects and view objects are addressed by full-byte hash (true content addressing) and must keep byte-level write-once. Only schema objects have the identity/content split.
- **Corruption still caught**: the existence branch re-parses the stored object and re-checks `compute_schema_digest(stored) == filename`, mirroring the already-identity-aware read path `_validate_schema_object`.
- **Zero migration**: the fix accepts the existing post-fix `dev-workspace` schema object as-is and unblocks the live failure immediately; parent §5.4 legacy boundary (pre-fix volatile-digest workspaces) is untouched.
- **Test gap to close**: parent slice only saved once then loaded; the missing case is save → recompile (new `generated_at`) → save, which is exactly the `meander` shutdown path.

### Alternatives Considered (2026-06-07 review)

- **Team alternative — reconstruct schema classes from the stored IR instead of requiring `schema_classes` on load** (class-less / from-IR load): considered and **deferred**. It attacks the drift at the load layer (no recompile → no fresh `generated_at`), but (1) reverses an explicit, documented decision — `load_workspace` states "Class-less dynamic load is not supported" and hard-requires `schema_classes` (`store.py:1729`/`:1744`); (2) is a substantial feature, not a bugfix — the SDK object model binds to the caller's real Python classes (`entities.get(User, ...)`, `sdk_owner_cls`, `store.py:738`), which a runtime-synthesized class cannot satisfy; (3) only covers load, not `attach` (`store.py:1784`) or other recompile sites, so the write-once landmine persists. The write-idempotency fix closes the collision at the persistence boundary for all paths and is correct regardless of whether load later stops requiring classes.
- **Strategic direction (separate design-point, not this slice)**: the principled long-term fix is to stop embedding address-excluded volatile metadata (`generated_at`) inside the content-addressed schema object — keep the addressed object equal to its canonical identity bytes and move `generated_at` to a manifest/sidecar, so "same filename / different bytes" becomes structurally impossible. To be captured as `workflow/design/design-points/active/schema-identity-and-loading.zh.md`. This slice stays the tactical stop-the-bleed; the design-point is the strategic follow-up. The two do not block each other.

## Open Items (pre-scope-freeze)

- **Branch decision**: current branch is `v0.2.0-impl-schema-digest-stability-2026-06-06` (the parent slice's impl branch, unpushed). Confirm whether to continue this bugfix on the same branch or seed a paired follow-up design/impl branch before Step 4.7 implementation. Default proposal: continue on the current branch since it is the same slice lineage and nothing is pushed.
- **Codex handoff**: blueprint is drafted for Codex to take through the implementation cadence (Step 4.x). Codex review of §5.1 ordering (validation-before-existence-branch) and the test matrix is the next step.

## Step 4.2 Review / Step 4.7 Implementation Notes

- **Root cause re-confirmed**: the failing second save is not a caller misuse. The caller writes a full canonical schema object whose identity digest equals the existing object filename, but whose `generated_at` differs. The previous `_write_once_bytes(...)` tail treated that as a byte-level content-address collision.
- **Fix altitude accepted**: `_write_schema_object(...)` is the right boundary because it covers both `write_schema_object_for_workspace(...)` and `Database.create(...)`; gating only in the SDK workspace helper would leave a second schema-object write path with the same invariant mismatch.
- **Ordering accepted**: incoming bytes are still parsed and canonicalized before the existence branch. This preserves malformed-input and digest/filename mismatch checks for both fresh writes and no-op writes.
- **Caller dependency check**: no legitimate caller depends on schema-object writes raising solely because `generated_at` changed. The remaining raise path is corruption detection: if the stored object's recomputed identity digest does not match the filename, the write raises `DatabaseError("schema object filename/content digest mismatch")`.
- **Test matrix implemented**:
  - Core helper write idempotency for `generated_at`-only schema IR differences.
  - Stored-object corruption guard on an existing schema path.
  - SDK workspace save → load/recompile → save regression mirroring the `meander` shutdown path.
- **Docs**: `src/factgraph/core/store/docs/README.md` now states repeated writes at the same schema identity keep the first writer's full canonical bytes. `docs/quickstart/load_and_save.md` stayed untouched because it already has unrelated dirty changes.
