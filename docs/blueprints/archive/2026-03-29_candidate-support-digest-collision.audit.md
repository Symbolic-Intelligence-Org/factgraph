# Task Blueprint Audit: Candidate Support Digest Collision Check

- Blueprint: [2026-03-29_candidate-support-digest-collision.md](./2026-03-29_candidate-support-digest-collision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | F-CORE-2 fix scope recorded. |
| 2026-03-29 | scoped | Scope frozen | Digest collision check in _remember_candidate_support only; no caller changes. |
| 2026-03-29 | implementing | runtime.py changes applied | Re-registration path now compares existing digest and raises on mismatch. |
| 2026-03-29 | implementing | Tests added | 3 tests in test_evidence_tree_explain_contracts.py cover first registration, idempotent same digest, and mismatch raise. |
| 2026-03-29 | implementing | Docs synced | 01_architecture.md F-CORE-2 marked RESOLVED. |
| 2026-03-29 | implemented | Regression passed | 590 tests, 0 failures. |

## Decision Notes

- Follow existing collision pattern from `_remember_support_artifact` and `_remember_provenance_envelope`.
- Raise `ValueError` on mismatch; idempotent on match (via `setdefault` for kind indices).
- All existing callers register each candidate_id exactly once, so no existing code will trigger the new raise.
