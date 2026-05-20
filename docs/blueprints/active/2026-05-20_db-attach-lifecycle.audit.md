# Task Blueprint Audit: DB Attach Lifecycle (Base Writable Form)

- Blueprint: [2026-05-20_db-attach-lifecycle.md](./2026-05-20_db-attach-lifecycle.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-20 | draft | Blueprint created | Scoped Slice 4 as Option α (base writable form only): introduce `FactGraph.attach(db)` classmethod, `fg.commit_assertions(...)` Database-routed write API, rejection of shipped Ledger-direct write paths on attached SDKStores, and SDK public exports for `AssertionInput` / `CommitResult` / `Database`. |
| 2026-05-21 | draft | Draft tightening applied | Applied review tightenings: cite fix (eleven top-level managers plus two `_SDKWhatIfManager` sub-managers), P1 (`Database.ledger` read-only property accessor), P2 (`MetaEntry` added to SDK exports alongside `AssertionInput`), T1 (`attach` carries `**kwargs` catch-all rejecting unknown kwargs with `SDKStoreError` rather than `TypeError`), T2 ("Ledger-direct" replaced with "Database-boundary-bypassing" wording across §1/§2/§4.3/§5.4), T3 (`_SDKViewsManager._sdk` back-reference scope localized to attached-runtime rejection guard with explicit non-attached invariance note). |

## Decision Notes

### 2026-05-20 — Initial Slice 4 scope (Option α)

Per the post-Q synthesis Slice 4 candidate and the Stage 0 source audit recorded in chat, Slice 4 implements only the Q2 base writable form `FactGraph.attach(db)`. The two scoped forms (`attach(db.as_of(tx_id))` and `attach(db, view=view)`) and the `ReadOnlyAttachmentError` type Q2 names are explicitly deferred to a later slice that will own the Q2 §13 ship-gate work.

Adopted Q decisions:

- Q1 (Database class boundary) — `attach` consumes a `Database` object, not a path or raw `Ledger`.
- Q2 (attach lifecycle) — option (a) classmethod-style constructor; base form writable; no `rules=`; multi-attach permitted; shipped constructors stay as compatibility.
- Q3 (tx identity primitives) — inherited from slice 1's `canonical_bytes_dbtx_v1` / `canonical_bytes_dbdata_v1` consumed by `Database.commit_assertions(...)`.
- Q7 (AssertionRecord shape) — inherited from slice 1's seven-field record produced by `Database.commit_assertions(...)`.

Q4, Q5, Q6, Q8 are not consumed in this slice. Their dependents (view-scoped form, view↔revocation composition, registry workspace migration, SavedRule deprecation) are out of scope.

### 2026-05-20 — Explicit exclusions

The draft deliberately excludes:

- snapshot form `attach(db.as_of(tx_id))` — blocked by absent Q1-territory `Database.as_of(...)`;
- view-scoped form `attach(db, view=view)` — blocked by Q2 §13 ship-gate requiring read-only enforcement on every write path;
- `ReadOnlyAttachmentError` type — no producer without a scoped form;
- routing shipped flat write methods (`fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.ingest` / `fg.add_schema_classes` / `fg.save_rule` / `fg.save_inference` / `fg.save`) through `Database.commit_assertions(...)` — reject rather than re-route, per §5.4 rationale;
- removal or deprecation of shipped `SDKStore.create / from_schema_classes / load`;
- changes to `_SDKViewsManager` in-memory two-field view shape or to slice 3 `Database.create_view(...)` substrate;
- public `view=` consumption surfaces (`fg.read.find` / `fg.run` / `fg.eval.evaluate`);
- evidence/explain metadata, failure envelope, `EvaluateResult` 5-field context, `rule_set_digest`;
- Q6 registry workspace migration and Q8 SavedRule deprecation;
- deeper multi-writable-attach concurrency invariants beyond independent head observation;
- workspace persistence routing for attached SDKStores (`fg.save(...)` is rejected on attached).

### 2026-05-20 — Open design questions surfaced from Stage 0

The Stage 0 audit identified three substantive OQs that the draft answers:

- **OQ-3** (`attach(db)` ↔ `SDKStore.__init__` integration): the draft chooses classmethod returning standard `SDKStore` with a new `_database` field, sharing managers and `Ledger` with the supplied `db`.  No subclass.
- **OQ-4** (write-path routing): the draft chooses reject-shipped-paths rather than re-route-through-Database.  Rationale in §5.4: re-routing every shipped write path is a separate Q1-boundary expansion slice;rejecting on attached preserves the slice scope and surfaces a clean Q1 boundary.
- **OQ-5** (shipped constructor coexistence): the draft chooses disjoint construction — attach-built SDKStores set `_database`, shipped-constructor SDKStores leave `_database` as `None`.  No mixed state.

These choices are open to preflight challenge.

### 2026-05-20 — Preflight items the draft leaves to preflight

The draft intentionally leaves several choices to preflight before `scoped`:

- exact placement of rejection guards on flat methods (early-return helper versus inline per method);
- whether `_SDKViewsManager` should gain a `_sdk` back-reference or receive the rejection check through a different mechanism (the draft picks the back-reference;preflight may revisit);
- whether schema mismatch in `attach` should error with `SDKStoreError` or a Database-layer error;
- whether the test file `tests/test_db_attach_lifecycle.py` should be split (lifecycle vs rejection vs multi-attach) or kept single;
- exact wording of the rejection error messages.

### 2026-05-21 — Draft tightening response to review

Review on `9b527d54` surfaced one cite-precision item, two substantive items (P1 `Database._ledger` private-field reach-around and P2 incomplete SDK exports for non-empty meta writes), and three tightenings (T1 attach signature inconsistency with `SDKStoreError` claim, T2 narrow "Ledger-direct" wording miscategorizing `_SDKViewsManager` in-memory mutation, T3 `_SDKViewsManager` back-reference scope clarity).  The tightening commit applies all six in one pass without changing the slice direction or scope:

- **Cite fix**: §4.1 now states eleven top-level private namespace managers instantiated in `__init__` at `:763-773`, with `_SDKWhatIfFactOverlayManager` and `_SDKWhatIfRuleManager` recorded as the two sub-managers built inside `_SDKWhatIfManager.__init__` at `:548-584`.  §5.6 and §6 wording updated accordingly.
- **P1 — `Database.ledger` accessor**: §5.2 introduces a new read-only property `Database.ledger` on `src/factgraph/core/store/database.py` returning `self._ledger`.  Documented as a runtime-binding accessor whose sole intended caller is `FactGraph.attach(...)`.  Avoids the SDK layer reaching into `Database._ledger` private field.  Property does not provide write semantics — Database writes still route through `Database.commit_assertions(...)`.  §6 invariants, §7 acceptance, and §8 plan (new step 1) updated.  Chosen over the "explicitly allow same-package private field bridge" alternative for cleaner test/document surface.
- **P2 — `MetaEntry` SDK export**: §5.7 adds `MetaEntry` to the SDK `__init__.py` export list alongside `AssertionInput` / `CommitResult` / `Database`.  `MetaEntry` is required at the SDK boundary because non-empty `AssertionInput.meta` is constructed from `MetaEntry` instances;exporting it keeps the attached commit API end-to-end usable without `factgraph.core.store` imports.  §7 acceptance and §8 plan (steps 2 and 9) updated.
- **T1 — `attach` `**kwargs` reject**: §5.1 signature gains an explicit `**kwargs: Any` catch-all and the Rules text records that any unknown keyword raises `SDKStoreError` rather than Python's default `TypeError`.  Chosen for consistency with the SDK's canonical boundary error type and to make rejection assertions testable.  §6 invariants, §7 acceptance, and §8 plan (step 5) updated.
- **T2 — "Ledger-direct" → "Database-boundary-bypassing"**: §1 problem, §2 goals, §4.3 surface enumeration heading prose, and §5.4 heading now use "shipped mutation paths that bypass the Database boundary" or equivalent wording.  `_SDKViewsManager.create / update / delete` is an in-memory dict mutation, not a Ledger write;the previous "Ledger-direct" wording risked miscategorizing it.  The Rule-2-bidirectionality check is now more precise.
- **T3 — `_SDKViewsManager._sdk` back-reference scope**: §5.4 adds a paragraph after the implementation note explicitly recording that the new `_sdk` back-reference is added solely for the attached-runtime rejection check;non-attached SDKStore `_SDKViewsManager` behavior — dict mutation semantics, attribute-RO via `FrozenSnapshotError`, two-field `FrozenAssertionView` return shape, and object identity — is unchanged.  §6 records the same invariant.

None of these changes expand the slice scope.  Snapshot form, view-scoped form, `ReadOnlyAttachmentError`, re-routing shipped flat write methods through `Database.commit_assertions(...)`, and `Database.as_of(...)` all remain Non-goals.
