# Task Blueprint: Frozen Assertion View Model

- Status: draft
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
  - [docs/blueprints/archive/2026-05-10_assertion-selection-crud-ergonomics.md](../archive/2026-05-10_assertion-selection-crud-ergonomics.md)
  - [docs/blueprints/archive/2026-03-18_scenario-a-temporal-semantics.md](../archive/2026-03-18_scenario-a-temporal-semantics.md)
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

### 5.3 Assertion collection operations

Questions:

- Should graph/entity/field assertion collections share
  `.active()`, `.history()`, `.at(t)`, `.version(v)`, `.where(...)`,
  `.by_id(...)`, `.one()`, `.first()`, and `.all()`?
- Are `active` / `history` base-set selectors while `at` / `version` /
  `where` are filters over the current set?
- Should these be methods at graph/entity level even though field-level
  `FieldAssertions.active/history` are currently properties?

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

Seed invariants, to be replaced after §5 locks:

- A view must not fork ledger state or create a mutable subgraph.
- View membership, if frozen, is by stable `asrt_id`.
- `write.retract(asrt_id)` remains the only scoped mutation primitive.
- Assertion collection filtering is read-side selection, not rule semantics.
- Projection/conflict policy must not be conflated with assertion-universe
  membership.
- Existing `ViewSpec` users must not be broken without an explicit migration
  decision.

## 7. Acceptance

Seed acceptance, to be replaced after §5 locks:

- [ ] Current `ViewSpec` usage is fully mapped across SDK, core,
      application, tests, and docs.
- [ ] §5 locks whether view means frozen assertion-id set.
- [ ] §5 locks whether `fg.assertions` is in scope.
- [ ] §5 locks read-only first slice vs rule/runtime integration.
- [ ] Compatibility story for existing `fg.views.create(name, ViewSpec)` is
      explicit.
- [ ] Affected SDK docs and working design notes are updated if behavior
      changes.

## 8. Implementation Plan

Draft-stage plan only:

1. Source-ground current view usage and record exact consumers.
2. Run §5 falsifier pass in narrow sections.
3. Update §6 / §7 / §8 after decisions are locked.
4. Scope-freeze only after compatibility and rule/runtime boundaries are
   explicit.
5. Implement in phases, starting with tests for the smallest locked surface.

## 9. Docs To Update

Likely docs if scoped:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md`

## 10. Outcome / Deviations

Task completion section to fill after implementation or explicit research
closure:

- Final landed decision:
- Final landed behavior:
- Deviations from draft:
- Deferred design questions:
- Archive notes:
