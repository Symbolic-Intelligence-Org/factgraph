# Core Development Progress and Roadmap

- Scope: `src/kernel/core`
- Last updated: 2026-03-10
- Baseline: current source behavior, not historical versions

## 1. Current Status Snapshot

Completed structural work:

- `Store` public entrypoints are grouped under `runtime/evaluation/queries/builders`
- `Store.evaluate` modes are unified as `native|souffle|problog`
- `mode='python'|'engine'` has been removed and now fails explicitly
- `core` and `adapters` are decoupled through `register_engine_evaluator`
- `Ledger` uses a SQLite truth + in-memory read-cache write-through model
- `project_view_facts_with_audit` uses `ProjectorAudit(contract_version=2)`
- `accept_many` supports `atomic` / `best_effort` and candidate dependency topological ordering
- the where AST gate is integrated (`FACTPY_WHERE_AST_VALIDATE`)
- upper-layer declaration metadata is now unified as `version / description / tags`; core explicitly remains non-semantic with respect to those fields

## 2. Completed Milestones

### M1. Store boundary consolidation (done)

Result:

- `runtime.py` owns the facade
- `evaluation.py` owns the evaluate flow
- `queries.py` owns query facades
- `builders.py` owns candidate construction

### M2. Engine injection decoupling (done)

Result:

- core no longer needs static adapter imports
- `souffle/problog/pyreason` register evaluators on adapter import

### M3. Ledger persistence (done)

Result:

- SQLite tables and indexes are in place
- append transactions and read-cache updates are synchronized
- the ledger can run in memory mode or file-backed mode

### M4. Batch accept capability (done)

Result:

- introduced `accept_many_candidate_sets(...)`
- supports dependency topological ordering, cycle detection, and atomic rollback

### M5. Projector audit interface (done)

Result:

- `project_view_facts_with_audit(...)` returns an audit structure
- audit fields focus on active/selected/policy-drop statistics

## 3. Current Main Risks

1. compatibility layers are still numerous: `store.api`, `Store.evaluate_dummy`, and `store/_*.py`
2. `accept_many` state-machine complexity has increased, but examples are still not systematic enough
3. consistency boundaries for file-backed multi-process ledger usage are still undefined

## 4. Next Priorities

### P1. Compatibility entrypoint reduction

Goals:

- define a clear removal plan for `evaluate_dummy`
- fully converge new code on `runtime/evaluation/queries/builders`

### P1. `accept_many` contract strengthening

Goals:

- document caller guidance for each `state/error.code`
- add fixed examples for atomic rollback and blocked dependency

### P1. Ledger runtime-boundary definition

Goals:

- document that the current guarantee is a single-process cache model
- if multi-process support is needed, define refresh/invalidation semantics first

### P2. Rule and engine semantic parity governance

Goals:

- keep native and adapter behavior aligned for new where features
- add parity regressions on critical paths

### P2. Performance baselines as standard practice

Goals:

- fix benchmark scenarios and recording format
- make performance changes traceable before and after implementation

## 5. Execution Principles

1. stabilize semantics before optimizing performance
2. reduce compatibility surface before expanding API surface
3. for external contract changes: update docs first, then implementation, then regression coverage
