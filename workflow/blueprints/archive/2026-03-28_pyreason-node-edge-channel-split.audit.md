# Task Blueprint Audit: PyReason Node-Edge Channel Split

- Blueprint: [2026-03-28_pyreason-node-edge-channel-split.md](./2026-03-28_pyreason-node-edge-channel-split.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Follow-up real-engine finding recorded | Real PyReason runs suggested the prior “all facts via add_fact” fix was incomplete: node labels and edge labels need different channels. |
| 2026-03-28 | scoped | Blueprint activated for implementation | Scope limited to runner channel split. Explicitly excludes head-in-body compiler validation pending proof. |
| 2026-03-28 | implemented | Runner channel split landed | `build_pyreason_graph(...)` now writes edge labels as graph attrs, `_session_fact_records(...)` now lowers node facts only, and docs/tests were updated to match. |
| 2026-03-28 | implemented | Validation completed | `PYTHONPATH=src python -m py_compile src/factpy_kernel/adapters/pyreason/runner.py src/factpy_kernel/adapters/pyreason/rule_ext.py src/factpy_kernel/adapters/pyreason/where_compile.py` passed; targeted PyReason suites passed with 73 tests and adjacent annotation/session regression suites passed with 101 tests. |

## Decision Notes

- The proposed head-in-body validation was intentionally excluded from this task because the local PyReason source does not enforce or document it as a parser/runtime invariant.
