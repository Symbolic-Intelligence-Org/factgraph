# Audit Log: Explain Conformance Batch B — unified repr value rendering

Paired with [2026-06-10_explain-conformance-batch-b-repr-rendering.md](./2026-06-10_explain-conformance-batch-b-repr-rendering.md).

---

## A. Source Preflight (2026-06-10)

Codex read these shipped anchors before drafting:

- `src/factgraph/application/explain/prober.py`
  - `_bake_repr_text(...)`
  - `_repr_fact(...)`
  - `_entity_repr_for_fact(...)`
  - `_fact_fallback_repr(...)`
  - `_repr_compare(...)`
  - `_repr_builtin(...)`
  - `_term_display(...)`
  - `_term_value(...)`
- `src/factgraph/application/schema_runtime.py`
  - `render_entity_repr(...)`
  - `_identity_value_text(...)`
  - `materialize_identity(...)`
  - `_normalize_identity_value(...)`
  - `resolve_selector(...)`
- `src/factgraph/application/entity_view.py`
  - `_recover_identity_from_predicates(...)`
- `src/factgraph/core/protocol/tup_v1.py`
  - `FLOAT64_HEX_RE`
  - `_float64_bits(...)`
  - `_val_atom_for_claim_arg(...)`
  - `ENTITY_REF_PREFIX`
- Existing tests:
  - `tests/application/explain/test_prober.py`
  - `tests/test_application_schema_runtime.py`
  - `tests/sdk/test_explain_conformance_native.py`

## B. Preflight Findings

1. `_bake_repr_text(...)` already has the required `schema_index` and
   `view_facts` context.
2. Only `%ENT` currently uses that context. `%FLD`, compare, builtin, and fact
   fallback all call `_term_display(...)`.
3. `_term_display(...)` has no `schema_index` or `view_facts` parameters, so it
   cannot recover encoded idrefs or schema-aware labels.
4. Bug 2's `_entity_repr_for_fact(...)` already proves the idref recovery
   strategy: `_recover_identity_from_predicates(...)` plus
   `render_entity_repr(...)`, with graceful fallback.
5. `render_entity_repr(...)` is currently sequential replacement:
   `%CLS` first, then identity fields in declaration order. This makes prefix
   collisions and value-injection possible.
6. `_identity_value_text(...)` is the display-only edge for entity labels.
7. `materialize_identity(...)` is a public normalization path used by
   `resolve_selector(...)` and `entity_view._recover_identity_from_predicates`.
   It must not be turned into a display decoder.
8. `tup_v1.py` already owns canonical float64 validation and bit conversion.
   Any float64 display helper should live there or reuse its internals, not
   duplicate protocol logic in prober/schema_runtime.
9. Time values are epoch-nanos integers in protocol paths. No confirmed defect
   requires changing time display in Batch B.

## C. Scope Questions For Review

1. **Renderer placement**:
   Draft recommends a context-aware renderer in `prober.py`, because all
   current consumers are native prober repr paths. Scope review should decide
   whether to keep it private there or move a display helper to a shared
   application module.

2. **Float64 helper exposure**:
   Draft recommends a small public/internal helper in `tup_v1.py` so display
   code can decode canonical hex without copying `struct.unpack(...)`. Scope
   review should confirm helper name and whether it returns `float` or display
   `str`.

3. **Unbound placeholder wording**:
   Draft requires no raw internal `$...` variable names in human text. Exact
   wording is open (`<unbound>`, `<unbound:x>`, etc.).

4. **Unknown placeholder handling in `render_entity_repr(...)`**:
   Schema authoring validation should prevent unknown placeholders. Draft
   recommends preserving unknown text literally rather than adding runtime
   validation in Batch B.

5. **Time display**:
   Audit mentioned possible epoch-nanos display leakage. Source preflight found
   no locked time display policy. Draft keeps current integer rendering and
   leaves friendly timestamp formatting to a future design if needed.

## D. Required Tests

Batch B implementation must include tests that fail on current rendering:

1. `%FLD` entity-ref renders an entity label, not `idref_v1:...`.
2. Compare atom entity-ref operands render entity labels.
3. Float64 canonical hex renders numeric text in prober repr text.
4. Float64 identity values render numeric text through `render_entity_repr`.
5. `materialize_identity(...)` remains unchanged for float64 identity values.
6. `render_entity_repr(...)` handles prefix collision and value-injection
   without sequential replacement corruption.
7. True-unbound `NotReached` repr text does not expose raw internal `$...`
   variable names.
8. Existing Batch A/D and adapter cohorts remain green.

## E. Implementation Outcome

Pending.
