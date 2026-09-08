# FactGraph SDK User Guide

- Applicable scope: `src/factgraph/sdk`
- Last updated: 2026-08-30

The end-to-end tour of `factgraph.sdk` for new users. Reading this doc plus
running the snippets is enough to use the SDK confidently for typical
workloads.

> **Current product path.** Sections 5–6 below retain the live/legacy
> `fg.eval.evaluate(...)` surface for compatibility. New Rule/Policy/Function
> work should start with the
> [complete Product V2 workflow](../../../../docs/quickstart/product_workflow_v2.md),
> which covers typed Query, Scenario, target-pinned execution profiles,
> structured Result/Explain data and detached replay.

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
6. [Evidence and why-not](#6-evidence-and-why-not)
7. [Audit](#7-audit)
8. [Views and packages](#8-views-and-packages)
9. [Error handling](#9-error-handling)
10. [Additive schema changes](#10-additive-schema-changes)
11. [Workspace lifecycle and legacy migration](#11-workspace-lifecycle-and-legacy-migration)
12. [Where to go next](#12-where-to-go-next)
13. [Appendix: migration notes (v2 → v3)](#13-appendix-migration-notes-v2--v3)

---

## 1. Install and FactGraph tour

### Install

```bash
python -m pip install factgraph
```

For development from source:

```bash
git clone https://github.com/Symbolic-Intelligence-Org/factgraph.git
cd factgraph
python -m pip install -e .
```

### Hello FactGraph

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity

class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tags: list[str] = Field()

fg = FactGraph.create(schema_classes=[User])

ref_alice = fg.entities.ref(User, user_id="u-1")
ref_bob   = fg.entities.ref(User, user_id="u-2")

fg.fields.set(User.name, ref_alice, "Alice")
fg.fields.set(User.name, ref_bob,   "Bob")
fg.fields.add(User.tags, ref_alice, "engineer")

snap = fg.entities.get(User, user_id="u-1")
print(snap.name, [r.value for r in snap.field("tags").active])
# → Alice ['engineer']
```

`FactGraph` is the canonical entry point. It is a literal alias of
`SDKStore` — both names refer to the same class. Operations are grouped by
navigation key: `fg.entities.*` for entity reads and lifecycle,
`fg.fields.*` for field writes, `fg.assertions.*` for assertion-id reads and
retracts, and `fg.schema.*` for schema operations.

The public namespaces:
`entities`, `fields`, `assertions`, `schema`, `eval`, `audit`, `package`,
`assertion_views`, `meta`, `rules`, and `inferences`. `meta` is the read-only
runtime-capability namespace (`fg.meta.capabilities()`); session-local named
assertion sets live under `fg.assertion_views`. See
[§0 of 04_api_surface.en.md](04_api_surface.en.md#0-namespace-map)
for the full map.

---

## 2. Schema

Schema is declared as Python classes. Every entity must declare at
least one `Identity()`; all identity fields form the immutable anchor bundle.
`Field()` declares non-identity fields, with cardinality inferred from the
type annotation.

```python
from factgraph.sdk import Entity, Field, Identity

class User(Entity):
    user_id: str = Identity()
    name: str = Field()

class Document(Entity):
    doc_id: str = Identity()
    title: str = Field()
    keywords: list[str] = Field()
    author: User = Field()  # entity_ref to User
```

### Compile and instantiate

`FactGraph.create(...)` compiles, validates, and constructs in one step:

```python
fg = FactGraph.create(schema_classes=[User, Document])
```

Pass `path=` when the graph should own a durable workspace. A workspace stores
the Database ledger, immutable transaction chain, and content-addressed schema
objects. Writes are durable when their SDK call returns:

```python
fg = FactGraph.create(schema_classes=[User, Document], path="./workspace")
ref = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.name, ref, "Alice")
fg.close()

same_graph = FactGraph.load_workspace("./workspace", schema_classes=[User, Document])
same_graph.close()
```

`FactGraph.load_workspace(...)` requires the same Python `Entity` classes used to create
the workspace. It validates the transaction history, active-state
digest, assertion content digests, Database schema object, and supplied classes
before returning a graph. Create/load holds an exclusive writer lock until
`close()`; opening the same durable workspace twice fails explicitly.

You can also compile separately:

```python
from factgraph.sdk import compile_schema_from_classes, schema_preflight_from_classes

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
report = fg.schema.validate_provenance(provenance_payload)
report.ok                # True if everything passes
report.warnings          # list[dict] — non-fatal advisories
report.errors            # list[dict], each: {code, severity, path, message, data}
```

This inspects provenance/meta payloads **without** writing. Returns a
`ValidationReport(ok, warnings, errors, diagnostics_contract_version)`.

---

## 3. Reading

### Get one entity by identity

```python
snap = fg.entities.get(User, user_id="u-1")          # → EntitySnapshot | None
```

### Find entities

```python
# By exact value on a single-cardinality field
admins = fg.entities.where(User, name="Alice")

# Multi-cardinality field uses containment match
engineers = fg.entities.where(User, tags="engineer")

# Limit result count
recent = fg.entities.where(Document, limit=20)
```

### Reference encoding

```python
ref = fg.entities.ref(User, user_id="u-1")
# → "idref_v1:User:<base32-sha256-digest>"  (opaque, content-derived)
```

`ref` is required as the second argument to `fg.fields.set(...)` and
`fg.fields.add(...)`. `fg.assertions.retract(...)` takes an assertion id
(`asrt_id`), not an entity ref. The ref string is opaque — never parse or
compare it as a textual identity; treat it as a stable handle.

### `EntitySnapshot` cheat-sheet

```python
snap = fg.entities.get(User, user_id="u-1")

snap.name                         # current single-field value
snap.field("tags").active         # → AssertionRecordSet (tuple-compatible)
[r.value for r in snap.field("tags").active]   # → ['engineer', ...]

snap.field("name").history      # → AssertionRecordSet (active + revoked)
snap.field("name").at("2026-05-01T00:00:00Z")  # active shortcut visible at t
snap.field("name").where(_meta={"version": "v3"})  # active records at version v3
snap.field("name").history.at("2026-05-01T00:00:00Z")  # history-level time filter
snap.field("name").history.by_id(asrt_id)      # exact assertion-id filter

target = (
    snap.field("name")
    .history.where(value="Alice", _meta={"source": "seed"})
    .one()
)
fg.assertions.retract(target.asrt_id)

snap.assertions.field("name")     # equivalent field-scoped assertion manager
snap.assertions.name              # shorthand when no manager method collides
snap.identity                     # dict of identity values (when identity_available=True)
snap.identity_available           # bool — False if snapshot lacks full identity
snap.entity_type                  # "User"
snap.ref                          # encoded idref_v1 ref
```

Notes:
- `.active`, `.all`, and `.history` are properties. `active` returns currently
  non-revoked records; `all` returns active plus revoked records.
  `.history` is a deprecated compatibility alias for `.all` and warns only
  when `FACTGRAPH_WARN_DEPRECATED=1`.
- Legacy call forms such as `.active()` and `.all()` remain accepted:
  assertion record sets are callable and return themselves.
- `AssertionView.at(t)` is an active-only shortcut for `.active.at(t)`.
  Version filtering uses `.where(_meta={"version": ...})`.
- `.active`, `.history`, `.all`, and record-set filters return `AssertionRecordSet`,
  a tuple-compatible collection of `AssertionRecord` values. Existing
  tuple-style iteration, indexing, and `len(...)` still work.
- `AssertionRecordSet` supports `.where(...)`, `.at(t)`,
  `.by_id(asrt_id)`, `.one()`, `.first()`, and `.all()`. Use chained
  filters plus `.one()` for exactly-one selection before retracting an
  assertion.
- `.at(t)` is a business-valid-time filter over assertion metadata
  `valid_from` / `valid_to`; it does not filter by `ingested_at`.
- `AssertionRecord` exposes `asrt_id`, `value`, `is_active`, context
  fields (`entity_type`, `field_name`, `pred_id`, `e_ref`), and `meta`
  (an `AssertionMeta`). Use `not record.is_active` for revoked/inactive
  records.
- `EntitySnapshot` is read-only; assigning to any attribute raises
  `FrozenSnapshotError`.

---

## 4. Writing

Four primitive operations: `set`, `add`, `retract`, `edit`. Plus
`ingest` for bulk insertion from external sources, and `batch` for
grouping multiple operations into one transaction.

### Single writes

```python
ref = fg.entities.ref(User, user_id="u-1")

name_asrt_id = fg.fields.set(User.name, ref, "Alice Liddell")
tag_asrt_id = fg.fields.add(User.tags, ref, "manager")
fg.assertions.retract(tag_asrt_id)                    # by assertion id
```

`set` on a multi-field raises `CardinalityError`. `add` on a
single-field raises `CardinalityError`. `set(...)` and `add(...)`
return the persisted `asrt_id`; later reads expose the same id through
`AssertionRecord.asrt_id`.

### Transactional editor

```python
with fg.entities.edit(User, user_id="u-1") as ed:
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

Batch entity handles require a complete identity bundle. The initial
`tx.entity(...)` call must provide every `Identity()` value. Identity defaults
are not materialized implicitly; writes always target one complete identity
coordinate.

### Bulk ingest

`fg.schema.ingest(items, *, meta=None)` is the external-batch import path. Each
item is one normalized fact write:

```python
ref_carol = fg.entities.ref(User, user_id="u-3")
ref_dave  = fg.entities.ref(User, user_id="u-4")

result = fg.schema.ingest(
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
`confidence` and `confidence_source` are removed user-authored write keys.
Use `raw_kind` and `bound` for uncertainty inputs.

Raw uncertainty validation:

```python
fg.fields.set(User.name, ref, "Alice", meta={
    "raw_kind": "probabilistic",
    "bound": [0.2, 0.8],
})  # ✅

fg.fields.set(User.name, ref, "Alice", meta={"raw_kind": "probabilistic"})  # ❌ bound missing
fg.fields.set(User.name, ref, "Alice", meta={"bound": [0.2, 0.8]})          # ❌ raw_kind missing
fg.fields.set(User.name, ref, "Alice", meta={"probability": 0.8})           # ❌ removed write key
```

Removed uncertainty write keys:

```python
fg.fields.set(User.name, ref, "Alice", meta={"confidence": 0.85})          # ❌ removed write key
fg.fields.set(User.name, ref, "Alice", meta={"confidence_source": "ml"})   # ❌ removed write key
```

### Which write entry point?

| If you need to ... | Use |
|---|---|
| Insert one fact | `fg.fields.set` / `fg.fields.add` |
| Update multiple fields atomically on one entity | `fg.entities.edit(...)` context manager |
| Group writes across multiple entities | `fg.batch(...)` context manager |
| Bulk-insert from external data | `fg.schema.ingest(...)` |
| Explain derived rows | `row.explain()` or `fg.eval.explain(expr, head=row.close())` |

---

## 5. Eval — Rule / Query / Inference

Three primitives:

| | Purpose | Returned by |
|---|---|---|
| `Rule` | Application protocol Rule used as an evaluation head or closed replay head | `from factgraph.sdk import Rule` |
| `Query` | Read-side projection over the current store | `fg.entities.*` and query helpers |
| `Inference` | A single inference (one head); produces evaluation rows | `fg.eval.evaluate(inf, engine=...)` → `EvaluateResult` |
| `RuleExpr` | Application-rule composition; evaluates with an inline, external, or projection `head=` | `fg.eval.evaluate(expr, head=rule, engine=...)` → `EvaluateResult` |

All three are constructed inside a `with vars(...) as (...):` block.
For the deeper DSL spec see
[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md).
That spec also covers the RuleExpr authoring surface:
`Rule` / `build_application_rule(...)`, `&` / `|` composition,
explicit `.eq(...)` joins, `.join_by_ports(...)`, bool guards, and
`fg.rules.inspect(...)` return-shape differences.
RuleExpr execution uses that same staged surface: pass an application `Rule` or
RuleExpr to `fg.eval.evaluate(..., head=...)`, keep joins explicit, and use
inline, external, or `Rule.projection(...)` heads. `fg.rules.inspect(...)`
reports closed-head status for application Rule inputs through `is_closed` and
`unbound_ports`; structural RuleExpr inspect does not define closed-head
semantics.

### Query

A `Query(head, where, on_missing?, on_type_mismatch?)` projects rows from
the current ledger. `head` is either a single item or a list of items —
each item is an entity binding (`Entity(var)`) or a field projection
(`Entity.field(...)`). `where` is the body (always a list).

```python
from factgraph.sdk import Query, vars

# Multi-projection head — list of two items, returns one column per item
with vars("u", "nm") as (u, nm):
    q = Query(
        head=[User(u), User.name(name=nm)],
        when=[User(u), u.name == nm],
    )

rows = fg.entities.where(User)
# → [<EntitySnapshot User Alice>, ...]

# Single-projection head — pass the item directly OR wrap it in a list
with vars("u",) as (u,):
    q_one = Query(head=User(u), when=[User(u)])           # single item
    q_one_list = Query(head=[User(u)], when=[User(u)])    # equivalent
    snaps = fg.entities.where(User)
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

An application `Rule(id, where, ports, version=..., repr=...)` is the
canonical reusable read pattern. Required: `id`, `ports`, `where` (all
non-empty); `version` is optional. Use the `build_application_rule(...)`
SDK bridge to construct one from Entity-DSL atoms; direct `Rule(...)`
construction requires raw `factgraph.core.rules.where_ast` atoms.

```python
from factgraph.sdk import build_application_rule, vars

with vars("u",) as (u,):
    r = build_application_rule(
        id="User:exists",
        version="1.0.0",
        when=[User(u), User(u).name == "Alice"],
        ports={"user": u},
    )

result = fg.eval.evaluate(r, head=r)
# → EvaluateResult(rows=(...), ...)
```

The `id=` must match a real predicate whose argument shape lines up with
the rule's `ports` (e.g. `User:exists` is a 1-arg existence predicate that
fits a single `user` port). Use `<entity>:<field>` predicate ids when the
rule projects multiple ports.

Application Rule `where` is AND-only: a flat list of atoms such as
`[User(u), User(u).name == "Alice"]`. `Case(...)` alternatives are not
accepted in application Rule bodies; use multi-branch composition via
`RuleExpr` (the `&` / `|` operators on application `Rule` values) or place
branch alternatives inside an `Inference` body.

Inspect rule or inference structure before attaching runtime semantics:

```python
shape = fg.rules.inspect(r)
shape["branches"][0]["id"]          # "declared_pref"
shape["branches"][0]["fallback_id"] # "c0"
shape["branches"][0]["atom_ids"]    # ["c0.c0", "c0.c1", ...]
```

Rule `run` is a row dispatcher. Passing an `Inference` to `run`
explicitly raises (`use sdk.eval.evaluate() instead`).

### Inference + evaluate

An `Inference(id, version, when, head=None, ...)` is a
single inference that produces accept-ready candidates. `head` is one
entity or field head. Multi-head public inferences are removed in
Track 1; use one `Inference` per head.

```python
from factgraph.sdk import Inference

with vars("d", "kw") as (d, kw):
    inf = Inference(
        id="drv.document_keyword",
        version="1.0.0",
        when=[Document(d), d.title == "FactPy guide"],
        head=Document.keywords(value=kw),  # fact-candidate head
    )

result = fg.eval.evaluate(inf, engine="native")               # → EvaluateResult
result = fg.eval.evaluate(inf, engine="problog")              # probabilistic rows
result = fg.eval.evaluate(inf, config=PyReasonConfig(...))
```

`engine` is **call-time**, not stored on the `Inference`. Allowed values:
`"native"` (default), `"souffle"`, `"problog"`, `"pyreason"`.
The public SDK rejects `engine_options=`, `registry=`, and the removed
`mode=` keyword. Use `engine=` and `config=`.

For multiple output facts, define separate inferences. This keeps the
public runtime call-site aligned with `SemanticsProfile` and with the
what-if shells, all of which are single-head surfaces.

`EvaluateRow.raw_kind` and `EvaluateRow.bound` are the public quantitative
carriers. Public code should treat `EvaluateResult` rows as bindings, claims,
and evidence anchors:

| Engine | `raw_kind` | `bound` |
|---|---|---|
| `native` / `souffle` | `None` | `None` |
| `problog` | `"probabilistic"` | probability point interval |
| `pyreason` | `"possibilistic"` | certainty interval |

### Explain

```python
row = result.first()
assert row is not None
explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(inf, head=closed_head)
```

Evaluation is read-only. Candidate accept shells are not part of the T5 public
SDK; persist new facts with explicit `fg.fields.*`, `fg.entities.*`, or
`fg.batch(...)` writes.

### Engine runtime options

```python
fg.eval.evaluate(
    inf,
    config=PyReasonConfig(
        temporal_projection={
            "mode": "fact_boundaries",
            "universe": ["2026-01-01", "2026-12-31"],
        },
    ),
)
```

Engine-specific rule projection is intentionally not carried by public SDK
rule objects. Track 2 adds lightweight public semantics wrappers as the
preferred SDK authoring shape:

```python
from factgraph.sdk import Case, EmitSpec, ProbLogConfig, PyReasonConfig

inf = Inference(
    id="drv.user_tag",
    version="v1",
    when=[
        Case([Pred("user:tag_seed", u, tag)], id="seed_path"),
        Case([Pred("user:tag_hint", u, tag)]),
    ],
    emits=EmitSpec("user:tag", [u, tag]),
)

fg.eval.evaluate(
    inf,
    config=ProbLogConfig(case_probabilities={"seed_path": 0.7}),
)

fg.eval.evaluate(
    inf,
    config=PyReasonConfig(
        timestep_delay=2,
        iteration_count=3,
        derived_bound=[0.7, 0.9],
        case_bounds={"seed_path": [0.8, 1.0], "c1": [0.2, 0.8]},
    ),
)
```

When `config=` is a public wrapper or `SemanticsProfile`, `engine=` is
derived from the semantics object unless explicitly provided as a mismatch
guard. `SemanticsProfile` remains exported as the advanced/canonical shape
for direct profile users and service JSON. Use `fg.eval.preview_config(...)`
to inspect configured projection lanes and the wrapper's lowered canonical
profile preview. The public SDK rejects `semantics_profile=`; that name is
reserved for core/application internals.

For ProbLog, `uncertainty_projection` controls how raw `raw_kind` + `bound`
inputs are projected to point probabilities. The default rejects raw
uncertainty until you choose a policy such as `lower`, `midpoint`, `upper`, or
`identity_probability`.

For PyReason, prefer canonical `iteration_count`, `derived_bound`,
`atom_bounds`, `fact_boundaries`, and `time_binned` for new code. Legacy
`head_bound`, `case_bounds`, `fixed_timesteps`, and `valid_time_boundaries`
remain compatibility surfaces. `atom_bounds` keys use application atom ids such
as `<rule_id>:atom_<index>` and are for application `Rule` inputs. For full
legacy configuration examples, see
[`docs/quickstart/engines_and_configs.md`](../../../../docs/quickstart/engines_and_configs.md).
For new Product V2 code, use target-pinned execution profiles from the
[complete Product V2 workflow](../../../../docs/quickstart/product_workflow_v2.md)
instead of passing arbitrary engine config to a Rule or Policy.

### Semantic annotations

PyReason and ProbLog adapters may produce engine-native evidence and
quantitative carrier data during evaluation. T5 public SDK code reads those
through `EvaluateRow.raw_kind`, `EvaluateRow.bound`, and `row.explain()`;
adapter-native annotation persistence is not a public SDK accept workflow.

For new user-authored writes, use
`meta={"raw_kind": ..., "bound": ...}`.

---

## 6. Evidence And Why-Not

The public evidence path is `EvaluateResult` plus `Explanation`:

| Method | Question |
|---|---|
| `row.explain()` | Why did this evaluated row pass? |
| `row.close()` | Produce a closed Rule replay head for this row |
| `fg.eval.explain(expr, head=closed_head)` | Replay a closed-head explanation |

Failed explanations use `Explanation(status="failed")` with
`failure_class`; `Explanation.repr` returns a deterministic failure summary.
There is no public `.eval.why_not(...)` or `fg.what_if.*`
candidate-universe shell in T5.

For the distinct, replacement-only Scenario path, start from a resolved Query:
`fg.query(...).bind(...).select(...).what_if(scenario).run()`. It returns a
detached `ScenarioRunV0` with `.diff()`, `.verify()`, and side-specific
`.explain(...)`; it is not a general What-if shell or an `EvaluateResult`.
See [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

For native or Souffle passed rows, `row.explain().evidence` is a row-level Form
1 `EvidenceGraph`: a root conclusion, selected-branch premises, assertion
seeds, and `supports` edges. For ProbLog passed rows, it is a row-level
provenance graph with `derives` edges and ProbLog trace / uncertainty projection
details under `engine_meta["problog"]`. The graph metadata mirrors the
row/result audit context; `run_id` stays on the `EvaluateResult` envelope.
Read `row.explain().repr` for deterministic multi-line text walked from that
graph. Unsupported and invalid request explanations return `None` for `repr`.
Treat PyReason row-level graphs, aggregate contributor envelopes, failed-graph
trees, and match witness output as future evidence tracks. The full legacy DTO
chain and current Product V2 structured Result/Explain/replay boundaries are
documented in
[Evaluation and evidence](../../../../docs/quickstart/evaluate_and_evidence.md).

---

## 7. Audit

```python
ref = fg.entities.ref(User, user_id="u-1")

# explain(asrt_id_or_record) — narrow by value atoms when needed
explanation = fg.audit.explain("user:name", ref)
# → {"pred_id": "user:name", "e_ref": ref, "active_claims": [...], "chosen_asrt_id": "asrt-..."}

# conflicts(record_or_entity_field) — inspect active assertion ids on a pred+entity
conflicting = fg.audit.conflicts(record)

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

- `explain` returns the active claims for a `(pred_id, e_ref)`
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

### Views

`fg.assertion_views` stores named frozen assertion-id selections. A
`FrozenAssertionSet` captures a deduplicated set of `asrt_id` strings
at creation time.

There is no built-in `default` view. The name `"default"` is not reserved:
if you create a frozen assertion view with that name, it behaves like any
other user-defined frozen assertion view.

Create a frozen assertion view from exact assertion ids or from objects
that expose `.asrt_id`:

```python
target = snap.field("name").history.where(_meta={"source": "seed"}).one()

review = fg.assertion_views.create("review_set", asrt_ids=[target.asrt_id])
review = fg.assertion_views.update("review_set", asrts=[target])

view = fg.assertion_views.get("review_set")        # → FrozenAssertionSet
records = fg.assertions.by_ids(view.asrt_ids)

fg.assertion_views.delete("review_set")
all_views = fg.assertion_views.list()              # → dict[str, FrozenAssertionSet]
```

Frozen assertion views are read back through `fg.assertions.by_id(...)`
and `fg.assertions.by_ids(...)`. They are not accepted as `find(...)` or
`run(...)` inputs. To inspect the assertions captured by a view, read the
membership and then look up records by id:

```python
view = fg.assertion_views.get("review_set")
records = fg.assertions.by_ids(view.asrt_ids)
```

`views.create(...)` / `views.update(...)` accept exactly one payload:
`asrt_ids=[...]` or `asrts=[...]`. Passing an ambiguous payload, a raw
dict, or unsupported view payload raises `SDKStoreError`.

### Packages (Souffle export and replay)

```python
from factgraph.adapters.souffle.package import ExportOptions

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
    fg.fields.set(User.tags, ref, "engineer")  # multi-field; should be add
except CardinalityError as e:
    print(e.field_name, e.actual_cardinality, e.operation)
    # → tags multi set
```

| Class | When |
|---|---|
| `SDKSchemaError` | Schema preflight or compilation issue |
| `SDKStoreError` | Most write/read/eval/what-if/audit failures |
| `EntityNotFoundError` | `fg.entities.get` / `fg.entities.edit` on missing identity |
| `CardinalityError` | `set` on multi-field, or `add` on single-field |
| `FrozenSnapshotError` | Assigning to a snapshot or namespace attribute |
| `EditorClosedError` | Operating on a committed/rolled-back editor |

### Error code constants

All seven error codes are exported from `factgraph.sdk`:

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
from factgraph.sdk import (
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
    fg.eval.evaluate(query)
except SDKStoreError as e:
    print("Caller bug: Query is not a T5 public evaluation entrypoint")
```

`SDKDSLError` (raised by Query/Rule/Inference construction) carries
the same `code` and `path` attributes; some codes (notably
`QUERY_UNBOUND_VAR`, `QUERY_ALIAS_CONFLICT`) surface there rather than
on `SDKStoreError`.

---

## 10. Additive Schema Changes

`fg.schema.apply(...)` adds new `Entity` classes to the active graph:

```python
class Account(Entity):
    account_id: str = Identity()
    risk_seed: str = Field()
    risk: str = Field()

result = fg.schema.apply(Account)
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
    user_id: str = Identity()
    name: str = Field()

fg = FactGraph.create(schema_classes=[User])

class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    nickname: str = Field()
    tags: list[str] = Field()

result = fg.schema.apply(User)
assert result.added_entities == []
assert result.added_fields == ["User.nickname", "User.tags"]
```

Existing assertions are not backfilled. Reads return the existing absence
semantics: `None` for missing single-cardinality fields and `()` for missing
multi-cardinality fields. After field-add, use the replacement class object;
reads or writes through superseded entity classes or descriptors raise
`SDKStoreError`.

The operation is immediate and durable for a Database-backed graph: new
classes can be used for `fg.entities.*`, `fg.fields.*`, `fg.assertions.*`,
in-memory `Rule(...)`, and in-memory `Inference(...)` right away. The schema
change is an isolated transaction that commits the old/new schema digests and
the new canonical schema object. `fg.save_workspace()` is not required.

Only additive entity-class extension and additive non-identity field extension
are implemented here. Identity-field changes, field rewrites, destructive
removal, deprecation metadata, and migration planning are deferred:
`fg.schema.delete`, `fg.schema.update`, `fg.schema.migrate`, and
`fg.schema.deprecate` are intentionally absent.

---

## 11. Workspace Lifecycle and Legacy Migration

Workspace persistence is now graph-bound and Database-owned. Bind a graph to a
workspace with `path=`:

```python
from factgraph.sdk import FactGraph

fg = FactGraph.create(
    schema_classes=[User, Document],
    path="/var/factpy/workspace",
)
```

`FactGraph.create(path=...)` and `FactGraph.load_workspace(...)` own their
Database and hold its exclusive writer lock. Use `fg.close()` or a context
manager before another process or graph opens the same workspace. v0.3 does
not provide a read-only durable open channel.

All canonical writes are write-through. `fg.save_workspace()` only updates
`db/meta.json:last_saved_at_epoch_ns`; it does not copy SQLite, advance the
transaction head, or form a commit boundary. Consequently, the legacy
"load, modify, omit save to discard" pattern no longer works. Copy the entire
closed workspace directory first, then open the copy for dry-run or sandbox
work.

> Q8 Phase 2 removed the SavedRule/SavedInference persistence layer. The
> graph-bound `fg.rules.*` namespace exposes `fg.rules.inspect(...)` only;
> `fg.rules.save / load / list / get`, `fg.inferences.save / load / list / get`,
> `SavedRuleRef`, and `SavedInferenceRef` are no longer part of the SDK
> surface. Rules and inferences are now used as in-memory value objects:

```python
from factgraph.sdk import Inference, build_application_rule, vars

with vars("u",) as (u,):
    my_rule = build_application_rule(
        id="User:exists",
        version="1.0.0",
        when=[User(u), User(u).name == "Alice"],
        ports={"user": u},
    )
result = fg.eval.evaluate(my_rule, head=my_rule)

my_inference = Inference(...)
candidates = fg.eval.evaluate(my_inference)
```

`SDKRegistry`, `FileAuthoringRegistry`, `SDKRegistryError`, `registry_root=`,
and `registry=` were removed by A20(E) / Q6-A. Pass `path=` for workspace
persistence. Migrate a closed v0.2 `ledger.db` workspace explicitly:

```bash
python -m factgraph migrate-workspace /var/factpy/workspace
```

The workspace layout is intentionally compact:

```text
workspace/
  factgraph_workspace.json
  db/
    assertions.db
    meta.json
    writer.lock
    objects/
      schema/
        <schema-digest>.json
      tx/
        <tx-digest>.json
    refs/                      # reserved; empty in v0.3 (head is in ledger_meta)
  views/                       # created lazily by db.create_view(...)
    objects/<view-digest>.json
```

`factgraph_workspace.json` uses version `"1"` and points only to `db/` and
`views/`. The current head and state commitment live transactionally in
`db/assertions.db`; schema and tx objects are content-addressed and write-once.
The workspace excludes artifact sidecars, in-memory assertion views,
audit/evidence round files, package-export output, and live registry content.
Use `fg.package.export_package(...)` for a distribution/reproduction artifact.

Legacy workspaces are never auto-migrated: `FactGraph.load_workspace(...)`
raises `SDKStoreError` with the command above. The CLI verifies a staging v0.3
workspace, preserves legacy rows and assertion ids, and writes a genesis import
transaction using ordinary assertion, revocation, and append-meta
operations because v0.2 commit history cannot be reconstructed. By default the
complete source is retained under `workspace.legacy.<UTC timestamp>/`; use
`--no-archive` only when that backup is intentionally unnecessary. Apply-log
readers remain compatible with
historical `db/audit/authoring_apply_events.jsonl`,
package-local `authoring_apply_events.jsonl`, and legacy
`registry/authoring_apply_events.jsonl` inputs. The service `/v1/registry/*`
routes were deleted.

During replacement, the CLI temporarily holds the complete source in a visible
`<workspace-name>.legacy-<UTC timestamp>` sibling. If migration is interrupted,
rerun the command. A `workspace_recovery_required` response lists candidate
siblings and says whether a replacement exists. Verify the candidate, then
restore it when the workspace is missing, or explicitly archive/remove it when
the replacement is valid. The CLI never chooses automatically.

See [`04_api_surface.en.md`](04_api_surface.en.md#27-rules-namespace-fgrules)
for the post-Phase-2 `fg.rules.*` and `fg.inferences.*` namespace shape.

---

## 12. Where to go next

- **[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md)** —
  canonical Rule / Query / Inference DSL spec (compile-time
  constraints, `where` syntax, engine runtime options,
  `accept` parameter boundaries, RuleExpr authoring, joins, bool guards,
  and inspect return-shape differences)
- **[`04_api_surface.en.md`](04_api_surface.en.md)** — full API
  reference with every method signature
- **[`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md)** —
  V1 Query/Scenario What-if, detached Explain/replay boundaries, and the
  bounded legacy captured ScenarioRun path
- **[`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md)** —
  walker views, recorder lifecycle, raw DTO construction, optional
  domain helpers, engine adapter registration

---

## 13. Appendix: migration notes (v2 → v3)

The v3 SDK removed the v2 flat method surface in favor of namespace managers.
Notable changes:

### Removed / renamed APIs

| v2 | v3 | Notes |
|---|---|---|
| `functional` field on `Field` | (removed) | Use `cardinality="single"` |
| `temporal` field on `Field` | (removed) | Temporal semantics moved to `meta` |
| `dims` field on `Field` | (removed) | Multi-dimensional fields not supported |
| `fg.get/find/ref/match` | `fg.entities.get/where/ref/match` | Layer 1 entity navigation |
| (new in v3) | `fg.entities.create` | Explicit complete Identity Claim bundle emit; entity-domain `:exists` is projected virtually rather than persisted |
| (new in v3) | `fg.entities.delete` | Whole-entity retract; PF-S2 Form A `(e_ref)` or Form B `(EntityCls, **identity)` |
| (new in v3) | `fg.entities.exists` | Boolean visibility check on the active Identity Claim bundle (no snapshot materialization) |
| `fg.set/add` | `fg.fields.set/add` | Layer 2 field writes |
| `fg.retract` | `fg.assertions.retract` | Layer 3 assertion-id mutation |
| `fg.edit` | `fg.entities.edit` | EntityEditor entry point |
| `fg.schema.add` | `fg.schema.register/extend/apply` | Explicit schema operation intent |
| `fact_key` / `pred_id` on `Pred` | (removed) | Use field accessors instead |
| `.chosen` on assertion view | (removed) | Use `snapshot.field("X").active` |
| `temporal_view` parameter | (removed) | Pass via `meta` and use a custom view |
| `mode=` keyword on SDK `evaluate` | (removed) | Use `engine=` |
| `semantics_profile=` keyword on SDK `evaluate` | (removed) | Use `config=` |
| public multi-head `Inference` | (removed) | Use one `Inference` per head |

### ProbLog branch probability transition

`Case(...)` represents rule structure only. It does not carry
probability, confidence, or engine-specific parameters. Public
`body_confidences` and `engine_ext` payloads are rejected. The old names
remain only in rejection messages and adapter/internal bridges.
`ProbLogConfig` is the preferred public wrapper for branch probabilities
and raw-uncertainty projection:

```python
fg.eval.evaluate(
    deriv,
    config=ProbLogConfig(case_probabilities={"declared_pref": 0.7}),
)
```

`SemanticsProfile.rule_projection.problog` remains the advanced/canonical
shape for direct profile users and service JSON.

`ProbLogConfig()` rejects raw uncertainty by default. Configure
`uncertainty_projection` explicitly when projecting
`meta={"raw_kind": ..., "bound": ...}` intervals into ProbLog point
probabilities; use the quickstart semantics page for the policy list.

Track 1 adds optional structural branch ids and rule inspection:
`Case([...], id="declared_pref")` and `fg.rules.inspect(rule_or_inference)`.
Case ids are inspect-only SDK metadata; authoring payloads, compiled
plans, registries, and adapters still receive positional branch structure.

### PyReason profile transition

PyReason now has a core-only `SemanticsProfile` consumption path:
`Store.evaluate(..., mode="pyreason", semantics_profile=profile)`.
It accepts `rule_projection.pyreason` entries for body intervals, head
intervals, and rule `timestep_delay`, plus canonical profile fields such as
`iteration_count`, `temporal_projection`, and `rule_projection.pyreason`.
Current temporal modes are `none`, `fixed_timesteps`, `fact_boundaries`,
`valid_time_boundaries`, and `time_binned`.

`PyReasonConfig` is the preferred public wrapper for currently lowerable
PyReason lanes:

```python
fg.eval.evaluate(
    inf,
    config=PyReasonConfig(
        timestep_delay=2,
        iteration_count=3,
        derived_bound=[0.7, 0.9],
    ),
)
```

Use `fact_boundaries` for canonical valid-time projection and `time_binned`
for fixed temporal bins:

```python
fg.eval.evaluate(
    inf,
    config=PyReasonConfig(
        temporal_projection={
            "mode": "time_binned",
            "universe": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
            "bin_size": "PT1H",
        },
    ),
)
```

`PyReasonConfig()` lowers to canonical `iteration_count=1`; do not combine
`iteration_count` with temporal modes that also imply timesteps. Legacy
`head_bound`, `case_bounds`, `fixed_timesteps`, and
`valid_time_boundaries` remain accepted for compatibility, but new examples
should prefer `derived_bound`, `atom_bounds`, `fact_boundaries`, and
`time_binned`. `time_binned.bin_size` is strict: ISO-style `P<n>D` /
`PT<n>H` / `PT<n>M`, or exactly `1d`, `1h`, `15m`, `1m`.
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
