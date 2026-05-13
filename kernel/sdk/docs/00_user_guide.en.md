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
5. [Eval — Rule / Query / Inference](#5-eval--rule--query--inference)
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

fg = FactGraph.create(schema_classes=[User])

ref_alice = fg.read.ref(User, user_id="u-1")
ref_bob   = fg.read.ref(User, user_id="u-2")

fg.write.set(User.name, ref_alice, "Alice")
fg.write.set(User.name, ref_bob,   "Bob")
fg.write.add(User.tags, ref_alice, "engineer")

snap = fg.read.get(User, user_id="u-1")
print(snap.name, [r.value for r in snap.field("tags").active])
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
from kernel.sdk import Entity, Field, Identity

class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

class Document(Entity):
    doc_id: str = Identity(primary_key=True)
    title: str = Field(cardinality="single")
    keywords: str = Field(cardinality="multi")
    author: User = Field(cardinality="single")  # entity_ref to User
```

### Compile and instantiate

`FactGraph.create(...)` compiles, validates, and constructs in one step:

```python
fg = FactGraph.create(schema_classes=[User, Document])
```

Pass `path=` when the graph should own a durable workspace. A workspace stores
the ledger, schema IR, and authoring registry together:

```python
fg = FactGraph.create(schema_classes=[User, Document], path="./workspace")
fg.save()

same_graph = FactGraph.load("./workspace", schema_classes=[User, Document])
```

`FactGraph.load(...)` requires the same Python `Entity` classes used to create
the workspace. It validates the manifest, ledger schema digest, registry schema
digest, and supplied classes before returning a graph.

You can also compile separately:

```python
from kernel.sdk import compile_schema_from_classes, schema_preflight_from_classes

report = schema_preflight_from_classes([User, Document])
report["ok"]          # False when diagnostics contain schema errors
report["errors"]      # list[dict] with path/message details
schema_ir = compile_schema_from_classes([User, Document])
```

`Relationship` classes are compile-level schema declarations, not
entities with identity fields. They declare endpoints with `from_entity`
and `to_entity`, and any relationship attributes are `Field(...)`
members. `FactGraph.create(...)` constructs a store from entity classes;
use `compile_schema_from_classes(...)` when you need to inspect
relationship schema IR directly.

### Provenance validation

```python
report = fg.schema.validate_provenance(candidate)  # also: fg.validate_provenance
report.ok                # True if everything passes
report.warnings          # list[dict] — non-fatal advisories
report.errors            # list[dict], each: {code, severity, path, message, data}
```

This inspects a `CandidateSet` (or a provenance/meta dict) **without**
writing. Returns a
`ValidationReport(ok, warnings, errors, diagnostics_contract_version)`.

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

# Apply a read-time policy (see §8) and limit
from kernel.sdk import ReadPolicy

recent = fg.read.find(
    Document,
    policy=ReadPolicy(respect_revocations=True, confidence_strategy="max"),
    limit=20,
)
```

### Reference encoding

```python
ref = fg.read.ref(User, user_id="u-1")
# → "idref_v1:User:<base32-sha256-digest>"  (opaque, content-derived)
```

`ref` is required as the second argument to `fg.write.set(...)` and
`fg.write.add(...)`. `fg.write.retract(...)` takes an assertion id
(`asrt_id`), not an entity ref. The ref string is opaque — never parse or
compare it as a textual identity; treat it as a stable handle.

### `EntitySnapshot` cheat-sheet

```python
snap = fg.read.get(User, user_id="u-1")

snap.name                         # current single-field value
snap.field("tags").active         # → AssertionRecordSet (tuple-compatible)
[r.value for r in snap.field("tags").active]   # → ['engineer', ...]

snap.field("name").history        # → AssertionRecordSet (active + revoked)
snap.field("name").at("2026-05-01T00:00:00Z")  # active shortcut visible at t
snap.field("name").version("v3")  # active shortcut at version v3
snap.field("name").history.at("2026-05-01T00:00:00Z")  # history-level time filter
snap.field("name").history.by_id(asrt_id)      # exact assertion-id filter

target = (
    snap.field("name")
    .history.where(value="Alice", source="seed")
    .one()
)
fg.write.retract(target.asrt_id)

snap.assertions.name              # equivalent to snap.field("name") — attr access
snap.identity                     # dict of identity values (when identity_available=True)
snap.identity_available           # bool — False if snapshot lacks full identity
snap.entity_type                  # "User"
snap.ref                          # encoded idref_v1 ref
```

Notes:
- `.active` and `.history` are **properties**, not methods (no
  parentheses). `FieldAssertions.at(t)` and `.version(v)` are active-only
  compatibility shortcuts for `.active.at(t)` and `.active.version(v)`.
- `.active`, `.history`, and record-set filters return `AssertionRecordSet`,
  a tuple-compatible collection of `AssertionRecord` values. Existing
  tuple-style iteration, indexing, and `len(...)` still work.
- `AssertionRecordSet` supports `.where(...)`, `.at(t)`, `.version(v)`,
  `.by_id(asrt_id)`, `.one()`, `.first()`, and `.all()`. Use chained
  filters plus `.one()` for exactly-one selection before retracting an
  assertion.
- `.at(t)` is a business-valid-time filter over assertion metadata
  `valid_from` / `valid_to`; it does not filter by `ingested_at`.
- `AssertionRecord` exposes `asrt_id`, `value`, `is_active`,
  `is_revoked`, and `meta` (an `AssertionMeta`).
- `EntitySnapshot` is read-only; assigning to any attribute raises
  `FrozenSnapshotError`.

---

## 4. Writing

Four primitive operations: `set`, `add`, `retract`, `edit`. Plus
`ingest` for bulk insertion from external sources, and `batch` for
grouping multiple operations into one transaction.

### Single writes

```python
ref = fg.read.ref(User, user_id="u-1")

name_asrt_id = fg.write.set(User.name, ref, "Alice Liddell")
tag_asrt_id = fg.write.add(User.tags, ref, "manager")
fg.write.retract(tag_asrt_id)                    # by assertion id
```

`set` on a multi-field raises `CardinalityError`. `add` on a
single-field raises `CardinalityError`. `set(...)` and `add(...)`
return the persisted `asrt_id`; later reads expose the same id through
`AssertionRecord.asrt_id`.

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

Batch entity handles are primary-first. The initial `tx.entity(...)` call
must provide every `Identity(primary_key=True)` value, unless that
primary identity has a literal `default` or `default_factory="uuid4"` that
can be materialized immediately. Use `bind(...)` only to complete
non-primary identity dimensions before the first field operation,
preview, or commit; writes always target one complete identity
coordinate.

### Bulk ingest

`fg.ingest(items, *, meta=None)` is the external-batch import path. Each
item is one normalized fact write:

```python
ref_carol = fg.read.ref(User, user_id="u-3")
ref_dave  = fg.read.ref(User, user_id="u-4")

result = fg.ingest(
    [
        {"kind": "set", "field": User.name, "e_ref": ref_carol, "value": "Carol"},
        {"kind": "set", "field": User.name, "e_ref": ref_dave,  "value": "Dave"},
        {"kind": "add", "field": User.tags, "e_ref": ref_carol, "value": "manager"},
        {"kind": "retract", "asrt_id": "asrt-old-id"},
    ],
    meta={"source": "import_2026_05_09"},  # merged into every item's meta
)

result.written_assertion_ids   # list[str] — newly persisted assertion ids
result.skipped_count           # int — rows skipped by validator
result.duplicate_count         # int — rows already present (idempotent dedup)
result.warnings                # list[dict] — non-fatal diagnostics
result.diagnostics             # list[dict] — full diagnostic stream (see §2)
```

Item shapes:
- `{"kind": "set", "field": <Field>, "e_ref": str, "value": Any, "meta"?: dict}`
- `{"kind": "add", "field": <Field>, "e_ref": str, "value": Any, "meta"?: dict}`
- `{"kind": "retract", "asrt_id": str, "meta"?: dict}`

Item-level `meta` overrides top-level `meta` keys.
`ingested_at`, `ingest_key`, and `revoked_asrt_id` are reserved
(passing them in user `meta` is an error).

Returns an `IngestResult(written_assertion_ids, skipped_count,
duplicate_count, warnings, diagnostics, diagnostics_contract_version)`.
Each entry in `warnings` and `diagnostics` follows the same dict shape
as `ValidationReport.errors` (`{code, severity, path, message, data}`).
`severity="error"` items trigger collect-and-stop semantics — the whole
batch is not written.

### The `meta` field

Every write accepts an optional `meta` dict. Keys recognized by the SDK:

| Key | Type | Purpose |
|---|---|---|
| `source` | str | Where this assertion came from |
| `trace_id` | str | Trace identifier for cross-system correlation |
| `confidence` | float in (0, 1] | Legacy/display metadata only; `int` is not auto-promoted |
| `raw_kind` | `"probabilistic"` or `"possibilistic"` | Raw uncertainty kind; must be paired with `bound` |
| `bound` | two-element JSON list `[lower, upper]` | Raw uncertainty bound; normalized to floats and matched exactly by assertion filters |
| `approved_by` | str | Reviewer identifier (for governance) |
| `note` | str | Free-form annotation |
| `derived_rule_id` | str | Set automatically by `accept(...)` for derived facts |
| `candidate_id` | str | Set automatically by `accept(...)` |

Unknown keys are preserved on the assertion as opaque metadata.
`probability`, `bound_lower`, and `bound_upper` are not accepted as
user-authored write meta; use `raw_kind` and `bound` instead. Engine adapters
may still produce annotations such as `problog/semantic/probability` or
`pyreason/semantic/bound_lower` as output/projection lanes.
Generic `confidence` is not a shared semantic annotation, not a ProbLog
probability fallback, and not a PyReason bound source.

Raw uncertainty validation:

```python
fg.write.set(User.name, ref, "Alice", meta={
    "raw_kind": "probabilistic",
    "bound": [0.2, 0.8],
})  # ✅

fg.write.set(User.name, ref, "Alice", meta={"raw_kind": "probabilistic"})  # ❌ bound missing
fg.write.set(User.name, ref, "Alice", meta={"bound": [0.2, 0.8]})          # ❌ raw_kind missing
fg.write.set(User.name, ref, "Alice", meta={"probability": 0.8})           # ❌ removed write key
```

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

## 5. Eval — Rule / Query / Inference

Three primitives:

| | Purpose | Returned by |
|---|---|---|
| `Rule` | Single-rule inference (`select` + `where`); produces rows | `fg.eval.run(rule)` → `list[dict]` (default) |
| `Query` | Read-side projection over the current store; produces rows | `fg.eval.run(query)` → `list[dict]` (default) |
| `Inference` | A single inference (one head); produces accept-ready candidates | `fg.eval.evaluate(inf, engine=...)` → `list[CandidateSet]` |

All three are constructed inside a `with vars(...) as (...):` block.
For the deeper DSL spec see
[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md).

### Query

A `Query(head, where, on_missing?, on_type_mismatch?)` projects rows from
the current ledger. `head` is either a single item or a list of items —
each item is an entity binding (`Entity(var)`) or a field projection
(`Entity.field(...)`). `where` is the body (always a list).

```python
from kernel.sdk import Query, vars

# Multi-projection head — list of two items, returns one column per item
with vars("u", "nm") as (u, nm):
    q = Query(
        head=[User(u), User.name(name=nm)],
        where=[User(u), u.name == nm],
    )

rows = fg.eval.run(q)
# → [{"u": <EntitySnapshot User Alice>, "nm": "Alice"}, ...]

# Single-projection head — pass the item directly OR wrap it in a list
with vars("u",) as (u,):
    q_one = Query(head=User(u), where=[User(u)])           # single item
    q_one_list = Query(head=[User(u)], where=[User(u)])    # equivalent
    snaps = fg.eval.run(q_one, row_format="instance")
    # → [<EntitySnapshot for Alice>, ...]
```

In the `dict` rows above, each column key is the **var token without
the `$` prefix** (so `vars("u", "nm")` produces aliases `"u"` and
`"nm"`). Entity-bound columns project to `EntitySnapshot` instances;
field-projection columns project to the field's value type.
`row_format="instance"` is only valid when `head` is a single
`Entity(var)` (either bare or wrapped in a one-element list).

Query options:
- `on_missing="error" | "skip" | "null"` — handle missing field references
- `on_type_mismatch="error" | "skip" | "null"` — handle type mismatches
- `row_format="dict" | "instance"` — Query **rejects** `"tuple"`. Default is `"dict"`.
  `"instance"` requires a single `Entity(var)` head.

Invalid `row_format` or incompatible head raises
`SDKStoreError(code=QUERY_INVALID_ROW_FORMAT)`. Unbound variables in
`where` fail at construction with `SDKDSLError(code=QUERY_UNBOUND_VAR)`.

### Rule + run

A `Rule(id, version, select, where, expose=False, ...)` is a named,
versioned single-rule inference. Required: `id`, `version`, `select`,
`where` (all non-empty). `expose=True` is required if other rules will
reference it via `RuleRef`.

```python
from kernel.sdk import Rule, vars

with vars("u",) as (u,):
    r = Rule(
        id="rule_alice",
        version="1.0.0",
        select=[u],
        where=[User(u), u.name == "Alice"],
        expose=True,
    )

rows = fg.eval.run(r)
# → [{"u": "idref_v1:User:<digest>"}, ...]   (default row_format="dict")
```

Rule's `where` accepts:
- A flat list of atoms: `[User(u), u.name == "Alice"]`
- OR a list of `Branch([...])` alternatives:
  ```python
  from kernel.sdk import Branch
  where = [
      Branch([User(u), Pred("user:lang_pref", u, lang)], id="declared_pref"),
      Branch([User(u), Pred("user:inferred_lang", u, lang)], id="inferred_pref"),
  ]
  ```
  `where` cannot mix `Branch(...)` with bare branches.
  The optional keyword-only `id=` is structural metadata for inspection
  and future semantics references. It must be unique within the inspected
  rule/inference and does not enter authoring payloads or engine adapters.

Inspect rule or inference structure before attaching runtime semantics:

```python
shape = fg.rules.inspect(r)
shape["branches"][0]["id"]          # "declared_pref"
shape["branches"][0]["fallback_id"] # "b0"
shape["branches"][0]["atom_ids"]    # ["b0.a0", "b0.a1", ...]
```

Rule `run` is a row dispatcher. Passing an `Inference` to `run`
explicitly raises (`use sdk.evaluate() instead`).

### Inference + evaluate

An `Inference(id, version, where, head=None, ...)` is a
single inference that produces accept-ready candidates. `head` is one
entity or field head. Multi-head public inferences are removed in
Track 1; use one `Inference` per head.

```python
from kernel.sdk import Inference

with vars("d", "kw") as (d, kw):
    inf = Inference(
        id="drv.document_keyword",
        version="1.0.0",
        where=[Document(d), d.title == "FactPy guide"],
        head=Document.keywords(value=kw),  # fact-candidate head
    )

candidates = fg.eval.evaluate(inf, engine="native")           # → list[CandidateSet]
candidates = fg.eval.evaluate(inf, engine="problog")          # probabilistic
candidates = fg.eval.evaluate(inf, engine="pyreason",
                              engine_options={"timesteps": 5})  # temporal
```

`engine` is **call-time**, not stored on the `Inference`. Allowed values:
`"native"` (default), `"souffle"`, `"problog"`, `"pyreason"`.
`engine="native"` rejects non-empty `engine_options`. The public SDK
`mode=` keyword is removed in Track 3 / E; use `engine=`.

For multiple output facts, define separate inferences. This keeps the
public runtime call-site aligned with `SemanticsProfile` and with the
what-if shells, all of which are single-head surfaces.

`CandidateSet` keeps internal/session `confidence` and `confidence_kind`
carriers for engine summaries, but service candidate DTOs do not expose those
legacy fields by default. Public code should treat candidates as identity,
payload, support, and evidence handles:

| Engine | `confidence` | `confidence_kind` |
|---|---|---|
| `native` / `souffle` | `None` | `"none"` |
| `problog` | probability `float` ∈ `(0, 1]` | `"probability"` |
| `pyreason` | lower-bound `float` ∈ `(0, 1]` | `"certainty"` |

### Accept

```python
result = fg.eval.accept(
    candidates[0],
    approved_by="u-admin",
    note="weekly batch",
)
```

`accept` writes the candidate's facts into the ledger. Sugar keys:
`approved_by`, `note`, `dry_run`, `identity_override` — each can also
be passed via `meta_overrides={...}` (but not in both at once).

Batch:

```python
results = fg.eval.accept_many(
    candidates,
    mode="atomic",                # or "best_effort"
    idempotent_duplicate_ok=True, # default — skip already-accepted
)
```

- Re-accepting the same candidate is idempotent (returns
  `result.kind="duplicate"`) when `idempotent_duplicate_ok=True`.
- Same claim with different business metadata such as `source` can create a
  separate assertion. Legacy candidate confidence differences alone do not
  change duplicate detection.
- `mode="atomic"` rolls the whole batch back on any failure;
  `"best_effort"` accepts what it can.

### Engine runtime options

```python
fg.eval.evaluate(inf, engine="pyreason", engine_options={"timesteps": 10})
```

`engine_options` is **call-time** runtime config. It never enters
`Rule`, `Inference`, authoring payloads, or the ledger. Engine-specific
rule projection is intentionally not carried by public SDK rule objects.
Track 2 adds lightweight public semantics wrappers as the preferred SDK
authoring shape:

```python
from kernel.sdk import Branch, ProbLogSemantics, PyReasonSemantics

inf = Inference(
    id="drv.user_tag",
    version="v1",
    where=[
        Branch([Pred("user:tag_seed", u, tag)], id="seed_path"),
        Branch([Pred("user:tag_hint", u, tag)]),
    ],
    target="user:tag",
    head_vars=[u, tag],
)

fg.eval.evaluate(
    inf,
    semantics=ProbLogSemantics(branch_probabilities={"seed_path": 0.7}),
)

fg.eval.evaluate(
    inf,
    semantics=PyReasonSemantics(
        timestep_delay=2,
        head_bound=[0.7, 0.9],
        branch_bounds={"seed_path": [0.8, 1.0], "b1": [0.2, 0.8]},
        temporal_projection={"mode": "fixed_timesteps", "timesteps": 4},
    ),
)
```

When `semantics=` is a public wrapper or `SemanticsProfile`, `engine=` is
derived from the semantics object unless explicitly provided as a mismatch
guard. `SemanticsProfile` remains exported as the advanced/canonical shape
for direct profile users and service JSON. Use `fg.eval.inspect_semantics(...)`
to inspect configured projection lanes and the wrapper's lowered canonical
profile preview. The public SDK rejects `semantics_profile=`; that name is
reserved for core/application internals.

For PyReason, `head_bound` is the default head interval for all branches.
`branch_bounds` is a per-branch override map keyed by explicit
`Branch(id=...)` values or fallback positional ids such as `b0` / `b1`.
Fallback ids are useful for quick experiments, but explicit branch ids are
more stable when an inference's branch order changes.

### Semantic annotations

PyReason runs produce `pyreason/semantic/*` annotations; ProbLog runs
produce `problog/semantic/probability`. These are persisted by adapter
helpers (not flat methods on `fg`):

```python
from kernel.adapters.pyreason.accept import persist_pyreason_annotations
from kernel.adapters.problog.accept  import persist_problog_annotations

accept_result = fg.eval.accept(candidates[0])

persist_pyreason_annotations(fg.ledger, run_id="run-1", store=fg, accept_result=accept_result)
persist_problog_annotations(fg.ledger,  run_id="run-1", store=fg, accept_result=accept_result)
```

Each helper walks the accept result, maps every accepted candidate to
its persisted `asrt_id`, and writes the engine-specific annotation
records into the ledger's annotation store.

These engine-native annotations are not the SDK's user-authored raw
uncertainty contract. For new writes, use `meta={"raw_kind": ..., "bound": ...}`.

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

All eight methods above are **also available as flat methods** on `fg` (e.g.
`fg.check(deriv, binding)`, `fg.check_fact_overlay(deriv, binding, overlay)`,
`fg.check_rule_disable(rule, support, ...)`, `fg.why_not(deriv, candidates)`).
The namespaced and flat forms are equivalent.

All return frozen application DTOs (e.g. `CheckResult`,
`DiagnoseResult`, `FactOverlayCheckResult`, `WhyNotUniverseResult`).
These DTOs are **not** in `kernel.sdk.__all__` — they live in
`kernel.application.protocol` and are imported only when the user
needs to typecheck a return value. See 06 for the result shapes.

---

## 7. Audit

```python
ref = fg.read.ref(User, user_id="u-1")

# explain_fact(pred_id, e_ref, *val_atoms) — narrow by value atoms when needed
explanation = fg.audit.explain_fact("user:name", ref)
# → {"pred_id": "user:name", "e_ref": ref, "active_claims": [...], "chosen_asrt_id": "asrt-..."}

# conflicts(pred_id, e_ref) — inspect active assertion ids on a pred+entity
conflicting = fg.audit.conflicts("user:name", ref)

# diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events,
#                   *, warnings=(), include_unchanged=False)
diff = fg.audit.diff_proof_frames(
    round_a_id,
    round_b_id,
    round_a_events,
    round_b_events,
    include_unchanged=False,  # set True to keep unchanged rows in the diff
)
```

- `explain_fact` returns the active claims for a `(pred_id, e_ref)`
  pair (optionally narrowed by trailing value atoms) plus the
  currently-chosen `asrt_id` per the current read/display policy.
- `conflicts` enumerates active conflicting assertions on the same
  `(pred_id, e_ref)` pair as `active_asrt_ids`, plus the
  `chosen_asrt_id` selected by the current read/display policy.
- `diff_proof_frames` compares two recorded inference rounds and
  returns a `ProofFrameDiff`. The `round_*_events` arguments are the
  full `tuple[RoundEvent, ...]` values captured by the round recorder
  or loaded from an audit package; `include_unchanged=False` trims the
  diff to changed rows only. `diff_proof_frames` does not read files or
  extract events from `evaluate`. See
  [06 §Q5](06_what_if_and_proof.en.md#q5-how-did-inference-change-between-rounds--fgaudit_diff_proof_frames).

---

## 8. Views and packages

### Views and ReadPolicy

The SDK keeps two related ideas separate:

- `fg.views` stores named frozen assertion-id selections. A
  `FrozenAssertionView` captures a deduplicated set of `asrt_id` strings
  at creation time.
- `ReadPolicy` is a call-site value object for read-time confidence and
  display aggregation. It is passed with `policy=...`; it is not stored in
  `fg.views` and has no named registry.

There is no built-in `default` view. The name `"default"` is not reserved:
if you create a frozen assertion view with that name, it behaves like any
other user-defined frozen assertion view.

Create a frozen assertion view from exact assertion ids or from objects
that expose `.asrt_id`:

```python
target = snap.field("name").history.where(source="seed").one()

review = fg.views.create("review_set", asrt_ids=[target.asrt_id])
review = fg.views.update("review_set", asrts=[target])

view = fg.views.get("review_set")        # → FrozenAssertionView
records = fg.assertions.by_ids(view.asrt_ids)

fg.views.delete("review_set")
all_views = fg.views.list()              # → dict[str, FrozenAssertionView]
```

Frozen assertion views are read back through `fg.assertions.by_id(...)`
and `fg.assertions.by_ids(...)`. They are not accepted as `find(...)` or
`run(...)` inputs. To inspect the assertions captured by a view, read the
membership and then look up records by id:

```python
view = fg.views.get("review_set")
records = fg.assertions.by_ids(view.asrt_ids)
```

Use `ReadPolicy` when you want read-time confidence/display metadata:

```python
from kernel.sdk import ReadPolicy

policy = ReadPolicy(
    respect_revocations=True,
    confidence_strategy="max",     # see strategy list below
    prefer_source=None,            # required when strategy="prefer_source"
)

rows = fg.read.find(User, name="Alice", policy=policy)
rows_with_meta, display_meta = fg.run(
    rule,
    policy=policy,
    return_display_meta=True,
)
```

`respect_revocations=True` means confidence/display aggregation skips
claims that have an active retraction. Set it to `False` only when you
intentionally want to inspect aggregation over both active and retracted
claims.

Aggregation strategies (`ConfidenceStrategy` literal):
- `"max"` — pick the assertion with the highest confidence (default)
- `"mean"` — average of all confidences
- `"median"` — median confidence
- `"prefer_source"` — pick assertions from the source named in
  `prefer_source`; falls back to `"max"` for sources outside the
  preferred set.

`views.create(...)` / `views.update(...)` accept exactly one payload:
`asrt_ids=[...]` or `asrts=[...]`. Passing an ambiguous payload, a raw
dict, or a `ReadPolicy` raises `SDKStoreError`.

### Packages (Souffle export and replay)

```python
from kernel.adapters.souffle.package import ExportOptions

fg.package.export_package("/tmp/my_export/", ExportOptions(package_kind="audit"))
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

All seven error codes are exported from `kernel.sdk`:

| Code | Raised when |
|---|---|
| `INVALID_ROW_FORMAT` | Rule `run` receives an unrecognized `row_format` value |
| `QUERY_INVALID_ROW_FORMAT` | Query `run` receives an invalid `row_format`, or `"instance"` is requested for a non-Entity head |
| `QUERY_MISSING_REF` | Query references an entity ref that doesn't exist in the store |
| `QUERY_TYPE_MISMATCH` | A Query value comparison hits a value of unexpected type and `on_type_mismatch="error"` |
| `QUERY_UNBOUND_VAR` | Query construction detects a `where` var with no binding upstream |
| `QUERY_ALIAS_CONFLICT` | Two Query head items lower to the same alias |
| `QUERY_NOT_IMPLEMENTED` | Query reaches a code path that is reserved but not yet wired |

```python
from kernel.sdk import (
    INVALID_ROW_FORMAT,
    QUERY_ALIAS_CONFLICT,
    QUERY_INVALID_ROW_FORMAT,
    QUERY_MISSING_REF,
    QUERY_NOT_IMPLEMENTED,
    QUERY_TYPE_MISMATCH,
    QUERY_UNBOUND_VAR,
    SDKStoreError,
)

try:
    fg.eval.run(query, row_format="banana")
except SDKStoreError as e:
    if e.code == QUERY_INVALID_ROW_FORMAT:
        print("Caller bug: row_format must be one of dict|instance")
```

`SDKDSLError` (raised by Query/Rule/Inference construction) carries
the same `code` and `path` attributes; some codes (notably
`QUERY_UNBOUND_VAR`, `QUERY_ALIAS_CONFLICT`) surface there rather than
on `SDKStoreError`.

---

## 10. Additive Schema Changes

`fg.schema.add(...)` adds new `Entity` classes to the active graph:

```python
class Account(Entity):
    account_id: str = Identity(primary_key=True)
    risk_seed: str = Field(cardinality="single")
    risk: str = Field(cardinality="single")

result = fg.schema.add(Account)
assert result.added_entities == ["Account"]
```

The returned `SchemaAddResult` records `old_digest`, `new_digest`, and
`added_entities`. It also records `added_fields` for additive field changes.
Re-adding an equivalent existing class is a no-op and returns
`added_entities=[]` and `added_fields=[]`.

To add non-identity fields to an existing entity, pass a replacement class with
the same Python class name and the added field declarations:

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

fg = FactGraph.create(schema_classes=[User])

class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    nickname: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")

result = fg.schema.add(User)
assert result.added_entities == []
assert result.added_fields == ["User.nickname", "User.tags"]
```

Existing assertions are not backfilled. Reads return the existing absence
semantics: `None` for missing single-cardinality fields and `()` for missing
multi-cardinality fields. After field-add, use the replacement class object;
reads or writes through superseded entity classes or descriptors raise
`SDKStoreError`.

The operation is immediate for the active graph: new classes can be used for
`fg.ref`, `fg.write`, `fg.read`, `fg.rules.save`, and `fg.inferences.save`
right away. If the graph is workspace-backed, call `fg.save()` to persist the
new workspace manifest digest; the manifest is not rewritten implicitly.

Only additive entity-class extension and additive non-identity field extension
are implemented here. Identity-field changes, field rewrites, destructive
removal, deprecation metadata, and migration planning are deferred:
`fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, and
`fg.schema.deprecate` are intentionally absent.

---

## 11. Registry

The graph-bound authoring registry tracks schemas, rules, and inferences
across versions. Bind it at graph construction time:

```python
from kernel.sdk import FactGraph

fg = FactGraph.create(
    schema_classes=[User, Document],
    path="/var/factpy/workspace",
)

rule_ref = fg.rules.save(my_rule)          # SavedRuleRef(rule_id, version)
inf_ref = fg.inferences.save(my_inference) # SavedInferenceRef(inference_id, version)

fg.rules.list()
fg.rules.get("rule_alice")                 # latest SavedRuleRef
fg.rules.load(rule_ref)                    # SDK Rule value object
fg.rules.load("rule_alice", version="1.0.0")
```

`SavedRuleRef` and `SavedInferenceRef` are registry load handles, not runtime
selectors. Load first, then run or evaluate the returned value object:

```python
loaded_rule = fg.rules.load(rule_ref)
rows = fg.eval.run(loaded_rule)

loaded_inf = fg.inferences.load(inf_ref)
candidates = fg.eval.evaluate(loaded_inf)
```

`SDKRegistry` is no longer part of `kernel.sdk.__all__`. Advanced migration or
debug code can still import `kernel.sdk.registry.SDKRegistry`, but normal SDK
code should use the graph-bound `fg.rules.*` and `fg.inferences.*` facades.

The workspace layout is intentionally compact:

```text
workspace/
  factgraph_workspace.json
  ledger.db
  registry/
```

`factgraph_workspace.json` uses version `"1"` and save scope `"level_4"`.
Level 4 includes ledger data, schema IR, and saved rules/inferences. It does
not include artifact sidecars, in-memory views, audit/evidence round files, or
package-export output. Use `fg.package.export_package(...)` when you need a
distribution/reproduction artifact rather than an editable workspace.

See [`04_api_surface.en.md`](04_api_surface.en.md#27-rules-namespace-fgrules)
for the `fg.rules.*` and `fg.inferences.*` method lists.

---

## 12. Where to go next

- **[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md)** —
  canonical Rule / Query / Inference DSL spec (compile-time
  constraints, `where` syntax, engine runtime options,
  `accept` parameter boundaries)
- **[`04_api_surface.en.md`](04_api_surface.en.md)** — full API
  reference with every method signature
- **[`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md)** —
  end-to-end tutorial of all nine what-if and proof methods
- **[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md)** —
  walker views, recorder lifecycle, raw DTO construction, optional
  domain helpers, engine adapter registration

---

## 13. Appendix: migration notes (v2 → v3)

The v3 SDK is API-compatible with v2 for the flat method surface.
Notable changes:

### Removed / renamed APIs

| v2 | v3 | Notes |
|---|---|---|
| `functional` field on `Field` | (removed) | Use `cardinality="single"` |
| `temporal` field on `Field` | (removed) | Temporal semantics moved to `meta` |
| `dims` field on `Field` | (removed) | Multi-dimensional fields not supported |
| `fact_key` / `pred_id` on `Pred` | (removed) | Use field accessors instead |
| `.chosen` on assertion view | (removed) | Use `snapshot.field("X").active` |
| `temporal_view` parameter | (removed) | Pass via `meta` and use a custom view |
| `mode=` keyword on SDK `evaluate` | (removed) | Use `engine=` |
| `semantics_profile=` keyword on SDK `evaluate` | (removed) | Use `semantics=` |
| public multi-head `Inference` | (removed) | Use one `Inference` per head |

### ProbLog branch probability transition

`Branch(...)` represents rule structure only. It does not carry
probability, confidence, or engine-specific parameters. Public
`body_confidences` and `engine_ext` payloads are rejected. The old names
remain only in rejection messages and adapter/internal bridges until
Track 2 makes `ProbLogSemantics` the preferred public wrapper for
branch probabilities:

```python
fg.eval.evaluate(
    deriv,
    semantics=ProbLogSemantics(branch_probabilities={"declared_pref": 0.7}),
)
```

`SemanticsProfile.rule_projection.problog` remains the advanced/canonical
shape for direct profile users and service JSON.

Track 1 adds optional structural branch ids and rule inspection:
`Branch([...], id="declared_pref")` and `fg.rules.inspect(rule_or_inference)`.
Branch ids are inspect-only SDK metadata; authoring payloads, compiled
plans, registries, and adapters still receive positional branch structure.

### PyReason profile transition

PyReason now has a core-only `SemanticsProfile` consumption path:
`Store.evaluate(..., mode="pyreason", semantics_profile=profile)`.
It accepts `rule_projection.pyreason` entries for body intervals, head
intervals, and rule `timestep_delay`, plus `temporal_projection` modes
`none`, `fixed_timesteps`, and `valid_time_boundaries`.

Track 2 makes `PyReasonSemantics` the preferred public wrapper for
currently lowerable PyReason lanes:

```python
fg.eval.evaluate(
    inf,
    semantics=PyReasonSemantics(
        timestep_delay=2,
        head_bound=[0.7, 0.9],
        temporal_projection={"mode": "fixed_timesteps", "timesteps": 4},
    ),
)
```

Track 3-post adds per-branch head interval overrides:

```python
fg.eval.evaluate(
    inf,
    semantics=PyReasonSemantics(
        head_bound=[0.5, 1.0],
        branch_bounds={
            "sensor_path": [0.8, 1.0],
            "b1": [0.2, 0.8],
        },
    ),
)
```

The SDK resolves branch ids while it still has the SDK `Inference`
object, lowers them into canonical `rule_projection.pyreason`
`target="branch:{index}", kind="interval"` entries, and the PyReason
adapter compiles those entries as per-branch head annotations. Empty
`branch_bounds={}` is equivalent to omitting branch-specific overrides.
`SemanticsProfile` remains the advanced/canonical shape for lower-level
profile users.

### Tag semantics on multi-fields

In v3, `add` on a multi-field creates a separate assertion per call
even for the same value. Use `meta` to differentiate when needed.
v2's de-duplication on `add` is gone; the v2 semantic is now expressed
via `accept(...)` idempotency.

### Row format

The default `row_format` is `"dict"`. For **Rule**, `"tuple"` still
works but emits `DeprecationWarning`. For **Query**, `"tuple"` is
**rejected** (only `"dict"` and `"instance"` are valid). New code
should always use `"dict"` or `"instance"`.
