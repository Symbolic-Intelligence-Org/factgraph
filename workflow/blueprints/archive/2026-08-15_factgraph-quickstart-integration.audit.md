# Task Blueprint Audit: FactGraph quickstart integration

- Blueprint: [2026-08-15_factgraph-quickstart-integration.md](./2026-08-15_factgraph-quickstart-integration.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | audit | Public docs drift mapped | Root README and quickstarts were legacy-first; Product V2 lacked an integrated entry path; obsolete internal links were present. |
| 2026-08-15 | implementation | Current Product path integrated | Added docs index and complete Product V2 workflow; updated Rule, engine, evidence, data, lifecycle and capability chapters. |
| 2026-08-15 | compatibility | Legacy generation retained | V0 `fg.eval.evaluate`, V1 GoalPlan and Q19 `fg.policy` are still documented, but explicitly separated from V2 Scenario/profile/result contracts. |
| 2026-08-15 | verification | Documentation integration complete | Local-link scan clean; executable quickstart and 69-test Product cohort green; Ruff and diff-check clean. |
| 2026-08-15 | implemented | Quickstart integration closed | Current Product workflow, compatibility boundaries and executable drift coverage are aligned. |
| 2026-08-15 | archived | Blueprint pair archived | Documentation and executable workflow were reverified before worktree integration. |

## Decision Notes

- Product V2 is the default learning path, not a replacement or silent alias
  for legacy evaluation.
- Structured Product Explain is the business-consumption contract; text
  renderers are presentation helpers and unavailable EvidenceGraph remains
  explicit.
- Scenario `meta` is write-like SDK syntax over separate semantic,
  provenance and display lanes; it is not ledger `claim_meta`.
- EvaluationRun replay and durable workspace persistence remain distinct
  artifact boundaries.
