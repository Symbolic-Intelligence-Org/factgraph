# Preflight: S1 — Schema DSL Repr Templates

- Blueprint: `workflow/blueprints/active/2026-06-08_explain-layer-s1-schema-repr.md`
- Fork/branch context: `v0.2.0-blueprint-explain-layer-2026-06-08`
- Status: PASS with amendment required
- Date: 2026-06-08

---

## 1. Scope

S1 covers schema authoring surface only:

- `Identity(repr=...)`
- `Field(repr=...)`
- `class Meta: repr = "..."`
- validation of repr placeholders at schema class / source parse time
- docs/tests for the authoring surface

S1 does not persist repr templates into canonical Schema IR. S2 owns Schema IR fields and `render_entity_repr(...)`.

---

## 2. Method

Fresh-read files:

- `src/factgraph/sdk/schema.py`
- `src/factgraph/authoring/schema_dsl_parse.py`
- `src/factgraph/authoring/schema_compile.py`
- `src/factgraph/core/schema/schema_ir.py`
- `src/factgraph/sdk/compile.py`
- `docs/quickstart/schema_definition.md`
- `docs/official/kernel/quickstart/schema.md`

Grep patterns:

- `Identity() only accepts description= and pattern=`
- `Field() only accepts description= and pattern=`
- `Entity.Meta only supports version, description, and tags`
- `__sdk_entity_spec__`
- `compile_schema_from_classes`
- `parse_authoring_schema_dsl_v1`

---

## 3. Required Findings

### PF-R1 — Source-file parser parity is required

`src/factgraph/authoring/schema_dsl_parse.py` has a parallel authoring path:

- `_apply_entity_meta_fields(...)` allowlist currently: `{"version", "description", "tags"}`
- `_build_identity_from_kwargs(...)` allowlist currently: `{"description", "pattern"}`
- `_build_field_from_kwargs(...)` allowlist currently: `{"description", "pattern"}`

If S1 only updates `src/factgraph/sdk/schema.py`, runtime Python schema classes accept `repr=` while source-file DSL rejects it. This is a split-brain authoring surface.

**Required amendment**: S1 implementation must update both runtime SDK schema classes and source-file parser.

### PF-R2 — Schema compile boundary must be explicit

`src/factgraph/sdk/compile.py` builds an authoring payload from `__sdk_entity_spec__`, then calls `compile_authoring_schema_v1(...)`.

`src/factgraph/authoring/schema_compile.py` currently copies:

- entity-level `version`, `description`, `tags`
- predicate-level `description`, `pattern`, `enum_values`

It does not copy `repr` into Schema IR. `src/factgraph/core/schema/schema_ir.py` also validates only the current entity/predicate core shape.

**Required amendment**: S1 should explicitly allow repr to exist only in authoring metadata. Tests should verify compile still succeeds, while canonical Schema IR persistence remains deferred to S2.

### PF-R3 — Public error wording and docs must include repr

Current shipped wording says:

- `Identity() only accepts description= and pattern= in Form I`
- `Field() only accepts description= and pattern= in Form I`
- `Entity.Meta only supports version, description, and tags`

Docs also repeat this in:

- `docs/quickstart/schema_definition.md`
- `docs/official/kernel/quickstart/schema.md`

**Required amendment**: Update error strings and docs so S1 does not leave stale authoring contract text behind.

---

## 4. Recommended Findings

### PF-r1 — Keep `%field_name` syntax explicit

The design prose uses `%<field_name>` as metasyntax, but examples use literal `%code`. Blueprint wording should avoid implying that angle brackets are literal template characters.

**Recommendation**: Document `Meta.repr` identity placeholders as `%field_name`.

### PF-r2 — Test `Meta.repr = "%CLS"` as valid

The design constrains mutable field references; it does not require `Meta.repr` to include an identity field placeholder.

**Recommendation**: Add a focused test so `%CLS`-only remains intentionally accepted.

---

## 5. Verified

- PF-v1: Existing `description=` / `pattern=` behavior is localized and can remain unchanged.
- PF-v2: `pattern=` type validation happens during `to_authoring(...)`, so adding `repr=` does not affect regex validation.
- PF-v3: `schema_compile.py` ignoring unknown authoring keys means S1 can stage metadata before S2 without persistence churn.
- PF-v4: `core/schema/schema_ir.py` does not need to change in S1.
- PF-v5: Parent design already separates S1(Schema DSL) from S2(Schema IR + renderer).

---

## 6. Scoped Details

- S1 should add focused tests in the SDK schema / authoring parser area rather than broad runtime evaluate tests.
- S1 should not update schema digest expectations unless implementation accidentally persists repr into Schema IR; such persistence would be an S2 scope breach.
- S1 docs should explain `repr=` as evidence wording, distinct from `description=` as human-readable schema documentation.

---

## 7. Abandonment

None. Preflight found no reason to stop S1.

---

## 8. Amendment Checklist

- [ ] Blueprint includes source-file parser parity as required scope.
- [ ] Blueprint states S1 authoring metadata may be ignored by schema compile until S2.
- [ ] Blueprint acceptance covers `%CLS`-only `Meta.repr`.
- [ ] Blueprint docs list includes stale wording sites.
- [ ] Audit log records preflight PASS with amendment required.
