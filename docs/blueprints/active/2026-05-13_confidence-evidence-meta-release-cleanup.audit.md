# Task Blueprint Audit: Confidence / Evidence Meta Release Cleanup

- Blueprint: [2026-05-13_confidence-evidence-meta-release-cleanup.md](./2026-05-13_confidence-evidence-meta-release-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | scoped | Blueprint created and scope frozen | Release cleanup focuses on cutting default public/persisted confidence propagation while preserving internal compatibility carriers. |
| 2026-05-13 | scoped | Scope clarification | Added behavior matrix, parse-compatible internal-carrier contract, duplicate-detection behavior change, adapter fallback removal boundary, and G1 sizing note. |
| 2026-05-13 | scoped | G1 red baseline | Added 11-test cleanup baseline: 7 forward failures + 4 guards/pass covering accept meta, write-protocol annotation projection, runtime candidate DTO compatibility, ProbLog/PyReason fallback boundaries, evidence tree display, duplicate detection, and internal carrier preservation. Prior lifecycle/schema preservation stack remains 217/217 OK. |
| 2026-05-13 | scoped | G2 implementation | Cut default candidate/generic confidence propagation across accept, write protocol, runtime candidate DTOs, ProbLog fallback, PyReason templates, and candidate evidence trees; migrated stale confidence tests and verified full kernel discovery 2198 OK / 1 skipped. |
| 2026-05-13 | scoped | G3 docs sync | Synchronized core, SDK, adapter, and service docs with the cleanup contract: legacy candidate confidence remains an internal carrier, generic `meta.confidence` is not shared semantic input, service DTOs omit legacy fields by default, and adapter-native probability/bound lanes remain canonical. |

## Decision Notes

- 2026-05-13: Chose the minimal release cleanup rather than a full confidence
  model redesign. `CandidateSet` fields remain internal/legacy for now.
- 2026-05-13: Old `confidence` / `confidence_kind` payload values remain
  parse-compatible internal carriers only; they no longer define default
  assertion meta, shared annotation, adapter export, evidence tree, or static
  UI semantics.
