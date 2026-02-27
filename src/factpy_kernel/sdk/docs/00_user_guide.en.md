# FactPy SDK User Guide

> Implementation baseline: commit `7252468`  
> This guide follows the real SDK behavior in `src/factpy_kernel/sdk` and is organized as: schema -> write -> read -> derivation.

---

## Table of Contents

1. [Setup and Initialization](#1-setup-and-initialization)
2. [Schema Definition](#2-schema-definition)
3. [Writing Data with `sdk.batch`](#3-writing-data-with-sdkbatch)
4. [Reading Data with `sdk.get` / `sdk.find`](#4-reading-data-with-sdkget--sdkfind)
5. [Editing Data with `sdk.edit`](#5-editing-data-with-sdkedit)
6. [External Import with `sdk.ingest`](#6-external-import-with-sdkingest)
7. [Rules and Derivations](#7-rules-and-derivations)
8. [Provenance Validation](#8-provenance-validation)
9. [Which Write API Should I Use?](#9-which-write-api-should-i-use)
10. [Error Handling Quick Reference](#10-error-handling-quick-reference)
11. [Registry Publish and Read: `SDKRegistry`](#11-registry-publish-and-read-sdkregistry)
12. [API Surface Additions (Advanced)](#12-api-surface-additions-advanced)

---

## Status Labels Used in This Guide

| Label | Meaning |
|------|------|
| **Stable Contract** | Externally committed behavior; safe for strict tests |
| **Current Behavior** | True in current implementation, may be optimized later |
| **Planned** | Not implemented yet; direction is known |

Terminology:
- `canonical ref` = canonical `idref_v1` token (string).

---

## 1. Setup and Initialization

### 1.1 Initialize Store

```python
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore

sdk = SDKStore.from_schema_classes([User, Country, Language, LivesIn])
```

Stable Contract:
- `SDKStore.from_schema_classes(...)` compiles schema first, then builds `Store`.
- `classes` must be a non-empty list of `Entity` subclasses, otherwise `SDKStoreError`.

### 1.2 Schema Preflight (CI / import time)

```python
from factpy_kernel.sdk import schema_preflight_from_classes

preflight = schema_preflight_from_classes([User, Country, LivesIn])

print(preflight["ok"])
print(preflight.get("warnings", []))
print(preflight.get("summary", {}))
```

Stable Contract:
- Returns a `dict` DTO (not an object).
- Core keys include `ok`, `warnings`, `errors`, `diagnostics`, and `summary` (on success).
- `schema_preflight_from_classes(...)` is independent from `SDKStore.from_schema_classes(...)`.

---

## 2. Schema Definition

### 2.1 Basic Declaration

```python
from factpy_kernel.sdk import Entity, Field, Identity

class Country(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="functional", pred_id="country:name")
    population: int = Field(cardinality="functional", pred_id="country:population")

class User(Entity):
    source_system: str = Identity()
    source_id: str = Identity()
    name: str = Field(cardinality="multi", pred_id="user:name")
    country: Country = Field(cardinality="functional", pred_id="user:country")
    age: int = Field(cardinality="functional", pred_id="user:age")
```

Stable Contract:
- Every `Entity` subclass must declare at least one `Identity`, otherwise `SDKSchemaError` at class definition time.
- Valid cardinalities are `functional`, `multi`, and `temporal` (enforced during schema compile).

### 2.2 `Identity(...)` Parameters

| Parameter | Meaning |
|------|------|
| `default=...` | Fixed default value |
| `default_factory="uuid4"` | Auto-generate identity when omitted |

Current Behavior:
- Both `sdk.ref(...)` and `tx.entity(...)` use the same identity resolution path.
- SDK v1 has explicit support for `uuid4` default factory behavior in `ref` path.

### 2.3 `Field(...)` Parameters

| Parameter | Required | Meaning |
|------|------|------|
| `cardinality` | ✅ | `functional` / `multi` / `temporal` |
| `pred_id` | Recommended | Explicit predicate id |
| `name` | - | Name override |
| `aliases` | - | Alias list |
| `display_name` | - | Display name |
| `description` | - | Description text |
| `value_name` | - | Value argument name |
| `fact_key` | - | Conflict-key dims subset |
| `dims` | - | Dimension specs |
| `type_domain` | - | Override inferred type domain |

Stable Contract:
- If `fact_key` is set, all entries must be dims of that field.
- `fact_key` is invalid when `dims` is empty.

### 2.4 Reified Records

```python
class LivesIn(Entity):
    class Meta:
        is_record = True

    uid: str = Identity(default_factory="uuid4")
    user: User = Field(cardinality="functional", pred_id="livesin:user")
    country: Country = Field(cardinality="functional", pred_id="livesin:country")
    since: int = Field(cardinality="functional", pred_id="livesin:since")
```

Stable Contract:
- Schema compile adds `LivesIn:exists` predicate.
- Batch writes on records auto-emit record-exists op when needed.

### 2.5 Common Annotation Mapping

| Python Type | type_domain |
|------|------|
| `str` | `string` |
| `int` | `int` |
| `bool` | `bool` |
| `float` | `float64` |
| `bytes` | `bytes` |
| `datetime` | `time` |
| `UUID` | `uuid` |
| other `Entity` subclass | `entity_ref` |

Current Behavior:
- String annotations are supported (`"str"`, `"datetime"`, `"uuid"`, `"entity_ref"`, etc.).
- Unknown annotations fall back to `entity_ref`.

### 2.6 Plain Object vs Managed Handle

```python
# Plain in-memory object (no store binding)
alice = User(source_id="u-001")
alice.name = "Alice"  # normal assignment

# Managed by sdk.batch()
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice_h = tx.entity(User, source_id="u-001")
    alice_h.name.add("Alice")  # managed API
    tx.commit()
```

Stable Contract:
- `.set/.add/.retract` are managed-handle capabilities (batch/edit), not plain object capabilities.

---

## 3. Writing Data with `sdk.batch`

### 3.1 Basic Flow

```python
with sdk.batch(meta={"trace_id": "import-001", "source": "HR"}) as tx:
    de = tx.entity(Country, source_system="ISO3166", source_id="DE")
    de.name.set("Germany")
    de.population.set(83_000_000)

    alice = tx.entity(User, source_system="APP", source_id="u-001")
    alice.name.add("Alice")
    alice.country.set(de)

    plan = tx.preview()
    res = tx.commit()
```

Stable Contract:
- `preview()` is read-only and repeatable.
- `SDKBatchTx` context manager does not auto-commit.

### 3.2 Cardinality Rules on Batch Handles

| Field Cardinality | Allowed | Forbidden |
|------|------|------|
| `functional` | `.set(value)` | `.add(value)` |
| `multi` | `.add(value)` | `.set(value)` |
| any | `.retract(assertion_id=...)` | retract-by-value |

Stable Contract:
- `entity_ref` fields accept managed handle or canonical ref token, not business strings.

### 3.3 Retract

```python
with sdk.batch(meta={"trace_id": "fix-001"}) as tx:
    alice = tx.entity(User, source_system="APP", source_id="u-001")
    alice.name.retract(assertion_id="asrt_old_xxx")
    tx.commit()
```

Stable Contract:
- Retract is by `assertion_id` only.

### 3.4 Wire Plan

```python
with sdk.batch(meta={"trace_id": "t1"}) as tx:
    alice = tx.entity(User, source_id="u-001")
    alice.name.add("Alice")
    wire_json = tx.preview().to_json(sdk)

from factpy_kernel.sdk.batch import WireBatchPlan
WireBatchPlan.from_json(wire_json).apply(sdk, strict_schema=True)
```

Current Behavior:
- `strict_schema=True` validates schema digest.
- Raw entity-ref token values in staged field ops can commit, but are rejected by wire export; use handle references for replayable wire plans.

### 3.5 Meta Merge Priority

`commit_meta > field_op_meta > entity_meta > batch_meta`

### 3.6 Dependency Closure (`include_deps`)

Stable Contract:
- `include_deps=True` (default) includes referenced handles automatically.
- With `include_deps=False`, missing dependencies fail at `preview()`/`commit()`.

---

## 4. Reading Data with `sdk.get` / `sdk.find`

### 4.1 `sdk.get(...)`

```python
alice = sdk.get(User, source_system="APP", source_id="u-001")
```

Stable Contract:
- Identity kwargs only; non-identity args -> `SDKSchemaError`.
- Returns `EntitySnapshot | None`.
- Snapshot from `get` has `identity_available=True`.

Current Behavior:
- Identity fields using `default_factory="uuid4"` must still be explicitly provided to `get(...)`.

### 4.2 `sdk.find(...)`

```python
rows = sdk.find(User, age=30)
rows = sdk.find(User, name="Alice")
rows = sdk.find(User, temporal_view="current", limit=20)
```

Filter Semantics (Stable Contract):
- `functional`: exact match
- `multi` / `temporal`: containment match in current tuple
- `entity_ref`: exact canonical-ref match (`ref` or `EntitySnapshot` accepted)

Stable Contract:
- `temporal_view` is `record` or `current`.
- `limit` must be non-negative int.
- Unknown filters -> `SDKSchemaError`.

Current Behavior:
- Dims filtering is not supported.
- If identity filters are used, all identity fields must be present.

### 4.3 `EntitySnapshot` API

```python
snap = sdk.get(User, source_system="APP", source_id="u-001")
snap.ref
snap.identity_available
snap.identity
snap.assertions.name.active
snap.assertions.name.history
snap.assertions.country.chosen
```

Stable Contract:
- Snapshot is read-only (`FrozenSnapshotError` on assignment).
- `.chosen` is valid only for non-dim functional fields.

### 4.4 `temporal_view` vs `assertions.history`

Stable Contract:
- `temporal_view` changes current visible values and entity visibility.
- `assertions.<field>.history` comes from ledger history and is not affected by `temporal_view`.

### 4.5 `identity_available` in `find` Results

Current Behavior:
- `find` without identity filters usually yields `identity_available=False`.
- `find` with full identity filters yields `identity_available=True`.

---

## 5. Editing Data with `sdk.edit`

### 5.1 Basic Context-Manager Usage

```python
with sdk.edit(User, source_system="APP", source_id="u-001") as user:
    user.name.add("Alicia")
    user.name.retract(asrt_id="asrt_old_name_xxx")
    user.country.set(fr_ref)
    user.age.set(31)
```

Stable Contract:
- Normal exit -> auto commit.
- Exception exit -> auto rollback; exception is not swallowed.
- Missing entity -> `EntityNotFoundError`.

### 5.2 Edit Records

```python
with sdk.edit(LivesIn, uid="li-uuid-001") as rec:
    rec.country.set(fr_ref)
    rec.since.set(2024)
```

### 5.3 Manual `preview/commit/rollback`

```python
editor = sdk.edit(User, source_system="APP", source_id="u-001")
editor.__enter__()
try:
    editor.name.add("Alicia")
    plan = editor.preview()
    editor.commit(meta={"trace_id": "manual-fix"})
except Exception:
    editor.rollback()
    raise
```

Stable Contract:
- Editor is closed after `commit()`/`rollback()`; further operations raise `EditorClosedError`.

### 5.4 `FieldEditor` Rules

| Field Cardinality | Allowed | Wrong Call |
|------|------|------|
| `functional` | `.set(...)` | `.add(...)` -> `CardinalityError` |
| `multi` | `.add(...)` | `.set(...)` -> `CardinalityError` |
| any | `.retract(asrt_id=...)` | missing `asrt_id` |

### 5.5 Not Found

Stable Contract:
- `sdk.edit(...)` never creates new entities; use `sdk.batch()` for creation.

---

## 6. External Import with `sdk.ingest`

### 6.1 Basic Usage

```python
result = sdk.ingest(
    [
        {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Alicia"},
        {"kind": "set", "field": User.country, "e_ref": alice_ref, "value": fr_ref},
        {"kind": "retract", "asrt_id": "asrt_old_name_xxx"},
    ],
    meta={"source": "CSV_IMPORT", "trace_id": "import-2026-01"},
)
```

### 6.2 Item Shapes

| `kind` | Required | Optional |
|------|------|------|
| `set` | `field`, `e_ref`, `value` | `dims`, `meta` |
| `add` | `field`, `e_ref`, `value` | `dims`, `meta` |
| `retract` | `asrt_id` | `meta` |

Stable Contract:
- `data` must be `list`/`tuple`.
- `field` must be SDK `Field` descriptor.
- `e_ref` must be canonical ref token.
- Ingest prechecks cardinality (`set` for functional, `add` for multi).

### 6.3 Meta Key Tiers

- Hard reserved: `ingested_at`, `ingest_key`, `revoked_asrt_id` (user must not write)
- Sensitive semantic keys: warning by default
- Convention/free keys: allowed (subject to meta value constraints)

Stable Contract:
- `allow_sensitive_meta=True` suppresses sensitive warnings only.

### 6.4 Exceptions vs Diagnostics

| Case | Behavior |
|------|------|
| Invalid top-level `meta` | raises `SDKStoreError` |
| Invalid item structure/meta/unknown retract target | `result.diagnostics` with `severity="error"` |
| Sensitive key (without allow) | `result.warnings` |

Stable Contract:
- Any `diagnostics` error triggers collect-and-stop (whole batch not written).

### 6.5 Typical Fallback: Record Relocation

When `find` does not provide identity, use `ingest(retract + set/add)` with `ref + asrt_id`.

---

## 7. Rules and Derivations

### 7.1 `vars(...)`

```python
with vars("p", "c") as (p, c):
    ...

with vars() as V:
    p, c = V("p", "c")
```

Stable Contract:
- `with vars() as (p, c)` is not supported.

### 7.2 Rules

```python
with vars("li", "p", "c") as (li, p, c):
    rule = Rule(
        id="q_country",
        version="1.0.0",
        select=[p, c],
        where=[LivesIn(li), li.user == p, li.country == c],
    )
rows = sdk.run(rule)
```

Stable Contract:
- Chain syntax like `LivesIn(li).user == p` is not supported.
- `RuleRef` target must be `expose=True`.
- String DSL is not supported (`sdk.run("...")`).

Current Behavior:
- SDK object DSL is lowered and then schema-aware compiled; record path sugar is generally rewritten against schema predicates (including custom `pred_id`).

### 7.3 Derivations

```python
with vars("u", "l", "li", "hl", "c") as (u, l, li, hl, c):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[LivesIn(li), li.user == u, li.country == c, HasLanguage(hl), hl.country == c, hl.language == l],
        head=Speaks(user=u, language=l),
        materialize_as="record",
    )

cands = sdk.evaluate(drv)
res = sdk.accept(cands[0], approved_by="pipeline")
```

Stable Contract:
- `sdk.accept(CandidateSet, ...)` accepts exactly one positional candidate set.
- Supported accept override keys: `approved_by`, `note`, `dry_run`.

Current Behavior:
- In schema-aware evaluate path, record derivations may auto-derive `id_policy`; explicit `id_policy` is still recommended for production stability.

### 7.4 Current DSL Limits

- No string DSL (`run/evaluate`).
- No chained path expression.
- No attr-vs-attr sugar (`a.x == b.x`).
- No non-linear multiplication (`x * y`).
- `Not(...)` body must be non-empty and safe under rule validation.

---

## 8. Provenance Validation

`sdk.validate_provenance(...)` is validation-only: no writes, no automatic blocking.

### 8.1 Usage

```python
report = sdk.validate_provenance(candidate_set, standard="derivation_v1")
```

Also supports dict input (flat-key form).

Stable Contract:
- Supported input: `CandidateSet` or `dict`.
- Supported standard: `derivation_v1` only.
- Returns `ValidationReport`.

### 8.2 Required Keys (`derivation_v1`)

- `derived_rule_id`
- `derived_rule_version`
- `run_id`
- `support_kind`
- `support_digest` (`sha256:<64hex>`)

### 8.3 Optional Digest Keys

- `schema_digest`
- `policy_digest`

Current Behavior:
- Malformed optional digests emit warnings, not errors.

### 8.4 Dict Shape Note

Current Behavior:
- Dict validation reads flat keys; it does not auto-unwrap `{"provenance": {...}}`.

### 8.5 Relationship with Writes

Stable Contract:
- Caller decides whether to gate `accept/ingest` using this report.

---

## 9. Which Write API Should I Use?

### 9.1 Quick Matrix

| Scenario | Recommended API |
|------|------|
| Build graph + preview + replay | `sdk.batch()` |
| Modify one known entity (full identity) | `sdk.edit(...)` |
| External write items / only `ref + asrt_id` | `sdk.ingest(...)` |
| Derivation candidate materialization | `sdk.evaluate(...) + sdk.accept(...)` |
| Minimal low-level direct write | `sdk.set/add/retract` |

### 9.2 Minimal Decision Tree

```text
Need previewable write plan?
  ├─ Yes -> sdk.batch()
  └─ No
      ├─ Full identity + one entity edit?
      │    ├─ Yes -> sdk.edit(...)
      │    └─ No
      │         ├─ Derivation candidate flow?
      │         │    ├─ Yes -> evaluate + accept
      │         │    └─ No -> sdk.ingest(...)
```

---

## 10. Error Handling Quick Reference

### 10.0 Error Layers

| Layer | Typical Errors |
|------|------|
| SDK facade | `SDKSchemaError`, `SDKStoreError` |
| Read/write objects | `EntityNotFoundError`, `FrozenSnapshotError`, `CardinalityError`, `EditorClosedError` |
| DSL construction | `SDKDSLError` |
| Core compile/execute | e.g., `RuleCompileError` |
| Ingest diagnostics channel | `result.diagnostics` |

### 10.1 Common Errors

| Error / Symptom | Typical Cause | Fix |
|------|------|------|
| `EntityNotFoundError` | editing missing entity | verify identity or create with batch |
| `FrozenSnapshotError` | assignment on snapshot/assertions | use edit/ingest path |
| `CardinalityError` | wrong set/add usage in edit | follow field cardinality |
| `EditorClosedError` | using editor after close | open a new edit session |
| `SDKSchemaError` | invalid get/find field usage | align with schema identity/fields |
| `SDKStoreError` | type mismatch, unsupported API shape, unknown accept kw | fix input contract |
| `SDKDSLError` | unsupported DSL construction | use supported DSL patterns |
| `RuleCompileError` (or wrapped) | semantic rule constraints | fix rule/ref exposure and where semantics |
| `diagnostics` has `severity="error"` | item-level ingest validation failed | fix by `path`; batch was not written |

### 10.2 Minimal Ingest Triage

```python
res = sdk.ingest(items, meta=meta)
for d in res.diagnostics:
    print(d["severity"], d["code"], d["path"], d["message"])
```

Recommended order:
1. `diagnostics`
2. `warnings`
3. `written_assertion_ids / skipped_count / duplicate_count`

---

## 11. Registry Publish and Read: `SDKRegistry`

`SDKRegistry` is the SDK wrapper around the authoring registry for schema/rule/derivation registration, publish runs, and version reads.

### 11.1 Initialize

```python
from factpy_kernel.sdk import SDKRegistry

reg = SDKRegistry(root_dir="./registry")
print(reg.root_dir)
```

Stable Contract:
- Constructor is one-of: `SDKRegistry(root_dir=...)` or `SDKRegistry(registry=...)`.
- If both `root_dir` and `registry` are provided, they must point to the same path, otherwise `SDKRegistryError`.

### 11.2 Apply Schema: `apply_schema_classes(...)`

```python
res = reg.apply_schema_classes(
    [Person],
    apply_request_id="req-001",
    transaction_policy="best_effort_no_rollback_v1",
)

print(res["ok"])
print(res["apply_execute"]["status"])
print(res["apply_execute"]["idempotency"]["replayed"])
```

Current Behavior:
- `apply_schema_classes(...)` compiles Entity classes into authoring schema, then calls `apply_authoring_bundle(...)`.
- Reusing the same `apply_request_id` triggers idempotent replay (`idempotency.replayed=True`).
- Nested fields such as `res["apply_execute"]["..."]` are current-behavior details and may evolve with authoring internals; for business success checks, prefer top-level `res["ok"]`.

### 11.3 Register / Apply Entry Points (object, spec, bundle)

You can register compiled specs directly, or pass SDK objects and let SDK compile first:

```python
from factpy_kernel.sdk import Rule, Derivation, Pred, vars

with vars("e", "c") as (e, c):
    rule = Rule(
        id="rule.country_rows",
        version="1.0.0",
        select=[e, c],
        where=[Pred("person:country", e, c)],
        expose=True,
    )

reg.register_rule(rule)
```

```python
with vars("e", "c") as (e, c):
    drv = Derivation(
        id="drv.country_copy",
        version="1.0.0",
        head=Person.country_copy(person=e, country_copy=c),
        materialize_as="fact",
        where=[Pred("person:country", e, c)],
    )

reg.register_derivation(drv)
```

You can also register already-compiled specs directly (skip SDK DSL compile):

```python
reg.register_rule_spec(compiled_rule_spec_dict)
reg.register_derivation_spec(compiled_derivation_spec_dict)
```

The lower-level unified entrypoint is `apply_authoring_bundle(...)`:

```python
res = reg.apply_authoring_bundle(
    authoring_schema=authoring_schema_dict,
    rule_request={"rule_spec_payload": compiled_rule_spec_dict},
    derivation_request={"derivation_id": "...", "version": "...", "target_pred_id": "...", "head_vars": [...], "where": [...]},
    apply_request_id="req-002",
)
```

Current Behavior:
- `register_rule(...)` / `register_derivation(...)` accept SDK objects or authoring payload dict.
- `register_rule_spec(...)` / `register_derivation_spec(...)` are for flows where you already have compiled spec dicts.
- `apply_authoring_bundle(...)` is the lower-level entrypoint used by `apply_schema_classes(...)`, suitable for applying schema/rule/derivation changes together.
- `register_derivation(...)` has a fallback: when `schema_ir` is not explicitly passed and first compile fails, it tries loading schema_ir from the registry and retries once.
- For head-only derivations, prefer calling `apply_schema_classes(...)` before registration, or pass `schema_ir=...` explicitly, to avoid relying on fallback retry behavior.

### 11.4 Read and List APIs

```python
print(reg.list_rule_ids())
print(reg.list_derivation_ids())
print(reg.list_rule_versions("rule.country_rows"))
print(reg.get_latest_rule_spec("rule.country_rows"))
print(reg.read_rule_spec("rule.country_rows", "1.0.0"))

print(reg.list_derivation_versions("drv.country_copy"))
print(reg.get_latest_derivation_spec("drv.country_copy"))
print(reg.read_derivation_spec("drv.country_copy", "1.0.0"))
```

Stable Contract:
- `list_*` APIs return ordered lists.
- `get_latest_*` / `read_*` return `None` when the target is missing.
- Rule and derivation read/list method names are symmetric (`*_rule_*` vs `*_derivation_*`).

### 11.5 Apply-Run Queries

```python
print(reg.list_apply_run_ids())
print(reg.list_apply_runs())
print(reg.show_apply_run("req-001"))
```

Current Behavior:
- `show_apply_run(...)` returns `None` if not found.
- `list_apply_runs()` returns apply execute run records (`list[dict]`).

### 11.6 Error Boundary

Stable Contract:
- Filesystem and authoring apply errors are wrapped as `SDKRegistryError`.
- `register_rule/register_derivation` raise `SDKRegistryError` when input is neither SDK object nor dict.

---

## 12. API Surface Additions (Advanced)

This section covers methods listed in `04_api_surface.md` that are not fully expanded in sections 1-10.

### 12.1 Low-Level Writes: `ref / set / add / retract`

```python
alice_ref = sdk.ref(User, source_system="APP", source_id="u-001")
sdk.set(User.country, alice_ref, de_ref)
sdk.add(User.name, alice_ref, "Alice")
sdk.retract("asrt_xxx")
```

Stable Contract:
- This is the thinnest write path (direct ledger writes), without batch preview/wire features.

### 12.2 Compiled Pass-Through: `evaluate_compiled / accept_compiled`

```python
cands = sdk.evaluate_compiled(...)
res = sdk.accept_compiled(...)
```

Current Behavior:
- These APIs pass through to underlying `store` methods. Use them when you already have compiled inputs and want to skip SDK object compile.
- Typical use case: you already have compiled specs produced by external flows (for example CLI/registry pipelines) and want direct execution.

### 12.3 Package Export and Run: `export_package / run_package`

```python
# options is adapter-specific (currently often Souffle ExportOptions)
options = ...
sdk.export_package("./pkg", options)
sdk.run_package("./pkg", entrypoints=["__query__"], engine="souffle")
```

Current Behavior:
- This capability depends on adapter implementation (currently mainly the Souffle adapter); exact `options` type/details can evolve with adapter changes.
- If your goal is standard SDK read/write/derivation flow, you can ignore this advanced layer.

### 12.4 Debug Properties: `sdk.store / sdk.ledger / sdk.schema_ir`

```python
print(sdk.store)
print(sdk.ledger)
print(sdk.schema_ir)
```

Stable Contract:
- These are intended for debugging, auditing, and advanced integrations.
- `sdk.schema_ir` is the compiled schema actually used by the current store.

### 12.5 Audit Queries: `explain_fact / conflicts`

These APIs are useful when debugging functional conflicts and chosen resolution.

```python
audit = sdk.explain_fact("person:country", person_ref)      # optional value-atom filter
audit_de = sdk.explain_fact("person:country", person_ref, "de")
conf = sdk.conflicts("person:country", person_ref)
```

`explain_fact(...)` returns (Current Behavior):
- `pred_id`
- `e_ref`
- `active_claims`: `list[dict]`, each item has `asrt_id`, `args`, `meta`
- `chosen_asrt_id`

`conflicts(...)` returns (Current Behavior):
- `pred_id`
- `e_ref`
- `active_asrt_ids`
- `chosen_asrt_id`

Parameter contract (Stable Contract):
- `pred_id`: predicate id (for example `"person:country"`).
- `e_ref`: canonical `idref_v1` token (for example from `snapshot.ref` or `sdk.ref(...)`).
- `explain_fact(..., *val_atoms)` filters `active_claims` by exact value-atom match.
