# Task Blueprint Audit: FactGraph F4 completion

- Blueprint: [`2026-08-12_factgraph-f4-completion.md`](./2026-08-12_factgraph-f4-completion.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-12 | draft | Shared F4 completion blueprint created | Consolidates the already-authorized F4B2/F4B3/F4C tail to avoid three repetitive document lifecycles. |
| 2026-08-12 | scoped | Three-way read-only contract audit completed | Replay, detached-evidence and Policy-projection audits found no structural blocker and supplied explicit safety boundaries. |
| 2026-08-12 | implementing | User directed F4 continuation and fast completion | Implementation proceeds as three independently committed code slices with one combined external review. |

## Decision Notes

- The compressed lifecycle is deliberate: Q6A/Q6B are adopted, F4A/F4B1 were
  independently reviewed CLEAR, and three fresh read-only audits serve as the
  implementation preflight. This does not waive per-slice test or stop boundaries.
- F4B2 statically rejects estimated work above 100,000 before invoking native
  evaluation; captured byte/fact limits alone do not bound intermediate joins.
- Stable runtime pins are semantic-contract versions, not package/build claims.
  Old unpinned bundles remain usable only with an explicitly weaker verdict.
- F4B3 owns assertion-backed inner evidence; F4C owns only the readonly authored
  topology projection. Neither owns Scenario, UI or authorization semantics.
- Final `implemented` and archive transitions wait for the user-side combined
  independent review.
