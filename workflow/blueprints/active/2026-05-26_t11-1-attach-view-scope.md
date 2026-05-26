# Task Blueprint: T11.1 Attach-Based View Scope

- Status: implemented
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M (predicted)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-26_t11-1-attach-view-scope.audit.md`
- Source decisions:
  - `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md`
  - T5.8 archive `efd65c0e`

## 0. Scope Locks

### In Scope

- Add attach-based view consumer support to the public SDK:
  - `FactGraph.attach(db, *, schema_classes=[...], view=None, ...)` accepts `view=None` or a frozen assertion view object.
  - `FactGraph.attach(db, view=view, schema_classes=[...])` materializes the snapshot identified by `view.base_tx_id`.
  - The attached runtime automatically scopes reads and evaluate calls to `view.asrt_ids`.
- Keep view-attached runtimes read-only:
  - `_attached_writable=False` for view-attached runtimes.
  - `fg.commit_assertions(...)` and existing attached write surfaces raise `SDKStoreError`.
  - Read-only state is visible enough for tests and diagnostics.
- Validate stale/scope conditions at attach time:
  - `view.schema_digest != db.schema_digest` rejects with `SDKStoreError`.
  - `view.db_id != db.db_id` rejects with `SDKStoreError`.
  - `view.base_tx_id` cannot be materialized from the Database rejects with `SDKStoreError`.
  - `view.asrt_ids` must exist in the materialized base snapshot; missing assertion ids reject without falling back to the full universe.
- Enforce the schema consistency chain before any scoped reads/evaluate:
  - `schema_digest(compile_schema_from_classes(schema_classes)) == db.schema_digest == view.schema_digest`.
  - If any link in that chain differs, attach fails before read/evaluate.
- Preserve the exact Database schema contract:
  - `schema_classes=[...]` must compile to the same `schema_digest` as the Database.
  - Incomplete `schema_classes` are not a view filter and must reject if their compiled schema digest differs.
  - Schema evolution, partial schema attach, and schema migration semantics are out of T11.1 unless shipped APIs already support them without weakening digest validation.
  - Step 4.6 must verify whether class order affects the compiled schema digest; if order-sensitive today, T11.1 records that shipped behavior rather than fixing it.
- Implement attach-scoped consumers:
  - `fg.read.find(...)` and `fg.read.get(...)` on a view-attached runtime see only assertions in the view.
  - `fg.eval.evaluate(...)` on a view-attached runtime evaluates against the same visible assertion set.
  - Existing method-level `view=` arguments remain rejected in T11.1.
- Improve method-level rejection messages:
  - `fg.read.find(..., view=...)` keeps rejecting but points to `FactGraph.attach(db, view=view)`.
  - `fg.eval.evaluate(..., view=...)` keeps rejecting with the same attach-based hint.
  - `fg.eval.explain(..., view=...)`, if it currently accepts or rejects by generic kwargs, must keep rejecting and mention attach-based view scope.
- Update tests:
  - Flip current frozen-view runtime-boundary tests from “view consumer not shipped” to “attach-based view consumer works.”
  - Add read-only write-attempt tests.
  - Add stale view rejection tests for schema mismatch, db mismatch, missing base transaction, and missing assertion ids where feasible.
  - Preserve method-level `view=` rejection tests with the new helpful message.
- Narrow docs:
  - Update or create the official quickstart Database/view page with a “View-scoped read via attach” section.
  - If this branch does not include the post-T5 quickstart Database page, add only the minimal page/section needed for T11.1 rather than importing unrelated docs commits.
  - Mention attach-based view scope from evidence/semantics docs only if current wording would otherwise contradict shipped behavior.

### Out of Scope

- Method-level `view=` consumer support for `fg.read.find(..., view=...)`, `fg.eval.evaluate(..., view=...)`, or manual explain.
- General `DatabaseValue` public attach support beyond what is strictly needed to materialize `view.base_tx_id`.
- Cross-doc S1-S6 / I10-A10 formal unblock.
- v0.2.0 release machinery.
- Writable sub-fg, branch/fork/merge, remote or multi-db views.
- Named durable view registry / A18.
- Adapter production edits.
- T1-T5 result, explanation, semantics, digest, SDK Rule, service, or OpenAPI contracts.
- New public DTOs.
- Broad docs migration.

### M-to-L / Stop-And-Amend Triggers

Pause and amend if implementation requires:

- broad Database or Store runtime redesign;
- multi-engine view-scope divergence that cannot be handled in SDK substrate only;
- changing the writable semantics of view-attached runtimes;
- weakening Database / `schema_classes` exact digest validation;
- implementing schema evolution, partial schema attach, or schema migration semantics;
- new public DTOs or public exception classes;
- adapter production edits;
- service or OpenAPI changes;
- changing T5 public result/evidence/explain contracts.

## 1. Inputs

The primary design source is `database-view-fg-layered-architecture.zh.md`.

- Section 9.1 defines `FactGraph.attach(db, view=view)` as a scoped read-only runtime over `view.base_tx_id`.
- Section 9.2 requires view-attached runtimes to be read-only.
- Section 12 defines view scope for read/evaluate/explain, but T11.1 intentionally implements only runtime-attached scope and keeps method-level `view=` deferred.
- Section 13 requires stale/scope validation before use and forbids silent fallback to the full universe.
- Section 16 Step 2 names `view=` consumers as the broader implementation route; user simplification for T11.1 narrows this to attach-based consumers first.

`rule-expression-and-proof-attempt.zh.md` explicitly moved C36-C44 view commitments to the Database/view design document. T11.1 should not reopen T5 rule-expression contracts; it only consumes T5 EvaluateResult/evidence substrate through the attached runtime’s visible assertion set.

Predecessor implementation truth:

- T5.8 archive `efd65c0e` is the branch base.
- `FactGraph.attach(...)` currently rejects unknown kwargs, including `view`.
- `fg.read.find(..., view=...)` currently rejects method-level `view=`.
- `fg.eval.evaluate(..., view=...)` currently rejects method-level `view=`.
- `tests/test_sdk_frozen_view_read_runtime_boundaries.py` currently locks the old rejection behavior and must be flipped or split.

Branch note:

- This T11 branch starts from pushed T5.8 archive `efd65c0e`. Local post-T5 quickstart Database docs commits on the T5 branch are not part of the T11 base unless explicitly merged later. T11.1 docs must not assume those commits exist.

## 2. Plan

### 2.1 Step 4.6 Inventory Before Implementation

Before scoped status, record:

- exact `FactGraph.attach(...)` signature and rejected kwargs;
- exact schema digest behavior when `schema_classes` are incomplete, reordered, or evolved relative to the Database;
- exact consistency-chain validation for `compiled_schema_digest`, `db.schema_digest`, and `view.schema_digest`;
- available Database APIs for materializing `view.base_tx_id`;
- durable Database-owned `FrozenAssertionView` shape and the SDK in-memory `FrozenAssertionView` shape;
- current `fg.read.find/get` implementation paths and where filtering by assertion id can be applied;
- current `fg.eval.evaluate(...)` path and where the visible assertion universe is chosen;
- all tests that currently assert method-level or runtime view rejection;
- docs locations that mention Database, durable views, `view=`, or unsupported view scope.

### 2.2 Accept `view=` At Attach Only

Update `FactGraph.attach(...)` to accept a keyword-only `view=None`.

Expected behavior:

- `view=None` preserves current writable Database attach behavior.
- `view=<durable Database view>` attaches to `view.base_tx_id`, validates scope, and returns a read-only runtime.
- SDK in-memory `fg.views.create(...)` objects may be accepted only if they can be safely associated with the attached Database snapshot; otherwise reject clearly. Step 4.6 must decide the exact policy based on shipped object fields.
- Unknown kwargs still reject.

### 2.3 Materialize The View Snapshot

Implementation should use existing Database internals or shipped helpers to load the snapshot for `view.base_tx_id`.

Required validation:

- match `db_id`;
- match `schema_digest` across compiled schema, Database, and view;
- materialize `base_tx_id`;
- verify `asrt_ids` are members of the base snapshot.

Implementation may improve schema mismatch diagnostics if this remains a small SDK boundary message change, for example by listing missing/extra entity names. This is optional and must not relax digest matching or become schema migration support.

The implementation must not silently use the current head if the base transaction is missing.

### 2.4 Apply Read Scope

The view-attached runtime should expose only `view.asrt_ids` through SDK read paths.

Implementation should prefer one shared substrate such as:

- an attached-runtime visibility filter stored on `SDKStore`;
- a Store/Ledger wrapper over the materialized snapshot;
- a narrow SDK facade filter, if that is sufficient and does not diverge from evaluate behavior.

Step 4.6 must identify the least invasive placement.

### 2.5 Apply Evaluate Scope

`fg.eval.evaluate(...)` on a view-attached runtime must use the same visible assertion universe as reads.

Required tests should prove a rule that would match in the full Database does not match when the required assertion is outside `view.asrt_ids`.

T11.1 does not need to add view metadata fields to `EvaluateResult` unless those fields already exist and can be populated without changing T5 contracts.

### 2.6 Preserve Method-Level Rejection

Method-level `view=` remains deferred:

- keep rejecting `fg.read.find(..., view=...)`;
- keep rejecting `fg.eval.evaluate(..., view=...)`;
- keep rejecting manual explain method-level `view=` if such a path exists.

Update messages to say: use `FactGraph.attach(db, view=view)` for view-scoped runtime reads/evaluation.

### 2.7 Narrow Docs

Docs should be limited to what T11.1 ships:

- attach-based view scope;
- read-only view-attached runtime;
- method-level `view=` remains deferred;
- stale/scope fail-fast behavior.

Do not perform broad Database/view docs migration in this slice.

## 3. Expected Code Changes

Likely production files:

- `src/factgraph/sdk/store.py`
  - `FactGraph.attach(..., view=None)` signature;
  - view validation/materialization helper(s);
  - read-only attached state;
  - read/evaluate visibility scope plumbing;
  - improved method-level `view=` rejection messages.
- Possibly `src/factgraph/sdk/facade.py` if SDK read filtering must happen below `SDKStore.find/get`.

Likely tests:

- `tests/test_sdk_frozen_view_read_runtime_boundaries.py`
  - flip rejection tests into attach-view behavior tests;
  - preserve method-level rejection tests with new hint.
- New or existing Database/view tests for:
  - attach view read-only;
  - view-scoped read;
  - view-scoped evaluate;
  - stale schema/db/tx/assertion validation.

Likely docs:

- `docs/official/kernel/quickstart/database.md` if present or created in this branch;
- possibly `docs/official/kernel/quickstart/evidence.md`;
- possibly `docs/official/kernel/quickstart/semantics.md`.

## 4. Minimum Test Matrix

- `FactGraph.attach(db, schema_classes=[...], view=view)` succeeds for a durable Database view.
- View-attached runtime is read-only and rejects `fg.commit_assertions(...)`.
- View-scoped `fg.read.find(...)` returns only entities whose visible assertions are in `view.asrt_ids`.
- View-scoped `fg.read.get(...)` does not hydrate hidden assertions.
- View-scoped `fg.eval.evaluate(...)` sees only view assertions.
- Method-level `fg.read.find(..., view=...)` rejects with attach-based hint.
- Method-level `fg.eval.evaluate(..., view=...)` rejects with attach-based hint.
- Schema mismatch rejects at attach.
- Incomplete or evolved `schema_classes` reject at attach.
- Reordered `schema_classes` behavior is tested or explicitly recorded according to shipped schema digest semantics.
- DB mismatch rejects at attach.
- Missing `base_tx_id` rejects at attach.
- Missing assertion id rejects at attach or first materialization, without full-universe fallback.

## 5. Verification Gates

- G7 baseline before feature: expected 180 tests OK from T5.8 archive.
- Focused attach-view tests pass.
- T5 public EvaluateResult / explanation / semantics focused tests remain green where touched.
- Touched-file ruff clean.
- `git diff --check` clean.
- No adapter, service, or OpenAPI files touched.
- Sacred `master` remains at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains isolated.

## 6. Risks

| Risk | Mitigation |
|---|---|
| View scope is applied to reads but not evaluate | Use shared visibility substrate or explicit paired tests proving both paths agree. |
| View attach silently falls back to current head | Validate and materialize `view.base_tx_id` at attach time. |
| Partial schema attach hides or mis-decodes data | Preserve exact schema digest matching and test incomplete/evolved schema classes. |
| SDK in-memory view object lacks enough durable metadata | Step 4.6 decides reject vs narrow support; no guessing. |
| Read-only enforcement misses a write path | Reuse existing attached write rejection helpers and add focused write-attempt tests. |
| Method-level `view=` accidentally becomes supported | Preserve rejection tests with attach-based hint. |
| Implementation drifts into service/OpenAPI/docs broad migration | Stop and amend; T11.1 is SDK attach-based only. |

## 7. Implementation Steps

1. Draft blueprint/audit and complete Step 4.2 review.
2. Run Step 4.6 inventory and move to scoped.
3. Record G7 baseline.
4. Implement attach-view validation and read-only state.
5. Implement read/evaluate visibility scope.
6. Update method-level rejection messages.
7. Update focused tests and narrow docs.
8. Run verification gates.
9. Step 4.7 review and fix if needed.
10. Closure and archive.

## 8. Reviewer Focus

- Whether attach-based `view` uses `base_tx_id`, not current head.
- Whether read and evaluate see the same scoped assertion universe.
- Whether view-attached runtimes are truly read-only.
- Whether stale/scope validation fails early.
- Whether method-level `view=` remains rejected with the attach-based hint.
- Whether SDK in-memory `fg.views` are not confused with durable Database views.

## 9. Acceptance

- [x] `FactGraph.attach(..., view=view)` works for supported durable views.
- [x] View-attached runtime is read-only.
- [x] Reads are scoped to `view.asrt_ids`.
- [x] Evaluate is scoped to `view.asrt_ids`.
- [x] Stale / mismatched views reject without fallback.
- [x] Method-level `view=` remains rejected with helpful attach-based guidance.
- [x] Focused tests and G7 baseline pass.
- [x] Docs describe attach-based view scope without promising method-level `view=`.
- [x] No adapter/service/OpenAPI files are touched.

## 10. Outcome / Deviations

### Commit References

- Draft: `7d17c7ae`
- Schema attach contract amend: `c4336762`
- Schema consistency-chain amend: `b30c9c59`
- Scoped inventory: `55b89f3b`
- G7 baseline: `88b3d729` (`180 tests in 0.122s, OK`)
- Feature: `76f46ada`

Step 4.7 review completed clean with `0 P0 / 0 P1`; no fix commit was required.

### Final Landed Code

T11.1 landed in 5 files with `394 insertions / 82 deletions`:

- `src/factgraph/sdk/store.py`
  - added `FactGraph.attach(db, *, schema_classes=[...], view=None, ...)`;
  - added a private read-only `_ViewScopedLedger` over durable Database views;
  - added durable view validation and base transaction materialization helpers;
  - made view-attached runtimes read-only for `fg.commit_assertions(...)`;
  - improved method-level `view=` rejection messages for read/evaluate/manual explain.
- `tests/test_db_attach_lifecycle.py`
  - added durable attach-view read, get, evaluate, frozen-base, read-only, stale-anchor, and method-level rejection coverage.
- `tests/test_sdk_frozen_view_read_runtime_boundaries.py`
  - rewrote old method-level view boundary tests for post-T5/T11 semantics and preserved rejection checks with attach-based hints.
- `docs/official/kernel/quickstart/namespace-map.md`
  - documented `FactGraph.attach(db, view=view)` as the Database-backed view consumer path.
- `docs/official/kernel/quickstart/persistence.md`
  - documented durable Database views, read-only attach behavior, and SDK in-memory view non-compatibility.

### Delivered Behavior

`FactGraph.attach(db, view=view)` now accepts durable Database views created by `db.create_view(...)`. SDK in-memory `fg.views.create(...)` views remain rejected because they do not carry `db_id`, `base_tx_id`, `schema_digest`, or `view_digest`.

Attach validates the full consistency chain before any read/evaluate entry:

```text
schema_digest(compile_schema_from_classes(schema_classes))
  == db.schema_digest
  == view.schema_digest
```

It also validates `view.db_id == db.db_id`, materializes `view.base_tx_id`, and checks that `view.asrt_ids` are present in that frozen base transaction. Missing or mismatched anchors raise `SDKStoreError`; there is no fallback to current head or the full assertion universe.

View-attached runtimes are read-only. Reads and native evaluate share the same visibility boundary through the attached Store/Ledger path that feeds `project_view_facts(...)`; `EvaluateResult.view_snapshot_digest` matches the durable view digest for the scoped runtime. Method-level `view=` on read/evaluate/manual explain remains deferred and rejected with a hint to use `FactGraph.attach(db, view=view)`.

### Test Gates

- Focused attach/view suite:
  - `PYTHONPATH=src python -m unittest tests.test_db_attach_lifecycle tests.test_sdk_frozen_view_read_runtime_boundaries -v`
  - Result: `20 tests`, OK.
- Focused T5/T11 evaluate preservation:
  - `PYTHONPATH=src python -m unittest tests.sdk.test_rule_expr_evaluate tests.test_db_attach_lifecycle tests.test_sdk_frozen_view_read_runtime_boundaries -v`
  - Result: `51 tests`, OK.
- G7 preservation:
  - same command as §5 baseline gate;
  - Result: `180 tests`, OK.
- Touched-file ruff:
  - `python -m ruff check src/factgraph/sdk/store.py tests/test_db_attach_lifecycle.py tests/test_sdk_frozen_view_read_runtime_boundaries.py docs/official/kernel/quickstart/namespace-map.md docs/official/kernel/quickstart/persistence.md`
  - Result: clean.
- `git diff --check`: clean.

### Deviations / Follow-Ups

- The branch base did not include the later post-T5 quickstart `database.md`, so T11.1 used narrow docs updates in `namespace-map.md` and `persistence.md` instead of editing a Database quickstart page.
- Schema digest order sensitivity was confirmed during Step 4.6 and preserved. Canonicalizing schema class order remains a separate optional polish slice.
- Helpful schema-delta diagnostics remain optional UX polish; T11.1 keeps exact digest validation as the hard contract.
- Method-level `view=` consumers remain v2-deferred per user simplification.
- `DatabaseValue` public attach support, cross-doc S1-S6 / I10-A10 unblock, release machinery, writable sub-fg, A11/A18, and schema migration/evolution remain future T11.x or v2 work.
