# Assertion records and views

Read and write worked at the snapshot level. This page goes one layer deeper.
Every fact you wrote is an `assertion`, and every assertion has a durable
identity called `asrt_id`. Working at this level is how you do precise edits,
named record selections, and audit-friendly retracts without ambiguity.

The mental model is:

```text
ledger
  -> assertion records (asrt_id + value + meta + active/revoked)
    -> grouped by entity coordinate     -> EntitySnapshot
    -> selected by id membership        -> FrozenAssertionView
    -> looked up by id                  -> fg.assertions.by_id
```

The discipline is:

```text
read side finds "which assertion";
write side only revokes that exact asrt_id.
```

If you remember one sentence: **FactGraph does not overwrite a row. It appends
assertions, and it revokes specific assertion ids.** The common misconception
this page prevents is treating snapshots like mutable table rows.

## Writes return assertion ids

`fg.write.set(...)` and `fg.write.add(...)` both return the `asrt_id` of the
assertion they just appended. Keeping that id is the simplest way to inspect
or retract that exact write later.

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
alice = fg.read.ref(User, user_id="u-1")

name_seed = fg.write.set(
    User.name,
    alice,
    "Alice",
    meta={"source": "seed", "trace_id": "import-001"},
)
name_hr = fg.write.set(
    User.name,
    alice,
    "Alice Liddell",
    meta={"source": "hr", "trace_id": "hr-2026-05"},
)

engineer = fg.write.add(
    User.tags,
    alice,
    "engineer",
    meta={
        "source": "profile",
        "trace_id": "profile-001",
        "valid_from": "2026-01-01T00:00:00Z",
        "version": "tag-v1",
    },
)
reviewer = fg.write.add(
    User.tags,
    alice,
    "reviewer",
    meta={"source": "import", "trace_id": "import-002"},
)
```

Calling `set(...)` twice on a single field does not overwrite the first
assertion. The second call appends a second assertion. Both stay in the
ledger. The snapshot scalar view picks the latest one.

```python
snap = fg.read.get(User, user_id="u-1")

assert snap.name == "Alice Liddell"
assert set(snap.tags) == {"engineer", "reviewer"}
```

## AssertionRecord shape

`AssertionRecord` is the unit of fact identity. The interesting attributes
are:

```text
record.asrt_id     -> str, durable id
record.value       -> the raw value
record.is_active   -> bool
record.entity_type -> SDK entity type name
record.field_name  -> SDK field name
record.pred_id     -> kernel predicate id
record.e_ref       -> encoded entity ref
record.meta        -> AssertionMeta
```

`AssertionMeta` exposes a fixed set of first-class slots plus a `raw`
dictionary for everything else you passed at write time.

### First-class slots

```text
meta.source                  -> "seed" / "hr" / "import"
meta.source_loc              -> sub-source locator (line, range, region)
meta.trace_id                -> "import-001"
meta.ingested_at             -> datetime, set by the ledger
meta.approved_by             -> reviewer id
meta.note                    -> free-form text
meta.derived_rule_id         -> set by accept(...) for inferred facts
meta.derived_rule_version
meta.candidate_id / candidate_key / candidate_kind
                             -> set by accept(...) for inferred facts
meta.raw                     -> dict[str, Any]
```

`raw` is the full meta dictionary as stored. First-class slots are
projections out of it. If you wrote `meta={"version": "tag-v1", "valid_from":
"..."}`, those keys live in `raw`.

### Convention meta keys you can write

These keys are recognized at write time. Anything outside this set still
goes through (it lands in `meta.raw`), but engines and adapters do not
interpret it.

| Key | Type | Notes |
| --- | --- | --- |
| `source` | str | Origin tag (`"import"`, `"hr"`, etc.). Participates in the ingest key. |
| `source_loc` | str | Sub-source locator (line range, region, document path). |
| `trace_id` | str | Cross-system trace identifier. Participates in the ingest key. |
| `raw_kind` | `"probabilistic"` or `"possibilistic"` | Raw uncertainty kind. **Must be paired with `bound`.** |
| `bound` | `[lower, upper]` | Two-element JSON list of floats in `[0, 1]` with `lower <= upper`. **Must be paired with `raw_kind`.** |
| `approved_by` | str | Reviewer id, for governance. |
| `note` | str | Free-form annotation. |
| `valid_from` / `valid_to` | str | Business-time interval endpoints (ISO 8601). Used by `.at(t)`. Land in `meta.raw`. |
| `version` | str / int | User-provided assertion version label. Land in `meta.raw`. |

### Raw uncertainty: `raw_kind` and `bound`

Raw uncertainty is the user-authored uncertainty contract. It describes how
a written assertion's value should be interpreted before any engine
projection.

```python
fg2 = FactGraph.create(schema_classes=[User])
ref = fg2.read.ref(User, user_id="u-9")

uncertain = fg2.write.set(
    User.name,
    ref,
    "Alice",
    meta={
        "source": "ocr",
        "trace_id": "ocr-2026-05",
        "raw_kind": "probabilistic",
        "bound": [0.2, 0.8],
    },
)

snap2 = fg2.read.get(User, user_id="u-9")
record = snap2.field("name").history.by_id(uncertain).one()

assert record.meta.raw["raw_kind"] == "probabilistic"
assert record.meta.raw["bound"] == [0.2, 0.8]
```

The two raw kinds are:

- **`"probabilistic"`** — values from probability, frequency, calibrated
  statistical estimates, or measured error models. The ProbLog adapter
  consumes this lane natively (point bounds project as `p::fact`; interval
  bounds require an explicit projection strategy).
- **`"possibilistic"`** — values from compatibility, physical allowance,
  expert uncertainty, or necessity/possibility bounds. The PyReason
  adapter consumes this lane natively as a truth/certainty-compatible
  bound.

The same numeric `bound` carries different meaning under each kind; the
write protocol preserves that boundary instead of flattening it.

For ProbLog, this raw carrier is paired with an explicit semantics projection.
`ProbLogSemantics()` defaults to rejecting both `probabilistic` and
`possibilistic` raw uncertainty until you choose a policy such as `lower`,
`midpoint`, `upper`, or `identity_probability`. The default reject behavior is
intentional: the SDK should not silently turn an interval into a point
probability.

### Canonical quantitative carrier

`raw_kind` + `bound` together form the **canonical quantitative carrier**
for any assertion that carries uncertainty. The contract is enforced on
three surfaces, with the same two fields:

1. **Write** (this page): writing `raw_kind` requires `bound`, and
   vice versa; independent `probability` and `bound_lower`/`bound_upper`
   keys are rejected before the assertion is appended.
2. **Evaluate** ([Configure inference semantics](semantics.md)):
   probabilistic and possibilistic adapters consume this lane natively;
   deterministic rows surface with `raw_kind=None, bound=None` (not
   `(1.0, 1.0)` and not an independent `probability=1.0`).
3. **Audit** ([Evidence: what-if and audit](evidence.md)): `EvaluateRow`
   and `Claim` carry the same `raw_kind` + `bound` fields; engine-specific
   projection outputs land on separate annotation lanes
   (`problog/semantic/probability`, `pyreason/semantic/bound_lower`,
   etc.), preserving the no-double-write rule below.

This is a **single-source contract**: the same two fields, never
duplicated, never normalized away to a single number, never split into
engine-specific shapes. The detailed write-side invariants follow.

The contract has four invariants:

1. **Paired.** `raw_kind` and `bound` must both appear or both be absent.
   Writing one without the other raises a write protocol error.
2. **Exact kind values.** `raw_kind` must be exactly `"probabilistic"` or
   `"possibilistic"`.
3. **Normalized bound.** `bound` must be a two-element JSON list of numeric
   values (booleans rejected), normalized to floats in `[0, 1]`, with
   `lower <= upper`.
4. **Annotation mirror.** When `raw_kind` and `bound` are present, the
   ledger also writes paired annotation rows on the
   `shared/semantic/raw_kind` and `shared/semantic/bound` lanes with
   `origin="observed"`. These lanes are the engine-neutral query
   interface for downstream consumers (adapters, audit) that need
   raw-uncertainty data without parsing `meta.raw`. The mirror is
   invariant: any update to the user-authored `raw_kind`/`bound` lands
   a new revision on both lanes; you do not write to these lanes
   directly, and they are kept in sync with `meta.raw` by the ledger.

`raw_kind` and `bound` are not first-class slots on `AssertionMeta`. They
land in `meta.raw["raw_kind"]` and `meta.raw["bound"]`, and you select them
through `.where(meta={...})` like any other raw key:

```python
uncertain_records = snap2.field("name").active.where(
    meta={"raw_kind": "probabilistic", "bound": [0.2, 0.8]}
)
assert uncertain_records.one().asrt_id == uncertain
```

### Reserved and rejected meta keys

System-managed keys cannot appear in user meta at write time. The ledger
fills them itself:

```text
ingested_at        -> filled by the ledger (nanosecond epoch)
ingest_key         -> filled by the ledger (idempotency key digest)
revoked_asrt_id    -> filled by retract(...) on the revocation record
```

Engine-specific uncertainty keys are rejected at write time. Use the raw
uncertainty contract above instead. **This enforces the no-double-write
rule**: every quantitative value lives in exactly one place — the canonical
carrier (`raw_kind` + `bound`) on user-authored assertions, or
engine-specific annotation lanes (`problog/semantic/probability`,
`pyreason/semantic/bound_lower`, etc.) on engine output. Allowing both
sides to carry the same value would create silent drift between the input
and output sides of the same uncertainty fact.

```text
probability        -> rejected; use raw_kind="probabilistic" + bound
bound_lower        -> rejected; use bound=[lower, upper]
bound_upper        -> rejected; use bound=[lower, upper]
```

Writing any of these raises a write protocol error before the assertion is
appended.

## Field assertion collections

Open the assertion view for one field with either:

```text
snap.field("name")         -> dynamic field name
snap.assertions.field("name")       -> field under the snapshot assertion manager
```

Both return the same `FieldAssertions` object. `snap.assertions.field(...)`
is the form that composes with snapshot-wide assertion manager methods.

```python
name_field = snap.field("name")
same_field = snap.assertions.field("name")

assert name_field.history.by_id(name_seed).one().value == "Alice"
assert same_field.history.by_id(name_hr).one().value == "Alice Liddell"
```

`FieldAssertions` exposes two base sets and two shortcuts:

| Surface | Returns | Use it for |
| --- | --- | --- |
| `.active` | `AssertionRecordSet` of non-revoked records | the current authoritative set |
| `.history` | `AssertionRecordSet` of every record, active and revoked | audit, replays, retract selection |
| `.all` | compatibility alias for `.history` | old code and tuple-like symmetry |
| `.at(t)` | shortcut for `.active.at(t)` | business-time slice of active records |
| `.version(v)` | shortcut for `.active.version(v)` | active records with `meta.raw["version"] == v` |

The shortcuts mean: most of the time you want active-only filters, and the
two common ones get a direct entry. Active-plus-revoked time or version
filters remain explicit:

```python
historical_v1 = snap.field("tags").history.version("tag-v1")
assert {r.value for r in historical_v1} == {"engineer"}
```

Legacy call forms such as `.active()` and `.all()` remain accepted. The returned
`AssertionRecordSet` is callable and returns itself, so old code does not need a
compatibility shim.

## AssertionRecordSet selection helpers

`AssertionRecordSet` is the tuple-compatible record collection returned by
`.active`, `.history`, `.all`, and graph-level readback. You do not import it; it is
the type you get back from those calls.

It behaves like a tuple:

```python
all_tags_history = snap.field("tags").history

assert len(all_tags_history) == 2

first = all_tags_history[0]
slice_two = all_tags_history[:2]
combined = slice_two + slice_two
```

Slicing, concatenation, and `*` preserve the helper methods, so you can keep
chaining selection calls.

Selection helpers cover the common assertion-selection questions:

| Helper | Filters on | Notes |
| --- | --- | --- |
| `.where(value=..., source=..., trace_id=..., version=..., meta={...})` | value and known meta slots | All criteria are keyword-only and AND together. `version=v` is short for `meta.raw["version"]==v`. Use `meta={...}` for arbitrary raw keys. |
| `.at(t)` | `meta.raw["valid_from"]` / `meta.raw["valid_to"]` | Business time. Records without `valid_from` are not matched. Half-open interval. |
| `.version(v)` | `meta.raw["version"] == v` | Same effect as `.where(version=v)`. |
| `.by_id(asrt_id)` | exact `asrt_id` | Returns a record set so you can still call `.one()`. |

Terminal helpers turn the set into a single record or a plain tuple:

| Helper | Returns | Use it for |
| --- | --- | --- |
| `.one()` | one `AssertionRecord` | exactly-one selection before destructive action |
| `.first()` | first record or `None` | preview, browse |
| `.all()` | plain `tuple[AssertionRecord, ...]` | when you need an unwrapped sequence |

`.one()` raises if the set is empty or has more than one record. That is the
point. Selection must be unique before the write side accepts a retraction.

```python
target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed", trace_id="import-001")
    .one()
)

assert target.asrt_id == name_seed
assert target.meta.source == "seed"
assert target.meta.raw["trace_id"] == "import-001"
```

Explicit `None` and omitted criteria are different:

```python
unfiltered = snap.field("tags").active.where()             # all active tags
no_source = snap.field("tags").active.where(source=None)    # source must be None

assert len(unfiltered) == 2
assert no_source.first() is None
```

`.where()` with no arguments does not filter. `.where(source=None)` requires
`source` to be `None` on the record.

## Business time vs ingestion time

`.at(t)` matches `meta.raw["valid_from"]` and `meta.raw["valid_to"]`, not the
ledger ingest timestamp:

```python
visible = snap.field("tags").history.at("2026-02-01T00:00:00Z")

assert {r.value for r in visible} == {"engineer"}
```

The engineer tag has `valid_from="2026-01-01T00:00:00Z"` and no `valid_to`,
so it matches any time at or after 2026-01-01. The reviewer tag has no
`valid_from`, so `.at(...)` does not match it.

The semantics are half-open:

```text
valid_from <= t and (valid_to is missing or valid_to > t)
```

If you want ingestion time instead, read `record.meta.ingested_at` directly.
That field is set by the ledger and is not affected by `valid_from` /
`valid_to`.

## Professional retract

`fg.write.retract(...)` takes one argument: an `asrt_id`. It does not take an
entity ref, a value, or an `AssertionRecord`. The "are you sure" check lives
on the read side.

The pattern is:

```text
read.get / find -> snap -> snap.field(name) -> where(...).one() -> retract
```

End to end:

```python
reviewer_target = (
    snap.field("tags")
    .active
    .where(value="reviewer", source="import", trace_id="import-002")
    .one()
)

revoker = fg.write.retract(
    reviewer_target.asrt_id,
    meta={"source": "manual-fix", "trace_id": "fix-001"},
)

assert isinstance(revoker, str)

after = fg.read.get(User, user_id="u-1")

assert set(after.tags) == {"engineer"}
assert reviewer_target.asrt_id in {r.asrt_id for r in after.field("tags").history}
assert reviewer_target.asrt_id not in {r.asrt_id for r in after.field("tags").active}
```

Two id values appear in any retract:

```text
target.asrt_id     -> the original assertion being revoked
revoker            -> the new revocation assertion id
```

If you already saved the original `asrt_id` at write time, you can retract
directly. No selection step is needed:

```python
fg.write.retract(name_seed, meta={"source": "manual-fix"})

later = fg.read.get(User, user_id="u-1")

assert name_seed not in {r.asrt_id for r in later.field("name").active}
assert name_seed in {r.asrt_id for r in later.field("name").history}
assert later.name == "Alice Liddell"
```

The original assertion is not deleted from the ledger. It moves out of
`.active` and stays in `.history` / `.all`.

## Frozen views: named assertion-id selections

`fg.views` stores named frozen sets of assertion ids.

```python
review = fg.views.create("name_review", asrt_ids=[name_seed, name_hr])

assert review.asrt_ids == frozenset({name_seed, name_hr})
assert "name_review" in fg.views.list()
```

You can also create a view from objects that carry an `.asrt_id`:

```python
seed_record = later.field("name").history.by_id(name_seed).one()
hr_record = later.field("name").history.by_id(name_hr).one()

obj_view = fg.views.create("name_review_objs", asrts=[seed_record, hr_record])

assert obj_view.asrt_ids == review.asrt_ids
```

`asrts=` is a convenience input. Anything with an `.asrt_id` attribute is
accepted, and only the id is stored. The object payload, value, and active
state are not part of the view.

`update(...)` replaces the membership entirely:

```python
fg.views.update("name_review", asrt_ids=[name_hr])

assert fg.views.get("name_review").asrt_ids == frozenset({name_hr})
```

There is no `patch(...)` or `diff(...)` in the current public surface.

A view does not require every id to exist in the ledger. Revoked assertions
stay valid members. Empty views are allowed.

`FrozenAssertionView` is the returned object type. It carries only `name`
and `asrt_ids` (a `frozenset[str]`). It is intentionally not in
`factgraph.sdk.__all__`; you reach it through `fg.views.get(...)` and
`fg.views.list()`. `fg.views` stores assertion-id sets, not read policies.

`fg.views` is intentionally outside workspace persistence. `fg.save(...)`
does not write view membership, and `FactGraph.load(...)` does not restore
it. Views are session-scoped name -> id-set bindings.

The design boundary: `fg.views` carries **no Database identity anchors**
(no `db_id`, no `base_tx_id`, no `schema_digest`) and no `view_digest`. It
is a working-tree bookmark, not an audit-chain anchor. Anything that needs
cross-session identity, evidence reproducibility, or participation in
`EvaluateResult.view_snapshot_digest` must use durable Database views — see
[Durable views are immutable](database.md#durable-views-are-immutable) for
the persistent-identity surface. The two are not interchangeable: session
views support full CRUD (`update(...)`, `delete(...)`) precisely because
nothing else references them; durable views are content-addressed
immutable for the opposite reason.

Database-owned durable view objects are a separate surface created with
`Database.create_view(...)`; they carry Database identity anchors and are
consumed through `FactGraph.attach(db, schema_classes=[...], view=view)`
for a read-only view-scoped runtime. See
[Database and durable views](database.md) for the full Database / durable
view tutorial.

For read-time assertion selection, use field-level `active`, `history`,
`.where(...)`, `.at(...)`, and `.version(...)`. Frozen views are id-set
containers.

## Graph-level readback: `fg.assertions`

`fg.assertions.by_id(...)` and `fg.assertions.by_ids(...)` are the
graph-level by-id readback for assertion records.

```python
seed_record = fg.assertions.by_id(name_seed)

assert seed_record is not None
assert seed_record.value == "Alice"
assert seed_record.meta.source == "seed"
```

`by_ids(...)` is the natural pair with frozen views:

```python
fg.views.update("name_review", asrt_ids=[name_seed, name_hr])
view = fg.views.get("name_review")

records = fg.assertions.by_ids(view.asrt_ids)

assert {r.value for r in records} == {"Alice", "Alice Liddell"}
```

`by_id(...)` returns `AssertionRecord | None` -- unknown ids resolve to
`None`. `by_ids(...)` returns an `AssertionRecordSet` -- unknown ids are
skipped silently, and there is no `strict=` flag in this slice.

From an `asrt_id`, the audit layer can supply higher-level explanation
through `fg.audit.explain_fact(...)` and `fg.audit.conflicts(...)`:

```python
explanation = fg.audit.explain_fact("user:name", alice)
conflicting = fg.audit.conflicts("user:name", alice)

assert explanation["pred_id"] == "user:name"
assert conflicting["pred_id"] == "user:name"
```

Those go beyond single-record lookup. This quickstart page stops at the
by-id boundary; cross-engine evidence graphs and round-event archives are
advanced audit surfaces.

## What is intentionally not supported

The current assertion surface is the smallest one that closes the
write -> snapshot -> select -> retract -> frozen-view -> readback loop. The
following are not in scope. The SDK either rejects them or simply does not
implement them:

- `fg.write.retract(entity_ref)` and `fg.write.retract(value=...)` -- selection
  must be on the read side, not in the retract call.
- `fg.write.retract(record)` with an `AssertionRecord` object -- pass the
  `record.asrt_id` field explicitly.
- `records[0].asrt_id` as a retract target -- ordering is not a confirmation
  mechanism. Use `.where(...).one()` for selection.
- `fg.assertions.where(...)`, `fg.assertions.at(...)`,
  `fg.assertions.version(...)`, and `fg.assertions.history(...)` -- start from
  `fg.assertions.active()` / `.all()` first, then chain record-set filters.
- `snap.assertions.where(...)` directly on the manager -- use
  `snap.assertions.active()` / `.all()` first, then call `.where(...)` on the
  returned `AssertionRecordSet`. Use `.field("where")` for a field literally
  named `where`.
- `fg.assertions.by_ids(..., strict=True)` -- unknown ids are skipped
  silently.
- `fg.views.patch(...)` and `fg.views.diff(...)` -- frozen view updates are
  full replacements.
- `fg.read.find(view=...)` and `fg.eval.evaluate(rule, view=...)` -- `view=` is
  not a parameter. Frozen views do not scope reads, rules, or inference
  evaluation; they are id-set containers only.
- `fg.eval.evaluate(inference, view=...)` -- inference evaluation always
  runs against active projection.
- Richer graph-level record context (`entity_type`, `pred_id`, field name)
  inside `by_ids(...)` results -- the record shape stays uniform.

Each item is a real boundary, not a missing feature. Crossing them changes
projection semantics, runtime fact universe, or write-side safety, and would
need a dedicated blueprint.

## Complete example

```python
from factgraph.sdk import Entity, FactGraph, Field, Identity


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])
alice = fg.read.ref(User, user_id="u-1")

name_seed = fg.write.set(
    User.name, alice, "Alice",
    meta={"source": "seed", "trace_id": "import-001"},
)
name_hr = fg.write.set(
    User.name, alice, "Alice Liddell",
    meta={"source": "hr", "trace_id": "hr-2026-05"},
)
engineer = fg.write.add(
    User.tags, alice, "engineer",
    meta={
        "source": "profile",
        "trace_id": "profile-001",
        "valid_from": "2026-01-01T00:00:00Z",
        "version": "tag-v1",
    },
)
reviewer = fg.write.add(
    User.tags, alice, "reviewer",
    meta={"source": "import", "trace_id": "import-002"},
)

snap = fg.read.get(User, user_id="u-1")

assert snap.name == "Alice Liddell"
assert set(snap.tags) == {"engineer", "reviewer"}

target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed", trace_id="import-001")
    .one()
)
assert target.asrt_id == name_seed
assert target.meta.raw["trace_id"] == "import-001"

visible_at = snap.field("tags").history.at("2026-02-01T00:00:00Z")
historical_v1 = snap.field("tags").history.version("tag-v1")

assert {r.value for r in visible_at} == {"engineer"}
assert {r.value for r in historical_v1} == {"engineer"}

reviewer_target = snap.field("tags").active.where(value="reviewer").one()
fg.write.retract(reviewer_target.asrt_id, meta={"source": "manual-fix"})

after = fg.read.get(User, user_id="u-1")

assert set(after.tags) == {"engineer"}
assert reviewer_target.asrt_id in {r.asrt_id for r in after.field("tags").history}

review = fg.views.create("name_review", asrt_ids=[name_seed, name_hr])
records = fg.assertions.by_ids(review.asrt_ids)

assert review.asrt_ids == frozenset({name_seed, name_hr})
assert {r.value for r in records} == {"Alice", "Alice Liddell"}

seed_record = fg.assertions.by_id(name_seed)

assert seed_record is not None
assert seed_record.meta.source == "seed"
```

## Syntax checklist

- `fg.write.set(...)` and `fg.write.add(...)` return `asrt_id` strings; keep
  them when you may need to retract or audit later.
- `AssertionRecord` exposes `asrt_id`, `value`, `is_active`, context fields
  (`entity_type`, `field_name`, `pred_id`, `e_ref`), and `meta`. Use
  `not record.is_active` for revoked/inactive records.
- `AssertionMeta` exposes `source`, `source_loc`, `trace_id`, `ingested_at`,
  `approved_by`, `note`, derived-rule fields, candidate fields, and `raw`.
- Business-time keys (`valid_from`, `valid_to`) and the `version` label live
  in `meta.raw`, not as first-class slots.
- Raw uncertainty is written as `meta={"raw_kind": ..., "bound": ...}` and
  also lives in `meta.raw`. `raw_kind` must be `"probabilistic"` or
  `"possibilistic"`; `bound` must be a two-element JSON list of floats in
  `[0, 1]` with `lower <= upper`; the two keys must be provided together.
- `raw_kind` and `bound` are also mirrored into shared annotation rows
  (`shared/semantic/raw_kind`, `shared/semantic/bound`) with
  `origin="observed"`.
- For uncertainty inputs, use `raw_kind` and `bound`.
- `probability`, `bound_lower`, and `bound_upper` are rejected as
  user-authored meta. They were per-engine projections and are not write
  inputs.
- `ingested_at`, `ingest_key`, and `revoked_asrt_id` are system-managed
  meta keys; user writes that include them are rejected.
- `snap.field("name")` and `snap.assertions.field("name")` both return
  `FieldAssertions`.
- `FieldAssertions.active` and `.history` return `AssertionRecordSet`;
  `.all` is a compatibility alias for `.history`, and legacy `.active()` /
  `.all()` call forms remain accepted.
- `FieldAssertions.at(t)` and `.version(v)` are shortcuts over the active
  set.
- `AssertionRecordSet` is tuple-compatible: indexing, slicing, concatenation,
  iteration, `len(...)`.
- `.where(value=..., source=..., trace_id=..., version=..., meta={...})` is
  keyword-only and AND-combined.
- `.at(t)` matches business time via `meta.raw["valid_from"]` and `valid_to`,
  not `ingested_at`.
- `.version(v)` matches `meta.raw["version"] == v`.
- `.by_id(asrt_id)` returns a record set so you can still call `.one()`.
- `.one()` requires exactly one record; `.first()` previews; `.all()` returns
  a tuple.
- `fg.write.retract(asrt_id)` revokes by id and returns the revoker's
  `asrt_id`.
- `fg.write.retract(...)` does not accept entity refs, values, or
  `AssertionRecord` objects.
- `fg.views.create/update(name, asrt_ids=[...])` stores a frozen id set;
  `asrts=` accepts objects with `.asrt_id`.
- `FrozenAssertionView.asrt_ids` is a `frozenset[str]`.
- `fg.views` is frozen-only: it stores `FrozenAssertionView` entries.
- `fg.assertions.by_id(asrt_id)` returns `AssertionRecord | None`;
  `fg.assertions.by_ids(asrt_ids)` returns `AssertionRecordSet` with unknown
  ids skipped silently.
- Graph-wide assertion queries, view-scoped reads, and `records[0]`-style
  retract are intentionally not supported.
