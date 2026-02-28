# Core Development Progress and Roadmap (factpy_kernel)

- Scope: `src/factpy_kernel/core`
- Last updated: 2026-02-28
- Current baseline: `509 unittest OK`

## 1. Current Status Summary (Quick Read)

### Major engineering work already completed

- `core` and `adapters` are now separated; `core` no longer statically imports `adapters`
- `Store` public entrypoints are now grouped as `runtime/evaluation/queries/builders`; `api.py` remains only as a compatibility shim
- `Store.__init__` enforces `SchemaIR` validation (early failure)
- `Ledger` is now a SQLite write-through cache with persistence, `ledger_path` recovery, and `schema_digest` binding
- policy/view hot paths continue to use `Ledger` in-memory indexes; 3k/10k benchmarks are back to the original performance band
- full `unittest` suite passes (`509 tests`)
- record accept semantic closure landed (staging marker + role digest + projector invisibility gating + structured diagnostics)
- shared `record_staging` resolver landed (`accept` / `projector` share conflict semantics)
- `project_view_facts_with_audit(...)` landed (default `project_view_facts(...)` return shape unchanged)
- `project_view_facts(..., legacy_record_visibility="allow"|"audit"|"deny")` landed (`allow` default; `audit` preserves the fact set)
- service-layer review docs were updated (`04_service_layer.md`); the current service is now the first frontend/BFF batch, not a rules-only thin layer
- `Public Contract v1` docs and regression tests landed (`04_public_contract_v1.md` / `test_public_contract_v1.py`)

### Current top risks (short list)

1. Some adapter export paths still rely on full scans and may become the next bottleneck
2. Benchmarking exists, but no team/CI performance regression gate exists yet
3. File-backed `Ledger` currently assumes a single-process write-through cache model; multi-process sharing is not yet guaranteed

### Current performance baseline (reference)

Benchmark script: `tools/benchmarks/bench_core_ledger_paths.py`

- Scale: `rows=3000`, `claims=12000`, `meta_rows=48000`
- `compute_chosen_for_predicate(country)`: `~12ms`
- `project_view_facts(record)`: `~74ms`
- `resolve_mapping_predicate(er:canon_of)`: `~28ms`

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
- Adapter import auto-registers the evaluator

**Done criteria (met)**
- No static adapter imports in `core`
- Engine mode raises a clear error when no evaluator is registered
- Importing the adapter restores engine evaluation behavior

### M3. `Store` Public Surface Consolidation (Done)

**Goal**
- Reduce `Store` public cognitive load while preserving compatibility imports

**Result**
- Added `store/runtime.py`
- Added `store/evaluation.py`
- Added `store/queries.py`
- Added `store/builders.py`
- Downgraded `store/api.py` to a compatibility shim

**Done criteria (met)**
- Full tests pass
- New code prefers `runtime/evaluation/queries/builders`
- Legacy imports still work

### M4. `Ledger` SQLite Persistence and Write-Through Cache (Done)

**Goal**
- Provide restart-safe local persistence without losing hot-path performance

**Result**
- SQLite tables are now the durable truth (`claims / claim_args / meta_rows / revokes / ingest_keys / ledger_meta`)
- in-memory dict/set/list indexes act as read cache, rebuilt on load and updated after commit
- Added `append_assertion(...)` / `append_revocation(...)`
- Added `get_ledger_meta(...)` / `set_ledger_meta(...)`
- `_force_replace_meta_rows(...)` now replaces the old `_meta_rows + rebuild_indexes()` test pattern

**Done criteria (met)**
- Full tests pass
- `SDKStore.from_schema_classes(..., ledger_path=...)` can restore runtime data
- Benchmarks are back in the original performance band

### M5. Record Accept Semantic Closure (Done, P0/P0.5)

**Goal**
- Close gaps around partial record materialization visibility, implicit nondeterminism, and diagnosability

**Result**
- record accept now uses staging markers and role-level digests
- `accept` and `projector` share `record_staging` conflict semantics
- `projector` hides non-committed / conflict / aborted record groups
- `projector` adds low-cost `roles_count_expected` completeness checks (count mismatch hides the group)
- `AcceptResult.diagnostics` exposes conflict consequences structurally

**Done criteria (met)**
- Partial-write retry recovery regressions pass
- committed+aborted / committed+inflight mismatch conflict regressions pass
- Full test suite passes

### M6. Projector Audit Statistics (Done, P1)

**Goal**
- Provide record-visibility statistics for migration/observability without changing the default `project_view_facts(...)` return shape

**Result**
- Added `project_view_facts_with_audit(...) -> (facts, ProjectorAudit)`
- Single scan, shared indexes, dual output (default path and audit path share the implementation)
- Added `legacy_record_visibility="allow"|"audit"|"deny"` (`allow` default; `audit` returns the same fact set; `deny` hides only legacy record groups)
- Audit statistics cover:
  - legacy records
  - marker conflicts (aggregated by reason)
  - committed hidden count mismatch

**Done criteria (met)**
- Added `test_view_projector_audit_v1.py`
- Default API output remains backward compatible
- `legacy_record_visibility=allow/audit` matches, and `deny` only affects legacy record visibility

## 3. Current Architecture Decisions (Keep These Stable)

### D1. `core` must not statically import `adapters`
- Engine behavior is injected via evaluator registration
- Reason: `core` must remain independently testable and reviewable

### D2. SQLite tables are truth; in-memory indexes are caches
- Durable truth lives in SQLite
- In-memory indexes are maintained only on load and after successful commits
- `rebuild_indexes()` is now a compatibility no-op, not a repair path
- Tests that need to replace meta rows should use `_force_replace_meta_rows(...)`

### D3. `Store` public API stability is prioritized over internal purity
- External callers continue to use `Store`
- New code should prefer `runtime/evaluation/queries/builders`
- Reason: reduce cascading changes while refactoring

## 4. Next Development / Optimization Targets (Prioritized)

### P1. Establish a performance regression baseline (short term)

**Motivation**
- Benchmarks exist, but there is no enforced team/CI gate yet

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

### P1. Observability and migration strategy for legacy record visibility

**Motivation**
- Legacy records (without `record_digest`) are still visible by default; the team should measure real usage before tightening policy

**Recommended actions**
- Build team-level observability on top of projector audit statistics (logs/export/dashboard)
- Use `audit` first to estimate migration cost, then decide if/when the default should move away from `legacy_record_visibility=allow`

**Acceptance criteria**
- Stable visibility into legacy counts, marker-conflict counts, and count-mismatch hidden groups
- No change to default `project_view_facts(...)` behavior

### P2. Expand semantic coverage for the new `Ledger` write paths

**Motivation**
- Index queries and the main idempotency flow are covered, but `append_assertion/append_revocation` boundaries still deserve broader sampling

**Recommended actions**
- Add more tests for `AppendResult.written`, rewrite-after-revoke, and ingest-key lazy backfill combinations
- Add consistency tests for `_force_replace_meta_rows(...)` and the `meta_rows` property
- Add more file-backed `Ledger(path=...)` recovery scenarios

**Acceptance criteria**
- Tests catch common persistence/cache regressions before they leak into integration paths

### P2. Gradually remove legacy compatibility entrypoints (`evaluate_dummy` / old `store.api` imports)

**Motivation**
- Reduce API surface and compatibility cost

**Recommended actions**
- Audit real usage
- Migrate tests/callers
- Remove deprecated paths

**Acceptance criteria**
- No remaining compat-import dependencies
- Full test suite remains green

### P3. Explore deeper storage / concurrency abstraction (mid-term)

**Motivation**
- File-backed `Ledger` still assumes a single-process write-through cache model; larger sharing models need a clearer abstraction

**Recommended actions (design-first)**
- Define the minimal storage/query interface used by core semantics
- Make the boundary between the current single-process cache model and future refresh/invalidation strategies explicit

**Acceptance criteria**
- Written design/interface draft exists
- No rushed multi-process consistency mechanism before the interface is clear

## 5. Short-Term Execution Plan (Suggested 1-2 Weeks)

### S1. Normalize benchmark usage
- Task: define default benchmark scales and recording format
- Files: `tools/benchmarks/bench_core_ledger_paths.py`, this roadmap doc
- Validation: run two scales and record outputs

### S2. Profile adapter export hotspots
- Task: add temporary timing/profiling to `adapters/souffle/package.py` critical paths
- Validation: remove temp instrumentation before merge (or gate behind a debug switch)

### S3. Expand persistence-path semantic tests
- Task: extend `test_ledger_indexes_v1.py` and `test_write_protocol_v1.py`
- Validation: full `unittest` suite passes

## 6. Mid-Term Plan (Suggested 1-2 Months)

- Evaluate a `Ledger` abstraction interface for richer storage/concurrency models (design first)
- Introduce a performance regression process (CI or team convention)
- Continue reducing legacy `Store` compatibility surface
- Enforce a stricter parity workflow when adding new semantic features across core and adapters

## 7. Non-Goals (Current Phase)

- No protocol version changes (`idref_v1` / `tup_v1` / `export_v1`)
- No major public `Store` API signature changes
- No movement of adapter logic back into `core`
- No multi-process `Ledger` cache consistency in the current phase

## 8. Development and Acceptance Checklist (Run After Core Changes)

### Required regression check

```bash
python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'
```

### Recommended for performance-related changes

```bash
python tools/benchmarks/bench_core_ledger_paths.py --rows 3000 --rounds 3
python tools/benchmarks/bench_core_ledger_paths.py --rows 10000 --rounds 3
```

### Documentation update rules

Update at least this file and `02_quality_assessment.en.md` when any of the following changes:

- `Store` structure is split/merged again
- `Ledger` persistence or cache strategy changes
- record visibility gating / staging conflict semantics change
- projector audit contract or counting semantics change
- test baseline count/status changes
- benchmark baseline changes materially

## 9. Risk and Rollback Strategy (For Current Refactors)

- If `Ledger` persistence/cache changes cause behavior issues:
  - reproduce with `test_ledger_indexes_v1.py` and `test_write_protocol_v1.py`
  - check whether code bypassed atomic write APIs or the test-only `_force_replace_meta_rows(...)` path
  - if needed, revert to a more conservative read-path implementation while preserving API
- If `Store` surface consolidation causes behavior issues:
  - verify `Store` facade signatures first
  - then compare logic across `runtime/evaluation/queries/builders` for semantic drift

---

This document is not a replacement for an issue tracker. It is a **stable snapshot of current core state and next-step direction**. Before starting new work, verify the task still aligns with the boundaries and invariants documented here.
