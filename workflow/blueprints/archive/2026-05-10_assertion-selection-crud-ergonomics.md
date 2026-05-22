# Task Blueprint: Assertion Selection And CRUD Ergonomics

- Status: implemented
- Created: 2026-05-10
- Last Updated: 2026-05-10
- Related Modules:
  - `src/kernel/sdk/facade.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/sdk/batch.py`
  - `src/kernel/application/entity_view.py`
  - `src/kernel/application/protocol/entity_read.py`
  - `src/kernel/application/entity_write.py`
  - `src/kernel/core/store/ledger.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md](../../references/working/design-points/identity-primary-key-coordinate-semantics.zh.md)
  - [docs/blueprints/archive/2026-05-10_primary-identity-domain-semantics.md](./2026-05-10_primary-identity-domain-semantics.md)
  - [docs/blueprints/archive/2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md)
- Audit Log:
  - [2026-05-10_assertion-selection-crud-ergonomics.audit.md](./2026-05-10_assertion-selection-crud-ergonomics.audit.md)

## 1. Problem

FactPy's write-side `retract(asrt_id)` is intentionally precise: it
retracts one persisted assertion by assertion id, not every fact matching a
field/value predicate. This is correct for an append-only, auditable ledger:
users should identify the exact assertion before deleting/revoking it.

The current user-facing ergonomics around finding that assertion id are less
clear. `set(...)` / `add(...)` already return assertion ids, and read-side
`EntitySnapshot.assertions.<field>.active/history` exposes
`AssertionRecord.asrt_id`, but the practical path for "select exactly the
assertion I intend to retract" is still too manual:

```python
matches = [
    record
    for record in snap.assertions.name.history
    if record.value == "Alice" and record.meta.source == "seed"
]
if len(matches) != 1:
    raise ValueError(...)
fg.write.retract(matches[0].asrt_id)
```

That pattern is semantically sound, but it makes normal CRUD feel like users
must manually traverse audit structures. The design question is whether the
SDK should add a narrow read-side assertion selection helper that preserves
precise `asrt_id`-based write semantics while giving users a safer and more
ergonomic "are you sure" selection path.

This blueprint also evaluates whether adjacent CRUD operations (`set`, `add`,
`edit`, `ingest`, batch field handles, and what-if overlays that consume
`asrt_id`) need related ergonomic improvements or only documentation fixes.

## 2. Goals

- Preserve `retract(asrt_id)` as the precise write-side primitive.
- Make the source of `asrt_id` obvious in SDK docs:
  - immediate writes return assertion ids;
  - later reads expose assertion ids through assertion records.
- Evaluate a read-side assertion selection API for exactly-one selection.
- Avoid accidental multi-retract / fuzzy-delete semantics.
- Keep the read/write namespace split clear:
  - read side selects assertions;
  - write side mutates by explicit assertion id or assertion record only if scoped.
- Evaluate whether other CRUD operations need matching improvements.
- Keep any implementation additive and compatible with existing
  `EntitySnapshot.assertions` / `FieldAssertions.active/history` behavior.

## 3. Non-goals

- No direct fuzzy retract API such as `retract(User.name, value="Alice")`
  unless it first proves an exactly-one guard that cannot silently revoke
  multiple assertions.
- No physical delete; ledger remains append-only with revocation assertions.
- No change to `asrt_id` generation or ledger row schema.
- No change to `idref_v1`, identity coordinate semantics, primary-first batch
  semantics, or partial-identity `find(...)` semantics.
- No package rename or release artifact rewrite.
- No broad CRUD redesign unless the §5 falsifier pass explicitly scopes it.

## 4. Current Context

Current source anchors:

- `SDKStore.set(...)` / `SDKStore.add(...)` return assertion ids for newly
  persisted field assertions.
- `SDKStore.retract(asrt_id, *, meta=None)` returns the revoker assertion id
  and remaps invalid / unknown core write errors into SDK errors.
- `EntitySnapshot.field("name").active/history` and
  `EntitySnapshot.assertions.name.active/history` expose
  `tuple[AssertionRecord, ...]`.
- `AssertionRecord` exposes `asrt_id`, `value`, `is_active`, `is_revoked`,
  and `meta`.
- `AssertionMeta` exposes common fields such as `source`, `trace_id`,
  `confidence`, `version` via `raw`, and related provenance metadata.
- Batch managed field retract is already assertion-id based:
  `.retract(assertion_id=...)`.

Current design constraints:

- `EntitySnapshot` is not one assertion; it may contain many fields and many
  assertions per field.
- `asrt_id` belongs to one persisted assertion, not to an entity snapshot.
- Read-side assertion history is audit-adjacent but already exposed through
  SDK `EntitySnapshot`.
- Post-L taxonomy keeps `read` and `write` namespaces distinct. New CRUD
  ergonomics must not blur "selection" and "mutation" into one unsafe command.

Related historical / recent blueprints:

- Primary identity/domain semantics locked the full-coordinate entity model
  and primary-first write handles.
- Primary-anchor domain read locked read-side partial identity enumeration via
  `find(...)` without write-side fan-out.

## 5. Design Questions / Falsifier Pass

### 5.1 Documentation-only baseline

Question: Is this problem solved by documentation alone?

Falsifiers:

- If docs can show a professional exactly-one pattern using existing
  `AssertionRecord` without making CRUD feel audit-internal, do not add API.
- If users still need verbose manual list comprehensions for normal
  retract/edit/overlay workflows, docs-only is insufficient.
- If existing examples imply magic assertion ids or positional `records[0]`
  selection, docs must be fixed regardless of API changes.

**Decision (LOCKED 2026-05-10; partially SUPERSEDED 2026-05-10):**

> The "no new assertion selector API" portion of this decision was
> superseded later the same day by §5.2-§5.7. The immediate docs hotfix and
> the required documentation fixes in this block remain authoritative; the
> "no selector API" conclusion does not.

The current `AssertionRecord` + `AssertionMeta` API surface is sufficient
to express professional exactly-one assertion selection patterns. The
ergonomic gap identified in this pass is documentation teaching, not API
capability. The required first slice is a docs-only fix; no new assertion
selector API is scoped under this blueprint.

Required docs fixes:

1. Fix `fg.write.retract` signature in `00_user_guide.en.md`: `retract`
   takes `asrt_id`, not `e_ref`. This blocker was split out as immediate
   hotfix `1523e41` before §5.1 was locked.
2. Document that `set(...)` and `add(...)` return `asrt_id`; remove magic
   `asrt_id="asrt-abc-123"` examples as the primary teaching path.
3. Add snapshot structure walk-through:
   `EntitySnapshot -> FieldAssertions -> AssertionRecord -> asrt_id`.
4. Document `AssertionRecord.asrt_id` and `AssertionMeta` as the read-side
   selection path for later retract targets.
5. Replace the positional `active_claims[0]["asrt_id"]` pattern in
   `06_what_if_and_proof.en.md` with explicit value/meta/source-based
   exactly-one selection.
6. Show an exactly-one guard pattern explicitly; do not teach `records[0]`
   unless the example has already constructed a single unambiguous record.

Conditional deferral of §5.2-§5.7:

- §5.2-§5.7 (selector helper, `.one()` semantics, write-side overload,
  filter dimensions, CRUD adjacency API changes, and namespace budget) are
  deferred pending the outcome of the docs-only fix above. Each remains a
  valid future ergonomic enhancement; none is permanently rejected.
- Re-open §5.2 and downstream if user feedback after docs ship still shows
  assertion-selection friction, or if later source-grounding finds CRUD
  workflows that cannot be expressed cleanly through existing
  `AssertionRecord` patterns plus docs.

**Supersession (REOPENED 2026-05-10):**

The docs-only conclusion remains valid for the immediate retract-signature
hotfix and documentation baseline, but the "no selector API" conclusion is
superseded by §5.2-§5.7 after user review of the desired CRUD ergonomics.
The updated direction is to keep precise `retract(asrt_id)` semantics while
adding a tuple-compatible assertion record collection with fluent read-side
selection helpers.

### 5.2 Read-side selector shape

Question: If API is needed, where should assertion selection live?

Candidates:

- Add fluent helpers on `FieldAssertions` / `tuple[AssertionRecord, ...]`
  surface, e.g. `snap.field("name").history.where(...).one()`.
- Add a read namespace helper, e.g.
  `fg.read.assertions(User.name, user_id="u-1").history().where(...).one()`.
- Add both only if one is clearly a thin convenience over the other.

Falsifiers:

- Reject any shape that hides field/entity identity enough to make selection
  ambiguous.
- Reject any shape that requires a new application protocol capability before
  proving the SDK facade cannot already select from exposed assertion records.
- Reject any shape that changes existing `.active` / `.history` tuple return
  behavior.

**Decision (REOPENED AND LOCKED 2026-05-10):**

Ship assertion selection as a tuple-compatible read-side collection returned
from the existing `EntitySnapshot` assertion access paths. The intended
runtime type is a tuple subclass, tentatively named `AssertionRecordSet`,
that behaves like `tuple[AssertionRecord, ...]` for existing callers while
adding fluent selection helpers.

Behavioral contract:

- `EntitySnapshot.field(...).active` / `.history` and
  `EntitySnapshot.assertions.<field>.active` / `.history` continue to be
  iterable, indexable, length-checkable, and tuple-compatible.
- `FieldAssertions.at(...)` and `FieldAssertions.version(...)` return the
  same assertion collection type as `.active` and `.history`.
- The collection supports read-only selection helpers such as `.where(...)`,
  `.one()`, `.all()`, and `.first()`; these helpers never mutate ledger
  state.
- No new namespace method such as `fg.read.assertions(...)` is introduced.
- No application protocol change is introduced for assertion selection.

Compatibility contract:

- Existing tuple-style usage remains valid:
  iteration, indexing (`records[0]`), `len(records)`, equality against
  tuples such as `records == ()`, and `isinstance(records, tuple)` continue
  to work.
- Slicing, concatenation, and multiplication return the same assertion
  collection type rather than a plain tuple, so chained `.where(...)`
  remains available on subsets and combined collections.
- The helper collection is documented as a returned object, not a new
  top-level SDK constructor.

Rationale:

The user-facing CRUD path needs a professional "select exactly one
assertion before retract" idiom without moving selection into the write
namespace. A tuple subclass preserves the existing sequence contract while
making the safe path concise:

```python
target = (
    snap.field("name")
    .history
    .where(value="Alice", source="seed")
    .one()
)
fg.write.retract(target.asrt_id)
```

This keeps `write.retract(...)` precise and id-based while making the read
side responsible for assertion selection.

Explicitly NOT decided in §5.2 (delegated):

- Exact `.one()` / `.all()` / `.first()` behavior → §5.3.
- Exact filter dimensions accepted by `.where(...)` → §5.5.
- Whether `write.retract(...)` accepts an `AssertionRecord` directly → §5.4.

### 5.3 Exactly-one semantics

Question: Should the helper include `.one()` / `.all()` / `.first()` semantics?

Default hypothesis:

- `.one()` is the important safety primitive: zero matches and multiple
  matches are both errors.
- `.all()` may be useful for inspection but should not imply mutation.
- `.first()` is dangerous unless explicitly documented as view-order
  dependent and not recommended for retract.

Falsifiers:

- If `.one()` cannot report enough context to let users resolve ambiguity, the
  helper is not ready.
- If `.first()` encourages accidental revocation, omit it.

**Decision (LOCKED 2026-05-10):**

The assertion collection ships with `.where(...)`, `.one()`, `.all()`, and
`.first()` as read-side helpers.

Behavioral contract:

- `.where(...)` returns another assertion collection of the same type.
- `.one()` returns a single `AssertionRecord` only when the collection has
  exactly one record; zero matches and multiple matches raise an SDK error.
- `.all()` returns a plain `tuple[AssertionRecord, ...]` for callers that
  want to leave the helper surface.
- `.first()` returns the first `AssertionRecord` or `None` for empty
  collections. It is an inspection convenience, not the recommended retract
  pattern.

Documentation contract:

- Retract examples use `.one()` before `fg.write.retract(target.asrt_id)`.
- `.first()` must be documented as order-dependent and unsuitable for
  destructive workflows unless the caller has already established
  unambiguous ordering and intent.

### 5.4 Write-side acceptance

Question: Should `write.retract(...)` accept `AssertionRecord` in addition to
`asrt_id: str`?

Candidates:

- Keep `write.retract(asrt_id: str)` only.
- Add `write.retract(record: AssertionRecord)` as a convenience that extracts
  `record.asrt_id`.
- Add a separate helper name only if overloading creates ambiguity.

Falsifiers:

- Reject any write API that accepts a selector / predicate and performs
  selection internally.
- Reject any overload that makes docs unclear about whether mutation is by id
  or by fuzzy match.

**Decision (LOCKED 2026-05-10):**

Keep `write.retract(asrt_id: str)` as the primary and documented write-side
primitive. Do not add selector or predicate acceptance to `write.retract(...)`.

Behavioral contract:

- `fg.write.retract(target.asrt_id)` remains the canonical pattern.
- `write.retract(...)` does not accept `.where(...)` selectors, filter
  kwargs, or field/value predicates.
- A future overload accepting `AssertionRecord` directly is not shipped in
  this slice. Re-open §5.4 to consider this overload only if user feedback
  shows the explicit `target.asrt_id` form causes confusion or if examples
  become unreadable without it.

Rationale:

The read side may help users find the exact assertion; the write side should
still receive one explicit assertion id. This preserves the "are you sure"
boundary and avoids any accidental multi-retract semantics.

### 5.5 Metadata and value filters

Question: What filters should assertion selection support?

Candidate filter dimensions:

- `value`
- `source`
- `trace_id`
- `confidence`
- `version`
- `ingest_key`
- `active` / `history` scope
- raw meta key predicates

Falsifiers:

- Reject filter names that are not backed by stable `AssertionMeta` or
  documented `meta.raw` behavior.
- Reject overly clever predicate DSLs unless simple equality is insufficient.

**Decision (LOCKED 2026-05-10):**

`.where(...)` supports simple equality filters over stable assertion record
fields and documented metadata fields. Predicate DSLs and arbitrary callables
are out of scope for this slice.

Scoped filters:

- `value=...` matches `AssertionRecord.value`.
- `source=...`, `trace_id=...`, and `confidence=...` match the corresponding
  `AssertionMeta` attributes.
- `version=...` is a convenience alias for the documented
  `AssertionMeta.raw["version"]` value when present.
- `meta={...}` matches key/value pairs in `AssertionMeta.raw`.

Semantics:

- Multiple filters are combined with AND semantics.
- Omitted filters do not participate in matching.
- Filtering for an explicit `None` value must be distinguishable from an
  omitted filter in implementation.

Explicitly NOT scoped:

- Predicate callables.
- Fuzzy matching or ordering expressions.
- Nested raw-meta query languages.

### 5.6 CRUD adjacency

Question: Do `set`, `add`, `edit`, `ingest`, batch field handles, or what-if
overlays need related changes?

Prompts:

- Should docs for `set` / `add` explicitly name their returned assertion id?
- Should batch commit results be documented as a source of assertion ids?
- Should `edit` expose selected assertion ids more clearly?
- Do what-if overlay examples that need `asrt_id` benefit from the same
  selector helper?
- Does `single` field semantics need clearer "read-side chosen value vs
  multiple assertions" documentation?

Falsifiers:

- If a CRUD operation already has a safe source of assertion ids, prefer docs
  over API.
- If a workflow requires locating exactly one assertion after the fact, it
  belongs in the assertion selection story.

**Decision (LOCKED 2026-05-10):**

The new helper surface is read-side assertion selection only. Adjacent CRUD
operations receive documentation updates, not new write-side selectors.

Required docs sync:

- `set(...)` and `add(...)` examples explicitly show that writes return
  `asrt_id`.
- Snapshot documentation explains the hierarchy:
  `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord`.
- Retract examples select exactly one record via `.where(...).one()` and then
  pass `target.asrt_id` to `write.retract(...)`.
- What-if / overlay examples that need an assertion id use the same
  selection idiom rather than positional `records[0]`.

No changes are scoped for `ingest`, batch commit results, or overlay write
semantics in this slice.

### 5.7 Namespace and public surface budget

Question: Does any new helper justify expanding `kernel.sdk.__all__` or the
post-L taxonomy?

Default hypothesis:

- Do not add new top-level exports.
- Prefer private helper classes returned from existing objects, if needed.
- Keep `read` for selection and `write` for mutation.

Falsifiers:

- If a helper type must be part of a stable public type contract, decide
  whether it belongs in `__all__` or remains documented as a returned object
  only.

**Decision (LOCKED 2026-05-10):**

No new top-level SDK export ships for assertion selection. The helper type is
part of the returned-object surface of `EntitySnapshot`, not a constructor or
namespace entry.

Surface contract:

- `kernel.sdk.__all__` remains unchanged.
- No new `fg.read.*` namespace method is added.
- The helper type may be documented by name as the return type of
  `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`, but
  it is not exported as a public constructor.
- The post-L taxonomy remains unchanged: `read` selects, `write` mutates by
  explicit assertion id.

### 5.8 Tests and compatibility

Question: What tests prove this is safe?

Expected future tests if scoped:

- Existing `EntitySnapshot.field(...).active/history` tuple behavior remains
  unchanged.
- Assertion selector `.one()` returns exactly one matching `AssertionRecord`.
- `.one()` zero / multiple match failures are explicit SDK errors.
- `write.retract(asrt_id)` remains unchanged.
- If `write.retract(AssertionRecord)` ships, it delegates to `asrt_id` and
  does not accept selectors.
- Docs examples avoid positional `records[0]` unless the example has already
  proven exactly-one state.

**Decision (LOCKED 2026-05-10):**

Compatibility is proven through focused SDK tests plus docs-lint style
checks. The implementation may ship only if existing tuple-like assertion
record usage remains compatible while the new helper semantics are covered.

Required test coverage:

- `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`
  return a tuple-compatible assertion collection with `.where(...)`,
  `.one()`, `.all()`, and `.first()`.
- Existing tuple behavior remains true: iteration, indexing, `len(...)`,
  equality to plain tuples such as `()`, and `isinstance(records, tuple)`.
- Slicing, concatenation, and multiplication preserve the assertion
  collection type and keep `.where(...)` available.
- `.where(...)` supports the §5.5 scoped filters and combines multiple
  filters with AND semantics.
- Chained `.where(...).where(...)` calls remain available and preserve the
  assertion collection type.
- `.where(...)` can distinguish an omitted filter from an explicit
  `None` filter.
- `.one()` returns exactly one `AssertionRecord`; zero and multiple matches
  raise an SDK error.
- `.all()` returns a plain `tuple[AssertionRecord, ...]`.
- `.first()` returns the first `AssertionRecord` or `None` for an empty
  collection.
- `write.retract(asrt_id)` behavior remains unchanged; no selector,
  predicate, or `AssertionRecord` overload ships in this slice.
- `kernel.sdk.__all__` remains unchanged.

Required docs / lint coverage:

- SDK docs show `set(...)` / `add(...)` returning `asrt_id`.
- SDK docs show snapshot structure as
  `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord`.
- Retract examples use `.where(...).one()` followed by
  `fg.write.retract(target.asrt_id)`.
- Docs do not teach magic assertion ids or positional `records[0]` as the
  primary retract selection pattern.

## 6. Boundaries And Invariants

Following the §5.1-§5.8 LOCKED decisions, the following invariants govern
any scoped implementation of this blueprint.

**Ledger and identity invariants:**

- Ledger remains append-only; retract appends a revocation assertion.
- `asrt_id` remains the unit of precise assertion retraction.
- `EntitySnapshot.ref` remains entity-coordinate identity; it is not an
  assertion id.
- `AssertionRecord.asrt_id` remains assertion identity.
- No change to `idref_v1`, identity coordinate semantics, primary-first
  batch semantics, or partial-identity `find(...)` semantics.

**SDK read-side assertion-selection invariants:**

- Assertion selection lives on existing `EntitySnapshot` assertion access
  paths; no new `fg.read.*` namespace method is introduced.
- `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`
  return a tuple-compatible assertion collection, tentatively named
  `AssertionRecordSet`.
- Existing tuple-style use remains compatible: iteration, indexing,
  `len(...)`, equality to plain tuples, and `isinstance(records, tuple)`.
- Slicing, concatenation, multiplication, and chained `.where(...)` calls
  preserve the helper collection type.
- The helper collection is read-only and never mutates ledger state.

**Selector semantics invariants:**

- `.where(...)` supports only the §5.5 scoped equality filters:
  `value`, `source`, `trace_id`, `confidence`, `version`, and `meta={...}`.
- Multiple `.where(...)` filters use AND semantics.
- Explicit `None` filters must be distinguishable from omitted filters.
- Predicate callables, fuzzy matching, ordering expressions, and nested raw
  metadata query languages are out of scope.
- `.one()` is the exact-selection safety primitive: zero and multiple matches
  raise SDK errors.
- `.all()` returns a plain tuple; `.first()` is inspection-only and not the
  documented retract pattern.

**SDK write-side invariants:**

- `write.retract(asrt_id: str)` remains the canonical and documented
  write-side primitive.
- `write.retract(...)` does not accept selectors, predicates, filter kwargs,
  or `AssertionRecord` objects in this slice.
- The canonical retract pattern is:
  read-side `.where(...).one()` -> `target.asrt_id` ->
  `write.retract(target.asrt_id)`.
- No fuzzy retract API such as `retract(User.name, value="Alice")` is
  introduced.

**Public surface invariants:**

- `kernel.sdk.__all__` remains unchanged.
- `AssertionRecordSet` may be documented as a returned object but is not a
  top-level exported constructor.
- No application protocol change is introduced for assertion selection.
- The post-L taxonomy remains unchanged: `read` selects, `write` mutates by
  explicit assertion id.

**Documentation invariants:**

- SDK docs explain where assertion ids come from: `set(...)` / `add(...)`
  return them immediately, and later reads expose them through
  `AssertionRecord.asrt_id`.
- SDK docs explain snapshot structure:
  `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord`.
- SDK docs avoid magic assertion ids and positional `records[0]` as the
  primary retract selection pattern.

**Repository safety invariants:**

- Working notes under `docs/references/working/` remain rationale inputs,
  not implementation truth.
- No release refs, historical snapshots, release branch artifacts, or
  `v0.1.0-rc.1` tag/release artifacts are modified by this blueprint.

## 7. Acceptance

Acceptance is split into three groups: closed gates from §5/§6 design
locking, scope-freeze gates that must pass before `draft -> scoped`, and
implementation gates that must pass before the behavior ships.

**Closed (§5 / §6 design pass, 2026-05-10):**

- [x] §5.1 has a LOCKED docs baseline with the no-selector conclusion
      explicitly marked as partially superseded.
- [x] §5.2 has a REOPENED AND LOCKED returned-object helper decision.
- [x] §5.3-§5.8 have explicit LOCKED decisions recorded in the audit log.
- [x] §6 invariants reflect §5.1-§5.8 without adding new behavior.

**Scope-freeze gates (passed before `draft -> scoped`, 2026-05-10):**

- [x] §7 acceptance reviewed and locked.
- [x] §8 implementation plan reviewed and locked.
- [x] Pre-scope-freeze docs/examples scan completed: grep SDK docs and
      examples for magic assertion ids, positional `records[0]` retract
      teaching, and stale `tuple[AssertionRecord, ...]` wording that would
      hide the new helper surface.
- [x] Any stale docs/examples found in the scan above are either updated in
      the Phase 3 docs plan or the relevant §5 decision is explicitly
      re-opened.
- [x] Blueprint body and audit log make the §5.1 supersession clear without
      requiring readers to infer it from commit history.

**Implementation gates (passed, 2026-05-10):**

- [x] `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`
      return a tuple-compatible assertion collection with `.where(...)`,
      `.one()`, `.all()`, and `.first()`.
- [x] Existing tuple behavior remains compatible: iteration, indexing,
      `len(...)`, equality to plain tuples such as `()`, and
      `isinstance(records, tuple)`.
- [x] Slicing, concatenation, multiplication, and chained
      `.where(...).where(...)` preserve the assertion collection type.
- [x] `.where(...)` supports `value`, `source`, `trace_id`, `confidence`,
      `version`, and `meta={...}` filters.
- [x] Multiple `.where(...)` filters use AND semantics.
- [x] Explicit `None` filters are distinguishable from omitted filters.
- [x] `.one()` returns exactly one `AssertionRecord`; zero and multiple
      matches raise SDK errors.
- [x] `.all()` returns a plain `tuple[AssertionRecord, ...]`.
- [x] `.first()` returns the first `AssertionRecord` or `None` for an empty
      collection.
- [x] `write.retract(asrt_id)` behavior remains unchanged; no selector,
      predicate, filter-kwargs, or `AssertionRecord` overload ships.
- [x] `kernel.sdk.__all__` remains unchanged.
- [x] No new `fg.read.*` namespace method is introduced.
- [x] No application protocol change is introduced for assertion selection.
- [x] Affected SDK docs are updated in the same implementation cycle as the
      behavior change.
- [x] SDK docs show `set(...)` / `add(...)` returning `asrt_id`.
- [x] SDK docs show snapshot structure as
      `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord`.
- [x] Retract examples use `.where(...).one()` followed by
      `fg.write.retract(target.asrt_id)`.
- [x] Docs avoid magic assertion ids and positional `records[0]` as the
      primary retract selection pattern.
- [x] No release refs, historical snapshots, release branch artifacts, or
      `v0.1.0-rc.1` tag/release artifacts are modified.

## 8. Implementation Plan

The §5 design pass is closed (2026-05-10). The remaining work follows the
five phases below, gated by §7 scope-freeze gates and §7 implementation
gates.

### Phase 0: Pre-scope-freeze

Complete all §7 scope-freeze gates before flipping blueprint status from
`draft` to `scoped`.

Non-trivial actions:

1. Pre-scope-freeze docs/examples scan:
   - grep SDK docs and examples for magic assertion ids;
   - grep positional `records[0]` retract teaching;
   - grep stale `tuple[AssertionRecord, ...]` wording that would hide the
     new returned-object helper surface.
2. Record findings in the audit log and either defer the fixes to Phase 3
   docs sync or re-open the relevant §5 decision.
3. Confirm the blueprint body and audit log make the §5.1 supersession clear
   without relying on commit history.

After all §7 scope-freeze gates pass: flip blueprint status to `scoped` and
record the event in the audit log.

### Phase 1: Test scaffolding

Add focused tests for the §7 implementation gates before the implementation
lands. Tests for the new helper behavior should fail on current code and
pass after Phase 2.

Coverage:

- `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`
  return the helper collection.
- Tuple compatibility: iteration, indexing, `len(...)`, equality to `()`,
  and `isinstance(records, tuple)`.
- Slicing, concatenation, multiplication, and chained
  `.where(...).where(...)` preserve helper type.
- `.where(...)` supports `value`, `source`, `trace_id`, `confidence`,
  `version`, and `meta={...}` filters.
- Multiple filters use AND semantics.
- Explicit `None` filters differ from omitted filters.
- `.one()` returns one record or raises SDK errors on zero/multiple matches.
- `.all()` returns a plain tuple.
- `.first()` returns first record or `None`.
- `write.retract(asrt_id)` remains unchanged.
- `kernel.sdk.__all__` remains unchanged.
- No new `fg.read.*` namespace method exists.

### Phase 2: Implementation

Scope: implement the returned-object helper surface in the SDK facade layer.
No application protocol, ledger, storage, authoring, or public export changes
are scoped.

Critical file:

- `src/kernel/sdk/facade.py`: add the tuple-compatible assertion collection
  type, route `FieldAssertions.active`, `.history`, `.at(...)`, and
  `.version(...)` through it, and implement `.where(...)`, `.one()`,
  `.all()`, and `.first()`.

Implementation constraints:

- Preserve `AssertionRecord` and `AssertionMeta` field semantics.
- Preserve existing `FieldAssertions` access paths.
- Preserve `write.retract(asrt_id)` behavior and signature.
- Do not modify `src/kernel/application/`, `src/kernel/authoring/`,
  `src/kernel/core/`, or `src/kernel/sdk/__init__.py`.
- Do not change `kernel.sdk.__all__`.
- Do not introduce a new `fg.read.*` namespace method.
- Do not add predicate DSLs or fuzzy retract semantics.

### Phase 3: Documentation sync

Update affected SDK docs in the same implementation cycle as Phase 2.

Target docs:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/sdk/docs/06_what_if_and_proof.en.md`
- `src/kernel/sdk/docs/07_walker_and_advanced.en.md`

Required docs content:

- Writes return assertion ids (`set(...)` / `add(...)`).
- Snapshot structure:
  `EntitySnapshot -> FieldAssertions -> AssertionRecordSet -> AssertionRecord`.
- Retract examples use `.where(...).one()` then
  `fg.write.retract(target.asrt_id)`.
- What-if / overlay examples use explicit selection instead of positional
  `active_claims[0]`.
- Docs do not present magic assertion ids as the main teaching path.

### Phase 4: Verification and close

1. Run focused assertion-selection tests.
2. Run the full kernel test suite; require green or record any pre-existing
   environment-only failure separately.
3. Verify every §7 implementation gate passes.
4. Confirm forbidden paths have no diff:
   `src/kernel/application/`, `src/kernel/authoring/`, `src/kernel/core/`,
   and `src/kernel/sdk/__init__.py`.
5. Confirm `kernel.sdk.__all__` is unchanged.
6. Confirm release refs, historical snapshots, `release/0.1.x`, and
   `v0.1.0-rc.1` artifacts are untouched.
7. Fill §10 Outcome / Deviations.
8. Add audit log entries for Phase 1 / Phase 2 / Phase 3 / Phase 4.
9. Flip blueprint status `scoped -> implemented`.

## 9. Docs To Update

Likely docs if scoped:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/sdk/docs/06_what_if_and_proof.en.md` if overlay examples need
  assertion selection.
- `src/kernel/sdk/docs/07_walker_and_advanced.en.md` if walker examples use
  magic assertion ids.
- `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`
  if the read/write assertion-id model is folded into the design-point note.

## 10. Outcome / Deviations

Task completion section to fill after implementation or explicit research
closure:

- Final landed decision: ship `AssertionRecordSet`, a tuple-compatible
  returned-object helper for read-side assertion selection on existing
  `FieldAssertions` access paths.
- Final landed behavior:
  - `FieldAssertions.active`, `.history`, `.at(...)`, and `.version(...)`
    return `AssertionRecordSet`.
  - `AssertionRecordSet` is a `tuple` subclass preserving iteration,
    indexing, `len(...)`, equality to plain tuples, slicing, concatenation,
    and multiplication while adding `.where(...)`, `.one()`, `.all()`, and
    `.first()`.
  - `.where(...)` supports `value`, `source`, `trace_id`, `confidence`,
    `version`, and `meta={...}` equality filters with AND semantics and
    explicit-`None` support.
  - `write.retract(asrt_id)` remains unchanged; no selector, predicate,
    filter-kwargs, or `AssertionRecord` overload ships.
  - `kernel.sdk.__all__` remains unchanged; no new `fg.read.*` namespace
    method or application protocol change ships.
  - SDK docs now teach `set/add` returning `asrt_id`, the snapshot assertion
    hierarchy, and `.where(...).one()` before `write.retract(target.asrt_id)`.
- Deviations from draft:
  - §5.1 initially locked a docs-only first slice. User review re-opened
    §5.2 and superseded only the "no selector API" conclusion; the docs
    hotfix baseline remained authoritative.
  - `07_walker_and_advanced.en.md` was added to the docs-sync target list
    after Phase 0 scan found a magic assertion id example.
  - Full kernel discovery still reports the pre-existing Problog cold-import
    circularity; focused and related SDK suites pass.
- Deferred design questions:
  - A possible future `write.retract(AssertionRecord)` overload remains
    deferred until user feedback shows `target.asrt_id` is confusing.
  - Predicate DSLs, fuzzy matching, nested metadata query languages, and
    fuzzy retract APIs remain out of scope.
- Archive notes: implemented locally on `master`; archive after final review
  and commit.
