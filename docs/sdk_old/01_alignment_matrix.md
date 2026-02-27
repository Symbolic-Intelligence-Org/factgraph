# SDK Alignment Matrix (Current Implementation)

Scope: `src/factpy_kernel/sdk` runtime behavior.

This matrix replaces old "missing/new" phrasing and reflects current shipped state.

## 1. Capability matrix

| Capability | Status | Notes |
| --- | --- | --- |
| Schema declarations (`Entity/Identity/Field`) | Implemented | Includes `Meta.is_record`, dims/fact_key support |
| Schema compile/preflight helpers | Implemented | `compile_schema_from_classes`, `schema_preflight_from_classes` |
| Low-level write (`ref/set/add/retract`) | Implemented | Immediate ledger writes |
| Batch staging (`sdk.batch`) | Implemented | Preview/commit, include_deps, wire plan export/replay |
| Read facade (`sdk.get`, `sdk.find`) | Implemented | Snapshot + assertions API |
| Edit facade (`sdk.edit`) | Implemented | Context manager over private batch tx |
| Ingest (`sdk.ingest`) | Implemented | Dict item schema + per-item diagnostics |
| Provenance validation (`sdk.validate_provenance`) | Implemented | `derivation_v1` standard |
| Rule object DSL (`Rule`, `RuleRef`, `Pred`, `Not`, `vars`) | Implemented | Runtime object DSL path is primary |
| Derivation object DSL (`Derivation`) | Implemented | `evaluate` + `accept` flow |
| Registry facade (`SDKRegistry`) | Implemented | `apply_schema_classes`, register/read/list helpers |

## 2. Behavior boundaries that are intentional in v1

| Topic | Current behavior |
| --- | --- |
| Runtime vars unpack | `with vars() as (p, c)` not supported at runtime SDK; use named/factory forms |
| String DSL in SDK store | `sdk.run("...")` / `sdk.evaluate("...")` rejected |
| `find` identity filters | If identity filters are used, all identity fields must be provided |
| Dims filtering in `find` | Not supported yet (raises `SDKSchemaError`) |
| `FieldAssertions.chosen` | Only valid for functional fields without dims |
| `edit` creation behavior | No implicit create; missing entity -> `EntityNotFoundError` |
| Ingest reserved meta | Top-level reserved key -> raise; item-level invalid meta -> diagnostics error |
| Accept options | SDK facade limits `accept` options to `approved_by`, `note`, `dry_run` |

## 3. Stable split between write paths

| API | Identity requirement | Best use |
| --- | --- | --- |
| `sdk.edit(Type, **identity)` | Required | Single-entity edits when identity is known |
| `sdk.ingest(items, ...)` | Not required | External/scripted writes, or only `ref + asrt_id` is available |
| `sdk.batch()` | Identity at handle creation time | Graph construction + preview/replay |

## 4. Known gaps (deferred by design)

| Item | Status | Trigger to revisit |
| --- | --- | --- |
| `sdk.create(...)` | Deferred | Define create semantics separate from edit/upsert |
| `sdk.save(plain_entity)` + snapshot-to-entity workflow | Deferred | Finalize diff/full-write semantics first |
| Ingest formal item types (TypedDict/dataclass) | Deferred | After additional real ingest scenarios confirm stable shape |
| `find` dims-aware filtering | Deferred | Add query semantics and tests for dims matching |

## 5. Notes for future changes

When any boundary above changes, update this matrix and the matching detailed doc in the same PR:

- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
