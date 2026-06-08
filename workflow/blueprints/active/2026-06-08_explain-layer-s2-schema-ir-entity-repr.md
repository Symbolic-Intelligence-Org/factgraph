# Task Blueprint: S2 — Schema IR Repr + Entity Repr Renderer

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08 (Step 4.2 review + tightening)
- Parent Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md)
- Depends On:
  - S0 Rule.repr rename — implemented at `eb79f1c5`
  - S1 Schema DSL repr templates — implemented at `6090eb05`
- Related Modules:
  - `src/factgraph/authoring/schema_compile.py` (authoring repr metadata → canonical Schema IR)
  - `src/factgraph/core/schema/schema_ir.py` (Schema IR validation / canonical identity bytes)
  - `src/factgraph/application/schema_runtime.py` (SchemaIndex repr metadata + entity label renderer)
  - `src/factgraph/sdk/compile.py` (compile path from SDK classes)
  - `src/factgraph/sdk/schema.py` and `src/factgraph/authoring/schema_dsl_parse.py` (S1 metadata producers; no S2 API shape change expected)
- Related Docs:
  - [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md) §5.1-§5.3, §10.1 S2
  - `docs/quickstart/schema_definition.md`
  - `docs/official/kernel/quickstart/schema.md`
  - `src/factgraph/sdk/docs/04_api_surface.en.md`
- Audit Log:
  - [2026-06-08_explain-layer-s2-schema-ir-entity-repr.audit.md](./2026-06-08_explain-layer-s2-schema-ir-entity-repr.audit.md)

---

## 1. Problem

S1 accepts and validates `repr=` metadata in the SDK/source schema authoring layers, but the metadata is still intentionally stopped before canonical Schema IR. That means downstream explain-layer code cannot access stable entity labels or field/identity wording through `SchemaIndex`.

S2 must persist that metadata into canonical Schema IR and expose an application-layer pure entity renderer so later prober slices can produce readable atom/conclusion labels without reaching back into SDK classes.

## 2. Goals

1. Persist entity-level `Meta.repr` into canonical Schema IR entity rows.
2. Persist `Identity.repr` / `Field.repr` into canonical Schema IR predicate rows.
3. Preserve S1 validation semantics while adding IR-level validation for externally supplied Schema IR.
4. Extend `SchemaIndex` runtime DTOs with repr metadata.
5. Add a pure application-layer `render_entity_repr(...)` helper for entity labels.
6. Make `repr` part of schema identity bytes, just like other canonical schema content.
7. Add focused tests covering SDK class compile, source parser compile, IR validation, runtime index, and entity rendering.
8. Update schema docs to state S2 persistence and rendering behavior.
9. Update S1's explicit "repr does not persist to Schema IR" boundary test into an S2 persistence test.

## 3. Non-goals

- No prober, `EvidenceTree`, `EvidenceAtom`, or atom-level `repr_text` assembly. Those are S3/S4.
- No `Explanation.repr` or `Explanation.repr_text` changes.
- No field atom rendering helper beyond carrying predicate-level `repr` through `PredicateInfo`.
- No SDK authoring API changes; S1 already added `repr=`.
- No workspace persistence rewrite. Schema digest changes are normal because `repr` becomes canonical Schema IR content.
- No relationship label renderer. Relationship field predicate `repr` persistence is in scope if preflight confirms S1 metadata reaches relationship authoring payloads, but entity label rendering remains entity-only.
- No migration or backward compatibility aliases for old Schema IR that lacks repr; absence means default rendering.

## 4. Current Context

**Source-read — shipped state after S1 (2026-06-08)**:

| # | Location | Current behavior | S2 target |
|---|---|---|---|
| 1 | `authoring/schema_compile.py:_compile_entity` | copies entity `version` / `description` / `tags`; ignores authoring `repr` | copy validated entity `repr` into entity row |
| 2 | `authoring/schema_compile.py:_compile_identity_field` | identity field rows may carry description/pattern/enum metadata, but no IR repr target | copy identity `repr` on the identity field row and through to the generated identity predicate |
| 3 | `authoring/schema_compile.py:_copy_description_pattern_enum` | copies predicate `description` / `pattern` / `enum_values` | also copy `repr` to field/identity/relationship predicate rows |
| 4 | `core/schema/schema_ir.py:_validate_entities` | validates entity type + identity fields; ignores extra row keys | validate optional entity `repr` as non-empty string + placeholder grammar |
| 5 | `core/schema/schema_ir.py:_validate_predicates` | validates predicate core shape; ignores optional metadata keys | validate optional predicate `repr` as non-empty string |
| 6 | `application/schema_runtime.py:EntityTypeInfo` | no repr field | add `repr: str | None` |
| 7 | `application/schema_runtime.py:PredicateInfo` | no repr field | add `repr: str | None` |
| 8 | `application/schema_runtime.py` | no entity rendering helper | add pure `render_entity_repr(...)` helper |

**Open checks for Step 4.2 / 4.3**:

| ID | Question | Current bias |
|---|---|---|
| Q-S2-A | Exact `render_entity_repr(...)` signature and module export location | `application/schema_runtime.py`, exported alongside `encode_entity_ref`; signature accepts `entity_type`, identity mapping, and `index` |
| Q-S2-B | Should IR validation re-run placeholder grammar? | Yes. External Schema IR should not bypass S1's template rules |
| Q-S2-C | Should relationship field `repr` persist? | Resolved in Step 4.2: yes; shared `Field(repr=)` metadata must persist on relationship predicate rows too |
| Q-S2-D | Does `repr` affect `schema_digest`? | Yes. It is canonical Schema IR content and should change schema identity |
| Q-S2-E | Default label when `Meta.repr` is absent | `"<EntityType> <first identity value>"` per design §5.2 |
| Q-S2-F | How to render missing/extra identity keys | Reuse `materialize_identity(...)` semantics: missing/unknown/type mismatch raises `SchemaResolutionError` |

## 5. Proposed Shape

### Canonical Schema IR

S2 carries S1 metadata into canonical IR:

```python
{
    "entity_type": "User",
    "identity_fields": [{"name": "user_id", "type_domain": "string", "repr": "%ENT has id %FLD"}],
    "repr": "%CLS %user_id",
}
```

and predicate rows:

```python
{
    "pred_id": "user:user_id",
    "owner_type": "User",
    "py_field_name": "user_id",
    "is_identity_field": True,
    "repr": "%ENT has id %FLD",
    ...
}
```

Entity rows store `Meta.repr`. Predicate rows store `Identity.repr` / `Field.repr` / relationship field `repr`.

Identity field rows also carry `repr` to match the existing `description` / `pattern` metadata pattern: `_compile_identity_field(...)` returns canonical identity field rows and `_compile_identity_predicate(...)` derives identity predicates from those rows. Runtime consumers read predicate-level `repr` through `PredicateInfo`, but the canonical entity identity row may still contain the same authoring metadata.

### Runtime Index

```python
@dataclass(frozen=True)
class PredicateInfo:
    ...
    repr: str | None = None

@dataclass(frozen=True)
class EntityTypeInfo:
    ...
    repr: str | None = None
```

### Entity Renderer

Proposed signature:

```python
def render_entity_repr(
    entity_type: str,
    identity: Mapping[str, Any],
    *,
    index: SchemaIndex,
) -> str:
    ...
```

Behavior:

- Materialize/validate identity using existing `materialize_identity(...)`.
- If `EntityTypeInfo.repr` is present, substitute `%CLS` and identity-field placeholders.
- If absent, return `"{entity_type} {first_identity_value}"`.
- Formatting is protocol-simple string conversion for now; S4 can refine value rendering for atom prose.

## 6. Boundaries And Invariants

- S2 is the first slice where `repr` changes canonical Schema IR and therefore `schema_digest`.
- S2 does not change authoring API validation except through IR-level validation on compiled/external schemas.
- S2 does not change write protocol, ledger claims, or `fg.audit`.
- S2 preserves all existing `description` / `pattern` / `enum_values` behavior.
- `Meta.repr` remains identity-only; mutable field placeholders remain invalid.
- Predicate-level `repr` is stored for later atom rendering but not consumed by S2 except through runtime index tests.
- Relationship field `repr` persists on relationship predicate rows because S1 exposes the same `Field(repr=)` descriptor for relationships.
- Missing `repr` remains valid; fallback rendering is deterministic.
- S2 implementation must fork from the S1 impl lineage, not bare `master`, because the parent blueprint branch does not itself contain S1 code changes.

## 7. Acceptance

- [ ] SDK class schemas with `Meta.repr`, `Identity.repr`, and `Field.repr` compile into Schema IR with `repr` keys.
- [ ] Source-file schema parser output compiles into the same Schema IR repr placement.
- [ ] `ensure_schema_ir(...)` accepts valid entity/predicate `repr` metadata.
- [ ] `ensure_schema_ir(...)` accepts valid identity field-row `repr` metadata and generated identity predicates carry the same template.
- [ ] Relationship `Field(repr=...)` compiles into relationship predicate `repr`.
- [ ] `ensure_schema_ir(...)` rejects empty/non-string repr metadata.
- [ ] `ensure_schema_ir(...)` rejects invalid `Meta.repr` placeholders (`%ENT`, `%FLD`, unknown/non-identity field placeholders).
- [ ] `schema_digest(...)` changes when a persisted repr template changes.
- [ ] `build_schema_index(...)` exposes `EntityTypeInfo.repr` and `PredicateInfo.repr`.
- [ ] `render_entity_repr("User", {"user_id": "u-1"}, index=...)` renders the `Meta.repr` template.
- [ ] `render_entity_repr(...)` uses the design fallback when `Meta.repr` is absent.
- [ ] S1's `test_repr_metadata_does_not_persist_to_schema_ir_in_s1` is replaced or rewritten to assert S2 persistence.
- [ ] Existing schema compile/runtime tests still pass.
- [ ] Docs describe that S1 authoring `repr=` is persisted in Schema IR and usable by the renderer.

## 8. Implementation Plan

1. Step 4.2: Review signature, relationship-field persistence, S1-lineage source truth, and schema-digest implications.
2. Step 4.3: Preflight `schema_compile.py`, `schema_ir.py`, `schema_runtime.py`, S1 tests, and docs blast radius.
3. Step 4.4: Fold preflight findings into this blueprint.
4. Step 4.6: Scope freeze after Q-S2-A through Q-S2-F are locked.
5. Step 4.7: Implement on `v0.2.0-impl-schema-ir-entity-repr-2026-06-08`, forked from the S1 impl lineage (`v0.2.0-impl-schema-repr-dsl-2026-06-08`).
6. Step 4.8: Close blueprint as implemented.
7. Step 4.9: Archive blueprint pair and preflight artifact.

## 9. Docs To Update

- `docs/quickstart/schema_definition.md`
- `docs/official/kernel/quickstart/schema.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`
- Program blueprint parent status table if S2 closes.

## 10. Outcome / Deviations

Task completion fills this section.
