# SDK Alignment Matrix (Current Implementation)

Updated: 2026-05-09 (post-L SDK ergonomics redesign)
Scope: `src/kernel/sdk`

> **post-L taxonomy note:** the v0.1 SDK top-level entrypoint is `FactGraph` (literal alias of `SDKStore`); the existing 30 flat methods are surfaced through 8 taxonomy namespaces + 2 sub-namespaces. The flat form (`sdk.<method>(...)` / `SDKStore.<method>(...)`) is permanently supported foundational API. See [04_api_surface.en.md §0](04_api_surface.en.md).

## 1. Layer Ownership

| Layer | Current Responsibility |
| --- | --- |
| `kernel.application` | canonical Python runtime authority; owns read/write/query/ingest/compiled derivation runtime DTOs and executors |
| `kernel.sdk` | Python product surface; owns schema/DSL authoring, `SDKStore` facade, snapshot/editor/batch outward objects, compatibility errors |
| `kernel.core` | low-level ledger/store/rules/evidence semantics |
| `service` / `agent` | delivery / product consumers; production runtime code must not add SDK runtime imports |

## 2. Capability Matrix

| Capability | Status | Current Behavior / Owner |
| --- | --- | --- |
| Schema declarations (`Entity/Identity/Field`) | Implemented | SDK authoring surface |
| Schema compile/preflight helpers | Implemented | SDK authoring helpers; `compile_schema_from_classes` may be used as an authoring import |
| Low-level writes (`ref/set/add/retract`) | Implemented | SDK convenience API; direct ledger writes retained for outward compatibility |
| Batch staging (`sdk.batch()`) | Implemented | SDK owns staging/wire/facade; application owns write planning/apply when operations fit application protocol |
| Read/write facade (`get/find/edit`) | Implemented | SDK owns snapshot/editor outward shape; application owns read DTO hydration/write planner |
| Assertion read views | Implemented | SDK facade shape |
| Ingest / provenance | Implemented | SDK owns descriptor parsing, diagnostics, and outward `IngestResult`; application owns normalized ingest executor for cache-resolvable items |
| Audit queries (`explain_fact/conflicts`) | Implemented | SDK facade over audit/core read helpers |
| Rule DSL + `sdk.run(rule)` | Implemented | SDK owns DSL/lowering; core/application execute runtime-normalized pieces |
| Query DSL + `sdk.run(query)` | Implemented | SDK owns `Query` DSL and outward row shape; application owns query runtime executor |
| Derivation + `sdk.evaluate/accept` | Implemented | SDK owns DSL sugar and compatibility; application owns compiled derivation evaluate/accept orchestration |
| Registry (`SDKRegistry`) | Implemented | SDK authoring-adjacent facade; application contracts do not accept `SDKRegistry` objects |

## 3. Hard Boundaries (Current Semantics)

| Topic | Current Behavior |
| --- | --- |
| SDK product surface | `kernel.sdk.__all__` exposes SDK user-facing surface / compatibility aliases only, not application internals |
| Application protocol | Does not accept SDK facade objects, SDK `Field` descriptors, or SDK DSL objects |
| service / agent imports | Production SDK imports are guarded by `test_sdk_consumer_boundary.py`; the only current allowlist entry is the agent extraction authoring helper `compile_schema_from_classes` |
| Legacy field semantics | `functional/temporal/dims/fact_key` are removed |
| `vars()` runtime unpack | `with vars() as (a,b)` is unsupported; named/factory forms are supported |
| String DSL | `sdk.run("...")` / `sdk.evaluate("...")` are unsupported |
| `find(...)` | No `temporal_view`; if identity filters are used, all identity fields are required |
| Assertion view surface | `.chosen` is removed; only `active/history/at/version` remain |
| `sdk.run(...)` dispatch | Rule and Query supported; Derivation is rejected with guidance to use `evaluate()` |
| `sdk.evaluate(...)` params | `temporal_view` is removed and fails explicitly |
| Rule `row_format` detail | `"tuple"` still works but emits `DeprecationWarning`; prefer `"dict"` |
| `SDKBatchTx` context | `with sdk.batch() as tx:` `__exit__` does not auto-commit or auto-rollback; explicit `commit()` is required |
| Wire export restriction | `BatchPlan.export()/to_json()` forbids raw `idref_v1` token values; entity refs should be represented via same-tx handles |
| `single` field semantics | `single` is a read-side scalar view; writes do not auto-prune older assertions |
| Derivation `head` semantics | Primary-key fields in `head` are compile-time hard errors |
| Cross-coordinate attr comparison | Only `==` on the same entity type and same `primary_key` field is allowed |
| RuleRef constraints | Target must be `expose=True`; `RuleRef` is forbidden inside `Not(...)` body |
| Query head constraints | Only `Entity(var)` or `Entity.field(...)`; field projection supports only `single` fields |
| Registry vs multi-head | `evaluate` supports multi-head; `register_derivation(...)` is still single-head-oriented |

## 4. Deferred Items

| Item | Status |
| --- | --- |
| `sdk.create(...)` | Deferred |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | Deferred |
| Formal typed ingest schema (TypedDict/dataclass) | Deferred |
| Temporal write semantics in Rule/Derivation head (`valid_from/valid_to/version`) | Deferred |
| Native multi-head publishing semantics in Registry | Deferred |
| Physical SDK god-file split (`store.py` / `batch.py` / `facade.py`) | Deferred; this cleanup completed runtime delegation, not line-count reduction |
| Full exception hierarchy migration | Deferred; application runtime uses DTO error shapes, while SDK product-domain errors remain SDK-owned |
