# Audit: T11.1 Attach-Based View Scope

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-1-attach-view-scope.md`
- Stage: draft
- Class: M (predicted)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | pending | Blueprint pair drafted | T11.1 starts the post-T5 Database/view phase from pushed T5.8 archive `efd65c0e`. Scope is attach-based view consumer only: SDK attach accepts view, attached reads/evaluate are scoped, method-level `view=` remains rejected. |

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
| §16 Step 2 view consumers | In scope only through attached runtime consumer. |
| C36-C44 migrated from rule-expression essay | Consume Database/view design; do not reopen T5 rule-expression contracts. |
| User simplification | Attach-based first, method-level deferred until demand emerges. |

## 6. Step 4.6 Pre-Implementation Inventory Plan

Run before scoped and record actual results:

| # | Check | Command shape | Expected / classification |
|---|---|---|---|
| 1 | Branch/base state | `git branch --show-current`, `git rev-parse HEAD`, `git status --short` | Confirm T11 branch from `efd65c0e`, dirty baseline preserved. |
| 2 | `FactGraph.attach` signature and rejected kwargs | `inspect.signature(FactGraph.attach)`, source read around `store.py:887` | Add `view=None`; preserve unknown kwarg rejection. |
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
- whether a minimal `database.md` must be created on this branch because the post-T5 docs slice is not in the base.

## 7. G7 Baseline Plan

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
| Scoped anchor | pending |
| Result | pending |
| Pytest policy | deferred unless specifically needed |

## 8. Draft Review Checklist

- [ ] Step 4.2 reviewer confirms attach-based-only scope.
- [ ] Step 4.2 reviewer confirms method-level `view=` remains rejected.
- [ ] Step 4.2 reviewer confirms stale/scope validation is in scope.
- [ ] Step 4.2 reviewer confirms no adapter/service/OpenAPI work.
- [ ] Step 4.2 reviewer confirms branch/base note is acceptable.
- [ ] Step 4.6 inventory results recorded before implementation.

## 9. Closure Notes

Pending.
