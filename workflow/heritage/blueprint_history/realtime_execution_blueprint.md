> 状态：讨论中 · 尚未实现  
> 类型：历史性能 / 实时执行蓝图  
> 说明：本文档保留为历史设计草案，用于记录 SDK v1 时代对单进程实时执行优化的设想；它不是当前实现真相。

# Real-Time Execution Blueprint (SDK v1)

This document describes a practical execution/runtime optimization plan for the current SDK without changing user-facing syntax.

## Goal

Make the SDK materially more usable for real-time workloads while preserving the existing API and DSL:

- `sdk.ref/set/add/retract`
- `sdk.batch()/edit()/ingest()`
- `sdk.get/find/run/evaluate/accept`
- `Rule`, `Query`, and `Derivation` syntax

The target is not a distributed stream engine. The target is a stronger single-process real-time runtime.

## Current Bottlenecks

The main latency problem is not the write protocol itself. The larger issue is that hot read paths repeatedly rebuild a full projected view of the ledger.

Current examples:

- `sdk.get(...)` calls `project_view_facts(...)` before snapshot assembly.
- `sdk.find(...)` also calls `project_view_facts(...)`.
- `sdk.run(...)` for `Rule` starts from `project_view_facts(...)`.
- `sdk.run(Query(...))` starts from `project_view_facts(...)`.
- `sdk.evaluate(...)` in native mode also projects the full active view before evaluating `where`.

As a result, primary-key reads, filtered reads, and rule/query evaluation all pay a global projection cost that grows with ledger size.

## Design Constraints

The optimization plan must preserve the following:

- No syntax or signature changes for existing public SDK entry points.
- No semantic drift in `single`/`multi` field behavior.
- No semantic drift in revocation, idempotency, or provenance/meta behavior.
- Existing contract tests must continue to pass.
- `souffle` and `problog` remain optional engines and stay off the synchronous hot path.

## Non-Goals

The first iteration does not attempt to provide:

- distributed writes
- multi-process live index coherence
- continuous query subscriptions
- external streaming infrastructure
- a new DSL

## Proposed Runtime Shape

### 1. Keep the append-only ledger as the source of truth

The ledger remains authoritative for persistence, replay, and auditability.

### 2. Add a process-local incremental read model

Introduce an `ActiveViewIndex` that is built once from the ledger and then incrementally updated on each write/retract.

This index should support:

- entity visibility by `entity_type + e_ref`
- current chosen value for `single` fields
- current active values for `multi` fields
- reverse lookup for hot `find(...)` filters
- predicate row iteration for rule/query evaluation

### 3. Add real batch commit at the ledger layer

Current SDK batching is API-level staging, but final writes are still applied one by one. Introduce a ledger-level batch append path so a group of prepared writes shares one SQLite transaction.

### 4. Move rule/query/native-derivation execution to on-demand lookup

Keep the current evaluator semantics, but stop requiring a full `view_facts` materialization on every call. Instead, evaluate against a lookup provider backed by `ActiveViewIndex`.

## Delivery Plan

### PR1: Batch Transaction Write Path

### Objective

Improve write throughput and reduce transaction overhead without changing SDK syntax.

### Changes

- Add a public batch append entry point in `core/store/ledger.py`.
- Split write-protocol code into:
  - prepare write
  - execute prepared write
- Keep `set_field(...)`, `add_field(...)`, and `retract_by_asrt(...)` as compatibility entry points.
- Update `sdk.batch()` and `sdk.ingest()` to collect prepared writes and commit them in one ledger transaction.

### Suggested additions

- `PreparedAssertionWrite`
- `PreparedRevocationWrite`
- `BatchAppendResult`
- `Ledger.append_batch(...)`

### Files

- `src/factpy_kernel/core/store/ledger.py`
- `src/factpy_kernel/core/evidence/write_protocol.py`
- `src/factpy_kernel/sdk/batch.py`
- `src/factpy_kernel/sdk/ingest.py`

### Expected result

- Better file-backed throughput
- Lower transaction overhead
- No public API changes

### PR2: Incremental Active Read Index

### Objective

Remove full active-view reprojection from `sdk.get(...)` and `sdk.find(...)`.

### Changes

- Add `core/view/active_index.py`.
- Build `ActiveViewIndex` from the ledger when `Store` is created/opened.
- Update the index incrementally after successful assertion append/revocation append.
- Route `sdk.get(...)` and `sdk.find(...)` through the index.
- Retain the current projection-based path as a parity/fallback path during rollout.

### Suggested `ActiveViewIndex` responsibilities

- `build_from_ledger(schema_ir, ledger)`
- `apply_assertion(...)`
- `apply_revocation(...)`
- `entity_visible(entity_type, e_ref)`
- `get_entity_snapshot_data(entity_type, e_ref)`
- `find_entity_refs(entity_type, filters)`
- `iter_predicate_rows(pred_id)`

### Files

- `src/factpy_kernel/core/view/active_index.py` (new)
- `src/factpy_kernel/core/store/runtime.py`
- `src/factpy_kernel/sdk/facade.py`

### Expected result

- `sdk.get(...)` becomes near-O(1) on the hot path
- exact/contained `sdk.find(...)` no longer requires full view projection
- much better real-time read behavior for ordinary application requests

### PR3: Lookup-Driven Rule/Query/Derivation Execution

### Objective

Remove full projection from the synchronous execution path for `run(...)` and native `evaluate(...)`.

### Changes

- Extend `where_eval` with a lookup-provider execution mode.
- Preserve the current `evaluate_where(view_facts, where)` path for compatibility.
- Add a new path such as `evaluate_where_with_lookup(lookup, where)`.
- Change `run_rule(...)`, `execute_query_plan(...)`, and native `evaluate_store(...)` to use lookup-backed evaluation.

### Minimal lookup interface

- `rows(pred_id) -> iterable[tuple]`
- `lookup(pred_id, key_positions, key_values) -> iterable[tuple]`

### Files

- `src/factpy_kernel/core/rules/where_eval.py`
- `src/factpy_kernel/core/rules/rule_ir.py`
- `src/factpy_kernel/sdk/query_runtime.py`
- `src/factpy_kernel/core/store/_evaluate.py`

### Expected result

- lower latency for `sdk.run(...)`
- lower latency for native `sdk.evaluate(...)`
- no DSL changes

## Runtime Placement

The safest place to host the new read index is on `Store`:

- the ledger already lives on `Store`
- rule/query/evaluate paths already receive `Store`
- SDK facade code can read through `sdk.store`

This keeps the optimization below the public SDK layer while remaining accessible to all execution paths.

## Behavioral Invariants

The new runtime must preserve:

- chosen-value semantics for `single` fields
- active-value semantics for `multi` fields
- revocation idempotency
- ingest-key idempotency
- current result shape and error contracts
- existing deterministic row ordering rules where already documented or asserted

## Rollout Strategy

Use staged adoption instead of a flag day:

1. Land batch writes first.
2. Land `ActiveViewIndex` and switch `get/find`.
3. Land lookup-driven evaluator changes for `run/query/evaluate`.
4. Keep projection-based parity tests until the new path is stable.

## Testing Requirements

### Contract parity

For the same ledger contents, old and new execution paths must produce identical results for:

- `sdk.get(...)`
- `sdk.find(...)`
- `sdk.run(...)`
- `sdk.evaluate(...)`

### Existing tests

At minimum, preserve coverage from:

- `src/factpy_kernel/tests/test_phase3_contracts_v1.py`

### New tests

- batch write parity tests
- incremental-index rebuild vs incremental-update parity tests
- read-path parity tests against projection-based reference behavior
- benchmark-style smoke tests for:
  - write throughput
  - `get(...)` latency
  - filtered `find(...)` latency
  - `run(...)` latency

## Operational Boundary

The first implementation should assume a single service process owns writes for a given ledger file.

This avoids cross-process cache invalidation and keeps the design practical. If multi-process live reads/writes are required later, that should be a separate design phase.

## Acceptance Criteria

The plan is considered successful when all of the following are true:

- public SDK syntax is unchanged
- public SDK result contracts are unchanged
- file-backed write throughput is materially better
- `sdk.get(...)` latency no longer scales with full ledger projection
- exact-filter `sdk.find(...)` latency is materially reduced
- `sdk.run(...)` and native `sdk.evaluate(...)` no longer rebuild the full active view on every call

## Summary

This blueprint is an execution-engine upgrade, not a language redesign.

The practical sequence is:
