# Task Blueprint: Schema Digest Stability

- Status: scoped
- Created: 2026-06-06
- Last Updated: 2026-06-06 (Step 4.6 scope freeze)
- Related Modules:
  - `src/factgraph/core/schema/schema_ir.py`
  - `src/factgraph/core/store/database.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/application/workspace_runtime.py`
- Related Docs:
  - [workflow/audit/active/2026-06-06_schema-digest-stability-vs-shipped.md](../../audit/active/2026-06-06_schema-digest-stability-vs-shipped.md)
  - [docs/quickstart/schema_definition.md](../../../docs/quickstart/schema_definition.md)
  - [docs/quickstart/load_and_save.md](../../../docs/quickstart/load_and_save.md)
- Audit Log:
  - [2026-06-06_schema-digest-stability.audit.md](./2026-06-06_schema-digest-stability.audit.md)

## 1. Problem

`schema_digest(schema_ir)` currently hashes the full schema IR object, including top-level `generated_at`. Because `compile_schema_from_classes(...)` emits a fresh timestamp by default, recompiling identical schema classes can produce a different digest after the timestamp changes.

This breaks schema equality checks during workspace reload and Database attach:

- `FactGraph.load_workspace(...)` recompiles `schema_classes` and compares the digest to the saved workspace manifest.
- `FactGraph.attach(db, schema_classes=...)` recompiles `schema_classes` and compares the digest to `db.schema_digest`.

Schema identity should represent the structure that interprets data, not the time the schema object was generated.

## 2. Goals

- Make `schema_digest(...)` stable across recompiles of identical schema structure even when `generated_at` differs.
- Keep `generated_at` in schema IR objects as metadata.
- Preserve structural mismatch detection for true schema changes.
- Preserve workspace schema object validation, but update it to validate schema identity rather than full object byte hash.
- Add regression tests for workspace reload and Database attach with differing generated timestamps.
- Update public docs to explain schema identity vs schema object metadata.

## 3. Non-goals

- Do not remove `generated_at` from schema IR.
- Do not change value validation semantics for `pattern` or `enum_values`.
- Do not decide whether `description`, `tags`, or entity `version` should be metadata-only in a future schema identity policy.
- Do not change `FactGraph.load_workspace(..., schema_classes=...)` requirement.
- Do not alter schema mutation additivity rules except where digest stability is directly required.
- Do not touch sacred Q-PR1 paths.

## 4. Current Context

- `src/factgraph/core/schema/schema_ir.py` validates `generated_at` as a required top-level field and hashes the whole schema IR object.
- `src/factgraph/authoring/schema_compile.py` generates `generated_at` using current UTC time when no override is provided.
- `src/factgraph/core/store/database.py` stores schema objects under a schema digest filename and currently requires full object bytes to hash to that digest.
- `src/factgraph/sdk/store.py` stores `_schema_digest` and uses recomputed digests for load / attach / ledger meta checks.
- Manual reproduction confirms identical schema classes can produce different digests across seconds and cause load / attach failures.

## 5. Proposed Shape

### 5.1 Split object canonicalization from identity canonicalization

Keep existing full object canonicalization:

```python
canonicalize_schema_ir_jcs(schema_ir) -> bytes
```

Add a schema identity canonicalizer:

```python
SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS = frozenset({"generated_at"})

def canonicalize_schema_ir_identity_jcs(schema_ir: dict) -> bytes:
    validated = ensure_schema_ir(schema_ir)
    identity = {
        key: value
        for key, value in validated.items()
        if key not in SCHEMA_IDENTITY_EXCLUDED_TOP_LEVEL_KEYS
    }
    _reject_floats(identity, "$")
    return json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

Then:

```python
def schema_digest(schema_ir: dict) -> str:
    return sha256_token(canonicalize_schema_ir_identity_jcs(schema_ir))
```

### 5.2 Identity field policy for this slice

Excluded:

- Top-level `generated_at` only.

Kept in identity for this slice:

- `schema_ir_version`
- `entities`
- `predicates`
- `projection`
- `protocol_version`
- `pattern`
- `enum_values`
- `description`
- `tags`
- `version`

Rationale: `generated_at` is unquestionably volatile metadata. `description`, `tags`, and `version` may also be metadata-like, but changing them in this slice would broaden policy scope beyond the reported bug.

### 5.3 Schema object validation update

After `schema_digest` no longer equals `sha256(full_schema_object_bytes)`, database schema object helpers must stop enforcing byte-hash equality.

Required behavior:

- Schema object files still store full canonical schema IR bytes including `generated_at`.
- Schema object filenames still use `schema_digest`, but that digest now means schema identity digest.
- `_write_schema_object(...)` must parse / validate the provided schema bytes and confirm `schema_digest(parsed_schema_ir) == schema_digest_arg`.
- `_validate_schema_object(...)` must read object bytes, parse / validate, confirm identity digest matches filename / expected digest, and confirm structural identity matches the caller's expected schema IR.
- Validation must tolerate different `generated_at` values between saved schema object and freshly compiled schema IR.
- Validation must still reject true structural mismatch.

Implementation lock from Step 4.3 PF-R1 / PF-R2:

- Add a parsed-object helper equivalent to `_schema_ir_from_canonical_bytes(schema_bytes)`:
  - parse UTF-8 JSON bytes
  - require root JSON object
  - call `ensure_schema_ir(...)`
  - raise `DatabaseError` with schema-object context on parse / validation failure
- `_write_schema_object(...)` must validate the passed canonical bytes by parsing them and confirming `schema_digest(parsed_schema_ir) == schema_digest_arg`.
- `_validate_schema_object(...)` should take `expected_schema_ir`, not `expected_bytes`.
- `_validate_schema_object(...)` must:
  - read and parse the stored object
  - confirm `schema_digest(stored_schema_ir) == schema_digest_arg`
  - confirm `schema_digest(expected_schema_ir) == schema_digest_arg`
  - compare identity canonical bytes for stored vs expected schema IR
  - not compare full canonical object bytes, because `generated_at` may differ
- Full schema object bytes remain canonical full IR bytes, including `generated_at`.

### 5.4 Legacy volatile-digest workspace / ledger boundary

This slice fixes schema identity for workspaces / databases created or saved after the new digest policy lands.

It does **not** silently migrate pre-fix workspaces or ledger-only databases whose manifest, ledger meta, tx objects, assertion digests, and schema object filenames were already anchored to the old full-object digest that included `generated_at`.

Reason:

- `schema_digest` is embedded in workspace manifest and ledger meta.
- Database tx identity recomputes from tx object `schema_digest`.
- Assertion digests include `schema_digest`.
- Head tx validation checks tx object `schema_digest` against expected digest.

Therefore an old volatile-digest workspace cannot be made compatible by a load-time fallback alone. Rewriting it would be a migration slice, not this bugfix.

Required user-facing behavior for this slice:

- New save/load and attach flows are stable.
- Existing old volatile-digest workspaces and old ledger-only files may continue to require the old digest anchor or a future migration tool.
- Docs must not imply this slice retroactively rewrites old workspace identity.

### 5.5 Test strategy

Prefer deterministic timestamp mocking over real `sleep`:

- Direct digest tests should pass two schema IRs with explicit `generated_at` values.
- Workspace / attach tests should patch the compiler timestamp source so create/save and load/attach see distinct `generated_at` values without depending on wall-clock seconds.

Add regression tests for:

- `schema_digest` equality when only `generated_at` differs.
- `schema_digest` inequality when a structural field changes.
- `description` or entity `version` still changes digest in this slice, guarding the current narrow identity policy.
- `FactGraph.save_workspace()` then `FactGraph.load_workspace(..., schema_classes=...)` succeeds when compiler timestamps differ.
- `Database.create(schema_ir=...)` then `FactGraph.attach(db, schema_classes=...)` succeeds when compiler timestamps differ.
- `schema_object_exists_for_workspace(...)` uses the stable identity digest path.
- schema object bytes still include the full schema object metadata, including `generated_at`.
- Schema object validation still rejects structural mismatch.

### 5.6 Docs

Docs must distinguish:

- schema object: full stored IR including metadata like `generated_at`
- schema identity digest: stable digest of structure-bearing schema fields, excluding volatile metadata
- legacy boundary: pre-fix volatile-digest workspace migration is out of this slice.

## 6. Boundaries And Invariants

- `master` and `v0.1-oss-prep` remain untouched.
- Q-PR1 sacred paths remain 0-diff vs `4c472b50`.
- Existing unrelated dirty files remain unstaged.
- `generated_at` remains present and validated in schema IR.
- `pattern` and `enum_values` remain schema-identity fields because runtime value validation consumes them.
- True structural schema mismatches still fail load / attach.
- Existing workspace manifests continue using `schema_digest` as the schema identity token.
- Existing pre-fix workspaces / ledgers already anchored to a volatile full-object digest are not silently rewritten in this slice.

## 7. Acceptance

- [ ] `schema_digest` ignores only `generated_at` among current schema IR fields.
- [ ] Two schema IRs differing only by `generated_at` produce equal `schema_digest`.
- [ ] Structural schema changes still produce unequal `schema_digest`.
- [ ] Workspace reload after a timestamp boundary succeeds for identical schema classes.
- [ ] `FactGraph.attach(db, schema_classes=...)` after a timestamp boundary succeeds for identical schema classes.
- [ ] Schema object write / validate works with full schema object bytes while using identity digest filenames.
- [ ] Schema object validation still rejects structural mismatch.
- [ ] Schema object tests confirm object path uses stable identity digest while stored bytes still include `generated_at`.
- [ ] Tests confirm `description` or `version` still changes digest in this slice.
- [ ] Tests use explicit timestamp overrides or timestamp-source mocks rather than wall-clock sleeps where possible.
- [ ] Legacy volatile-digest workspace / ledger migration is documented as out of scope.
- [ ] Docs explain schema object metadata vs schema identity digest.
- [ ] Tests pass for schema, workspace, database attach, and affected SDK lifecycle surfaces.
- [ ] No sacred Q-PR1 path changes.

## 8. Implementation Plan

1. Add `canonicalize_schema_ir_identity_jcs(...)` and update `schema_digest(...)` in `src/factgraph/core/schema/schema_ir.py`.
2. Update schema object helper internals in `src/factgraph/core/store/database.py` to validate identity digest from parsed schema IR instead of hashing full bytes.
3. Update SDK / workspace tests for differing generated timestamps during load and attach behavior.
4. Add direct schema digest unit coverage for `generated_at` exclusion and structural mismatch.
5. Update `docs/quickstart/schema_definition.md`.
6. Update `docs/quickstart/load_and_save.md`.
7. Run focused tests:
   - `PYTHONPATH=src python -m pytest tests/test_factgraph_workspace_lifecycle.py tests/test_db_identity_substrate.py tests/test_schema_mutation_lifecycle.py`
   - plus any directly added schema digest tests.
8. Run sacred checks and dirty-baseline preservation checks.

## 9. Docs To Update

- `docs/quickstart/schema_definition.md`
- `docs/quickstart/load_and_save.md`

No new durable docs entry is expected, so `docs/README.md` should not need an update.

## 10. Outcome / Deviations

To be filled in Step 4.8 closure.
