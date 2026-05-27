# Audit: T8-D Round 2 Souffle User Docs

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-d-round2-souffle-user-docs.md`
- Stage: implemented
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-D round 2 Souffle user docs blueprint pair drafted | Triggered by T8-B-2 Q8 / closure follow-up; Q1-Q8 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | pending scoped commit | Source-backed inventory and Q1-Q8 completed | File scope locked to `evidence.md` + SDK `00_user_guide.en.md`; focused baseline ran 38 OK. |
| 2026-05-27 | implementation | `9616c28d` | Quickstart docs aligned | `evidence.md` now describes native + Souffle Form 1 and removes Souffle from the deferred row-level Form 1 boundary. |
| 2026-05-27 | implementation | `476eaabb` | SDK guide aligned | SDK summary now names native or Souffle rows as shipped and ProbLog/PyReason Form 1 graphs as future. |
| 2026-05-27 | closure | pending closure commit | Closure recorded | Verification 38 OK, `git diff --check` clean, dirty baseline preserved. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-D first round edited exactly `evidence.md` and SDK `00_user_guide.en.md`.
- T8-B-2 shipped Souffle row-level Form 1 through the same row-result helper
  shape as native.
- The evidence quickstart still appears to contain native-only Form 1 wording
  and a deferred Souffle row-level Form 1 boundary.
- The SDK user guide appears to contain a concise native-only Form 1 summary.
- Audit module docs were already updated by T8-B-2 and are not expected to be
  edited in this round.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify exact line refs
and file scope before implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Is the file scope exactly `evidence.md` + SDK `00_user_guide.en.md`? | Answered: yes; other docs either delegate to `evidence.md`, are high-level engine lifecycle docs, or are already aligned audit-module docs. |
| Q2 | Which exact `evidence.md` locations need native -> native + Souffle expansion? | Answered: §6 title/body, winning-path wording, deferred boundary line, and `EDGE_SUPPORTS` sentence only. |
| Q3 | Which exact SDK user-guide locations need native -> native + Souffle expansion? | Answered: §6 concise Form 1 summary lines only. |
| Q4 | How should the deferred row-level Form 1 boundary change? | Answered: remove Souffle from the future-work line; keep ProbLog/PyReason and all other boundaries unchanged. |
| Q5 | Does the existing ASCII Form 1 topology remain valid for Souffle? | Answered: yes; T8-B-2 shipped the shared Form 1 helper and existing node/edge kinds. |
| Q6 | Does the `winning_path_only` marker apply to Souffle user docs? | Answered: yes; T8-B-2 verified selected-branch-only Souffle support and protocol coverage. |
| Q7 | What verification is appropriate for docs-only round 2? | Answered: focused no-op evidence baseline, `git diff --check`, and dirty/sacred status checks. |
| Q8 | Should user docs mention the Souffle proof-tree converter boundary? | Answered: no; leave that audit-module implementer boundary in audit docs. |

## 4. Step 4.6 Inventory Results

| Area | Finding | Decision |
|---|---|---|
| Shipped Souffle behavior | T8-B-2 archive records Souffle row artifacts using the shared Form 1 row-result helper, existing Form 1 node/edge kinds, exact 14-key graph metadata, `run_id` absence, `winning_path_only`, and seed reuse. | Symmetric native -> native + Souffle wording is accurate. |
| Quickstart gap | `evidence.md` §6 still says shipped Form 1 is native-only and keeps Souffle in future row-level Form 1 alignment. | Edit only §6 wording and the single deferred boundary line. |
| SDK guide gap | `00_user_guide.en.md` §6 still summarizes Form 1 as native-only and treats adapter Form 1 as future. | Edit only the compact summary; keep quickstart as the detailed source. |
| Leave-alone docs | Nearby quickstart/SDK docs either link to `evidence.md`, discuss high-level engine lifecycle, or are already aligned audit-module references. | No other files in implementation scope. |
| Proof-tree boundary | Audit docs already explain that Souffle proof-tree readback remains the adapter converter path. | Do not mirror that implementer distinction in user docs. |
| Verification | Focused no-op baseline ran 38 tests OK. | Use the same command plus `git diff --check` and status checks for closure. |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Souffle behavior differs from native in a user-visible way | Symmetric text edit would overstate behavior | Verify T8-B-2 archive and current runtime/docs source. |
| Docs edit grows beyond two files | Scope creep for S-cycle | Count file scope and stop/amend if needed. |
| Deferred boundary accidentally teaches ProbLog/PyReason as shipped | User-facing contract drift | Explicit Current boundaries edit plan. |
| Docs duplicate quickstart detail in SDK guide | Future drift risk | Preserve quickstart-detail / SDK-summary split. |
| Audit module docs are edited unnecessarily | Duplicates T8-B-2 completed alignment | Treat audit docs as reference only unless Step 4.6 finds gap. |
| Dirty baseline is touched | Workflow violation | Stage only scoped blueprint/docs files. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q8 answered.
- [x] File scope and verification locked.
- [x] Closure notes filled.

## 7. Closure Notes

T8-D round 2 completed as a narrow mirror of T8-D first round:

- Implementation touched exactly two user-facing docs files:
  `docs/official/kernel/quickstart/evidence.md` and
  `src/factgraph/sdk/docs/00_user_guide.en.md`.
- Quickstart changed native-only Form 1 wording to native + Souffle, preserved
  the ASCII topology, preserved the metadata/failure-mode sections, and removed
  only Souffle from the deferred row-level Form 1 line.
- SDK guide kept the concise-summary role and changed future adapter wording to
  ProbLog/PyReason Form 1 only.
- Audit module docs were not edited; they were already aligned by T8-B-2.
- Verification: focused no-op evidence baseline 38 OK, `git diff --check`
  clean, dirty baseline still `4 M + 1 D + 3 U`.

The evidence track user-facing loop now reflects T8-A metadata validation,
T8-B-1 native Form 1, and T8-B-2 Souffle Form 1. T8-C remains the future lane
for ProbLog/PyReason enrichment.
