# FactPy SDK User Guide

The end-to-end tour of `kernel.sdk` for new users. Reading this doc plus
running the snippets is enough to use the SDK confidently for typical
workloads.

For exhaustive API listings see
[`04_api_surface.en.md`](04_api_surface.en.md). For counterfactual
analysis see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).
For walker views and advanced importables see
[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md).

---

## Table of Contents

1. [Install and FactGraph tour](#1-install-and-factgraph-tour)
2. [Schema](#2-schema)
3. [Reading](#3-reading)
4. [Writing](#4-writing)
5. [Eval — Rule / Query / Derivation](#5-eval--rule--query--derivation)
6. [What-if](#6-what-if)
7. [Audit](#7-audit)
8. [Views and packages](#8-views-and-packages)
9. [Error handling](#9-error-handling)
10. [Registry](#10-registry)
11. [Where to go next](#11-where-to-go-next)
12. [Appendix: migration notes (v2 → v3)](#12-appendix-migration-notes-v2--v3)

---

## 1. Install and FactGraph tour

### Install

```bash
python -m pip install factpy-kernel
```

For development from source:

```bash
git clone https://github.com/Symbolic-Intelligence-Org/hnsm-backend.git
cd hnsm-backend
python -m pip install -e .
```

### Hello FactGraph

```python
from kernel.sdk import Entity, FactGraph, Field, Identity

class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")

fg = FactGraph.from_schema_classes([User])

fg.ingest([
    {"entity": "User", "user_id": "u-1", "name": "Alice"},
    {"entity": "User", "user_id": "u-2", "name": "Bob"},
])

fg.write.add(User.tags, fg.read.ref(User, user_id="u-1"), "engineer")

snap = fg.read.get(User, user_id="u-1")
print(snap.name, snap.field("tags").current())
# → Alice ['engineer']
```

`FactGraph` is the canonical entry point. It is a literal alias of
`SDKStore` — both names refer to the same class. Operations are
available both as flat methods (`fg.get(...)`, `fg.add(...)`) and as
namespaced methods (`fg.read.get(...)`, `fg.write.add(...)`); both
forms are permanent and equivalent.

The eight namespaces:
`schema`, `read`, `write`, `eval`, `what_if`, `audit`, `package`,
`views`. See [§0 of 04_api_surface.en.md](04_api_surface.en.md#0-namespace-map)
for the full map.

---

## 2. Schema

Schema is declared as Python classes. Every entity must declare at
least one `Identity(primary_key=True)`; `Field` declares non-identity
fields with `cardinality="single"` or `"multi"`.

```python
from kernel.sdk import Entity, Field, Identity, Relationship

class Document(Entity):
    doc_id: str = Identity(primary_key=True)
    title: str = Field(cardinality="single")
    keywords: str = Field(cardinality="multi")
    author: str = Field(cardinality="single")  # entity_ref to User

class Authored(Relationship):
    user: str = Identity(primary_key=True)      # User.user_id
    document: str = Identity(primary_key=True)  # Document.doc_id
    role: str = Field(cardinality="single")
```

### Compile and instantiate

`from_schema_classes` compiles, validates, and constructs in one step:

```python
fg = FactGraph.from_schema_classes([User, Document, Authored])
```

You can also compile separately:

```python
from kernel.sdk import compile_schema_from_classes, schema_preflight_from_classes

schema_preflight_from_classes([User, Document])    # raises SDKSchemaError on issues
schema_ir = compile_schema_from_classes([User, Document])
```

### Provenance validation

```python
report = fg.schema.validate_provenance(items)  # also: fg.validate_provenance
report.ok                # True if everything passes
report.errors            # list of (item_index, code, message)
```

This inspects an item batch's provenance shape **without** writing.
Useful as a pre-flight before `fg.ingest(...)`. Returns a
`ValidationReport`.

---

## 3. Reading

### Get one entity by identity

```python
snap = fg.read.get(User, user_id="u-1")          # → EntitySnapshot | None
# Or flat:
snap = fg.get(User, user_id="u-1")
```

### Find entities

```python
# By exact value on a single-cardinality field
admins = fg.read.find(User, name="Alice")

# Multi-cardinality field uses containment match
engineers = fg.read.find(User, tags="engineer")

# Apply a named view (see §8) and limit
recent = fg.read.find(Document, view="last_30_days", limit=20)
```

### Reference encoding

```python
ref = fg.read.ref(User, user_id="u-1")  # → "User#u-1" (encoded form)
```

`ref` is required as the second argument to `fg.write.{set,add,retract}`.

### `EntitySnapshot` cheat-sheet

```python
snap = fg.read.get(User, user_id="u-1")

snap.name                         # current single-field value
snap.field("tags").current()      # → list of current multi-field values
snap.field("name").history()      # → all assertions ever (active + retracted)
snap.field("name").at("2026-05-01T00:00:00Z")  # value at a point in time
snap.field("name").version(3)     # value at version N

snap.assertions.field("name")     # FieldAssertions namespace (raw access)
snap.identity                     # dict of identity values
snap.entity_type                  # "User"
snap.ref                          # encoded ref
```

`EntitySnapshot` is read-only; assigning to any attribute raises
`FrozenSnapshotError`.

---

## 4. Writing

Four primitive operations: `set`, `add`, `retract`, `edit`. Plus
`ingest` for bulk insertion from external sources, and `batch` for
grouping multiple operations into one transaction.

### Single writes

```python
ref = fg.read.ref(User, user_id="u-1")

fg.write.set(User.name, ref, "Alice Liddell")    # single-cardinality field
fg.write.add(User.tags, ref, "manager")          # multi-cardinality field
fg.write.retract(asrt_id="asrt-abc-123")         # by assertion id
```

`set` on a multi-field raises `CardinalityError`. `add` on a
single-field raises `CardinalityError`.

### Transactional editor

```python
with fg.write.edit(User, user_id="u-1") as ed:
    ed.field("name").set("Alice in Wonderland")
    ed.field("tags").add("storyteller")
    ed.commit(meta={"source": "manual_review", "approved_by": "u-admin"})
```

The editor preview-then-commit pattern is recommended when multiple
fields need to change atomically with shared meta.

### Batch transactions

```python
with fg.batch(meta={"source": "import_2026_05_09"}) as tx:
    alice = tx.entity(User, user_id="u-1")
    alice.field("name").set("Alice")
    alice.field("tags").add("engineer")

    bob = tx.entity(User, user_id="u-2")
    bob.field("name").set("Bob")

    tx.commit()  # or tx.rollback() — `with` does NOT auto-commit
```

The context manager **does not** auto-commit on success or rollback on
exception — call them explicitly. This is intentional so that batch
preview/review patterns work naturally.

### Bulk ingest

```python
result = fg.ingest([
    {"entity": "User", "user_id": "u-3", "name": "Carol", "_meta": {...}},
    {"entity": "User", "user_id": "u-4", "name": "Dave"},
])

result.ingested_count
result.assertion_ids
result.validation_report
```

`ingest` accepts each item as either:
- `{"entity": "User", <identity>, <fields>, "_meta": {...}}` — single-row form
- A pre-built application protocol DTO (advanced)

Returns an `IngestResult` with counts, ids, and a `ValidationReport`.

### The `meta` field

Every write accepts an optional `meta` dict. Keys recognized by the SDK:

| Key | Type | Purpose |
|---|---|---|
| `source` | str | Where this assertion came from |
| `trace_id` | str | Trace identifier for cross-system correlation |
| `confidence` | float in (0, 1] | Probabilistic confidence; `int` is not auto-promoted |
| `approved_by` | str | Reviewer identifier (for governance) |
| `note` | str | Free-form annotation |
| `derived_rule_id` | str | Set automatically by `accept(...)` for derived facts |
| `candidate_id` | str | Set automatically by `accept(...)` |

Unknown keys are preserved on the assertion as opaque metadata.

`confidence` validation:

```python
fg.write.set(User.name, ref, "Alice", meta={"confidence": 0.85})  # ✅
fg.write.set(User.name, ref, "Alice", meta={"confidence": 1})     # ❌ int rejected
fg.write.set(User.name, ref, "Alice", meta={"confidence": 1.2})   # ❌ out of range
```

### Which write entry point?

| If you need to ... | Use |
|---|---|
| Insert one fact | `fg.write.set` / `fg.write.add` |
| Update multiple fields atomically on one entity | `fg.write.edit(...)` context manager |
| Group writes across multiple entities | `fg.batch(...)` context manager |
| Bulk-insert from external data | `fg.ingest(...)` |
| Persist derived facts | `fg.eval.accept(...)` (handles meta automatically) |

---

## 5. Eval — Rule / Query / Derivation

Three primitives:

| | Purpose | Returned by `fg.eval.run` |
|---|---|---|
| `Rule` | A single inference (head + body) | List of `CandidateSet` |
| `Query` | Materialize a view of the current store | `list[dict]` (default) |
| `Derivation` | A multi-rule envelope for engine evaluation | Use `fg.eval.evaluate` |

### Query

```python
from kernel.sdk import Query, Pred, vars

user, lang = vars("user", "lang")

q = Query(
    head=[user, lang],
    body=[Pred("User", user, lang=lang)],
)

rows = fg.eval.run(q)            # → [{"user": "u-1", "lang": "en"}, ...]
rows = fg.eval.run(q, row_format="instance")  # → [EntitySnapshot, ...] for single-Entity head
```

Query options:
- `on_missing="error" | "skip" | "null"` — handle missing field references
- `on_type_mismatch="error" | "skip" | "null"` — handle type mismatches
- `row_format="dict" | "instance" | "tuple"` — `tuple` is deprecated

Invalid `row_format` or incompatible head raises
`SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.

### Rule + run

```python
from kernel.sdk import Rule, Pred, vars

user, role = vars("user", "role")

r = Rule(
    head=Pred("Authored", user, document=vars("d")),
    body=[
        Pred("User", user),
        Pred("Document", vars("d"), author=user),
    ],
)

candidates = fg.eval.run(r)      # → list[CandidateSet]
```

Rule `body` may be a `Body([...])` or a raw list of `Pred` literals.
`Body` is required when you need to pass `body_confidences` for
probabilistic engines.

### Derivation + evaluate

```python
from kernel.sdk import Derivation

deriv = Derivation(rules=[r1, r2, r3])

candidates = fg.eval.evaluate(deriv, mode="native")           # → list[CandidateSet]
candidates = fg.eval.evaluate(deriv, mode="problog")          # probabilistic
candidates = fg.eval.evaluate(deriv, mode="pyreason",
                              engine_options={"timesteps": 5})  # temporal
```

`mode` selects the engine; `engine_options` is call-time runtime
config that never enters the `Derivation` or the ledger.
`mode="native"` rejects non-empty `engine_options`.

`CandidateSet.confidence`:
- `native` / `souffle` → `None`
- `problog` → probability `float`
- `pyreason` → lower-bound `float`

### Accept

```python
result = fg.eval.accept(
    candidates[0],
    approved_by="u-admin",
    note="weekly batch",
)
```

`accept` writes the candidate's facts into the ledger. Sugar keys:
`approved_by`, `note`, `dry_run`, `identity_override` (also via
`meta_overrides`).

```python
results = fg.eval.accept_many(candidates)  # idempotent batch accept
```

Accepting the same candidate twice is idempotent (skipped).
Accepting the same claim with a **different** confidence creates a
new assertion alongside, not a replacement.

### Engine semantics (`engine_ext` vs `engine_options`)

```python
from kernel.adapters.pyreason import PyReasonRuleExt

r = Rule(head=..., body=..., engine_ext=PyReasonRuleExt(timestep_delay=1))

# engine_options is call-time only
fg.eval.evaluate(deriv, mode="pyreason", engine_options={"timesteps": 10})
```

`engine_ext` lives **on the rule definition** (definition-time semantics
that travel with the rule). `engine_options` is **call-time** runtime
config that never enters the `Derivation` or ledger.

### Semantic annotations

PyReason runs produce `pyreason/semantic/*` annotations; ProbLog runs
produce `problog/semantic/probability`. To persist them after
`accept(...)`:

```python
fg.persist_pyreason_annotations()
fg.persist_problog_annotations()
```

---

## 6. What-if

Counterfactual analysis without writing to the ledger. The full tour
is in [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

Quick reference:

| Method | Question |
|---|---|
| `fg.what_if.check(deriv, binding)` | Does this fact derive? |
| `fg.what_if.diagnose(deriv, binding)` | Why does it derive (or why not)? |
| `fg.what_if.fact_overlay.check(deriv, binding, overlay)` | What if facts were different? |
| `fg.what_if.fact_overlay.recheck_proof_frame(support, overlay)` | Re-check a held proof under overlay |
| `fg.what_if.rule.disable(rule, support, ...)` | What if this body literal were disabled? |
| `fg.what_if.rule.literal_replace(rule, support, ...)` | What if this literal were replaced? |
| `fg.what_if.rule.add_condition(rule, support, ...)` | What if we added this condition? |
| `fg.what_if.why_not(deriv, candidates)` | Across this candidate universe, what doesn't derive and why? |

All return frozen application DTOs (not in `kernel.sdk.__all__`); see
06 for the result shapes.

---

## 7. Audit

```python
explanation = fg.audit.explain_fact("User#u-1.name@asrt-abc-123")
conflicts = fg.audit.conflicts()
diff = fg.audit.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)
```

`explain_fact` returns the proof structure for a specific fact
(by encoded locator). `conflicts` enumerates active conflicting
assertions. `diff_proof_frames` compares two recorded rounds — see
[06 §Q5](06_what_if_and_proof.en.md#q5-how-did-derivation-change-between-rounds--fgaudit_diff_proof_frames).

---

## 8. Views and packages

### Views

```python
spec = {
    "strategy": "max_confidence",
    "predicate": "User",
    "fields": ["name"],
}

fg.views.create("preferred_names", spec)
fg.views.update("preferred_names", new_spec)
fg.views.delete("legacy_view")          # cannot delete "default"
fg.views.get("preferred_names")
all_views = fg.views.list()             # → dict[str, ViewSpec]
```

Use a view in `find` with `view="preferred_names"`.

Available aggregation strategies include `max_confidence`, `mean`,
`latest`. See `kernel.sdk.views` source for the full set.

### Packages (Souffle export and replay)

```python
fg.package.export_package("/tmp/my_export/")
fg.package.run_package(
    "/tmp/my_export/",
    entrypoints=["my_rule"],
    engine="souffle",
)
```

`export_package` materializes a Souffle-format package directory.
`run_package` invokes the engine on it. Useful for offline analysis
and integration with non-Python toolchains.

---

## 9. Error handling

All SDK errors derive from `SDKError` and expose:
- `code` — error code constant (see [§1.5 of 04](04_api_surface.en.md#15-errors-and-error-codes))
- `path` — JSON-pointer-style locator into the offending input
- `__cause__` — chained underlying exception (when applicable)

### Top-level taxonomy

```python
try:
    fg.write.set(User.tags, ref, "engineer")  # multi-field; should be add
except CardinalityError as e:
    print(e.field_name, e.actual_cardinality, e.operation)
    # → tags multi set
```

| Class | When |
|---|---|
| `SDKSchemaError` | Schema preflight or compilation issue |
| `SDKStoreError` | Most write/read/eval/what-if/audit failures |
| `EntityNotFoundError` | `read.get` / `write.edit` on missing identity |
| `CardinalityError` | `set` on multi-field, or `add` on single-field |
| `FrozenSnapshotError` | Assigning to a snapshot or namespace attribute |
| `EditorClosedError` | Operating on a committed/rolled-back editor |
| `SDKRegistryError` | Registry/rule registration issues |

### Error code constants

```python
from kernel.sdk import (
    INVALID_ROW_FORMAT,
    QUERY_INVALID_ROW_FORMAT,
    QUERY_MISSING_REF,
    SDKStoreError,
)

try:
    fg.eval.run(query, row_format="banana")
except SDKStoreError as e:
    if e.code == QUERY_INVALID_ROW_FORMAT:
        print("Caller bug: row_format must be one of dict|instance|tuple")
```

### Optional-domain bundles

When importing optional domain packs (e.g. ECSS), use the
`ensure_domain` helper rather than catching `ImportError`. See
[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md#optional-domain-bundles).

---

## 10. Registry

The registry tracks compiled schemas, rules, and derivations across
versions and apply runs.

```python
from kernel.sdk import SDKRegistry

reg = SDKRegistry(...)            # see ./registry.py for constructor

reg.apply_schema_classes([User, Document])
reg.register_rule(my_rule)
reg.register_derivation(my_derivation)

reg.list_rule_ids()
reg.list_rule_versions("rule:authored_v1")
reg.read_rule_spec("rule:authored_v1", version=2)
```

Apply runs:

```python
reg.list_apply_run_ids()
reg.list_apply_runs()
reg.show_apply_run("apply-2026-05-09T10:00:00Z")
```

`register_derivation` is single-head-oriented; for multi-head
publishing, expand into multiple single-head derivations first.

See [§3 of 04](04_api_surface.en.md#3-sdkregistry-methods) for the
full method list.

---

## 11. Where to go next

- **[`04_api_surface.en.md`](04_api_surface.en.md)** — full API
  reference with every method signature
- **[`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md)** —
  end-to-end tutorial of all nine what-if and proof methods
- **[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md)** —
  walker views, recorder lifecycle, raw DTO construction, optional
  domain helpers, engine adapter registration

---

## 12. Appendix: migration notes (v2 → v3)

The v3 SDK is API-compatible with v2 for the flat method surface.
Two changes worth noting:

### Removed/renamed APIs

| v2 | v3 | Notes |
|---|---|---|
| `functional` field on `Field` | (removed) | Use `cardinality="single"` |
| `temporal` field on `Field` | (removed) | Temporal semantics moved to `meta` |
| `dims` field on `Field` | (removed) | Multi-dimensional fields not supported |
| `fact_key` / `pred_id` on `Pred` | (removed) | Use field accessors instead |
| `.chosen` on assertion view | (removed) | Use `field(...).current()` |
| `temporal_view` parameter | (removed) | Pass via `meta` and use a custom view |
| `engine` keyword in `evaluate` | renamed | Use `mode` |
| `python` keyword in `evaluate` | renamed | Use `mode="native"` |

### body_confidences bridge

Probabilistic engines (`problog`) accept per-literal confidence via
`Body([...], body_confidences=[...])`. The legacy v2 `body_confidences`
keyword on `Rule(...)` is still accepted but emits a deprecation
warning; new code should use the `Body(...)` constructor form.

### Tag semantics on multi-fields

In v3, `add` on a multi-field creates a separate assertion per call
even for the same value. Use `meta` to differentiate when needed.
v2's de-duplication on `add` is gone; the v2 semantic is now expressed
via `accept(...)` idempotency.

### Row format

The default `row_format` is `"dict"`. `"tuple"` still works but emits
`DeprecationWarning`. New code should use `"dict"` or `"instance"`.
