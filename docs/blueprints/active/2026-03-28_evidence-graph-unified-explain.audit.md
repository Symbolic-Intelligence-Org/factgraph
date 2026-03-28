# Blueprint Audit: Evidence Graph — Unified Explain Surface

- Blueprint: [2026-03-28_evidence-graph-unified-explain.md](./2026-03-28_evidence-graph-unified-explain.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Unified EvidenceGraph abstraction for traceability/explainability across all engines. Wrap-don't-replace design. 4 open questions for discussion. |
| 2026-03-28 | scoped | 5 decisions frozen | D-EG1: audit/ not core/. D-EG2: CSS grid timeline. D-EG3: Souffle from SouffleProofTreeV0. D-EG4: no JSON serialization v1. D-EG5: candidate evidence page not assertion page. Integration point corrected. Naming principle: "evidence graph, not evidence tree". |
| 2026-03-28 | scoped | Step 1 data model refined for implementation | `provenance_kind` renamed to `support_kind` to align with `CandidateSet`. `layout_hint` narrowed to `tree | timeline`. `rule_fire` and `dag` deferred from v1. `MappingProxyType` shallow freeze and duplicate id validation added. |
| 2026-03-28 | scoped | Step 2 PyReason converter implemented | `pyreason_trace_to_evidence_graph(...)` now consumes `trace + candidate_payload`, roots on the latest matching candidate event, emits `layout_hint="timeline"`, and only materializes intra-fact `updates` edges. `clause_groundings` stay in `engine_meta`; cross-fact causal edge synthesis remains deferred. |
| 2026-03-28 | scoped | Step 3 ProbLog converter implemented | `problog_trace_to_evidence_graph(...)` now consumes `trace + candidate_payload`, normalizes the trace into a call-frame tree, roots on the best matching answer/call frame, emits `layout_hint="tree"`, and keeps `result/complete/fail/location` in `engine_meta`. Synthetic answer/query anchoring is best-effort and allows payload-term subset matching when query vars include body-only vars. |
| 2026-03-28 | scoped | Step 4 standalone renderer implemented | `render_evidence_graph_html(...)` now dispatches on `layout_hint` and renders tree/timeline HTML fragments in `audit/evidence_graph.py`. Tree layout walks incoming child edges from `root_node_id`; timeline layout uses CSS grid with timestep columns and component rows. Static UI integration is still deferred, but the insertion seam is fixed at `_render_candidate_evidence_page(...).provenance_block`. |
