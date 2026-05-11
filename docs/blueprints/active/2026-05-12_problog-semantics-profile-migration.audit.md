# Task Blueprint Audit: ProbLog SemanticsProfile Migration

- Blueprint: [2026-05-12_problog-semantics-profile-migration.md](./2026-05-12_problog-semantics-profile-migration.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Track 3 / C opened after B shipped `SemanticsProfile` scaffolding. Source audit found ProbLog has a concentrated adapter-local bridge: `legacy_body_confidences` and `ProbLogRuleExt.branch_probabilities` already normalize through `resolve_problog_engine_ext(...)`, while SDK/service profile kwargs remain rejected by B. Draft frames C around profile-to-ProbLog rule projection consumption and leaves runtime call-site scope for G0. |

## Decision Notes

- 2026-05-12: C is the first adapter-consumption slice after B. It must distinguish adapter consumption from public runtime call-site design; E still owns SDK/service profile acceptance unless C explicitly expands.
- 2026-05-12: The natural adapter-local target remains `ProbLogRuleExt`. C should normalize `SemanticsProfile.rule_projection.problog` into that internal type rather than making the exporter consume profile dicts.
- 2026-05-12: Legacy bridges cannot be removed at draft time because E has not introduced a durable profile call-site yet. `legacy_body_confidences` and `ProbLogRuleExt` must remain guard-tested unless G0 records a different replacement plan.
