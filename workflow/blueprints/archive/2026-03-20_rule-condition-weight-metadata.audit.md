# Task Blueprint Audit: Rule Condition Weight Metadata

- Blueprint: [2026-03-20_rule-condition-weight-metadata.md](./2026-03-20_rule-condition-weight-metadata.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Opened as Child 2 of `certainty-weight-vocabulary` after Child 1 (`candidate-confidence-kind`) closed. |
| 2026-03-20 | scoped | Scope frozen | `condition_weights` defined as version-scoped rule metadata; key shape frozen as `b{branch}.a{atom}`; `RuleSpec` and where evaluator explicitly kept out of scope. |
| 2026-03-20 | implementing | Metadata propagation landed | SDK `Rule`, authoring compile, service compile-preview, and registry canonicalization/read now preserve `description / tags / condition_weights`. Compiler validates atom-position keys and positive finite values. |
| 2026-03-20 | implemented | Archived | Module docs synced (`core/authoring/service/sdk`), child blueprint marked implemented, and full suite passed (`180` tests). |

## Decision Notes

- 2026-03-20: This slice must also repair rule metadata persistence. Without that, `condition_weights` would have no stable carrier and even existing `description / tags` would remain lossy through registry canonicalization.
- 2026-03-20: Condition keys deliberately use atom-position keys (`b{branch}.a{atom}`), not `pred_atom_key` / `step_key`, because the metadata is attached to the rule authoring surface before witness-kind-specific suffixes exist.
- 2026-03-20: Registry canonicalization now reuses `compile_authoring_rule_v1(...)` instead of compressing payloads through `RuleSpec`; this keeps the logical execution boundary unchanged while preserving rule asset metadata.
