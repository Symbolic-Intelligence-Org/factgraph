# Core Quality Assessment and Module Scoring (factpy_kernel)

- Scope: `src/factpy_kernel/core`
- Last updated: 2026-02-24
- Assessment baseline: directory refactor complete, `Store` phase-1 decomposition complete, `Ledger` indexing optimization complete, record accept staging semantics closed, projector audit API landed
- Validation status: `python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'` -> `459 tests OK`

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
| Architectural boundary clarity | 9.0 | `core` and `adapters` decoupled via registration; `Store` still exposes engine entrypoint (reasonable) |
| Semantic completeness | 8.5 | Protocol/Schema/write/policy/view/rules/derivation/mapping form a complete loop |
| Maintainability | 8.5 | `Store` split into `api/_evaluate/_accept/_builders/_queries`, a major improvement |
| Correctness & defensive validation | 9.0 | Strong validation in `SchemaIR`, write protocol, and where evaluation |
| Testability & regression coverage | 9.0 | Full `unittest` suite passes (338); new core-boundary/index tests added |
| Extensibility | 7.5 | Strong modularity, but Python where vs adapter compiler still requires sync discipline |
| Performance (current state) | 6.8 | `Ledger` indexing is in place, but storage is still in-memory and some export scans remain |
| **Composite (subjective weighted)** | **8.3** | Semantically mature core with good engineering shape for continued iteration |

**Conclusion**: `core` is now in a state where it can be independently reviewed, refactored, and evolved. The main focus shifts from structural cleanup to deeper performance work and incremental capability expansion.

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
- Keep protocol layer small and stable; version explicitly when semantics change

### 3.2 `schema` (`schema/schema_ir.py`) — 8.8/10

**Responsibility**
- `SchemaIR` validation, canonicalization, digest

**Strengths**
- Strong validation and early failure behavior
- `Store.__init__` now validates `SchemaIR` immediately

**Risks / Gaps**
- Some higher-level schema semantics (especially some mapping combinations) can still fail at runtime

**Recommendation**
- Gradually increase compile-time/static checks for mapping configuration combinations

### 3.3 `store.ledger` (`store/ledger.py`) — 8.2/10

**Responsibility**
- Append-only in-memory ledger and query API

**Strengths**
- Clear data model and strong auditability semantics
- In-memory indexes now implemented (claims/meta/claim_args/revokes)
- `rebuild_indexes()` supports test/debug workflows that directly mutate private lists

**Risks / Gaps**
- Still pure in-memory storage (capacity and durability limitations)
- Index maintenance logic depends on regression tests to prevent drift

**Recommendation**
- Preserve “lists are truth, indexes are cache”
- If scaling beyond current use, introduce a storage backend abstraction first

### 3.4 `store facade` (`store/api.py`, `store/_evaluate.py`, `store/_accept.py`, `store/_builders.py`, `store/_queries.py`) — 8.6/10

**Responsibility**
- Public `Store` API and orchestration across core modules

**Strengths**
- Successfully split from a monolithic file into focused private modules
- Public `Store` API remains stable while internal complexity drops
- `core` no longer statically imports adapters (`register_engine_evaluator`)

**Risks / Gaps**
- `api.py` still carries some legacy compatibility surface (e.g. `evaluate_dummy`)
- Engine entrypoint is still exposed on `Store` (a practical compromise, not a pure semantic-only facade)

**Recommendation**
- Continue keeping `api.py` thin
- Add more module-level unit tests for `_evaluate/_accept/_builders/_queries` over time

### 3.5 `evidence.write_protocol` — 8.8/10

**Responsibility**
- Append-only write protocol: write/add/retract/replace and ingest_key idempotency

**Strengths**
- Clear semantics and explicit errors
- Idempotency and revocation design are strong

**Risks / Gaps**
- Batch/transaction semantics remain MVP-grade

**Recommendation**
- Define transaction failure semantics before expanding batch writes

### 3.6 `policy` (`active/chosen/policy_ir`) — 8.0/10

**Responsibility**
- Active/chosen decisions and policy IR generation (core-relevant parts)

**Strengths**
- Deterministic chosen tie-break (`ingested_at + asrt_id`)
- Good alignment with `view.projector`

**Risks / Gaps**
- `multi/temporal` chosen path still contains MVP constraints (all active treated as chosen)

**Recommendation**
- If temporal semantics are expanded, update policy/view consistently with explicit rules

### 3.7 `view` (`view/projector.py`) — 8.4/10

**Responsibility**
- Project business-view facts from ledger

**Strengths**
- Clear handling for `functional/multi/temporal(record/current)`
- Hot path now uses `Ledger.find_claim_args(...)`

**Risks / Gaps**
- Performance still depends on total cost across policy + projector + per-claim arg reconstruction

**Recommendation**
- Keep semantics-first; continue performance work around `Ledger` query usage and call frequency

### 3.8 `rules` (`where_eval.py`, `rule_ir.py`) — 8.2/10

**Responsibility**
- Python evaluation for where-subset and RuleSpec/RuleRegistry execution

**Strengths**
- Well-scoped subset, strict validation, high-quality error reporting
- RuleRef expansion and cycle safety are implemented

**Risks / Gaps**
- Long-term sync cost remains with adapter-side `where_compile` (outside core, but affects evolution)

**Recommendation**
- Treat Python where semantics as the source of truth; enforce parity tests for new operators

### 3.9 `derivation` (`candidates.py`, `accept.py`) — 8.5/10

**Responsibility**
- Candidate representation and accept/materialization

**Strengths**
- `CandidateSet` shape is clear and idempotency metadata is complete
- `accept_candidate_set` supports both record and fact paths

**Risks / Gaps**
- Complex error categories still rely heavily on exception messages

**Recommendation**
- If diagnostics/audit tooling expands, gradually add more structured error typing

### 3.10 `mapping` (`mapping/canon.py`) — 8.3/10

**Responsibility**
- Mapping predicate conflict resolution and tie-break

**Strengths**
- Structured outputs (`candidates/decisions/conflicts`) are audit-friendly
- Clean integration boundary with `Store.resolve_mapping`

**Risks / Gaps**
- Performance remains dependent on ledger query patterns and metadata access

**Recommendation**
- Use profiling before deeper optimization in large datasets

## 4. Completed Improvements (Recent Work)

### 4.1 Architecture and Boundary Work
- `core` / `adapters` decoupling: `Store.evaluate_engine` now delegates through registration instead of static imports
- `Store.__init__` now validates `SchemaIR` immediately
- `Store` decomposed into `api/_evaluate/_accept/_builders/_queries`

### 4.2 Performance and Data Access
- Added in-memory indexes for `Ledger` claims/meta/claim_args/revokes
- Added `Ledger.find_claim_args(...)` and switched policy/view hotspots to use it
- `Ledger.find_meta(...)` now chooses indexed paths for filter combinations (including `kind`)
- `adapters/souffle/package.py` moved part of meta scanning to `find_meta(...)`

### 4.3 Tests and Guardrails
- Added `test_core_store_boundary_v1.py` (core boundary / engine registration behavior)
- Added `test_ledger_indexes_v1.py` (Ledger index semantics)
- Full `unittest` suite passes: `459 tests OK`

## 5. Current Technical Debt (Prioritized)

### P1: `Ledger` is still in-memory only (no persistence)

- **Impact**: limits capacity, restart recovery, and cross-process sharing
- **Risk**: becomes a hard blocker outside single-process / moderate-size usage
- **Recommendation**: define a storage abstraction before evaluating SQLite/file snapshot/embedded KV backends
- **Acceptance criteria**: append-only and query semantics remain unchanged; core tests remain green

### P1: No enforced performance regression baseline yet

- **Impact**: future refactors may silently regress runtime cost
- **Recommendation**: use `tools/benchmarks/bench_core_ledger_paths.py` with fixed sizes (e.g. 3k/10k) and track baseline output
- **Acceptance criteria**: a documented team workflow or CI job exists for benchmark checks

### P2: Adapter export path still has some full scans (`claims/claim_args`)

- **Impact**: large export package generation may become slower than necessary
- **Recommendation**: profile `adapters/souffle/package.py` and optimize only measured hotspots
- **Acceptance criteria**: export tests remain green and measured export latency improves

### P2: Python where vs adapter compiler dual implementation sync cost

- **Impact**: new where features can drift semantically
- **Recommendation**: keep `core.rules.where_eval` as baseline and require parity tests for all new operators

### P3: Legacy compatibility entrypoint `evaluate_dummy` still exists

- **Impact**: API surface is slightly noisier; tests emit deprecation warnings
- **Recommendation**: remove after usage audit and caller/test migration

## 6. Testing and Quality Evidence (Current)

- Full test suite: `459 tests OK`
- Boundary guardrail: `test_core_store_boundary_v1.py`
- Index semantics guardrail: `test_ledger_indexes_v1.py`
- Benchmark script: `tools/benchmarks/bench_core_ledger_paths.py`

Example benchmark values (`rows=3000`, `rounds=3`):

- `compute_chosen_for_predicate(country)`: `~11ms`
- `project_view_facts(record)`: `~47ms`
- `resolve_mapping_predicate(er:canon_of)`: `~23ms`

> Note: this benchmark is for relative regression tracking, not a production SLA target.

## 7. When to Update This Assessment

Reassess (or at least update scores/notes) after any of the following:

- major `Store` decomposition/consolidation changes
- `Ledger` query semantics or indexing strategy changes
- new `type_domain` / `cardinality` / where operators
- changes to `core` vs `adapter` boundary policy
- material changes to full-test or benchmark baselines
