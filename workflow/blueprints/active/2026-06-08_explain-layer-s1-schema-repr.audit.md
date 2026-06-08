# Audit Log: S1 — Schema DSL Repr Templates

- Blueprint: [2026-06-08_explain-layer-s1-schema-repr.md](./2026-06-08_explain-layer-s1-schema-repr.md)
- Status: draft

---

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-06-08 | draft | Blueprint created | Source-read `sdk/schema.py` and design §5.1-§5.3. Draft locks S1 as SDK DSL acceptance + validation, with Schema IR persistence deferred to S2 unless preflight proves a thinner split is impossible. |
| 2026-06-08 | draft | Step 4.2 review + tightening | Source-read `authoring/schema_dsl_parse.py`, `authoring/schema_compile.py`, `core/schema/schema_ir.py`, and `sdk/compile.py`. Tightened parser parity into scope, resolved Meta.repr `%CLS`-only as valid, and made S1/S2 boundary explicit: repr authoring keys may be ignored by schema compile until S2. |
| 2026-06-08 | draft | Step 4.3 preflight PASS with amendment required | Wrote `workflow/audit/active/2026-06-08_explain-layer-s1-schema-repr-preflight.md`. Findings: PF-R1 parser parity required, PF-R2 schema compile boundary explicit, PF-R3 stale error/docs wording. No abandonment. |

---

## Decision Notes

### D-1: S1/S2 split

**Decision (draft)**: S1 is the authoring DSL slice. It adds `repr=` to `Identity()` / `Field()` and `Meta.repr`, validates placeholder grammar at class definition time, and stores the result in SDK declaration metadata. It does not change core Schema IR required fields or persistence.

**Reasoning**: The program blueprint separates S1 (Schema DSL) from S2 (Schema IR + `render_entity_repr`). Keeping the IR change in S2 avoids mixing public authoring surface, schema object persistence, and render runtime in one slice.

### D-2: Placeholder grammar bias

**Decision (draft)**: Field/Identity templates are current-atom templates and should allow only `%CLS`, `%ENT`, and `%FLD`. `Meta.repr` is an entity label template and should allow `%CLS` plus identity-field placeholders only.

**Reasoning**: This matches `explain-layer-complete-design.zh.md` §5.2. It keeps mutable fields out of entity labels and prevents field-level templates from reaching sideways into unrelated fields.

### D-3: Parser parity remains an audit item

**Decision (Step 4.2)**: `src/factgraph/authoring/schema_dsl_parse.py` is in S1 scope. It has parallel `Identity()` / `Field()` / `Meta` allowlists, so source-file authoring must accept and emit `repr` metadata in lockstep with runtime SDK schema classes.

**Reasoning**: `schema.py` is the primary runtime SDK DSL surface, but parser parity prevents a split-brain authoring experience if the parser accepts the same descriptor calls.

### D-4: `Meta.repr` does not require an identity placeholder

**Decision (Step 4.2)**: `Meta.repr = "%CLS"` is valid. `Meta.repr` remains identity-only for any field placeholders it references, but it need not reference one.

**Reasoning**: The design constrains mutable-field references; it does not require every label to include an identity value. Requiring an identity placeholder would be an extra product constraint with no immediate implementation need.

### D-5: S1 stores authoring metadata; S2 persists canonical Schema IR

**Decision (Step 4.2)**: S1 may add `repr` to `__sdk_entity_spec__` and source parser output while leaving `schema_compile.py` / canonical Schema IR unchanged. Tests should make the boundary explicit: classes with `repr=` compile successfully, but IR persistence is S2.

**Reasoning**: `compile_schema_from_classes(...)` builds an authoring payload from `__sdk_entity_spec__`; `schema_compile.py` currently copies only `description`, `pattern`, and `enum_values` to predicates and entity-level metadata. That means S1 can safely stage authoring metadata without changing schema object identity/persistence.
