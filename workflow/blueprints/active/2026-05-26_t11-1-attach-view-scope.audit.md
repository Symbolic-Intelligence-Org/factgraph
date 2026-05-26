# Audit: T11.1 Attach-Based View Scope

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-1-attach-view-scope.md`
- Stage: scoped
- Class: M (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | pending | Blueprint pair drafted | T11.1 starts the post-T5 Database/view phase from pushed T5.8 archive `efd65c0e`. Scope is attach-based view consumer only: SDK attach accepts view, attached reads/evaluate are scoped, method-level `view=` remains rejected. |
| 2026-05-26 | scoped | pending | Step 4.6 inventory recorded | Inventory locked branch/base, exact schema digest behavior, order sensitivity, core vs SDK view shapes, attach/read/evaluate insertion points, stale validation boundaries, and docs/test targets. T11.1 remains M-class and attach-based only. |
| 2026-05-26 | baseline | pending | G7 baseline recorded | Ran inherited G7 preservation command at scoped anchor `55b89f3b`: 180 tests in 0.122s, OK. Pytest remains deferred. |

## 2. Source Chain

| Source | Reason |
|---|---|
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` §9.1 | Defines `FactGraph.attach(db, view=view)` as scoped read-only runtime over `view.base_tx_id`. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` §9.2 | Requires view-attached runtimes to be read-only. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` §12 | Defines broader view scope for read/evaluate/explain and equivalence with runtime-attached view; T11.1 narrows to attach-based path only. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` §13 | Defines stale/scope validation and forbids silent fallback. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md` §16 Step 2 | Names view consumer work; user decision narrows first slice to attach-based consumer. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | Confirms view commitments C36-C44 migrated out to Database/view design. |
| `src/factgraph/sdk/store.py` | Shipped SDK attach/read/evaluate implementation truth. |
| `tests/test_sdk_frozen_view_read_runtime_boundaries.py` | Current rejection tests to flip/preserve. |

## 3. Pre-Draft Shipped Source Reads

| Source | Snapshot |
|---|---|
| `src/factgraph/sdk/store.py:887-918` | `FactGraph.attach(db, *, schema_classes, default_row_format=None, **kwargs)` rejects all unknown kwargs, including `view`, then attaches current head as writable. |
| `src/factgraph/sdk/store.py:906-912` | `FactGraph.attach(...)` compiles `schema_classes`, computes `schema_digest`, and rejects if it differs from `db.schema_digest`; incomplete schema classes are rejected rather than treated as a read/view filter. |
| `src/factgraph/core/schema/schema_ir.py:62-78` | `schema_digest(...)` hashes canonical JSON with `sort_keys=True`; Step 4.6 must still verify whether upstream `compile_schema_from_classes([...])` list ordering changes entity/predicate arrays before canonicalization. |
| `src/factgraph/sdk/store.py:1064-1082` | `fg.read.find(...)` rejects method-level `view=` with old unsupported/policy wording. |
| `src/factgraph/sdk/store.py:2146-2150` | `evaluate(...)` rejects method-level `view=` and `policy=` with generic evaluate wording. |
| `tests/test_sdk_frozen_view_read_runtime_boundaries.py` | Current tests assert method-level `view=` rejection and legacy `run(..., view=...)` rejection. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md:395-421` | Design says attach to view materializes `view.base_tx_id` and is read-only. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md:535-587` | Design says view scope applies to read/evaluate/explain; T11.1 intentionally defers method-level `view=`. |
| `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md:669-693` | Implementation route calls out view consumers and read-only enforcement ship gate. |

## 4. Pre-Draft Risk Notes

| Risk | Current reading |
|---|---|
| Branch base mismatch | T11 branch starts at `efd65c0e`; local quickstart Database docs slice after T5.8 is not present. Docs work must not assume those commits unless user explicitly merges them. |
| Schema/classes mismatch | Database data is bound to the Database schema digest. Partial `schema_classes` could make reads appear to work while silently hiding or mis-decoding data, so T11.1 must preserve exact digest validation. |
| Schema digest order sensitivity | Canonical JSON sorts object keys, but entity/predicate arrays may still reflect compiler order. Step 4.6 must test reordered `schema_classes` and record shipped behavior rather than assuming set semantics. |
| SDK in-memory vs durable view | SDK `fg.views` historically has a smaller in-memory view shape. Step 4.6 must decide whether accepting SDK in-memory views is possible or should reject clearly. |
| Evaluate scoping | Current evaluate path may share Store/Ledger state with reads. Step 4.6 must identify the actual shared visibility point before implementation. |
| Attached writes | Existing attach writes are allowed for current-head attach. T11.1 must make only view-attached runtimes read-only without regressing normal attached Database writes. |
| Method-level `view=` | The design supports method-level in the future, but user simplification explicitly defers it. Tests must preserve rejection. |

## 5. Scope Mapping

| Design / user item | T11.1 treatment |
|---|---|
| §9.1 `FactGraph.attach(db, view=view)` | In scope. |
| §9.2 read-only view attach | In scope. |
| §12 method-level `view=` | Out of scope for T11.1; keep rejected with hint. |
| §13 stale / scope validation | In scope at attach time. |
| Database schema binding | Preserve shipped exact schema digest check; schema evolution and partial schema attach are out of scope. |
| Schema consistency chain | Enforce `compiled_schema_digest == db.schema_digest == view.schema_digest` before scoped runtime use. |
| §16 Step 2 view consumers | In scope only through attached runtime consumer. |
| C36-C44 migrated from rule-expression essay | Consume Database/view design; do not reopen T5 rule-expression contracts. |
| User simplification | Attach-based first, method-level deferred until demand emerges. |

## 6. Step 4.6 Pre-Implementation Inventory Plan

Run before scoped and record actual results:

| # | Check | Command shape | Expected / classification |
|---|---|---|---|
| 1 | Branch/base state | `git branch --show-current`, `git rev-parse HEAD`, `git status --short` | Confirm T11 branch from `efd65c0e`, dirty baseline preserved. |
| 2 | `FactGraph.attach` signature and rejected kwargs | `inspect.signature(FactGraph.attach)`, source read around `store.py:887` | Add `view=None`; preserve unknown kwarg rejection. |
| 2a | Schema digest exactness | Create/open/attach with complete, incomplete, and evolved `schema_classes`; compare compiled digest against `db.schema_digest` | Preserve exact digest rejection; partial schema attach out of scope. |
| 2b | Schema digest order stability | Create/open/attach with reordered complete `schema_classes`; inspect `compile_schema_from_classes` output ordering and digest | Record shipped behavior; do not fix order sensitivity unless already supported by substrate. |
| 2c | Schema consistency chain | Attach a durable view and verify `compiled_schema_digest == db.schema_digest == view.schema_digest`; mutate/mismatch one link where feasible | Reject before read/evaluate with `SDKStoreError`. |
| 2d | Schema mismatch diagnostics | Inspect current message and decide whether a small missing/extra entity hint is feasible | Optional secondary scope; no schema migration semantics. |
| 3 | Durable Database view shape | Introspect core `FrozenAssertionView` fields | Need `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest`. |
| 4 | SDK in-memory `FrozenAssertionView` shape | Introspect SDK `FrozenAssertionView` fields | Decide accept/reject policy for SDK view object. |
| 5 | Database snapshot materialization | Source read for `Database.head`, transaction/object lookup, `_ledger_for_attach` | Find safe way to materialize `view.base_tx_id`. |
| 6 | Assertion id existence check | Source read for Database assertions / ledger rows | Decide where to verify `view.asrt_ids`. |
| 7 | SDK read path | Source read `read.find/get` and `sdk.facade` | Identify visibility filter point. |
| 8 | SDK evaluate path | Source read `_candidate_sets_to_evaluate_result`, runtime evaluate helpers, Store/Ledger bridge | Identify visibility filter point shared with reads. |
| 9 | Attached write restrictions | Source read existing `_reject_attached_write`, `commit_assertions`, write methods | Ensure view-attached runtime read-only without regressing normal attach. |
| 10 | Method-level `view=` rejections | Grep `view=` rejection paths | Update messages only; do not enable method-level consumer. |
| 11 | Existing tests | `rg "view|FrozenAssertionView|attach" tests` | Classify tests to flip, preserve, or add. |
| 12 | Docs locations | `rg "view=|Database|attach\\(" docs/official/kernel src/factgraph/sdk/docs` | Identify narrow docs edits. |
| 13 | Adapter/service guard | `rg "view=" src/service docs/api src/factgraph/adapters` | Confirm no T11.1 implementation owner. |

Step 4.6 must decide:

- whether SDK in-memory `fg.views` objects are supported by attach or rejected;
- exact helper/location for view visibility filtering;
- exact stale/mismatch error messages;
- whether schema mismatch diagnostics should remain digest-only or include a small entity-set delta hint;
- whether a minimal `database.md` must be created on this branch because the post-T5 docs slice is not in the base.

## 7. Step 4.6 Pre-Implementation Inventory Results

| # | Check | Result | Source / evidence |
|---|---|---|---|
| 1 | Branch/base state | Current branch is `v0.2.0-t11-1-attach-view-scope-2026-05-26` at draft/amend lineage from `efd65c0e`; dirty baseline remains 6 modified + 1 untracked. | `git branch --show-current`; `git rev-parse --short HEAD`; `git rev-parse --short efd65c0e`; `git status --short`. |
| 2 | `FactGraph.attach` signature and rejected kwargs | Shipped signature is `(db, *, schema_classes, default_row_format=None, **kwargs)`; `view` is currently in `_ATTACH_REJECTED_KWARGS`. T11.1 must remove `view` from rejected kwargs only for attach and preserve all other unknown/constructor-style kwarg rejection. | `src/factgraph/sdk/store.py:126-137`, `src/factgraph/sdk/store.py:887-918`; `inspect.signature(FactGraph.attach)` confirmed. |
| 2a | Schema digest exactness | Complete matching class list attaches. Incomplete class list and evolved class list both reject with `SDKStoreError("schema mismatch...")`. `schema_classes` is not a filter. | Empirical `Database.create(schema_ir=compile_schema_from_classes([User, Account]))`; `FactGraph.attach(..., [User])` and `[UserEvolved, Account]` rejected. Source at `src/factgraph/sdk/store.py:906-912`. |
| 2b | Schema digest order stability | Reordered complete class list changes the compiled schema digest today. `[User, Account]` and `[Account, User]` produced different digests and reordered attach rejected. T11.1 records this shipped order-sensitive behavior; it must not fix order stability inside attach-view. | Empirical digests: `sha256:59dcc3...` vs `sha256:ea0185...`; `schema_digest(...)` source at `src/factgraph/core/schema/schema_ir.py:62-78`. |
| 2c | Schema consistency chain | Required chain is `compiled_schema_digest == db.schema_digest == view.schema_digest`. First link is shipped by current attach; second link must be added for `view=` attach before read/evaluate. | Current attach source `src/factgraph/sdk/store.py:906-912`; durable view fields include `schema_digest` at `src/factgraph/core/store/database.py:75-80`. |
| 2d | Schema mismatch diagnostics | Current attach message is digest-only. T11.1 may add a small missing/extra entity hint if cheap, but scoped implementation does not require it. | Current error source `src/factgraph/sdk/store.py:908-912`; empirical mismatch output confirmed digest-only message. |
| 3 | Durable Database view shape | Core durable `FrozenAssertionView` fields are `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest`. | `src/factgraph/core/store/database.py:74-81`; dataclass introspection confirmed. |
| 4 | SDK in-memory view shape | SDK in-memory `FrozenAssertionView` fields are only `name` and `asrt_ids`; it lacks `db_id`, `base_tx_id`, `schema_digest`, and `view_digest`. T11.1 should reject SDK in-memory views for `FactGraph.attach(db, view=...)` unless implementation discovers a safe Database association, which current shape does not provide. | `src/factgraph/sdk/store.py:116-118`; dataclass introspection confirmed. |
| 5 | Database snapshot materialization | Workspace Databases can read tx objects by id through private `_read_tx_object(...)`; `Database.head()` only exposes current head. No public `Database.as_of(...)` exists in this branch. Memory/legacy modes cannot create durable views. | `src/factgraph/core/store/database.py:724-765`, `src/factgraph/core/store/database.py:809-828`, `src/factgraph/core/store/database.py:478-512`. |
| 6 | Assertion id existence check | `Database.create_view(...)` validates `asrt_ids` exist as ledger claims at creation time, but T11.1 attach must still verify the view's ids against the materialized base snapshot and reject missing/stale ids without falling back to full universe. | Creation check at `src/factgraph/core/store/database.py:492-495`; active id helper at `src/factgraph/core/store/database.py:548-553`. |
| 7 | SDK read path | `fg.read.find/get` delegate to `sdk.facade`, which calls application `execute_read_request(...)` / `hydrate_entity(...)`; both build visible facts via `project_view_facts(store.ledger, store.schema_ir)`. Shared visibility should be applied at the attached `Store`/ledger boundary rather than as a read-only facade filter. | `src/factgraph/sdk/store.py:1039-1082`; `src/factgraph/application/entity_view.py:68-85`, `src/factgraph/application/entity_view.py:112-136`. |
| 8 | SDK evaluate path | Native evaluate also projects through `project_view_facts(store.ledger, store.schema_ir)` and `project_view_facts_with_witness(...)`. The same attached Store/ledger visibility boundary can cover reads and native evaluate. Engine adapter paths may consume store/ledger differently, so focused tests must at least prove native view scope and avoid adapter edits. | `src/factgraph/core/store/_evaluate.py:183-214`; public evaluate path at `src/factgraph/sdk/store.py:2146-2231`. |
| 9 | Attached write restrictions | Existing `_reject_attached_write(...)` rejects most write paths whenever `_database is not None`, but `fg.commit_assertions(...)` currently allows all attached runtimes. View-attached runtime must set `_attached_writable=False` and make `commit_assertions(...)` reject when attached read-only while preserving current writable Database attach. | `_attached_writable` init at `src/factgraph/sdk/store.py:721-722`; attach sets true at `src/factgraph/sdk/store.py:914-918`; commit path at `src/factgraph/sdk/store.py:1025-1031`; write guards at `src/factgraph/sdk/store.py:749-751`. |
| 10 | Method-level `view=` rejections | `fg.read.find(..., view=...)` and `evaluate(..., view=...)` reject today. `eval.explain(..., view=...)` rejects via unknown kwargs. T11.1 updates wording only, pointing to `FactGraph.attach(db, view=view)`. | `src/factgraph/sdk/store.py:1064-1076`, `src/factgraph/sdk/store.py:2146-2150`, `src/factgraph/sdk/store.py:2233-2243`. |
| 11 | Existing tests | Current tests lock old method-level view rejection and attach boundary behavior. T11.1 should preserve method-level rejection tests while adding/flipping attach-based view tests. | `tests/test_sdk_frozen_view_read_runtime_boundaries.py`; `tests/test_db_attach_lifecycle.py`. |
| 12 | Docs locations | This branch does not contain `docs/official/kernel/quickstart/database.md` because it starts at `efd65c0e`. Existing docs still describe SDK in-memory `fg.views` and method-level `view=` rejection. T11.1 docs should add minimal attach-view text without importing unrelated T5 branch docs commits. | `test -f docs/official/kernel/quickstart/database.md` returned absent; `rg` hits in `quickstart/assertions.md`, SDK docs, and namespace map. |
| 13 | Adapter/service guard | `src/service/runtime_v1.py` has unrelated request-level view/policy data; docs/api and adapters have no T11.1 implementation owner. No service/OpenAPI/adapter edits are scoped. | `rg "view=" src/service docs/api src/factgraph/adapters` classified as service/documentation only. |

Step 4.6 decisions:

- T11.1 remains one M-class attach-based slice.
- SDK in-memory `fg.views` objects are rejected for `FactGraph.attach(db, view=...)` by default because they do not carry Database identity, base transaction, schema digest, or view digest.
- The visibility boundary should be shared by read and evaluate through the attached Store/ledger path that feeds `project_view_facts(...)`.
- Schema exactness is order-sensitive today; T11.1 records and preserves that behavior instead of changing schema canonicalization.
- Method-level `view=` stays rejected with an attach-based hint.
- Minimal docs for attach-based view scope are in scope because `database.md` is absent on the T11 branch base.
- Optional schema delta diagnostics remain secondary and must not block or broaden the slice.

## 8. G7 Baseline Plan

Expected inherited baseline: 180 tests OK from T5.8 archive.

Command:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Baseline record fields to fill later:

| Field | Value |
|---|---|
| Branch | `v0.2.0-t11-1-attach-view-scope-2026-05-26` |
| Sacred state | `master = 562c74195df43e933bed92a3ff25de94dd8ce666` |
| Dirty baseline | 6 modified + 1 untracked preserved |
| Scoped anchor | `55b89f3b` |
| Command | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr tests.sdk.test_ruleexpr_inspect tests.sdk.test_rule_naming tests.application.protocol.test_rule_aggregate tests.test_branch_identity_rule_inspect tests.application.protocol.test_rule_expr_lowering tests.application.protocol.test_rule_expr_lowering_adapter tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr_head_validation -v` |
| Result | 180 tests in 0.122s, OK |
| Pytest policy | deferred unless specifically needed |

## 9. Draft Review Checklist

- [x] Step 4.2 reviewer confirms attach-based-only scope.
- [x] Step 4.2 reviewer confirms method-level `view=` remains rejected.
- [x] Step 4.2 reviewer confirms stale/scope validation is in scope.
- [x] Step 4.2 reviewer confirms no adapter/service/OpenAPI work.
- [x] Step 4.2 reviewer confirms branch/base note is acceptable.
- [x] Step 4.6 inventory results recorded before implementation.

## 10. Closure Notes

Pending.
