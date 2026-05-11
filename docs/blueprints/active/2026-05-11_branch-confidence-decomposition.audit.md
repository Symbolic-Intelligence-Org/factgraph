# Task Blueprint Audit: Branch Confidence Decomposition

- Blueprint: [2026-05-11_branch-confidence-decomposition.md](./2026-05-11_branch-confidence-decomposition.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Blueprint created | Track 3 / A2 opened after narrow source audit. Scope drafts public `Body` -> `Branch` rename, `Body.confidence` removal, public `body_confidences` rejection, and temporary internal ProbLog bridge preservation. |
| 2026-05-11 | scoped | Scope frozen | Locked D1-D8: remove `Body.confidence`; rename public `Body` to `Branch` without alias; rename SDK DSL file `body.py` to `branch.py`; keep `Branch` engine-parameter-free; retain internal `body_confidences` only as a ProbLog bridge; reject public authoring/service `body_confidences`; use `ProbLogRuleExt.branch_probabilities` as the temporary public fallback; enforce `Body` absence from `kernel.sdk`. |
| 2026-05-11 | implementing | G1 red baseline tests added | Added `test_branch_confidence_decomposition.py` covering D1-D8. Targeted run `env PYTHONPATH=src python -m unittest kernel.tests.test_branch_confidence_decomposition` fails as expected with 7 failures: `Branch` is not exported yet, `Body` is still exported, `body.py` still exists, `Branch(..., confidence=...)` / engine kwargs cannot be tested until `Branch` exists, authoring `body_confidences` is still accepted, and service top-level / derivation-level `body_confidences` are still accepted. Two guard tests already pass: internal `body_confidences` IR remains present and `ProbLogRuleExt.branch_probabilities` remains available. |
| 2026-05-11 | implementing | G2 implementation landed | Renamed SDK DSL `body.py` to `branch.py`, replaced public `Body` with `Branch`, removed branch-level `confidence`, rejected public authoring/service `body_confidences`, preserved compiled/internal `body_confidences` and `legacy_body_confidences` for the ProbLog bridge, and migrated touched domain tests to call-site engine / `Branch` syntax. Targeted A2 + ProbLog + SDK invariant + A1 regression suite passes 72/72; import-order-compatible artifact/evidence domain suite passes 50/50. |
| 2026-05-11 | implementing | G3 docs sync landed | Updated SDK user guide, rules docs, API surface, ProbLog adapter docs, authoring docs, and core architecture docs from public `Body` / `Body.confidence` / authoring `body_confidences` syntax to `Branch` structure plus transitional `ProbLogRuleExt.branch_probabilities`. Release-facing stale syntax grep now has no public `Body` hits and keeps `body_confidences` only as internal-bridge or rejection text. |

## Decision Notes

- 2026-05-11: A2 expands from only `Body.confidence` removal to `Body` -> `Branch` rename because the wrapper represents branch structure, not a whole rule body; this also aligns with future `Path.branch(...)` rule projection terminology.
- 2026-05-11: Narrow audit found `body_confidences` is generic in IR / authoring / service plumbing but has only one real consumer: the ProbLog bridge named `legacy_body_confidences`.
- 2026-05-11: A2 intentionally leaves `ProbLogRuleExt.branch_probabilities` as the temporary public fallback. A3 owns `engine_ext`; Phase B/C owns SemanticsProfile / ProbLog projection.
- 2026-05-11: Scope-freeze turns the absence of `Body` into a first-class invariant, following the ReadPolicy `ViewSpec` and A1 `Derivation.mode` hard-cut precedent.
- 2026-05-11: G1 red baseline intentionally includes passing guards for D4/D7 alongside failing public-surface tests, matching A1's pattern of preserving internal bridges while removing public definition-time shortcuts.
- 2026-05-11: G2 also repaired domain tests that still carried inner `derivation.mode` from before A1; native cases now omit the inner key and Souffle cases use top-level `engine`.
