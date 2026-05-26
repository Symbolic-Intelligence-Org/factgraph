# Audit: T11.2.6 SDK Assertion Property Access

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-6-sdk-assertion-property-access.md`
- Stage: draft
- Class: S/M (predicted narrow SDK ergonomics slice)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve the standing dirty set except for the scoped
  `facade.py` + companion test pair if implementation lands them.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | TBD | T11.2.6 blueprint pair drafted | Triggered by T11.2.5 dirty verdict and T11.2.7 match decoupling. |

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

## 4. Verification Plan

- `git status --short --branch`.
- `git diff -- src/factgraph/sdk/facade.py tests/test_sdk_assertion_record_set_view_filters.py`.
- Focused assertion tests selected by Step 4.6.
- `ruff` on touched Python file if implementation lands code.
- `git diff --check`.
- `git rev-parse master`.

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Land/stash/revert verdict recorded.
- [ ] Compatibility decision reviewed.
- [ ] Namespace collision decision reviewed.
- [ ] Docs sync decision reviewed.
- [ ] Closure notes filled.
