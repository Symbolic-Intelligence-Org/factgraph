# Task Blueprint Audit: Certainty Propagation Prototype

- Blueprint: [2026-03-20_certainty-propagation-prototype.md](./2026-03-20_certainty-propagation-prototype.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | scoped | Blueprint created | Child 3 of certainty-weight-vocabulary. Scope B chosen: prototype-first, summary-second minimal verification of `confidence_kind` + `condition_weights` vocabulary end-to-end usability. Strict constraints: certainty lane only, additive summary block, no core set changes, winning branch only, no rule-level cap, no writeback to CandidateSet/SupportArtifact. |
| 2026-03-20 | implementing | Prototype landed | Added `core.annotation._certainty` with recursive condition-node walk, condition-key prefix extraction (`b{branch}.a{atom}` from tree carrier keys like `b0.a0:user:name` / `b0.a1:eq`), bottleneck aggregation, and repo-style annotation tests. |
| 2026-03-20 | implemented | Archived | Annotation docs and core architecture docs synced. Full suite passed (`194` tests). |

## Decision Notes

- 2026-03-20: Scope B (wider: derivation + summary extension entry) chosen over scope A (derivation only) because without a summary integration point, vocabulary validation remains incomplete — condition_weights would be consumed but never surfaced.
- 2026-03-20: `aggregate_certainty` uses bottleneck (minimum weighted impact) semantics, consistent with `_min_max.py` widest-path approach. Weighted sum / weighted mean deferred to salience/impact full implementation.
- 2026-03-20: `CertaintySummary` is an optional extension block alongside evidence tree summary, not a modification to the 12-field core set. This preserves the existing summary contract.
- 2026-03-20: Only `confidence_kind="certainty"` lane is implemented. `probability` and `none` lanes return `None` — no pseudo-mapping between lanes.
- 2026-03-20: The concrete tree carriers expose `pred_atom_key` / `step_key` with suffixes (`:pred_id` / `:kind`), while `condition_weights` use the prefix namespace `b{branch}.a{atom}`. The prototype therefore extracts the prefix before lookup instead of attempting a direct string match.
