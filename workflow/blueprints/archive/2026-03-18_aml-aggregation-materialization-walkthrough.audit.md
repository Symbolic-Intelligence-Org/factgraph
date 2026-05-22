# Task Blueprint Audit: AML Aggregation Materialization Walkthrough

- Blueprint: [2026-03-18_aml-aggregation-materialization-walkthrough.md](./2026-03-18_aml-aggregation-materialization-walkthrough.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the Route-A walkthrough slice after `aml-event-aggregation-semantics` adopted pre-materialized aggregation as the first-round direction and deferred true in-rule aggregation to T2-level capability work. |
| 2026-03-18 | scoped | Scope freeze | Locked the walkthrough to raw+materialized dual-layer facts, a downstream rule that consumes only the materialized layer, and five-layer explain validation focused on materialization-boundary honesty. |
| 2026-03-18 | implemented | Route-A walkthrough regression landed | Added a synthetic raw+materialized AML walkthrough to `test_phase3_contracts_v1.py` and validated that the existing explain stack distinguishes helper outputs from downstream rule consumption without contract changes. |
| 2026-03-18 | verified | Full phase-3 contract suite passed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 67 tests, confirming the materialization walkthrough fits inside the current explain substrate. |
| 2026-03-18 | archived | Blueprint archived | The walkthrough concluded that Route A is explain-honest enough for first-round AML aggregation; no helper-traceability, wording, or T2 blocker was exposed. |

## Decision Notes

- 2026-03-18
  - Scope rule: this slice must validate the honesty boundary between raw inputs, helper outputs, and downstream rule consumption without inventing a new helper API.
- 2026-03-18
  - Delivery rule: existing raw/summary/narrative/NL/static surfaces should be reused as-is; if they are insufficient, the failure must be named as a single follow-on gap.
- 2026-03-18
  - T2 guardrail: the walkthrough must not quietly reintroduce in-rule event aggregation or sequence/state semantics.
- 2026-03-18
  - Scope lock: the walkthrough is explicitly a Route-A validation slice. Raw transactions remain drill-down context, while the rule itself consumes only materialized helper outputs plus supporting signals.
- 2026-03-18
  - Outcome: Route A held. The trace remained honest about what the rule consumed, while raw input assertions stayed inspectable via audit assertions/static pages; no follow-on gap blueprint is required before staying on the materialization path.
