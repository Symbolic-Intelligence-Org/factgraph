# Audit: T11.2.6 SDK Assertion Property Access

- Status: implemented
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-6-sdk-assertion-property-access.md`
- Stage: implemented
- Class: S/M (predicted narrow SDK ergonomics slice)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve the standing dirty set except for the scoped
  `facade.py` + companion test pair if implementation lands them.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `da2bdc0a` | T11.2.6 blueprint pair drafted | Triggered by T11.2.5 dirty verdict and T11.2.7 match decoupling. |
| 2026-05-26 | scoped | `fdf8a78b` | Step 4.6 assertion property inventory recorded | Layer split, reserved names, docs scope, tests, and land verdict locked. |
| 2026-05-26 | implemented | `1e7b4949` | SDK assertion property access landed | Property-style field assertions, compatibility shim, namespace proxy tests, and narrow docs sync. |

## 2. Pre-Draft Inventory

Read-only findings:

| Item | Finding |
|---|---|
| Dirty production diff | `src/factgraph/sdk/facade.py` currently has `+17/-2`: `AssertionRecordSet.__call__`, `FieldAssertions.active/history/all` properties, internal manager calls updated to property access, and `AssertionNamespace.__getattr__`. |
| Dirty companion test | `tests/test_sdk_assertion_record_set_view_filters.py` has `+15` covering property and legacy call forms for field and namespace access. |
| Match coupling | T11.2.7 final design says match returns `tuple[EntityCls snapshot, ...]`, not `AssertionRecordSet`; this facade slice is independent of match. |
| Docs surface | `docs/official/kernel/quickstart/assertions.md` and `src/factgraph/sdk/docs/*.en.md` contain a mix of `.active()` / `.all()` and `.active` / `.history` examples. Step 4.6 must decide docs sync scope. |
| Release blocker | Tracked dirty `facade.py` + test still block `scripts/release.sh` clean-tree dry-runs until this pair lands or is explicitly stashed/reverted. |

## 3. Step 4.6 Inventory Plan

The scoped inventory must fill:

1. exact `facade.py` dirty hunk summary with file/line anchors;
2. exact companion-test dirty hunk summary with file/line anchors;
3. current callable/method surface before accepting the change;
4. property + legacy-call compatibility matrix;
5. `AssertionNamespace.__getattr__` reserved-name / collision matrix;
6. docs grep table for assertion access forms;
7. focused test inventory and missing edge-case decision;
8. final land vs stash/revert verdict;
9. implementation file set;
10. release-note / T11.3 handoff wording.

## 3.1 Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Dirty hunk summary | `facade.py +17/-2`: adds `AssertionRecordSet.__call__`, turns `FieldAssertions.active/history/all` into properties, updates internal namespace aggregation to property access, and adds `AssertionNamespace.__getattr__`. Companion test `+15` verifies property + call compatibility. |
| 2 | Layer split | Graph-level `_SDKAssertionsManager.active()` / `.all()` remain methods (`store.py:459`, `:464`). Field-level `FieldAssertions.active/history/all` become properties (`facade.py:204-229`). Snapshot namespace proxy is `AssertionNamespace.__getattr__` (`facade.py:301-306`). |
| 3 | Compatibility matrix | `field.active` returns `AssertionRecordSet`; `field.active()` returns the same object through `AssertionRecordSet.__call__`; `field.all` and `field.all()` both map to history; `field.history` is the preferred explicit history name. |
| 4 | Collision matrix | Reserved `AssertionNamespace` public names are `field`, `active`, `all`, `by_id`, and `by_ids`; these win over schema-field proxy. Unknown fields raise `AttributeError`. Private/dunder names are not intended to proxy. |
| 5 | Docs grep | `docs/official/kernel/quickstart/assertions.md` and SDK docs still teach `.active()` / `.all()` in several assertion-access sections; some tests/docs already use `.active` / `.history`. Implementation should narrow-edit those sections. |
| 6 | Test inventory | Existing `tests/test_sdk_assertion_record_set.py` already exercises property form. Dirty companion test covers property/call identity for field and namespace field proxy. Missing edge coverage: unknown field and reserved-name collision. |
| 7 | Final verdict | Land as backward-compatible SDK assertion ergonomics. Do not stash/revert. |
| 8 | Implementation file set | `src/factgraph/sdk/facade.py`, `tests/test_sdk_assertion_record_set_view_filters.py`, and narrow assertion-access docs. No other dirty baseline files. |
| 9 | Release wording | "Field-scoped assertion sets now support property-style access (`snapshot.field('name').active`, `.history`) while legacy `.active()` / `.all()` call forms remain accepted." |
| 10 | T11.3 handoff | Landing this slice resolves the production/test dirty pair. Remaining tracked dirty docs/notebooks still require later handling or explicit stash/revert before release dry-run. |

## 4. Verification Plan

- `git status --short --branch`.
- `git diff -- src/factgraph/sdk/facade.py tests/test_sdk_assertion_record_set_view_filters.py`.
- Focused assertion tests selected by Step 4.6.
- `ruff` on touched Python file if implementation lands code.
- `git diff --check`.
- `git rev-parse master`.

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Land/stash/revert verdict recorded.
- [x] Compatibility decision reviewed.
- [x] Namespace collision decision reviewed.
- [x] Docs sync decision reviewed.
- [x] Closure notes filled.

## 6. Closure Notes

Implemented with `1e7b4949` (`feat(sdk): add property-style assertion access`).

Final landed scope:

- `AssertionRecordSet.__call__() -> self` preserves legacy field-level
  `.active()` / `.all()` calls.
- `FieldAssertions.active`, `.history`, and `.all` are property-first accessors.
- `AssertionNamespace.__getattr__` exposes collision-free schema fields through
  `snap.assertions.<field>`.
- Companion tests cover property access, legacy-call identity, known/unknown
  field proxy behavior, reserved method precedence, dunder lookup, and misuse
  chaining.
- Six assertion-access docs files were updated to teach property-first access
  while documenting legacy call compatibility.

Verification:

- `PYTHONPATH=src python -m unittest tests.test_sdk_assertion_record_set_view_filters`
  → `7 OK`.
- `python -m ruff check src/factgraph/sdk/facade.py tests/test_sdk_assertion_record_set_view_filters.py`
  → clean.
- `git diff --check` → clean.
- Field-level stale-call docs grep for `snap/snapshot.field(...).active()` and
  `.all()` returned zero hits.

No release machinery, match API, service, OpenAPI, notebook, external reference,
or unrelated dirty-baseline files were touched. Remaining dirty tracked files
are docs/notebooks deferred by T11.2.5; T11.3 still needs them landed,
stashed, or explicitly reverted before release dry-run.
