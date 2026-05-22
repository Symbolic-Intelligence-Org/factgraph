# Decision Blueprint Audit: PyReason Execution Surface v0

- Blueprint: [2026-03-27_pyreason-execution-surface-v0-decision.md](./2026-03-27_pyreason-execution-surface-v0-decision.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | 4 decisions for review: EvaluateMode gate, engine_options, WhereIR compiler, annotation strategy |
| 2026-03-27 | scoped | 3 corrections applied | D2: removed false claim about evaluate_engine kwargs passthrough. D3: compiler scope reworded to lowered WhereIR terms. D4a: changed from `"pyreason_degraded"` to reusing `engine_no_witness_v1`. D4b: post-accept example uses `accepted.written_assertions` (correct field name). |

## Decision Notes

- Q1 initial analysis underestimated core changes — `EvaluateMode` Literal gate is explicit, not just registry
- Q2 `engine_options` doesn't exist in current codebase — deferred to v1
- Q2 critical finding: evaluate receives lowered WhereIR, not Rule DSL atoms — new compiler needed
- Q4 `accept_pyreason_session()` cannot serve as execution surface accept — no session in generic flow
| 2026-03-27 | superseded | Blueprint superseded | Office hours redesign session revealed deeper structural issues (shadow pipeline, engine_ext never implemented). Decisions D1-D4 incorporated into new unified decision blueprint: `2026-03-27_multi-engine-execution-surface-decision.md`. This blueprint archived. |
