# Core Schema Repr Templates

- Scope: `src/factgraph/core/schema/schema_repr.py`
- Last updated: 2026-06-09
- Audience: schema DSL maintainers and explain-layer implementers

`schema_repr.py` owns the shared validation rules for schema-level `repr=`
templates. Both schema declaration paths use these helpers:

- runtime SDK declarations in `factgraph.sdk.schema`
- source/AST declarations in `factgraph.authoring.schema_dsl_parse`

S1 only accepts and validates explicit templates. It does not compile them into
Schema IR, so `schema_digest(...)` remains unchanged when a caller adds or
removes `repr=` metadata.

## Placeholder Matrix

| Placeholder | `Field.repr` / `Identity.repr` | `Entity.Meta.repr` |
|---|---|---|
| `%CLS` | allowed | allowed |
| `%ENT` | allowed | rejected |
| `%FLD` | allowed, current field value only | rejected |
| `%<identity_field>` | rejected | allowed for identity fields only |

Unknown placeholders are rejected. Field names that collide with reserved
placeholders (`CLS`, `ENT`, `FLD`) are rejected when a `repr` template is used,
because the template language could not distinguish the field from the reserved
token.

## Layer Boundary

`repr=` is authoring metadata for the explain layer. S1 deliberately keeps it
out of authoring payloads and compiled Schema IR. S2 is responsible for deciding
how templates become runtime render inputs for `render_entity_repr(...)`.
