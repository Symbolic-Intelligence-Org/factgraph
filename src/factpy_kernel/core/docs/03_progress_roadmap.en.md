# Core Development Progress and Roadmap (factpy_kernel)

- Scope: `src/factpy_kernel/core`
- Last updated: 2026-02-24
- Current baseline: `459 unittest OK`

## 1. Current Status Summary (Quick Read)

### Major engineering work already completed

- `core` and `adapters` are now separated; `core` no longer statically imports `adapters`
- `Store` phase-1 decomposition is complete (`api/_evaluate/_accept/_builders/_queries`)
- `Store.__init__` enforces `SchemaIR` validation (early failure)
- `Ledger` now has in-memory indexes (claims/meta/claim_args/revokes)
- policy/view hotspots now use `Ledger.find_claim_args(...)`
- full `unittest` suite passes (`459 tests`)
- record accept semantic closure landed (staging marker + role digest + projector invisibility gating + structured diagnostics)
- shared `record_staging` resolver and `project_view_facts_with_audit(...)` landed (default API shape unchanged)

### Current top risks (short list)

1. `Ledger` is still in-memory only (capacity/durability limitation)
2. Some adapter export paths still rely on full scans and may become the next bottleneck
3. Benchmarking exists, but no team/CI performance regression gate exists yet

### Current performance baseline (reference)

Benchmark script: `tools/benchmarks/bench_core_ledger_paths.py`

- Scale: `rows=3000`, `claims=12000`, `meta_rows=48000`
- `compute_chosen_for_predicate(country)`: `~11ms`
- `project_view_facts(record)`: `~47ms`
- `resolve_mapping_predicate(er:canon_of)`: `~23ms`

## 2. Completed Milestones (By Theme)

### M1. Directory Layering and Boundary Cleanup (Done)

**Goal**
- Establish a clear engineering boundary between `core` (semantics) and `adapters` (engine/export integration)

**Result**
- Directory structure reorganized
- Souffle-specific code moved under `adapters/souffle`
- Top-level compatibility shims removed (clean layout retained)

**Done criteria (met)**
- New import paths work
- Full test suite passes

### M2. `Store` Boundary Purification (Done)

**Goal**
- Remove static adapter dependencies from `core.store.api`

**Result**
- Introduced `register_engine_evaluator(...)`
- Engine evaluation logic moved into `adapters/souffle/engine_eval.py`
- Adapter import auto-registers evaluator

**Done criteria (met)**
- No static adapter imports in `core`
- Engine mode raises clear error when no evaluator is registered
- Importing adapter restores engine evaluation behavior

### M3. `Store` Decomposition (Phase 1, Done)

**Goal**
- Reduce `Store` file complexity while preserving external API

**Result**
- `store/_evaluate.py`: evaluation flow
- `store/_accept.py`: accept + digest flow
- `store/_builders.py`: candidate building / record spec / value coercion
- `store/_queries.py`: explain/conflicts/mapping
- `store/api.py`: reduced to facade + registration point + small compatibility entrypoints

**Done criteria (met)**
- Full tests pass
- Adapter no longer depends on `Store` private method names

### M4. `Ledger` In-Memory Index Optimization (Done)

**Goal**
- Reduce hot query costs (`find_claims/find_meta/has_active_revocation/...`)

**Result**
- Added claims/meta/claim_args/revokes indexes
- Added `find_claim_args(...)`
- Switched policy/view hotspots to indexed lookup
- Added `rebuild_indexes()` for private-list mutation recovery in tests/debug flows

**Done criteria (met)**
- Full tests pass (`338`)
- New index semantics tests pass

## 3. Current Architecture Decisions (Keep These Stable)

### D1. `core` must not statically import `adapters`
- Engine behavior is injected via evaluator registration
- Reason: `core` must remain independently testable and reviewable

### D2. `Ledger` lists are source of truth; indexes are caches
- Indexes are maintained in `append_*`
- `rebuild_indexes()` is the repair path for test/debug direct mutations
- Reason: avoid dual-source-of-truth drift

### D3. `Store` public API stability is prioritized over internal purity
- External callers continue to use `Store`
- Internal behavior evolves in `store/_*.py`
- Reason: reduces cascading changes while refactoring

## 4. Next Development / Optimization Targets (Prioritized)

### P1. Establish a performance regression baseline (short term)

**Motivation**
- Multiple structural/index optimizations have landed, but there is no enforced regression gate

**Recommended actions**
- Fix benchmark scenarios (e.g. `3k` and `10k` rows)
- Record baseline output in docs or CI artifacts
- Run before/after performance-sensitive refactors

**Acceptance criteria**
- Clear command and result format exist
- Team members can reproduce comparable results (with expected variance)

### P1. Profile adapter export hotspots (`claims/claim_args` paths)

**Motivation**
- `adapters/souffle/package.py` still contains several full traversals that may dominate large exports

**Recommended actions**
- Profile or add scoped timing around `_build_fact_rows` and audit-related aggregation paths
- Prefer `Ledger.find_meta/find_claims/find_claim_args` where behavior is preserved

**Acceptance criteria**
- Export-related tests remain green
- Measurable export-time improvement on a fixed scenario

### P2. Expand semantic tests for Ledger index paths

**Motivation**
- Current coverage is good, but more filter-combination and ordering checks will reduce future regression risk

**Recommended actions**
- Add `find_meta` multi-filter ordering tests
- Add `find_claim_args` consistency tests vs expected behavior
- Add `rebuild_indexes()` recovery tests for claims/revokes, not only meta rows

**Acceptance criteria**
- Tests catch common index-regression classes before they escape to integration paths

### P2. Remove legacy compatibility entrypoints (e.g. `evaluate_dummy`) over time

**Motivation**
- Reduce API surface and test warnings

**Recommended actions**
- Audit real usage
- Migrate tests/callers
- Remove deprecated path

**Acceptance criteria**
- No deprecation warnings from `evaluate_dummy`
- Full test suite remains green

### P3. Explore storage backend abstraction (mid-term)

**Motivation**
- Current in-memory `Ledger` limits scalability and durability

**Recommended actions (design-first)**
- Define a minimal required storage/query interface used by core semantics
- Preserve append-only and query semantics

**Acceptance criteria**
- Written design/interface draft exists
- No rushed backend implementation before interface is stable

## 5. Short-Term Execution Plan (Suggested 1-2 Weeks)

### S1. Normalize benchmark usage
- Task: define default benchmark scales and recording format
- Files: `tools/benchmarks/bench_core_ledger_paths.py`, this roadmap doc
- Validation: run two scales and record outputs

### S2. Profile adapter export hotspots
- Task: add temporary timing/profiling to `adapters/souffle/package.py` critical paths
- Validation: remove temp instrumentation before merge (or gate behind debug switch)

### S3. Expand index tests
- Task: extend `test_ledger_indexes_v1.py`
- Validation: full `unittest` suite passes

## 6. Mid-Term Plan (Suggested 1-2 Months)

- Evaluate a `Ledger` abstraction interface in preparation for persistence/snapshot backends (design first)
- Introduce a performance regression process (CI or team convention)
- Continue reducing legacy `Store` compatibility surface
- Enforce a stricter parity workflow when adding new semantic features across core and adapters

## 7. Non-Goals (Current Phase)

- No protocol version changes (`idref_v1` / `tup_v1` / `export_v1`)
- No rewrite of `Ledger` into a database backend in this phase
- No major public `Store` API signature changes
- No movement of adapter logic back into `core`

## 8. Development and Acceptance Checklist (Run After Core Changes)

### Required regression check

```bash
python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'
```

### Recommended for performance-related changes

```bash
python tools/benchmarks/bench_core_ledger_paths.py --rows 3000 --rounds 3
```

### Documentation update rules

Update at least this file and `02_quality_assessment.en.md` when any of the following changes:

- `Store` structure is split/merged again
- `Ledger` indexing strategy changes
- test baseline count/status changes
- benchmark baseline changes materially

## 9. Risk and Rollback Strategy (For Current Refactors)

- If `Ledger` indexing causes behavioral issues:
  - reproduce with `test_ledger_indexes_v1.py`
  - check whether private lists were mutated without calling `rebuild_indexes()`
  - if needed, revert to linear-scan implementation while preserving API (rollback is low-cost)
- If `Store` decomposition causes behavioral issues:
  - verify `Store` facade signatures first
  - then compare logic across `_evaluate/_accept/_builders/_queries` for semantic drift

---

This document is not an issue tracker replacement. It is a **stable snapshot of current core state and next-step direction**. Before starting new work, verify the task still aligns with the boundaries and invariants documented here.
