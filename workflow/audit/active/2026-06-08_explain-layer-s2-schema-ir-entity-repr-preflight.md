# Preflight: S2 — Schema IR Repr + Entity Repr Renderer

- Date: 2026-06-08
- Blueprint: `workflow/blueprints/active/2026-06-08_explain-layer-s2-schema-ir-entity-repr.md`
- Status: PASS with amendment required
- Source truth: S1 impl lineage `v0.2.0-impl-schema-repr-dsl-2026-06-08` for authoring API, current parent blueprint branch for shared compile/runtime files.

---

## 1. Scope

S2 persists S1 `repr` metadata into canonical Schema IR, exposes that metadata through `SchemaIndex`, and adds a pure entity-label renderer. It does not implement atom rendering, prober assembly, or SDK authoring API changes.

---

## 2. Method

Rule 1 source-read targets:

| Target | Purpose |
|---|---|
| `git show v0.2.0-impl-schema-repr-dsl-2026-06-08:src/factgraph/sdk/schema.py` | Verify S1 runtime DSL metadata producers |
| `git show v0.2.0-impl-schema-repr-dsl-2026-06-08:src/factgraph/authoring/schema_dsl_parse.py` | Verify S1 source parser metadata producers |
| `src/factgraph/authoring/schema_compile.py` | Locate compile persistence points |
| `src/factgraph/core/schema/schema_ir.py` | Locate canonical validation and digest behavior |
| `src/factgraph/application/schema_runtime.py` | Locate runtime DTO and renderer placement |
| `src/factgraph/application/schema_mutation_runtime.py` | Check schema-change policy interaction |
| `tests/test_schema_repr_dsl.py`, `tests/test_relationship_schema.py`, `tests/test_application_schema_runtime.py` | Test blast radius |

---

## 3. Required Findings

### PF-R1 — S1 implementation lineage is mandatory

The parent blueprint branch records S1 as implemented, but does not contain S1 source code. The S2 implementation branch must fork from `v0.2.0-impl-schema-repr-dsl-2026-06-08`.

Evidence:

- S1 impl `sdk/schema.py` stores `_DataMember.repr`, emits it through `_add_common_authoring(...)`, and validates `Meta.repr`.
- S1 impl `schema_dsl_parse.py` accepts `repr` for `Identity(...)`, `Field(...)`, and `Meta`.

Blueprint action: already folded in Step 4.2; keep as required acceptance.

### PF-R2 — Identity `repr` placement must mirror existing identity metadata duplication

`_compile_identity_field(...)` returns identity field rows and `_compile_identity_predicate(...)` derives predicates from those rows. Existing metadata such as `description` and `pattern` can therefore appear on both the entity identity field row and generated identity predicate row.

S2 should carry `repr` the same way:

- entity identity field row: `{"name": ..., "type_domain": ..., "repr": ...}`
- generated identity predicate row: `{"pred_id": ..., "is_identity_field": True, "repr": ...}`

Blueprint action: already folded in Step 4.2; keep explicit in tests.

### PF-R3 — Relationship field `repr` persistence is in scope

S1 `RelationshipMeta` builds relationship field authoring rows via `member.to_authoring(...)`, the same `Field` path used by entity fields. Dropping relationship `repr` during compile would create inconsistent `Field(repr=...)` behavior.

Evidence:

- S1 impl `sdk/schema.py:350-365` collects `Field` members in `RelationshipMeta`.
- S1 impl `sdk/schema.py:363` calls `member.to_authoring(...)`.
- `schema_compile.py:_compile_relationship_field(...)` uses `_copy_description_pattern_enum(...)`, the same natural helper extension point.

Blueprint action: already folded in Step 4.2; preflight confirms it.

### PF-R4 — Schema mutation policy must treat repr changes as canonical schema changes

`schema_mutation_runtime.validate_additive_schema_extension(...)` compares entity identity field rows and predicate stable projections. Since S2 makes `repr` canonical identity-bearing content, changing `repr` on an existing entity/field should not be silently treated as additive.

Evidence:

- `schema_mutation_runtime.py:63-66` compares `current_entity.identity_fields` vs candidate.
- `schema_mutation_runtime.py:74-85` compares current/candidate predicates.
- `schema_digest(...)` includes all canonical Schema IR content except top-level `generated_at`.

Required decision: S2 should **not** whitelist existing `repr` changes in additive schema mutation. Add one acceptance/test note: existing repr changes remain schema changes, while new entity/field repr metadata is allowed as part of the new row.

### PF-R5 — Application export must be explicit if renderer is public within application layer

`application/schema_runtime.py` exports helpers both through its local `__all__` and `factgraph.application.__init__`. If `render_entity_repr(...)` is the intended application-layer API for prober/S4 consumers, S2 should export it consistently from both places.

Evidence:

- `schema_runtime.py.__all__` currently lists schema runtime helpers.
- `application/__init__.py:93-108` imports schema runtime symbols.
- `application/__init__.py:118-205` lists the public application exports.

Required decision: add `render_entity_repr` to `schema_runtime.__all__` and `factgraph.application.__all__`. No SDK export in S2.

---

## 4. Recommended Findings

### PF-r1 — Renderer input should accept `Mapping[str, Any]`, not only `dict`

`materialize_identity(...)` currently checks for `dict`, but S2's public renderer can type as `Mapping[str, Any]` while normalizing via `dict(identity)` before calling existing validation. This keeps the pure function ergonomic without changing lower-level validation.

Blueprint action: clarify signature if desired.

### PF-r2 — Use existing placeholder scanner semantics rather than inventing a second grammar

S1 has `_repr_template_tokens(...)` in SDK and source parser layers. Core Schema IR cannot import SDK, but S2 should implement the same `%([A-Za-z_][A-Za-z0-9_]*)` token rule locally in `schema_ir.py` to avoid changing accepted templates.

Blueprint action: add "grammar parity" acceptance.

---

## 5. Verified

| ID | Verification |
|---|---|
| PF-v1 | `core/schema/schema_ir.py` rejects unexpected top-level keys but does not currently reject extra entity/predicate row keys, so adding `repr` row metadata is shape-compatible once validators are extended. |
| PF-v2 | `schema_digest(...)` already uses canonical identity bytes that include all non-`generated_at` Schema IR content, so no digest helper change is needed. |
| PF-v3 | `build_schema_index(...)` is the right runtime projection layer; prober slices should not read raw Schema IR directly for labels. |
| PF-v4 | Existing relationship tests in `tests/test_relationship_schema.py` provide a natural place to add relationship `repr` persistence coverage. |
| PF-v5 | Existing runtime tests in `tests/test_application_schema_runtime.py` provide a natural place to add `render_entity_repr(...)` and runtime DTO coverage. |

---

## 6. Scoped Details

- Atom-level use of predicate `repr` is out of S2. S2 only persists and exposes it.
- Entity renderer fallback is `"<EntityType> <first identity value>"`; richer value formatting can wait for S4.
- No workspace migration is needed; new schema bytes/digest apply to newly compiled schema objects.

---

## 7. Abandonment

No abandonment findings. S2 remains implementable as scoped after folding PF-R4/PF-R5 and clarifying PF-r1/PF-r2.

---

## 8. Amendment Checklist

Fold into blueprint Step 4.4:

1. Add PF-R4 mutation-policy boundary and acceptance.
2. Add PF-R5 application export requirement, no SDK export.
3. Clarify renderer accepts mapping-like identity but normalizes through existing validation.
4. Add Schema IR placeholder grammar parity requirement.
5. Add tests list: S1 boundary inversion, relationship repr, schema mutation repr-change behavior, application export.
