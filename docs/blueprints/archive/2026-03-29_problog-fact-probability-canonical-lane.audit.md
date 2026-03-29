# Task Blueprint Audit: ProbLog Fact Probability Canonical Lane

- Blueprint: [2026-03-29_problog-fact-probability-canonical-lane.md](./2026-03-29_problog-fact-probability-canonical-lane.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | New follow-up slice after branch closeout: fact-level ProbLog probability still reads shared `meta.confidence` instead of the canonical annotation lane. |
| 2026-03-29 | scoped | Scope frozen | Export will prefer `problog/semantic/probability`, keep `meta.confidence` as legacy fallback, and preserve deterministic default `1.0`. No new write API is introduced in this slice. |
| 2026-03-29 | implementing | Canonical read priority implemented | `_claim_probability(...)` now reads `problog/semantic/probability` first and only falls back to `meta.confidence` when the canonical annotation is absent. |
| 2026-03-29 | implemented | Tests and docs synced | Added focused export tests and updated ProbLog / SDK docs to describe canonical-vs-legacy probability lanes. |
| 2026-03-29 | archived | Blueprint archived | Outcome filled and blueprint pair moved to `docs/blueprints/archive/`. |

## Decision Notes

- This slice fixes read priority only; it does not redesign write protocol.
- Canonical ProbLog semantic annotation is the source of truth when present.
- Legacy `meta.confidence` remains compatibility-only.
- Malformed canonical annotation data should fail fast instead of silently falling back to legacy meta.
