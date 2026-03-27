# Task Blueprint Audit: ProbLog Semantic Annotation Parity L4

- Blueprint: [2026-03-27_problog-semantic-annotation-parity-l4.md](./2026-03-27_problog-semantic-annotation-parity-l4.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | scoped | Blueprint created | L4 narrowed to semantic annotation parity: write `problog/semantic/probability` into Annotation Store and reuse existing L2 audit/static consumers. Explicitly excludes session API, engine_options, body_confidences debt cleanup, and fake provenance. |
| 2026-03-27 | implemented | L4 delivered and archived | Added ProbLog pending-annotation caching during `evaluate_problog(...)`, introduced `persist_problog_annotations(...)` for post-accept binding to `asrt_id`, updated adapter docs, added focused L4 tests, and verified `499` total tests green. |

## Decision Notes

- Current confirmed write path: ProbLog probability already enters `CandidateSet.confidence` in `parse_problog_output(...)`, and core accept already mirrors it to `meta.confidence`; the missing parity piece is engine-native annotation persistence.
- Implementation chose a dedicated `store._problog_pending_annotations` side channel instead of reusing PyReason's `_engine_pending_annotations`, because ProbLog needs candidate-scoped binding (`candidate_id -> asrt_id`) after shared accept.
- Provenance remains a separate spike/decision concern until a real ProbLog decomposition carrier is verified.
