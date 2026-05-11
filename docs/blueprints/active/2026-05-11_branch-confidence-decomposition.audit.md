# Task Blueprint Audit: Branch Confidence Decomposition

- Blueprint: [2026-05-11_branch-confidence-decomposition.md](./2026-05-11_branch-confidence-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A2 opened after narrow source audit. Scope drafts public `Body` -> `Branch` rename, `Body.confidence` removal, public `body_confidences` rejection, and temporary internal ProbLog bridge preservation. |
| 2026-05-11 | scoped | Scope frozen | Locked D1-D8: remove `Body.confidence`; rename public `Body` to `Branch` without alias; rename SDK DSL file `body.py` to `branch.py`; keep `Branch` engine-parameter-free; retain internal `body_confidences` only as a ProbLog bridge; reject public authoring/service `body_confidences`; use `ProbLogRuleExt.branch_probabilities` as the temporary public fallback; enforce `Body` absence from `kernel.sdk`. |

## Decision Notes

- 2026-05-11: A2 expands from only `Body.confidence` removal to `Body` -> `Branch` rename because the wrapper represents branch structure, not a whole rule body; this also aligns with future `Path.branch(...)` rule projection terminology.
- 2026-05-11: Narrow audit found `body_confidences` is generic in IR / authoring / service plumbing but has only one real consumer: the ProbLog bridge named `legacy_body_confidences`.
- 2026-05-11: A2 intentionally leaves `ProbLogRuleExt.branch_probabilities` as the temporary public fallback. A3 owns `engine_ext`; Phase B/C owns SemanticsProfile / ProbLog projection.
- 2026-05-11: Scope-freeze turns the absence of `Body` into a first-class invariant, following the ReadPolicy `ViewSpec` and A1 `Derivation.mode` hard-cut precedent.
