# Audit: Schema Digest Stability vs Shipped Runtime

- Status: complete
- Created: 2026-06-06
- Last Updated: 2026-06-06
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow the implementing blueprint.
- Inputs:
  - User report: same schema recompiles with a new timestamp, then digest equality checks fail.
  - Shipped source read / spot-checked per Rule 1.
- Outputs / Downstream:
  - Implementing blueprint: [2026-06-06_schema-digest-stability.md](../../blueprints/active/2026-06-06_schema-digest-stability.md)
- Related:
  - `docs/quickstart/load_and_save.md`
  - `docs/quickstart/schema_definition.md`
- Source intent: schema digest should identify the schema structure that interprets data, not volatile object metadata.
- Branch: `v0.2.0-blueprint-schema-digest-stability-2026-06-06`

## 1. Scope

Primary surface:

| Layer | File | Path |
|---|---|---|
| Schema IR canonicalization | schema digest implementation | `src/factgraph/core/schema/schema_ir.py` |
| Authoring compiler | generated timestamp source | `src/factgraph/authoring/schema_compile.py` |
| Database workspace | schema object write / validate | `src/factgraph/core/store/database.py` |
| SDK workspace | load / attach digest comparison | `src/factgraph/sdk/store.py` |
| Application workspace | manifest digest comparison | `src/factgraph/application/workspace_runtime.py` |
| Docs/tests | lifecycle and schema docs | `tests/test_factgraph_workspace_lifecycle.py`, `tests/test_db_identity_substrate.py`, `docs/quickstart/load_and_save.md`, `docs/quickstart/schema_definition.md` |

Out of scope:

- Do not remove `generated_at` from schema IR objects.
- Do not change `FactGraph.load_workspace(..., schema_classes=...)` requirement.
- Do not redesign schema mutation lifecycle beyond digest stability.
- Do not decide entity-level `version` identity semantics in this slice.

## 2. Inputs

The shipped compiler emits a fresh `generated_at` when no override is supplied:

- `src/factgraph/authoring/schema_compile.py:54-68` builds schema IR and sets `"generated_at": generated_at or _utc_now_iso_z()`.

The shipped digest hashes the whole validated schema IR:

- `src/factgraph/core/schema/schema_ir.py:21-28` requires top-level `generated_at`.
- `src/factgraph/core/schema/schema_ir.py:62-78` canonicalizes the whole validated object and hashes those bytes.

The shipped workspace and attach paths compare newly compiled schema digests:

- `src/factgraph/sdk/store.py:1746-1751` recompiles `schema_classes` during `FactGraph.load_workspace(...)` and passes that digest to workspace manifest validation.
- `src/factgraph/sdk/store.py:1784-1790` recompiles `schema_classes` during `FactGraph.attach(db, ...)` and compares to `db.schema_digest`.

Minimal reproduction on 2026-06-06:

```text
compile generated_at 1: 2026-06-06T10:23:22Z
compile generated_at 2: 2026-06-06T10:23:23Z
compile digest equal: False
```

Workspace reload reproduction:

```text
saved generated_at: 2026-06-06T10:23:54Z
saved digest: sha256:bd2bc903...
load error: SDKStoreError workspace schema_digest mismatch:
manifest='sha256:bd2bc903...',
expected='sha256:348fa55...'
```

Attach reproduction:

```text
attach error: SDKStoreError schema mismatch:
Database has schema_digest='sha256:...', but schema_classes compile to 'sha256:...'
```

## 3. Triage Table

| ID | Classification | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| A1 | (c) shape conflict | `schema_digest` is currently object-content hash, not schema-identity hash. | `canonicalize_schema_ir_jcs(...)` includes `generated_at`. | Split full object canonicalization from digest identity canonicalization. |
| A2 | (c) shape conflict | Schema object write / validate assumes filename digest equals full object bytes digest. | `database.py:641-643`, `:682-684`. | Validate object payload by recomputing schema identity digest from parsed schema IR, not by hashing full object bytes. |
| A3 | (b) small gap | Tests create/load workspace within the same second, hiding the bug. | Existing lifecycle tests load immediately after save. | Add cross-second reload / attach regression tests. |
| I1 | (a) shipped covers | `generated_at` is explicitly metadata-like compiler output and can remain required. | `generated_at` is top-level and validated as non-empty string. | Keep it in schema object; exclude from identity digest only. |
| I2 | (a) shipped covers | `pattern` and `enum_values` are semantic validation fields. | `application/value_validation.py` consumes both. | Keep in identity digest. |
| I3 | (c) shape conflict | `description` and `tags` look metadata-like, but excluding them now broadens scope. | Compiler copies them into schema IR; runtime partly carries `description`. | Keep them in digest for this slice; defer policy decision. |
| I4 | (c) shape conflict | Entity `version` semantics are policy-sensitive. | Compiler copies `Entity.Meta.version`; runtime does not deeply consume it like cardinality/type. | Keep in digest for this slice; defer policy decision. |
| D1 | (c) shape conflict | `FactGraph.load_workspace(...)` fails for identical classes after timestamp crosses one-second boundary. | Manual reproduction. | Implement stable schema identity digest. |
| D2 | (c) shape conflict | `FactGraph.attach(db, schema_classes=...)` fails for identical classes after timestamp crosses one-second boundary. | Manual reproduction. | Same fix covers attach. |
| N1 | (a) shipped covers | Schema structure fields are already canonicalized deterministically. | JSON canonicalization sorts keys and rejects floats. | Preserve JCS style for identity projection. |

## 4. Open Questions

No blocker Qs for this slice.

Carry-forward policy questions:

- Q-deferred-1: Should `description` and `tags` be excluded from schema identity in a later metadata-policy slice?
- Q-deferred-2: Should entity-level `version` be identity-bearing or metadata-only?

## 5. Frictions

- Schema object filename currently acts as content-addressed object hash. After this slice, it becomes schema-identity-addressed object filename while object bytes may include metadata.
- Existing `validate_schema_object_for_workspace(path, schema_ir)` compares full expected bytes. That must change to tolerate different `generated_at` while still rejecting structural mismatches.

## 6. Cross-doc Seams

- `docs/quickstart/schema_definition.md` currently describes schema digest as hash of canonicalized schema IR. It should clarify identity projection excludes volatile metadata.
- `docs/quickstart/load_and_save.md` should describe load/attach as schema identity matching, not full object timestamp matching.

## 7. Recommendations for Blueprint

Implement a narrow stability slice:

1. Keep `canonicalize_schema_ir_jcs(...)` as full schema object canonicalization.
2. Add identity canonicalization excluding only top-level `generated_at`.
3. Change `schema_digest(...)` to use identity canonicalization.
4. Change schema object write / validate to validate parsed object identity digest and full schema validity, not full object byte digest.
5. Add tests for cross-second compile, workspace reload, and Database attach.
6. Update schema/load docs.

## 8. Audit Method Notes

This audit was created from a direct user-reported defect and confirmed through source reads plus minimal runtime reproduction. It uses Stage 1 audit output but skips Q-resolution because no blocker Q is needed for the `generated_at` fix.

## 9. Audit Completeness Checklist

- [x] All in-scope rows triaged
- [x] All open Qs surfaced
- [x] All frictions enumerated
- [x] Out-of-scope explicitly listed
- [x] Recommendations provided
