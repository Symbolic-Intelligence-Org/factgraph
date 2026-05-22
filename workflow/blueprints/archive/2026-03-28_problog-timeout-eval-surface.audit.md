# Task Blueprint Audit: ProbLog Timeout Eval Surface

- Blueprint: [2026-03-28_problog-timeout-eval-surface.md](./2026-03-28_problog-timeout-eval-surface.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Scoped the ProbLog slice around formalizing existing evaluator/runtime capability instead of adding new definition-time API. |
| 2026-03-28 | scoped | Scope frozen | Limit runtime surface to `engine_options.timeout`; defer `ProbLogRuleExt`, provenance, and body_confidences core debt. |
| 2026-03-28 | implemented | Evaluator split landed | Moved `evaluate_problog(...)` out of adapter `__init__.py` into dedicated `engine_eval.py`; `__init__.py` now only registers and re-exports. |
| 2026-03-28 | implemented | Runtime option support landed | Added `resolve_problog_timeout(...)`; shared `engine_options={"timeout": ...}` now flows into `run_problog(...)`. |
| 2026-03-28 | implemented | Real-engine blocker fixed | Real ProbLog CLI validation exposed that tab-format outputs (`answer(...):\t0.42`) were rejected by the parser; importer now strips the trailing colon before predicate parsing. |
| 2026-03-28 | implemented | Validation completed | Targeted ProbLog regression suites passed with 48 tests; full suite passed with 533 tests; real CLI smoke produced one `user:tag` candidate with probability `0.42`. |
| 2026-03-28 | archived | Blueprint archived | Outcome recorded and files moved to `docs/blueprints/archive/`. |

## Decision Notes

- This slice prioritizes existing real runtime capability (`timeout`) over speculative definition-time API.
- `body_confidences` remains the current ProbLog-specific compile input and is intentionally not refactored here.
- The parser fix discovered during real-engine validation is considered in-scope because it is required to make the newly formalized runtime surface actually executable against the local ProbLog CLI.
