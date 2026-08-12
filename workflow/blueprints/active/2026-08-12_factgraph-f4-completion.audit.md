# Task Blueprint Audit: FactGraph F4 completion

- Blueprint: [`2026-08-12_factgraph-f4-completion.md`](./2026-08-12_factgraph-f4-completion.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-12 | draft | Shared F4 completion blueprint created | Consolidates the already-authorized F4B2/F4B3/F4C tail to avoid three repetitive document lifecycles. |
| 2026-08-12 | scoped | Three-way read-only contract audit completed | Replay, detached-evidence and Policy-projection audits found no structural blocker and supplied explicit safety boundaries. |
| 2026-08-12 | implementing | User directed F4 continuation and fast completion | Implementation proceeds as three independently committed code slices with one combined external review. |
| 2026-08-13 | implementing | F4B2 independent red-team found a resource-gate undercount | The preflight was tightened before F4B2 acceptance: it now charges primary bindings plus captured-row receipt reconstruction against a saturating relation-scan bound. A high-cardinality, projection-collapsing regression must reject before evaluator entry. |
| 2026-08-13 | implementing | F4B2 code stop amended from 650 to 750 production additions | This is a narrow consequence of the required DoS correction, not a new feature surface; final review must separately verify that no runtime/API scope expanded. |

## Decision Notes

- The compressed lifecycle is deliberate: Q6A/Q6B are adopted, F4A/F4B1 were
  independently reviewed CLEAR, and three fresh read-only audits serve as the
  implementation preflight. This does not waive per-slice test or stop boundaries.
- F4B2 statically rejects estimated work above 100,000 before invoking native
  evaluation. The bound includes raw-binding enumeration and per-binding/captured-row
  receipt reconstruction over witness relations; captured byte/fact limits alone do
  not bound intermediate joins or support rebuilding.
- Stable runtime pins are semantic-contract versions, not package/build claims.
  Old unpinned bundles remain usable only with an explicitly weaker verdict.
- F4B3 owns assertion-backed inner evidence; F4C owns only the readonly authored
  topology projection. Neither owns Scenario, UI or authorization semantics.
- Final `implemented` and archive transitions wait for the user-side combined
  independent review.
