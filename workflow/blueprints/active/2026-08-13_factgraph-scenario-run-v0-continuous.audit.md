# Task Blueprint Audit: FactGraph ScenarioRun v0 continuous delivery

- Blueprint: [`2026-08-13_factgraph-scenario-run-v0-continuous.md`](./2026-08-13_factgraph-scenario-run-v0-continuous.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Scope reconstructed from Q7/Q11/F4 | Existing Scenario fast path is retained; it is not promoted by implication. |
| 2026-08-13 | scoped | User authorized project-level continuous delivery | One bounded ScenarioRun lifecycle is allowed; non-goals remain hard stops. |
| 2026-08-13 | implementing | Core receipt-capture seam selected | Capture stays ephemeral and cannot write Store support state. |
| 2026-08-13 | implementing | ScenarioRun capture boundary hardened | Replaced provisional raw inner capture exposure with an exact Scenario-only frame; generic F4 decode rejects it, while the private source-aware adapter relabels every witness before detached evidence playback. |
| 2026-08-13 | implementing | Review repairs applied | Fixed semantic-diff canonicalization, source-metadata override admission, exact baseline/effective delta inventory, and `diff()` seal revalidation. A static type check then caught `FieldPath` shadowing by `dataclasses.field`; the DTO now aliases the helper and mypy is clean. |
| 2026-08-13 | implemented | Continuous delivery verification complete | Focused ScenarioRun, concentrated Query/Scenario/F4, and integrated application+SDK suites passed; ruff, mypy and `git diff --check` passed. Final independent review requested against this exact state. |
| 2026-08-13 | implemented | Final review test-gap repair | Added a permanent interleaving regression: a view mutation after baseline capture must fail closed before effective execution. Clarified the decision wording to one baseline plus one effective evaluation. |
| 2026-08-13 | implemented | Independent final review: CLEAR | Re-executed the stale-window guard and focused ScenarioRun cohort (`79 passed, 37 subtests passed`); no P0/P1 blocker. Verified exports, Scenario frame, source labels and documentation. |

## Decision Notes

- Avoid treating two ordinary `EvaluationRunBundleV0` values as the public
  Scenario contract.  Their capture primitives are reused privately behind a
  Scenario-specific seal and source relabeling adapter.
- The implementation is deliberately compressed under the user's direction;
  checks are concentrated at semantic boundaries rather than repeated per file.
- The ScenarioRun outer-size limit accounts for two maximum F4 captures after
  URL-safe base64 expansion plus bounded Scenario metadata. It is an encoded
  payload ceiling, not a promise that arbitrary large source data is suitable
  for caller custody.
