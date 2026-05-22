# Task Blueprint Audit: ProbLog RuleExt Branch Probabilities

- Blueprint: [2026-03-29_problog-rule-ext-branch-probabilities.md](./2026-03-29_problog-rule-ext-branch-probabilities.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | Reopens the post-closeout ProbLog probability debt as a new active task instead of editing archived closeout materials. |
| 2026-03-29 | scoped | Scope frozen | Confirmed `body_confidences` is per-branch weighting over normalized `where` OR branches. Adopt `ProbLogRuleExt.branch_probabilities: tuple[float, ...] | None`, preserve value range `(0, 1]`, and migrate via `engine_ext` before deleting shared-core `body_confidences`. |
| 2026-03-29 | scoped | Migration plan refined after audit | Added three explicit constraints: remove `engine_eval.py` blanket `engine_ext` rejection first, bridge legacy `body_confidences` in SDK evaluate rather than authoring payload serialization, and fail fast when explicit `engine_ext` conflicts with legacy branch probabilities. |
| 2026-03-29 | implementing | Typed ProbLog extension landed | Added `ProbLogRuleExt` and helper functions; `engine_eval.py` now validates `ProbLogRuleExt` instead of blanket-rejecting all `engine_ext`. |
| 2026-03-29 | implementing | Shared core routing cleaned up | SDK/runtime now bridge legacy `body_confidences` to `ProbLogRuleExt`; shared evaluate signatures and adapter export no longer consume `body_confidences`. |
| 2026-03-29 | implemented | Docs + targeted regression complete | Updated adapter/SDK/core/authoring docs and ran targeted ProbLog/runtime regression: `33 tests` passed. |
| 2026-03-29 | archived | Blueprint archived | Outcome filled and blueprint pair moved to `docs/blueprints/archive/`. |

## Decision Notes

- The replacement shape is branch-oriented, not scalar `probability: float`.
- `ProbLogRuleExt` is definition-time only; it does not replace fact-level probability, candidate output probability, or accepted semantic annotations.
- Migration order is fixed: add typed carrier -> lower compatibility inputs -> switch adapter consumption -> remove shared-core sidecar.
- Migration bridge point is the SDK evaluate path because `engine_ext` must not enter authoring payloads.
- During migration, explicit `engine_ext` is the source of truth; conflicting legacy `body_confidences` is an error, not a silent merge.
- Actual implementation also needed the same bridge in `service/runtime_v1.py`, because runtime derivation evaluation bypasses SDK and otherwise would have retained the deleted shared-core parameter.
