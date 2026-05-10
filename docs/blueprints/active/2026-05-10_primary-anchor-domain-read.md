# Task Blueprint: Primary-Anchor Domain Read

- Status: draft
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
  - [2026-05-10_primary-identity-domain-semantics.md](./2026-05-10_primary-identity-domain-semantics.md)
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
- The parent blueprint's [§6 invariant](./2026-05-10_primary-identity-domain-semantics.md)
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

### 5.D Lookup-by-domain helper

Question: should the DTO offer a fluent helper to fetch one coordinate
snapshot from the collection without re-querying?

Falsifiers to run:

- Evaluate `result.get(locale="en")` vs `result.snapshots["en"]` vs
  `result.find(domain={"locale": "en"})`.
- Check whether the helper is idempotent and free of substrate access (so the
  DTO stays a pure value).

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

### 5.G Write-side parity (deferred)

Question: should there ever be a primary-anchor write API in the future
(e.g., "set field X on every domain of this primary anchor")?

Default answer: NO. The parent blueprint locks primary-only writes as
forbidden. This question is recorded only to prevent quiet drift; it is NOT
in scope for this blueprint.

Falsifiers to run:

- None at this stage. Re-open only if a future user request explicitly
  motivates it.

## 6. Boundaries And Invariants

- `idref_v1` continues to encode all identity fields; this blueprint does not
  introduce a primary-only ref unless §5.E explicitly forces it (which would
  trigger immediate re-scoping).
- `fg.read.get(...full identity...) -> EntitySnapshot | None` is unchanged.
- `EntitySnapshot` continues to represent one complete coordinate.
- Primary-only writes remain forbidden (locked by parent blueprint).
- Working notes under `docs/references/working/` are rationale inputs, not
  current implementation truth.
- Archived release snapshots remain immutable.
- Parent blueprint's locked §5.1-§5.4 / §5.7-§5.9 decisions are inputs to
  this blueprint and must NOT be re-litigated here.

## 7. Acceptance

- [ ] §5.A-§5.G questions have explicit decisions or documented deferrals.
- [ ] If §5.A locks "ship", §5.B / §5.C / §5.D produce a concrete DTO + API
      design that respects parent blueprint invariants.
- [ ] If §5.A locks "do not ship", the blueprint is closed with a clear
      rationale and archived.
- [ ] Application-layer DTO + pure function design is finalized BEFORE any
      SDK shell sketch.
- [ ] Tests for the new API (if scoped) cover empty / single-coordinate /
      multi-coordinate cases plus the lookup-by-domain helper.
- [ ] No archived release snapshots or sacred branches are modified.
- [ ] Parent blueprint's archived locked decisions are preserved verbatim.

## 8. Implementation Plan

Draft-stage plan only:

1. Run §5.A "ship-or-not" assessment first; if it shelves the blueprint,
   stop here.
2. If shipping, run §5.E "logical-entity-ref" check before any DTO design;
   a positive result re-scopes this blueprint immediately.
3. Run §5.F application-side feasibility before §5.B / §5.C / §5.D SDK
   shell design.
4. Lock §5.B / §5.C / §5.D in iterative gap cadence (one at a time + audit).
5. Scope-freeze only after every §5.x question has a locked decision.
6. If implementation is approved later, design application-layer DTO + pure
   function FIRST, then SDK shell, then tests, then docs.

## 9. Docs To Update

Only after decisions are locked AND the API ships:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`
  (extend §6.3 / §6.6 with primary-anchor read semantics if shipped)

## 10. Outcome / Deviations

Task completion section to fill after implementation, explicit research
closure, or shelve:

- Final landed decision:
- Final landed behavior:
- Deviations from draft:
- Deferred design questions:
- Archive notes:
