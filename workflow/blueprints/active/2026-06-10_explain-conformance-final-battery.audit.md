# Audit Log: Explain Conformance Final — native battery, docs, and full matrix

Paired with [2026-06-10_explain-conformance-final-battery.md](./2026-06-10_explain-conformance-final-battery.md).

---

## A. Source Preflight (2026-06-10)

Codex read these anchors before drafting:

- Parent program:
  - `workflow/blueprints/active/2026-06-10_explain-conformance-rework.md`
  - `workflow/blueprints/active/2026-06-10_explain-conformance-rework.audit.md`
- Module docs:
  - `src/factgraph/application/explain/docs/README.md`
  - `src/factgraph/application/protocol/docs/README.md`
  - `docs/quickstart/evaluate_and_evidence.md`
- Test files:
  - `tests/application/explain/test_prober.py`
  - `tests/sdk/test_explain_conformance_native.py`
  - `tests/core/rules/test_aggregate_eval.py`
  - `tests/application/protocol/test_rule_aggregate.py`
  - adapter evidence tests for Souffle/ProbLog/PyReason

## B. Preflight Findings

1. All bugfix batches A/E/D/B/C are implemented and gate-passed.
2. `tests/application/explain/test_prober.py` now carries most native prober
   semantics and repr fidelity tests.
3. `tests/sdk/test_explain_conformance_native.py` carries row-level
   evaluate→explain conformance tests for anchoring and aggregates.
4. `application/explain/docs/README.md` is stale at slice-boundary level: it
   describes S3/S4 only and says later slices wire Explanation/adapters.
5. `application/protocol/docs/README.md` is mostly current but still contains
   at least one stale adapter-rich-wiring-deferred note.
6. `docs/quickstart/evaluate_and_evidence.md` has broad legacy flat-DAG
   sections. This is likely a separate quickstart rewrite unless a narrow
   patch is clearly sufficient.

## C. Battery Inventory Draft

Current conformance battery:

| Surface | Test anchor |
|---|---|
| G1 monotonic witness backtracking | `tests/application/explain/test_prober.py::NativeProberTests.test_monotonic_witness_backtracking_keeps_later_successful_env` |
| G2 head/body occurrence + joins | `test_structure_preserves_head_body_occurrences_and_join_materialization` |
| OR paths | `test_or_branches_are_exhaustive_paths` |
| True NotReached | `test_not_reached_is_only_unbound_dependency` |
| Batch D verdict cascade | `test_downstream_check_after_failed_upstream_can_hold_from_prefix_anchor`; `test_downstream_bind_atom_after_failed_upstream_is_not_reached_when_unbound` |
| Schema Fact repr / `%ENT` | `test_fact_repr_baking_uses_schema_template_and_entity_renderer`; `test_fact_repr_baking_recovers_bound_idref_identity_from_visible_facts` |
| idref fallback | `test_fact_repr_baking_falls_back_when_bound_idref_identity_is_not_visible` |
| Fact/Compare/Builtin fallback | `test_repr_baking_has_fallbacks_for_fact_compare_and_builtin` |
| Cross-type entity-ref `%FLD` | `test_fact_field_entity_ref_uses_shared_renderer_for_cross_type_label` |
| Compare entity refs | `test_compare_entity_refs_use_shared_renderer` |
| float64 display | `test_float64_hex_uses_display_text_in_fact_and_compare`; schema-runtime float64 identity tests |
| float64 misfire guard | `test_string_field_that_looks_like_float64_hex_is_not_decoded` |
| value-injection guard | `test_fact_repr_does_not_reinterpret_field_values_as_placeholders`; schema-runtime prefix/value-injection tests |
| Batch C NotAtom | `test_not_atom_single_inner_renders_friendly_negated_repr_and_preserves_verdict`; `test_not_atom_and_body_groups_inner_repr_without_raw_tuple_text`; `test_not_atom_or_of_and_body_renders_stable_grouped_repr` |
| Batch A projection/external/OR/join anchoring | `tests/sdk/test_explain_conformance_native.py::NativeExplainConformanceTests` |
| Batch E aggregate evaluate→explain | `tests/sdk/test_explain_conformance_native.py::NativeAggregateExplainConformanceTests` |
| Aggregate substrate | `tests/core/rules/test_aggregate_eval.py`; `tests/application/protocol/test_rule_aggregate.py` |
| Adapter rich evidence | `tests/test_souffle_evidence_graph.py`; `tests/test_problog_provenance_v0.py`; `tests/test_pyreason_provenance_v0.py` |

Coverage review:

- No missing high-risk cell found for the conformance audit scope.
- `docs/quickstart/evaluate_and_evidence.md` still contains broad legacy
  flat-DAG content. This is documentation debt, not a code conformance gap; it
  should be rewritten as a separate quickstart docs slice.

## D. Matrix Commands

Baseline before docs:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.explain.test_prober \
  tests.sdk.test_explain_conformance_native \
  tests.test_application_schema_runtime \
  tests.application.protocol.test_evaluate_result_digests \
  tests.test_souffle_evidence_graph \
  tests.test_problog_provenance_v0 \
  tests.test_pyreason_provenance_v0 \
  tests.sdk.test_rule_expr_evaluate \
  tests.core.rules.test_aggregate_eval \
  tests.application.protocol.test_rule_aggregate \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.sdk.test_evaluate_result_exports
```

Result: `144 OK`.

Final matrix after docs:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.explain.test_prober \
  tests.sdk.test_explain_conformance_native \
  tests.test_application_schema_runtime \
  tests.application.protocol.test_evaluate_result_digests \
  tests.test_souffle_evidence_graph \
  tests.test_problog_provenance_v0 \
  tests.test_pyreason_provenance_v0 \
  tests.sdk.test_rule_expr_evaluate \
  tests.core.rules.test_aggregate_eval \
  tests.application.protocol.test_rule_aggregate \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.sdk.test_evaluate_result_exports
```

Result: `144 OK`.

Demo:

```bash
PYTHONPATH=src python examples/explain_layer_demo.py
```

Result: PASS. The demo renders row-anchored paths-model evidence with friendly
labels:

- `User u-1 is in region us`
- `User u-1 is 30 years old`
- `30 >= 18`

## E. Implementation Outcome

Ready for reviewer gate.

Implementation notes:

- Rewrote `application/explain/docs/README.md` to describe final current
  behavior after S3-S6 and conformance batches A/E/D/B/C.
- Patched `application/protocol/docs/README.md` stale adapter-deferred text and
  stale adapter test module names.
- Recorded a native conformance battery inventory in this audit.
- Classified `docs/quickstart/evaluate_and_evidence.md` as follow-up: it still
  contains broad legacy flat-DAG content and should be rewritten as a dedicated
  quickstart docs slice rather than patched piecemeal here.

No runtime source behavior was changed in this final cleanup.
