# Core Quality Assessment and Module Scoring (factpy_kernel)

- Scope: `src/factpy_kernel/core`
- Last updated: 2026-02-28
- Assessment baseline: `Store` public entrypoints are now grouped as `runtime/evaluation/queries/builders`, `Ledger` is now a SQLite write-through cache with persistence, record accept staging semantics are closed, and the projector audit API has landed
- Validation status: `python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'` -> `509 tests OK`

## 1. Assessment Method and Scoring Dimensions

This document evaluates only the **semantic core layer (`core`)**. It does not include product ergonomics or deployment complexity in `adapters/sdk/authoring/audit`.

Scoring dimensions (0-10 each):

- Architectural boundary clarity
- Semantic completeness (is the core loop closed?)
- Maintainability (responsibility split, readability, change cost)
- Correctness and defensive validation
- Testability and regression coverage
- Extensibility (future semantic evolution)
- Performance (current implementation)

## 2. Overall Score (core)

| Dimension | Score | Notes |
|---|---:|---|
| Architectural boundary clarity | 9.1 | `core` and `adapters` stay decoupled via registration; `Store` public entrypoints and compatibility shims are now clearer |
| Semantic completeness | 8.8 | Protocol/Schema/write/policy/view/rules/derivation/mapping form a complete loop, and persistence/recovery is now part of the runtime story |
| Maintainability | 8.9 | `Store` is now grouped as `runtime/evaluation/queries/builders`; `api.py` is only a compatibility shim |
| Correctness & defensive validation | 9.3 | Strong validation in `SchemaIR`, write protocol, and where evaluation; persistence/recovery paths also have targeted regression coverage |
| Testability & regression coverage | 9.4 | Full `unittest` suite passes (`509 tests`); persistence, service-layer, and grouped-module regressions were added |
| Extensibility | 8.0 | Strong modularity, but Python where vs adapter compiler sync and the current single-process cache model still require discipline |
| Performance (current state) | 8.0 | Read paths are back in the original performance band, and the 10k benchmark is essentially at baseline; adapter export paths still need work |
| **Composite (subjective weighted)** | **8.9** | The core is now durable, recoverable, auditable, and in good engineering shape for continued evolution |

**Conclusion**: `core` is now in a state where it can be persisted, recovered, independently reviewed, and continuously refactored. The main focus shifts from structural cleanup to performance deepening, compatibility cleanup, and higher-level interface integration.

## 3. Module-Level Analysis and Scores

> Scoring is based on the current code shape within `core`, not the maturity of adapters/authoring/sdk.

### 3.1 `protocol` (`protocol/tup_v1.py`, `protocol/idref_v1.py`, `protocol/digests.py`) — 9.0/10

**Responsibility**
- Defines typed tuple encoding, idref encoding, and digest rules

**Strengths**
- Small, stable, and foundational
- Integrates naturally with `SchemaIR`, `derivation`, and `write_protocol`

**Risks / Gaps**
- Protocol expansion (new tags/encoding changes) requires strict compatibility handling

**Recommendation**
- Keep the protocol layer small and stable; version explicitly when semantics change

### 3.2 `schema` (`schema/schema_ir.py`) — 8.9/10

**Responsibility**
- `SchemaIR` validation, canonicalization, digest

**Strengths**
- Strong validation and early failure behavior
- `Store.__init__` validates `SchemaIR` immediately

**Risks / Gaps**
- Some higher-level schema semantics (especially some mapping combinations) can still fail at runtime

**Recommendation**
- Gradually increase compile-time/static checks for mapping configuration combinations

### 3.3 `store.ledger` (`store/ledger.py`) — 8.8/10

**Responsibility**
- Append-only SQLite ledger, idempotent write paths, and read-cache query API

**Strengths**
- Clear data model and strong auditability semantics
- SQLite tables hold durable truth while in-memory indexes serve hot reads
- `append_assertion(...)` / `append_revocation(...)`, `ingest_keys`, and `ledger_meta` are now part of the stable story
- `_force_replace_meta_rows(...)` clearly replaces the old private-list writeback test pattern

**Risks / Gaps**
- File-backed `Ledger` still assumes a single-process write-through cache model
- Adapter export paths do not yet exploit every available index path

**Recommendation**
- Preserve the “SQLite is truth, in-memory indexes are cache” model
- If multi-process sharing becomes necessary, design refresh/invalidation semantics first

### 3.4 `store` public surface (`store/runtime.py`, `store/evaluation.py`, `store/builders.py`, `store/queries.py`, `store/_accept.py`, `store/api.py`) — 8.9/10

**Responsibility**
- Public `Store` API and orchestration across core modules

**Strengths**
- Public entrypoints are clearer than the previous `_*.py`-heavy surface
- Public `Store` API remains stable while internal complexity drops
- `core` no longer statically imports adapters (`register_engine_evaluator`)

**Risks / Gaps**
- `api.py` still carries compatibility baggage
- `_accept.py` remains on the legacy path because of existing monkeypatch contracts in tests

**Recommendation**
- Continue shrinking the compatibility surface over time
- Add more module-level tests as needed, not only full-suite regression coverage

### 3.5 `evidence.write_protocol` — 8.9/10

**Responsibility**
- Append-only write protocol: write/add/retract/replace and ingest-key idempotency

**Strengths**
- Clear semantics and explicit errors
- Now uses atomic ledger entrypoints with transaction boundaries inside `Ledger`
- Idempotency and revocation design are strong

**Risks / Gaps**
- Batch write semantics remain MVP-grade

**Recommendation**
- Define transaction failure semantics before expanding batch writes

### 3.6 `policy` (`active/chosen/policy_ir`) — 8.2/10

**Responsibility**
- Active/chosen decisions and policy IR generation (core-relevant parts)

**Strengths**
- Deterministic chosen tie-break (`ingested_at + asrt_id`)
- Good alignment with `view.projector`

**Risks / Gaps**
- `multi/temporal` chosen paths still contain MVP constraints (all active treated as chosen)

**Recommendation**
- If temporal semantics are expanded, update policy/view consistently with explicit rules

### 3.7 `view` (`view/projector.py`) — 8.9/10

**Responsibility**
- Project business-view facts from the ledger

**Strengths**
- Clear handling for `functional/multi/temporal(record/current)`
- Continues to use ledger hot-path indexes; performance is back in the original baseline band
- Record visibility gating is aligned with shared `record_staging` semantics
- `project_view_facts_with_audit(...)` supports legacy/conflict/count-mismatch statistics without changing the default API shape

**Risks / Gaps**
- Audit statistics currently live mostly as return structures; team-level observability/export pipelines are still thin

**Recommendation**
- Keep semantics first; performance work should now focus on adapter export paths and call frequency

### 3.8 `rules` (`where_eval.py`, `rule_ir.py`) — 8.3/10

**Responsibility**
- Python evaluation for the where-subset and RuleSpec/RuleRegistry execution

**Strengths**
- Well-scoped subset, strict validation, high-quality error reporting
- RuleRef expansion and cycle safety are implemented

**Risks / Gaps**
- Long-term sync cost remains with adapter-side `where_compile`

**Recommendation**
- Treat Python where semantics as the source of truth; require parity tests for new operators

### 3.9 `derivation` (`candidates.py`, `accept.py`) — 9.0/10

**Responsibility**
- Candidate representation and accept/materialization

**Strengths**
- `CandidateSet` shape is clear and idempotency metadata is complete
- `accept_candidate_set` supports both record and fact paths
- Record accept uses staging markers, role digests, closed conflict handling, and structured diagnostics
- Shared `record_staging` logic reduces semantic drift between accept and projector

**Risks / Gaps**
- Complex error categories still partly rely on diagnostics code/message conventions

**Recommendation**
- If diagnostics/audit tooling expands, gradually add more structured error typing

### 3.10 `mapping` (`mapping/canon.py`) — 8.4/10

**Responsibility**
- Mapping predicate conflict resolution and tie-break

**Strengths**
- Structured outputs (`candidates/decisions/conflicts`) are audit-friendly
- Clean integration boundary with `Store.resolve_mapping`

**Risks / Gaps**
- Performance still depends on ledger query patterns and metadata access

**Recommendation**
- Use profiling before deeper optimization on large datasets

## 4. Completed Improvements (Recent Work)

### 4.1 Architecture and Boundary Work
- `core` / `adapters` decoupling: `Store.evaluate(mode='engine')` delegates through registration instead of static imports
- `Store.__init__` validates `SchemaIR` immediately
- `Store` public surface is now grouped as `runtime/evaluation/queries/builders`

### 4.2 Persistence and Data Access
- `Ledger` moved from a pure in-memory implementation to a SQLite write-through cache
- Added `append_assertion(...)` / `append_revocation(...)`
- Added a dedicated `ingest_keys` table and lazy backfill path
- Added `ledger_meta` and `schema_digest`-based restore validation
- policy/view hot paths continue to use in-memory indexes

### 4.3 Tests and Guardrails
- Added `test_core_store_boundary_v1.py` (core boundary / engine registration behavior)
- Added `test_ledger_indexes_v1.py` (atomic ledger entrypoints, index semantics, idempotency)
- Added/enhanced `test_derivation_accept_v1.py` (record partial recovery / closed conflict handling / staging visibility)
- Added `test_view_projector_audit_v1.py` (projector audit counting semantics and default API stability)
- Added `test_core_store_grouped_modules_v1.py` (`Store` grouped public entrypoints)
- Full `unittest` suite passes: `509 tests OK`

## 5. Current Technical Debt (Prioritized)

### P1: No enforced CI performance baseline yet

- **Impact**: future refactors may silently regress runtime cost
- **Recommendation**: use `tools/benchmarks/bench_core_ledger_paths.py` with fixed sizes (for example 3k/10k) and track the baseline
- **Acceptance criteria**: a documented team workflow or CI job exists for benchmark checks

### P1: Adapter export paths still have some full scans (`claims/claim_args`)

- **Impact**: large export-package generation may be slower than necessary
- **Recommendation**: profile `adapters/souffle/package.py` and optimize only measured hotspots
- **Acceptance criteria**: export tests remain green and measured export latency improves

### P2: File-backed `Ledger` is still a single-process write-through cache model

- **Impact**: multi-process sharing has no cache refresh/invalidation guarantee yet
- **Recommendation**: design the minimal refresh/consistency abstraction before any broader concurrency work
- **Acceptance criteria**: a clear interface draft exists instead of incremental patching

### P2: Python where vs adapter compiler dual implementation sync cost

- **Impact**: new where features can drift semantically
- **Recommendation**: keep `core.rules.where_eval` as the baseline and require parity tests for all new operators

### P2: Projector audit statistics do not yet have a team-level observability pipeline

- **Impact**: `ProjectorAudit` can return the right counts, but production/batch consumers do not yet have a standard logging/dashboard path
- **Recommendation**: build an audit-stat consumption path first, then use the measured trend to decide when to move from `legacy_record_visibility=allow` to `audit/deny`
- **Acceptance criteria**: stable visibility into legacy/conflict/count-mismatch trends

### P3: `evaluate_dummy` and old `store.api` compatibility entrypoints still exist

- **Impact**: the API surface remains noisier than necessary
- **Recommendation**: remove them after a clear migration window and caller/test updates

## 6. Testing and Quality Evidence (Current)

- Full test suite: `509 tests OK`
- Boundary guardrail: `test_core_store_boundary_v1.py`
- Index/persistence guardrail: `test_ledger_indexes_v1.py`
- Record-accept guardrail: `test_derivation_accept_v1.py`
- Projector-audit guardrail: `test_view_projector_audit_v1.py`
- Grouped-module guardrail: `test_core_store_grouped_modules_v1.py`
- Benchmark script: `tools/benchmarks/bench_core_ledger_paths.py`

Example benchmark values (`rows=3000`, `rounds=3`):

- `compute_chosen_for_predicate(country)`: `~12ms`
- `project_view_facts(record)`: `~74ms`
- `resolve_mapping_predicate(er:canon_of)`: `~28ms`

> Note: this benchmark is for relative regression tracking, not a production SLA target.

## 7. When to Update This Assessment

Reassess (or at least update scores/notes) after any of the following:

- major `Store` decomposition/consolidation changes
- `Ledger` persistence or cache strategy changes
- new `type_domain` / `cardinality` / where operators
- changes to `core` vs `adapter` boundary policy
- material changes to full-test or benchmark baselines
