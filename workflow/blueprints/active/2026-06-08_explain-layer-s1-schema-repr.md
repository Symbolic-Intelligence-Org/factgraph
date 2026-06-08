# Task Blueprint: S1 — Schema DSL Repr Templates

- Status: scoped
- Created: 2026-06-08
- Last Updated: 2026-06-08 (Step 4.6 scope freeze)
- Parent Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md)
- Related Modules:
  - `src/factgraph/sdk/schema.py` (primary SDK DSL surface)
  - `src/factgraph/authoring/schema_dsl_parse.py` (source-file schema parser parity check)
  - `src/factgraph/core/schema/` (S2 boundary; no IR persistence in S1 unless preflight proves unavoidable)
- Related Docs:
  - [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md) §5.1-§5.3, §10.1 S1
  - `docs/quickstart/schema_definition.md`
  - `docs/official/kernel/quickstart/schema.md`
  - `src/factgraph/core/schema/docs/README.md`
- Audit Log:
  - [2026-06-08_explain-layer-s1-schema-repr.audit.md](./2026-06-08_explain-layer-s1-schema-repr.audit.md)
- Preflight:
  - [2026-06-08_explain-layer-s1-schema-repr-preflight.md](../../audit/active/2026-06-08_explain-layer-s1-schema-repr-preflight.md)

---

## 1. Problem

The explain layer needs schema-authored wording templates for atom-level evidence. S0 already renamed `Rule.desc` to `Rule.repr`, but the schema DSL still only accepts `description=` and `pattern=` on `Identity()` / `Field()`, and `Entity.Meta` only accepts `version`, `description`, and `tags`.

Without S1, S3/S4 can build evidence atoms but cannot render domain-specific field and entity labels from schema declarations.

## 2. Goals

1. Add `repr: str | None` to `Identity(...)` and `Field(...)` as authoring-time templates for field/identity atom wording.
2. Add `class Meta: repr = "..."` support for entity labels.
3. Validate repr template placeholder grammar at schema class definition time.
4. Store validated repr templates in SDK-level declaration metadata so S2 can compile them into schema IR.
5. Keep the source-file authoring parser in lockstep with runtime SDK schema classes.
6. Keep `description=` semantics unchanged; `repr=` is wording for evidence rendering, not documentation text.
7. Update SDK schema docs and focused tests.

## 3. Non-goals

- No Schema IR persistence or `ensure_schema_ir(...)` shape change in S1. That is S2.
- No `render_entity_repr(...)` function in S1. That is S2.
- No prober, `EvidenceTree`, or `Explanation.repr_text` work. Those are S3/S4.
- No changes to `Rule.repr`; S0 is already complete.
- No changes to `description=` or `pattern=` behavior.
- No write protocol changes and no ledger/audit model changes.

## 4. Current Context

**Preflight source-read — shipped state (2026-06-08)**:

| # | Location | Shipped behavior | S1 target |
|---|---|---|---|
| 1 | `src/factgraph/sdk/schema.py:62-74` | `_DataMember` accepts only `description` and `pattern` | Add `repr` validation/storage alongside existing fields |
| 2 | `src/factgraph/sdk/schema.py:101-113` | `Identity(...)` rejects all kwargs except `description=` / `pattern=` | Accept `repr=` and keep other legacy kwargs rejected |
| 3 | `src/factgraph/sdk/schema.py:143-156` | `Field(...)` rejects all kwargs except `description=` / `pattern=` | Accept `repr=` and keep other legacy kwargs rejected |
| 4 | `src/factgraph/sdk/schema.py:77-82` | `_add_common_authoring(...)` emits `description`/`pattern` only | Emit DSL-level `repr` metadata if S1 stores in authoring dict |
| 5 | `src/factgraph/sdk/schema.py:404-434` | `Entity.Meta` supports only `version`, `description`, `tags` | Add `repr` and validate identity-only placeholders |
| 6 | `docs/quickstart/schema_definition.md:66` | Docs say `Identity()` / `Field()` accept only two kwargs | Update to include `repr=` |
| 7 | `docs/official/kernel/quickstart/schema.md:168` | Docs say `Entity.Meta` only supports version/description/tags | Update to include `repr` |

**Open checks for Step 4.2 / 4.3**:

| ID | Question | Current bias |
|---|---|---|
| Q-S1-A | Should S1 emit `repr` into `__sdk_entity_spec__` authoring dicts before Schema IR changes? | Yes. Store DSL metadata now; S2 decides canonical IR placement. |
| Q-S1-B | Should `Field.repr` / `Identity.repr` allow identity placeholders like `%user_id`? | No. Field/Identity templates allow only `%CLS`, `%ENT`, `%FLD`. |
| Q-S1-C | Should `Meta.repr` require at least one identity placeholder? | Resolved in Step 4.2: no. `%CLS`-only is valid; referenced field placeholders remain identity-only. |
| Q-S1-D | Does `authoring/schema_dsl_parse.py` need parallel support for source-file schema DSL? | Resolved in Step 4.2: yes. It has parallel `Identity`/`Field`/`Meta` allowlists and must stay in lockstep. |

**Step 4.3 preflight findings folded (2026-06-08)**:

| ID | Finding | Blueprint response |
|---|---|---|
| PF-R1 | Source-file parser parity is required | `schema_dsl_parse.py` is in Goals / Proposed Shape / Acceptance |
| PF-R2 | Schema compile boundary must be explicit | S1 stores authoring metadata; S2 persists canonical IR |
| PF-R3 | Public error wording and docs must include `repr` | Docs and error wording listed in §9 / Acceptance |
| PF-r1 | `%field_name` syntax must be explicit | Placeholder table uses literal `%field_name` |
| PF-r2 | `%CLS`-only `Meta.repr` should be valid | Q-S1-C resolved accordingly and acceptance added |

## 5. Proposed Shape

### `Identity` / `Field`

```python
class User(Entity):
    user_id: str = Identity(repr="%ENT has id %FLD")
    country: Country = Field(repr="%ENT lives in %FLD")
```

Allowed placeholders:

| Placeholder | Meaning | Valid in |
|---|---|---|
| `%CLS` | Entity class name | `Identity.repr`, `Field.repr`, `Meta.repr` |
| `%ENT` | Subject entity label rendered from its `Meta.repr` | `Identity.repr`, `Field.repr` only |
| `%FLD` | Current field value; entity refs render through their `Meta.repr` | `Identity.repr`, `Field.repr` only |
| `%field_name` | Current entity identity field value; angle brackets in design prose are metasyntax, not literal template characters | `Meta.repr` only |

### `Entity.Meta.repr`

```python
class User(Entity):
    user_id: str = Identity()

    class Meta:
        repr = "%CLS %user_id"
```

`Meta.repr` is an identity-only entity label template. It forbids `%ENT`, forbids `%FLD`, and may only reference declared `Identity()` field names. It does not require an identity placeholder; `%CLS` alone is valid but less specific.

### S1/S2 split

S1 owns authoring API acceptance and validation. S2 owns schema IR persistence, canonical schema validation, and `render_entity_repr(...)`.

S1 stores repr templates in authoring metadata (`__sdk_entity_spec__` and the source-file parser output). `compile_schema_from_classes(...)` / `compile_authoring_schema_v1(...)` may ignore those keys until S2; this is acceptable and should be tested so the boundary is explicit.

### Source-file schema parser parity

`src/factgraph/authoring/schema_dsl_parse.py` has the same shipped `Identity()` / `Field()` / `Meta` allowlists as `sdk/schema.py`. S1 must update both:

- `_build_identity_from_kwargs(...)` accepts `repr=`.
- `_build_field_from_kwargs(...)` accepts `repr=`.
- `_apply_entity_meta_fields(...)` accepts `repr`.
- The parser emits the same authoring metadata keys as runtime schema classes.

## 6. Boundaries And Invariants

- Existing `description=` and docstring fallback behavior remains unchanged.
- Existing `pattern=` validation remains unchanged and still only applies to string-typed members.
- Unsupported legacy kwargs remain rejected with updated wording that includes `repr=`.
- Placeholder validation occurs at class definition time, not at prober runtime.
- `Meta.repr` references only identity fields to avoid mutable-label drift.
- S1 does not alter schema object digest behavior, schema IR required keys, or workspace persistence.
- S1 does not touch `FactGraph` runtime, `EvaluateRow`, `EvidenceGraph`, or `Explanation`.
- Unknown authoring keys in `schema_compile.py` are not a blocker for S1; S2 owns carrying repr keys through into canonical Schema IR.

## 7. Acceptance

- [ ] `Identity(repr="%ENT has id %FLD")` is accepted and stored in SDK declaration metadata.
- [ ] `Field(repr="%ENT lives in %FLD")` is accepted and stored in SDK declaration metadata.
- [ ] `class Meta: repr = "%CLS %user_id"` is accepted when `user_id` is an identity field.
- [ ] Empty or non-string repr templates raise `SDKSchemaError`.
- [ ] `Meta.repr` using `%ENT` or `%FLD` raises `SDKSchemaError`.
- [ ] `Meta.repr` referencing a non-identity field raises `SDKSchemaError`.
- [ ] `Field.repr` / `Identity.repr` using identity-field placeholders raises `SDKSchemaError`.
- [ ] `Meta.repr = "%CLS"` is accepted.
- [ ] `schema_dsl_parse.py` accepts and emits the same `repr` authoring metadata.
- [ ] Compiling schema classes with `repr=` still succeeds even though S2 has not persisted repr into Schema IR yet.
- [ ] Existing `description=` / `pattern=` tests still pass.
- [ ] SDK schema docs mention `repr=` separately from `description=`.

## 8. Implementation Plan

1. Step 4.2: Review S1/S2 split and lock Q-S1-A/B/C/D.
2. Step 4.3: Preflight `schema.py`, `authoring/schema_dsl_parse.py`, schema compile path, and docs blast radius.
3. Step 4.4: Fold preflight findings into this blueprint.
4. Step 4.6: Scope freeze after placeholder grammar and parser parity are locked.
5. Step 4.7: Implement on `v0.2.0-impl-schema-repr-dsl-2026-06-08`.
6. Step 4.8: Close blueprint as implemented.
7. Step 4.9: Archive blueprint pair.

## 9. Docs To Update

- `docs/quickstart/schema_definition.md`
- `docs/official/kernel/quickstart/schema.md`
- `src/factgraph/core/schema/docs/README.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md` if preflight confirms API table coverage
- Error wording sites:
  - `src/factgraph/sdk/schema.py` (`Identity()` / `Field()` kwarg errors; `Entity.Meta` allowlist error)
  - `src/factgraph/authoring/schema_dsl_parse.py` (same source-file parser errors)
  - `docs/quickstart/schema_definition.md` unknown-kwarg table
  - `docs/official/kernel/quickstart/schema.md` Meta allowlist prose

## 10. Outcome / Deviations

To be filled at closure.
