# Task Blueprint Audit: Examples SDK Schema Cleanup

- Blueprint: [2026-03-28_examples-sdk-schema-cleanup.md](./2026-03-28_examples-sdk-schema-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Captured examples cleanup scope and required compatibility fix. |
| 2026-03-28 | scoped | Scope frozen for implementation | Includes relationship owner_type compatibility and example/documentation cleanup. |

## Decision Notes

- 2026-03-28: Relationship `owner_type` cleanup is treated as a minimal compatibility fix because example-level schema mutation is not acceptable as the long-term surface.
- 2026-03-28: ECSS preset helpers stay in place for backward compatibility; demos move to explicit `Entity` declarations instead of raw predicate injection.
- 2026-03-28: `examples/example_full.py` was pulled into scope after audit found deprecated `functional` cardinality, `pred_id` override, and `Meta.is_record` usage that no longer matches current SDK docs.
