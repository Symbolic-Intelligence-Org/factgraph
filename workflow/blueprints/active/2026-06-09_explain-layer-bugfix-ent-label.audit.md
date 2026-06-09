# Audit Log: Explain v2 bugfix — `%ENT` entity label recovery

Paired with [2026-06-09_explain-layer-bugfix-ent-label.md](./2026-06-09_explain-layer-bugfix-ent-label.md).

---

## A. Root Cause Review (2026-06-09)

Claude's demo audit found that row anchoring is fixed, but `%ENT` field repr
still renders raw idref strings.

Codex source-read confirmation:

- `prober.py:_probe_atom(...)` already has `view_facts`.
- `_bake_repr_text(...)` currently receives only `schema_index`.
- `_entity_repr_for_fact(...)` supports `EntityRef` and mapping-with-identity,
  but not bare idref strings.
- `entity_view._recover_identity_from_predicates(...)` already recovers
  identity mappings from `view_facts` for an idref and entity type.
- `schema_runtime.render_entity_repr(...)` already renders the recovered
  identity through `Meta.repr` or default labels.

Verdict: root cause accepted.

## B. Locked Fix

- Thread `view_facts` through repr baking.
- For bare idref strings, use `_recover_identity_from_predicates(...)` and then
  `render_entity_repr(...)`.
- Use `ENTITY_REF_PREFIX`; do not hard-code `idref_v1:`.
- Use predicate `owner_type` as the primary entity type.
- Fall back to raw term display on lookup/render failure.

## C. Boundaries

- Do not touch row anchoring seed logic.
- Do not edit SchemaIR or DTO contracts.
- Do not alter adapter converters.
- Keep this as a presentation bugfix.

## D. Required Regression Tests

1. `%ENT` renders `Meta.repr` label for bare idref subject values.
2. Multi-entity row explanations remain row-specific and labels match each row.
3. Missing identity facts fall back without raising.
4. `%FLD`, compare, and builtin rendering remain unchanged.
5. Demo output no longer describes `%ENT` as a known gap and shows friendly
   entity labels.

## E. Implementation Outcome

Pending.
