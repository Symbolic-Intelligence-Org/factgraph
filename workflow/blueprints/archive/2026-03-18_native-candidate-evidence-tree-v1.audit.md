# Task Blueprint Audit: Native Candidate Evidence Tree V1

- Blueprint: [2026-03-18_native-candidate-evidence-tree-v1.md](./2026-03-18_native-candidate-evidence-tree-v1.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the first implementation-facing evidence-tree slice after aligning the runtime-traceability parent blueprint. Scope is intentionally narrowed to native candidate trees over existing `SupportArtifact` rather than full Rainbird-style parity. |
| 2026-03-18 | scoped | Scope freeze | Narrowed V1 assertion leaf shape to `asrt_id/pred_id/e_ref/claim_args` only, explicitly leaving revocation and meta fields on the existing assertion-detail surface; kept the slice native-only, candidate-only, and tree-not-graph. |
| 2026-03-18 | implemented | Runtime / audit / static tree surfaces added | Added a shared native candidate evidence-tree builder, runtime `explain-tree`, audit candidate tree reconstruction, and minimal static candidate tree pages without changing existing flat explain contracts. |
| 2026-03-18 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 76 tests after adding candidate tree coverage, degraded native-only guardrails, and static tree assertions. |
| 2026-03-18 | archived | Blueprint archived after docs alignment | Updated core/service/audit module docs to record candidate evidence tree v1 as current implementation truth, then archived this task blueprint. |

## Decision Notes

- 2026-03-18: This slice starts from `candidate`, not `rule_run`, because native candidate explain already has a stable entry chain: `candidate_id -> support_digest -> SupportArtifact`.
- 2026-03-18: The first round is explicitly tree-oriented, not graph-oriented.
- 2026-03-18: Engine witness parity, salience breakdown, snippet/span provenance, and source-linkage remain deferred unless the v1 tree slice exposes a concrete blocker.
- 2026-03-18: `assertion_fact` leaves must not become embedded full assertion dumps; V1 only carries `asrt_id`, `pred_id`, `e_ref`, and `claim_args`, with deeper assertion state still owned by assertion-detail drill-down.
