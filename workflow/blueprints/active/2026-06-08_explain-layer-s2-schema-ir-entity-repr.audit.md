# Audit Log: S2 — Schema IR Repr + Entity Repr Renderer

- Blueprint: [2026-06-08_explain-layer-s2-schema-ir-entity-repr.md](./2026-06-08_explain-layer-s2-schema-ir-entity-repr.md)
- Status: draft

---

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-06-08 | draft | Blueprint created | Source-read `schema_compile.py`, `schema_ir.py`, `schema_runtime.py`, parent design §5.2/§10.1, and S1 closure. Draft locks S2 as canonical Schema IR persistence + runtime index + entity renderer, with atom rendering deferred to S4. |

---

## Decision Notes

### D-1: S2 follows S1 but does not expand authoring API

**Decision (draft)**: S2 consumes S1's already-validated authoring metadata and persists it into canonical Schema IR. It does not add new SDK descriptor parameters or new `Entity.Meta` options.

**Reasoning**: S1 already owns the public authoring surface. S2's job is to make that metadata available to application/runtime code and later prober slices.

### D-2: `repr` is canonical schema identity content

**Decision (draft)**: Once S2 persists `repr` into Schema IR, `schema_digest(...)` should change when `repr` changes.

**Reasoning**: `schema_digest` is now a schema identity digest over canonical schema content excluding only top-level `generated_at`. A rendering template changes the explain-layer interpretation of the schema, so it should be identity-bearing unless Step 4.3 discovers a conflict.

### D-3: `render_entity_repr(...)` is application-layer runtime code

**Decision (draft)**: Put the pure renderer near `SchemaIndex` in `application/schema_runtime.py` unless preflight finds a cleaner local module boundary.

**Reasoning**: Rendering needs validated Schema IR, `EntityTypeInfo`, and `materialize_identity(...)` semantics. Keeping it in the application runtime layer avoids SDK dependency and keeps prober slices from reading SDK classes.

### D-4: Predicate-level `repr` is carried but not consumed in S2

**Decision (draft)**: S2 persists `Identity.repr` / `Field.repr` on predicate metadata and exposes it through `PredicateInfo.repr`. It does not render atom text yet.

**Reasoning**: Atom-level wording requires prober context (`%ENT`, `%FLD`, entity-ref rendering, atom status). That belongs to S4 after S3 builds evidence atoms.
