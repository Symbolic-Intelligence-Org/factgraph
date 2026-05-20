# Task Blueprint: DB Attach Lifecycle (Base Writable Form)

- Status: scoped
- Created: 2026-05-20
- Last Updated: 2026-05-21
- Related Modules:
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/sdk/__init__.py`
  - `src/factgraph/core/store/database.py`
  - `src/factgraph/core/store/__init__.py`
  - `src/factgraph/core/store/docs/README.md`
- Related Docs:
  - [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](../../audit/2026-05-20_database-view-design-vs-shipped-runtime.md)
  - [docs/audit/2026-05-20_post-q-db-view-synthesis.md](../../audit/2026-05-20_post-q-db-view-synthesis.md)
  - [docs/decisions/2026-05-20_q1-database-class-boundary-decision.md](../../decisions/2026-05-20_q1-database-class-boundary-decision.md)
  - [docs/decisions/2026-05-20_q2-attach-lifecycle-decision.md](../../decisions/2026-05-20_q2-attach-lifecycle-decision.md)
  - [docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md](../../decisions/2026-05-20_q3-tx-identity-primitives-decision.md)
  - [docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md](../../decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md)
  - [docs/audit/2026-05-21_db-attach-lifecycle-preflight.md](../../audit/2026-05-21_db-attach-lifecycle-preflight.md)
  - [docs/blueprints/archive/2026-05-20_db-identity-substrate.md](../archive/2026-05-20_db-identity-substrate.md)
  - [docs/blueprints/archive/2026-05-20_db-workspace-physical-layout.md](../archive/2026-05-20_db-workspace-physical-layout.md)
  - [docs/blueprints/archive/2026-05-20_db-view-shape-persistence.md](../archive/2026-05-20_db-view-shape-persistence.md)
  - [docs/references/working/design-points/database-view-fg-layered-architecture.zh.md](../../references/working/design-points/database-view-fg-layered-architecture.zh.md)
- Audit Log:
  - [2026-05-20_db-attach-lifecycle.audit.md](./2026-05-20_db-attach-lifecycle.audit.md)

## 1. Problem

Slices 1-3 introduced the `Database` identity substrate, the new-layout workspace physical layout, and durable view shape and persistence inside `src/factgraph/core/store/database.py`. The shipped `SDKStore` / `FactGraph` surface in `src/factgraph/sdk/store.py` is still unaware of `Database`: it has no import of `Database`, no `attach` lifecycle method, and its three shipped constructors `SDKStore.create / from_schema_classes / load` continue to build the runtime directly from a `Ledger` and an optional workspace `path`, bypassing the Q1 `Database` boundary established at the substrate layer.

Q2 closed the attach lifecycle pattern with three forms — base writable, snapshot read-only, view-scoped read-only — and locked their read/write semantics from design §9.1-§9.2. Q2 §13 adds a Step-5 ship-gate: any scoped form (snapshot or view) MUST NOT ship before read-only enforcement on every write path is in place. Implementing all three forms in one slice would either drag in `Database.as_of(...)` (Q1-territory snapshot primitive that does not yet exist) and full per-write-path RO enforcement, or violate Q2 §13.

This slice scopes the smallest implementable cut: the **base writable form** `FactGraph.attach(db)`. It wires `Database` into the SDK runtime, exposes a Database-routed write API on the attached runtime, blocks shipped mutation paths that bypass the Database boundary on attached SDKStores so that the Q1 boundary is materially enforced at runtime, and leaves the snapshot and view-scoped forms — together with the `ReadOnlyAttachmentError` type Q2 names — to a later slice that owns the Q2 §13 ship-gate work.

## 2. Goals

- Introduce `FactGraph.attach(db: Database)` as a classmethod-style constructor distinct from `SDKStore.create / from_schema_classes / load`, returning a writable `SDKStore` bound to a Q1 `Database` object.
- Define a Database-routed write API on attached SDKStores: `fg.commit_assertions(assertions: Sequence[AssertionInput]) -> CommitResult`, delegating to `Database.commit_assertions(...)`.
- Reject all shipped mutation paths that bypass the Database boundary on attached SDKStores so writes can only flow through the Q1 boundary;non-attached SDKStores keep these paths unchanged as compatibility surface.
- Validate base-form multi-attach: multiple `FactGraph.attach(db)` instances on the same `Database` succeed and observe `db.head()` independently at each `commit_assertions` call.
- Add `AssertionInput`, `CommitResult`, `MetaEntry`, and `Database` to the SDK public surface so attached SDKStores can be used without callers importing from `factgraph.core.store`.
- Preserve all slice 1-3 contracts (canonical byte protocols, `Database.commit_assertions` shape, `Database.head` resolution flow, `Database.create_view` substrate API, 6-field `FrozenAssertionView`) without modification.

## 3. Non-goals

- Do not implement `FactGraph.attach(db.as_of(tx_id))` snapshot read-only form.  `Database.as_of(...)` does not yet exist;adding it is Q1-territory snapshot primitive work owned by a later slice.
- Do not implement `FactGraph.attach(db, view=view)` view-scoped read-only form.  Per Q2 §13 ship-gate, that form requires read-only enforcement on every write path.
- Do not introduce the `ReadOnlyAttachmentError` type Q2 names.  No scoped form ships in this slice, so the named error has no producer.
- Do not route the shipped write methods (`fg.set`, `fg.add`, `fg.retract`, `fg.edit`, `fg.ingest`, `fg.add_schema_classes`, `fg.save_rule`, `fg.save_inference`, `fg.accept`, `fg.accept_many`, `fg.batch(...)`, and manager delegates) through `Database.commit_assertions(...)` on attached SDKStores.  Reject them instead;refactoring those paths to be Database-routed is a separate later slice (Q1 boundary expansion).
- Do not change non-attached SDKStore behavior.  `SDKStore.create / from_schema_classes / load` continue to use `Ledger` directly per the Q2 §6.10 compatibility commitment.
- Do not deprecate or remove `SDKStore.create / from_schema_classes / load`.  Compatibility surface stays available until a later release-engineering decision.
- Do not change the slice 3 `_SDKViewsManager` in-memory two-field view shape, slice 3 `Database.create_view(...)` substrate API, or any slice 3 SDK compatibility boundary.
- Do not implement `fg.read.find(view=...)`, `fg.run(view=...)`, `fg.eval.evaluate(view=...)` or any other public `view=` consumption surface.  Those remain cross-doc blocked.
- Do not implement evidence/explain metadata, failure envelope, `EvaluateResult` 5-field context, or `rule_set_digest` work.
- Do not change Q6 registry workspace migration or Q8 SavedRule deprecation behavior.
- Do not change Database identity protocols (`canonical_bytes_dbtx_v1`, `canonical_bytes_dbdata_v1`, `canonical_bytes_assertion_v1`, `canonical_bytes_view_v1`) or assertion record shape.
- Do not harden multi-writable-attach concurrency invariants beyond "each attached SDKStore independently observes `db.head()` at commit time".  Per Q2 §2.4, the deeper concurrency model is blueprint-level and may relax later.
- Do not implement `fg.save(...)` workspace persistence routing for attached SDKStores.  Attached SDKStores reject `fg.save(...)` in this slice;workspace persistence on attached runtimes is later work.

## 4. Current Context

### 4.1 Shipped `SDKStore` surface

`SDKStore` is defined at `src/factgraph/sdk/store.py:712-3431`. The `__init__` signature at `:722-777` accepts `classes` plus optional `store`, `schema_ir`, `artifact_store_root`, `registry_root`, `registry`, `workspace_path`, `default_row_format`. It builds an internal `Store` over a `Ledger` and instantiates eleven top-level private namespace managers in `__init__` at `:763-773` (`_SDKViewsManager`, `_SDKAssertionsManager`, `_SDKSchemaManager`, `_SDKReadManager`, `_SDKWriteManager`, `_SDKRulesManager`, `_SDKInferencesManager`, `_SDKEvalManager`, `_SDKWhatIfManager`, `_SDKAuditManager`, `_SDKPackageManager`). `_SDKWhatIfManager.__init__` (`:548-584`) internally constructs two sub-managers `_SDKWhatIfFactOverlayManager` (`:508-524`) and `_SDKWhatIfRuleManager` (`:526-546`).

The three shipped constructors are:

- `SDKStore.create(schema_classes, *, ledger=None, ledger_path=None, path=None, ...)` at `:782-834`.
- `SDKStore.from_schema_classes(classes, *, ledger=None, ledger_path=None, ...)` at `:836-857`.
- `SDKStore.load(path, *, schema_classes=None, default_row_format=None)` at `:859-895`.

All three route through `_from_schema_classes_impl(...)` at `:897` and ultimately bind a `Ledger` directly, with no `Database` object in scope. `FactGraph = SDKStore` is a literal alias at `:3432`.

### 4.2 Absence of `attach` and `Database` in the SDK layer

`grep "def attach" src/` returns no results. `grep "Database" src/factgraph/sdk/store.py` returns no results. The shipped SDK is fully Database-unaware.

### 4.3 Shipped write surfaces

The shipped `SDKStore` mutation paths that bypass the Database boundary are:

- `_SDKWriteManager.set / add / retract / edit` at `:328-354`, delegating to flat `SDKStore.set / add / retract / edit` (`fg.retract` flat impl at `:1886`).
- `_SDKSchemaManager.add / ingest` at `:267-281`, delegating to flat `SDKStore.add_schema_classes / ingest`.
- `_SDKRulesManager.save` at `:375-382`, delegating to flat `SDKStore.save_rule` at `:2092`.
- `_SDKInferencesManager.save` at `:417`, delegating to flat `SDKStore.save_inference` at `:2127`.
- `_SDKEvalManager.accept / accept_many` at `:489-505`, delegating to flat `SDKStore.accept / accept_many` at `:2350-2378`;those delegate into `Store.accept / accept_many` and ultimately write through the raw `Ledger`.
- `SDKStore.batch(...)` at `:1009-1012`, returning `SDKBatchTx`;`SDKBatchTx.commit(...)` applies a `BatchPlan` that can call flat write methods and can directly call `set_field(sdk.ledger, ...)` for record-exists operations.
- `_SDKViewsManager.create / update / delete` at `:121-168` (in-memory dict mutation).
- Flat `SDKStore.save(path=None)` at `:2063` (workspace persistence).

All of these either mutate the underlying `Ledger` or change SDKStore-owned in-memory state without participating in any `Database` transaction boundary.

### 4.4 Slice 1-3 Database substrate baseline (cross-slice contracts)

`src/factgraph/core/store/database.py` (1073 lines) provides the Database substrate:

- Canonical byte protocols at `:107-185`: `canonical_bytes_dbdata_v1`, `canonical_bytes_view_v1`, `canonical_bytes_dbtx_v1`, `canonical_bytes_assertion_v1`.
- Identity helpers at `:187-235`: `assertion_digest_for`, `asrt_id_for`, `view_digest_for`.
- `Database.__init__` at `:241-252` takes `ledger`, `db_id`, `schema_digest`, optional `workspace_paths`.
- `Database.create(path=..., *, schema_ir=...)` at `:254-258` dispatches to memory or workspace creation.
- `Database.open(path, *, schema_ir=...)` at `:323-332` dispatches to new-layout workspace or legacy-ledger open.
- `Database.head()` at `:371-387` returns a `DatabaseValue` with `db_id`, `tx_id`, `schema_digest`, `data_digest`;new-layout instances resolve via `head.txt → tx object → DatabaseValue` per slice 2 PF-2.
- `Database.commit_assertions(assertions: Sequence[AssertionInput])` at `:389-473` returns `CommitResult(parent_tx_id, value, assertions)`.
- `Database.create_view(name, asrt_ids, *, base=None)` at `:475-509` returns the six-field `FrozenAssertionView` per slice 3.

`core/store/__init__.py:5-23` exports `Database`, `DatabaseValue`, `AssertionInput`, `AssertionRecord`, `CommitResult`, `FrozenAssertionView`, the canonical byte prefixes, and the digest helpers.  Lazy `__getattr__` at `:26-54` defers the import until first use.

### 4.5 Q-contract backbone for this slice

- Q1 (Database class boundary) locks `Database` as a new application/storage layer above `Ledger`;`attach(db)` consumes a `Database` object, not a path or raw `Ledger`.
- Q2 (attach lifecycle) §1 picks option (a) — `attach(db)` is a new classmethod-style constructor distinct from shipped constructors.  §2.2 commits: base form is writable;writes commit to `db` current head via the Q1 boundary;exact write API surface is blueprint-level.  §2.3 forbids `rules=` per A15-D.  §2.4 allows multi-attach;deeper concurrency model is blueprint-level.  §6.10 keeps shipped constructors as compatibility.  §6.13 ship-gate applies only to scoped forms, not to base.
- Q3 (tx identity primitives) locks `canonical_bytes_dbtx_v1` and `canonical_bytes_dbdata_v1` byte protocols already consumed by `Database.commit_assertions(...)`.
- Q7 (AssertionRecord shape) locks the seven-field canonical durable record already produced by `Database.commit_assertions(...)`.

## 5. Proposed Shape

### 5.1 `FactGraph.attach(db)` classmethod

Add a new classmethod to `SDKStore`:

```python
@classmethod
def attach(
    cls,
    db: Database,
    *,
    schema_classes: list[type[Entity]],
    default_row_format: str | None = None,
    **kwargs: Any,
) -> "SDKStore":
    ...
```

Rules:

- `db` is a `Database` instance (Q1 boundary).  Path arguments and raw `Ledger` arguments are rejected.
- `schema_classes` is required and is compiled to a schema IR;the resulting `schema_digest` must equal `db.schema_digest` or `attach` raises `SDKStoreError`.  This comparison uses the Database object's `schema_digest` directly, not the underlying Ledger's compatibility metadata cache.  This protects against a caller attaching a Database whose schema does not match the Entity classes the SDK runtime will use.
- The attached `SDKStore` instance carries an internal `_database` reference and an `_attached_writable: bool = True` marker.  Internally it constructs the existing private namespace managers (eleven top-level plus the two `_SDKWhatIfManager` sub-managers) exactly as today, sharing the `Ledger` instance held by `db`.
- `attach` carries an explicit `**kwargs` catch-all that is rejected: any unknown keyword raises `SDKStoreError` rather than Python's default `TypeError`.  The reject list always includes `rules=`, `view=`, `policy=`, `path=`, `ledger=`, `ledger_path=`, `registry=`, `registry_root=`, `artifact_store_root=`, and `workspace_path=` — these names match shipped constructors and are explicitly forbidden so callers do not silently fall back to shipped behavior — and any other unknown name is also rejected with `SDKStoreError`.

Aliasing: because `FactGraph = SDKStore` (`:3432`), `FactGraph.attach(db, schema_classes=...)` is the user-facing form.

### 5.2 Internal SDKStore binding state

Two new fields on `SDKStore`:

- `_database: Database | None` — `None` for shipped constructors, set to the Q1 boundary instance for `attach(db)`.
- `_attached_writable: bool` — `True` when attached via base form;reserved for later scoped-form work that may set it to `False`.

Existing fields (`_classes`, `_store`, `_schema_ir`, `_schema_digest`, `_workspace_path`, `_authoring_registry`, manager instances, etc.) remain unchanged.  When `attach(db)` is used, `_workspace_path` is left as `None` and the existing `Ledger` from `db` is reused inside `_store`;no new workspace path is materialized.

The attached SDKStore acquires the underlying `Ledger` through a new internal Database accessor added by this slice in `src/factgraph/core/store/database.py`:

```python
def _ledger_for_attach(self) -> Ledger:
    return self._ledger
```

This is an internal runtime-binding bridge for `FactGraph.attach(...)`, not a public Database API and not an SDK export.  Returning a `Ledger` necessarily exposes a mutable substrate to the caller that receives it, so this method must not be documented as "write-safe" user surface.  Its purpose is to keep the SDK layer from reaching into `Database._ledger` while preserving the Q1 rule that Database writes route through `Database.commit_assertions(...)`.

Predicate helper:

```python
def _is_attached(self) -> bool:
    return self._database is not None
```

### 5.3 `fg.commit_assertions(...)` API

Add a flat method on `SDKStore`:

```python
def commit_assertions(
    self, assertions: Sequence[AssertionInput]
) -> CommitResult:
    if self._database is None:
        raise SDKStoreError(
            "fg.commit_assertions(...) is only available on FactGraph.attach(db) runtimes;"
            " use shipped fg.set / fg.add / fg.write.* for non-attached SDKStores"
        )
    return self._database.commit_assertions(assertions)
```

This is a thin pass-through to `Database.commit_assertions(...)`.  It honors the Q2 §6 criterion 3a invariant: writes commit to `db` current head via the Q1 `Database` boundary.

Inputs use the slice-1 `AssertionInput` shape (`pred_id`, `fact_tuple`, `meta`).  Output is the slice-1 `CommitResult` (`parent_tx_id`, `value`, `assertions`).  Neither type is wrapped or re-shaped at the SDK layer — Q1 boundary types pass through verbatim.

The method is NOT exposed on any namespace manager;it is a flat method on `SDKStore` to mirror the existing flat method style for write entry points (`fg.set`, `fg.add`, `fg.retract`, `fg.edit`).

### 5.4 Rejection of shipped Database-boundary-bypassing write methods on attached SDKStores

When `self._is_attached()` is true, the following methods raise `SDKStoreError` with a clear message pointing at `fg.commit_assertions(...)` or the appropriate alternative:

- Flat: `fg.set(...)`, `fg.add(...)`, `fg.retract(...)`, `fg.edit(...)`, `fg.ingest(...)`, `fg.add_schema_classes(...)`, `fg.save_rule(...)`, `fg.save_inference(...)`, `fg.accept(...)`, `fg.accept_many(...)`, `fg.batch(...)`, `fg.save(...)`.
- Manager-delegated: `_SDKWriteManager.set / add / retract / edit`, `_SDKSchemaManager.add / ingest`, `_SDKRulesManager.save`, `_SDKInferencesManager.save`, `_SDKEvalManager.accept / accept_many`, `_SDKViewsManager.create / update / delete`.

Implementation note: because manager methods already delegate to flat methods (e.g., `_SDKWriteManager.set` → `self._sdk.set`), placing the rejection guard at each flat method covers both flat callsites and manager callsites.  Manager methods that do not delegate to a flat method (`_SDKViewsManager.create / update / delete` mutate `self._views` directly) need their own guard that checks the parent SDKStore.

`fg.batch(...)` is rejected at batch construction time on attached SDKStores.  This avoids the `SDKBatchTx.commit(...)` path entirely, including the `BatchPlan.apply(...)` branch that can directly call `set_field(sdk.ledger, ...)` for record-exists operations even if flat `fg.set / add / retract` are guarded.

The new `_sdk` back-reference added to `_SDKViewsManager` for this rejection guard is the only change to `_SDKViewsManager`.  Implement it by changing `_SDKViewsManager.__init__` to accept `sdk: SDKStore`, setting both `_sdk` and `_views` with `object.__setattr__`, and changing `SDKStore.__init__` from `_SDKViewsManager()` to `_SDKViewsManager(self)`.  Non-attached SDKStore `_SDKViewsManager` behavior — dict mutation semantics, attribute-RO via `FrozenSnapshotError`, the two-field `FrozenAssertionView` returned to callers, and `_SDKViewsManager` object identity — is unchanged.  The back-reference is used only by the attached-runtime rejection check on `create / update / delete`.

The error message format:

```
attached FactGraph runtimes route writes only through fg.commit_assertions(...);
{method_name} is not available on attached runtimes
```

Reads (`fg.read.find`, `fg.read.get`, `fg.read.ref`, `fg.assertions.by_id / by_ids / active / all / field`, `fg.eval.run`, `fg.eval.evaluate`, `fg.eval.inspect_semantics`, `fg.what_if.*`, `fg.audit.*`, `fg.package.*`, `fg.rules.inspect / load / list / get`, `fg.inferences.load`, `fg.views.get / list`) work unchanged on attached SDKStores — they query the `Ledger` shared with `db` and observe the same data.  `fg.eval.accept` and `fg.eval.accept_many` are writes, not reads, and are rejected on attached runtimes.

Rationale for "reject" rather than "route through Database":

The Database-routed alternative would be to rewrite each shipped write method (`fg.set`, `fg.add`, `fg.eval.accept`, `fg.batch`, etc.) so that on attached SDKStores it internally constructs one or more `AssertionInput` values and calls `db.commit_assertions(...)`.  That refactor touches every write path (flat methods, eval accept methods, batch staging, manager delegates, and shared helpers like `_SDKWriteManager`) and changes the contract for what an assertion id looks like at the SDK boundary (slice-1 content-addressed `asrt_id` vs the shipped path).  It also reopens questions about meta handling, ingest validation, candidate acceptance, batch `RecordExistsOp`, and schema mutation rejection that span far beyond the Q2 attach lifecycle.  Per `feedback_smaller_batch_design_blueprints`, that work is its own slice;this slice defers it by rejecting rather than re-routing.

### 5.5 Non-attached SDKStore behavior preserved

When `self._database is None` (shipped constructors path):

- `fg.commit_assertions(...)` raises `SDKStoreError` explaining the method is only available on attached runtimes.
- All shipped flat write methods (`fg.set`, `fg.add`, `fg.retract`, `fg.edit`, `fg.ingest`, `fg.add_schema_classes`, `fg.save_rule`, `fg.save_inference`, `fg.accept`, `fg.accept_many`, `fg.batch`, `fg.save`) work unchanged.
- All shipped manager methods (`_SDKWriteManager.*`, `_SDKSchemaManager.*`, `_SDKRulesManager.*`, `_SDKInferencesManager.*`, `_SDKEvalManager.accept / accept_many`, `_SDKViewsManager.*`) work unchanged.
- All shipped constructors (`SDKStore.create / from_schema_classes / load`) work unchanged.

This honors Q2 §6.10: shipped `SDKStore.create / from_schema_classes / load` remain as compatibility constructors during migration.

### 5.6 Multi-attach pattern

Multiple `FactGraph.attach(db, schema_classes=...)` calls on the same `Database` are permitted.  Each returned SDKStore:

- Holds an independent reference to the same `db` and the same underlying `Ledger`.
- Observes `db.head()` independently at each `commit_assertions(...)` call (no caching across calls).
- Carries its own private namespace managers (eleven top-level plus the two `_SDKWhatIfManager` sub-managers), its own `_schema_ir` snapshot, and its own `_application_schema_index`.

When two attached SDKStores commit in interleaved order, each call sees whatever head exists at its own commit time;there is no batching, no transaction coordination, and no cross-instance head invalidation.  `Database.commit_assertions(...)` already enforces no-duplicate-asrt-id and head-advancement per slice 1;those guarantees are inherited.

Deeper concurrency invariants (head advancement notification, read-after-write visibility across attached instances, write serialization under contention) are deferred per Q2 §2.4 commitment that "Concurrency model for multiple writable base-form attaches is blueprint-level (Q2 does not lock it)".  This slice ships only the minimal invariant: each attach is independent;each commit checks current head at commit time.

Low-level `AssertionInput` commits do not populate SDK-local identity caches such as `_identity_values_by_e_ref`.  Attached runtimes should be tested against ledger-backed reads after `commit_assertions(...)`;callers should not assume that a low-level commit automatically creates managed SDK refs for later `fg.set / add` use.  This is an implementation-detail note, not a new public API commitment.

### 5.7 SDK public exports

Add to `src/factgraph/sdk/__init__.py` exports:

- `AssertionInput` (from `factgraph.core.store`)
- `CommitResult` (from `factgraph.core.store`)
- `MetaEntry` (from `factgraph.core.store`)
- `Database` (from `factgraph.core.store`)

`MetaEntry` is exported alongside `AssertionInput` because non-empty `AssertionInput.meta` requires `MetaEntry` instances at construction time;keeping `MetaEntry` accessible from `factgraph.sdk` lets callers use the attached commit API end-to-end without importing from `factgraph.core.store`.

This enables the canonical attach usage pattern:

```python
from factgraph import FactGraph
from factgraph.sdk import AssertionInput, Database

db = Database.create(path="./workspace", schema_ir=...)
fg = FactGraph.attach(db, schema_classes=[Person, Account])
result = fg.commit_assertions([
    AssertionInput(pred_id="...", fact_tuple=(("entity_ref", "..."), ...), meta=()),
])
```

`DatabaseValue`, `DatabaseError`, `DuplicateAssertionError`, `FrozenAssertionView`, `AssertionRecord`, and the canonical-byte / digest helpers are NOT added to SDK exports in this slice.  Per `feedback_narrow_public_api`, only types that the attached write API requires at the SDK boundary are surfaced;the rest remain accessible via `factgraph.core.store` for advanced users.

## 6. Boundaries And Invariants

- `FactGraph.attach(db)` is a classmethod;it is not an instance method.
- `attach` consumes a `Database` object;path arguments, raw `Ledger` arguments, and rules-loading arguments are rejected.
- An attached SDKStore's writes route only through `db.commit_assertions(...)`;no other write path produces an effect.
- The shipped flat write methods, eval accept paths, batch write paths, and manager delegates are rejected on attached SDKStores;they are unchanged on non-attached SDKStores.
- An attached SDKStore's `_database` field is non-`None`;a non-attached SDKStore's `_database` field is `None`.
- `attach` rejects schema mismatch between `schema_classes` and `db.schema_digest`.
- `attach` does NOT accept `rules=`, `view=`, `policy=`, `path=`, `ledger=`, `ledger_path=`, `registry=`, `registry_root=`, `artifact_store_root=`, or `workspace_path=`.  Unknown kwargs in the `**kwargs` catch-all raise `SDKStoreError` (not Python's default `TypeError`).
- Multiple attached SDKStores on the same `Database` are permitted;each independently observes `db.head()` at commit time.
- This slice does NOT introduce `ReadOnlyAttachmentError`;Q2 names it for scoped forms not shipped here.
- This slice does NOT add `Database.as_of(...)`, snapshot-form attach, view-scoped-form attach, or any public `view=` consumption surface.
- All slice 1-3 canonical byte protocols, identity helpers, Database APIs, and FrozenAssertionView shape are unchanged.
- The existing SDK manager namespaces, their attribute-RO `FrozenSnapshotError` behavior, and their public read methods are unchanged on both attached and non-attached SDKStores.
- `fg.views.get / list` work on attached SDKStores;`fg.views.create / update / delete` are rejected on attached SDKStores (Database-level view creation goes through `db.create_view(...)`, slice 3 API).
- `Database._ledger_for_attach()` is an internal runtime-binding bridge exposing the mutable `Ledger` substrate to `FactGraph.attach(...)` only.  It is not an SDK export and is not documented as public write-safe Database surface;Database writes still route through `Database.commit_assertions(...)`.
- The new `_sdk` back-reference on `_SDKViewsManager` is added solely to support the attached-runtime rejection guard;it is installed with `object.__setattr__` in `_SDKViewsManager.__init__(sdk)`. Non-attached `_SDKViewsManager` behavior, dict mutation semantics, attribute-RO via `FrozenSnapshotError`, two-field `FrozenAssertionView` return shape, and `_SDKViewsManager` object identity are unchanged.

## 7. Acceptance

- [ ] `FactGraph.attach(db: Database, *, schema_classes, default_row_format=None, **kwargs)` exists as classmethod on `SDKStore`.
- [ ] `FactGraph.attach(...)` rejects path arguments, raw `Ledger` arguments, `rules=`, `view=`, `policy=`, `path=`, `ledger=`, `ledger_path=`, `registry=`, `registry_root=`, `artifact_store_root=`, and `workspace_path=`.  Unknown kwargs raise `SDKStoreError` (not Python's default `TypeError`).
- [ ] `FactGraph.attach(db, schema_classes=...)` rejects schema mismatch between compiled `schema_classes` digest and `db.schema_digest`.
- [ ] `Database._ledger_for_attach()` exists as an internal attach bridge returning the `Ledger` substrate held by Database;`FactGraph.attach(...)` uses this method instead of `db._ledger` and it is not exported from `factgraph.sdk`.
- [ ] An attached SDKStore's `_database` is the supplied `Database` instance;a non-attached SDKStore's `_database` is `None`.
- [ ] `fg.commit_assertions(assertions)` on an attached SDKStore returns `CommitResult` from `db.commit_assertions(...)` verbatim.
- [ ] `fg.commit_assertions(...)` on a non-attached SDKStore raises `SDKStoreError`.
- [ ] On attached SDKStores, the following flat methods raise `SDKStoreError`: `fg.set`, `fg.add`, `fg.retract`, `fg.edit`, `fg.ingest`, `fg.add_schema_classes`, `fg.save_rule`, `fg.save_inference`, `fg.accept`, `fg.accept_many`, `fg.batch`, `fg.save`.
- [ ] On attached SDKStores, the following manager methods raise `SDKStoreError`: `_SDKWriteManager.set / add / retract / edit`, `_SDKSchemaManager.add / ingest`, `_SDKRulesManager.save`, `_SDKInferencesManager.save`, `_SDKEvalManager.accept / accept_many`, `_SDKViewsManager.create / update / delete`.
- [ ] On non-attached SDKStores, all shipped flat write methods and manager methods listed above work unchanged.
- [ ] On attached SDKStores, read methods (`fg.read.find / get / ref`, `fg.assertions.by_id / by_ids / active / all / field`, `fg.rules.inspect / load / list / get`, `fg.inferences.load`, `fg.views.get / list`, `fg.eval.run / evaluate / inspect_semantics`, `fg.what_if.*`, `fg.audit.*`, `fg.package.*`) work and reflect the data in the shared `Ledger`.
- [ ] Multiple attached SDKStores on the same `Database` succeed;each can commit independently and observes `db.head()` at its own commit time.
- [ ] `AssertionInput`, `CommitResult`, `MetaEntry`, and `Database` are exported from `factgraph.sdk`.
- [ ] No `ReadOnlyAttachmentError`, `Database.as_of(...)`, snapshot-form attach, view-scoped-form attach, or public `view=` consumption surface lands in this slice.
- [ ] Existing slice 1-3 tests still pass (`tests.test_db_identity_substrate`, `tests.test_sdk_frozen_assertion_view`).
- [ ] New tests cover: attach lifecycle (success + schema mismatch + unknown kwargs), `fg.commit_assertions` routing, rejection of each shipped write method on attached (including `fg.eval.accept / accept_many` and `fg.batch(...)`), preservation of each shipped write method on non-attached, multi-attach commit independence, and SDK public export presence.
- [ ] `src/factgraph/core/store/docs/README.md` and SDK store module docs reflect the attach lifecycle and its writable boundary.

## 8. Implementation Plan

This section reflects the post-preflight implementation plan after `docs/audit/2026-05-21_db-attach-lifecycle-preflight.md` and the follow-up blueprint amendments.  Per `feedback_audit_execution_discipline` Rule 1, implementation must still re-read source files at task-execution time.

1. Add internal `Database._ledger_for_attach()` to `src/factgraph/core/store/database.py` returning `self._ledger`.  Document as a runtime-binding bridge used by `FactGraph.attach(...)` only;do not export it from `factgraph.sdk` and do not describe it as public write-safe Database surface.
2. Add `Database`, `AssertionInput`, `CommitResult`, `MetaEntry` imports to `src/factgraph/sdk/store.py` (top-of-file, alongside existing `Ledger` import).
3. Add `_database: Database | None = None` and `_attached_writable: bool = False` fields to `SDKStore.__init__`;default values keep non-attached behavior identical.
4. Add `SDKStore._is_attached()` predicate helper.
5. Add `FactGraph.attach(db, *, schema_classes, default_row_format=None, **kwargs)` classmethod on `SDKStore`.  Do not route through `_from_schema_classes_impl(...)` for the authoritative schema check.  Instead: compile `schema_classes`, compute `schema_digest(schema_ir)`, compare directly to `db.schema_digest`, construct `Store(schema_ir=schema_ir, ledger=db._ledger_for_attach())`, instantiate `SDKStore(classes, store=..., default_row_format=...)`, then set `_database = db` and `_attached_writable = True`.  Reject `**kwargs` with `SDKStoreError` (not the default `TypeError`).
6. Add flat `SDKStore.commit_assertions(assertions)` method that checks `_is_attached()` and delegates to `db.commit_assertions(...)`.
7. Add rejection guards at the start of each shipped flat write method (`set`, `add`, `retract`, `edit`, `ingest`, `add_schema_classes`, `save_rule`, `save_inference`, `accept`, `accept_many`, `batch`, `save`) that raises `SDKStoreError` when `_is_attached()` is true.
8. Add rejection guards in `_SDKViewsManager.create / update / delete` that check the parent SDKStore.  Change `_SDKViewsManager.__init__` to `__init__(self, sdk: SDKStore)`, set `_sdk` with `object.__setattr__`, keep `_views` initialization via `object.__setattr__`, and change `SDKStore.__init__` from `_SDKViewsManager()` to `_SDKViewsManager(self)`. This back-reference is used only by the attached-runtime rejection check and does not affect non-attached `_SDKViewsManager` behavior.
9. Add `AssertionInput`, `CommitResult`, `MetaEntry`, `Database` to `src/factgraph/sdk/__init__.py` `__all__` and import block.
10. Add tests in `tests/test_db_attach_lifecycle.py` (new file) covering the acceptance items above.
11. Update `src/factgraph/core/store/docs/README.md` with an "Attach lifecycle" section pointing at the base writable form and noting that scoped forms remain deferred.
12. Update SDK store module docstring at `:712-720` to mention `FactGraph.attach(db)` as an alternative lifecycle for new code while keeping shipped constructors as compatibility.

## 9. Docs To Update

- `src/factgraph/core/store/docs/README.md`
- `src/factgraph/sdk/store.py` class docstring at `:712-720`
- `docs/blueprints/archive/README.md` after implementation and archive

## 10. Outcome / Deviations

To be filled at closure.
