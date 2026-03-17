# Task Blueprint Audit: Candidate ID Support Backref

- Blueprint: [2026-03-17_candidate-id-support-backref.md](./2026-03-17_candidate-id-support-backref.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a narrow follow-up blueprint after the first durable export slice was completed, to add an in-memory `candidate_id -> support_digest` backref without expanding into generic explain protocols or durable indexing. |
| 2026-03-17 | scoped | Scope and collision semantics locked | Confirmed the slice stays on `candidate_id`, writes at evaluate time from `_evaluate.py`, and uses first-write-wins semantics for any accidental duplicate registrations. |
| 2026-03-17 | implemented | Candidate backref index landed | Added `Store`-side `candidate_id -> support_digest` indexing plus native evaluate-path registration and a public `get_candidate_support_digest(...)` helper. |
| 2026-03-17 | validated | Compile + focused unittest passed | `compileall` passed for touched store/test modules; focused unittest verified native backref lookup, entity/fact sharing through candidate-level support, missing-id `None`, and compatibility candidates staying out of the index. |

## Decision Notes

- 2026-03-17: The first backref slice should index by `candidate_id`, not `candidate_key`; cross-run `candidate_key` semantics are currently too ambiguous for a single-value mapping.
- 2026-03-17: Backrefs should be written at evaluate time, not accept time, so `candidate_id` can be used for explain lookup before any accept flow occurs.
- 2026-03-17: The write point should live in `_evaluate.py` outside the builders, because only that layer sees `store`, `row.support_digest`, and the finalized `candidate.candidate_id` together.
- 2026-03-17: Entity-path candidates produced from the same row should all map to the same `support_digest`.
- 2026-03-17: The public API of this slice should stop at `get_candidate_support_digest(candidate_id)`; convenience APIs that jump directly to explain dict are deferred.
- 2026-03-17: Duplicate `candidate_id` registrations should be handled with first-write-wins semantics; index write paths should not introduce last-write overwrite behavior or collision exceptions in the first slice.
- 2026-03-17: Although the write point remains in `_evaluate.py` outside the builders, the final implementation should register backrefs from the finished candidate objects themselves, provided they carry real native `support_kind/support_digest`, rather than preserving an unnecessary binding-reconstruction layer.
