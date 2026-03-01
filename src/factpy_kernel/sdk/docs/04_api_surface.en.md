# SDK API Surface Index (v1)

Quick index of `from factpy_kernel.sdk import ...` and major public APIs.

## 1. Top-Level Exports

### Schema / Store / Registry
- `Entity`
- `Field`
- `Identity`
- `SDKStore`
- `SDKRegistry`

### DSL
- `Rule`
- `RuleRef`
- `Derivation`
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### Schema Helpers
- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### Ingest / Provenance
- `IngestResult`
- `ValidationReport`

### Errors
- `SDKSchemaError`
- `SDKStoreError`
- `SDKRegistryError`
- `EntityNotFoundError`
- `FrozenSnapshotError`
- `CardinalityError`
- `EditorClosedError`

## 2. `SDKStore` Main Methods

- `from_schema_classes(..., ledger=None, ledger_path=None)`
- `batch(...)`
- `get(...)`
- `find(...)`
- `edit(...)`
- `ingest(...)`
- `validate_provenance(...)`
- `ref(...)`
- `set(...)`
- `add(...)`
- `retract(...)`
- `run(...)`
- `evaluate(...)`
- `evaluate_compiled(...)`
- `accept(...)`
- `accept_many(...)`
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

Notes:
- `from_schema_classes(..., ledger_path="...")` is the recommended file-backed restore path.
- First creation writes `schema_digest`; later restores validate schema compatibility.

## 3. `SDKRegistry` Main Methods

- `apply_schema_classes(...)`
- `apply_authoring_bundle(...)`
- `read_manifest(...)`
- `upsert_schema_ir(...)`
- `register_rule_spec(...)`
- `register_rule(...)`
- `register_derivation_spec(...)`
- `register_derivation(...)`
- `get_schema_entry(...)`
- `list_rule_ids(...)`
- `list_derivation_ids(...)`
- `list_rule_versions(...)`
- `list_derivation_versions(...)`
- `list_apply_run_ids(...)`
- `list_apply_runs(...)`
- `show_apply_run(...)`
- `get_latest_rule_spec(...)`
- `get_latest_derivation_spec(...)`
- `read_rule_spec(...)`
- `read_derivation_spec(...)`

Notes (easy-to-misuse methods):
- `read_manifest()`: reads registry manifest index; if manifest file does not exist yet, returns default empty shape.
- `upsert_schema_ir(...)`: writes compiled `schema_ir` directly (bypasses `apply_schema_classes` path).
- `get_schema_entry()`: returns schema entry metadata (for example `path`), not the schema_ir payload itself.

## 4. Common Facade Return Objects

- `EntitySnapshot`
  - `ref`, `entity_type`, `identity_available`, `identity`, `assertions`, `field(name)`
- `EntityEditor`
  - `preview()`, `commit(meta=...)`, `rollback()`, `ref`, `entity_type`
- `FieldEditor`
  - `set(...)`, `add(...)`, `retract(asrt_id=..., meta=...)`

## 5. Batch Objects

- `SDKBatchTx`
  - `entity(...)`, `preview(...)`, `commit(...)`, `save(...)`
- `BatchPlan`
  - `ops`, `warnings`, `export(sdk)`, `to_json(sdk)`, `apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`, `to_json()`, `from_dict(...)`, `from_json(...)`, `apply(sdk, strict_schema=True)`

## 6. Derivation Quick Guide (v2)

### 6.1 Default path is inferred from `head`

| Head shape | Default behavior | Evaluate output |
|---|---|---|
| `EntityType(...)` | entity path | one entity candidate + dependent fact candidates |
| `EntityType.field(...)` | fact path | fact candidates |
| no `head` (`target + head_vars`) | fact-only compatibility path | fact candidates |

### 6.2 `CandidateSet` and accept APIs

- `sdk.evaluate(...)` returns `list[CandidateSet]` with key v2 fields:
  - `candidate_id` (per-run handle)
  - `candidate_key` (cross-run stable key)
  - `candidate_kind` (`fact` / `entity`)
- `sdk.accept(...)` accepts one candidate.
- For dependency graphs, prefer `sdk.accept_many(..., mode="atomic")`.

See also:
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.en.md` (Derivation DSL and head rules)

## 7. Common call templates (v2)

### 7.1 fact derivation

```python
with vars("p", "c") as (p, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=p, country_copy=c),
        where=[Pred("person:country", p, c)],
    )

cands = sdk.evaluate(drv, mode="python")
fact = next(c for c in cands if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 7.2 entity derivation (dependency graph)

```python
with vars("u", "l") as (u, l):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        head=Speaks(user=u, language=l),
        where=[Pred("person:country", u, "de"), Pred("user:lang_pref", u, l)],
    )

cands = sdk.evaluate(drv, mode="python")
rows = sdk.accept_many(cands, mode="atomic")
```

### 7.3 incomplete identity

```python
entity = next(c for c in cands if c.candidate_kind == "entity")
sdk.accept(entity, identity_override={"source_id": "u-001"})
```

Do not use `materialize_as` / `id_policy`.
