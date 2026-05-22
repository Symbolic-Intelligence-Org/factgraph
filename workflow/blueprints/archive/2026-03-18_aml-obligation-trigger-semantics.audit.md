# Task Blueprint Audit: AML Obligation Trigger Semantics

- Blueprint: [2026-03-18_aml-obligation-trigger-semantics.md](./2026-03-18_aml-obligation-trigger-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the next AML analysis slice after the case-review walkthrough confirmed that explain delivery is sufficient for single-rule-run review, leaving trigger semantics as the highest-value remaining pressure test. |
| 2026-03-18 | scoped | Scope frozen | Closed Q1/Q2/Q3 directly from archived `T1/U1` boundaries: pre-aggregated facts keep AML trigger inside current substrate, flag-style placeholder is sufficient, and uncertainty is not a first-round blocker. |
| 2026-03-18 | implemented | Adopted conclusion recorded | The blueprint now recommends `aml-trigger-walkthrough` as the next slice and defers aggregation, judgment contract, and weak-signal combination to future gap blueprints only if the walkthrough proves them necessary. |
| 2026-03-18 | archived | Analysis blueprint archived | This slice completed as a pure analysis pass with no code or module-doc changes. |

## Decision Notes

- 2026-03-18
  - Ordering rule: this slice must answer temporal sufficiency before judgment contract questions, and judgment contract questions before uncertainty, to avoid conflating three different kernel gaps.
- 2026-03-18
  - First-round target: the real question is not “can AML be fully modeled,” but “what is the minimal trigger shape that current substrate can or cannot already express.”
- 2026-03-18
  - Output of this slice should be an adopted next-slice recommendation, not an implementation attempt.
- 2026-03-18
  - Closure rule: because `T1 temporal` and `U1 uncertainty` scopes were already frozen by archived blueprints, Q1/Q2/Q3 did not require further open-ended analysis and were resolved directly into an adopted outcome.
