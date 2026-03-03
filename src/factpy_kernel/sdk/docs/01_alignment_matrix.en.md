# SDK Alignment Matrix (Current Implementation)

Updated: 2026-03-03  
Scope: `src/factpy_kernel/sdk`

## 1. Capability Matrix

| Capability | Status | Current Behavior |
| --- | --- | --- |
| Schema declarations (`Entity/Identity/Field`) | Implemented | `Field.cardinality` supports only `single|multi`; `Identity(primary_key=...)` is active |
| Schema compile/preflight helpers | Implemented | `build_authoring_schema_from_classes` / `compile_schema_from_classes` / `schema_preflight_from_classes` |
| Low-level writes (`ref/set/add/retract`) | Implemented | Direct ledger writes with SDK-side type checks |
| Batch staging (`sdk.batch()`) | Implemented | `preview/commit`, dependency closure, wire plan export/replay |
| Read/write facade (`get/find/edit`) | Implemented | Snapshot is read-only; editor allows field writes only |
| Assertion read views | Implemented | `active` / `history` / `.at(t)` / `.version(v)` |
| Ingest / provenance | Implemented | `sdk.ingest(...)`, `sdk.validate_provenance(...)` |
| Audit queries (`explain_fact/conflicts`) | Implemented | Active-assertion diagnostics; `single` fields include `chosen_asrt_id` |
| Rule DSL + `sdk.run(rule)` | Implemented | Object DSL supported; `row_format` applies only to Rule path |
| Query DSL + `sdk.run(query)` | Implemented | Query always returns `list[dict]` |
| Derivation + `sdk.evaluate/accept` | Implemented | `head` shape infers fact/entity candidate kind; multi-head evaluate is flattened |
| Registry (`SDKRegistry`) | Implemented | Complete schema/rule/derivation register + read surface |

## 2. Hard Boundaries (Current Semantics)

| Topic | Current Behavior |
| --- | --- |
| Legacy field semantics | `functional/temporal/dims/fact_key` are removed |
| `vars()` runtime unpack | `with vars() as (a,b)` is unsupported; named/factory forms are supported |
| String DSL | `sdk.run("...")` / `sdk.evaluate("...")` are unsupported |
| `find(...)` | No `temporal_view`; if identity filters are used, all identity fields are required |
| Assertion view surface | `.chosen` is removed; only `active/history/at/version` remain |
| `sdk.run(...)` dispatch | Rule and Query supported; Derivation is rejected with guidance to use `evaluate()` |
| `sdk.evaluate(...)` params | `temporal_view` is removed and fails explicitly |
| Derivation `head` semantics | Primary-key fields in `head` are compile-time hard errors |
| Cross-coordinate attr comparison | Only `==` on the same entity type and same `primary_key` field is allowed |
| RuleRef constraints | Target must be `expose=True`; `RuleRef` is forbidden inside `Not(...)` body |
| Query head constraints | Only `Entity(var)` or `Entity.field(...)`; field projection supports only `single` fields |
| Registry vs multi-head | `evaluate` supports multi-head; `register_derivation(...)` is still single-head-oriented |

## 3. Deferred Items

| Item | Status |
| --- | --- |
| `sdk.create(...)` | Deferred |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | Deferred |
| Formal typed ingest schema (TypedDict/dataclass) | Deferred |
| Temporal write semantics in Rule/Derivation head (`valid_from/valid_to/version`) | Deferred |
| Native multi-head publishing semantics in Registry | Deferred |
