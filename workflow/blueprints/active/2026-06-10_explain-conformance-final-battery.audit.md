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

To be filled during implementation with exact test names.

Required surfaces:

- G1 monotonic witness backtracking.
- G2 head/body occurrence and join shape.
- Batch A inline/projection/external/OR/join row anchoring.
- Batch D downstream verdict cascade and true NotReached.
- Batch B entity-ref, float64, prefix collision, value injection, and unbound
  rendering.
- Batch C NotAtom `negated=True` and friendly repr.
- Batch E aggregate evaluate→explain.
- Adapter rich evidence for Souffle/ProbLog/PyReason.

## D. Matrix Commands

To be filled during implementation.

## E. Implementation Outcome

To be filled after final cleanup and gate.
