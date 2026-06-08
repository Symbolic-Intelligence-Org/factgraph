# Audit Log: S1 — Schema DSL Repr Templates

- Blueprint: [2026-06-08_explain-layer-s1-schema-repr.md](./2026-06-08_explain-layer-s1-schema-repr.md)
- Status: draft

---

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-06-08 | draft | Blueprint created | Source-read `sdk/schema.py` and design §5.1-§5.3. Draft locks S1 as SDK DSL acceptance + validation, with Schema IR persistence deferred to S2 unless preflight proves a thinner split is impossible. |

---

## Decision Notes

### D-1: S1/S2 split

**Decision (draft)**: S1 is the authoring DSL slice. It adds `repr=` to `Identity()` / `Field()` and `Meta.repr`, validates placeholder grammar at class definition time, and stores the result in SDK declaration metadata. It does not change core Schema IR required fields or persistence.

**Reasoning**: The program blueprint separates S1 (Schema DSL) from S2 (Schema IR + `render_entity_repr`). Keeping the IR change in S2 avoids mixing public authoring surface, schema object persistence, and render runtime in one slice.

### D-2: Placeholder grammar bias

**Decision (draft)**: Field/Identity templates are current-atom templates and should allow only `%CLS`, `%ENT`, and `%FLD`. `Meta.repr` is an entity label template and should allow `%CLS` plus identity-field placeholders only.

**Reasoning**: This matches `explain-layer-complete-design.zh.md` §5.2. It keeps mutable fields out of entity labels and prevents field-level templates from reaching sideways into unrelated fields.

### D-3: Parser parity remains an audit item

**Decision (draft)**: `src/factgraph/authoring/schema_dsl_parse.py` is not assumed in or out yet. Step 4.3 must classify whether source-file schema parsing must accept `repr=` in the same slice.

**Reasoning**: `schema.py` is the primary runtime SDK DSL surface, but parser parity prevents a split-brain authoring experience if the parser accepts the same descriptor calls.
