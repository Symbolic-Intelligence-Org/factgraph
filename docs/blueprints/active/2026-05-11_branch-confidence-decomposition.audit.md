# Task Blueprint Audit: Branch Confidence Decomposition

- Blueprint: [2026-05-11_branch-confidence-decomposition.md](./2026-05-11_branch-confidence-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A2 opened after narrow source audit. Scope drafts public `Body` -> `Branch` rename, `Body.confidence` removal, public `body_confidences` rejection, and temporary internal ProbLog bridge preservation. |

## Decision Notes

- 2026-05-11: A2 expands from only `Body.confidence` removal to `Body` -> `Branch` rename because the wrapper represents branch structure, not a whole rule body; this also aligns with future `Path.branch(...)` rule projection terminology.
- 2026-05-11: Narrow audit found `body_confidences` is generic in IR / authoring / service plumbing but has only one real consumer: the ProbLog bridge named `legacy_body_confidences`.
- 2026-05-11: A2 intentionally leaves `ProbLogRuleExt.branch_probabilities` as the temporary public fallback. A3 owns `engine_ext`; Phase B/C owns SemanticsProfile / ProbLog projection.
