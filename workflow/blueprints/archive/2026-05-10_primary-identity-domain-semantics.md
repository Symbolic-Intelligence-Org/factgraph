# Task Blueprint: Primary Identity / Domain Semantics

- Status: implemented
- Created: 2026-05-10
- Last Updated: 2026-05-10
- Related Modules:
  - `src/kernel/sdk/schema.py`
  - `src/kernel/sdk/batch.py`
  - `src/kernel/sdk/facade.py`
  - `src/kernel/application/schema_runtime.py`
  - `src/kernel/authoring/derivation_compile.py`
  - `src/kernel/authoring/where_schema_lowering.py`
- Related Docs:
  - [Identity primary-key coordinate semantics](../../references/working/design-points/identity-primary-key-coordinate-semantics.zh.md)
  - [Historical n-ary Identity evolution](../../blueprint_history/从dims到n元Identity的设计演进.md)
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-05-10_primary-identity-domain-semantics.audit.md](./2026-05-10_primary-identity-domain-semantics.audit.md)

## 1. Problem

Current runtime behavior encodes every declared `Identity` field into the
stable `idref_v1` entity reference. `primary_key=True` is already meaningful
in schema validation and rule authoring, especially for cross-coordinate
comparisons and field-head lowering, but it has weak direct significance in
SDK read/write ergonomics.

This creates a documentation and design tension:

- The storage/runtime coordinate is complete identity based.
- The user-facing model wants to distinguish a logical primary anchor from
  non-primary domain or coordinate dimensions.
- Current batch partial binding allows identity fields to be supplied in any
  order, so `tx.entity(User, locale="en").bind(user_id="u-1")` is currently
  possible even when `user_id` is the primary identity.
- Current read APIs require complete identity for `get(...)` and do not expose
  a primary-anchor domain collection view.

This blueprint explores whether SDK read/write should expose a clearer
primary-anchor layer plus full-coordinate domain layer while preserving the
current `idref_v1 = all identity fields` implementation unless explicitly
disproven.

## 2. Goals

- Evaluate primary-first completion for `tx.entity(...).bind(...)`.
- Evaluate whether read APIs should add a primary-anchor/domain collection
  layer.
- Preserve current `idref_v1 = all identity fields` unless a later falsifier
  proves a storage-level change is required.
- Keep `get(...full identity...) -> EntitySnapshot | None` stable unless a
  later falsifier explicitly justifies changing it.
- Clarify the public distinction between primary identity anchor, non-primary
  identity coordinate dimensions, and mutable `Field(...)` facts.

## 3. Non-goals

- No immediate code implementation.
- No package rename.
- No storage rewrite.
- No change to archived release snapshots or historical Path B refs.
- No broad user-doc rewrite until design decisions are locked.
- No migration of working reference material into current truth until the
  blueprint reaches scoped or implemented status.

## 4. Current Context

- `Identity(...)` and `Field(...)` descriptors are defined in
  `src/kernel/sdk/schema.py`; entity metadata separates `identity_fields` from
  mutable fields and currently requires at least one `Identity(primary_key=True)`.
- `SDKStore.ref(...)` and application schema runtime materialize all identity
  fields into `idref_v1`; primary fields do not form a separate runtime ref.
- `SDKBatchTx.entity(...)` and `ManagedEntityHandle.bind(...)` currently accept
  identity fields in any order and resolve a handle only when all identity
  fields are materialized.
- `sdk_get(...)` currently validates complete identity, allowing only literal
  defaults to be omitted; it returns a single `EntitySnapshot`.
- `sdk_find(...)` currently requires all identity filters when any identity
  filter is supplied.
- Rule authoring already treats primary identity fields specially:
  cross-coordinate attr comparison is limited to primary-key identity fields,
  and field heads carry primary identity implicitly from where-bound entities.
- The working design note under `docs/references/working/design-points/`
  captures the current interpretation but is not authoritative current
  implementation truth.

## 5. Proposed Shape

The recommended starting hypothesis is:

1. **Primary-first completion first.** `tx.entity(...)` should require all
   primary identity fields to be present or materializable at initial handle
   creation. `bind(...)` may complete non-primary identity dimensions before
   any operation.
2. **Domain collection read later.** A primary-only read should be considered
   as an explicit API such as `fg.read.domains(...)` or `fg.read.entity(...)`,
   not by overloading `fg.read.get(...)`.
3. **No `get(...)` return-type overload.** Full-coordinate `get(...)` should
   continue returning `EntitySnapshot | None`.
4. **No storage ref split by default.** The runtime token remains the full
   coordinate `idref_v1`; any primary-anchor abstraction is SDK-facing unless
   falsifiers prove otherwise.

### 5.1 Primary-First Completion

Question: should `tx.entity(User, user_id=...)` be allowed while
`tx.entity(User, locale=...)` is rejected when `user_id` is primary?

Falsifiers to run:

- Search tests and examples for reverse-order partial binding.
- Verify batch internals can reject missing primary fields without changing
  complete-coordinate writes.
- Confirm the change improves the documented meaning of `primary_key=True`
  without implying a primary-only entity reference exists.

**Decision (LOCKED 2026-05-10):**

`tx.entity(...)` must be anchored by primary identity at handle creation.
A handle may not be created from non-primary identity fields alone. In the
single-primary, no-default baseline case, this means
`tx.entity(User, user_id="u-1")` is allowed while
`tx.entity(User, locale="en")` is rejected when `user_id` is primary.

This decision locks the direction of **primary-first completion** without
yet locking the exact completeness rule for multi-primary entities or
primary identity defaults. Those are delegated to §5.2 and §5.3.

Behavioral contract:

- **Allowed baseline**: `tx.entity(User, user_id="u-1")` when `user_id` is
  the only non-default primary identity field; the resulting handle may
  complete `locale` (or any non-primary identity) via `bind(...)` later.
- **Rejected baseline**: `tx.entity(User, locale="en")` when `user_id` is
  primary and absent.
- The rejection lives at the SDK ergonomics layer only. The runtime
  substrate continues to encode `idref_v1` from the full identity coordinate.
  **No primary-only entity reference is introduced** by this decision.

Error message contract:

- Entity creation errors must name the missing primary identity fields and
  say that primary identity must be provided at `entity(...)` time.
- Commit / preview / write errors for incomplete full coordinates keep the
  existing `_ensure_handle_resolved` shape and continue to instruct users to
  complete missing identity via `handle.bind(...)`.

Explicitly NOT decided in §5.1 (delegated):

- Whether `Identity(primary_key=True, default=...)` or
  `default_factory="uuid4"` count as "present" for primary-presence check →
  §5.3.
- Whether multi-primary entities require all primary identity fields at one
  call vs allow partial-primary upfront → §5.2.
- Whether `bind(...)` retains mutating semantics or gains a branching
  `domain(...)` form → §5.4.
- Any read-side primary-anchor / domain collection API → spin-off blueprint
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).
- Any change to `idref_v1` substrate encoding → out of scope under §6
  invariant; reopening requires explicit invariant change.

### 5.2 Multi-Primary Rule

Question: must all primary identity fields be present at initial
`tx.entity(...)` creation?

Falsifiers to run:

- Build a multi-primary fixture and check current partial-binding behavior.
- Decide whether accepting only some primary fields creates an incoherent
  primary anchor.
- Confirm error paths and messages can name missing primary identity fields.

**Decision (LOCKED 2026-05-10):**

For entities with more than one `Identity(primary_key=True)` field, all
primary identity fields must be present at the initial `tx.entity(...)`
call. Partial-primary handles cannot be created; `bind(...)` may not be
used to complete a missing primary identity field.

Rationale: a primary anchor is a complete anchor, not a fragment that can
be assembled by progressive `bind(...)` calls. Allowing
`tx.entity(AccountUser, tenant_id="t-1").bind(user_id="u-1")` would
introduce an intermediate handle whose primary anchor is undefined,
contradicting the §5.1 rule that handles must be anchored by primary
identity at handle creation.

Behavioral contract:

- **Allowed**: `tx.entity(AccountUser, tenant_id="t-1", user_id="u-1")`
  when both `tenant_id` and `user_id` are primary identity fields; the
  resulting handle may complete any non-primary identity (e.g., `locale`)
  via `bind(...)` later.
- **Rejected**: `tx.entity(AccountUser, tenant_id="t-1").bind(user_id="u-1")`
  when both `tenant_id` and `user_id` are primary identity fields —
  `entity(...)` raises immediately because `user_id` is missing primary;
  `bind(...)` never executes.
- A single missing primary field and multiple missing primary fields follow
  the same SDK error path; the error names every missing primary identity
  field.

Error message contract:

- Entity creation errors must list every missing primary identity field by
  name in the error message.
- Multi-primary entities use the same SDK error path as single-primary
  entities; the count of missing primary fields does not change the error
  class.
- Exact string format remains unlocked; only the semantic contract above
  is binding.

Explicitly NOT decided in §5.2 (delegated):

- Whether `Identity(primary_key=True, default=...)` or
  `default_factory="uuid4"` count as "present" for the multi-primary
  upfront check → §5.3.

### 5.3 Primary Defaults

Question: do primary identity `default` / `default_factory` values count as
present, or must primary identity be explicit?

Falsifiers to run:

- Inspect `Identity.default` and `default_factory="uuid4"` usage across tests
  and docs.
- Decide whether generated primary identity values are acceptable for a
  primary anchor, or whether explicitness is required for user control.
- Confirm this decision does not accidentally make `tx.entity(User)` create a
  meaningful anchor when the user did not supply one.

**Decision (LOCKED 2026-05-10):**

For the §5.1 / §5.2 primary-presence check at `tx.entity(...)` handle
creation, primary identity is considered "present" under the following
rules:

- `Identity(primary_key=True, default=<literal>)` counts as present; the
  literal default is materialized at handle creation.
- `Identity(primary_key=True, default_factory="uuid4")` counts as present
  only because `tx.entity(...)` materializes the factory into a concrete
  value at handle creation; the materialized value is stored on the handle.
- `Identity(primary_key=True)` with no `default` and no `default_factory`
  must receive an explicit value at the `tx.entity(...)` call.

Semantic boundary — create vs query:

Create-side default materialization is **not** symmetric with query-side
identity inference. The fact that `tx.entity(Session)` can produce a
materialized primary anchor for
`Session.sid: Identity(primary_key=True, default_factory="uuid4")` does
**not** make `fg.read.get(Session)` or `fg.read.get(User, missing_uuid_pk)`
legal:

- Create side: the factory generates a value, the handle holds it, and
  every subsequent operation references the materialized primary anchor.
- Read / query side: the existing `sdk_get(...)` rejection of uuid4 primary
  identity (and any other unfilled primary identity) is preserved. A query
  must supply an explicit primary identity value because the reader does
  not know which existing entity is being requested.

Behavioral examples:

- **Allowed at entity creation**:

  ```python
  from uuid import UUID

  class Session(Entity):
      sid: UUID = Identity(primary_key=True, default_factory="uuid4")
  tx.entity(Session)  # handle materialized with a generated sid
  ```

- **Rejected at entity creation**:

  ```python
  class User(Entity):
      user_id: str = Identity(primary_key=True)
  tx.entity(User)  # missing primary; no default available
  ```

- **Rejected at read** (unchanged from current behavior):

  ```python
  fg.read.get(Session)              # uuid4 primary not supplied
  fg.read.get(User)                 # no default available
  fg.read.get(User, locale="en")    # primary not supplied
  ```

Explicitly NOT decided in §5.3 (delegated):

- Whether `bind(...)` retains mutating semantics or gains a branching
  `domain(...)` form for non-primary identity → §5.4.
- Any read-side primary-anchor / domain collection API → spin-off blueprint
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).
- Any change to read-side identity inference for query APIs (e.g., letting
  `sdk_get(...)` infer uuid4 primary identity) → out of scope; current
  rejection is preserved.

### 5.4 Bind Semantics

Question: does `bind(...)` remain mutating completion, or should a future API
support branching domain handles?

Falsifiers to run:

- Verify current `bind(...)` mutates a handle in place.
- Decide whether the minimal primary-first change should preserve mutating
  completion semantics.
- If branching is desired, evaluate a separate API such as
  `handle.domain(...)` rather than changing `bind(...)` silently.

**Decision (LOCKED 2026-05-10):**

`bind(...)` remains a mutating in-place identity completion mechanism on
the existing `ManagedEntityHandle`. It does not return a new handle, does
not branch into multiple coordinate handles, and does not introduce a
parent/child handle relationship.

Scope of `bind(...)`:

- May complete any **non-primary** `Identity(...)` field that was not
  supplied at `tx.entity(...)` time.
- May NOT add a missing primary identity field or alter an existing primary
  identity field (per §5.1 / §5.2 input constraints below).
- May NOT create a new handle. The existing handle is mutated; the same
  Python object is returned for fluent chaining.

Input constraints from §5.1 / §5.2 / §5.3 (not re-litigated here):

- Primary identity is established at `tx.entity(...)` time, before any
  `bind(...)` call. (§5.1)
- For multi-primary entities, all primary identity fields are present
  upfront. (§5.2)
- `default` / `default_factory="uuid4"` materialize primary identity at
  handle creation; they do not let primary identity be deferred to
  `bind(...)`. (§5.3)

Rejected within the parent blueprint scope:

- A branching `handle.domain(non_primary_id="...")` API that produces a
  new child handle from the same primary anchor.
- A branching variant of `bind(...)` that returns a new handle rather than
  mutating in place.
- A "logical entity" handle that fans out into multiple coordinate handles
  via a fluent API.

These rejections are about scope, not correctness. A branching
`handle.domain(...)` form does not necessarily require any change to
`idref_v1` — it could exist purely as an SDK-layer handle factory over
existing full-coordinate refs. The reason to defer is that it introduces
a new handle lifecycle and multi-coordinate fork semantics, with its own
return types, ownership rules, and test surface, all of which are outside
the primary-first completion minimum scope of this blueprint.

Explicitly NOT decided in §5.4 (delegated):

- Branching / domain-handle / fan-out designs belong to the spin-off
  blueprint
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md)
  or a later follow-up blueprint, not this one.
- Whether the long-term direction prefers fluent branching
  (`handle.domain(...)`) vs an entity-level read collection
  (`fg.read.domains(...)`) vs both → spin-off blueprint.

### 5.5 Read Layer

Question: should primary-only read be a new method such as
`fg.read.domains(...)` rather than overloading `fg.read.get(...)`?

Falsifiers to run:

- Confirm `get(...)` currently means single complete-coordinate lookup.
- Evaluate whether overloading `get(...)` would create unstable return types.
- Determine whether existing `find(...)` can supply the domain collection
  implementation or whether a lower-level query helper is needed.

**Deferred (2026-05-10):**

Primary-anchor/domain read API design is split into
[2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).
This parent blueprint keeps only the primary-first write/handle completion
scope.

### 5.6 Return Type

Question: if primary-domain read ships, should it define a new collection type
rather than returning `EntitySnapshot`?

Falsifiers to run:

- Define the minimum fields a domain collection needs: primary identity,
  coordinate snapshots, lookup-by-domain helper, and empty/not-found semantics.
- Confirm `EntitySnapshot.ref` cannot honestly represent a primary-only anchor.
- Decide whether the collection type is exported from `kernel.sdk`.

**Deferred (2026-05-10):**

Domain collection return-type design is split into
[2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).
This parent blueprint does not define a new read DTO.

### 5.7 Write Layer

Question: should primary-only writes remain forbidden unless a full coordinate
is selected?

Falsifiers to run:

- Evaluate ambiguous write semantics: write to all domains, default domain, or
  reject until full coordinate.
- Check whether existing batch handle completion is the safest public model.
- Confirm error messages teach the difference between primary anchor and full
  coordinate.

**Decision (LOCKED 2026-05-10):**

Primary-only writes are rejected. Any entity/handle write-side operation
(`set`, `add`, `edit`, `preview`, `commit`, and handle-scoped field
retraction) requires a handle whose identity coordinate is complete: every
primary identity field plus every non-primary `Identity(...)` field must
be materialized.

Write semantics:

- A handle that has primary identity but not all non-primary identity
  fields must complete via `bind(...)` before any write-side operation.
- The runtime substrate writes under one full-coordinate `idref_v1`;
  there is no concept of "write to all domains" and no concept of
  "write to a default domain" that fans out across multiple coordinates.

Rejected alternatives (within parent blueprint scope):

- Writing to "all domains of a primary anchor" (e.g., setting a field for
  every coordinate sharing the same primary identity).
- Writing to a "default domain" of a primary anchor when non-primary
  identity is omitted.
- Implicit non-primary materialization at write time (e.g., picking the
  first matching coordinate).

These alternatives introduce ambiguous write semantics across multiple
coordinates and would couple write behavior to read-side query
infrastructure that this blueprint does not introduce.

Error path on incomplete coordinate at write time:

- Existing `_ensure_handle_resolved` rejection shape is preserved (per the
  §5.1 commit-time error contract): the error names every still-missing
  identity field and instructs the user to complete via `bind(...)`.
- By construction, primary identity is already explicit or materialized at
  handle creation (per §5.1 / §5.2 / §5.3), so any incompleteness at write
  time is a non-primary completion gap.

Explicitly NOT decided in §5.7 (delegated):

- Any future write-to-domain-set API (e.g., "set field X on all
  coordinates of primary Y") → spin-off blueprint
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md)
  §5.G (currently recorded there as DEFAULT NO and OUT-OF-SCOPE).
- Error message wording refinements at write time → covered by §5.1
  commit-time error contract; no further refinement here.
- Flat assertion-id retraction (`fg.write.retract(asrt_id)`) is not an
  entity/handle write operation and is unaffected by this decision.

### 5.8 Rule Alignment

Question: is the SDK-facing primary/domain model consistent with current
rule semantics?

Falsifiers to run:

- Verify cross-coordinate comparison continues to rely on primary-key identity
  fields only.
- Verify field-head lowering still treats primary identity as implicit and
  non-primary identity as required for coordinate disambiguation.
- Confirm any new terminology does not contradict historical n-ary Identity
  design.

**Decision (LOCKED 2026-05-10):**

The primary-first SDK handle model locked by §5.1–§5.4 / §5.7 is aligned
with the rule authoring layer's existing primary-key special status. No
rule-layer behavior is introduced, modified, or relaxed by this blueprint.

Confirmed alignment points:

- **Cross-coordinate attribute comparison** in rule `where` clauses
  continues to be restricted to primary-key identity fields. Compile-time
  enforcement currently lives in `_rewrite_attr_eq_atom`
  (`src/kernel/authoring/where_schema_lowering.py`, observed around lines
  217-291), which raises when the compared field is not declared
  `primary_key=True`.
- **Field head primary identity carry**: in derivation field heads,
  primary identity continues to be implicit from the where-bound entity
  variable, while non-primary identity continues to be explicitly required
  (and validated against the bound coordinate). Compile-time enforcement
  currently lives in `_lower_entity_head_with_schema`
  (`src/kernel/authoring/derivation_compile.py`, observed around lines
  243-293), which rejects head kwargs containing primary identity fields.
- **Where-bound entity binding** (e.g., `User(u)` in a where clause)
  continues to bind a full identity coordinate (full `idref_v1`); the
  SDK's primary-first handle model does not change the rule-layer
  interpretation of entity variable binding.

What this blueprint does NOT introduce:

- No new rule-layer terminology, no new compile-time check, no new
  authoring DSL form, no new field-head lowering rule.
- No relaxation of existing rule-layer enforcement — primary-key
  cross-coordinate comparison and field-head implicit/explicit identity
  rules remain compile-time enforced.
- No changes to `src/kernel/authoring/derivation_compile.py`,
  `src/kernel/authoring/where_schema_lowering.py`, or any other authoring
  module under `src/kernel/authoring/`.

Why §5.8 is a status-only LOCKED:

The rule layer already treats `primary_key=True` as the special anchor for
cross-coordinate joins and field-head implicit identity carry. The SDK
ergonomics gap closed by §5.1–§5.4 / §5.7 is precisely about giving the
SDK handle model the same primary-anchor treatment that the rule layer
already enforces. Once §5.1–§5.4 / §5.7 are locked, alignment is by
construction; this section records the alignment as fact and confirms no
follow-up rule-layer work is required.

Explicitly NOT decided in §5.8 (delegated):

- Any future rule-layer extension that would touch primary/non-primary
  identity semantics → out of scope; would require its own blueprint.

### 5.9 Compatibility

Question: what breaks if primary-first completion becomes enforced?

Falsifiers to run:

- Search tests, docs, examples, notebooks, and archived demos for reverse-order
  binding or partial identity reads.
- Run a narrow compatibility suite before any implementation.
- Decide whether the change requires a compatibility note or a staged warning.

**Decision (LOCKED 2026-05-10):**

Primary-first completion as locked by §5.1–§5.4 / §5.7 has no observed
breakage in the current test surface and is scoped for direct enforcement
(no staged warning, no deprecation period), subject to the pre-scope-freeze
docs/examples/notebooks scan below.

Compatibility findings:

- **Tests**: No existing tests under `src/kernel/tests/` exercise
  reverse-order partial binding (e.g., `tx.entity(User, locale="en")` then
  `bind(user_id=...)` when `user_id` is primary). All observed test
  patterns place primary identity at `tx.entity(...)` time; the
  enforcement does not break any existing test.
- **Docs / examples / notebooks**: Compatibility closure is not complete
  until the pre-scope-freeze scan below passes. Any live user-facing
  reverse-order binding example must be updated or the decision re-opened.
- **Public SDK surface**: This decision adds no exported names and removes
  no exported names. It tightens validation for an undocumented
  reverse-order partial-binding path rather than changing the named SDK
  surface.

Pre-scope-freeze checklist (falsifier closure):

- Grep `examples/`, `notebooks/`, `docs/`, and `src/kernel/sdk/docs/` for
  any pattern that creates a `ManagedEntityHandle` from non-primary
  identity then binds primary later. If found: each instance must be
  updated to primary-first form before scope-freeze.
- Confirm no published rc.1 user-facing documentation teaches reverse-
  order binding as the recommended pattern.

Implementation strategy locked:

- **Direct enforcement at `tx.entity(...)` boundary**, not behind a
  feature flag, not behind a deprecation warning.
- Single error path (per §5.1 entity-creation contract) at the call site
  where the missing primary identity is detected.
- No `__future__`-style opt-in; no dual-mode coexistence.

Explicitly NOT decided in §5.9 (delegated):

- Any future relaxation that would re-enable reverse-order binding (e.g.,
  for a special "draft handle" mode) → out of scope; would require its
  own blueprint that re-litigates §5.1.
- Behavior under `factpy-kernel` consumers that pin to pre-rc.1 commits
  → out of scope; rc.1 is the published baseline.

## 6. Boundaries And Invariants

Following the §5.1–§5.4 / §5.7 / §5.8 / §5.9 LOCKED decisions, the
following invariants govern any scoped implementation of this blueprint.

**Substrate invariants:**

- `idref_v1` encodes the full identity coordinate (primary + non-primary
  identity fields). This blueprint does NOT introduce a primary-only
  entity reference at runtime.
- `EntitySnapshot` represents one complete coordinate, not a primary-only
  domain collection.

**SDK ergonomics invariants (`tx.entity(...)` / `bind(...)` / write path):**

- `tx.entity(...)` requires primary identity at handle creation; partial
  primary handles cannot be created (§5.1, §5.2).
- `Identity(primary_key=True, default=...)` and
  `Identity(primary_key=True, default_factory="uuid4")` count as present
  for the primary-presence check by virtue of materialization at handle
  creation (§5.3).
- `bind(...)` remains a mutating in-place identity completion mechanism;
  it may complete non-primary identity only and may not add or alter
  primary identity (§5.4).
- Entity/handle write-side operations (`set`, `add`, `edit`, `preview`,
  `commit`, and handle-scoped field retraction) require a complete
  coordinate; primary-only writes are rejected (§5.7).
- Flat assertion-id retraction (`fg.write.retract(asrt_id)`) is not an
  entity/handle write and is unaffected (§5.7 delegation).

**Read path invariants:**

- `fg.read.get(...full identity...) -> EntitySnapshot | None` is unchanged.
- `sdk_get(...)` continues to require explicit primary identity; uuid4
  primary identity is not inferred at read time (§5.3 semantic boundary).
- `sdk_find(...)` all-or-nothing identity filter behavior is unchanged by
  this blueprint.
- Any primary-anchor / domain collection read API design is owned by the
  spin-off blueprint
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md),
  not this blueprint (§5.5 / §5.6 DEFERRED).

**Rule authoring invariants (preserved, no behavior change):**

- Cross-coordinate attribute comparison in `where` clauses remains
  restricted to primary-key identity fields (compile-time enforcement at
  `_rewrite_attr_eq_atom`).
- Derivation field heads continue to carry primary identity implicitly
  from the where-bound entity variable; non-primary identity remains
  explicitly required (compile-time enforcement at
  `_lower_entity_head_with_schema`).
- `User(u)` in a where clause continues to bind a full identity
  coordinate.
- No changes to `src/kernel/authoring/` (§5.8).

**Repository safety invariants:**

- Working notes under `docs/references/working/` are rationale inputs,
  not current implementation truth.
- Archived release snapshots remain immutable.
- Release and historical snapshot refs are not modified by this blueprint;
  any publish or release-branch operation remains separately authorized.
- The existing `v0.1.0-rc.1` tag and release artifacts are not rewritten
  by this blueprint.

## 7. Acceptance

Acceptance is split into three groups: closed gates from §5 iterative
locking, scope-freeze gates that must pass before `draft → scoped`, and
implementation gates that must pass before any code change ships.

**Closed (§5 iterative gap pass, 2026-05-10):**

- [x] §5.1–§5.4 / §5.7 / §5.8 / §5.9 have explicit LOCKED decisions
      recorded in the audit log.
- [x] §5.5 / §5.6 have explicit DEFERRED decisions pointing to the
      spin-off blueprint
      [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).

**Scope-freeze gates (passed before `draft → scoped`, 2026-05-10):**

- [x] §6 invariants reviewed and consistent with §5.1–§5.9 LOCKED
      decisions.
- [x] §7 acceptance reviewed and locked.
- [x] §8 implementation plan reviewed and locked.
- [x] Pre-scope-freeze docs/examples/notebooks scan completed: grep
      `examples/`, `notebooks/`, `docs/`, `src/kernel/sdk/docs/` for any
      reverse-order partial-binding teaching pattern; record findings.
- [x] Any reverse-order binding example found in the scan above is either
      updated to primary-first form or the §5.1 decision is explicitly
      re-opened.
- [x] Parent blueprint and spin-off blueprint cross-references are
      self-evident in body text (no audit-log dependency for readers).

**Implementation gates (passed, 2026-05-10):**

- [x] Any scoped implementation preserves full-coordinate `idref_v1`
      (per §6 substrate invariants).
- [x] Tests cover allowed and rejected `tx.entity(...)` orders for
      single-primary entities (per §5.1).
- [x] Tests cover multi-primary upfront requirements (per §5.2).
- [x] Tests cover primary-presence semantics for `default=<literal>`,
      `default_factory="uuid4"`, and no-default primary identity
      (per §5.3); existing `sdk_get(...)` uuid4 rejection remains intact.
- [x] Tests cover `bind(...)` rejecting primary identity completion and
      accepting non-primary identity completion (per §5.4).
- [x] Tests cover write-side rejection on incomplete coordinates and
      confirm flat assertion-id retraction is unaffected (per §5.7).
- [x] No diff under `src/kernel/authoring/` (per §5.8).
- [x] Direct enforcement at the `tx.entity(...)` boundary; no feature
      flag, no deprecation warning, no `__future__`-style opt-in
      (per §5.9 implementation strategy).
- [x] Full-coordinate `fg.read.get(...)` behavior is unchanged.
- [x] Affected SDK docs are updated in the same implementation cycle as
      the behavior change, not before §5 decisions are locked.
- [x] No archived release snapshot, existing `release/0.1.x` artifact, or
      `v0.1.0-rc.1` tag/release artifact is modified.

## 8. Implementation Plan

The §5 iterative gap pass is closed (2026-05-10). The remaining work
follows the five phases below, gated by §7 scope-freeze gates and §7
implementation gates.

### Phase 0: Pre-scope-freeze (gated by §7 scope-freeze gates)

Complete all §7 scope-freeze gates before flipping blueprint status from
`draft` to `scoped`. The two non-trivial actions are:

1. Pre-scope-freeze docs/examples/notebooks scan: grep `examples/`,
   `notebooks/`, `docs/`, `src/kernel/sdk/docs/` for reverse-order
   partial-binding teaching patterns; record findings in audit log;
   update affected examples to primary-first form, or re-open §5.1.
2. Confirm parent blueprint and spin-off blueprint cross-references are
   self-evident in body text.

After all six §7 scope-freeze gates pass: flip blueprint status to
`scoped` and record the event in audit log.

### Phase 1: Test scaffolding (before any code change)

Add behavior tests codifying the §5.x LOCKED contracts. Tests should
fail on current code (TDD baseline) and pass after Phase 2 lands.

Target location: an appropriate test module under `src/kernel/tests/`,
following existing precedent.

Coverage (per §7 implementation gates):

- §5.1: single-primary `tx.entity(...)` allowed/rejected orders.
- §5.2: multi-primary upfront required; partial-primary handle rejected.
- §5.3: `default=<literal>` / `default_factory="uuid4"` / no-default
  primary-presence semantics; `sdk_get(...)` uuid4 rejection unchanged.
- §5.4: `bind(...)` rejects primary identity completion; accepts
  non-primary identity completion.
- §5.7: write-side rejection on incomplete coordinate; flat
  `fg.write.retract(asrt_id)` unaffected.
- Error message semantic contracts (per §5.1 / §5.2): entity-creation
  errors name missing primary identity; commit/preview/write retains
  `_ensure_handle_resolved` shape; no literal string assertions.

### Phase 2: Implementation (single implementation cycle)

Scope: tighten input validation in the SDK ergonomics layer. No
substrate, rule authoring, or read API changes.

Critical files:

- `src/kernel/sdk/batch.py`: extend `_materialize_identity_values` and
  `entity(...)` to enforce primary-presence at handle creation; extend
  `_bind_identity` to reject primary identity fields; preserve
  `_ensure_handle_resolved` shape for commit-time errors.

Out of scope by default:

- `src/kernel/application/schema_runtime.py`: no application selector or
  DTO behavior should change; touch only if a failing scoped test proves
  an SDK-layer fix is insufficient.

Implementation strategy invariants (per §5.9):

- Direct enforcement at the `tx.entity(...)` boundary.
- No feature flag, no deprecation warning, no `__future__`-style opt-in,
  no dual-mode coexistence.
- Single new error message at the entity-creation call site (semantic
  contract per §5.1).

### Phase 3: Documentation sync (same cycle as Phase 2)

In the same implementation cycle as Phase 2 (per §7 docs gate):

- Update affected SDK docs:
  - `src/kernel/sdk/docs/00_user_guide.en.md`
  - `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- Review the working design-point note
  [docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md](../../references/working/design-points/identity-primary-key-coordinate-semantics.zh.md)
  §6.3 / §6.6 and update only if the landed behavior changes or sharpens
  the working interpretation.

### Phase 4: Verification and close

1. Run the full kernel test suite; require green.
2. Verify every §7 implementation gate passes.
3. Confirm no diff under `src/kernel/authoring/` (per §5.8).
4. Confirm no archived release snapshot, existing `release/0.1.x`
   artifact, or `v0.1.0-rc.1` tag/release artifact is modified
   (per §6 repository safety invariants).
5. Fill §10 Outcome / Deviations with the final landed decision and any
   deviations from this plan.
6. Add audit log entries for Phase 1 / Phase 2 / Phase 3 / Phase 4
   events as they complete.
7. Flip blueprint status `scoped → implemented`.

## 9. Docs To Update

Only after decisions are locked:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `docs/references/working/design-points/identity-primary-key-coordinate-semantics.zh.md`
- `docs/README.md` only if a durable docs entry is added or promoted.

## 10. Outcome / Deviations

Final landed decision:

- Primary-first completion is implemented for SDK batch handles.
- `tx.entity(...)` now requires every primary identity field to be present
  after create-time materialization of literal defaults and
  `default_factory="uuid4"`.
- `bind(...)` remains mutating in-place completion and rejects any primary
  identity kwarg, even when the supplied value matches an already-bound
  primary identity.
- Entity/handle writes still require a complete full coordinate. Flat
  assertion-id retraction remains unaffected.

Final landed behavior:

- New SDK-layer validation lives in `src/kernel/sdk/batch.py`.
- No storage/substrate change: `idref_v1` remains full-coordinate
  (primary + non-primary identity fields).
- No read API change: full-coordinate `fg.read.get(...)` remains the
  lookup surface, and omitted uuid4 primary identity remains rejected by
  `sdk_get(...)`.
- No rule-authoring change and no diff under `src/kernel/authoring/`.
- New behavior coverage lives in
  `src/kernel/tests/test_sdk_batch_primary_identity.py`.
- SDK docs were synced in the same implementation cycle:
  `src/kernel/sdk/docs/00_user_guide.en.md` gained primary-first batch
  guidance and `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
  records the updated batch identity constraints.

Deviations from draft:

- The implementation chose the strictest §5.4-compatible interpretation:
  `bind(...)` rejects primary identity kwargs even when the supplied value
  equals the existing primary identity value. This prevents callers from
  using `bind(...)` as a primary-confirmation path and keeps the primary
  boundary exclusively at `tx.entity(...)`.
- The working tree already contained broader uncommitted
  `00_user_guide.en.md` source-truth cleanup before this implementation
  pass. This blueprint's docs sync in that file is limited to the
  primary-first batch paragraph; the broader existing user-guide diff is
  outside this blueprint's scope.
- Full unittest discovery still reports the pre-existing Problog
  cold-import circularity after running 1765 tests with 1 skipped. Focused
  primary/batch/read/schema tests pass, and `ruff` plus `git diff --check`
  are clean.

Deferred design questions:

- Primary-anchor/domain collection read API remains deferred to
  [2026-05-10_primary-anchor-domain-read.md](./2026-05-10_primary-anchor-domain-read.md).
- Branching domain-handle or logical-entity-handle semantics remain
  deferred to the spin-off or a future blueprint.
- No release-branch or rc.1 artifact update is part of this blueprint.

Archive notes:

- Blueprint is implemented locally but not archived in this pass. Archive
  after any desired post-implementation review and commit grouping.
