# SDK Alignment Matrix (Current Implementation)

Scope: `src/factpy_kernel/sdk`

## 1. Capability Matrix

| Capability | Status | Notes |
|---|---|---|
| Schema declarations (`Entity/Identity/Field`) | Implemented | Supports dims/fact_key; `Meta.is_record` remains metadata only (not a behavior switch) |
| Schema compile/preflight helpers | Implemented | `build_authoring_schema_from_classes`, `compile_schema_from_classes`, `schema_preflight_from_classes` |
| Low-level write (`ref/set/add/retract`) | Implemented | Immediate ledger writes |
| Batch staging (`sdk.batch`) | Implemented | Preview/commit, dependency closure, wire plan export/replay |
| Read/write facade (`get/find/edit`) | Implemented | Snapshot + assertion view + editor |
| Ingest / provenance tooling | Implemented | `sdk.ingest`, `sdk.validate_provenance` |
| Audit queries (`explain_fact/conflicts`) | Implemented | Conflict-group and chosen diagnostics summary |
| Rule/Derivation object DSL | Implemented | `Rule/RuleRef/Derivation/Pred/Not/vars` |
| Registry facade (`SDKRegistry`) | Implemented | Apply/register/read/list surface |
| Registry advanced entrypoints (`apply_authoring_bundle` / `register_*_spec` / `upsert_schema_ir`) | Implemented | Authoring integration and compiled-spec workflows |

## 2. v1 Boundaries

| Topic | Current Behavior |
|---|---|
| Runtime vars unpack | `with vars() as (a,b)` is unsupported |
| String DSL | `sdk.run("...")` / `sdk.evaluate("...")` unsupported |
| `find` identity filtering | If identity filters are used, all identity fields are required |
| Dims filtering in `find` | Unsupported |
| `FieldAssertions.chosen` | Only for non-dim functional fields |
| `edit` behavior | Edit existing only; no implicit create |
| `accept` options | SDK facade only allows `approved_by`, `note`, `dry_run` |
| `explain_fact(*val_atoms)` | `*val_atoms` apply exact value-atom filtering; returns active_claims + chosen_asrt_id |
| `conflicts(pred_id, e_ref)` | Returns active_asrt_ids and chosen_asrt_id for the active conflict group |
| `RuleRef` and `expose` | Dependency auto-registration does not bypass `expose=True`; non-exposed RuleRef targets still fail |

## 3. Easy-to-Miss Behaviors

1. `Rule.dependency_rules()` collects direct where-level `RuleRef(RuleObj)` dependencies, not full transitive closure in one call.
2. `sdk.run(...)` auto-registers dependencies only when `registry` is not explicitly provided.
3. Field-head kwargs require at least one DSL value; not all kwargs must be DSL values.
4. Low-level `sdk.set/add` do not enforce cardinality strongly; cardinality checks are mainly enforced by batch/edit/ingest facades.
5. `find` without identity filters usually yields snapshots with `identity_available=False`.
6. `validate_provenance(dict)` uses flat keys and does not auto-unwrap nested `{"provenance": ...}`.

## 4. Deferred Items

| Item | Status |
|---|---|
| `sdk.create(...)` | Deferred |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | Deferred |
| Formal typed ingest item schema (TypedDict/dataclass) | Deferred |
| Dims-aware filtering in `find` | Deferred |
