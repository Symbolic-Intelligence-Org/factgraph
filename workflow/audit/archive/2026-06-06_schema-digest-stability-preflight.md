# Preflight: Schema Digest Stability

- Status: complete
- Created: 2026-06-06
- Last Updated: 2026-06-06
- Branch: `v0.2.0-schema-digest-stability-preflight-2026-06-06`
- Blueprint source: `v0.2.0-blueprint-schema-digest-stability-2026-06-06 @ 5e1fdd08`
- Output: Step 4.4 amendments required on blueprint branch.

## 1. Scope

This preflight verifies the scoped fix shape for schema digest stability before implementation.

Primary files re-read / spot-checked:

| Area | File | Relevant anchors |
|---|---|---|
| Schema IR digest | `src/factgraph/core/schema/schema_ir.py` | `:21-28`, `:62-78`, `:92-95` |
| Schema object helpers | `src/factgraph/core/store/database.py` | `:576-590`, `:634-684` |
| Workspace manifest | `src/factgraph/application/workspace_runtime.py` | `:83-109`, `:133-150` |
| SDK load / attach | `src/factgraph/sdk/store.py` | `:1518-1525`, `:1744-1751`, `:1784-1790`, `:1818-1834` |
| Database identity embedding | `src/factgraph/core/store/database.py` | `:521-525`, `:753-760`, `:812-821`, `:834-839` |

## 2. Method

Fresh-source checks were performed against the current shipped code at preflight time:

- `schema_digest(...)` still hashes full schema IR through `canonicalize_schema_ir_jcs(...)`.
- `generated_at` is still required top-level schema IR metadata.
- Schema object write / validate still assumes `sha256(full_schema_bytes) == schema_digest`.
- Workspace load / attach still recompute digest from newly compiled schema classes.
- Database tx / assertion / head checks embed `schema_digest`, confirming old volatile-digest workspaces cannot be silently repaired by a load-time fallback.

## 3. Findings

| ID | Bucket | Finding | Source verification | Amendment |
|---|---|---|---|---|
| PF-R1 | Required | Schema object helpers need parsed-object validation helpers, not byte-hash equality. | `_write_schema_object` hashes raw bytes at `database.py:641`; `_validate_schema_object` compares raw bytes at `:679-684`. | Blueprint §5.3 should name concrete helper shape: parse bytes as JSON object, `ensure_schema_ir`, recompute `schema_digest(parsed)`, and compare expected identity canonical bytes excluding `generated_at`. |
| PF-R2 | Required | `validate_schema_object_for_workspace(path, schema_ir)` cannot pass `expected_bytes` once `generated_at` may differ. | Public helper currently computes `schema_bytes = canonicalize_schema_ir_jcs(schema_ir)` and passes bytes at `database.py:585-590`. | Blueprint should require `_validate_schema_object(..., expected_schema_ir=...)`, not `expected_bytes`. |
| PF-R3 | Required | Legacy volatile-digest boundary must include ledger-only lifecycles, not just workspace objects. | `_from_schema_classes_impl` checks ledger meta at `sdk/store.py:1825-1834`; Database legacy open checks ledger meta at `database.py:339-344`. | Blueprint §5.4 / acceptance should state old ledger files anchored to old full-object digest are also out of scope for silent migration. |
| PF-r1 | Recommended | Tests should include `schema_object_exists_for_workspace(...)` after identity digest change. | Existing helper test checks object path under digest at `tests/test_db_identity_substrate.py:187-196`. | Add test that object file exists under stable identity digest and contains full schema bytes including `generated_at`. |
| PF-r2 | Recommended | Direct digest test should guard `description/tags/version` current policy. | Blueprint keeps these fields in identity for this slice. | Add tests showing `description` or `version` still changes digest, preventing accidental broader exclusion. |
| PF-v1 | Verified | `pattern` / `enum_values` are semantic fields. | `application/value_validation.py` consumes both through `PredicateInfo`. | Keep in identity digest. |
| PF-v2 | Verified | Application workspace manifest only checks digest token equality. | `workspace_runtime.py:103-109`. | No manifest code shape change expected beyond new digest value. |
| PF-v3 | Verified | Load / attach failure reproduces from timestamp drift. | Manual reproduction recorded in Stage 1 audit. | Covered by regression tests. |
| PF-s1 | Scoped detail | Test mocking target should patch authoring compiler timestamp or pass explicit generated_at where possible. | `_utc_now_iso_z` is in `schema_compile.py`. | Implementation can choose explicit generated_at for direct digest tests and patch `_utc_now_iso_z` for lifecycle tests. |

## 4. Required Amendments

Apply these on the blueprint branch:

1. Add concrete schema object parsed-validation helper shape:
   - `_schema_ir_from_canonical_bytes(...)`
   - `_schema_identity_matches(...)` or equivalent
   - `_validate_schema_object(..., expected_schema_ir=...)`
2. Expand legacy boundary to include old ledger-only lifecycles and Database legacy ledger open.
3. Expand acceptance to cover:
   - object file under identity digest path
   - full schema object bytes still include `generated_at`
   - `description` / `version` policy is guarded by tests

## 5. Recommended Implementation Notes

- Preserve `canonicalize_schema_ir_jcs(...)` behavior as a full-object writer. It should still include `generated_at`.
- Add a new function for identity bytes rather than adding optional flags to `canonicalize_schema_ir_jcs(...)`; optional flags would make call sites ambiguous.
- Use JSON parse + `ensure_schema_ir` for schema object validation so invalid schema object bytes fail clearly.

## 6. Distribution

- Required: 3
- Recommended: 2
- Verified: 3
- Scoped detail: 1
- Abandonment: 0

Healthy distribution: 3R / 2r / 3v / 1s / 0A. No abandonment blocker.

## 7. Preflight Verdict

PASS with amendment required.

The blueprint is implementable after Step 4.4 folds PF-R1 / PF-R2 / PF-R3 and the two recommended test locks.
