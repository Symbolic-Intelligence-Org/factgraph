# Task Blueprint: Frozen Assertion View Model

- Status: implemented
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/sdk/store.py`
  - `src/kernel/sdk/facade.py`
  - `src/kernel/core/view/projector.py`
  - `src/kernel/core/store/types.py`
  - `src/kernel/application/entity_view.py`
  - `src/kernel/application/query_runtime.py`
  - `src/kernel/core/store/_evaluate.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md](../../references/working/design-points/read-write-snapshot-assertion-selection.zh.md)
  - [docs/blueprints/archive/2026-05-10_assertion-selection-crud-ergonomics.md](./2026-05-10_assertion-selection-crud-ergonomics.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md](./2026-03-18_scenario-a-temporal-semantics.md)
- Audit Log:
  - [2026-05-11_frozen-assertion-view-model.audit.md](./2026-05-11_frozen-assertion-view-model.audit.md)

## 1. Problem

FactPy currently has several adjacent but not fully aligned concepts named
or shaped like "views":

- `ViewSpec(active, confidence_strategy, prefer_source)` lives in the SDK
  `fg.views` registry and is documented as a view, but current behavior is
  closer to display/projection metadata policy than assertion-universe
  selection.
- `project_view_facts(...)` is the runtime/core active-chosen projection
  used by query/rule/application paths, but it does not consume user
  `ViewSpec` registry entries.
- `EntitySnapshot.field(...).active/history/at/version` exposes field-level
  assertion collections, but those operations are not available at graph or
  entity scope.
- `write.retract(asrt_id)` already operates at assertion identity level,
  while most `read` / `write` namespace documentation is entity-oriented.

This creates a conceptual gap: the system can naturally be viewed both as an
entity collection and as an assertion collection, but the API only recently
made field-level assertion collection ergonomics explicit through
`AssertionRecordSet`.

The design question is whether the next view model should define:

```text
View = named frozen set of assertion ids
```

and separate that assertion-universe selection from projection/conflict
policy such as `confidence_strategy` and `prefer_source`.

This blueprint is therefore not proposing a parallel view mechanism. It is
a design pass toward redefining the long-term meaning of the existing
`fg.views` registry: a FactGraph view should name an assertion universe,
not merely a projection/confidence policy. Current code already has a
split between the SDK `fg.views` registry and core `project_view_facts(...)`;
this blueprint treats that split as existing design debt, not as a reason
to introduce another independent view system.

## 2. Goals

- Define a clear conceptual model for graph-level assertion collections,
  entity-level assertion collections, and field-level assertion collections.
- Evaluate whether `fg.assertions` should become the graph-level assertion
  collection entrypoint.
- Evaluate whether `fg.views.create(...)` should support named frozen
  assertion-id selections through `asrt_ids=[...]` and/or `asrts=[...]`.
- Preserve `write.retract(asrt_id)` as the precise mutation primitive.
- Keep the first scoped slice read/projection-oriented unless a later
  falsifier proves rule/runtime integration must be included.
- Separate assertion-universe selection from confidence/projection policy.
- Preserve existing `ViewSpec` compatibility until an explicit migration path
  is scoped.

## 3. Non-goals

- No `fg_subset` / subgraph object that forks or copies the database.
- No physical delete; ledger remains append-only.
- No fuzzy retract such as `retract(User.name, value=...)`.
- No immediate removal of `ViewSpec`.
- No package rename or release artifact rewrite.
- First scoped slice is frozen assertion-id selection only: view
  membership is captured from explicit `asrt_id` values and does not grow
  automatically as new assertions are written.
- No dynamic predicate-based view in this blueprint. A dynamic membership
  view such as "all assertions matching this predicate, including future
  writes" requires a separate blueprint and falsifier pass.
- No rule/evaluate/runtime projector integration in this blueprint.
  `fg.run(...)`, `fg.evaluate(...)`, and `project_view_facts(...)` keep
  their current assertion universe behavior unless a later blueprint
  explicitly scopes runtime view consumption.

## 4. Current Context

Current implementation facts to verify and refine during §5:

- `ViewSpec` currently has exactly:
  - `active: bool = True`
  - `confidence_strategy: "max" | "mean" | "median" | "prefer_source"`
  - `prefer_source: str | None`
- `fg.views` currently manages a name-to-`ViewSpec` registry with
  `create`, `update`, `delete`, `get`, and `list`.
- `fg.read.find(..., view=...)` resolves a named/spec view after `sdk_find`
  and injects confidence metadata into returned snapshots.
- `fg.run(rule, view=..., return_display_meta=True)` uses `ViewSpec` only
  for display metadata after rule rows are produced.
- `fg.run(Query, view=...)` rejects view.
- `fg.evaluate(..., view=...)` rejects view.
- Core/application runtime paths commonly call `project_view_facts(...)`,
  but that projector does not consume the SDK `fg.views` registry.
- Field-level `AssertionRecordSet` already provides
  `.where(...)`, `.one()`, `.all()`, `.first()` and tuple-compatible
  collection behavior.

Related recent design conclusions:

- `AssertionRecordSet` established read-side assertion selection helpers
  while preserving exact `retract(asrt_id)` semantics.
- Temporal business-time filtering currently exists only at field assertion
  level through `.at(t)`, backed by `meta.raw["valid_from"]` /
  `meta.raw["valid_to"]`.
- Archived temporal semantics explicitly warned against casually restoring
  broad `temporal_view` runtime semantics.

## 5. Design Questions / Falsifier Pass

### 5.1 View identity

Candidate lock:

```text
View = named frozen assertion-id selection
```

Falsifiers:

- Current runtime usage proves `ViewSpec` must remain the only `view`
  concept for compatibility.
- A frozen asrt-id set cannot support key review workflows without dynamic
  predicate semantics.
- The term `view` is too overloaded and a separate name such as
  `selection` is required.

**Decision (LOCKED 2026-05-11):**

A FactGraph view is a **named frozen assertion-id selection**: membership
is fixed at view-creation time by a concrete set of `asrt_id` strings, and
the view name in `fg.views` resolves to that set.

This is a redefinition of the long-term meaning of the existing `fg.views`
registry, not a parallel mechanism. The current `ViewSpec` type is treated
as legacy projection-policy compatibility, not the target meaning of
"view". Existing `ViewSpec` support must remain available until a
migration step is explicitly scoped (§5.5 / §5.8).

Locked semantics:

- A view is not a subgraph and does not fork ledger state.
- A view is not a dynamic predicate; future writes do not enter the view
  automatically.
- A view stores or resolves to assertion identity (`asrt_id`) membership,
  not copied assertion payloads.
- A view may be created from richer assertion objects as a convenience,
  but only their `asrt_id` values participate in membership.
- Projection/conflict policy is not view membership and is handled by
  §5.5.

Explicitly NOT decided in §5.1:

- The exact `fg.views.create(...)` overload shape → §5.4.
- The compatibility shape for existing `fg.views.create(name, ViewSpec)`
  users → §5.8.
- Whether rule/runtime execution consumes frozen assertion views → §5.7.

### 5.2 `fg.assertions` graph-level collection

Questions:

- Should `fg.assertions` expose all assertions in the current graph?
- What record shape should `fg.assertions.where(...).all()` return?
- Does graph-level assertion record need `entity_type`, `field_name`,
  `pred_id`, `e_ref`, `identity`, `value`, `meta`, `is_active`, and
  `is_revoked`?
- Should graph/entity/field assertion collections share one interface while
  allowing different record richness by scope?

**Decision (LOCKED 2026-05-11):**

First-slice graph-level assertion access ships as a narrow by-id lookup
surface, not as full graph-wide assertion enumeration.

`fg.assertions` is introduced as a read-only assertion namespace whose
first scoped purpose is to close the `FrozenAssertionView` readback loop:

```python
view = fg.views.get("review_set")          # FrozenAssertionView
records = fg.assertions.by_ids(view.asrt_ids)
target = fg.assertions.by_id(one_asrt_id)
```

Shipped surface:

- `fg.assertions.by_id(asrt_id) -> AssertionRecord | None`
- `fg.assertions.by_ids(asrt_ids) -> AssertionRecordSet`

Semantics:

- `by_id(...)` returns `None` when the assertion id is unknown.
- `by_ids(...)` accepts any `Iterable[str]`. `FrozenAssertionView.asrt_ids`
  (a `frozenset`) is therefore directly usable as input.
- `by_ids(...)` returns an `AssertionRecordSet` containing the records that
  can be resolved from the supplied ids. Unknown ids are skipped by
  default; the first slice does not ship a `strict=` parameter.
- Returned records use the existing `AssertionRecord` shape. They do not
  add `entity_type`, `field_name`, `pred_id`, `e_ref`, or identity fields
  in this slice.
- Returned record order is implementation-defined and stable within a
  single process; this blueprint does not introduce a new public sort
  guarantee. The natural implementation is sorted by `asrt_id`, but
  callers should not depend on a specific order.
- Lookup uses existing ledger by-id primitives (`get_claim`, `find_meta`,
  `find_claim_args`, revocation state) and does not require a new
  application protocol, core store primitive, or rule/runtime integration.

Explicitly not shipped in §5.2 first slice:

- `fg.assertions.active`
- `fg.assertions.history`
- `fg.assertions.where(...)`
- graph-wide `.at(t)` / `.version(v)` enumeration
- entity-level whole-snapshot `snapshot.assertions.where(...)`

Rationale:

The first slice must make frozen assertion views inspectable without
turning `fg.assertions` into a graph-wide query language. Full graph-level
enumeration would require a richer record shape carrying entity/field
context and would create ledger-wide scan, indexing, and application-first
runtime authority questions. By-id lookup is a narrow SDK read helper over
existing ledger primitives and is sufficient to connect
`FrozenAssertionView.asrt_ids` back to concrete `AssertionRecord` values.

This `fg.assertions` namespace is distinct from the
`fg.read.assertions(...)` selector entry that was explicitly not shipped in
the archived assertion-selection blueprint. The archived rejection was
about adding a read-namespace selector that duplicated snapshot-side
`FieldAssertions` traversal. The current `fg.assertions` is a top-level
by-id lookup namespace, not a snapshot-traversing selector.

Conditional re-open:

- Re-open §5.2 if users need exploratory graph-level assertion querying
  such as `fg.assertions.where(source="seed").all()`.
- Re-open §5.2 if future view workflows require record context beyond the
  current `AssertionRecord` shape (`entity_type`, `field_name`, `pred_id`,
  `e_ref`, identity).
- Re-open §5.2 if users need strict all-or-error resolution for
  `by_ids(...)`; this can be added later as an opt-in keyword without
  changing the default skip-unknown behavior.

### 5.3 Assertion collection operations

Questions:

- Should graph/entity/field assertion collections share
  `.active()`, `.history()`, `.at(t)`, `.version(v)`, `.where(...)`,
  `.by_id(...)`, `.one()`, `.first()`, and `.all()`?
- Are `active` / `history` base-set selectors while `at` / `version` /
  `where` are filters over the current set?
- Should these be methods at graph/entity level even though field-level
  `FieldAssertions.active/history` are currently properties?

**Decision (LOCKED 2026-05-11):**

Assertion collection operations are defined on assertion collections, not
on rule/runtime evaluation. The first slice extends the existing
`AssertionRecordSet` returned-object surface with filter helpers while
preserving all behavior locked by the assertion-selection blueprint.

Conceptual model:

- `active` and `history` are **base-set selectors**.
- `at(t)`, `version(v)`, `where(...)`, and `by_id(...)` are **filters over
  the current assertion collection**.
- `.one()`, `.first()`, and `.all()` are **terminal helpers** over the
  current assertion collection.

Field-level compatibility:

- `FieldAssertions.active` remains a property returning
  `AssertionRecordSet`.
- `FieldAssertions.history` remains a property returning
  `AssertionRecordSet`.
- `FieldAssertions.at(t)` remains supported and is defined as the
  compatibility shortcut for `FieldAssertions.active.at(t)`.
- `FieldAssertions.version(v)` remains supported and is defined as the
  compatibility shortcut for `FieldAssertions.active.version(v)`.
- `FieldAssertions.at(t)` / `.version(v)` therefore keep current behavior:
  they filter active assertions, not full history.

`AssertionRecordSet` operations:

- `.where(...)` keeps the existing filter dimensions and AND semantics
  from the assertion-selection blueprint.
- `.at(t)` filters the current record set by business-time validity using
  `meta.raw["valid_from"]` / `meta.raw["valid_to"]`. Missing
  `valid_from` excludes the record. `valid_to` is exclusive when present.
- `.at(t)` parameter format follows the current `FieldAssertions.at(t)`
  validation contract: ISO 8601 timestamp text.
- `.version(v)` filters the current record set by
  `meta.raw["version"] == v`.
- `.by_id(asrt_id)` filters the current record set to records whose
  `record.asrt_id == asrt_id`.
- `.one()`, `.first()`, and `.all()` keep existing semantics.
- Every non-terminal filter returns `AssertionRecordSet`, preserving
  chaining: `.history.at(t).where(...).by_id(...).one()`.

Archived invariant preservation:

- This extension is purely additive on top of the archived
  assertion-selection blueprint. Its tuple compatibility,
  `.where(...)` / `.one()` / `.all()` / `.first()` semantics,
  `write.retract(asrt_id)` boundary, and `kernel.sdk.__all__` unchanged
  invariant remain preserved.

Graph/entity scope deferred shape:

- Graph-level and entity-level assertion collections, if shipped in this
  blueprint, should reuse the same `AssertionRecordSet` filter/terminal
  surface.
- Whether graph/entity base-set selectors are exposed as properties or
  methods is not decided here → §5.2.
- Field-level property shape is preserved regardless of the graph/entity
  shape chosen later.

Explicitly NOT decided in §5.3:

- The concrete `fg.assertions` graph-level entrypoint shape → §5.2.
- Whether entity-level `snapshot.assertions` grows a whole-entity
  collection view in addition to the existing field namespace → §5.2 /
  §5.6.
- Runtime/rule temporal semantics for `.at(t)` or `.version(v)` → §5.7
  deferred.

### 5.4 View creation and update

Candidate shape:

```python
fg.views.create("review_set", asrt_ids=[...])
fg.views.create("review_set", asrts=[...])
fg.views.update("review_set", asrt_ids=[...])
fg.views.patch("review_set", add_asrt_ids=[...], remove_asrt_ids=[...])
fg.views.diff("review_set", asrt_ids=[...])
```

Questions:

- Should `asrts=[...]` be accepted as a convenience that stores only
  `record.asrt_id` internally?
- Should `update` mean whole-set replacement?
- Should `patch` be required before any mutating view update can ship?
- What should `diff` return: ids only, assertion records, or a dedicated
  diff DTO?

**Decision (LOCKED 2026-05-11):**

First-slice view creation ships as additive overloads on the existing
`fg.views.create(...)` and `fg.views.update(...)` registry methods.

Supported creation / replacement shapes:

```python
fg.views.create("review_set", asrt_ids=[...])
fg.views.create("review_set", asrts=[...])
fg.views.update("review_set", asrt_ids=[...])
fg.views.update("review_set", asrts=[...])
```

Legacy compatibility remains unchanged:

```python
fg.views.create("preferred_names", ViewSpec(...))
fg.views.update("preferred_names", ViewSpec(...))
```

Dispatch contract:

- Exactly one view payload is accepted per call: a legacy `ViewSpec`,
  `asrt_ids=[...]`, or `asrts=[...]`.
- `ViewSpec` payloads preserve existing behavior exactly (per §5.8).
- `asrt_ids=[...]` creates or replaces a frozen assertion-membership
  view. Membership is normalized to an immutable deduplicated set of
  `asrt_id` strings. Membership order is not public API.
- `asrts=[...]` is a convenience input only. Each object must expose
  `asrt_id`; only those ids participate in membership. Assertion payload,
  value, meta, activity state, and ordering are not stored as view
  membership.
- Assertion ids are validated as assertion identities, not entity refs.
  Revoked assertions are valid members because views select assertion
  universe membership, not only active facts.

Readback contract:

- `fg.views.get(name)` returns the stored immutable view entry.
- For legacy entries, this remains `ViewSpec`.
- For frozen assertion views, this returns a `FrozenAssertionView` — a
  frozen returned-object value exposing the membership as
  `asrt_ids: frozenset[str]`.
- `FrozenAssertionView` is documented as returned-object surface from
  `fg.views.get(...)` / `fg.views.list()` and is not added to
  `kernel.sdk.__all__`.
- `fg.views.list()` returns all registered views as
  `dict[str, ViewSpec | FrozenAssertionView]`.
- The built-in `"default"` view remains the legacy `ViewSpec()` entry in
  this slice.

Mutation contract:

- `update(name, ...)` is whole-set replacement for assertion views.
- `delete(name)` keeps current behavior for all view kinds: `"default"` is
  protected; other existing view names may be deleted.
- `patch(...)` is not shipped in this slice.
- `diff(...)` is not shipped in this slice.

Explicitly NOT decided in §5.4:

- Incremental update helpers such as
  `fg.views.patch(name, add_asrt_ids=[...], remove_asrt_ids=[...])`.
- View diff helpers such as `fg.views.diff(name, asrt_ids=[...])` and
  their return type.
- Persistence/import/export of named views.
- Any dynamic predicate-based membership update.
- Whether `asrt_ids` strings are validated against ledger existence is an
  implementation choice. Default is no existence check, because a frozen
  view may reference assertions from a different snapshot, an import, or a
  future fresh-graph scenario.
- Empty `asrt_ids=[]` membership is accepted by default; it creates a
  frozen empty view and can serve as a future `patch(...)` seed.

### 5.5 Projection policy split

Candidate split:

```text
view
  -> assertion universe / frozen asrt_id set

projection policy
  -> confidence_strategy / prefer_source / chosen-value policy
```

Questions:

- Should `ViewSpec` be treated as legacy projection policy?
- Should a new `ProjectionSpec` be introduced, or should projection options
  remain keyword args on read/run calls?
- Should `confidence_strategy` and `prefer_source` move from view creation
  to read/run call time?
- How should compatibility with `fg.views.create(name, ViewSpec(...))` be
  preserved?

**Decision (LOCKED 2026-05-11):**

Projection/conflict policy is separate from view membership.

View membership answers:

```text
Which assertion ids are visible in this named view?
```

Projection policy answers:

```text
Given the visible assertions, how should conflicts, confidence, and
chosen values be projected for read/display?
```

For this blueprint:

- `confidence_strategy` and `prefer_source` are projection-policy
  concerns, not view-membership concerns.
- This blueprint does not redesign projection policy in the first slice.
- Existing `ViewSpec(confidence_strategy=..., prefer_source=...)`
  behavior remains compatibility surface per §5.8.
- Future APIs may move projection policy to runtime call options or a
  `ProjectionSpec`, but that migration is deferred.
- A frozen assertion view may later be combined with projection policy,
  but the two concepts must remain distinct.

Explicitly NOT decided in §5.5:

- Whether projection policy becomes `ProjectionSpec`.
- Whether `fg.read.find(..., projection=...)` is added.
- Whether old `ViewSpec.active` maps to view membership, projection
  policy, or compatibility-only behavior in a future migration.

### 5.6 Read API behavior

Questions:

- Should `fg.read.get/find(..., view="review_set")` restrict the assertion
  universe before snapshot projection?
- If a view excludes an entity's existence assertion but includes field
  assertions, is the entity visible?
- If a view includes a field assertion but excludes conflicting assertions,
  how is scalar field projection computed?
- Should view-scoped reads always expose full assertion history within the
  view, or only projected active assertions?

**Decision (LOCKED 2026-05-11):**

First-slice read APIs preserve current `ViewSpec` behavior and do not
consume frozen assertion-view membership for snapshot projection.

Legacy behavior remains unchanged:

- `fg.read.find(Entity, view=ViewSpec(...))` keeps current projection /
  confidence behavior.
- `fg.read.find(Entity, view="<legacy ViewSpec name>")` keeps current
  projection / confidence behavior.
- `fg.read.get(...)` remains identity-only and does not gain a `view=`
  parameter.
- `fg.run(rule, view="<legacy ViewSpec name>", return_display_meta=True)`
  keeps current display-meta behavior.
- `fg.evaluate(..., view=...)` continues to reject view.

Frozen assertion-view behavior in this slice:

- `fg.read.find(Entity, view="<FrozenAssertionView name>")` raises a clear
  SDK error. Frozen assertion views are inspectable through
  `fg.views.get(name).asrt_ids` plus `fg.assertions.by_ids(...)`, not
  through snapshot projection.
- `fg.read.find(Entity, view=FrozenAssertionView(...))`, if a caller holds
  a returned object directly, raises the same category of SDK error.
- `fg.run(rule, view="<FrozenAssertionView name>", return_display_meta=True)`
  raises a clear SDK error. Frozen assertion views do not affect rule fact
  universe or display-meta calculation in this slice.
- `fg.run(Query, view="<FrozenAssertionView name>")` remains rejected by
  the existing Query view rule.
- `fg.evaluate(..., view=...)` remains rejected for all view values.

Error message contract:

- The raised error must identify the API path (`fg.read.find` or
  `fg.run`) and the rejected frozen assertion view, either by name or by
  `FrozenAssertionView` type.
- The error must point users to the supported workaround:
  `fg.views.get(name).asrt_ids` plus `fg.assertions.by_ids(...)`.
- Exact string format is implementation-defined; only the semantic
  content above is binding.

Moot questions under this first slice:

- Entity visibility under frozen views is not defined here.
- Field scalar projection under frozen views is not defined here.
- Whether view-scoped reads expose full assertion history within the view
  is not defined here.

User-facing workaround:

```python
view = fg.views.get("review_set")     # FrozenAssertionView
records = fg.assertions.by_ids(view.asrt_ids)
```

Rationale:

`ViewSpec` currently means projection/confidence policy on read/display
paths. `FrozenAssertionView` means assertion-universe membership. Letting
`fg.read.find(..., view=<FrozenAssertionView>)` silently reinterpret
`view=` would collapse the §5.5 membership/projection split and force this
blueprint to decide entity visibility, field projection, and history
semantics. Those are follow-up read-scoping questions, not first-slice
view creation questions.

Conditional re-open:

- Re-open §5.6 if users need entity-scoped reads from frozen assertion
  views.
- Re-open §5.6 if §5.2 is re-opened to add richer graph assertion records
  with entity/field context.

### 5.7 Rule / runtime integration

Questions:

- Should first scoped implementation explicitly defer `fg.run(..., view=...)`
  over frozen assertion views?
- If rule/run support is scoped, should `project_view_facts(...)` accept an
  assertion-id universe parameter?
- How does assertion-view scoping interact with existing active/chosen
  projection in core/runtime paths?
- How do we prevent assertion filtering names like `.at(t)` from reopening
  broad temporal reasoning semantics accidentally?

**Decision (LOCKED 2026-05-11):**

Rule/runtime integration is deferred. Changing the long-term meaning of
`fg.views` and adding frozen assertion-view membership does not
automatically make rule/evaluate consume that assertion universe.

Current code has an existing split: the SDK `fg.views` registry is not
consumed by core `project_view_facts(...)`. This blueprint records that
split as design debt but does not close it in the first scoped slice.

Specifically deferred to a follow-up blueprint:

- `fg.run(rule, view=...)` does not gain assertion-universe scoping in
  this slice; current display-meta behavior is preserved.
- `fg.evaluate(..., view=...)` continues to reject view in this slice.
- `project_view_facts(...)` is not extended with an assertion-universe
  parameter in this slice.
- Application capability helpers that call `project_view_facts(...)` keep
  their current active/chosen projection behavior.

Rule/runtime integration must be scoped explicitly through its own §5
falsifier pass before any runtime fact-universe behavior changes.

### 5.8 Compatibility and migration

Questions:

- Which current docs/tests rely on `fg.views.create(name, ViewSpec)`?
- Should existing `ViewSpec` behavior remain as-is while new assertion views
  are added under different overloads?
- Should `ViewSpec` be renamed only in docs, or via code alias in a later
  migration?
- What deprecation, if any, is acceptable for a preview release line?

**Decision (LOCKED 2026-05-11):**

Existing `ViewSpec` behavior remains compatible in this blueprint. The
first scoped slice must not break code that currently uses:

```python
fg.views.create("preferred_names", ViewSpec(...))
fg.views.update("preferred_names", ViewSpec(...))
fg.views.get("preferred_names")
fg.read.find(User, view="preferred_names")
fg.run(rule, view="preferred_names", return_display_meta=True)
```

Compatibility contract:

- `ViewSpec` remains accepted by the existing registry path during this
  slice.
- Existing `fg.views.create(name, ViewSpec)` and
  `fg.views.update(name, ViewSpec)` behavior is not removed here.
- The long-term conceptual direction is to treat `ViewSpec` as projection
  policy compatibility, not as the target meaning of view membership.
- Any rename or migration from `ViewSpec` to `ProjectionSpec` is deferred
  to a follow-up blueprint.
- No deprecation warning is introduced in this slice unless later §5
  decisions explicitly scope one.

This compatibility lock exists to separate conceptual correction from
breaking API migration.

## 6. Boundaries And Invariants

Following the §5.1–§5.8 LOCKED decisions, the following invariants govern
any scoped implementation of this blueprint.

**Ledger and assertion identity invariants:**

- The ledger remains append-only; no physical delete is introduced.
- `write.retract(asrt_id)` remains the precise mutation primitive for
  revoking one assertion.
- `asrt_id` remains the assertion identity unit used for view membership.
- A view must not fork ledger state, copy the database, or create a mutable
  subgraph.
- Existing `idref_v1`, identity coordinate semantics, primary-first batch
  identity semantics, and partial-identity `find(...)` semantics inherited
  from the archived 2026-05-10 blueprints remain unchanged.

**`fg.views` registry and `FrozenAssertionView` invariants:**

- `fg.views.create/update/delete/get/list` preserve legacy `ViewSpec`
  compatibility (per §5.8).
- The built-in `"default"` view remains protected and continues to be the
  legacy `ViewSpec()` entry in this slice.
- `fg.views.create/update(name, ViewSpec(...))` keeps existing behavior.
- `fg.views.create/update(name, asrt_ids=[...])` and
  `fg.views.create/update(name, asrts=[...])` create or replace frozen
  assertion-membership views (per §5.4).
- Each create/update call accepts exactly one view payload kind:
  `ViewSpec`, `asrt_ids`, or `asrts`.
- `FrozenAssertionView` membership is an immutable deduplicated
  `frozenset[str]` of `asrt_id` values; membership order is not public
  API.
- `asrts=[...]` is convenience input only. Only `.asrt_id` participates in
  membership; assertion value, metadata, activity state, payload, and
  ordering are not stored as membership.
- Revoked assertions are valid members because membership is assertion
  universe selection, not active-fact projection.
- Empty `asrt_ids=[]` membership is valid and creates a frozen empty view.
- The default first-slice behavior does not require ledger-existence
  validation for `asrt_ids`.
- `fg.views.get/list` read back mixed legacy `ViewSpec` and
  `FrozenAssertionView` entries.
- `FrozenAssertionView` is a returned-object surface exposing
  `asrt_ids: frozenset[str]`; it is not added to `kernel.sdk.__all__`.
- `fg.views.patch(...)` and `fg.views.diff(...)` are not shipped in this
  slice.

**`AssertionRecordSet` extension invariants:**

- The archived assertion-selection blueprint remains the additive baseline:
  tuple compatibility, slicing/concatenation/multiplication type
  preservation, `.where(...)`, `.one()`, `.all()`, `.first()`,
  `write.retract(asrt_id)`, and unchanged `kernel.sdk.__all__` are
  preserved.
- `AssertionRecordSet.at(t)` filters the current record set by
  business-time validity using `meta.raw["valid_from"]` /
  `meta.raw["valid_to"]`.
- `valid_from` is required for `.at(t)` inclusion; missing `valid_from`
  excludes the record.
- `valid_to` is exclusive when present, giving `[valid_from, valid_to)`
  interval semantics.
- `.at(t)` input follows the current ISO 8601 timestamp-text validation
  contract.
- `AssertionRecordSet.version(v)` filters the current record set by
  `meta.raw["version"] == v`.
- `AssertionRecordSet.by_id(asrt_id)` filters the current record set by
  exact `record.asrt_id` match.
- Every non-terminal filter returns `AssertionRecordSet`, preserving
  chaining.
- Assertion collection filtering is SDK read-side selection, not rule
  semantics.

**`FieldAssertions` compatibility invariants:**

- `FieldAssertions.active` remains a property returning
  `AssertionRecordSet`.
- `FieldAssertions.history` remains a property returning
  `AssertionRecordSet`.
- `FieldAssertions.at(t)` remains supported and is the compatibility
  shortcut for `FieldAssertions.active.at(t)`.
- `FieldAssertions.version(v)` remains supported and is the compatibility
  shortcut for `FieldAssertions.active.version(v)`.
- Existing tuple-style use of field assertion records remains compatible.

**`fg.assertions` namespace invariants:**

- `fg.assertions` is a top-level read-only assertion namespace.
- The first slice ships only
  `fg.assertions.by_id(asrt_id) -> AssertionRecord | None` and
  `fg.assertions.by_ids(Iterable[str]) -> AssertionRecordSet`.
- `FrozenAssertionView.asrt_ids` is directly usable as
  `fg.assertions.by_ids(...)` input.
- Unknown ids are skipped by default in `by_ids(...)`; no `strict=`
  parameter ships in this slice.
- Returned records use the existing `AssertionRecord` shape and do not add
  `entity_type`, `field_name`, `pred_id`, `e_ref`, or identity fields.
- Returned record order is implementation-defined and stable within a
  single process; callers must not depend on a public sort guarantee.
- `fg.assertions.active`, `fg.assertions.history`,
  `fg.assertions.where(...)`, and graph-wide `.at(...)` / `.version(...)`
  enumeration are not shipped in this slice.
- Entity-level whole-snapshot `snapshot.assertions.where(...)` is not
  shipped in this slice.
- The `fg.assertions` namespace is distinct from the archived
  `fg.read.assertions(...)` selector that was explicitly not shipped; it
  is a by-id lookup namespace, not a snapshot-traversing selector.
- Lookup uses existing ledger by-id primitives and does not require a new
  application protocol, core store primitive, or runtime integration.

**Read API behavior invariants:**

- `fg.read.find(Entity, view=ViewSpec(...))` keeps current projection /
  confidence behavior.
- `fg.read.find(Entity, view="<legacy ViewSpec name>")` keeps current
  projection / confidence behavior.
- `fg.read.get(...)` remains identity-only and does not gain a `view=`
  parameter.
- `fg.run(rule, view="<legacy ViewSpec name>", return_display_meta=True)`
  keeps current display-meta behavior.
- `fg.read.find(Entity, view="<FrozenAssertionView name>")` and
  `fg.read.find(Entity, view=FrozenAssertionView(...))` raise SDK errors
  instead of applying snapshot projection through frozen membership.
- `fg.run(rule, view="<FrozenAssertionView name>", return_display_meta=True)`
  raises an SDK error instead of using frozen membership for rule fact
  universe or display-meta calculation.
- `fg.run(Query, view=...)` remains rejected.
- `fg.evaluate(..., view=...)` remains rejected for all view values.
- Frozen-view read/run rejection errors must identify the API path, name or
  type the rejected frozen assertion view, and point users to
  `fg.views.get(name).asrt_ids` plus `fg.assertions.by_ids(...)`.
- Entity visibility, field scalar projection, and view-scoped history under
  frozen assertion views are not defined in this slice.

**Runtime / rule integration invariants:**

- `fg.run(...)` does not gain assertion-universe scoping from frozen views
  in this slice.
- `project_view_facts(...)` is not extended with an assertion-universe
  parameter in this slice.
- Application capability helpers that call `project_view_facts(...)` keep
  their current active/chosen projection behavior.
- Closing the SDK `fg.views` registry / core projector split is design debt
  reserved for a follow-up blueprint.
- Broad temporal reasoning semantics are not reopened by SDK assertion
  filters such as `.at(t)` or `.version(v)`.

**Public surface and repository safety invariants:**

- `kernel.sdk.__all__` remains unchanged.
- `FrozenAssertionView` is documented as a returned-object surface, not as
  an exported constructor.
- `fg.assertions` follows the existing namespace-property pattern of
  `fg.read`, `fg.write`, and `fg.views`; namespace properties are not
  `kernel.sdk.__all__` exports.
- Working notes under `docs/references/working/` remain rationale inputs,
  not current implementation truth.
- Archived blueprints and release snapshots remain immutable.
- `release/0.1.x` and `v0.1.0-rc.1` artifacts are not modified by this
  blueprint.
- Archived 2026-05-10 primary-identity, primary-anchor read, and
  assertion-selection LOCKED decisions are inputs to this blueprint and
  are not re-litigated here.

## 7. Acceptance

Acceptance is split into three groups: closed gates from the §5 design
pass, scope-freeze gates that must pass before `draft → scoped`, and
implementation gates that must pass before any code change ships.

**Closed (§5 design pass, 2026-05-11):**

- [x] §5.1–§5.8 have explicit LOCKED decisions recorded in the audit log.
- [x] Frame-pass batch locks (§5.1 / §5.5 / §5.7 / §5.8) are recorded in
      baseline commit `c977fba`.
- [x] §6 invariants (8 groups) reflect §5.1–§5.8 LOCKED decisions without
      introducing new behavior.
- [x] `AssertionRecordSet` extension preserves the archived
      assertion-selection blueprint §6 invariants as additive baseline.
- [x] Legacy `fg.views.create(name, ViewSpec)` compatibility surface is
      preserved per §5.8.

**Scope-freeze gates (passed before `draft → scoped`, 2026-05-11):**

- [x] §6 invariants reviewed and consistent with §5.1–§5.8 LOCKED
      decisions.
- [x] §7 acceptance reviewed and locked.
- [x] §8 implementation plan reviewed and locked.
- [x] Pre-scope-freeze docs/examples/notebooks scan completed: grep SDK
      docs/examples for stale `view` / `ViewSpec` language that would
      mislead users about `FrozenAssertionView` semantics.
- [x] Any stale items found in the scan above are either deferred to Phase
      3 docs sync or the relevant §5 decision is explicitly re-opened.
- [x] Blueprint body and audit log explain the frame-pass design order
      (§5.1 / §5.5 / §5.7 / §5.8 batch locked before §5.4 / §5.3 / §5.2 /
      §5.6 sequential locks) without requiring readers to infer it from
      git history.

**Implementation gates (passed, 2026-05-11):**

Ledger and assertion identity:

- [x] No diff under `src/kernel/core/store/` for this slice.
- [x] `asrt_id` generation semantics are unchanged.
- [x] No physical delete capability is introduced.

`fg.views` and `FrozenAssertionView`:

- [x] Legacy `fg.views.create/update/delete/get/list(...)` behavior with
      `ViewSpec` is preserved.
- [x] `fg.views.create(name, asrt_ids=[...])` stores membership as
      `frozenset[str]`.
- [x] `fg.views.create(name, asrts=[...])` accepts duck-typed objects with
      `asrt_id`; only `asrt_id` participates in membership.
- [x] Exactly one payload kind is accepted per `create/update` call.
- [x] Revoked `asrt_id` values are accepted as members.
- [x] Empty `asrt_ids=[]` is accepted.
- [x] No ledger-existence check is required on `asrt_ids` by default.
- [x] Built-in `"default"` view protection is preserved.
- [x] `FrozenAssertionView.asrt_ids` exposes `frozenset[str]`.
- [x] `FrozenAssertionView` is not in `kernel.sdk.__all__`.
- [x] `patch(...)` / `diff(...)` are not shipped.

`AssertionRecordSet` extension:

- [x] Existing `.where(...)`, `.one()`, `.all()`, `.first()`, tuple
      compatibility, and `kernel.sdk.__all__` invariants from the archived
      assertion-selection blueprint are preserved.
- [x] `.at(t)` filters by `meta.raw["valid_from"]` /
      `meta.raw["valid_to"]` with half-open interval
      `[valid_from, valid_to)`; missing `valid_from` excludes.
- [x] `.at(t)` input is validated as ISO 8601 timestamp text.
- [x] `.version(v)` filters by `meta.raw["version"] == v`.
- [x] `.by_id(asrt_id)` filters by exact `record.asrt_id == asrt_id`.
- [x] All non-terminal filters return `AssertionRecordSet`; chained
      `.where(...).at(...).version(...).by_id(...)` works.
- [x] `AssertionRecordSet` remains absent from `kernel.sdk.__all__`.

`FieldAssertions` compatibility:

- [x] `.active` / `.history` remain properties returning
      `AssertionRecordSet`.
- [x] `FieldAssertions.at(t)` is equivalent to `.active.at(t)` and keeps
      active-only behavior.
- [x] `FieldAssertions.version(v)` is equivalent to `.active.version(v)`.

`fg.assertions` namespace:

- [x] `fg.assertions.by_id(asrt_id) -> AssertionRecord | None`.
- [x] `fg.assertions.by_ids(Iterable[str]) -> AssertionRecordSet`.
- [x] `FrozenAssertionView.asrt_ids` is accepted directly by
      `fg.assertions.by_ids(...)`.
- [x] Unknown ids are skipped by default.
- [x] No `strict=` parameter is shipped.
- [x] No graph-wide `.active`, `.history`, `.where(...)`, `.at(...)`, or
      `.version(...)` is shipped.
- [x] Returned records use the existing `AssertionRecord` shape; no
      `entity_type`, `field_name`, `pred_id`, `e_ref`, or identity fields
      are added.

Read API behavior:

- [x] `fg.read.find(Entity, view=ViewSpec(...))` and
      `view="<legacy ViewSpec name>"` are unchanged.
- [x] `fg.read.get(...)` accepts no `view=` parameter.
- [x] `fg.read.find(Entity, view="<FrozenAssertionView name>")` raises an
      SDK error.
- [x] `fg.read.find(Entity, view=<FrozenAssertionView object>)` raises the
      same SDK error category.
- [x] `fg.run(rule, view="<legacy ViewSpec name>", return_display_meta=True)`
      is unchanged.
- [x] `fg.run(rule, view=<FrozenAssertionView>, return_display_meta=True)`
      raises an SDK error.
- [x] Error messages name or type the rejected frozen view, identify the
      API path, and point to `fg.views.get(name).asrt_ids` plus
      `fg.assertions.by_ids(...)`.

Runtime / rule defer:

- [x] No diff in `project_view_facts(...)` signature.
- [x] No diff under `src/kernel/core/store/_evaluate.py` related to
      assertion-universe handling.
- [x] No diff in application capability helpers for Check, Diagnose, Fact
      Overlay, Why-not, ProofFrame, or ProofFrame Diff.
- [x] `fg.evaluate(..., view=...)` continues to reject all view values.

Public surface and repository safety:

- [x] `kernel.sdk.__all__` length remains 35.
- [x] `fg.assertions` follows the existing `fg.read` / `fg.write` /
      `fg.views` namespace-property pattern and is not added to
      `kernel.sdk.__all__`.
- [x] Affected SDK docs are updated in the same implementation cycle as
      the behavior change.
- [x] No archived release snapshot, existing `release/0.1.x` artifact, or
      `v0.1.0-rc.1` tag/release artifact is modified.
- [x] No diff in archived blueprints under `docs/blueprints/archive/`.

## 8. Implementation Plan

The §5 design pass is closed (2026-05-11). The remaining work follows the
five phases below, gated by §7 scope-freeze gates and §7 implementation
gates.

### Phase 0: Pre-scope-freeze (gated by §7 scope-freeze gates)

Complete all §7 scope-freeze gates before flipping blueprint status from
`draft` to `scoped`. The non-trivial actions are:

1. Pre-scope-freeze docs/examples/notebooks scan: grep SDK docs/examples
   for stale `view` / `ViewSpec` language that would mislead users about
   `FrozenAssertionView` semantics, including:
   - wording that implies `view` only means legacy projection policy;
   - `find(..., view=...)` examples that need frozen-view rejection
     clarification;
   - wording that implies `fg.run(...)` / `fg.evaluate(...)` consume
     `fg.views` registry entries as assertion universes.
2. Record scan findings in the audit log and either defer them to Phase 3
   docs sync or explicitly re-open the relevant §5 decision.
3. Confirm the blueprint body and audit log explain the frame-pass design
   order (§5.1 / §5.5 / §5.7 / §5.8 batch locked before §5.4 / §5.3 /
   §5.2 / §5.6 sequential locks) without requiring readers to infer it
   from git history.

After all §7 scope-freeze gates pass: flip blueprint status to `scoped`
and record the event in the audit log.

### Phase 1: Test scaffolding (before implementation)

Add behavior tests codifying the §5.x LOCKED contracts. Tests for newly
scoped behavior should fail on current code (TDD baseline) and pass after
Phase 2 lands.

Target locations: appropriate test modules under `src/kernel/tests/`,
split by behavior area so failures are diagnosable:

- `test_sdk_assertion_record_set_extension.py`: `AssertionRecordSet`
  `.at(...)` / `.version(...)` / `.by_id(...)` filters, chainability, and
  archived assertion-selection invariants.
- `test_sdk_frozen_assertion_view.py`: `FrozenAssertionView`,
  `fg.views.create/update(...)` frozen-membership overloads, legacy
  `ViewSpec` compatibility, default-view protection, and no `patch` /
  `diff`.
- `test_sdk_field_assertions_compat.py`: `FieldAssertions.active` /
  `.history` compatibility and `.at(...)` / `.version(...)` shortcut
  equivalence.
- `test_sdk_fg_assertions.py`: `fg.assertions.by_id(...)` /
  `.by_ids(...)`, iterable inputs, unknown-id skip behavior, no `strict=`,
  and existing `AssertionRecord` shape.
- `test_sdk_view_read_api_rejection.py`: frozen-view rejection for
  `fg.read.find(...)` by name and by object, plus §5.6 error-message
  semantic contract.
- `test_sdk_view_runtime_defer.py`: `fg.run(...)` / `fg.evaluate(...)`
  frozen-view rejection and legacy display-meta behavior.
- `test_sdk_view_surface.py`: `kernel.sdk.__all__` unchanged and no new
  `fg.read.*` / `fg.write.*` helper methods.

Coverage must map back to §7 implementation gates. Git-verifiable gates
such as forbidden-path diffs and release-artifact safety remain Phase 4
checks rather than unit-test responsibilities.

### Phase 2: Implementation (SDK ergonomics layer, single cycle)

Scope: implement frozen assertion views and by-id assertion readback in the
SDK ergonomics layer only. No application protocol, rule authoring, core
store, runtime projector, or export-surface changes are scoped.

Critical files:

- `src/kernel/sdk/facade.py`:
  - add/host `FrozenAssertionView` as a returned-object surface, or import
    it from an adjacent SDK module if implementation chooses to place it
    there;
  - extend `AssertionRecordSet` with `.at(t)`, `.version(v)`, and
    `.by_id(asrt_id)` while preserving tuple compatibility and existing
    `.where(...)` / `.one()` / `.all()` / `.first()` behavior;
  - preserve `FieldAssertions.active` / `.history` as properties and keep
    `FieldAssertions.at(...)` / `.version(...)` as active-set shortcuts.
- `src/kernel/sdk/store.py`:
  - extend `_SDKViewsManager` (or successor) so `create/update` accept
    exactly one payload kind: legacy `ViewSpec`, `asrt_ids=[...]`, or
    `asrts=[...]`;
  - store frozen membership as immutable deduplicated `frozenset[str]`;
  - make `get/list` read back mixed `ViewSpec | FrozenAssertionView`
    entries while preserving legacy behavior;
  - add `SDKStore.assertions` as a read-only namespace property returning
    an internal assertions manager;
  - implement `fg.assertions.by_id(...)` / `.by_ids(...)` using existing
    ledger by-id primitives;
  - update `_resolve_view_spec(...)` or its successor to dispatch by
    registry-entry type: legacy `ViewSpec` flows through the existing
    projection/confidence path; `FrozenAssertionView` raises per §5.6.

Implementation constraints:

- Do not modify `src/kernel/application/`.
- Do not modify `src/kernel/authoring/`.
- Do not modify `src/kernel/core/`, including `project_view_facts(...)`
  and `src/kernel/core/store/_evaluate.py`.
- Do not modify `src/kernel/sdk/__init__.py`; `kernel.sdk.__all__`
  remains unchanged.
- Do not add new top-level `fg.read.*` or `fg.write.*` methods.
- Do not introduce `patch(...)`, `diff(...)`, a dynamic predicate view, a
  predicate DSL, fuzzy retract, or physical delete.
- Do not add `strict=` to `fg.assertions.by_ids(...)` in this slice.
- Do not extend `AssertionRecord` with entity / field / predicate /
  identity context fields.
- Preserve direct legacy `ViewSpec` compatibility for
  `fg.views.create/update/get/list(...)`, `fg.read.find(..., view=...)`,
  and `fg.run(..., view=..., return_display_meta=True)`.
- Error messages for frozen-view rejection must satisfy §5.6: identify the
  API path, name or type the rejected frozen assertion view, and point to
  `fg.views.get(name).asrt_ids` plus `fg.assertions.by_ids(...)`.
- No feature flag, deprecation warning, `__future__` opt-in, or dual-mode
  runtime integration path is introduced.

### Phase 3: Documentation sync (same cycle as Phase 2)

In the same implementation cycle as Phase 2, update affected SDK docs:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`
  if present and still aligned with the implemented API

Docs must explain:

- the long-term meaning of view as named frozen assertion-id selection;
- legacy `ViewSpec` as projection-policy compatibility, not the new view
  membership model;
- `FrozenAssertionView` creation/update/readback through
  `fg.views.create/update/get/list(...)`;
- the readback workflow:
  `view = fg.views.get(name)` then
  `records = fg.assertions.by_ids(view.asrt_ids)`;
- `AssertionRecordSet.at(...)`, `.version(...)`, `.by_id(...)`, and
  chainability examples;
- `fg.assertions.by_id(...)` / `.by_ids(...)` usage and unknown-id skip
  behavior;
- `fg.read.find(...)` / `fg.run(...)` frozen-view rejection and the
  workaround path;
- rule/runtime integration and `project_view_facts(...)` remaining
  unchanged in this slice;
- `patch(...)`, `diff(...)`, dynamic predicate views, graph-wide assertion
  enumeration, and view-scoped snapshot reads as follow-up design work.

### Phase 4: Verification and close

1. Run focused SDK tests added in Phase 1; require green.
2. Run relevant existing SDK/kernel test suites; require green, or record
   any pre-existing environment-only failure separately.
3. Verify every §7 implementation gate passes.
4. Confirm forbidden paths are clean with `git diff`:
   `src/kernel/application/`, `src/kernel/authoring/`, `src/kernel/core/`,
   and `src/kernel/sdk/__init__.py`.
5. Verify `kernel.sdk.__all__` count remains 35 and neither
   `FrozenAssertionView` nor `AssertionRecordSet` is exported.
6. Verify no new `fg.read.*` / `fg.write.*` helper method shipped.
7. Confirm no archived blueprint, archived release snapshot, existing
   `release/0.1.x` artifact, or `v0.1.0-rc.1` tag/release artifact is
   modified.
8. Fill §10 Outcome / Deviations. Record the frame-pass cadence as an
   explicit notable event: §5.1 / §5.5 / §5.7 / §5.8 were batch-locked in
   baseline commit `c977fba` before sequential §5.4 / §5.3 / §5.2 / §5.6
   locks.
9. Add audit log entries for Phase 1 / Phase 2 / Phase 3 / Phase 4 events
   as they complete.
10. Flip blueprint status `scoped → implemented`.

## 9. Docs To Update

Likely docs if scoped:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`

## 10. Outcome / Deviations

Task completed 2026-05-11.

- Final landed decision:
  Ship a first-slice frozen assertion view model in the SDK ergonomics
  layer. A FactGraph view can now be a named frozen assertion-id selection
  (`FrozenAssertionView`) while legacy `ViewSpec` projection-policy entries
  remain compatible.
- Final landed behavior:
  `fg.views.create/update(...)` accept exactly one payload kind: legacy
  `ViewSpec`, `asrt_ids=[...]`, or `asrts=[...]`; frozen membership is
  stored as `frozenset[str]` and read back through
  `FrozenAssertionView.asrt_ids`. `fg.assertions.by_id(...)` and
  `.by_ids(...)` provide by-id record readback using existing
  `AssertionRecord` / `AssertionRecordSet` shapes. `AssertionRecordSet`
  gained additive `.at(...)`, `.version(...)`, and `.by_id(...)` filters
  while preserving archived tuple-compatibility and `.where/.one/.all/.first`
  behavior. Legacy `ViewSpec` behavior for `fg.read.find(...)` and
  `fg.run(..., return_display_meta=True)` is unchanged. Frozen assertion
  views are rejected by snapshot/rule projection paths with guidance to use
  `fg.views.get(name).asrt_ids` plus `fg.assertions.by_ids(...)`.
- Deviations from draft:
  The blueprint's frame-pass on 2026-05-11 batch-locked §5.1 / §5.5 /
  §5.7 / §5.8 in baseline commit `c977fba` before sequential §5.4 /
  §5.3 / §5.2 / §5.6 locks. This was an intentional cadence choice to
  stabilize intertwined terminology, compatibility, runtime, and projection
  boundaries before lower-level API shape decisions. The implementation
  placed `FrozenAssertionView` in `src/kernel/sdk/store.py` as a
  non-exported returned-object surface rather than in `facade.py`; this
  keeps the object next to the `fg.views` registry that owns it.
- Deferred design questions:
  Dynamic predicate views, `patch(...)` / `diff(...)`, graph-wide assertion
  enumeration, entity-level `snapshot.assertions.where(...)`, strict
  by-id lookup mode, richer graph assertion record context, view-scoped
  snapshot reads, and rule/runtime assertion-universe integration remain
  follow-up blueprint work. Legacy `ViewSpec` → `ProjectionSpec` naming /
  migration remains deferred.
- Archive notes:
  Implemented locally on `master`; archive after final review and commit.
