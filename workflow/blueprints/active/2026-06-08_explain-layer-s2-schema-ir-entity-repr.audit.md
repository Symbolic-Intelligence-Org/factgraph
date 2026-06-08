# Audit Log: S2 — Schema IR Repr + Entity Repr Renderer

- Blueprint: [2026-06-08_explain-layer-s2-schema-ir-entity-repr.md](./2026-06-08_explain-layer-s2-schema-ir-entity-repr.md)
- Status: draft

---

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-06-08 | draft | Blueprint created | Source-read `schema_compile.py`, `schema_ir.py`, `schema_runtime.py`, parent design §5.2/§10.1, and S1 closure. Draft locks S2 as canonical Schema IR persistence + runtime index + entity renderer, with atom rendering deferred to S4. |
| 2026-06-08 | draft | Step 4.2 review + tightening | Source-read S1 impl lineage (`v0.2.0-impl-schema-repr-dsl-2026-06-08`) for SDK/source parser metadata producers. Tightened S1 test inversion, identity field-row repr placement, relationship field repr persistence, and S1-lineage fork requirement. |
| 2026-06-08 | draft | Step 4.3 preflight PASS + Step 4.4 amendment | Preflight artifact found no abandonment. Folded PF-R4 schema mutation boundary, PF-R5 application export requirement, PF-r1 mapping input clarification, and PF-r2 grammar parity requirement. |

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

### D-5: S1 boundary test must invert in S2

**Decision (Step 4.2)**: S2 must replace or rewrite S1's focused boundary test `test_repr_metadata_does_not_persist_to_schema_ir_in_s1`.

**Reasoning**: That S1 test intentionally locked the pre-S2 boundary. Once S2 lands, the correct assertion is the opposite: `repr` metadata persists to canonical Schema IR and affects schema identity. Leaving the S1 test untouched would create a false regression.

### D-6: Identity and relationship placement

**Decision (Step 4.2)**: Identity field rows may carry `repr`, generated identity predicate rows carry the same template, and relationship field `repr` persists on relationship predicate rows.

**Reasoning**: Existing compile code already carries identity metadata through identity field rows and then derives identity predicates from those rows. Relationship fields use the same `Field(...)` authoring metadata path as entity fields, so dropping `repr` there would create a split-brain Field API.

### D-7: Implementation fork source

**Decision (Step 4.2)**: S2 implementation must fork from `v0.2.0-impl-schema-repr-dsl-2026-06-08`, not from the parent blueprint branch or bare master.

**Reasoning**: The parent blueprint branch records S1 as archived but does not contain the S1 code changes. S2 depends on S1's runtime/source authoring metadata producers.

### D-8: Repr changes are schema changes

**Decision (Step 4.4)**: Existing schema rows with changed `repr` are not treated as additive schema extensions. S2 keeps `schema_mutation_runtime`'s direct row comparison behavior.

**Reasoning**: S2 makes `repr` canonical schema identity content. A metadata-only repr edit changes explain-layer interpretation and `schema_digest`, so silently accepting it as additive would contradict the identity model.

### D-9: Application export only

**Decision (Step 4.4)**: Export `render_entity_repr(...)` through `factgraph.application.schema_runtime` and `factgraph.application`, but not through `factgraph.sdk`.

**Reasoning**: S2's renderer is an application-layer helper for prober/runtime code. SDK user-facing rendering helpers can be designed after S3/S4 once atom rendering semantics are stable.
