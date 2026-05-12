# Task Blueprint Audit: Confidence / Evidence Meta Release Cleanup

- Blueprint: [2026-05-13_confidence-evidence-meta-release-cleanup.md](./2026-05-13_confidence-evidence-meta-release-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | scoped | Blueprint created and scope frozen | Release cleanup focuses on cutting default public/persisted confidence propagation while preserving internal compatibility carriers. |
| 2026-05-13 | scoped | Scope clarification | Added behavior matrix, parse-compatible internal-carrier contract, duplicate-detection behavior change, adapter fallback removal boundary, and G1 sizing note. |

## Decision Notes

- 2026-05-13: Chose the minimal release cleanup rather than a full confidence
  model redesign. `CandidateSet` fields remain internal/legacy for now.
- 2026-05-13: Old `confidence` / `confidence_kind` payload values remain
  parse-compatible internal carriers only; they no longer define default
  assertion meta, shared annotation, adapter export, evidence tree, or static
  UI semantics.
