# Task Blueprint Audit: Provenance Coverage and Bridge

- Blueprint: [2026-03-23_provenance-coverage-and-bridge.md](./2026-03-23_provenance-coverage-and-bridge.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-23 | scoped | Sub-blueprint created | Three-step scope: provenance statuses artifact, candidate page bridge, package-level query summary. |
| 2026-03-26 | implementing | Step 1 completed | Added `audit/provenance_statuses.jsonl` materialization, reader/query loading, and candidate-level provenance status lookup without changing service endpoints or core contracts. |
| 2026-03-26 | implementing | Step 2 completed | Candidate evidence pages now render provenance availability badges, truncation warnings, and a visual bridge note between evidence tree and engine provenance. |
| 2026-03-26 | implementing | Step 3 completed | `AuditQuery` now summarizes provenance coverage over unique `candidate_id`s, and the audit landing page renders provenance coverage / truncated proof metric cards when status rows are present. |
| 2026-03-26 | implementing | Tests and docs completed | Added regression coverage for status artifacts, coverage summary, old-package fallback, candidate badge rendering, and landing-page coverage metrics. Updated audit and service docs to document `provenance_statuses.jsonl` and coverage semantics. |
| 2026-03-26 | implemented | Archived | Child blueprint completed and moved to `docs/blueprints/archive/`; provenance consumer surface now covers availability, truncation, and package-level coverage in addition to raw proof-tree rendering. |
