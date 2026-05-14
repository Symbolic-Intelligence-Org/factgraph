# Core Quality Assessment (code snapshot)

- Scope: `src/factgraph/core`
- Last updated: 2026-03-10
- Assessment baseline: current source structure and public entrypoints, not historical versions

## 1. Summary

`core` is currently in a state where semantic boundaries are clear and long-term iteration is practical. Its main strengths are:

- clear `Store` entrypoints (`runtime/evaluation/queries/builders`)
- atomic ledger writes with explicit persistence (`SQLite` truth + in-memory read cache)
- explicit evaluate mode constraints (`native|souffle|problog`)
- batch semantics through `accept_many` (`atomic` / `best_effort`)
- double guardrails on `where` via AST gate and validator
- a clean boundary from upper-layer declaration metadata: `version / description / tags` stay in authoring/sdk assets and do not leak into core execution semantics

## 2. Dimension Scores (current snapshot)

| Dimension | Score | Notes |
|---|---:|---|
| Architectural boundary clarity | 9.2 | core and adapters are decoupled through registration; entrypoints are clearly grouped |
| Semantic completeness | 8.7 | write/projection/rules/derivation/accept/mapping now form a closed loop |
| Maintainability | 8.8 | public entrypoints and implementation layers are separated reasonably well |
| Correctness guardrails | 9.0 | SchemaIR validation, where gate, and write-protocol input constraints are strong |
| Extensibility | 8.3 | engines are pluggable, but compatibility shims and legacy entrypoints still need gradual cleanup |
| Performance foundation | 8.2 | hot ledger paths already use cached indexes; future work is mainly export and large-batch optimization |
| Composite | 8.7 | the core is stable enough for sustained iteration; next focus should be compatibility cleanup and observability |

## 3. Module Observations

### 3.1 `store.runtime/evaluation/queries/builders`

Strengths:

- responsibilities are clearly separated
- `Store` API stays stable
- public SDK `evaluate(engine=...)` behavior is explicit and historical aliases now fail clearly
- query entrypoints (`explain/conflicts/resolve_mapping`) are separated from candidate construction

Risks:

- `_*.py` implementation modules and the `store.api` shim still add reading overhead

### 3.2 `store.ledger`

Strengths:

- append-only and revocation semantics are stable
- SQLite persistence and read cache coexist behind a consistent interface
- atomic boundaries around `append_assertion/append_revocation` are clear

Risks:

- file-backed ledger still assumes a single-process cache model

### 3.3 `view.projector`

Strengths:

- `single/multi` semantics are clear
- `project_view_facts_with_audit` provides lightweight audit statistics
- `project_view_facts_with_audit` keeps projection audit metadata separate
  from the projected fact rows

Risks:

- audit currently returns structures only; it does not yet imply a long-term observability pipeline

### 3.4 `derivation.accept`

Strengths:

- `AcceptResult` fields are stable
- `accept_many` provides topological ordering, cycle detection, and atomic rollback
- entity and fact candidate paths are already converged

Risks:

- part of the error-code surface still depends on exception message prefixes; over time it should become more structured

### 3.5 `rules.where_*`

Strengths:

- AST parse/validate and evaluator layers are clearly separated
- the gate is controllable through `FACTPY_WHERE_AST_VALIDATE`

Risks:

- any new where capability still needs semantic sync between the native path and adapter compilation

## 4. Main Risks and Priorities

### P1: compatibility surface is still broader than ideal

Examples:

- `Store.evaluate_dummy(...)` still exists
- `store.api` and `_*.py` compatibility modules still exist

Recommendation:

- define a deprecation timeline and migrate callers gradually

### P1: external docs and regression examples for `accept_many` still need strengthening

Current state:

- implementation semantics are solid, but the batch state flow still has a high onboarding cost for new callers

Recommendation:

- add minimal reusable examples for atomic rollback, blocked dependency, and duplicate handling

### P1: multi-process ledger consistency boundaries are still undefined

Recommendation:

- if multi-process support is required, define cache refresh/invalidation semantics before expanding the implementation

## 5. Suggested Next-Stage Goals

1. shrink compatibility entrypoints first, especially `evaluate_dummy` and old import shims
2. strengthen contract examples and error-code docs for batch `accept_many`
3. establish performance regression records for fixed benchmark scenarios, especially export and large-batch writes
