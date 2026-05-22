# Task Blueprint Audit: Core + Audit Batch Fix

- Blueprint: [2026-03-29_core-audit-batch.md](./2026-03-29_core-audit-batch.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | 5 findings batched: F-CORE-4/5 + F-EG-1/3/4 |
| 2026-03-29 | scoped | Scope frozen | F-EG-2 excluded (separate blueprint next round) |
| 2026-03-29 | implemented | All fixes applied | 596 tests green; 3 new tests added |

## Decision Notes

- F-CORE-5: docs-only — `(0,1]` is intentional design (zero-probability facts should not exist in ledger)
- F-CORE-4: inline comments only, no control flow changes
- F-EG-1: DFS cycle detection in __post_init__, raise ValueError
- F-EG-3: raise AuditReadError on duplicate, not warning (matches existing error patterns)
- F-EG-4: narrow to (ValueError, KeyError, TypeError) — covers the known failure modes from souffle_proof_tree_from_dict
