# Task Blueprint Audit: Rule / Query / Inference head semantics design note

- Blueprint: [2026-05-12_rule-query-inference-head-semantics.md](./2026-05-12_rule-query-inference-head-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Scope limited to recording a future optimization direction as a non-authoritative reference note. |
| 2026-05-12 | scoped | Scope frozen | No SDK behavior, module docs, evidence APIs, or public names are changed before release. |
| 2026-05-12 | implemented | Reference note added | Added the design-point note and index links; archived immediately as a documentation-only capture task. |

## Decision Notes

- 2026-05-12: The design discussion is treated as future redesign input, not a
  release-blocking implementation task.
- 2026-05-12: The key design collision to preserve is that `Query.head`,
  `Rule.select`, and `Inference.head` are all head-like user surfaces but mean
  projection, relation signature, and conclusion respectively.
- 2026-05-12: Current evidence tree behavior remains documented as candidate /
  inference-result centered. Any future evidence facade or unified proof-result
  object needs a separate active blueprint.
