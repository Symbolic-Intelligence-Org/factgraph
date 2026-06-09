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

## D. Scope Review (2026-06-09)

Claude approved `draft → scoped` and independently checked three implementation
risk points:

1. `ENTITY_REF_PREFIX` is defined at `factgraph.core.protocol.tup_v1`.
2. `entity_view` does not directly import `application.explain.prober`, so the
   direct helper import has no known direct cycle.
3. `_bake_repr_text → _repr_fact → _entity_repr_for_fact` is a single call
   chain from `_probe_atom`, which already has `view_facts`.

Additional scope notes:

- If a transitive import cycle appears, promote the idref recovery helper into
  `schema_runtime` rather than creating an unrelated new module.
- Add a multi-entity `%ENT` regression, not only a single-entity case.

## E. Required Regression Tests

1. `%ENT` renders `Meta.repr` label for bare idref subject values.
2. Multi-entity row explanations remain row-specific and labels match each row.
3. Missing identity facts fall back without raising.
4. `%FLD`, compare, and builtin rendering remain unchanged.
5. Demo output no longer describes `%ENT` as a known gap and shows friendly
   entity labels.

## F. Implementation Outcome

Implemented in `50bf72a2`.

Codex implementation:

- Threaded `view_facts` from `_probe_atom(...)` into `_bake_repr_text(...)`,
  `_repr_fact(...)`, and `_entity_repr_for_fact(...)`.
- Added a bare-idref `%ENT` branch using `ENTITY_REF_PREFIX`,
  `_recover_identity_from_predicates(...)`, and
  `schema_runtime.render_entity_repr(...)`.
- Preserved graceful fallback to raw term display when identity facts are not
  visible or rendering fails.
- Added focused prober tests for visible-identity recovery and hidden-identity
  fallback.
- Upgraded the multi-entity SDK row-anchoring regression to assert friendly
  `%ENT` labels and absence of raw idrefs.
- Updated `examples/explain_layer_demo.py` so it documents and demonstrates the
  repaired `%ENT` behavior.

Independent gate record:

- Boundary check: only `prober.py`, focused tests, and the demo changed; row
  seed logic, DTOs, adapters, and `schema_runtime.py` were untouched.
- Direct helper import succeeded without an import cycle, so the promote-helper
  fallback was not used.
- Demo output includes `User u-1 is in region us` and `User u-1 is 30 years old`.
- Focused tests: `PYTHONPATH=src python -m unittest tests.application.explain.test_prober tests.sdk.test_rule_expr_evaluate`
  → `50 tests OK`.
- Explain cohort: `PYTHONPATH=src python -m unittest tests.application.protocol.test_explanation_render tests.test_audit_evidence_graph tests.application.explain.test_prober tests.test_souffle_evidence_graph tests.test_problog_evidence_graph tests.test_pyreason_provenance_v0 tests.test_pyreason_evidence_graph tests.test_problog_semantics_profile_migration tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_evaluate_result_dtos`
  → `127 tests OK`.

Verdict: PASS. No deviations.
