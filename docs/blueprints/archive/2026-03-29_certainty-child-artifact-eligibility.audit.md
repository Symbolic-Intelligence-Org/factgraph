# Task Blueprint Audit: Certainty Child Artifact Eligibility Guard

- Blueprint: [2026-03-29_certainty-child-artifact-eligibility.md](./2026-03-29_certainty-child-artifact-eligibility.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | F-CORE-3 fix scope recorded. |
| 2026-03-29 | scoped | Scope frozen | Null guard in check_certainty_artifact_eligibility only; no caller changes. |
| 2026-03-29 | implementing | Resolver guard applied | Missing child now returns ineligible before leaf-child check. |
| 2026-03-29 | implementing | Tests added | 3 tests in test_certainty_explain_contracts.py cover missing child, leaf child, and non-leaf child. |
| 2026-03-29 | implementing | Docs synced | 01_architecture.md F-CORE-3 marked RESOLVED. |
| 2026-03-29 | implemented | Regression passed | 593 tests, 0 failures. |

## Decision Notes

- Decompose compound `child is not None and len(child.rule_ref_edges) > 0` into two separate guards.
- Missing child (lookup returns None) → ineligible, matching the semantic intent that eligibility requires a verifiable leaf child.
- All existing callers pass `store._lookup_support_artifact` which returns None only for genuinely missing artifacts; no existing production path will change behavior because current tests always have child artifacts loaded.
