# Task Blueprint: Primary-Anchor Domain Read

- Status: implemented
- Created: 2026-05-10
- Last Updated: 2026-05-10
- Related Modules:
  - `src/kernel/sdk/facade.py`
  - `src/kernel/sdk/__init__.py`
  - `src/kernel/application/schema_runtime.py`
  - `src/kernel/application/protocol/` (new DTO target)
- Related Docs:
  - [Identity primary-key coordinate semantics](../../references/working/design-points/identity-primary-key-coordinate-semantics.zh.md)
  - [Historical n-ary Identity evolution](../../blueprint_history/从dims到n元Identity的设计演进.md)
- Parent Blueprint:
  - [2026-05-10_primary-identity-domain-semantics.md](../archive/2026-05-10_primary-identity-domain-semantics.md)
- Audit Log:
  - [2026-05-10_primary-anchor-domain-read.audit.md](./2026-05-10_primary-anchor-domain-read.audit.md)

## 1. Problem

The parent blueprint locks SDK-side `tx.entity(...).bind(...)` behavior so that
primary identity becomes a logical anchor at handle-creation time, while
non-primary identity becomes a coordinate dimension that can be completed by
`bind(...)`. The parent blueprint deliberately defers the *read* side: today
`fg.read.get(...)` requires a complete coordinate and returns
`EntitySnapshot | None`; there is no read-time API that takes only primary
identity and returns the set of coordinates that share it.

This blueprint explores whether to add a primary-only read API as a new SDK
capability, what its DTO shape should be, and how it relates (or does not
relate) to the runtime token `idref_v1`.

The key design tension: a primary-only read implies a *logical entity layer*
distinct from the *full coordinate layer*. The parent blueprint freezes
`idref_v1 = all identity fields` as an invariant. Any implementation here must
respect that invariant while still letting users navigate the
"primary anchor → domain coordinates" hierarchy on the read side.

## 2. Goals

- Decide whether to ship a primary-anchor read API at all.
- If yes, decide between `fg.read.domains(...)`, `fg.read.entity(...)`, or
  another shape — and exclude `get(...)` overload.
- Define the DTO returned by the new API — minimum fields, lookup helpers,
  empty/not-found semantics.
- Design the application-layer DTO + pure function FIRST per the
  application-first runtime authority precedent before touching the SDK shell.
- Preserve the parent blueprint's `idref_v1 = all identity fields` invariant
  unless a falsifier here proves it must change (which would re-open scope).

## 3. Non-goals

- No code implementation in this blueprint.
- No change to `fg.read.get(...)` return type or signature.
- No write-side primary-anchor API (the parent blueprint locks primary-only
  writes as forbidden).
- No introduction of a logical-entity ref token at runtime unless §5.E
  explicitly proves it is necessary.
- No package rename, no archived release snapshot modification, no sacred
  branch touches.

## 4. Current Context

- `sdk_get(...)` ([src/kernel/sdk/facade.py:379](../../src/kernel/sdk/facade.py:379))
  validates a complete identity coordinate (allowing literal defaults to be
  omitted) and returns one `EntitySnapshot` or None. It explicitly rejects
  uuid4 default_factory primary keys at read time.
- `sdk_find(...)` ([src/kernel/sdk/facade.py:439](../../src/kernel/sdk/facade.py:439))
  is currently all-or-nothing on identity filters; it cannot supply a
  primary-only filtering path today.
- `EntitySnapshot` ([src/kernel/sdk/facade.py:165](../../src/kernel/sdk/facade.py:165))
  carries one complete `idref_v1` and one set of identity / field values; it
  cannot honestly represent a primary-only collection.
- Application-layer schema runtime
  ([src/kernel/application/schema_runtime.py:355](../../src/kernel/application/schema_runtime.py:355))
  encodes refs from full identity coordinates only.
- The parent blueprint's [§6 invariant](../archive/2026-05-10_primary-identity-domain-semantics.md)
  freezes `idref_v1 = all identity fields` until explicit falsification.

## 5. Open Questions

This is a draft seed; the questions below need source-grounded falsifiers
before any of them locks. Each question is independent and can be advanced or
shelved on its own.

### 5.A Whether to ship at all

Question: is a primary-anchor read API worth adding to the public SDK
surface, or is `fg.read.find(...)` (extended to accept primary-only filters)
sufficient?

Falsifiers to run:

- Survey existing user-facing examples / notebooks / docs for any pattern that
  would benefit from "give me all coordinates with primary X" semantics.
- Check whether `find(...)` could be relaxed to accept primary-only filters
  without overloading its semantic contract.
- Confirm whether the parent blueprint's primary-anchor mental model already
  delivers enough value without a new read API.

**Decision (LOCKED 2026-05-10):**

Ship read-side primary-anchor lookup support, but do not add a new SDK
read namespace method or new DTO under this blueprint. The minimum public
shape is to relax `fg.read.find(...)` / `SDKStore.find(...)` so identity
filters may be partial, including primary-only filters.

Behavioral contract:

- `fg.read.get(...full identity...) -> EntitySnapshot | None` remains
  unchanged and continues to require a complete identity coordinate.
- `fg.read.find(User, user_id="u-1")` returns a list of complete
  `EntitySnapshot` coordinates whose recovered identity matches
  `user_id="u-1"`.
- `fg.read.find(User, user_id="u-1", locale="en")` remains valid and
  returns the matching coordinate list, normally 0 or 1.
- `fg.read.find(User)` with zero filters is unchanged by this decision; it
  follows the existing empty-filter `find(...)` behavior.
- Field filters and identity filters may be combined; all supplied filters
  must match.
- No match returns `[]`.
- `idref_v1` remains full-coordinate. No primary-only entity reference is
  introduced.

Rationale:

The application read path already has the substrate needed to enumerate
complete entity refs and hydrate snapshots. The current blocker is the SDK
`find(...)` all-or-nothing identity filter check, not storage capability.
No current docs/examples/tests demonstrate user demand strong enough to
justify a separate `fg.read.domains(...)` method or domain collection DTO
at this time. Extending `find` keeps the public shape small and preserves
the existing `get` contract.

Explicitly NOT decided in §5.A:

- Exact `find(...)` signature changes, keyword validation details, returned
  snapshot ordering, and performance characteristics for primary-only scans
  → §5.B / §5.F.
- A future `fg.read.domains(...)` / `fg.read.entity(...)` API.
- A new `EntityDomainSet` / primary-domain collection DTO.
- Any logical-entity-ref token.
- Any write-side primary-anchor operation.

### 5.B API surface and naming

Question: if shipped, should the API be `fg.read.domains(...)`,
`fg.read.entity(...)`, or another name?

Falsifiers to run:

- Audit current `fg.read.*` namespace ([src/kernel/sdk/facade.py](../../src/kernel/sdk/facade.py))
  for naming consistency.
- Compare the candidate names against the post-L SDK ergonomics redesign
  precedent (top-level client / nested namespaces / short names).
- Decide whether the API takes positional `entity_cls` + primary identity
  kwargs, or a single primary-identity dict.

**Decision (LOCKED 2026-05-10):**

The API surface remains `fg.read.find(...)` / `SDKStore.find(...)`. No new
method name is introduced under this blueprint.

Signature contract:

- Keep the existing call shape:

  ```python
  fg.read.find(EntityCls, *, view=None, limit=None, **filters)
  SDKStore.find(EntityCls, *, view=None, limit=None, **filters)
  ```

- `filters` may contain any declared identity field subset and/or declared
  data field filters.
- Unknown filter names remain errors.
- `fg.read.get(...)` remains the only single-coordinate read API and keeps
  its full-identity requirement.

Filter semantics:

- Identity filters are equality filters over recovered snapshot identity.
- Field filters keep the existing `find(...)` field-filter behavior.
- If both identity filters and field filters are supplied, all supplied
  filters must match.
- Full-identity filters may continue to use the existing direct get-backed
  path as an optimization, but this is not part of the public contract.
- Partial-identity filters use scan/filter semantics over complete
  coordinates.

Ordering / limit / performance contract:

- Return type remains `list[EntitySnapshot]`.
- For full-identity filters, snapshot ordering follows the existing
  `find(...)` enumeration behavior unchanged. For partial-identity
  filters, ordering is implementation-defined and stable within a single
  process; this blueprint does not introduce a new public sort guarantee.
- `limit` applies after all supplied filters match.
- No index or performance guarantee is introduced for primary-only scans.
  Any future indexed partial-identity lookup is an optimization, not a
  public behavior requirement.

Explicitly NOT decided in §5.B:

- Whether identity filtering is implemented entirely in SDK `facade.py` or
  moved into application-layer `EntityReadRequest` shape → §5.F.
- Any new method name such as `domains(...)` / `entity(...)`.
- Any new return DTO or helper method.

### 5.C DTO shape

Question: what minimum fields does the returned DTO need?

Candidate fields:

- The primary identity values that defined the query;
- A tuple / set of `EntitySnapshot` for each matching complete coordinate;
- An accessor method like `get(domain={...})` to look up one snapshot by
  non-primary identity values;
- Empty / not-found semantics (empty collection vs None vs explicit
  `NotFound` sentinel).

Falsifiers to run:

- Define a `EntityDomainSet` (or equivalent) skeleton in
  `kernel/application/protocol/` and check whether its fields can be derived
  cleanly from existing application substrate.
- Confirm `EntitySnapshot.ref` cannot honestly represent a primary-only anchor
  (already verified by parent blueprint).
- Decide whether the collection type is exported from `kernel.sdk.__all__`
  (per the [narrow public API feedback](../../../memory/feedback_narrow_public_api.md)).

**Decision (LOCKED 2026-05-10):**

No new DTO ships under this blueprint. The return shape for primary-anchor
read support is the existing `list[EntitySnapshot]` returned by
`fg.read.find(...)` / `SDKStore.find(...)`.

Return semantics:

- A primary-only or partial-identity `find(...)` query returns zero or more
  complete `EntitySnapshot` values.
- Each returned `EntitySnapshot` represents one complete full-coordinate
  entity snapshot, exactly as existing `find(...)` results do.
- Returned snapshots from partial-identity `find(...)` must expose the full
  recovered identity coordinate through `snapshot.identity`, including both
  primary and non-primary identity fields, so callers can distinguish
  domains. `snapshot.identity_available` must be `True` on these results,
  consistent with the existing `EntitySnapshot.identity` property contract
  that ties identity-kwargs trustworthiness to that flag.
- Empty result remains `[]`.
- No `EntityDomainSet`, no `NotFound` sentinel, no primary-anchor wrapper,
  and no exported DTO name are introduced.
- `kernel.sdk.__all__` is unchanged by this blueprint.

Rationale:

§5.A and §5.B select the existing `find(...)` surface instead of a new
domain-collection API. A new DTO would add public API shape without adding
new runtime information: the application read path already recovers full
identity coordinates during snapshot hydration, and the matching snapshots
themselves are the useful result.

Explicitly NOT decided in §5.C:

- Whether existing SDK snapshot hydration already exposes full identity for
  partial-identity `find(...)`, or implementation must populate
  `snapshot.identity` from recovered DTO refs → §5.F.
- Any future domain collection DTO shape.
- Any accessor such as `result.get(locale="en")` or
  `result.find(domain={...})` → §5.D will record the helper-method
  decision.
- Any SDK export change.

### 5.D Lookup-by-domain helper

Question: should the DTO offer a fluent helper to fetch one coordinate
snapshot from the collection without re-querying?

Falsifiers to run:

- Evaluate `result.get(locale="en")` vs `result.snapshots["en"]` vs
  `result.find(domain={"locale": "en"})`.
- Check whether the helper is idempotent and free of substrate access (so the
  DTO stays a pure value).

**Decision (LOCKED 2026-05-10):**

No lookup-by-domain helper ships under this blueprint. Because §5.C
chooses the existing `list[EntitySnapshot]` return shape instead of a
domain collection DTO, there is no result object on which to hang a
`get(...)`, `find(...)`, or `domain(...)` helper.

Behavioral contract:

- Callers receive a plain `list[EntitySnapshot]`.
- Callers select one coordinate by iterating/filtering the list using
  `snapshot.identity` and ordinary Python code.
- No lookup-by-domain helper method is added to `EntitySnapshot`.
- No helper method is added to `fg.read` beyond the §5.A / §5.B relaxed
  `find(...)` behavior.

Rationale:

Adding a helper without a collection DTO would require either mutating
`EntitySnapshot` into a collection-like object or adding another SDK method,
both of which contradict §5.A–§5.C. The useful information is already
available in the returned snapshots once §5.C identity visibility is
satisfied.

Explicitly NOT decided in §5.D:

- Any future convenience wrapper around a snapshot list.
- Any future domain collection helper such as `result.get(locale="en")`.

### 5.E Logical-entity-ref future

Question: does shipping this API commit the runtime to introducing a separate
`logical_entity_ref` token, or can the entire feature live as an SDK-side
projection over existing full-coordinate refs?

Falsifiers to run:

- Confirm that returning a collection of full-coordinate `EntitySnapshot`
  instances does NOT require a primary-only ref to exist at runtime.
- Verify that any aggregation / iteration helper can be implemented on top of
  the existing application substrate without minting a new ref kind.
- If a primary-only ref token IS required, immediately re-scope this blueprint
  and reopen the parent blueprint's §6 invariant.

**Decision (LOCKED 2026-05-10):**

No `logical_entity_ref` or primary-only ref token is required or introduced
under this blueprint. Primary-anchor read support is expressed entirely as
a query over existing full-coordinate entity refs, returning full-coordinate
`EntitySnapshot` values.

Rationale:

§5.A–§5.D select relaxed `find(...)` partial identity filtering, existing
`list[EntitySnapshot]` return shape, and ordinary Python filtering over
`snapshot.identity`. None of those choices require a runtime object that
represents "the logical entity behind all coordinates." The application
read path already enumerates full-coordinate refs and hydrates snapshots;
the SDK change can be modeled as filtering those complete coordinates.

Invariants:

- `idref_v1` remains the only entity ref encoding used at runtime.
- `EntitySnapshot.ref` continues to be a full-coordinate ref.
- No primary-only ref string, token, DTO field, or public SDK identifier is
  introduced.
- The parent blueprint's full-coordinate substrate invariant
  ([§6](../archive/2026-05-10_primary-identity-domain-semantics.md))
  remains closed and does not need to be reopened.

Explicitly NOT decided in §5.E:

- Any future logical-entity-ref design.
- Any storage/index layer that groups coordinates by primary identity.
- Any change to entity-ref encoding.

### 5.F Application-side selector design

Question: can the application layer materialize a partial-identity query
(primary-only) and produce an enumerable list of complete coordinates today,
or is a new query primitive needed?

Falsifiers to run:

- Inspect existing application selector resolution paths
  ([src/kernel/application/schema_runtime.py](../../src/kernel/application/schema_runtime.py))
  for partial-identity behavior.
- Determine whether ledger or projection scans can answer "all
  full-coordinate refs whose primary identity matches X" efficiently.
- If a new query primitive is needed, scope the application-side DTO + pure
  function FIRST, then surface via SDK shell (per
  [application-first runtime authority](../../../memory/project_application_first_runtime_authority.md)).

**Decision (LOCKED 2026-05-10):**

Implement partial-identity `find(...)` filtering in the SDK facade layer,
not by extending `EntityReadRequest` or application protocol DTOs.

Implementation contract:

- `sdk_find(...)` continues to split filters into identity filters and
  data-field filters.
- Unknown filter names remain SDK schema errors.
- Full-identity filters may keep the existing get-backed optimization.
- Partial-identity filters use the existing application `mode="find"` read
  path to enumerate hydrated full-coordinate snapshots, then apply
  identity-filter matching in SDK facade code.
- SDK snapshot hydration for partial-identity `find(...)` must populate
  `snapshot.identity` from the full recovered `EntitySnapshotDTO.ref.identity`
  and set `snapshot.identity_available=True`.
- Field filters continue to use existing SDK field-filter matching.

Why SDK facade and not application protocol:

The application protocol currently models `field_filters` only, and the
application read layer explicitly rejects identity fields in field filters.
Adding identity filters to `EntityReadRequest` would create new protocol
surface and DTO validation behavior. §5.A–§5.E deliberately choose a narrow
SDK-visible behavior change over new application DTO shape.

This is a deliberate, scope-bounded exception to the project's
application-first runtime authority precedent. The exception is justified
because partial-identity filtering does not introduce a new substrate
capability: the application layer already enumerates and hydrates full
coordinates via `mode="find"`. The SDK-layer filter is an ergonomic shell
over an existing capability, not a new capability. If a future use case
demonstrates a need for application-layer partial-identity reads (for
example, callers of `execute_read_request(...)` outside the SDK facade),
this decision should be revisited and a real application-protocol
extension scoped under a follow-up blueprint.

Explicitly NOT decided in §5.F:

- Any new application-layer `identity_filters` field.
- Any new pure application helper for partial identity reads.
- Any new index or storage-level acceleration.
- Any behavior change for `execute_read_request(...)` callers outside the
  SDK facade.

### 5.G Write-side parity (deferred)

Question: should there ever be a primary-anchor write API in the future
(e.g., "set field X on every domain of this primary anchor")?

Default answer: NO. The parent blueprint locks primary-only writes as
forbidden. This question is recorded only to prevent quiet drift; it is NOT
in scope for this blueprint.

Falsifiers to run:

- None at this stage. Re-open only if a future user request explicitly
  motivates it.

**Decision (LOCKED 2026-05-10):**

No primary-anchor write API ships under this blueprint. Write-side parity
with primary-anchor reads remains explicitly out of scope.

Behavioral contract:

- Parent blueprint behavior remains unchanged (per
  [parent §5.7 LOCKED](../archive/2026-05-10_primary-identity-domain-semantics.md)):
  entity/handle writes require a complete full identity coordinate.
- `fg.read.find(User, user_id="u-1")` may return all matching coordinate
  snapshots, but there is no corresponding write API that mutates all
  coordinates sharing `user_id="u-1"`.
- No "write to all domains", no "write to default domain", and no
  primary-anchor fan-out write behavior is introduced.
- Flat assertion-id retraction remains unaffected by this blueprint.

Rationale:

Read-side partial identity filtering is observational: it returns existing
full-coordinate snapshots. Write-side primary-anchor behavior would be
mutational across multiple coordinates and would require new conflict,
fan-out, ordering, and rollback semantics. Those semantics are not implied
by §5.A–§5.F and are not needed to ship the narrow read-side improvement.

Explicitly NOT decided in §5.G:

- Any future write-to-domain-set API.
- Any bulk write API over coordinates sharing a primary identity.
- Any default-domain write rule.

## 6. Boundaries And Invariants

Following the §5.A–§5.G LOCKED decisions, the following invariants govern
any scoped implementation of this spin-off blueprint.

**Substrate invariants:**

- `idref_v1` remains the only entity ref encoding used at runtime (per
  §5.E). No primary-only ref string, token, DTO field, or public SDK
  identifier is introduced.
- `EntitySnapshot.ref` continues to be a full-coordinate ref.
- The parent blueprint's full-coordinate substrate invariant is preserved
  and not reopened by this blueprint.

**SDK read-path invariants (`fg.read.find(...)` / `SDKStore.find(...)`):**

- Public surface remains the existing `find(...)` method; no new
  read-namespace method is introduced (per §5.A / §5.B).
- `find(...)` accepts partial identity filters (including primary-only),
  combined with optional field filters; all supplied filters must match.
- Unknown filter names remain SDK schema errors (existing safety
  preserved).
- Return type remains `list[EntitySnapshot]` (per §5.C); no new DTO,
  no `EntityDomainSet`, no `NotFound` sentinel, no primary-anchor wrapper.
- Returned snapshots from partial-identity `find(...)` expose the full
  recovered identity coordinate through `snapshot.identity`, with
  `snapshot.identity_available=True` (per §5.C).
- No lookup-by-domain helper method on `EntitySnapshot`, no new helper on
  `fg.read.*` (per §5.D).
- `kernel.sdk.__all__` is unchanged by this blueprint.
- `fg.read.get(...full identity...) -> EntitySnapshot | None` is unchanged.
- `sdk_get(...)` continues to require explicit primary identity; uuid4
  primary identity is not inferred at read time (parent §5.3 inheritance).
- For partial-identity filters, no public sort / ordering / performance
  guarantee is introduced (per §5.B).

**SDK write-path invariants (inherited from parent §5.7):**

- Entity/handle writes continue to require a complete full-coordinate
  identity.
- No "write to all domains", no "write to default domain", no
  primary-anchor fan-out write behavior is introduced (per §5.G).
- Flat assertion-id retraction (`fg.write.retract(asrt_id)`) remains
  unaffected.

**Application protocol invariants (per §5.F):**

- `EntityReadRequest` is not extended with identity filters; the existing
  application-layer rejection of identity fields in `field_filters` is
  preserved.
- Partial-identity matching is implemented entirely in the SDK facade
  layer. This is a deliberate, scope-bounded exception to the project's
  application-first runtime authority precedent, applied only to the
  ergonomic shell over the existing application `mode="find"` capability.
- `execute_read_request(...)` callers outside the SDK facade see no
  behavior change.
- Future use cases that demonstrate a need for application-layer
  partial-identity reads (for example, callers of
  `execute_read_request(...)` outside the SDK facade) would justify
  revisiting this exception under a follow-up blueprint.

**Rule authoring invariants (preserved, no behavior change):**

- No changes to `src/kernel/authoring/`; rule semantics remain governed by
  parent blueprint §5.8.

**Repository safety invariants:**

- Working notes under `docs/references/working/` are rationale inputs, not
  current implementation truth.
- Archived release snapshots remain immutable.
- Release and historical snapshot refs are not modified by this blueprint;
  any publish or release-branch operation remains separately authorized.
- The existing `v0.1.0-rc.1` tag and release artifacts are not rewritten
  by this blueprint.
- Parent blueprint's archived LOCKED decisions are inputs to this blueprint
  and must NOT be re-litigated here.

## 7. Acceptance

Acceptance is split into three groups: closed gates from §5 iterative
locking, scope-freeze gates that must pass before `draft → scoped`, and
implementation gates that must pass before any code change ships.

**Closed (§5 iterative gap pass, 2026-05-10):**

- [x] §5.A–§5.G have explicit LOCKED decisions recorded in the audit log.
- [x] §5.A locks "ship" via relaxed `find(...)` partial identity filters,
      not via a new SDK method or DTO.
- [x] §5.F records the deliberate, scope-bounded exception to
      application-first runtime authority.

**Scope-freeze gates (passed before `draft → scoped`, 2026-05-10):**

- [x] §6 invariants reviewed and consistent with §5.A–§5.G LOCKED
      decisions.
- [x] §7 acceptance reviewed and locked.
- [x] §8 implementation plan reviewed and locked.
- [x] Pre-scope-freeze docs/examples/notebooks scan completed: grep
      release-facing docs/examples for existing `find(...)` identity-filter
      examples that would need wording updates.
- [x] Any stale teaching found in the scan above is either updated or
      explicitly deferred to the implementation docs sync phase.
- [x] Parent/spin-off cross-references are self-evident in body text.

**Implementation gates (passed, 2026-05-10):**

- [x] No new SDK read method, no new DTO, no `kernel.sdk.__all__` change.
- [x] `fg.read.get(...full identity...)` behavior remains unchanged.
- [x] `fg.read.find(...)` accepts partial identity filters, including
      primary-only filters.
- [x] Unknown filter names still raise SDK schema errors.
- [x] Field filters and identity filters combine with AND semantics.
- [x] Partial-identity `find(...)` results expose full recovered identity
      via `snapshot.identity` and `snapshot.identity_available=True`.
- [x] Empty result remains `[]`; zero-filter `find(...)` behavior remains
      unchanged.
- [x] Partial-identity result ordering has no new public sort guarantee;
      `limit` applies after all supplied filters match.
- [x] No `EntityReadRequest` / application protocol extension; existing
      application rejection of identity fields in `field_filters` remains.
- [x] `execute_read_request(...)` callers outside the SDK facade see no
      behavior change.
- [x] No `idref_v1`, `EntitySnapshot.ref`, storage, index, or authoring-layer
      change.
- [x] No primary-anchor write API; complete-coordinate write requirement
      remains unchanged.
- [x] Affected SDK docs are updated in the same implementation cycle as
      the behavior change, not before §5 decisions are locked.
- [x] No archived release snapshot, existing `release/0.1.x` artifact, or
      `v0.1.0-rc.1` tag/release artifact is modified.

## 8. Implementation Plan

The §5 iterative gap pass is closed (2026-05-10). The remaining work
follows the phases below, gated by §7 scope-freeze gates and §7
implementation gates.

### Phase 0: Pre-scope-freeze (gated by §7 scope-freeze gates)

Complete all §7 scope-freeze gates before flipping blueprint status from
`draft` to `scoped`.

Non-trivial actions:

1. Pre-scope-freeze docs/examples/notebooks scan: grep release-facing
   docs/examples for existing `find(...)` identity-filter examples that
   imply all-or-nothing identity filters or otherwise conflict with
   partial-identity `find(...)`; record findings in audit log.
2. Confirm parent/spin-off cross-references are self-evident in body text.

After all §7 scope-freeze gates pass: flip blueprint status to `scoped`
and record the event in audit log.

### Phase 1: Test scaffolding (before code change)

Add behavior tests codifying the §5.A–§5.G LOCKED contracts. Tests should
fail on current code where behavior is not yet implemented and pass after
Phase 2 lands.

Coverage:

- Partial identity filters: `fg.read.find(User, user_id="u-1")` returns all
  matching full-coordinate snapshots.
- Full identity filters: existing exact-coordinate behavior remains valid.
- Combined identity + field filters use AND semantics.
- Unknown filter names still raise SDK schema errors.
- Empty result remains `[]`.
- Zero-filter `find(...)` behavior is unchanged.
- Partial-identity results expose full `snapshot.identity` and
  `snapshot.identity_available=True`.
- `fg.read.get(...)` behavior remains unchanged.
- No application protocol behavior change is observable outside SDK facade.

### Phase 2: Implementation (SDK facade only)

Scope: update SDK read ergonomics while preserving application protocol,
substrate, write path, and authoring behavior.

Critical files:

- `src/kernel/sdk/facade.py`: relax `sdk_find(...)` identity filter
  validation; implement partial-identity matching over hydrated snapshots;
  hydrate full recovered identity into SDK `EntitySnapshot` for
  partial-identity results.
- Tests added in Phase 1.

Implementation invariants:

- Do not extend `EntityReadRequest`.
- Do not modify `src/kernel/application/protocol/`,
  `src/kernel/application/entity_view.py`,
  `src/kernel/application/schema_runtime.py`, `src/kernel/authoring/`,
  storage/index code, or SDK public exports.
- Preserve full-identity get-backed optimization as an implementation
  detail where practical.
- Preserve field-filter behavior and unknown-filter validation.
- No feature flag, warning, deprecation path, or dual-mode behavior.

### Phase 3: Documentation sync (same cycle as Phase 2)

Update affected SDK docs in the same implementation cycle as the behavior
change:

- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- Working note:
  `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`
  only if the implementation changes the working explanation materially.

Docs should explain that `find(...)` may be used as a primary-anchor read
by supplying partial identity filters, while `get(...)` remains
full-coordinate only.

### Phase 4: Verification and close

1. Run focused tests for SDK read/find behavior.
2. Run the full kernel test suite; require green or record any pre-existing
   environment-only failure separately.
3. Verify every §7 implementation gate passes.
4. Confirm no diff under application protocol, application read runtime,
   authoring, substrate/storage/index, SDK public exports, or release refs.
5. Fill §10 Outcome / Deviations with final landed behavior and any
   deviations from this plan.
6. Add audit log entries for Phase 1 / Phase 2 / Phase 3 / Phase 4 events.
7. Flip blueprint status `scoped → implemented`.

## 9. Docs To Update

Only after decisions are locked AND the API ships:

- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`
  (extend §6.3 / §6.6 with primary-anchor read semantics if shipped)

## 10. Outcome / Deviations

Task completion section to fill after implementation, explicit research
closure, or shelve:

- Final landed decision: primary-anchor read support ships by relaxing
  existing `fg.read.find(...)` / `SDKStore.find(...)` identity filters.
  Partial identity filters, including primary-only filters, are accepted;
  no new read method, no new DTO, no helper, no logical-entity-ref, and no
  write-side parity API ship.
- Final landed behavior: `sdk_find(...)` keeps full-identity get-backed
  behavior where applicable and uses existing application `mode="find"`
  hydration plus SDK-facade identity filtering for partial identity filters.
  Partial-identity results expose full `snapshot.identity` with
  `snapshot.identity_available=True`. `get(...)`, zero-filter `find(...)`,
  unknown-filter errors, application `EntityReadRequest`, authoring,
  substrate refs, storage/index, SDK exports, and write behavior are
  unchanged.
- Deviations from draft: the seed application-first default was superseded
  by the §5.F scope-bounded SDK-facade exception. The stale-doc scan found
  `01_concepts.en.md` and `02_readwrite_and_ingest.en.md`, so Phase 3 docs
  sync updated those two files rather than the seed's initial
  `00_user_guide.en.md` / `02_readwrite_and_ingest.en.md` pair. Full
  kernel discovery still reports the pre-existing Problog cold-import
  circularity; the focused SDK/application suites pass.
- Deferred design questions: any future `fg.read.domains(...)` /
  `fg.read.entity(...)`, `EntityDomainSet`, lookup helper,
  logical-entity-ref, application-protocol identity filters, indexed
  partial-identity reads, or primary-anchor write API require follow-up
  blueprint work.
- Archive notes: implemented locally; archive move remains a separate
  follow-up if desired.
