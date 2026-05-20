# Task Blueprint: DB View Shape And Persistence

- Status: draft
- Created: 2026-05-20
- Last Updated: 2026-05-20
- Related Modules:
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/core/store/database.py`
  - `src/factgraph/core/store/ledger.py`
  - `src/factgraph/core/store/docs/README.md`
- Related Docs:
  - [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](../../audit/2026-05-20_database-view-design-vs-shipped-runtime.md)
  - [docs/audit/2026-05-20_post-q-db-view-synthesis.md](../../audit/2026-05-20_post-q-db-view-synthesis.md)
  - [docs/blueprints/archive/2026-05-20_db-identity-substrate.md](../archive/2026-05-20_db-identity-substrate.md)
  - [docs/blueprints/archive/2026-05-20_db-workspace-physical-layout.md](../archive/2026-05-20_db-workspace-physical-layout.md)
  - [docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md](../../decisions/2026-05-20_q3-tx-identity-primitives-decision.md)
  - [docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md](../../decisions/2026-05-20_q4-frozenassertionview-shape-decision.md)
  - [docs/decisions/2026-05-20_q5-view-revocation-composition-decision.md](../../decisions/2026-05-20_q5-view-revocation-composition-decision.md)
  - [docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md](../../decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md)
  - [docs/references/working/design-points/database-view-fg-layered-architecture.zh.md](../../references/working/design-points/database-view-fg-layered-architecture.zh.md)
- Audit Log:
  - [2026-05-20_db-view-shape-persistence.audit.md](./2026-05-20_db-view-shape-persistence.audit.md)

## 1. Problem

The DB identity substrate and workspace physical layout slices implemented Database identity, transaction objects, schema objects, `db/refs/head.txt`, and new-layout workspace storage. The view layer is still the shipped SDK-only compatibility shape:

- `FrozenAssertionView(name, asrt_ids)` has only `name` and `asrt_ids`.
- `_SDKViewsManager` stores views in memory only.
- View objects are explicitly not included in `fg.save(...)`.
- `fg.read.find(view=...)`, `fg.run(view=...)`, and `fg.eval.evaluate(view=...)` still reject `view`.

Q4 closed the target shape: `FrozenAssertionView` is a six-field anchored DTO with `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, and `view_digest`. Q5 closed the revocation composition rule: when a view is supplied, the scope universe is exactly `view.asrt_ids`; default no-view reads remain active-only.

This blueprint scopes the third implementable DB/view slice: canonical view DTO shape, deterministic view digest computation, anonymous content-addressed view object persistence under `views/objects/`, and compatibility boundaries for the shipped two-field SDK view registry.

## 2. Goals

- Introduce the canonical six-field `FrozenAssertionView` shape from Q4.
- Define deterministic `view_digest` computation over `db_id`, `base_tx_id`, `schema_digest`, and sorted `asrt_ids`;`name` must not affect identity.
- Persist anonymous immutable view objects under `views/objects/<view_digest>.json`.
- Use filesystem-safe raw hex filename segments while storing and validating the full digest token in object content.
- Treat `views/` as Database workspace view-object storage, not as the shipped SDK in-memory named view registry.
- Preserve shipped SDK in-memory view behavior as a compatibility surface until a later SDK migration explicitly replaces it.
- Respect Q5's scope-universe rule without implementing public `view=` read/evaluate APIs.
- Keep this slice limited to view shape and view persistence substrate.

## 3. Non-goals

- Do not implement public `fg.read.find(view=...)`, `fg.run(view=...)`, or `fg.eval.evaluate(view=...)` semantics. Those remain cross-doc blocked by the rule-expression redraft seams.
- Do not implement `FactGraph.attach(...)`, snapshot attach, or view-scoped attach.
- Do not implement `EvaluateResult`, `EvidenceGraph.metadata`, stale/out-of-scope failure envelopes, explain API behavior, or `rule_set_digest`.
- Do not implement a persistent named view registry. This slice stores anonymous content-addressed view objects; name lookup remains a future decision.
- Do not implement view set algebra.
- Do not change DB identity protocols, transaction object semantics, schema object semantics, or assertion identity.
- Do not change Q8/Q6 SavedRule or registry migration behavior.
- Do not remove the shipped in-memory `_SDKViewsManager` compatibility surface.
- Do not implement runtime projection/materialization policies beyond recording the Q5 scope-universe invariant.

## 4. Current Context

### 4.1 Shipped SDK view surface

`sdk/store.py` currently defines a two-field `FrozenAssertionView` dataclass with `name` and `asrt_ids` at `src/factgraph/sdk/store.py:88-92`.

`_SDKViewsManager` stores views in an in-memory dictionary, exposes create/update/delete/get/list methods, and records that views store assertion ids only and are not included in `fg.save(...)` at `src/factgraph/sdk/store.py:101-179`.

`_build_view_entry(...)` accepts either `asrt_ids` or assertion-like objects, normalizes them to ids, and returns the two-field SDK shape at `src/factgraph/sdk/store.py:2682-2717`.

The current read/evaluate surfaces reject view parameters:

- `fg.read.find(..., view=...)` rejects at `src/factgraph/sdk/store.py:1049-1050`.
- `fg.run(..., view=...)` rejects at `src/factgraph/sdk/store.py:1923-1924`.
- `fg.eval.evaluate(..., view=...)` rejects at `src/factgraph/sdk/store.py:2241-2244`.

### 4.2 Implemented DB workspace substrate

The implemented DB workspace layout reserves `views/` in `DatabaseWorkspacePaths` and the workspace manifest, but it does not create view objects or implement view persistence.

`core/store/database.py` now owns Database identity, new-layout workspace resolution, transaction objects, schema objects, and head resolution. It intentionally leaves `views/` as a later slice.

### 4.3 Decision target

Q4 locks the canonical design target:

- `FrozenAssertionView(name, db_id, base_tx_id, schema_digest, asrt_ids, view_digest)`.
- `view_digest` is a content digest, not a typed durable id.
- `name` is excluded from `view_digest`.
- The shipped two-field SDK view shape is a compatibility artifact, not the new design carrier.

Q5 locks the runtime composition boundary:

- with `view=` specified, the scope universe is exactly `view.asrt_ids`;
- no `is_active` re-filter is applied at the scope layer;
- projection/materialization policies may operate after scope selection but must not redefine the scope universe or change `view_digest`.

## 5. Proposed Shape

### 5.1 Canonical view DTO

Define a canonical `FrozenAssertionView` record with these fields:

- `name: str`
- `db_id: str`
- `base_tx_id: str`
- `schema_digest: str`
- `asrt_ids: tuple[str, ...]`
- `view_digest: str`

This record is the Database-owned durable view object shape. The implementation may place it in a core store module rather than in the SDK facade, but it must not create a second canonical public type with overlapping responsibility.

The shipped two-field SDK `FrozenAssertionView` may remain as a legacy compatibility adapter. If it remains, code and docs must clearly distinguish it from the canonical six-field durable view object.

### 5.2 View digest

`view_digest` is `sha256:<hex>`.

Semantic inputs are locked by Q4:

- domain marker for the subset-view protocol;
- `db_id`;
- `base_tx_id`;
- `schema_digest`;
- sorted `asrt_ids`.

The exact byte protocol for combining these semantic inputs is a preflight decision. It must be deterministic, domain-separated, cross-process reproducible, and must not include:

- `name`;
- local path;
- creation time;
- process id, host id, or random UUID;
- SQLite row ids;
- current active/revoked state outside the frozen `asrt_ids` set.

### 5.3 View object storage

Persist immutable anonymous view objects under:

```text
<workspace>/views/objects/<64hex>.json
```

Rules:

- `<64hex>` is the raw lowercase hex suffix from `view_digest.removeprefix("sha256:")`.
- Object content carries and validates the full `sha256:<hex>` `view_digest`.
- Filename/content mismatch is an error.
- Rewriting an existing view object with different content is an error.
- Rewriting an existing view object with identical content is idempotent.

The object content must include the six canonical DTO fields. Exact JSON field ordering and byte canonicalization are preflight decisions, but object bytes must be deterministic enough to support reliable validation.

### 5.4 Base snapshot and membership validation

Creating a durable view object requires a base Database snapshot:

- `db_id` comes from the Database.
- `base_tx_id` comes from the selected base `DatabaseValue`.
- `schema_digest` comes from the selected base `DatabaseValue`.
- `asrt_ids` are the requested frozen assertion ids.

Validation must ensure every `asrt_id` belongs to the same Database base snapshot. The exact validation mechanism is a preflight item because the implemented workspace layout has transaction objects but does not yet claim full rebuild-from-objects tooling for arbitrary historical snapshots.

This slice may choose to support only current-head view creation if historical snapshot membership cannot be validated without expanding scope.

### 5.5 Scope-universe invariant

The persisted view object records a frozen scope universe. Per Q5:

- If this view is later consumed by a view-scoped runtime surface, the scope universe is exactly `view.asrt_ids`.
- Revoked assertions listed in `view.asrt_ids` remain in that scope universe.
- Default no-view read/evaluate behavior remains active-only and is not changed by this slice.

This slice does not implement the public surfaces that consume the view. It only records the durable object semantics those later surfaces must consume.

### 5.6 Compatibility with shipped SDK views

The shipped `_SDKViewsManager` remains in-memory and name-based during this slice.

Allowed compatibility shapes:

- Keep SDK views fully unchanged and introduce durable view persistence under `Database` / core store APIs only.
- Add conversion helpers between the shipped two-field shape and the canonical six-field shape only when a Database base snapshot is supplied.
- Update documentation to warn that the two-field SDK view is not a durable view object.

Disallowed compatibility shapes:

- Treat the two-field SDK `FrozenAssertionView` as a valid new-layout persistent view.
- Persist SDK in-memory view names as a durable named registry in this slice.
- Infer `db_id`, `base_tx_id`, or `schema_digest` from a two-field view without an explicit Database base snapshot.

## 6. Boundaries And Invariants

- The canonical durable view object has exactly the six Q4 fields.
- `view_digest` excludes `name`.
- `view_digest` is derived from sorted `asrt_ids`, not from caller order.
- `view_digest` is independent of active/revoked state after the view is created.
- With a view supplied, Q5's scope universe is exactly `view.asrt_ids`; projection policies must not redefine that universe.
- The implementation must not implement public `view=` read/evaluate semantics in this slice.
- The implementation must not implement evidence/explain metadata behavior in this slice.
- The implementation must not add a persistent named view registry in this slice.
- View object filenames use raw lowercase hex suffixes; object contents carry full digest tokens.
- Existing shipped SDK in-memory view behavior must remain compatible unless an explicit migration plan is added to this blueprint first.

## 7. Acceptance

- [ ] A canonical six-field durable `FrozenAssertionView` shape exists and is documented.
- [ ] `view_digest` computation is deterministic, excludes `name`, and uses sorted `asrt_ids`.
- [ ] View objects persist under `views/objects/<64hex>.json`.
- [ ] View object filename/content mismatch is rejected.
- [ ] Existing view objects are write-once: identical content is idempotent; conflicting content errors.
- [ ] View creation validates Database/base snapshot membership or explicitly restricts scope to the validation surface implemented.
- [ ] The shipped SDK two-field view shape is not treated as a durable view object.
- [ ] No `fg.read.find(view=...)`, `fg.run(view=...)`, `fg.eval.evaluate(view=...)`, `FactGraph.attach(...)`, `EvidenceGraph.metadata`, failure envelope, or `rule_set_digest` implementation lands in this slice.
- [ ] Existing DB identity substrate and DB workspace layout tests still pass.
- [ ] New tests cover digest stability, name exclusion, sorted-id normalization, filename/content validation, and SDK compatibility boundaries.
- [ ] Affected module docs under `src/factgraph/core/store/docs/` and/or SDK docs are updated.

## 8. Implementation Plan

This section remains draft until implementation preflight completes. Before moving to `scoped`, perform a fresh source audit of the shipped SDK view manager, implemented Database workspace layout, transaction object read/write helpers, and current docs.

1. Define the canonical durable view record.
   - Decide module placement.
   - Decide whether to reuse the SDK class name directly or introduce a core durable record plus SDK adapter.
2. Define view digest bytes.
   - Choose the byte protocol for Q4's semantic inputs.
   - Validate `name` exclusion and sorted-id normalization.
3. Add `views/objects/` persistence helpers.
   - Use raw hex filename segments and full digest tokens in content.
   - Use write-once semantics consistent with tx/schema object helpers.
4. Add base snapshot validation.
   - Decide current-head-only versus historical snapshot support based on implemented tx-object/replay capability.
5. Add compatibility docs and tests.
   - Document the shipped two-field SDK view as compatibility-only.
   - Add tests proving no public `view=` API surface is implemented.

## 9. Docs To Update

- `src/factgraph/core/store/docs/README.md`
- SDK docs if the shipped view manager documentation changes
- `docs/blueprints/archive/README.md` after implementation and archive

## 10. Outcome / Deviations

Task completion will fill:

- final landed modules;
- exact view digest byte protocol;
- exact Database/base snapshot validation boundary;
- compatibility behavior for shipped SDK views;
- any carry-forward issues;
- archive commit references.
