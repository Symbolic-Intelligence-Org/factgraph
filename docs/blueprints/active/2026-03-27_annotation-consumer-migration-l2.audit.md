# Task Blueprint Audit: Annotation Consumer Migration (L2)

- Blueprint: [2026-03-27_annotation-consumer-migration-l2.md](./2026-03-27_annotation-consumer-migration-l2.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | L2 child under multi-engine-semantic-delivery. 12 meta_rows consumers identified; minimal migration slice = audit export JSONL + static HTML engine semantics panel. |
| 2026-03-27 | draft | 3 P1/P2 fixes | (1) Implementation ownership corrected: package.py is the write-out entry, not audit/assertions.py. (2) Full 4-layer chain documented: package.py → reader.py → assertions.py → static_ui.py. (3) "不碰 souffle/package.py" removed from non-goals; replaced with "不改 Souffle provenance/rule export 语义，只扩 artifact set". |
| 2026-03-27 | scoped | Approved for implementation | No new blocking findings. assertion_annotations is optional artifact for backward compat with old packages. |
