# Audit: T8-B-2 Souffle Form 1 Conformance

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-b-2-souffle-form1-conformance.md`
- Stage: draft
- Class: S/M-M pending Step 4.6
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus three untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-B-2 Souffle Form 1 conformance blueprint pair drafted | Triggered by T8-B-1 native lane completion; Q1-Q9 intentionally pending for source-backed Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-B-1 shipped native row Form 1 at `9e9a7f49` and T8-D documented the
  native shipped subset at `22891808`.
- T8-B scoped inventory deferred Souffle row-result alignment because the
  existing converter looked graph-shaped but adapter-local.
- Reviewer due diligence found that Souffle row support artifacts may be
  native-like internally even though their kind is `SOUFFLE_WITNESS_KIND`.
- Current implementation likely has three possible strategies: extend the
  native Form 1 helper, add a dedicated Souffle helper, or keep using/migrate
  the proof-tree converter.

This draft scan is not a Step 4.6 answer. It intentionally avoids selecting a
strategy before source-backed inventory verifies exact data shape and metadata
semantics.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which strategy should T8-B-2 use: trivial extension, dedicated helper, or converter reuse? | Pending Step 4.6. |
| Q2 | Do native Form 1 `engine_meta` fields apply to Souffle support artifacts? | Pending Step 4.6. |
| Q3 | What is the future role of `souffle_proof_tree_to_evidence_graph(...)`? | Pending Step 4.6. |
| Q4 | How should SDK support plumbing admit Souffle artifacts? | Pending Step 4.6. |
| Q5 | How should `_build_passed_row_evidence_graph(...)` dispatch after Souffle support lands? | Pending Step 4.6. |
| Q6 | What is the test matrix? | Pending Step 4.6. |
| Q7 | Are audit module docs updated in this cycle? | Pending Step 4.6. |
| Q8 | Does Souffle shipping trigger a T8-D round 2 user-docs follow-up? | Pending Step 4.6. |
| Q9 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Souffle support artifact is less native-like than expected | Trivial extension becomes unsafe | Verify exact fields and conventions in `engine_eval.py` and `_support.py`. |
| Native `engine_meta` shape is not semantically correct for Souffle | Shared helper may overstate behavior | Per-field compatibility table before implementation. |
| Existing Souffle converter is confused with row-result path | Candidate-side behavior may regress or user-facing claims may drift | Explicit converter keep/migrate/defer decision. |
| SDK plumbing becomes broad allow-any-support | Future unsupported adapter artifacts may be rendered incorrectly | Lock allowlist/denylist strategy. |
| T8-A validation gate is bypassed | Breaks C135 runtime invariant | Trace `_build_passed_row_evidence_graph(...)` dispatch before code. |
| T8-D docs expand into this runtime cycle | Scope creep | Decide follow-up vs in-cycle docs in Step 4.6. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] Strategy and class locked.
- [ ] Test matrix and verification gates locked.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
