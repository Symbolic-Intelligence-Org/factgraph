# Core Architecture Overview (factpy_kernel)

- Scope: `src/factpy_kernel/core`
- Last updated: 2026-02-28
- Code baseline: `Store` is now grouped into public `runtime/evaluation/queries/builders` modules; `Ledger` is now a SQLite write-through cache with persistence
- Audience: developers who need to understand core semantics, navigate the codebase, and continue core development

## 1. Scope and Positioning

This document covers only the **semantic core layer (`core`)**. It does **not** describe implementation details of:

- `src/factpy_kernel/adapters/souffle` (engine/export adapter)
- `src/factpy_kernel/sdk` (developer-friendly Python facade)
- `src/factpy_kernel/authoring` (DSL/preflight/workflow)
- `src/factpy_kernel/audit` (audit query/UI/DTO)

The responsibility of `core` is to provide a **semantically stable kernel**: fact representation, schema constraints, append-only evidence storage, policy/view semantics, Python-path rule evaluation, candidate generation/materialization, and mapping resolution.

## 2. Current Directory Structure (core)

```text
src/factpy_kernel/core/
  __init__.py              # core public API facade (stable entrypoints)
  protocol/                # typed tuple / idref / digest protocols
  schema/                  # SchemaIR validation, canonicalization, digest
  store/                   # Ledger + Store runtime + evaluation/query/builders entrypoints
  evidence/                # append-only write protocol (set/add/retract/replace)
  policy/                  # active/chosen/policy_ir
  view/                    # Python-side business view projection
  rules/                   # where Python evaluation + RuleSpec/RuleRegistry
  derivation/              # CandidateSet + accept materialization
  mapping/                 # mapping conflict resolution and tie-break
```

## 3. Module Responsibility Map (Read This First)

| Module | Main Responsibility | Key Entrypoints | Main Dependencies |
|---|---|---|---|
| `protocol.tup_v1` | canonical typed tuple encoding, claim_arg reconstruction | `canonical_bytes_tup_v1`, `claim_args_from_rest_terms` | none |
| `protocol.idref_v1` | stable entity reference (`idref`) encoding | `encode_idref_v1` | `protocol.digests` |
| `schema.schema_ir` | SchemaIR validation, canonicalization, digest | `ensure_schema_ir`, `schema_digest` | `protocol.digests` |
| `store.ledger` | append-only SQLite ledger + in-memory read cache | `append_assertion`, `append_revocation`, `find_*` | core data classes |
| `evidence.write_protocol` | append-only write/retract/replace protocol, ingest-key idempotency | `set_field`, `add_field`, `retract_by_asrt`, `replace_field` | `Ledger`, `protocol.*` |
| `policy.active/chosen` | active checks and chosen selection | `is_active`, `compute_chosen_for_predicate` | `Ledger`, `write_protocol` |
| `view.projector` | project business-view facts from ledger | `project_view_facts`, `project_view_facts_with_audit` | `policy`, `Ledger` |
| `rules.where_eval` | Python interpreter for where-subset | `evaluate_where` | projected view facts |
| `rules.rule_ir` | RuleSpec/RuleRegistry/RuleRef execution and cycle safety | `run_rule` | `where_eval`, `Store` |
| `derivation.candidates` | candidate set and key digest | `CandidateSet`, `make_candidate` | `protocol` |
| `derivation.accept` | accept candidates and materialize into ledger | `accept_candidate_set` | `Ledger`, `write_protocol` |
| `mapping.canon` | mapping conflict resolution and tie-break | `resolve_mapping_predicate` | `Ledger`, `policy` |
| `store.runtime` | `Store` facade + engine evaluator registration | `Store`, `register_engine_evaluator` | `store.evaluation`, `store.queries`, `store._accept` |
| `store.api` | compatibility shim for `store.runtime` | `Store`, `register_engine_evaluator` | `store.runtime` |
| `store.evaluation` | public entrypoint for `Store.evaluate(...)` | `evaluate_store` | `view`, `where_eval`, `store.builders` |
| `store.builders` | candidate construction, record materialization spec, value coercion | helper functions | `protocol`, `derivation` |
| `store.queries` | explain/conflicts/resolve_mapping public entrypoints | `explain_fact`, `conflicts`, `resolve_mapping` | `policy`, `mapping` |
| `store._accept` | `Store.accept(...)` flow | `accept_store_candidate` | `policy_ir`, `derivation.accept` |

## 4. Core Data Model (Semantic Foundation)

`Ledger` maintains the following append-only structures (`src/factpy_kernel/core/store/ledger.py`):

- `Claim`
  - Assertion primary row: `asrt_id`, `pred_id`, `e_ref`, `rest_terms`
- `ClaimArg`
  - Row-form expanded arguments for `Claim` (useful for projection/export/audit)
- `MetaRow`
  - Metadata attached to assertion/retraction actions (`kind` in `str/num/bool/time/json`)
- `Revokes`
  - Revocation edge: `revoker_asrt_id -> revoked_asrt_id`

Design principles:

- **append-only**: add rows, do not mutate facts in place
- **explicit revocation**: invalidation is modeled with `Revokes`, not by mutating `Claim`
- **metadata travels with assertions**: `ingested_at`, `run_id`, `materialize_id`, etc. attach via `MetaRow`
- **auditability**: history and revocation paths remain available for explanation and replay
- **durable truth**: SQLite tables are the source of truth; in-memory indexes are read caches

## 5. Current Ledger Structure (Performance and Persistence)

`Ledger` now uses a **SQLite write-through cache**:

- SQLite tables are the durable truth (`claims / claim_args / meta_rows / revokes / ingest_keys / ledger_meta`)
- in-memory dict/set/list indexes are read caches, rebuilt on load and updated after successful commits
- `Ledger(path=":memory:")` remains the default in-memory mode

In-memory indexes include:

- `claims`
  - `_claim_by_asrt_id`
  - `_claims_by_pred_id`
  - `_claims_by_e_ref`
  - `_claims_by_pred_e_ref`
- `claim_args`
  - `_claim_args_by_asrt_id`
- `meta`
  - `_meta_by_asrt_id`
  - `_meta_by_key`
  - `_meta_by_kind`
  - `_meta_by_asrt_id_key`
  - `_meta_by_asrt_id_key_kind`
- `revokes`
  - `_revoked_asrt_ids`
  - `_first_revoker_by_revoked_asrt_id`

Notes:

- Cache updates happen only after SQLite commits succeed
- `rebuild_indexes()` is now a compatibility no-op, not a repair mechanism
- Tests that need to replace meta rows should use `ledger._force_replace_meta_rows(...)`

## 6. Core Runtime Flows (Most Useful During Development)

### 6.1 Write Flow (append-only)

```mermaid
flowchart LR
  A["write_protocol.set_field/add_field"] --> B["Ledger.append_assertion"]
  B --> C["SQLite transaction + write-through cache update"]
  D["write_protocol.retract_by_asrt"] --> E["Ledger.append_revocation"]
  E --> C
```

Key points:

- `write_protocol` handles input validation, ingest-key idempotency, retract/replace semantics
- `Ledger` owns transaction boundaries, persistence, and cache maintenance

### 6.2 View Flow (policy + projector)

```mermaid
flowchart LR
  A["Ledger claims/meta/revokes"] --> B["policy.active"]
  B --> C["policy.chosen"]
  C --> D["view.projector.project_view_facts"]
  D --> E["view facts: pred -> tuples"]
```

Key points:

- `functional`: chosen selection via `ingested_at` + `asrt_id`
- `multi`: all active assertions are visible
- `temporal`: supports `record/current` view semantics (Python path)

### 6.3 Rule + Candidate Flow (Python path)

```mermaid
flowchart LR
  A["Store.evaluate(mode='python')"] --> B["view.projector"]
  B --> C["rules.where_eval.evaluate_where"]
  C --> D["store.builders.*_candidates_from_bindings"]
  D --> E["CandidateSet list"]
```

### 6.4 Materialization Flow (accept)

```mermaid
flowchart LR
  A["Store.accept"] --> B["store._accept.accept_store_candidate"]
  B --> C["derivation.accept.accept_candidate_set"]
  C --> D["write_protocol + Ledger"]
```

### 6.5 Engine Flow Boundary (core vs adapter)

`core` does not statically import `adapters`. `Store.evaluate(mode='engine')` uses a registration-based injection point:

- core side: `register_engine_evaluator(...)` (`store/runtime.py`; `store/api.py` only forwards for compatibility)
- adapter side: `adapters/souffle/__init__.py` auto-registers `evaluate_store_engine` on import

This guarantees:

- `core` can be imported and tested independently
- engine implementations are replaceable

## 7. Store Structure (Current Grouping)

`Store` is now organized as **public grouped modules + compatibility shim + a small private implementation tail**:

- `store/runtime.py`
  - `Store` facade
  - `register_engine_evaluator`
  - small compatibility helpers
- `store/evaluation.py`
  - public entrypoint for `Store.evaluate(...)`
- `store/queries.py`
  - public explain/conflicts/resolve_mapping helpers
- `store/builders.py`
  - public candidate-building / coercion / record-spec helpers
- `store/api.py`
  - compatibility shim for legacy imports
- `store/_accept.py`
  - current `Store.accept(...)` implementation path
- `store/_evaluate.py`, `store/_builders.py`, `store/_queries.py`
  - compatibility-backed implementation modules

Maintenance rules:

- Public API remains on `Store`
- New code should prefer `runtime/evaluation/queries/builders`
- Legacy `api.py` / `_*.py` paths remain only for compatibility and should not be the default entrypoints for new work

## 8. Core Invariants (Must Understand Before Changing Code)

These constraints should not be broken casually:

1. `Store.__init__` must validate `SchemaIR`
   - currently done via `ensure_schema_ir(...)` at initialization time
2. `Ledger` is append-only
   - do not introduce direct mutation/overwrite write APIs for claims/meta/revokes
3. `revokes` represents invalidation; `active` is policy-derived
   - do not persist an “active” flag back onto claims
4. `chosen` must be deterministic
   - tie-break uses `ingested_at` + `asrt_id` lexical order
5. `core` must not statically import `adapters`
   - engine behavior must come through registration
6. SQLite tables are truth; in-memory indexes are caches
   - do not bypass write APIs and mutate SQLite/cache state independently
   - tests that need forced meta replacement must use `_force_replace_meta_rows(...)`, not `rebuild_indexes()`

## 9. Developer Extension Guide (Common Changes)

### 9.1 Add a new `type_domain`

At minimum review these places:

- `protocol/tup_v1.py` (encoding/validation)
- `store/builders.py` (`coerce_value_for_tag`)
- `adapters/souffle` (representation/export/compiler if engine path needs it)
- tests (Python evaluate, view/export parity)

### 9.2 Add/change `cardinality`

At minimum review:

- `policy/chosen.py`
- `view/projector.py`
- `record_staging.py`
- `schema/schema_ir.py`
- `adapters/souffle/souffle_view_gen.py`

### 9.3 Add a where operator (Python semantics is the baseline)

- define semantics and validation in `core/rules/where_eval.py` first
- then mirror in `adapters/souffle/where_compile.py`
- add parity tests (Python vs engine)

### 9.4 Add a new Store capability

Placement guidance:

- query/diagnostic behavior: `store/queries.py`
- candidate/build logic: `store/builders.py`
- evaluation orchestration: `store/evaluation.py`
- accept/materialization orchestration: `store/_accept.py`
- `runtime.py` should remain the facade + registration point
- `api.py` should remain compatibility-only

## 10. Debugging and Test Entry Points

Useful test files:

- `src/factpy_kernel/tests/test_core_store_boundary_v1.py`
  - validates no static adapter imports in core and engine evaluator registration behavior
- `src/factpy_kernel/tests/test_core_store_grouped_modules_v1.py`
  - validates grouped `Store` public entrypoints and compatibility shim behavior
- `src/factpy_kernel/tests/test_ledger_indexes_v1.py`
  - validates atomic ledger entrypoints, index query semantics, and first-revoker semantics
- `src/factpy_kernel/tests/test_view_projector_v1.py`
- `src/factpy_kernel/tests/test_view_projector_audit_v1.py`
- `src/factpy_kernel/tests/test_write_protocol_v1.py`

Full regression command:

```bash
python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'
```

Core-path benchmark script:

```bash
python tools/benchmarks/bench_core_ledger_paths.py --rows 3000 --rounds 3
```

## 11. Known Caveats (Avoid Common Pitfalls)

- If a test needs to replace meta rows, use `ledger._force_replace_meta_rows(...)`; do not rely on `rebuild_indexes()`
- `Store.evaluate(mode='engine')` will raise an “engine evaluator not registered” error until an adapter is imported
- In core changes, semantic correctness comes before speed; persistence/cache optimizations must preserve append-only and query semantics exactly
