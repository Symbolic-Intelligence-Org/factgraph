# Task Blueprint Audit: Check Operation

- Blueprint: [2026-05-03_check-operation.md](./2026-05-03_check-operation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-03 | draft | Blueprint created | Created from resolved conceptual + interaction topic after blind validation. Step 0 must freeze Protocol Contract before scoped implementation. |
| 2026-05-03 | draft | Acceptance hardening after blueprint audit | Added explicit anti-regression gates for side-channel request purity, engine-native evidence preservation, invalid binding shape, drift-prevention review, and no in-Check caching. |

## Decision Notes

- 2026-05-03: Blueprint starts in `draft` because concrete DTO / error / engine payload / test contract is intentionally not frozen by the reference topic doc.
- 2026-05-03: Application-first boundary is mandatory. Any SDK surface is optional and delegate-only.
- 2026-05-03: Step 0 is a gate, not optional planning; no multi-file implementation before Step 0 decisions are recorded here.
- 2026-05-03: Step 0 must map topic doc §7.1-§7.6 drift traps to explicit prevention/detection decisions before status can move to `scoped`.
- 2026-05-03: RuleRef/evidence caching is out of scope for Check MVP. If future caching is introduced, it must live behind registry/runtime authority, not inside Check request/result objects.
