# Audit: T8-A Metadata + Validation Foundation

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-a-metadata-validation-foundation.md`
- Stage: draft
- Class: M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current modified docs/notebooks plus untracked reference material
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-A metadata/validation foundation blueprint pair drafted | Triggered by T8 split inventory after T7 bridge shipped; Q1-Q9 intentionally pending for Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8 split inventory archived at `a872fa5b` recommends T8-A as the first
  evidence implementation slice and identifies two possible internal steps:
  metadata builder/sufficiency checker, then validation/debug assertion.
- `EvaluateResult` currently owns the envelope and row context; graph metadata
  is built inline by `_evidence_metadata_for_row_result(...)`.
- `_explain_live_row(...)` passes metadata into the graph builder and catches
  `ValueError` as unsupported explanation output.
- `EvidenceGraph.__post_init__` already enforces structural graph validation.
- T7 added a strict 14-key metadata test and `run_id` absence check, so T8-A
  starts with an explicit backwards-compat regression anchor.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
builder/checker/debug assertion shape before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should T8-A ship as one blueprint or split into T8-A-1 / T8-A-2? | Pending Step 4.6. |
| Q2 | What is the central metadata builder shape? | Pending Step 4.6. |
| Q3 | What is the metadata sufficiency checker shape? | Pending Step 4.6. |
| Q4 | How should strict graph validation integrate with `_explain_live_row(...)`? | Pending Step 4.6. |
| Q5 | How should debug assertion be enabled? | Pending Step 4.6. |
| Q6 | Which tests are mandatory before implementation? | Pending Step 4.6. |
| Q7 | Are module docs or design docs required in this cycle? | Pending Step 4.6. |
| Q8 | What remains deferred to T8-B/T8-C/T8-D? | Pending Step 4.6. |
| Q9 | Are there stop/amend findings from source inventory? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Builder/checker shape becomes accidental public API | Future compatibility risk | Keep helper internal unless explicitly scoped otherwise. |
| Metadata contract drifts from 14 keys | Breaks T7/T6 contract | Use exact set-equality tests and inventory current callers. |
| `run_id` leaks into graph metadata | Violates sessionless envelope/graph separation | Preserve envelope-only invariant in tests. |
| Debug assertion breaks normal runtime | User-facing regression | Decide enablement path before implementation. |
| Validation gate expands into topology | Scope drift into T8-B/T8-C | Keep T8-A to metadata/validation foundation only. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] Scope split / implementation shape locked.
- [ ] Tests and verification gates locked.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
