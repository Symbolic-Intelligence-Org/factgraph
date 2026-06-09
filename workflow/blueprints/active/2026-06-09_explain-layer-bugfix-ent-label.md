# Task Blueprint: Explain v2 Bugfix — `%ENT` entity label recovery

- Status: draft
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Type: bugfix slice
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (edit target)
  - `src/factgraph/application/entity_view.py` (helper context)
  - `src/factgraph/application/schema_runtime.py` (render helper context)
  - `examples/explain_layer_demo.py` (demo note update if in scope)
- Audit Log:
  - [2026-06-09_explain-layer-bugfix-ent-label.audit.md](./2026-06-09_explain-layer-bugfix-ent-label.audit.md)

---

## 1. Problem

After the row-anchoring fix, native explanations are row-coherent, but field
templates using `%ENT` can still render a raw `idref_v1:...` token instead of a
schema-authored entity label such as `User u-1`.

This is a presentation correctness issue, not an evidence anchoring issue. The
evidence proves the row, but the rendered text is too low-level for the explain
layer's intended user-facing surface.

## 2. Root Cause

`prober.py:_entity_repr_for_fact(...)` currently succeeds only when the subject
term value is:

1. an `EntityRef` with an identity bundle; or
2. a mapping containing an `identity` mapping.

The native prober usually sees the subject as a bare `idref_v1:<type>:<digest>`
string, both from view-fact enumeration and from the row seed after
`_public_term_value(...)` unwrapping. A bare idref has no identity bundle, so
`_entity_repr_for_fact(...)` falls back to `_term_display(...)` and emits the raw
idref.

## 3. Goals

1. Thread `view_facts` through the repr-baking call chain inside `prober.py`.
2. For `%ENT`, recover identity values for bare idref subject strings by using
   the existing `_recover_identity_from_predicates(...)` helper.
3. Render recovered identities with `schema_runtime.render_entity_repr(...)`.
4. Preserve graceful fallback to raw idref when identity facts are not visible.
5. Keep non-entity repr behavior unchanged (`%FLD`, compare, builtin, fallback
   fact repr).

## 4. Non-goals

- Do not change row anchoring or `_initial_probe_bindings_for_row(...)`.
- Do not change prober witness/backtracking semantics.
- Do not change SchemaIR, `render_entity_repr(...)`, or DTO shapes.
- Do not alter adapter provenance converters.
- Do not make `%ENT` resolution fatal when identity facts are hidden; fallback
  remains allowed.

## 5. Current Context

- `prober.py:_probe_atom(...)` already receives `view_facts`.
- `_probe_atom(...)` currently calls `_bake_repr_text(form, schema_index)`.
- `_bake_repr_text(...)` calls `_repr_fact(...)`, which calls
  `_entity_repr_for_fact(...)`.
- `application.entity_view._recover_identity_from_predicates(...)` already
  resolves `idref_v1` tokens to identity mappings by reading identity predicate
  facts from `view_facts`.
- `schema_runtime.render_entity_repr(...)` already renders recovered identities
  with `Meta.repr` or the default label.

## 6. Proposed Shape

Update only `prober.py` unless implementation finds a compelling helper-boundary
reason to promote code.

1. Thread `view_facts` into repr baking:

   ```python
   repr_text = _bake_repr_text(form, schema_index, view_facts=view_facts)
   ```

2. Pass `view_facts` through `_repr_fact(...)` into `_entity_repr_for_fact(...)`.

3. Add a bare-idref string branch in `_entity_repr_for_fact(...)`:

   ```python
   if (
       schema_index is not None
       and isinstance(value, str)
       and value.startswith(ENTITY_REF_PREFIX)
   ):
       try:
           identity = _recover_identity_from_predicates(
               value,
               entity_type=entity_type,
               view_facts=view_facts,
               index=schema_index,
           )
           return schema_runtime.render_entity_repr(schema_index, entity_type, identity)
       except Exception:
           return _term_display(subject)
   ```

4. Import `ENTITY_REF_PREFIX` from `factgraph.core.protocol.tup_v1` instead of
   hard-coding `idref_v1:`.

5. Import `_recover_identity_from_predicates` from
   `factgraph.application.entity_view`. This private helper is acceptable for
   this targeted application-internal bugfix because it is the existing canonical
   idref-to-identity resolver. If implementation finds this import creates a
   cycle, promote a small shared helper instead and record the deviation.

## 7. Decisions

- **Entity type source**: use `PredicateInfo.owner_type` as the authoritative
  field-owner entity type for `%ENT`. The predicate metadata already identifies
  the subject entity type for schema field predicates.
- **Idref parsing**: do not parse entity type from idref as the primary path in
  this slice. Parsing may be used only as defensive fallback if implementation
  proves a concrete owner-type gap.
- **Fallback**: identity lookup or rendering failures must not crash explain.
  Fall back to the raw term display, matching the existing behavior.
- **Demo**: update `examples/explain_layer_demo.py` note after implementation so
  it no longer claims `%ENT` is an active gap.

## 8. Acceptance

- [ ] `%ENT` for a bound or enumerated entity-ref subject renders a friendly
  entity label from `Meta.repr` (for example, `User u-1`) instead of raw idref.
- [ ] Multi-entity native explanations remain row-anchored and each row's
  `%ENT` label matches that row's identity.
- [ ] Identity-unavailable fallback returns raw idref and does not raise.
- [ ] `%FLD`, Compare, Builtin, and fallback fact repr behavior remains
  unchanged.
- [ ] Existing prober monotonic / join / OR / row-anchoring tests remain green.
- [ ] `PYTHONPATH=src python examples/explain_layer_demo.py` renders `User u-1`
  in the relevant atom text.
- [ ] Explain cohort remains green.

## 9. Implementation Plan

1. Import `ENTITY_REF_PREFIX` and `_recover_identity_from_predicates` into
   `application/explain/prober.py`.
2. Thread `view_facts` from `_probe_atom(...)` to `_bake_repr_text(...)`,
   `_repr_fact(...)`, and `_entity_repr_for_fact(...)`.
3. Add the bare-idref `%ENT` recovery branch with graceful fallback.
4. Add tests for successful label recovery and identity-hidden fallback.
5. Update `examples/explain_layer_demo.py` gap note and run the demo.
6. Run focused prober / SDK explain tests and the explain cohort.

## 10. Docs To Update

- `examples/explain_layer_demo.py`: remove or revise the current "known repr
  polish gap" note.

## 11. Outcome / Deviations

To be filled after implementation.
